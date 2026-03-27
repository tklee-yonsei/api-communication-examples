"""공통 통신 인터페이스 및 비즈니스 로직 패키지.

이 패키지는 모든 통신 방식(REST, gRPC, WebSocket)에서 공통으로 사용되는
인터페이스와 비즈니스 로직을 제공합니다.
"""

from __future__ import annotations

from communication.base import (
    JobClient,
    JobNotFoundError,
    JobRecord,
    JobRequest,
)
from communication.types import JobId, JobParams, JobStatus, Result

# 공통 비즈니스 로직 export
from communication.job_queue import Job, JobQueue, get_job_queue
from communication.jobs import (
    CalcJobHandler,
    EchoJobHandler,
    FibJobHandler,
    HashJobHandler,
    StatsJobHandler,
)
from communication.jobs.types import (
    BaseError,
    CalcError,
    CalcParams,
    CalcResult,
    EchoParams,
    EchoResult,
    FibError,
    FibParams,
    FibResult,
    HashParams,
    HashResult,
    JobResult,
    StatsError,
    StatsParams,
    StatsResult,
)

__all__ = [
    # Base
    "JobClient",
    "JobId",
    "JobNotFoundError",
    "JobParams",
    "JobRecord",
    "JobRequest",
    "JobStatus",
    "Result",
    # Job Queue
    "Job",
    "JobQueue",
    "get_job_queue",
    # Job Handlers
    "CalcJobHandler",
    "EchoJobHandler",
    "FibJobHandler",
    "HashJobHandler",
    "StatsJobHandler",
    # Job Types
    "BaseError",
    "CalcError",
    "CalcParams",
    "CalcResult",
    "EchoParams",
    "EchoResult",
    "FibError",
    "FibParams",
    "FibResult",
    "HashParams",
    "HashResult",
    "JobResult",
    "StatsError",
    "StatsParams",
    "StatsResult",
]
