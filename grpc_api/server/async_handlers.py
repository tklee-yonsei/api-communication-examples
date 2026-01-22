"""비동기 작업 처리 헬퍼 함수."""

from __future__ import annotations

import logging
import uuid
from typing import Awaitable, Callable, Optional

import grpc

from grpc_api.protos import jobs_pb2
from grpc_api.server.types import JobPayload
from rest_api.core.job_queue import Job, JobQueue

# Job 완료 시 호출될 콜백 타입
OnCompleteCallback = Callable[[str], Awaitable[None]]

from rest_api.core.jobs import FibJobHandler, HashJobHandler
from rest_api.core.jobs.types import (
    BaseError,
    FibParams,
    FibResult,
    FibError,
    HashParams,
    HashResult,
)

logger = logging.getLogger(__name__)


async def create_hash_job(
    request: jobs_pb2.HashRequest,
    store: dict[str, object],
    job_queue: JobQueue,
    on_complete: OnCompleteCallback,
) -> tuple[jobs_pb2.CreateJobResponse, Optional[grpc.StatusCode], Optional[str]]:
    """해시 작업을 생성합니다.

    Args:
        request: Hash 요청
        store: 작업 저장소
        job_queue: 작업 큐
        on_complete: 완료 콜백

    Returns:
        tuple: (CreateJobResponse, StatusCode, details)
    """
    job_id = str(uuid.uuid4())
    logger.info(f"CreateHashJob: {job_id}")

    # 파라미터 준비
    data = dict(request.data)
    params = HashParams(**data)

    # 작업 저장
    job_payload: JobPayload[HashParams, HashResult, BaseError] = JobPayload(
        id=job_id,
        type="hash",
        params=params,
        status="pending",
    )
    store[job_id] = job_payload

    # 작업 큐에 제출
    job = Job(
        job_id=job_id,
        job_type="hash",
        handler=HashJobHandler,
        store=store,
        on_complete=on_complete,
    )

    if not await job_queue.submit(job):
        job_payload.status = "failed"
        job_payload.result = BaseError(error="Job queue is full")
        return (
            jobs_pb2.CreateJobResponse(job_id=job_id, status="failed"),
            grpc.StatusCode.RESOURCE_EXHAUSTED,
            "Job queue is full, try again later",
        )

    return (
        jobs_pb2.CreateJobResponse(job_id=job_id, status="pending"),
        None,
        None,
    )


async def create_fib_job(
    request: jobs_pb2.FibRequest,
    store: dict[str, object],
    job_queue: JobQueue,
    on_complete: OnCompleteCallback,
) -> tuple[jobs_pb2.CreateJobResponse, Optional[grpc.StatusCode], Optional[str]]:
    """피보나치 작업을 생성합니다.

    Args:
        request: Fib 요청
        store: 작업 저장소
        job_queue: 작업 큐
        on_complete: 완료 콜백

    Returns:
        tuple: (CreateJobResponse, StatusCode, details)
    """
    job_id = str(uuid.uuid4())
    logger.info(f"CreateFibJob: {job_id}, n={request.n}")

    # 파라미터 준비
    params = FibParams(n=request.n)

    # 작업 저장
    job_payload: JobPayload[FibParams, FibResult, FibError] = JobPayload(
        id=job_id,
        type="fib",
        params=params,
        status="pending",
    )
    store[job_id] = job_payload

    # 작업 큐에 제출
    job = Job(
        job_id=job_id,
        job_type="fib",
        handler=FibJobHandler,
        store=store,
        on_complete=on_complete,
    )

    if not await job_queue.submit(job):
        job_payload.status = "failed"
        job_payload.result = FibError(error="Job queue is full")
        return (
            jobs_pb2.CreateJobResponse(job_id=job_id, status="failed"),
            grpc.StatusCode.RESOURCE_EXHAUSTED,
            "Job queue is full, try again later",
        )

    return (
        jobs_pb2.CreateJobResponse(job_id=job_id, status="pending"),
        None,
        None,
    )
