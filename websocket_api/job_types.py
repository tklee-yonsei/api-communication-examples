"""WebSocket API 타입 정의."""

from __future__ import annotations

from typing import Generic, Optional, TypeVar, Union

from pydantic import BaseModel

from communication.types import Result
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
    StatsError,
    StatsParams,
    StatsResult,
)

P = TypeVar("P", bound=BaseModel)
R = TypeVar("R", bound=BaseModel)
E = TypeVar("E", bound=BaseModel)


class JobPayload(BaseModel, Generic[P, R, E]):
    """서버가 보관하는 Job 상태 레코드 (Pydantic 제네릭 모델).

    Attributes:
        id: 생성된 작업의 고유 ID
        type: 작업 종류 식별자
        params: 작업 파라미터 (Pydantic 모델)
        status: 현재 상태(pending, running, done 등)
        result: 작업 처리 결과(있을 경우에만, Pydantic 모델 또는 None)
    """

    id: str
    type: str
    params: P
    status: str
    result: Optional[Union[R, E]] = None


# Job 타입별 Payload 별칭
EchoJobPayload = JobPayload[EchoParams, EchoResult, BaseError]
CalcJobPayload = JobPayload[CalcParams, Result[CalcResult, CalcError], BaseError]
HashJobPayload = JobPayload[HashParams, HashResult, BaseError]
StatsJobPayload = JobPayload[StatsParams, Result[StatsResult, StatsError], BaseError]
FibJobPayload = JobPayload[FibParams, Result[FibResult, FibError], BaseError]

# 모든 JobPayload의 Union
AnyJobPayload = (
    EchoJobPayload | CalcJobPayload | HashJobPayload | StatsJobPayload | FibJobPayload
)
