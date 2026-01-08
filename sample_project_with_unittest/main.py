"""
main.py - 메인 프로그램
"""

from sample_project_with_unittest.calculator import add, multiply, subtract
from sample_project_with_unittest.display import print_result, print_title


def main() -> None:
    """메인 함수"""
    a = 10
    b = 5

    print_title()

    print_result("+", a, b, add(a, b))
    print_result("-", a, b, subtract(a, b))
    print_result("*", a, b, multiply(a, b))


if __name__ == "__main__":
    main()
