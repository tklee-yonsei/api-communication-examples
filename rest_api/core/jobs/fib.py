from __future__ import annotations

from rest_api.core.jobs.base import AsyncJobHandler
from rest_api.core.jobs.types import FibError, FibParams, FibResult


class FibJobHandler(AsyncJobHandler[FibParams, FibResult | FibError]):
    """피보나치 작업 핸들러."""

    async def execute(self, params: FibParams) -> FibResult | FibError:
        """작은 n에 대한 피보나치 수 계산 (n 최대 40)."""
        n = params.n

        # Pydantic Field 검증으로 이미 보장되지만, 명시적으로 체크
        if n < 0:
            return FibError(error="n must be non-negative")
        if n > 40:
            return FibError(error="n too large (max 40)")

        return FibResult(n=n, fib=_fib_iter(n))


def _fib_iter(n: int) -> int:
    if n == 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
