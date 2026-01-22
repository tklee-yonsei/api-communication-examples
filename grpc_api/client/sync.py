"""동기 gRPC 클라이언트 구현."""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false

from __future__ import annotations

from typing import Optional, cast

import grpc

from communication.base import (
    JobClient,
    JobNotFoundError,
    JobRecord,
)
from communication.types import JobParams, JobStatus
from grpc_api.client.utils import (
    create_calc_request,
    create_echo_request,
    create_fib_request,
    create_hash_request,
    create_stats_request,
    generate_fallback_job_id,
)
from grpc_api.protos import jobs_pb2, jobs_pb2_grpc


class GrpcJobClient(JobClient):
    """gRPC 서비스를 사용하는 JobClient 구현.

    REST API의 RestJobClient와 동일한 인터페이스를 제공합니다.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 50051,
        channel: Optional[grpc.Channel] = None,
    ) -> None:
        """클라이언트를 초기화합니다.

        Args:
            host: gRPC 서버 호스트
            port: gRPC 서버 포트
            channel: 기존 gRPC 채널 (테스트용)
        """
        self.host = host
        self.port = port
        self._owns_channel = channel is None

        if channel is not None:
            self.channel = channel
        else:
            self.channel = grpc.insecure_channel(f"{host}:{port}")

        self.stub = jobs_pb2_grpc.JobServiceStub(self.channel)

    def create_job(self, job_type: str, params: JobParams) -> JobRecord:
        """작업을 생성하고 레코드를 반환합니다.

        동기 작업(echo, calc, stats): 즉시 결과 반환
        비동기 작업(hash, fib): job_id 반환

        Args:
            job_type: 작업 종류 식별자
            params: 작업 수행에 필요한 파라미터

        Returns:
            JobRecord: 생성된 작업에 대한 기록
        """
        if job_type == "echo":
            # Echo 동기 작업 - 즉시 결과 반환
            request = create_echo_request(params)
            response = self.stub.Echo(request)
            # 결과를 params에 포함하여 반환 (동기 작업은 job_id 없음)
            result = {"echo": dict(response.echo)}
            return JobRecord(
                id="",  # 동기 작업은 job_id 없음
                type=job_type,
                params={"result": result},
                status="done",
            )

        elif job_type == "calc":
            # Calc 동기 작업 - 즉시 결과 반환
            request = create_calc_request(params)
            response = self.stub.Calc(request)
            result = {
                "op": response.op,
                "a": response.a,
                "b": response.b,
                "result": response.result,
            }
            if response.error:
                result["error"] = response.error
            return JobRecord(
                id="",
                type=job_type,
                params={"result": result},
                status="done",
            )

        elif job_type == "stats":
            # Stats 동기 작업 - 즉시 결과 반환
            request = create_stats_request(params)
            response = self.stub.Stats(request)
            if response.error:
                result = {"error": response.error}
            else:
                result = {
                    "count": response.count,
                    "min": response.min,
                    "max": response.max,
                    "sum": response.sum,
                    "mean": response.mean,
                    "median": response.median,
                }
            return JobRecord(
                id="",
                type=job_type,
                params={"result": result},
                status="done",
            )

        elif job_type == "hash":
            # Hash 비동기 작업
            request = create_hash_request(params)
            response = self.stub.CreateHashJob(request)

            return JobRecord(
                id=response.job_id,
                type=job_type,
                params=params,
                status=cast(JobStatus, response.status),
            )

        elif job_type == "fib":
            # Fib 비동기 작업
            request = create_fib_request(params)
            response = self.stub.CreateFibJob(request)

            return JobRecord(
                id=response.job_id,
                type=job_type,
                params=params,
                status=cast(JobStatus, response.status),
            )

        else:
            # 알 수 없는 타입은 echo로 처리
            request = create_echo_request(params)
            self.stub.Echo(request)
            job_id = generate_fallback_job_id()
            return JobRecord(
                id=job_id,
                type=job_type,
                params=params,
                status="done",
            )

    def get_job(self, job_id: str) -> JobRecord:
        """작업 상태를 조회합니다.

        Args:
            job_id: 조회 대상 작업의 식별자

        Returns:
            JobRecord: 요청한 작업의 현재 기록

        Raises:
            JobNotFoundError: 작업이 존재하지 않으면 발생
        """
        request = jobs_pb2.JobId(id=job_id)

        try:
            response = self.stub.GetJob(request)

            if response.status == "not_found":
                raise JobNotFoundError(f"Job {job_id} not found")

            # 결과 추출
            result = self._extract_job_result(response)

            return JobRecord(
                id=response.id,
                type=response.type,
                params={"result": result} if result else {},
                status=cast(JobStatus, response.status),
            )

        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                raise JobNotFoundError(f"Job {job_id} not found") from e
            raise

    def _extract_job_result(
        self, response: jobs_pb2.JobStatus
    ) -> Optional[dict[str, object]]:
        """JobStatus 응답에서 결과를 추출합니다."""
        # oneof result 필드 확인
        which_result = response.WhichOneof("result")

        if which_result == "hash_result":
            hr = response.hash_result
            return {
                "algo": hr.algo,
                "input": hr.input,
                "digest": hr.digest,
            }
        elif which_result == "fib_result":
            fr = response.fib_result
            return {
                "n": fr.n,
                "fib": fr.fib,
            }
        elif which_result == "error":
            return {"error": response.error.error}

        return None

    def close(self) -> None:
        """채널을 닫아 네트워크 리소스를 해제합니다."""
        if self._owns_channel:
            self.channel.close()

    # ========================================
    # 추가 gRPC 전용 메서드
    # ========================================

    def get_queue_status(self) -> dict[str, object]:
        """작업 큐 상태를 조회합니다.

        Returns:
            dict: 큐 상태 정보
        """
        request = jobs_pb2.Empty()
        response = self.stub.GetQueueStatus(request)

        return {
            "queue_size": response.queue_size,
            "is_full": response.is_full,
            "max_workers": response.max_workers,
        }

    def list_jobs(self, limit: int = 50) -> dict[str, object]:
        """전체 작업 목록을 조회합니다.

        Args:
            limit: 반환할 최대 작업 수

        Returns:
            dict: 작업 목록과 총 개수
        """
        request = jobs_pb2.ListJobsRequest(limit=limit)
        response = self.stub.ListJobs(request)

        jobs = []
        for job_status in response.jobs:
            jobs.append(
                {
                    "id": job_status.id,
                    "type": job_status.type,
                    "status": job_status.status,
                }
            )

        return {
            "jobs": jobs,
            "total": response.total,
        }
