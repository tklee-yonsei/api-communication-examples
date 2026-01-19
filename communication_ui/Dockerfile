FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir \
    flask \
    requests \
    types-requests

COPY communication/ /app/communication
COPY rest_api/ /app/rest_api
COPY communication_ui/ /app/communication_ui

EXPOSE 3000
CMD ["python", "-m", "communication_ui.rest.app"]
