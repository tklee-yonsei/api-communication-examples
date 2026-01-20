"""작업 처리 핸들러들 - AsyncJobHandler 기반 클래스 제공."""

from __future__ import annotations

from rest_api.core.jobs.calc import CalcJobHandler
from rest_api.core.jobs.echo import EchoJobHandler
from rest_api.core.jobs.fib import FibJobHandler
from rest_api.core.jobs.hash_job import HashJobHandler
from rest_api.core.jobs.stats import StatsJobHandler

__all__ = [
    "EchoJobHandler",
    "CalcJobHandler",
    "HashJobHandler",
    "StatsJobHandler",
    "FibJobHandler",
]
