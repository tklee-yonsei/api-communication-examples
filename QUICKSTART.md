# FastAPI 서버 빠른 시작 가이드

## 🚀 로컬 실행

### 1. 직접 실행

```bash
# 의존성 설치
pip install fastapi uvicorn httpx requests

# 서버 실행
python -m rest_api.server

# 또는 uvicorn으로 실행 (권장)
uvicorn rest_api.server:create_app --factory --host 0.0.0.0 --port 8080 --reload
```

### 2. API 문서 확인

서버 실행 후:

- **Swagger UI**: <http://localhost:8080/docs>
- **ReDoc**: <http://localhost:8080/redoc>

### 3. 테스트 요청

```bash
# Echo 엔드포인트
curl -X POST http://localhost:8080/echo \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello FastAPI!"}'

# Calc 엔드포인트
curl -X POST http://localhost:8080/calc \
  -H "Content-Type: application/json" \
  -d '{"op": "add", "a": 10, "b": 5}'

# Hash 백그라운드 작업
curl -X POST http://localhost:8080/hash_jobs \
  -H "Content-Type: application/json" \
  -d '{"data": "test"}'

# 작업 상태 확인 (job_id는 위 응답에서 받은 값)
curl http://localhost:8080/jobs/{job_id}

# 큐 상태 확인
curl http://localhost:8080/queue/status
```

## 🐳 Docker로 실행

### 1. Docker Compose로 실행 (권장)

```bash
# 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f rest-api

# 서비스 중지
docker-compose down
```

### 2. 단일 컨테이너 실행

```bash
# 이미지 빌드
docker build -t rest-api -f rest_api/Dockerfile .

# 컨테이너 실행
docker run -p 8080:8080 rest-api

# 백그라운드 실행
docker run -d -p 8080:8080 --name rest-api rest-api
```

## 📊 UI 테스트 도구

Communication UI를 통해 브라우저에서 테스트:

```bash
# Docker Compose로 전체 환경 시작
docker-compose up -d

# 브라우저에서 접속
# http://localhost:3000
```

UI에서 다음 작업 가능:

- 1개/100개/10000개 요청 전송
- 성능 및 정확도 측정
- 실시간 결과 확인

## 🧪 비동기 작업 예제

### Python 스크립트로 테스트

```bash
python rest_api/example_async.py
```

### 대화형 테스트

```python
import asyncio
from rest_api.core.jobs import process_echo, process_calc

async def test():
    # Echo
    result = await process_echo({"message": "Hello!"})
    print(result)
    
    # Calc
    result = await process_calc({"op": "mul", "a": 3, "b": 4})
    print(result)

asyncio.run(test())
```

## 📝 주요 엔드포인트

| 메서드 | 경로             | 설명               | 응답      |
| ------ | ---------------- | ------------------ | --------- |
| POST   | `/echo`          | 입력 반환          | 즉시      |
| POST   | `/calc`          | 사칙연산           | 즉시      |
| POST   | `/stats`         | 통계 계산          | 즉시      |
| POST   | `/hash_jobs`     | 해시 작업 생성     | job_id    |
| POST   | `/fib_jobs`      | 피보나치 작업 생성 | job_id    |
| GET    | `/jobs/{job_id}` | 작업 상태 조회     | 작업 정보 |
| GET    | `/queue/status`  | 큐 상태 조회       | 큐 정보   |
| GET    | `/docs`          | Swagger UI         | HTML      |
| GET    | `/redoc`         | ReDoc              | HTML      |

## 🔧 개발 환경

### VSCode Devcontainer

```bash
# VSCode에서 "Reopen in Container" 클릭
# 또는 Cmd/Ctrl + Shift + P → "Dev Containers: Reopen in Container"
```

Devcontainer에는 다음이 포함됩니다:

- Python 3.14
- FastAPI, Uvicorn, httpx
- Black, Pylint, pytest
- 모든 API 통신 도구 (gRPC, WebSocket, Message Queue)

## 📚 추가 문서

- [REST API 상세 문서](rest_api/README.md)
- [프로젝트 타입 정의](TYPES.md)
- [비동기 처리 가이드](ASYNC.md)
