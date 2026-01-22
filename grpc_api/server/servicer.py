"""gRPC JobService 구현체."""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingTypeArgument=false
# pyright: reportUnknownParameterType=false
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Optional

import grpc

from grpc_api.protos import jobs_pb2, jobs_pb2_grpc
from grpc_api.server.async_handlers import create_fib_job, create_hash_job
from grpc_api.server.sync_handlers import handle_calc, handle_echo, handle_stats
from grpc_api.server.utils import job_payload_to_proto
from grpc_api.server.watcher import WatcherManager
from rest_api.core.job_queue import JobQueue

logger = logging.getLogger(__name__)


class JobServiceServicer(jobs_pb2_grpc.JobServiceServicer):
    """gRPC JobService 구현체.

    REST API 서버와 동일한 핸들러를 재사용하여
    동기/비동기 작업을 처리합니다.
    """

    def __init__(self) -> None:
        """서비스를 초기화합니다."""
        # 여러 타입의 JobPayload를 저장할 수 있도록 object 사용
        # 실제로는 JobPayload[P, R, E]의 다양한 인스턴스가 저장됨
        self.store: dict[str, object] = {}
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
            job_status = job_payload_to_proto(job)
            await self.watcher_manager.broadcast(job_status)

    # ========================================
    # 동기 작업 (Unary RPC)
    # ========================================

    async def Echo(
        self,
        request: jobs_pb2.EchoRequest,
        context: grpc.aio.ServicerContext,
    ) -> jobs_pb2.EchoResponse:
        """Echo: 입력을 그대로 반환합니다."""
        return await handle_echo(request)

    async def Calc(
        self,
        request: jobs_pb2.CalcRequest,
        context: grpc.aio.ServicerContext,
    ) -> jobs_pb2.CalcResponse:
        """Calc: 사칙연산을 수행합니다."""
        return await handle_calc(request)

    async def Stats(
        self,
        request: jobs_pb2.StatsRequest,
        context: grpc.aio.ServicerContext,
    ) -> jobs_pb2.StatsResponse:
        """Stats: 리스트 통계를 계산합니다."""
        return await handle_stats(request)

    # ========================================
    # 비동기 작업 (Unary RPC)
    # ========================================

    async def CreateHashJob(
        self,
        request: jobs_pb2.HashRequest,
        context: grpc.aio.ServicerContext,
    ) -> jobs_pb2.CreateJobResponse:
        """해시 작업을 생성합니다."""
        job_queue = await self._ensure_queue_started()
        response, status_code, details = await create_hash_job(
            request, self.store, job_queue, self._on_job_complete
        )
        if status_code is not None:
            context.set_code(status_code)
            if details is not None:
                context.set_details(details)
        return response

    async def CreateFibJob(
        self,
        request: jobs_pb2.FibRequest,
        context: grpc.aio.ServicerContext,
    ) -> jobs_pb2.CreateJobResponse:
        """피보나치 작업을 생성합니다."""
        job_queue = await self._ensure_queue_started()
        response, status_code, details = await create_fib_job(
            request, self.store, job_queue, self._on_job_complete
        )
        if status_code is not None:
            context.set_code(status_code)
            if details is not None:
                context.set_details(details)
        return response

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

        return job_payload_to_proto(job)

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
            response.jobs.append(job_payload_to_proto(job))

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
                yield job_payload_to_proto(job)

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
