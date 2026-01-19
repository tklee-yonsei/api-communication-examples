# 비동기 처리 전략

## 현재 상태 분석

### 문제점

```python
@app.post("/hash_jobs")
def create_hash_job() -> Response:
    # ❌ 문제: "비동기"라고 하지만 즉시 처리
    result = process_hash(params)  # 블로킹!
    return make_response(jsonify({"job_id": job_id, "status": "done"}), 201)
```

### 동기 vs 비동기 엔드포인트 차이

| 엔드포인트 타입                        | 현재 동작                 | 이상적인 동작                             |
| -------------------------------------- | ------------------------- | ----------------------------------------- |
| **동기** (`/echo`, `/calc`, `/stats`)  | ✅ 즉시 처리 후 결과 반환  | ✅ 그대로 유지 또는 async/await로 개선     |
| **비동기** (`/hash_jobs`, `/fib_jobs`) | ❌ 즉시 처리 (가짜 비동기) | ✅ 큐에 넣고 job_id 반환 → 백그라운드 처리 |

## Python 비동기 옵션

### 1. Flask 네이티브 async/await (Flask 2.0+)

**동기 엔드포인트 개선:**

```python
@app.post("/calc")
async def calc() -> Response:
    """async/await로 비블로킹 I/O 가능"""
    data_raw: Any = request.get_json(silent=True)
    try:
        params = validate_params(data_raw, CalcParams)
    except ValidationError as e:
        return make_response(jsonify({"error": str(e)}), 400)
    
    # CPU 바운드 작업은 여전히 블로킹
    # I/O 바운드라면 await로 개선 가능
    result = process_calc(params)
    return make_response(jsonify({"result": result}), 200)
```

**장점:**

- Flask 내장 기능
- 코드 변경 최소
- I/O 바운드 작업에 효과적

**단점:**

- CPU 바운드 작업(calc, fib)은 여전히 블로킹
- 진정한 백그라운드 작업 큐는 아님

### 2. threading.Thread (간단한 백그라운드 작업)

**비동기 엔드포인트 개선:**

```python
import threading

@app.post("/hash_jobs")
def create_hash_job() -> Response:
    job_id = str(uuid.uuid4())
    
    # 1. 즉시 pending 상태로 저장
    jobs[job_id] = {
        "id": job_id,
        "type": "hash",
        "params": params,
        "status": "pending",
        "result": None,
    }
    
    # 2. 백그라운드 스레드에서 처리
    def process_in_background():
        result = process_hash(params)
        jobs[job_id]["status"] = "done"
        jobs[job_id]["result"] = result
    
    thread = threading.Thread(target=process_in_background)
    thread.start()
    
    # 3. 즉시 job_id 반환
    return make_response(jsonify({"job_id": job_id, "status": "pending"}), 202)
```

**장점:**

- 추가 의존성 불필요
- 간단한 구현
- 진정한 비동기 처리

**단점:**

- 서버 재시작 시 작업 손실
- 분산 환경에서 작동 안 함
- 작업 관리 기능 부족

### 3. Celery (프로덕션급 작업 큐) ⭐ 추천

**설치:**

```bash
pip install celery[redis]
```

**Celery 워커 설정:**

```python
# rest_api/worker.py
from celery import Celery

celery_app = Celery(
    "rest_api",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

@celery_app.task
def process_hash_task(params: dict) -> dict:
    """백그라운드에서 실행될 작업"""
    from rest_api.core.jobs import process_hash
    return process_hash(params)

@celery_app.task
def process_fib_task(params: dict) -> dict:
    """백그라운드에서 실행될 작업"""
    from rest_api.core.jobs import process_fib
    return process_fib(params)
```

**Flask 엔드포인트:**

```python
from rest_api.worker import process_hash_task

@app.post("/hash_jobs")
def create_hash_job() -> Response:
    job_id = str(uuid.uuid4())
    
    # Celery 작업 시작 (non-blocking)
    task = process_hash_task.apply_async(
        args=[params],
        task_id=job_id
    )
    
    # 즉시 반환
    return make_response(jsonify({
        "job_id": job_id,
        "status": "pending"
    }), 202)

@app.get("/jobs/<job_id>")
def get_job(job_id: str) -> Response:
    """Celery 작업 상태 조회"""
    from celery.result import AsyncResult
    
    task = AsyncResult(job_id, app=celery_app)
    
    if task.state == "PENDING":
        status = "pending"
        result = None
    elif task.state == "SUCCESS":
        status = "done"
        result = task.result
    elif task.state == "FAILURE":
        status = "failed"
        result = {"error": str(task.info)}
    else:
        status = task.state.lower()
        result = None
    
    return make_response(jsonify({
        "id": job_id,
        "status": status,
        "result": result
    }), 200)
```

**장점:**

- 프로덕션급 안정성
- 분산 처리 가능
- 작업 재시도, 스케줄링, 모니터링 지원
- Redis/RabbitMQ 백엔드
- 서버 재시작 후에도 작업 유지

**단점:**

- 추가 인프라 필요 (Redis)
- 학습 곡선

### 4. FastAPI (현대적 비동기 프레임워크)

**완전히 새로운 프레임워크:**

