FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# FastAPI 및 관련 패키지 설치
RUN pip install --no-cache-dir \
    fastapi>=0.115.0 \
    "uvicorn[standard]>=0.32.0" \
    httpx>=0.27.0 \
    requests>=2.32 \
    types-requests

COPY communication/ /app/communication
COPY rest_api/ /app/rest_api

EXPOSE 8080

# Uvicorn으로 FastAPI 서버 실행
CMD ["uvicorn", "rest_api.server:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
