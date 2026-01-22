from __future__ import annotations

from communication.types import Result
from communication.jobs.base import AsyncJobHandler
from communication.jobs.types import StatsError, StatsParams, StatsResult


class StatsJobHandler(AsyncJobHandler[StatsParams, Result[StatsResult, StatsError]]):
    """통계 작업 핸들러."""

    async def execute(self, params: StatsParams) -> Result[StatsResult, StatsError]:
        """숫자 리스트 통계 작업(values: list[float])."""
        if not params.values:
            return StatsError(error="values must be an array")

        nums = _to_numbers(params.values)
        if len(nums) == 0:
            return StatsError(error="values must contain numbers")

        nums_sorted = sorted(nums)
        count = len(nums)
        total = sum(nums)
        mean = total / count
        median = _median(nums_sorted)

        return StatsResult(
            count=count,
            min=nums_sorted[0],
            max=nums_sorted[-1],
            sum=total,
            mean=mean,
            median=median,
        )


def _to_numbers(values: list[float]) -> list[float]:
    """숫자 리스트를 검증하고 반환합니다."""
    nums: list[float] = []
    for v in values:
        try:
            nums.append(float(v))
        except (TypeError, ValueError):
            continue
    return nums


def _median(nums_sorted: list[float]) -> float:
    n = len(nums_sorted)
    mid = n // 2
    if n % 2 == 1:
        return nums_sorted[mid]
    return (nums_sorted[mid - 1] + nums_sorted[mid]) / 2
