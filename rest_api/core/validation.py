"""요청 파라미터 검증 및 타입 변환 유틸리티."""

from __future__ import annotations

from typing import Any, Type, TypeVar, cast

from rest_api.core.jobs.types import (
    CalcParams,
    EchoParams,
    FibParams,
    HashParams,
    StatsParams,
)

T = TypeVar("T", EchoParams, CalcParams, HashParams, StatsParams, FibParams)


class ValidationError(Exception):
    """파라미터 검증 실패 예외."""


def validate_params(data: Any, param_type: Type[T]) -> T:
    """요청 데이터를 검증하고 타입이 지정된 params로 변환합니다.

    Args:
        data: 원본 요청 데이터 (보통 request.get_json() 결과)
        param_type: 변환할 TypedDict 타입

    Returns:
        T: 검증된 params

    Raises:
        ValidationError: 검증 실패 시
    """
    if not isinstance(data, dict):
        raise ValidationError("params must be a dict")

    # 런타임 검증은 최소한으로만 수행
    # TypedDict는 런타임에 검증되지 않으므로 cast 사용
    # 각 job handler에서 추가 검증 수행
    return cast(T, data)


def validate_dict_payload(data: Any) -> dict[str, Any]:
    """일반 dict payload 검증.

    Args:
        data: 원본 요청 데이터

    Returns:
        dict[str, Any]: 검증된 dict

    Raises:
        ValidationError: dict가 아닌 경우
    """
    if not isinstance(data, dict):
        raise ValidationError("payload must be a dict")
    return cast(dict[str, Any], data)
