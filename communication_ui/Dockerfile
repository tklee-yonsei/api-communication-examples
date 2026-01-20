FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 프로젝트 파일 복사
COPY pyproject.toml uv.lock* /app/
COPY communication/ /app/communication
COPY rest_api/ /app/rest_api
COPY communication_ui/ /app/communication_ui

# uv로 의존성 설치 (시스템 Python에 직접 설치)
RUN uv pip install --system -r pyproject.toml

EXPOSE 3000

CMD ["python", "-m", "communication_ui.rest.app"]
