"""Job Handler 단위 테스트.

각 AsyncJobHandler 구현체의 execute() 메서드를 독립적으로 테스트합니다.
모든 핸들러는 비동기로 동작하므로 pytest-asyncio를 사용합니다.

테스트 대상:
- EchoJobHandler: 입력을 그대로 반환
- CalcJobHandler: 사칙연산 수행
- HashJobHandler: SHA-256 해시 생성
- StatsJobHandler: 통계 계산
- FibJobHandler: 피보나치 수 계산
"""

from __future__ import annotations

import pytest

from communication.jobs import (
    CalcJobHandler,
    EchoJobHandler,
    FibJobHandler,
    HashJobHandler,
    StatsJobHandler,
)
from communication.jobs.types import (
    CalcError,
    CalcParams,
    CalcResult,
    EchoParams,
    EchoResult,
    FibParams,
    FibResult,
    HashParams,
    HashResult,
    StatsError,
    StatsParams,
    StatsResult,
)


class TestEchoJobHandler:
    """EchoJobHandler 테스트.

    EchoJobHandler는 입력 파라미터를 그대로 반환합니다.
    """

    @pytest.fixture
    def handler(self) -> EchoJobHandler:
        """EchoJobHandler 인스턴스를 생성합니다.

        Returns:
            EchoJobHandler: 테스트 대상 핸들러
        """
        return EchoJobHandler()

    @pytest.mark.asyncio
    async def test_echo_simple_data(self, handler: EchoJobHandler) -> None:
        """간단한 데이터가 그대로 반환되는지 테스트합니다."""
        params = EchoParams(message="hello", count=42)
        result = await handler.execute(params)

        assert isinstance(result, EchoResult)
        assert result.echo["message"] == "hello"
        assert result.echo["count"] == 42

    @pytest.mark.asyncio
    async def test_echo_empty_params(self, handler: EchoJobHandler) -> None:
        """빈 파라미터도 정상 처리되는지 테스트합니다."""
        params = EchoParams()
        result = await handler.execute(params)

        assert isinstance(result, EchoResult)
        assert result.echo == {}

    @pytest.mark.asyncio
    async def test_echo_nested_data(self, handler: EchoJobHandler) -> None:
        """중첩된 데이터 구조도 반환되는지 테스트합니다."""
        params = EchoParams(nested={"inner": {"value": 123}}, items=[1, 2, 3])
        result = await handler.execute(params)

        assert isinstance(result, EchoResult)
        assert result.echo["nested"] == {"inner": {"value": 123}}
        assert result.echo["items"] == [1, 2, 3]


class TestCalcJobHandler:
    """CalcJobHandler 테스트.

    CalcJobHandler는 사칙연산(add, sub, mul, div)을 수행합니다.
    """

    @pytest.fixture
    def handler(self) -> CalcJobHandler:
        """CalcJobHandler 인스턴스를 생성합니다.

        Returns:
            CalcJobHandler: 테스트 대상 핸들러
        """
        return CalcJobHandler()

    @pytest.mark.asyncio
    async def test_calc_add(self, handler: CalcJobHandler) -> None:
        """덧셈 연산을 테스트합니다."""
        params = CalcParams(op="add", a=10.0, b=5.0)
        result = await handler.execute(params)

        assert isinstance(result, CalcResult)
        assert result.op == "add"
        assert result.a == 10.0
        assert result.b == 5.0
        assert result.result == 15.0

    @pytest.mark.asyncio
    async def test_calc_sub(self, handler: CalcJobHandler) -> None:
        """뺄셈 연산을 테스트합니다."""
        params = CalcParams(op="sub", a=10.0, b=3.0)
        result = await handler.execute(params)

        assert isinstance(result, CalcResult)
        assert result.result == 7.0

    @pytest.mark.asyncio
    async def test_calc_mul(self, handler: CalcJobHandler) -> None:
        """곱셈 연산을 테스트합니다."""
        params = CalcParams(op="mul", a=4.0, b=3.0)
        result = await handler.execute(params)

        assert isinstance(result, CalcResult)
        assert result.result == 12.0

    @pytest.mark.asyncio
    async def test_calc_div(self, handler: CalcJobHandler) -> None:
        """나눗셈 연산을 테스트합니다."""
        params = CalcParams(op="div", a=20.0, b=4.0)
        result = await handler.execute(params)

        assert isinstance(result, CalcResult)
        assert result.result == 5.0

    @pytest.mark.asyncio
    async def test_calc_div_by_zero(self, handler: CalcJobHandler) -> None:
        """0으로 나누기 시 에러가 반환되는지 테스트합니다."""
        params = CalcParams(op="div", a=10.0, b=0.0)
        result = await handler.execute(params)

        assert isinstance(result, CalcError)
        assert "division by zero" in result.error

    @pytest.mark.asyncio
    async def test_calc_negative_numbers(self, handler: CalcJobHandler) -> None:
        """음수 연산을 테스트합니다."""
        params = CalcParams(op="add", a=-5.0, b=-3.0)
        result = await handler.execute(params)

        assert isinstance(result, CalcResult)
        assert result.result == -8.0

    @pytest.mark.asyncio
    async def test_calc_float_precision(self, handler: CalcJobHandler) -> None:
        """부동소수점 연산을 테스트합니다."""
        params = CalcParams(op="div", a=1.0, b=3.0)
        result = await handler.execute(params)

        assert isinstance(result, CalcResult)
        assert abs(result.result - 0.3333333333) < 0.0001


