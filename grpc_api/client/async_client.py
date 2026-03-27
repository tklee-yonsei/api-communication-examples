"""비동기 gRPC 클라이언트 구현."""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Optional, cast

import grpc

from communication.base import JobNotFoundError, JobRecord
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


class AsyncGrpcJobClient:
    """비동기 gRPC 클라이언트.

    asyncio와 함께 사용할 수 있는 비동기 버전입니다.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 50051,
    ) -> None:
        """클라이언트를 초기화합니다.

        Args:
            host: gRPC 서버 호스트
            port: gRPC 서버 포트
        """
        self.host = host
        self.port = port
        self.channel: Optional[grpc.aio.Channel] = None
        self.stub: Optional[jobs_pb2_grpc.JobServiceStub] = None

    async def connect(self) -> None:
        """서버에 연결합니다."""
        self.channel = grpc.aio.insecure_channel(f"{self.host}:{self.port}")
        self.stub = jobs_pb2_grpc.JobServiceStub(self.channel)

    async def close(self) -> None:
        """연결을 종료합니다."""
        if self.channel is not None:
            await self.channel.close()

    async def __aenter__(self) -> "AsyncGrpcJobClient":
        await self.connect()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def create_job(self, job_type: str, params: JobParams) -> JobRecord:
        """비동기로 작업을 생성합니다."""
        if self.stub is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        if job_type == "echo":
            request = create_echo_request(params)
            await self.stub.Echo(request)

            job_id = generate_fallback_job_id()
            return JobRecord(
                id=job_id,
                type=job_type,
                params=params,
                status="done",
            )

        elif job_type == "calc":
            request = create_calc_request(params)
            await self.stub.Calc(request)

            job_id = generate_fallback_job_id()
            return JobRecord(
                id=job_id,
                type=job_type,
                params=params,
                status="done",
            )

        elif job_type == "stats":
            request = create_stats_request(params)
            await self.stub.Stats(request)

            job_id = generate_fallback_job_id()
            return JobRecord(
                id=job_id,
                type=job_type,
                params=params,
                status="done",
            )

        elif job_type == "hash":
            request = create_hash_request(params)
            response = await self.stub.CreateHashJob(request)

            return JobRecord(
                id=response.job_id,
                type=job_type,
                params=params,
                status=cast(JobStatus, response.status),
            )

        elif job_type == "fib":
            request = create_fib_request(params)
            response = await self.stub.CreateFibJob(request)

            return JobRecord(
                id=response.job_id,
                type=job_type,
                params=params,
                status=cast(JobStatus, response.status),
            )

        else:
            request = create_echo_request(params)
            await self.stub.Echo(request)
            job_id = generate_fallback_job_id()
            return JobRecord(
                id=job_id,
                type=job_type,
                params=params,
                status="done",
            )

    async def get_job(self, job_id: str) -> JobRecord:
        """비동기로 작업 상태를 조회합니다."""
        if self.stub is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        request = jobs_pb2.JobId(id=job_id)

        try:
            response = await self.stub.GetJob(request)

            if response.status == "not_found":
                raise JobNotFoundError(f"Job {job_id} not found")

            return JobRecord(
                id=response.id,
                type=response.type,
                params={},
                status=cast(JobStatus, response.status),
            )

        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                raise JobNotFoundError(f"Job {job_id} not found") from e
            raise

    async def watch_jobs(self) -> AsyncGenerator[JobRecord, None]:
        """작업 상태 변경을 스트리밍으로 수신합니다.

        Yields:
            JobRecord: 상태가 변경된 작업
        """
        if self.stub is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        request = jobs_pb2.Empty()

        async for job_status in self.stub.WatchJobs(request):
            yield JobRecord(
                id=job_status.id,
                type=job_status.type,
                params={},
                status=cast(JobStatus, job_status.status),
            )
