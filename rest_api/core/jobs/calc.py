from __future__ import annotations

from rest_api.core.jobs.base import AsyncJobHandler
from rest_api.core.jobs.types import CalcError, CalcParams, CalcResult


class CalcJobHandler(AsyncJobHandler[CalcParams, CalcResult | CalcError]):
    """계산 작업 핸들러."""

    async def execute(self, params: CalcParams) -> CalcResult | CalcError:
        """사칙연산 작업(op: add|sub|mul|div, a, b)."""
        op = params.op
        a = params.a
        b = params.b

        if op == "add":
            val = a + b
        elif op == "sub":
            val = a - b
        elif op == "mul":
            val = a * b
        elif op == "div":
            if b == 0:
                return CalcError(error="division by zero")
            val = a / b
        else:
            return CalcError(error=f"unsupported op: {op}")

        return CalcResult(op=op, a=a, b=b, result=val)
