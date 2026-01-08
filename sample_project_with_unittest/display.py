"""
display.py - 출력 함수 구현
"""


def print_title() -> None:
    """제목 출력"""
    print("================================")
    print("     간단한 계산기 예제")
    print("================================")
    print()


def print_result(operation: str, a: int, b: int, result: int) -> None:
    """계산 결과 출력"""
    print(f"{a} {operation} {b} = {result}")
