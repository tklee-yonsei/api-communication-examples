"""
test_display.py - display 함수 유닛 테스트
"""

import pytest

from sample_project_with_unittest.display import print_result, print_title


def test_print_title(capsys: pytest.CaptureFixture[str]) -> None:
    """print_title 함수 테스트"""
    print_title()
    captured = capsys.readouterr()
    assert "간단한 계산기 예제" in captured.out
    assert "================================" in captured.out


def test_print_result(capsys: pytest.CaptureFixture[str]) -> None:
    """print_result 함수 테스트"""
    print_result("+", 10, 5, 15)
    captured = capsys.readouterr()
    assert "10 + 5 = 15" in captured.out

    print_result("-", 10, 5, 5)
    captured = capsys.readouterr()
    assert "10 - 5 = 5" in captured.out

    print_result("*", 10, 5, 50)
    captured = capsys.readouterr()
    assert "10 * 5 = 50" in captured.out
