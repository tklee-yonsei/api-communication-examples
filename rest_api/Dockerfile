FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 프로젝트 파일 복사
COPY pyproject.toml /app/
COPY communication/ /app/communication
COPY rest_api/ /app/rest_api

# pyproject.toml의 의존성 설치
RUN pip install --no-cache-dir .

EXPOSE 8080

# Uvicorn으로 FastAPI 서버 실행
CMD ["uvicorn", "rest_api.server:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
