"""gRPC 서버 타입 정의."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

from communication.types import Result
from communication.jobs.types import JobResult

# 제네릭 타입 변수
P = TypeVar("P")  # params 타입
R = TypeVar("R", bound=JobResult)  # result 타입 (성공)
E = TypeVar("E", bound=JobResult)  # result 타입 (에러)


@dataclass
class JobPayload(Generic[P, R, E]):
    """gRPC 작업 상태 레코드.

    Attributes:
        id: 작업 고유 ID
        type: 작업 종류 (hash, fib)
        params: 작업 파라미터 (제네릭 타입 P)
        status: 현재 상태 (pending, running, done, failed)
        result: 작업 결과 (완료 시, Optional[Union[R, E]])
    """

    id: str
    type: str
    params: P
    status: str = "pending"
    result: Optional[Result[R, E]] = None
