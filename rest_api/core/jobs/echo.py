from __future__ import annotations

from rest_api.core.jobs.base import AsyncJobHandler
from rest_api.core.jobs.types import EchoParams, EchoResult


class EchoJobHandler(AsyncJobHandler[EchoParams, EchoResult]):
    """Echo 작업 핸들러."""

    async def execute(self, params: EchoParams) -> EchoResult:
        """입력을 그대로 반환합니다."""
        return EchoResult(echo=params.model_dump())
