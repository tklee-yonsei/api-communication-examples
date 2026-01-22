"""WebSocket 연결 관리."""

from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket


class WebSocketManager:
    """WebSocket 연결을 관리하고 브로드캐스트를 처리합니다."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """새로운 WebSocket 연결을 수락합니다."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        """WebSocket 연결을 제거합니다."""
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, object]) -> None:
        """모든 연결된 클라이언트에게 메시지를 브로드캐스트합니다."""
        if not self.active_connections:
            return

        message_json = json.dumps(message, default=str)
        async with self._lock:
            disconnected: list[WebSocket] = []
            for connection in self.active_connections:
                try:
                    await connection.send_text(message_json)
                except Exception:
                    disconnected.append(connection)
            # 끊어진 연결 제거
            for conn in disconnected:
                if conn in self.active_connections:
                    self.active_connections.remove(conn)


# 전역 WebSocket 매니저
ws_manager = WebSocketManager()
