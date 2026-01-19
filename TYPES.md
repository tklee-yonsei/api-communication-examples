# 타입 안전성 개선 가이드

이 프로젝트는 엄격한 타입 체킹을 사용합니다 (`pyproject.toml`의 `basedpyright strict` 모드).

## 주요 타입 정책

### 1. `Any` 사용 금지

- `Any` 대신 구체적인 타입 사용
- 예외: Flask `request.get_json()` 등 불가피한 경우만

### 2. 제네릭 활용

- `dict[str, object]` 대신 제네릭 TypedDict 사용
- 각 엔드포인트가 정확한 params 타입을 알 수 있도록 구현

### 3. 타입 검증 레이어

- `rest_api/validation.py`의 `validate_params()`로 런타임 검증
- TypedDict는 정적 타입만 제공하므로 런타임 검증 필요

### 4. Flask Response 타입

- ❌ `Tuple[Any, int]` - Any 사용으로 타입 안전성 저하
- ✅ `Response` - Flask의 Response 객체 타입
- `make_response(jsonify(...), status_code)`로 명시적 Response 생성

## 주요 타입 정의

### communication/base.py

```python
JobParams: TypeAlias = dict[str, object]  # 범용 파라미터 타입
JobStatus = Literal["pending", "running", "done", "failed", "error"]
```

### rest_api/jobs/types.py

각 job별 구체적인 params/result 타입:

- `EchoParams`, `EchoResult`
- `CalcParams`, `CalcResult`, `CalcError`
- `HashParams`, `HashResult`
- `StatsParams`, `StatsResult`, `StatsError`
- `FibParams`, `FibResult`, `FibError`
- `JobResult` = 모든 result 타입의 Union
- `AnyJobParams` = 모든 params 타입의 Union

### rest_api/server.py - 제네릭 JobPayload

```python
P = TypeVar("P", EchoParams, CalcParams, HashParams, StatsParams, FibParams)

class JobPayload(TypedDict, Generic[P]):
    """타입 매개변수 P로 params 타입이 지정됨"""
    id: str
    type: str
    params: P  # 제네릭 타입!
    status: str
    result: Optional[JobResult]

# 모든 가능한 JobPayload 타입의 Union
AnyJobPayload = (
    JobPayload[EchoParams]
    | JobPayload[CalcParams]
    | JobPayload[HashParams]
    | JobPayload[StatsParams]
    | JobPayload[FibParams]
)
```

### rest_api/validation.py - 타입 검증 레이어
```python
def validate_params(data: Any, param_type: Type[T]) -> T:
    """요청 데이터를 검증하고 타입이 지정된 params로 변환"""
    if not isinstance(data, dict):
        raise ValidationError("params must be a dict")
    return cast(T, data)
```

### rest_api/jobs/__init__.py - 각 job별 독립 함수
```python
def process_echo(params: EchoParams) -> JobResult:
    """Echo 작업 처리."""
    return run_echo(params)

def process_calc(params: CalcParams) -> JobResult:
    """계산 작업 처리."""
    return run_calc(params)

def process_hash(params: HashParams) -> JobResult:
    """해시 작업 처리."""
    return run_hash(params)

# ... 기타 함수들
```

**장점:**
- 오버로드 불필요
- 함수 이름만으로 명확한 의도 전달
- 타입 체커가 자동으로 정확한 params 타입 인식

## 실제 사용 예제

### 엔드포인트에서 타입 안전하게 사용
```python
@app.post("/calc")
def calc() -> Response:
    """Flask Response 타입으로 명확한 반환 타입 선언"""
    data_raw: Any = request.get_json(silent=True)
    try:
        # 타입 검증 + 변환: CalcParams로 확정
        params = validate_params(data_raw, CalcParams)
    except ValidationError as e:
        return make_response(jsonify({"error": str(e)}), 400)
    
    # 명시적인 함수 호출 - 타입 체커가 자동으로 CalcParams 인식
    result = process_calc(params)
    return make_response(jsonify({"result": result}), 200)
```

**개선 전 vs 후:**

1. **함수 분리:**
```python
# 개선 전: 문자열로 타입 구분 (오버로드 필요)
result = process_job("calc", params)
result = process_job("echo", params)

# 개선 후: 독립 함수로 명확한 의도
result = process_calc(params)
result = process_echo(params)
```

2. **Flask Response 타입:**
```python
# 개선 전: Tuple[Any, int] - Any 사용으로 타입 불명확
@app.post("/calc")
def calc() -> Tuple[Any, int]:
    return jsonify({"result": result}), 200

# 개선 후: Response - 명시적인 Flask Response 타입
@app.post("/calc")
def calc() -> Response:
    return make_response(jsonify({"result": result}), 200)
```

### JobPayload 생성 시 타입 명시
```python
# 제네릭 타입 명시로 params 타입 확정
calc_payload: JobPayload[CalcParams] = {
    "id": job_id,
    "type": "calc",
    "params": params,  # CalcParams 타입
    "status": "done",
    "result": result,
}
jobs[job_id] = calc_payload
```

### 타입 체커의 이점
```python
# IDE에서 자동완성 지원
params.get("op")    # "add" | "sub" | "mul" | "div"
params.get("a")     # float
params.get("b")     # float

# 잘못된 필드 접근 시 경고
params.get("invalid")  # TypedDict에 없는 키

# Flask Response 타입
response = calc()   # Response 타입으로 인식
response.status_code  # 200 (타입 체커가 속성 인식)
```

## 타입 안전성 체크리스트

- [x] `Any` 사용 제거 (Flask request 등 불가피한 경우만)
- [x] 제네릭 TypedDict로 구조화
- [x] 타입 검증 레이어 (`validate_params`)
- [x] ~~오버로드로 함수 시그니처 명확화~~ → **독립 함수로 분리** ✨
- [x] ~~`Literal` 타입으로 job_type 구분~~ → **함수 이름으로 구분**
- [x] ~~`Tuple[Any, int]` 반환~~ → **`Response` 타입 사용** ✨
- [x] `cast()` 사용 최소화 (검증 레이어로 캡슐화)

## 설계 원칙

### ✅ DO: 명시적 함수 분리
```python
def process_calc(params: CalcParams) -> JobResult: ...
def process_echo(params: EchoParams) -> JobResult: ...
```
- 함수 이름만으로 명확한 의도
- 타입 체커 자동 추론
- 오버로드 불필요

### ✅ DO: Flask Response 타입 사용
```python
@app.post("/calc")
def calc() -> Response:
    return make_response(jsonify({"result": result}), 200)
```
- 명시적인 반환 타입
- `Any` 사용 제거
- IDE 자동완성 지원

### ❌ DON'T: 문자열 타입 디스패처
```python
def process_job(job_type: str, params: Any) -> Any: ...
# 타입 안전성 상실, 오버로드로 복잡도 증가
```

### ❌ DON'T: Tuple[Any, int] 반환
```python
def endpoint() -> Tuple[Any, int]:
    return jsonify(...), 200
# Any 사용으로 타입 정보 손실
```

## 참고 자료
- [PEP 589 – TypedDict](https://peps.python.org/pep-0589/)
- [PEP 544 – Protocols](https://peps.python.org/pep-0544/)
- [PEP 612 – Parameter Specification Variables](https://peps.python.org/pep-0612/)
- [mypy strict mode](https://mypy.readthedocs.io/en/stable/command_line.html#cmdoption-mypy-strict)
