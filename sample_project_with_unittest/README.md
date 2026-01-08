# Sample Project with Unit Tests

Python으로 작성된 간단한 계산기 프로젝트입니다. Python 프로젝트 구조를 따라 구성되었습니다.

## 프로젝트 구조

```text
py_programming_base/
├── sample_project_with_unittest/
│   ├── __init__.py            # 패키지 초기화 파일
│   ├── calculator.py          # 계산 함수 구현 (add, subtract, multiply)
│   ├── display.py             # 출력 함수 구현
│   ├── main.py                # 메인 프로그램
│   └── README.md              # 이 파일
└── tests/
    └── sample_project_with_unittest/
        ├── test_calculator.py # calculator 유닛 테스트
        └── test_display.py    # display 유닛 테스트
```

## 실행 방법

### 메인 프로그램 실행

프로젝트 루트(`py_programming_base/`)에서 실행:

```bash
python -m sample_project_with_unittest.main
```

또는

```bash
python3 -m sample_project_with_unittest.main
```

### 테스트 실행

```bash
# 프로젝트 루트에서 실행
# 모든 테스트 실행
pytest tests/sample_project_with_unittest/

# 개별 테스트 실행
pytest tests/sample_project_with_unittest/test_calculator.py
pytest tests/sample_project_with_unittest/test_display.py

# 상세 출력
pytest tests/sample_project_with_unittest/ -v
```

## 함수 설명

### Calculator 함수

- `add(a: int, b: int) -> int`: 두 정수의 덧셈
- `subtract(a: int, b: int) -> int`: 두 정수의 뺄셈
- `multiply(a: int, b: int) -> int`: 두 정수의 곱셈

### Display 함수

- `print_title() -> None`: 제목 출력
- `print_result(operation: str, a: int, b: int, result: int) -> None`: 계산 결과 출력
