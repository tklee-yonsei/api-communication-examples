"""gRPC 기반 비동기 작업 서버.

REST API 서버와 동일한 기능을 gRPC로 제공합니다.
동기 작업(Echo, Calc, Stats)과 비동기 작업(Hash, Fib)을 지원합니다.
"""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingTypeArgument=false
# pyright: reportUnknownParameterType=false
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from concurrent import futures
from typing import Any, Optional

import grpc

from grpc_api.protos import jobs_pb2, jobs_pb2_grpc
from rest_api.core.job_queue import Job, JobQueue
from rest_api.core.jobs import (
    CalcJobHandler,
    EchoJobHandler,
    FibJobHandler,
    HashJobHandler,
    StatsJobHandler,
)
from rest_api.core.jobs.types import (
    BaseError,
    CalcParams,
    EchoParams,
    FibParams,
    HashParams,
    StatsParams,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobPayload:
    """gRPC 작업 상태 레코드.

    Attributes:
        id: 작업 고유 ID
        type: 작업 종류 (hash, fib)
        params: 작업 파라미터
        status: 현재 상태 (pending, running, done, failed)
        result: 작업 결과 (완료 시)
    """

    def __init__(
        self,
        job_id: str,
        job_type: str,
        params: Any,
        status: str = "pending",
        result: Any = None,
    ) -> None:
        self.id = job_id
        self.type = job_type
        self.params = params
        self.status = status
        self.result = result


class WatcherManager:
    """작업 상태 변경을 구독하는 클라이언트를 관리합니다."""

    def __init__(self) -> None:
        self._watchers: list[asyncio.Queue[jobs_pb2.JobStatus]] = []
        self._lock = asyncio.Lock()

    async def add_watcher(self) -> asyncio.Queue[jobs_pb2.JobStatus]:
        """새로운 watcher를 추가합니다."""
        queue: asyncio.Queue[jobs_pb2.JobStatus] = asyncio.Queue()
        async with self._lock:
            self._watchers.append(queue)
        return queue

    async def remove_watcher(self, queue: asyncio.Queue[jobs_pb2.JobStatus]) -> None:
        """watcher를 제거합니다."""
        async with self._lock:
            if queue in self._watchers:
                self._watchers.remove(queue)

    async def broadcast(self, job_status: jobs_pb2.JobStatus) -> None:
        """모든 watcher에게 작업 상태를 브로드캐스트합니다."""
        async with self._lock:
            for queue in self._watchers:
                try:
                    await queue.put(job_status)
                except Exception:
                    pass


class JobServiceServicer(jobs_pb2_grpc.JobServiceServicer):
    """gRPC JobService 구현체.

    REST API 서버와 동일한 핸들러를 재사용하여
    동기/비동기 작업을 처리합니다.
    """

    def __init__(self) -> None:
        """서비스를 초기화합니다."""
        self.store: dict[str, JobPayload] = {}
        self.job_queue: Optional[JobQueue] = None
        self.watcher_manager = WatcherManager()
        self._queue_started = False

    async def _ensure_queue_started(self) -> JobQueue:
        """작업 큐가 시작되었는지 확인하고 반환합니다."""
        if self.job_queue is None:
            self.job_queue = JobQueue(max_workers=4, max_queue_size=100)
        if not self._queue_started:
            await self.job_queue.start()
            self._queue_started = True
        return self.job_queue

    async def _on_job_complete(self, job_id: str) -> None:
        """작업 완료 시 watcher들에게 알립니다."""
        job = self.store.get(job_id)
        if job is not None:
            job_status = self._job_payload_to_proto(job)
            await self.watcher_manager.broadcast(job_status)

    def _job_payload_to_proto(self, job: JobPayload) -> jobs_pb2.JobStatus:
        """JobPayload를 protobuf JobStatus로 변환합니다."""
        status = jobs_pb2.JobStatus(
            id=job.id,
            type=job.type,
            status=job.status,
        )

        if job.result is not None:
            if job.status == "failed" or job.status == "error":
                if isinstance(job.result, dict):
                    status.error.CopyFrom(
                        jobs_pb2.BaseError(
                            error=job.result.get("error", "Unknown error")
                        )
                    )
                elif hasattr(job.result, "error"):
                    status.error.CopyFrom(jobs_pb2.BaseError(error=job.result.error))
            elif job.type == "hash":
                result = job.result
                if isinstance(result, dict):
                    status.hash_result.CopyFrom(
                        jobs_pb2.HashResult(
                            algo=result.get("algo", ""),
                            input=result.get("input", ""),
                            digest=result.get("digest", ""),
                        )
                    )
            elif job.type == "fib":
                result = job.result
                if isinstance(result, dict):
                    status.fib_result.CopyFrom(
                        jobs_pb2.FibResult(
                            n=result.get("n", 0),
                            fib=result.get("fib", 0),
                        )
                    )

        return status

    # ========================================
    # 동기 작업 (Unary RPC)
    # ========================================

    async def Echo(
        self,
        request: jobs_pb2.EchoRequest,
        context: grpc.aio.ServicerContext,
    ) -> jobs_pb2.EchoResponse:
        """Echo: 입력을 그대로 반환합니다."""
        logger.info("Echo request received")

        # map을 dict로 변환
        data = dict(request.data)

        # EchoJobHandler 사용
        handler = EchoJobHandler()
        params = EchoParams(**data)
        result = await handler.execute(params)

        # 결과를 protobuf로 변환
        response = jobs_pb2.EchoResponse()
        for key, value in result.echo.items():
            response.echo[key] = str(value)

        return response

    async def Calc(
        self,
        request: jobs_pb2.CalcRequest,
        context: grpc.aio.ServicerContext,
    ) -> jobs_pb2.CalcResponse:
        """Calc: 사칙연산을 수행합니다."""
        logger.info(f"Calc request: {request.op} {request.a} {request.b}")

        handler = CalcJobHandler()
        params = CalcParams(op=request.op, a=request.a, b=request.b)  # type: ignore[arg-type]
        result = await handler.execute(params)

        # 에러 체크
        if hasattr(result, "error"):
            return jobs_pb2.CalcResponse(
                op=request.op,
                a=request.a,
                b=request.b,
                result=0.0,
                error=result.error,
            )

        return jobs_pb2.CalcResponse(
            op=result.op,
            a=result.a,
            b=result.b,
            result=result.result,
        )

    async def Stats(
        self,
        request: jobs_pb2.StatsRequest,
        context: grpc.aio.ServicerContext,
    ) -> jobs_pb2.StatsResponse:
        """Stats: 리스트 통계를 계산합니다."""
        logger.info(f"Stats request: {len(request.values)} values")

        handler = StatsJobHandler()
        params = StatsParams(values=list(request.values))
        result = await handler.execute(params)

        # 에러 체크
        if hasattr(result, "error"):
            return jobs_pb2.StatsResponse(error=result.error)

        return jobs_pb2.StatsResponse(
            count=result.count,
            min=result.min,
            max=result.max,
            sum=result.sum,
            mean=result.mean,
            median=result.median,
        )

    # ========================================
    # 비동기 작업 (Unary RPC)
    # ========================================

    async def CreateHashJob(
        self,
        request: jobs_pb2.HashRequest,
        context: grpc.aio.ServicerContext,
    ) -> jobs_pb2.CreateJobResponse:
        """해시 작업을 생성합니다."""
        job_id = str(uuid.uuid4())
        logger.info(f"CreateHashJob: {job_id}")

        # 파라미터 준비
        data = dict(request.data)
        params = HashParams(**data)

        # 작업 저장
        job_payload = JobPayload(
            job_id=job_id,
            job_type="hash",
            params=params,
            status="pending",
        )
        self.store[job_id] = job_payload

        # 작업 큐에 제출
        job_queue = await self._ensure_queue_started()
        job = Job(
            job_id=job_id,
            job_type="hash",
            handler=HashJobHandler,
            store=self.store,
            on_complete=self._on_job_complete,
        )

        if not await job_queue.submit(job):
            job_payload.status = "failed"
            job_payload.result = BaseError(error="Job queue is full")
            context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
            context.set_details("Job queue is full, try again later")
            return jobs_pb2.CreateJobResponse(
                job_id=job_id,
                status="failed",
            )

        return jobs_pb2.CreateJobResponse(
            job_id=job_id,
            status="pending",
        )

    async def CreateFibJob(
        self,
        request: jobs_pb2.FibRequest,
        context: grpc.aio.ServicerContext,
    ) -> jobs_pb2.CreateJobResponse:
        """피보나치 작업을 생성합니다."""
        job_id = str(uuid.uuid4())
        logger.info(f"CreateFibJob: {job_id}, n={request.n}")

        # 파라미터 준비
        params = FibParams(n=request.n)

        # 작업 저장
        job_payload = JobPayload(
            job_id=job_id,
            job_type="fib",
            params=params,
            status="pending",
        )
        self.store[job_id] = job_payload

        # 작업 큐에 제출
        job_queue = await self._ensure_queue_started()
        job = Job(
            job_id=job_id,
            job_type="fib",
            handler=FibJobHandler,
            store=self.store,
            on_complete=self._on_job_complete,
        )

        if not await job_queue.submit(job):
            job_payload.status = "failed"
            job_payload.result = BaseError(error="Job queue is full")
            context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
            context.set_details("Job queue is full, try again later")
            return jobs_pb2.CreateJobResponse(
                job_id=job_id,
                status="failed",
            )

        return jobs_pb2.CreateJobResponse(
            job_id=job_id,
            status="pending",
        )

    async def GetJob(
        self,
        request: jobs_pb2.JobId,
        context: grpc.aio.ServicerContext,
    ) -> jobs_pb2.JobStatus:
        """작업 상태를 조회합니다."""
        job = self.store.get(request.id)
        if job is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Job {request.id} not found")
            return jobs_pb2.JobStatus(id=request.id, status="not_found")

        return self._job_payload_to_proto(job)

    async def ListJobs(
        self,
        request: jobs_pb2.ListJobsRequest,
        context: grpc.aio.ServicerContext,
    ) -> jobs_pb2.ListJobsResponse:
        """전체 작업 목록을 조회합니다."""
        limit = request.limit if request.limit > 0 else 50

        all_jobs = list(self.store.values())
        recent_jobs = all_jobs[-limit:] if len(all_jobs) > limit else all_jobs
        recent_jobs = list(reversed(recent_jobs))

        response = jobs_pb2.ListJobsResponse(total=len(self.store))
        for job in recent_jobs:
            response.jobs.append(self._job_payload_to_proto(job))

        return response

    async def GetQueueStatus(
        self,
        request: jobs_pb2.Empty,
        context: grpc.aio.ServicerContext,
    ) -> jobs_pb2.QueueStatusResponse:
        """작업 큐 상태를 조회합니다."""
        job_queue = await self._ensure_queue_started()
        return jobs_pb2.QueueStatusResponse(
            queue_size=job_queue.get_queue_size(),
            is_full=job_queue.is_full(),
            max_workers=4,
        )

    # ========================================
    # 스트리밍 RPC (gRPC 고유 기능)
    # ========================================

    async def WatchJobs(
        self,
        request: jobs_pb2.Empty,
        context: grpc.aio.ServicerContext,
    ) -> AsyncGenerator[jobs_pb2.JobStatus, None]:
        """작업 상태 변경을 실시간으로 스트리밍합니다."""
        logger.info("New watcher connected")
        queue = await self.watcher_manager.add_watcher()

        try:
            # 초기 작업 목록 전송
            for job in self.store.values():
                yield self._job_payload_to_proto(job)

            # 새로운 업데이트 스트리밍
            while True:
                try:
                    job_status = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield job_status
                except asyncio.TimeoutError:
                    # 연결 유지를 위한 빈 상태 전송 (옵션)
                    continue
        except asyncio.CancelledError:
            pass
        finally:
            await self.watcher_manager.remove_watcher(queue)
            logger.info("Watcher disconnected")


class GrpcServer:
    """gRPC 서버 래퍼 클래스."""

    def __init__(self, host: str = "[::]", port: int = 50051) -> None:
        """서버를 초기화합니다.

        Args:
            host: 서버가 바인딩할 호스트 (기본값: [::] 모든 인터페이스)
            port: 서버가 수신할 포트 번호
        """
        self.host = host
        self.port = port
        self.server: Optional[grpc.aio.Server] = None
        self.servicer = JobServiceServicer()

    async def start(self) -> None:
        """서버를 시작합니다."""
        self.server = grpc.aio.server(
            futures.ThreadPoolExecutor(max_workers=10),
            options=[
                ("grpc.max_send_message_length", 50 * 1024 * 1024),
                ("grpc.max_receive_message_length", 50 * 1024 * 1024),
            ],
        )
        jobs_pb2_grpc.add_JobServiceServicer_to_server(self.servicer, self.server)
        self.server.add_insecure_port(f"{self.host}:{self.port}")

        await self.server.start()
        logger.info(f"gRPC server started on port {self.port}")

    async def stop(self, grace: float = 5.0) -> None:
        """서버를 종료합니다.

        Args:
            grace: 정상 종료 대기 시간(초)
        """
        if self.server is not None:
            await self.server.stop(grace)
            logger.info("gRPC server stopped")

    async def wait_for_termination(self) -> None:
        """서버가 종료될 때까지 대기합니다."""
        if self.server is not None:
            await self.server.wait_for_termination()


async def serve(port: int = 50051) -> None:
    """gRPC 서버를 실행합니다.

    Args:
        port: 서버가 수신할 포트 번호
    """
    server = GrpcServer(port=port)
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop()


def run_server(port: int = 50051) -> None:
    """동기적으로 서버를 실행합니다.

    Args:
        port: 서버가 수신할 포트 번호
    """
    asyncio.run(serve(port))


if __name__ == "__main__":
    run_server(port=50051)
