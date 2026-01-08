# 마이크로서비스 API 통신 예제

마이크로서비스 간 통신 방식을 비교하고 실습하는 프로젝트입니다.

## 참고 글

이 프로젝트는 다음 글과 함께 작성된 코드 예제입니다:

- [마이크로서비스 API 통신 방식 완벽 가이드](https://tklee-yonsei.github.io/aimimo_web/ko/blog/communication/)

## 통신 방식

| 방식              | 특징                      | 사용 사례            |
| ----------------- | ------------------------- | -------------------- |
| **REST API**      | HTTP 기반, 요청-응답      | CRUD 작업, 외부 API  |
| **gRPC**          | 바이너리 프로토콜, 고성능 | 내부 서비스 간 통신  |
| **WebSocket**     | 양방향 실시간             | 모니터링, 알림       |
| **Message Queue** | 비동기 처리               | 작업 큐, 이벤트 처리 |

## 프로젝트 구조

```text
.
├── .devcontainer/     # VS Code 개발 컨테이너 설정
├── rest_api/          # Flask REST API 서버/클라이언트
├── grpc/              # gRPC 서버/클라이언트 + proto 파일
├── websocket/         # Flask-SocketIO 실시간 통신
├── message_queue/     # Redis 기반 작업 큐
└── docker-compose.yml # 테스트 환경 구성
```

## 개발 환경

### Dev Container (VS Code)

VS Code에서 Dev Container로 열면 필요한 패키지가 자동 설치됩니다.

### 테스트 환경 (Docker Compose)

여러 서비스를 동시에 실행하여 통신 테스트:

```bash
docker-compose up -d
```

| 서비스           | 포트  | 설명                 |
| ---------------- | ----- | -------------------- |
| REST API         | 8080  | Flask REST 서버      |
| WebSocket        | 8081  | Flask-SocketIO 서버  |
| gRPC             | 50051 | gRPC 서버            |
| Redis            | 6379  | Message Queue        |
| Worker           | -     | 작업 처리 (2 인스턴스) |

## 참고 자료

- [gRPC 공식 문서](https://grpc.io/docs/)
- [Socket.IO 문서](https://socket.io/docs/v4/)
- [Redis Pub/Sub](https://redis.io/docs/manual/pubsub/)
