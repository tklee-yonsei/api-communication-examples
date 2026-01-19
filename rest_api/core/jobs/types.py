"""각 작업별 파라미터와 결과 타입 정의 (Pydantic 모델)."""

from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, Field


class BaseError(BaseModel):
    """공통 에러 모델."""

    error: str


# ===== Echo Job =====
class EchoParams(BaseModel):
    """Echo 작업 파라미터 (모든 필드 선택적)."""

    model_config = {"extra": "allow"}  # 추가 필드 허용

    def __init__(self, **data: object) -> None:
        """모든 필드를 선택적으로 허용."""
        super().__init__(**data)


class EchoResult(BaseModel):
    """Echo 작업 결과."""

    echo: dict[str, object]


# ===== Calc Job =====
class CalcParams(BaseModel):
    """계산 작업 파라미터."""

    op: Literal["add", "sub", "mul", "div"] = Field(default="add")
    a: float = Field(default=0.0)
    b: float = Field(default=0.0)


class CalcResult(BaseModel):
    """계산 작업 결과."""

    op: str
    a: float
    b: float
    result: float


class CalcError(BaseError):
    """계산 작업 에러."""


# ===== Hash Job =====
class HashParams(BaseModel):
    """해시 작업 파라미터 (모든 필드 선택적)."""

    model_config = {"extra": "allow"}  # 추가 필드 허용


class HashResult(BaseModel):
    """해시 작업 결과."""

    algo: str
    input: str
    digest: str


# ===== Stats Job =====
class StatsParams(BaseModel):
    """통계 작업 파라미터."""

    values: list[float]


class StatsResult(BaseModel):
    """통계 작업 결과."""

    count: int
    min: float
    max: float
    sum: float
    mean: float
    median: float


class StatsError(BaseError):
    """통계 작업 에러."""


# ===== Fib Job =====
class FibParams(BaseModel):
    """피보나치 작업 파라미터."""

    n: int = Field(ge=0, le=40, description="피보나치 수열의 인덱스 (0-40)")


class FibResult(BaseModel):
    """피보나치 작업 결과."""

    n: int
    fib: int


class FibError(BaseError):
    """피보나치 작업 에러."""


# ===== 통합 타입 =====
JobResult = Union[
    EchoResult,
    CalcResult,
    CalcError,
    HashResult,
    StatsResult,
    StatsError,
    FibResult,
    FibError,
    BaseError,
]
