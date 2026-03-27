"""요청 파라미터 검증 및 타입 변환 유틸리티."""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel


class ValidationError(Exception):
    """파라미터 검증 실패 예외."""


def validate_params[T: BaseModel](data: Any, param_type: type[T]) -> dict[str, Any]:
    """요청 데이터를 검증하고 dict로 반환합니다.

    이 함수는 기본적인 dict 검증만 수행합니다.
    실제 Pydantic 모델 검증은 각 job handler에서 수행됩니다.

    Args:
        data: 원본 요청 데이터 (보통 request.get_json() 결과)
        param_type: 참조용 파라미터 타입 (현재는 사용되지 않음)

    Returns:
        dict[str, Any]: 검증된 dict

    Raises:
        ValidationError: dict가 아닌 경우
    """
    _ = param_type  # 향후 Pydantic 검증에 사용 가능
    if not isinstance(data, dict):
        raise ValidationError("params must be a dict")

    return cast(dict[str, Any], data)


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
