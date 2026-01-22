"""보조 유틸리티 함수."""

from __future__ import annotations

import json
from typing import cast


def parse_params(raw: object) -> dict[str, object]:
    """파라미터를 dict로 변환합니다.

    Args:
        raw: 변환할 값 (None, dict, JSON 문자열 등)

    Returns:
        dict[str, object]: 변환된 파라미터 딕셔너리
    """
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return cast(dict[str, object], raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return cast(dict[str, object], parsed)
    return {}


def coerce_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    """값을 정수로 변환하고 범위 내로 제한합니다.

    Args:
        value: 정수로 변환할 값
        default: 변환 실패 시 기본값
        minimum: 허용되는 최소값
        maximum: 허용되는 최대값

    Returns:
        int: 범위 내로 제한된 정수 값
    """
    as_int: int
    if isinstance(value, int):
        as_int = value
    elif isinstance(value, (str, float)):
        try:
            as_int = int(value)
        except (ValueError, TypeError):
            as_int = default
    else:
        as_int = default
    clamped: int = max(minimum, min(maximum, as_int))
    return clamped
