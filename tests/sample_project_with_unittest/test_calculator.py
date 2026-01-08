"""
test_calculator.py - calculator 함수 유닛 테스트
"""

from sample_project_with_unittest.calculator import add, multiply, subtract


def test_add() -> None:
    """add 함수 테스트"""
    assert add(2, 3) == 5, "add(2, 3) should return 5"
    assert add(-1, 1) == 0, "add(-1, 1) should return 0"
    assert add(-2, -3) == -5, "add(-2, -3) should return -5"


def test_subtract() -> None:
    """subtract 함수 테스트"""
    assert subtract(2, 3) == -1, "subtract(2, 3) should return -1"
    assert subtract(10, 5) == 5, "subtract(10, 5) should return 5"
    assert subtract(5, 5) == 0, "subtract(5, 5) should return 0"


def test_multiply() -> None:
    """multiply 함수 테스트"""
    assert multiply(2, 3) == 6, "multiply(2, 3) should return 6"
    assert multiply(0, 5) == 0, "multiply(0, 5) should return 0"
    assert multiply(-2, 3) == -6, "multiply(-2, 3) should return -6"
