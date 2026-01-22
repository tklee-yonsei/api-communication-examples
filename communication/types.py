"""공통 타입 정의.

프로젝트 전반에서 사용되는 공통 타입들을 정의합니다.
"""

from __future__ import annotations

from typing import Literal, TypeAlias, TypeVar, Union


# ===== Result 타입 (성공 또는 실패) =====
# Union은 여러 가능한 결과 타입을 나타낼 때 사용하고,
# Result는 명시적으로 "성공 또는 실패"를 나타냄
#
# 주의: Failure는 예외(Exception)가 아니라 에러 데이터 객체입니다.
#       예를 들어 StatsError는 Pydantic 모델로 error: str 필드를 가진 데이터 객체입니다.
#
# 사용 예:
#   Result[CalcResult, CalcError]  # 성공: CalcResult, 실패: CalcError (에러 데이터)
#   Result[StatsResult, StatsError]  # 성공: StatsResult, 실패: StatsError (에러 데이터)
#
# 실제로는 Union이지만, 의미론적으로 "성공 결과 또는 에러 데이터"를 명확히 표현
Success = TypeVar("Success")
Failure = TypeVar("Failure")  # Failure는 예외가 아니라 에러 데이터 객체
Result = Union[Success, Failure]


# ===== Job 관련 타입 별칭 =====
JobId: TypeAlias = str
JobParams: TypeAlias = dict[str, object]
JobStatus = Literal["pending", "running", "done", "failed", "error"]