```python
from fastapi import FastAPI, HTTPException
from typing import Optional

app = FastAPI()

@app.post("/calc")
async def calc(params: CalcParams) -> dict:
    """네이티브 async/await 지원"""
    result = await process_calc_async(params)
    return {"result": result}
```

**장점:**

- 네이티브 async/await
- 뛰어난 타입 지원 (Pydantic)
- 자동 OpenAPI 문서
- 고성능

**단점:**

- 전체 재작성 필요
- Flask에서 마이그레이션 비용

## 추천 솔루션

### 프로젝트 목적별 선택

#### 1. 간단한 데모/학습용 ✅ **현재 구현**

→ **threading.Thread**

- 추가 의존성 없음
- 구현 간단
- 비동기 개념 학습에 적합

#### 2. 실제 프로덕션 환경

→ **Celery** ⭐

- 안정적이고 검증됨
- 분산 처리 가능
- 작업 관리 기능 풍부

#### 3. 성능이 중요한 새 프로젝트

→ **FastAPI**

- 최고의 성능
- 현대적인 Python 패턴
- 타입 안전성 우수

## 현재 구현 상태

### ✅ Phase 1: 통합 작업 큐 구현 완료 (`rest_api/job_queue.py`)

**아키텍처:**

```text
Flask API → JobQueue → queue.Queue → ThreadPoolExecutor (워커 풀)
                                              ↓
                                         작업 실행
                                              ↓
                                         결과 저장
```

**동기 엔드포인트:**

- `/echo`, `/calc`, `/stats`
- 즉시 결과 반환 (200 OK)
- 작업 완료까지 블로킹

**비동기 엔드포인트:**

- `/hash_jobs`, `/fib_jobs`
- 즉시 job_id 반환 (202 Accepted)
- **통합 작업 큐**에서 처리
- `GET /jobs/{job_id}`로 상태 조회
- `GET /queue/status`로 큐 상태 확인

**구현 방식 (`rest_api/job_queue.py`):**
```python
# 1. 전역 통합 큐 생성
job_queue = JobQueue(max_workers=4, max_queue_size=100)
job_queue.start()

# 2. 작업 객체 생성 및 큐 제출
job = Job(
    job_id=job_id,
    job_type="hash",
    handler=process_hash,
    params=params,
    store=jobs
)
job_queue.submit(job)  # 큐에 추가

# 3. 워커 풀에서 비동기 처리
# - 최대 4개의 워커가 동시에 작업 처리
# - queue.Queue로 작업 스케줄링
# - ThreadPoolExecutor로 스레드 풀 관리
```

**주요 개선 사항:**

- ✅ **통합 관리**: 모든 비동기 작업을 하나의 큐로 관리
- ✅ **워커 풀**: 무제한 스레드 생성 방지 (최대 4개)
- ✅ **백프레셔**: 큐 크기 제한 (최대 100개)
- ✅ **스케줄링**: FIFO 방식으로 공정한 처리
- ✅ **모니터링**: `/queue/status` 엔드포인트로 상태 확인

**개선 전 vs 후 비교:**

| 항목        | 개선 전 (API당 스레드) | 개선 후 (통합 큐)     |
| ----------- | ---------------------- | --------------------- |
| 스레드 생성 | 요청마다 무제한        | 워커 풀 (최대 4개) ✅  |
| 작업 관리   | API별로 분산           | 통합 큐로 중앙 관리 ✅ |
| 스케줄링    | 없음                   | FIFO 큐 ✅             |
| 백프레셔    | 없음 (OOM 위험)        | 큐 크기 제한 ✅        |
| 모니터링    | 불가능                 | `/queue/status` ✅     |
| 리소스 제어 | ❌                      | ✅                     |
| 동시성 제한 | ❌                      | ✅                     |

**코드 비교:**

```python
# 개선 전: API당 스레드 생성
def create_hash_job():
    job_id = str(uuid.uuid4())
    jobs[job_id] = {..., "status": "pending"}
    
    # ❌ 무제한 스레드 생성 - 리소스 고갈 위험
    def process():
        result = process_hash(params)
        jobs[job_id]["status"] = "done"
    
    threading.Thread(target=process, daemon=True).start()
    return {"job_id": job_id}

# 개선 후: 통합 큐 사용
def create_hash_job():
    job_id = str(uuid.uuid4())
    jobs[job_id] = {..., "status": "pending"}
    
    # ✅ 통합 큐에 제출 - 워커 풀이 처리
    job = Job(job_id, "hash", process_hash, params, jobs)
    job_queue.submit(job)  # 큐가 가득 차면 False 반환
    
    return {"job_id": job_id}
```

### 향후 계획

#### Phase 2: Celery로 업그레이드 (Message Queue 섹션)

Message Queue 예제로 확장하여 실제 큐 시스템 비교

#### Phase 3 (선택): FastAPI 버전 추가

REST/gRPC/WebSocket/MQ와 함께 FastAPI 비교군 추가

## docker-compose 통합

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  rest-api:
    build: .
    depends_on:
      - redis
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0

  celery-worker:
    build: .
    command: celery -A rest_api.worker worker --loglevel=info
    depends_on:
      - redis
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
```

## 참고 자료

- [Flask async/await](https://flask.palletsprojects.com/en/2.3.x/async-await/)
- [Celery Documentation](https://docs.celeryq.dev/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Python asyncio](https://docs.python.org/3/library/asyncio.html)
