"""MQ 서버 실행 진입점.

이 모듈은 `python -m mq_api`로 서버를 실행할 수 있도록 합니다.
"""

from __future__ import annotations

import os

import uvicorn

from mq_api.server import MQServer

if __name__ == "__main__":
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    server = MQServer(redis_url=redis_url)
    uvicorn.run(server.app, host="0.0.0.0", port=8083)