class TestHashJobHandler:
    """HashJobHandler 테스트.

    HashJobHandler는 입력 파라미터를 JSON으로 직렬화한 후 SHA-256 해시를 생성합니다.
    """

    @pytest.fixture
    def handler(self) -> HashJobHandler:
        """HashJobHandler 인스턴스를 생성합니다.

        Returns:
            HashJobHandler: 테스트 대상 핸들러
        """
        return HashJobHandler()

    @pytest.mark.asyncio
    async def test_hash_generates_sha256(self, handler: HashJobHandler) -> None:
        """SHA-256 해시가 생성되는지 테스트합니다."""
        # HashParams는 extra="allow"로 임의 필드를 허용하므로 model_validate 사용
        params = HashParams.model_validate({"data": "test"})
        result = await handler.execute(params)

        assert isinstance(result, HashResult)
        assert result.algo == "sha256"
        assert len(result.digest) == 64  # SHA-256은 64자리 hex

    @pytest.mark.asyncio
    async def test_hash_same_input_same_output(self, handler: HashJobHandler) -> None:
        """동일한 입력에 대해 동일한 해시가 생성되는지 테스트합니다."""
        params1 = HashParams.model_validate({"value": "hello"})
        params2 = HashParams.model_validate({"value": "hello"})

        result1 = await handler.execute(params1)
        result2 = await handler.execute(params2)

        assert result1.digest == result2.digest

    @pytest.mark.asyncio
    async def test_hash_different_input_different_output(
        self, handler: HashJobHandler
    ) -> None:
        """다른 입력에 대해 다른 해시가 생성되는지 테스트합니다."""
        params1 = HashParams.model_validate({"value": "hello"})
        params2 = HashParams.model_validate({"value": "world"})

        result1 = await handler.execute(params1)
        result2 = await handler.execute(params2)

        assert result1.digest != result2.digest

    @pytest.mark.asyncio
    async def test_hash_empty_params(self, handler: HashJobHandler) -> None:
        """빈 파라미터도 정상 처리되는지 테스트합니다."""
        params = HashParams()
        result = await handler.execute(params)

        assert isinstance(result, HashResult)
        assert len(result.digest) == 64

    @pytest.mark.asyncio
    async def test_hash_input_preserved(self, handler: HashJobHandler) -> None:
        """입력 JSON 문자열이 결과에 포함되는지 테스트합니다."""
        params = HashParams.model_validate({"key": "value"})
        result = await handler.execute(params)

        assert isinstance(result, HashResult)
        assert "key" in result.input
        assert "value" in result.input


