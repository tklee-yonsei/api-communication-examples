# 마이크로서비스 API 통신 예제

마이크로서비스 간 통신 방식을 비교하고 실습하는 프로젝트입니다.
현재는 **REST API**, **gRPC**, **WebSocket** 경로의 서버/클라이언트를 제공합니다. Message Queue 버전은 이후 단계에서 추가됩니다.

## 참고 글

이 프로젝트는 다음 글과 함께 작성된 코드 예제입니다:

- [마이크로서비스 API 통신 방식 완벽 가이드](https://tklee-yonsei.github.io/aimimo_web/ko/blog/communication/)

## 통신 방식

| 방식              | 특징                      | 사용 사례            | 상태     |
| ----------------- | ------------------------- | -------------------- | -------- |
| **REST API**      | HTTP 기반, 요청-응답      | CRUD 작업, 외부 API  | ✅ 구현됨 |
| **gRPC**          | 바이너리 프로토콜, 고성능 | 내부 서비스 간 통신  | ✅ 구현됨 |
| **WebSocket**     | 양방향 실시간             | 모니터링, 알림       | ✅ 구현됨 |
| **Message Queue** | 비동기 처리               | 작업 큐, 이벤트 처리 | 🚧 예정   |

## 프로젝트 구조

```text
.
├── communication/     # 공통 인터페이스 (JobClient 등)
├── rest_api/          # FastAPI REST API 서버/클라이언트
├── grpc_api/          # gRPC 서버/클라이언트
├── communication_ui/  # 통신 실험용 웹 UI
└── docker-compose.yml # 테스트 환경 구성
```

## 개발 환경

### Dev Container (VS Code)

VS Code에서 Dev Container로 열면 필요한 패키지가 자동 설치됩니다.

### 테스트 환경 (Docker Compose)

REST 서버, gRPC 서버, 웹 UI를 함께 실행합니다:

```bash
# 개발 환경 (핫리로드 활성화)
docker compose --profile dev up -d

# 프로덕션 환경
docker compose --profile prod up -d
```

| 서비스           | 포트  | 설명                                      |
| ---------------- | ----- | ----------------------------------------- |
| REST API         | 8080  | FastAPI REST 서버 (curl로 직접 호출 가능) |
| gRPC API         | 50051 | gRPC 서버 (grpcurl로 호출 가능)           |
| communication-ui | 3001  | 브라우저 UI. 1/100/10000 버튼 지원        |

### UI 사용법 (communication-ui)

1) 브라우저에서 <http://localhost:3000> 접속  
2) `REST API Base URL` 기본값(rest-api:8080)은 컨테이너 간 호출용이며, 호스트에서 직접 호출하려면 `http://localhost:8080`으로 변경  
3) "Job 타입 예시" 버튼으로 job type/params를 자동 채움  
4) `1/100/10000개 전송` 버튼으로 대량 요청 → 처리 속도/성공 수를 확인  
5) 비동기 작업(hash, fib)의 경우 결과의 `job_id`를 하단 "상태 조회"에서 확인

### 지원 job 타입 (REST)

#### 동기 작업 (즉시 결과 반환 - 200 OK)

작업이 완료될 때까지 **블로킹**되며, 완료 후 결과를 즉시 반환합니다.

- `echo`: `POST /echo` - 입력을 그대로 반환
  - 예: `{"message": "hello"}`
  - 응답: `{"result": {"echo": {"message": "hello"}}}`
  
- `calc`: `POST /calc` - 사칙연산 수행
  - 예: `{"op": "mul", "a": 6, "b": 7}`
  - 응답: `{"result": {"op": "mul", "a": 6, "b": 7, "result": 42}}`
  
- `stats`: `POST /stats` - 리스트 통계 계산
  - 예: `{"values": [1, 2, 3, 4, 5]}`
  - 응답: `{"result": {"count": 5, "min": 1, "max": 5, ...}}`

#### 비동기 작업 (job_id 즉시 반환 - 202 Accepted)

요청을 받으면 즉시 `job_id`를 반환하고, **백그라운드 스레드**에서 작업을 처리합니다.  
`GET /jobs/{job_id}`로 완료 여부와 결과를 조회할 수 있습니다.

- `hash`: `POST /hash_jobs` - SHA-256 해시 계산 (백그라운드)
  - 예: `{"foo": "bar"}`
  - 즉시 응답: `{"job_id": "uuid...", "status": "pending"}`
  - 조회 시: `{"id": "uuid...", "status": "done", "result": {...}}`
  
- `fib`: `POST /fib_jobs` - 피보나치 수 계산 (백그라운드, n 최대 40)
  - 예: `{"n": 10}`
  - 즉시 응답: `{"job_id": "uuid...", "status": "pending"}`
  - 조회 시: `{"id": "uuid...", "status": "done", "result": {"n": 10, "fib": 55}}`

**비동기 작업 흐름:**

```text
1. POST /hash_jobs → 202 Accepted, job_id 반환
2. (통합 작업 큐에서 워커 풀이 처리 중...)
3. GET /jobs/{job_id} → status: "pending"
4. (작업 완료)
5. GET /jobs/{job_id} → status: "done", result 포함
6. GET /queue/status → 큐 상태 확인 (대기 중인 작업 수)
```

**통합 작업 큐 특징:**

- **워커 풀**: 최대 4개의 워커가 동시에 작업 처리
- **작업 스케줄링**: FIFO 방식으로 공정하게 처리
- **백프레셔**: 큐가 가득 차면 503 Service Unavailable 반환
- **모니터링**: `/queue/status`로 실시간 큐 상태 확인

### curl 직접 호출 예시

#### 동기 작업 (즉시 결과 반환)

```bash
# 계산 작업 - 즉시 결과 반환
curl -X POST http://localhost:8080/calc \
  -H "Content-Type: application/json" \
  -d '{"op":"add","a":10,"b":20}'
# 응답: {"result": {"op": "add", "a": 10, "b": 20, "result": 30}}
```

#### 비동기 작업 (백그라운드 처리)

```bash
# 1. 피보나치 작업 요청 - 즉시 job_id 반환
curl -X POST http://localhost:8080/fib_jobs \
  -H "Content-Type: application/json" \
  -d '{"n":15}'
# 응답 (202 Accepted): {"job_id": "abc-123...", "status": "pending"}

# 2. 작업 상태 조회 (처리 중)
curl http://localhost:8080/jobs/abc-123...
# 응답: {"id": "abc-123...", "status": "pending", "result": null}

# 3. 작업 상태 조회 (완료 후)
curl http://localhost:8080/jobs/abc-123...
# 응답: {"id": "abc-123...", "status": "done", "result": {"n": 15, "fib": 610}}
```

**비동기의 장점:**

- 클라이언트가 응답을 즉시 받음 (블로킹 안 됨)
- 긴 작업도 타임아웃 없이 처리 가능
- 여러 작업을 동시에 요청 후 나중에 결과 수집
- 통합 워커 풀로 리소스 제어 (최대 4개 동시 실행)

#### 큐 상태 확인

```bash
# 작업 큐 상태 조회
curl http://localhost:8080/queue/status
# 응답: {"queue_size": 3, "is_full": false, "max_workers": 4}
```

## 참고 자료

- [gRPC 공식 문서](https://grpc.io/docs/)
- [Socket.IO 문서](https://socket.io/docs/v4/)
- [Redis Pub/Sub](https://redis.io/docs/manual/pubsub/)
