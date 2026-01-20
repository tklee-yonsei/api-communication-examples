"""비동기 작업 처리 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from rest_api.core.jobs.types import JobResult

# 파라미터와 결과 타입을 위한 제네릭 타입 변수
TParams = TypeVar("TParams")
TResult = TypeVar("TResult", bound=JobResult)


class AsyncJobHandler(ABC, Generic[TParams, TResult]):
    """비동기 작업 처리 인터페이스.

    모든 작업 핸들러는 이 인터페이스를 구현해야 합니다.
    """

    @abstractmethod
    async def execute(self, params: TParams) -> TResult:
        """작업을 비동기로 실행합니다.

        Args:
            params: 작업 수행에 필요한 파라미터

        Returns:
            작업 실행 결과
        """
        pass


__all__ = ["AsyncJobHandler", "TParams", "TResult"]