class TestStatsJobHandler:
    """StatsJobHandler 테스트.

    StatsJobHandler는 숫자 리스트에 대한 통계(count, min, max, sum, mean, median)를 계산합니다.
    """

    @pytest.fixture
    def handler(self) -> StatsJobHandler:
        """StatsJobHandler 인스턴스를 생성합니다.

        Returns:
            StatsJobHandler: 테스트 대상 핸들러
        """
        return StatsJobHandler()

    @pytest.mark.asyncio
    async def test_stats_basic_calculation(self, handler: StatsJobHandler) -> None:
        """기본 통계 계산을 테스트합니다."""
        params = StatsParams(values=[1.0, 2.0, 3.0, 4.0, 5.0])
        result = await handler.execute(params)

        assert isinstance(result, StatsResult)
        assert result.count == 5
        assert result.min == 1.0
        assert result.max == 5.0
        assert result.sum == 15.0
        assert result.mean == 3.0
        assert result.median == 3.0

    @pytest.mark.asyncio
    async def test_stats_single_value(self, handler: StatsJobHandler) -> None:
        """단일 값에 대한 통계를 테스트합니다."""
        params = StatsParams(values=[42.0])
        result = await handler.execute(params)

        assert isinstance(result, StatsResult)
        assert result.count == 1
        assert result.min == 42.0
        assert result.max == 42.0
        assert result.sum == 42.0
        assert result.mean == 42.0
        assert result.median == 42.0

    @pytest.mark.asyncio
    async def test_stats_even_count_median(self, handler: StatsJobHandler) -> None:
        """짝수 개수의 값에 대한 중앙값을 테스트합니다."""
        params = StatsParams(values=[1.0, 2.0, 3.0, 4.0])
        result = await handler.execute(params)

        assert isinstance(result, StatsResult)
        assert result.median == 2.5  # (2 + 3) / 2

    @pytest.mark.asyncio
    async def test_stats_negative_values(self, handler: StatsJobHandler) -> None:
        """음수 값이 포함된 통계를 테스트합니다."""
        params = StatsParams(values=[-5.0, -3.0, 0.0, 3.0, 5.0])
        result = await handler.execute(params)

        assert isinstance(result, StatsResult)
        assert result.min == -5.0
        assert result.max == 5.0
        assert result.sum == 0.0
        assert result.mean == 0.0

    @pytest.mark.asyncio
    async def test_stats_empty_list_error(self, handler: StatsJobHandler) -> None:
        """빈 리스트에 대해 에러가 반환되는지 테스트합니다."""
        params = StatsParams(values=[])
        result = await handler.execute(params)

        assert isinstance(result, StatsError)
        assert "array" in result.error.lower() or "values" in result.error.lower()

    @pytest.mark.asyncio
    async def test_stats_float_values(self, handler: StatsJobHandler) -> None:
        """부동소수점 값에 대한 통계를 테스트합니다."""
        params = StatsParams(values=[1.5, 2.5, 3.5])
        result = await handler.execute(params)

        assert isinstance(result, StatsResult)
        assert result.sum == 7.5
        assert result.mean == 2.5


class TestFibJobHandler:
    """FibJobHandler 테스트.

    FibJobHandler는 피보나치 수열의 n번째 수를 계산합니다.
    n은 0 이상 40 이하로 제한됩니다.
    """

    @pytest.fixture
    def handler(self) -> FibJobHandler:
        """FibJobHandler 인스턴스를 생성합니다.

        Returns:
            FibJobHandler: 테스트 대상 핸들러
        """
        return FibJobHandler()

    @pytest.mark.asyncio
    async def test_fib_zero(self, handler: FibJobHandler) -> None:
        """F(0) = 0을 테스트합니다."""
        params = FibParams(n=0)
        result = await handler.execute(params)

        assert isinstance(result, FibResult)
        assert result.n == 0
        assert result.fib == 0

    @pytest.mark.asyncio
    async def test_fib_one(self, handler: FibJobHandler) -> None:
        """F(1) = 1을 테스트합니다."""
        params = FibParams(n=1)
        result = await handler.execute(params)

        assert isinstance(result, FibResult)
        assert result.n == 1
        assert result.fib == 1

    @pytest.mark.asyncio
    async def test_fib_small_values(self, handler: FibJobHandler) -> None:
        """작은 피보나치 수를 테스트합니다."""
        expected = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]

        for n, expected_fib in enumerate(expected):
            params = FibParams(n=n)
            result = await handler.execute(params)

            assert isinstance(result, FibResult)
            assert result.fib == expected_fib

    @pytest.mark.asyncio
    async def test_fib_ten(self, handler: FibJobHandler) -> None:
        """F(10) = 55를 테스트합니다."""
        params = FibParams(n=10)
        result = await handler.execute(params)

        assert isinstance(result, FibResult)
        assert result.fib == 55

    @pytest.mark.asyncio
    async def test_fib_twenty(self, handler: FibJobHandler) -> None:
        """F(20) = 6765를 테스트합니다."""
        params = FibParams(n=20)
        result = await handler.execute(params)

        assert isinstance(result, FibResult)
        assert result.fib == 6765

    @pytest.mark.asyncio
    async def test_fib_max_value(self, handler: FibJobHandler) -> None:
        """최대 허용 값 F(40)을 테스트합니다."""
        params = FibParams(n=40)
        result = await handler.execute(params)

        assert isinstance(result, FibResult)
        assert result.fib == 102334155
