"""
sample.py - 별(*)로 산 모양 출력하기

간단한 for loop 예제
"""


def main() -> None:
    height = 5  # 산의 높이

    print("=== 별로 산 만들기 ===\n")

    for i in range(1, height + 1):
        # 공백 출력 (오른쪽 정렬용)
        for _ in range(height - i):
            print(" ", end="")
        # 별 출력 (홀수 개씩: 1, 3, 5, 7, 9...)
        for _ in range(2 * i - 1):
            print("*", end="")
        print()  # 줄바꿈


if __name__ == "__main__":
    main()
