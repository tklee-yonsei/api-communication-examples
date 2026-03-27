"""Validation 유틸리티 단위 테스트.

요청 파라미터 검증 및 타입 변환 유틸리티를 테스트합니다.

테스트 대상:
- validate_params: 타입별 파라미터 검증
- validate_dict_payload: 일반 dict 검증
- ValidationError: 검증 실패 예외
"""

from __future__ import annotations

from typing import Any

import pytest

from rest_api.core.validation import (
    ValidationError,
    validate_dict_payload,
    validate_params,
)
from rest_api.core.jobs.types import (
    CalcParams,
    EchoParams,
    FibParams,
    HashParams,
    StatsParams,
)


class TestValidateParams:
    """validate_params 함수 테스트.

    다양한 파라미터 타입에 대한 검증을 테스트합니다.
    """

    def test_validate_echo_params(self) -> None:
        """EchoParams 검증을 테스트합니다."""
        data: dict[str, Any] = {"message": "hello", "count": 42}
        result = validate_params(data, EchoParams)

        # validate_params는 dict를 그대로 반환
        assert result["message"] == "hello"
        assert result["count"] == 42

    def test_validate_calc_params(self) -> None:
        """CalcParams 검증을 테스트합니다."""
        data: dict[str, Any] = {"op": "add", "a": 10.0, "b": 5.0}
        result = validate_params(data, CalcParams)

        assert result["op"] == "add"
        assert result["a"] == 10.0
        assert result["b"] == 5.0

    def test_validate_hash_params(self) -> None:
        """HashParams 검증을 테스트합니다."""
        data: dict[str, Any] = {"value": "test-data"}
        result = validate_params(data, HashParams)

        assert result["value"] == "test-data"

    def test_validate_stats_params(self) -> None:
        """StatsParams 검증을 테스트합니다."""
        data: dict[str, Any] = {"values": [1.0, 2.0, 3.0]}
        result = validate_params(data, StatsParams)

        assert result["values"] == [1.0, 2.0, 3.0]

    def test_validate_fib_params(self) -> None:
        """FibParams 검증을 테스트합니다."""
        data: dict[str, Any] = {"n": 10}
        result = validate_params(data, FibParams)

        assert result["n"] == 10

    def test_validate_params_not_dict_raises(self) -> None:
        """dict가 아닌 데이터에서 ValidationError가 발생하는지 테스트합니다."""
        with pytest.raises(ValidationError) as exc_info:
            validate_params("not a dict", EchoParams)

        assert "dict" in str(exc_info.value).lower()

    def test_validate_params_none_raises(self) -> None:
        """None 데이터에서 ValidationError가 발생하는지 테스트합니다."""
        with pytest.raises(ValidationError):
            validate_params(None, EchoParams)

    def test_validate_params_list_raises(self) -> None:
        """리스트 데이터에서 ValidationError가 발생하는지 테스트합니다."""
        with pytest.raises(ValidationError):
            validate_params([1, 2, 3], CalcParams)

    def test_validate_params_empty_dict(self) -> None:
        """빈 dict도 통과하는지 테스트합니다 (최소한의 검증)."""
        data: dict[str, Any] = {}
        result = validate_params(data, EchoParams)

        assert result == {}


class TestValidateDictPayload:
    """validate_dict_payload 함수 테스트.

    일반적인 dict payload 검증을 테스트합니다.
    """

    def test_validate_dict_payload_success(self) -> None:
        """정상적인 dict가 통과하는지 테스트합니다."""
        data = {"key": "value", "number": 123}
        result = validate_dict_payload(data)

        assert result == data

    def test_validate_dict_payload_empty(self) -> None:
        """빈 dict가 통과하는지 테스트합니다."""
        data: dict[str, Any] = {}
        result = validate_dict_payload(data)

        assert result == {}

    def test_validate_dict_payload_nested(self) -> None:
        """중첩된 dict가 통과하는지 테스트합니다."""
        data = {"outer": {"inner": {"deep": "value"}}}
        result = validate_dict_payload(data)

        assert result["outer"]["inner"]["deep"] == "value"

    def test_validate_dict_payload_not_dict_raises(self) -> None:
        """dict가 아닌 데이터에서 ValidationError가 발생하는지 테스트합니다."""
        with pytest.raises(ValidationError) as exc_info:
            validate_dict_payload("string payload")

        assert "dict" in str(exc_info.value).lower()

    def test_validate_dict_payload_none_raises(self) -> None:
        """None에서 ValidationError가 발생하는지 테스트합니다."""
        with pytest.raises(ValidationError):
            validate_dict_payload(None)

    def test_validate_dict_payload_list_raises(self) -> None:
        """리스트에서 ValidationError가 발생하는지 테스트합니다."""
        with pytest.raises(ValidationError):
            validate_dict_payload([{"key": "value"}])

    def test_validate_dict_payload_number_raises(self) -> None:
        """숫자에서 ValidationError가 발생하는지 테스트합니다."""
        with pytest.raises(ValidationError):
            validate_dict_payload(42)


class TestValidationError:
    """ValidationError 예외 테스트."""

    def test_validation_error_message(self) -> None:
        """에러 메시지가 올바르게 설정되는지 테스트합니다."""
        error = ValidationError("Custom error message")
        assert str(error) == "Custom error message"

    def test_validation_error_inheritance(self) -> None:
        """ValidationError가 Exception을 상속하는지 테스트합니다."""
        error = ValidationError("test")
        assert isinstance(error, Exception)
