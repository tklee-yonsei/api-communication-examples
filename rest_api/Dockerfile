FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    flask \
    requests \
    types-requests

COPY communication/ /app/communication
COPY rest_api/ /app/rest_api

EXPOSE 8080
CMD ["python", "-m", "rest_api.server"]
