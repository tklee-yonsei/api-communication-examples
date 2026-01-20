FROM python:3.14-slim

# 시스템 패키지 업데이트 및 기본 도구 설치
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    git-flow \
    vim \
    nano \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# pip 업그레이드
RUN pip install --no-cache-dir --upgrade pip

# 코드 품질 도구
RUN pip install --no-cache-dir \
    black \
    pylint \
    pytest \
    pytest-asyncio

# 추가 통신 프로토콜용 패키지 (gRPC, WebSocket, Message Queue)
RUN pip install --no-cache-dir \
    grpcio \
    grpcio-tools \
    flask-socketio \
    "python-socketio[client]" \
    redis \
    pika

# 작업 디렉토리 설정
WORKDIR /workspace

# pyproject.toml 복사 후 의존성 설치 (postCreateCommand에서 처리하도록 변경 가능)
# 개발 환경에서는 볼륨 마운트 후 설치하는 것이 더 유연함
