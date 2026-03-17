"""UI 서버 설정 상수."""

from __future__ import annotations

import os

# REST API 설정
# Docker 네트워크 내부: rest-api:8080
# devcontainer/로컬: host.docker.internal:8080 또는 localhost:8080
DEFAULT_BASE_URL = os.getenv("REST_API_BASE_URL", "http://host.docker.internal:8080")
# WebSocket URL (http -> ws 변환)
DEFAULT_WS_URL = os.getenv(
    "REST_API_WS_URL",
    DEFAULT_BASE_URL.replace("http://", "ws://").replace("https://", "wss://"),
)

# gRPC API 설정
DEFAULT_GRPC_HOST = os.getenv("GRPC_API_HOST", "localhost")
DEFAULT_GRPC_PORT = int(os.getenv("GRPC_API_PORT", "50051"))

# WebSocket API 설정
# Docker 네트워크 내부: websocket-api-dev:8082
# devcontainer/로컬: localhost:8082 (포트 포워딩 필요)
DEFAULT_WEBSOCKET_URL = os.getenv(
    "WEBSOCKET_API_URL", "ws://websocket-api-dev:8082/ws"
)

# Message Queue API 설정
# Docker 네트워크 내부: mq-api-dev:8083
# devcontainer/로컬: localhost:8083 (포트 포워딩 필요)
DEFAULT_MQ_BASE_URL = os.getenv(
    "MQ_API_BASE_URL", "http://mq-api-dev:8083"
)

MAX_CONCURRENCY = 64
MAX_COUNT = 20000
