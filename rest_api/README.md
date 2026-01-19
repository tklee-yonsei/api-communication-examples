# REST API 모듈

FastAPI 기반 비동기 REST API 작업 처리 시스템

## 주요 특징

- ✨ **FastAPI**: 현대적이고 빠른 비동기 웹 프레임워크
- 🚀 **완전 비동기**: 모든 작업이 async/await로 처리
- 📝 **자동 문서화**: `/docs`에서 Swagger UI 제공
- 🔄 **비동기 작업 큐**: asyncio 기반 작업 스케줄링
- 🎯 **타입 안전성**: TypedDict와 타입 힌트 활용

## 디렉토리 구조

```text
rest_api/
├── server.py          # FastAPI 서버 진입점
├── client.py          # REST 클라이언트 구현
├── Dockerfile         # 컨테이너 설정
├── __init__.py        # 패키지 진입점
└── core/              # 서버 핵심 구성요소
    ├── job_queue.py   # 비동기 작업 큐 (asyncio 기반)
    ├── validation.py  # 요청 파라미터 검증
    └── jobs/          # 작업 처리 로직
        ├── base.py    # 비동기 작업 인터페이스
        ├── types.py   # 작업 타입 정의
        ├── echo.py    # Echo 작업 (async)
        ├── calc.py    # 계산 작업 (async)
        ├── stats.py   # 통계 작업 (async)
        ├── hash_job.py # 해시 작업 (async)
        └── fib.py     # 피보나치 작업 (async)
```

## 주요 컴포넌트

### server.py

- **FastAPI 기반 비동기 REST API 서버**
- 즉시 응답 엔드포인트: `/echo`, `/calc`, `/stats` (모두 async)
- 백그라운드 작업 엔드포인트: `/hash_jobs`, `/fib_jobs`
- 작업 조회: `/jobs/<job_id>`
- 큐 상태: `/queue/status`
- **자동 API 문서**: `/docs` (Swagger UI), `/redoc` (ReDoc)

### client.py

- `RestJobClient`: `JobClient` 인터페이스 구현
- REST API를 통한 작업 생성 및 조회
- requests 기반 동기 클라이언트

### core/job_queue.py

- `JobQueue`: asyncio 기반 비동기 작업 큐
- asyncio.Queue와 asyncio.Task 활용
- 동시 실행 작업 수 제한 (Semaphore)
- 큐 크기 제한으로 백프레셔 제공

### core/jobs/base.py

- `AsyncJobHandler`: 비동기 작업 처리 인터페이스
- 모든 작업이 이 인터페이스를 따름
- Generic 타입으로 타입 안전성 보장

### core/validation.py

- 요청 파라미터 검증 유틸리티
- TypedDict 기반 타입 변환 및 검증

### core/jobs/

- **모든 작업이 async 함수로 구현**
- `types.py`: 모든 작업 타입 정의
- 각 작업 모듈: 독립적인 비동기 처리 함수 제공

## 사용 예시

### 서버 실행

```bash
# 직접 실행
python -m rest_api.server

# 또는 uvicorn으로 실행
uvicorn rest_api.server:create_app --factory --host 0.0.0.0 --port 8080
```

### API 문서 확인

서버 실행 후 브라우저에서:

- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`

### 클라이언트 사용

```python
from rest_api import RestJobClient

client = RestJobClient("http://localhost:8080")

# 즉시 응답 작업
job = client.create_job("echo", {"message": "Hello FastAPI!"})
print(job.status)  # "done"

# 백그라운드 작업
job = client.create_job("hash", {"data": "test"})
print(job.status)  # "pending"

# 작업 상태 확인
result = client.get_job(job.id)
print(result.status)  # "done" or "pending"
```

### 비동기 작업 직접 호출

```python
import asyncio
from rest_api.core.jobs import process_echo

async def main():
    result = await process_echo({"message": "Hello"})
    print(result)

asyncio.run(main())
```

## 테스트

```bash
# 전체 테스트
pytest tests/rest_api/

# 특정 테스트
pytest tests/rest_api/test_rest_client_contract.py -v
```

## 의존성

- `fastapi>=0.115.0`: 비동기 웹 프레임워크
- `uvicorn[standard]>=0.32.0`: ASGI 서버
- `httpx>=0.27.0`: 비동기 HTTP 클라이언트
- `requests>=2.32`: 동기 HTTP 클라이언트
