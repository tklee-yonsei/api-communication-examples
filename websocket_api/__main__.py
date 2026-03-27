"""WebSocket 서버 실행 진입점.

이 모듈은 `python -m websocket_api.server`로 서버를 실행할 수 있도록 합니다.
"""

from __future__ import annotations

from websocket_api.server import WebSocketServer

if __name__ == "__main__":
    server = WebSocketServer()
    server.run(host="0.0.0.0", port=8082)
