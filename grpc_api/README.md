# gRPC API 서버

REST API와 동일한 기능을 gRPC 프로토콜로 제공하는 서버입니다.

## 특징

- **고성능 바이너리 프로토콜**: HTTP/2 기반의 효율적인 통신
- **강력한 타입 시스템**: Protocol Buffers를 통한 스키마 정의
- **스트리밍 지원**: 서버-사이드 스트리밍으로 실시간 작업 상태 모니터링
- **공통 인터페이스**: REST API와 동일한 `JobClient` 인터페이스 구현

## 지원 작업

### 동기 작업 (Unary RPC)

요청을 받으면 즉시 결과를 반환합니다.

| RPC 메서드 | 설명               | 파라미터                           |
| ---------- | ------------------ | ---------------------------------- |
| `Echo`     | 입력을 그대로 반환 | `data: map<string, string>`        |
| `Calc`     | 사칙연산 수행      | `op: string, a: double, b: double` |
| `Stats`    | 리스트 통계 계산   | `values: repeated double`          |

### 비동기 작업 (Unary RPC + Polling)

job_id를 즉시 반환하고, `GetJob`으로 결과를 조회합니다.

| RPC 메서드       | 설명                   | 파라미터                    |
| ---------------- | ---------------------- | --------------------------- |
| `CreateHashJob`  | SHA-256 해시 작업 생성 | `data: map<string, string>` |
| `CreateFibJob`   | 피보나치 작업 생성     | `n: int32`                  |
| `GetJob`         | 작업 상태 조회         | `id: string`                |
| `ListJobs`       | 전체 작업 목록 조회    | `limit: int32`              |
| `GetQueueStatus` | 작업 큐 상태 조회      | -                           |

### 스트리밍 RPC (gRPC 고유 기능)

| RPC 메서드  | 설명                             |
| ----------- | -------------------------------- |
| `WatchJobs` | 작업 상태 변경을 실시간 스트리밍 |

## 사용법

### 서버 실행

```bash
# 개발 환경 (Docker Compose)
docker compose --profile dev up -d grpc-api-dev

# 또는 직접 실행
python -m grpc_api.server
```

### 클라이언트 사용

```python
from grpc_api.client import GrpcJobClient, AsyncGrpcJobClient

# 동기 클라이언트
with GrpcJobClient(host="localhost", port=50051) as client:
    # Echo 작업
    record = client.create_job("echo", {"message": "Hello"})
    print(record)

    # 비동기 작업 생성 후 조회
    record = client.create_job("fib", {"n": 20})
    status = client.get_job(record.id)
    print(status)

# 비동기 클라이언트
async with AsyncGrpcJobClient(host="localhost", port=50051) as client:
    record = await client.create_job("calc", {"op": "add", "a": 1, "b": 2})
    print(record)
```

### grpcurl 사용 예시

```bash
# Echo 작업
grpcurl -plaintext -d '{"data": {"message": "hello"}}' \
  localhost:50051 jobs.JobService/Echo

# Calc 작업
grpcurl -plaintext -d '{"op": "mul", "a": 6, "b": 7}' \
  localhost:50051 jobs.JobService/Calc

# 피보나치 작업 생성
grpcurl -plaintext -d '{"n": 20}' \
  localhost:50051 jobs.JobService/CreateFibJob

# 작업 상태 조회
grpcurl -plaintext -d '{"id": "your-job-id"}' \
  localhost:50051 jobs.JobService/GetJob

# 작업 상태 스트리밍
grpcurl -plaintext -d '{}' \
  localhost:50051 jobs.JobService/WatchJobs
```

## Proto 파일 컴파일

Proto 파일을 수정한 후에는 Python 코드를 재생성해야 합니다:

```bash
python -m grpc_api.compile_proto
```

또는 직접 실행:

```bash
python -m grpc_tools.protoc \
  --proto_path=grpc_api/protos \
  --python_out=grpc_api/protos \
  --grpc_python_out=grpc_api/protos \
  --pyi_out=grpc_api/protos \
  grpc_api/protos/jobs.proto
```

## REST API와의 비교

| 특성          | REST API              | gRPC                |
| ------------- | --------------------- | ------------------- |
| 프로토콜      | HTTP/1.1 (JSON)       | HTTP/2 (Protobuf)   |
| 타입 안전성   | 런타임 검증           | 컴파일 타임 검증    |
| 성능          | 좋음                  | 매우 좋음           |
| 디버깅        | 쉬움 (curl, 브라우저) | 도구 필요 (grpcurl) |
| 스트리밍      | WebSocket 필요        | 네이티브 지원       |
| 브라우저 지원 | 네이티브              | gRPC-Web 필요       |

## 파일 구조

```text
grpc_api/
├── __init__.py
├── server.py           # gRPC 서버 구현
├── client.py           # 동기/비동기 클라이언트
├── compile_proto.py    # Proto 컴파일 스크립트
├── example_async.py    # 사용 예제
├── Dockerfile          # 프로덕션 빌드
├── Dockerfile.dev      # 개발용 빌드
├── README.md           # 이 파일
├── core/
│   └── jobs/           # REST API의 jobs 모듈 재사용
└── protos/
    ├── jobs.proto      # gRPC 서비스 정의
    ├── jobs_pb2.py     # 생성된 메시지 코드
    ├── jobs_pb2.pyi    # 타입 스텁
    └── jobs_pb2_grpc.py # 생성된 서비스 코드
```
