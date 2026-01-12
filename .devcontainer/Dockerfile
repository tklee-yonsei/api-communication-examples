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

# 코드 품질 도구 + 타입 스텁
RUN pip install --no-cache-dir \
    black \
    pylint \
    pytest \
    types-requests

# API 통신 예제용 패키지
RUN pip install --no-cache-dir \
    # REST API
    flask \
    requests \
    # gRPC
    grpcio \
    grpcio-tools \
    # WebSocket
    flask-socketio \
    "python-socketio[client]" \
    # Message Queue
    redis \
    pika

# 작업 디렉토리 설정
WORKDIR /workspace
