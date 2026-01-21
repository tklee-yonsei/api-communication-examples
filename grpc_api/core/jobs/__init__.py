"""gRPC jobs 모듈 - REST API의 jobs 모듈을 재사용합니다."""

from rest_api.core.jobs import (
    CalcJobHandler,
    EchoJobHandler,
    FibJobHandler,
    HashJobHandler,
    StatsJobHandler,
)
from rest_api.core.jobs.types import (
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
    StatsError,
    StatsParams,
    StatsResult,
)

__all__ = [
    # 핸들러
    "EchoJobHandler",
    "CalcJobHandler",
    "StatsJobHandler",
    "HashJobHandler",
    "FibJobHandler",
    # 타입
    "BaseError",
    "EchoParams",
    "EchoResult",
    "CalcParams",
    "CalcResult",
    "CalcError",
    "HashParams",
    "HashResult",
    "StatsParams",
    "StatsResult",
    "StatsError",
    "FibParams",
    "FibResult",
    "FibError",
]
