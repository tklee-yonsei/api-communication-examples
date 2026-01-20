FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 프로젝트 파일 복사
COPY pyproject.toml /app/
COPY communication/ /app/communication
COPY rest_api/ /app/rest_api
COPY communication_ui/ /app/communication_ui

# pyproject.toml의 의존성 설치
RUN pip install --no-cache-dir .

EXPOSE 3000
CMD ["python", "-m", "communication_ui.rest.app"]
