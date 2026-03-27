"""UI 서버용 데이터 타입 정의."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobResult:
    """단일 작업 요청의 결과.

    Attributes:
        success: 작업 성공 여부
        data: 성공 시 데이터, 실패 시 에러 정보
    """

    success: bool
    data: dict[str, object]


@dataclass(frozen=True)
class BatchResult:
    """배치 작업의 결과.

    Attributes:
        successes: 성공한 작업 목록
        failures: 실패한 작업 목록
    """

    successes: list[dict[str, object]]
    failures: list[dict[str, object]]
