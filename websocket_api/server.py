"""WebSocket API 서버 구현."""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false

from __future__ import annotations

import json
import logging
import uuid
from typing import Optional, Union, cast

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from communication.job_queue import Job, get_job_queue
from communication.jobs import (
    CalcJobHandler,
    EchoJobHandler,
    FibJobHandler,
    HashJobHandler,
    StatsJobHandler,
)
from websocket_api.job_types import (
    AnyJobPayload,
    HashJobPayload,
    FibJobPayload,
    JobPayload,
)
from communication.jobs.types import BaseError

logger = logging.getLogger(__name__)


class WebSocketServer:
    """FastAPI 기반 WebSocket API 서버."""

    def __init__(self, store: Optional[dict[str, AnyJobPayload]] = None) -> None:
        """WebSocket 서버를 초기화합니다.

        Args:
            store: 작업 상태를 저장할 공유 스토어
        """
        self.store: dict[str, AnyJobPayload] = store if store is not None else {}
        self.app = FastAPI(title="WebSocket API Server", version="1.0.0")
        self._register_routes()

    @staticmethod
    def _pydantic_to_dict(
        obj: Union[BaseModel, dict[str, object]],
    ) -> dict[str, object]:
        """Pydantic 모델을 dict로 변환합니다."""
        if isinstance(obj, BaseModel):
            return cast(dict[str, object], obj.model_dump())
        return obj

    async def _on_job_complete(self, job_id: str) -> None:
        """Job 완료 시 WebSocket 연결들에게 브로드캐스트합니다."""
        job = self.store.get(job_id)
        if job is not None:
            # WebSocket 연결들에게 브로드캐스트는 각 연결의 핸들러에서 처리
            pass

    def _register_routes(self) -> None:
        """WebSocket 라우트를 등록합니다."""
        app = self.app

        @app.websocket("/ws")
        async def websocket_endpoint(  # pyright: ignore[reportUnusedFunction]
            websocket: WebSocket,
        ) -> None:
            """WebSocket 연결을 처리합니다.

            메시지 형식:
            - 클라이언트 -> 서버: {"type": "create_job", "job_type": "echo", "params": {...}}
            - 서버 -> 클라이언트: {"type": "job_created", "job": {...}}
            - 서버 -> 클라이언트: {"type": "job_update", "job": {...}}
            - 서버 -> 클라이언트: {"type": "job_result", "job": {...}}
            """
            await websocket.accept()
            logger.info("WebSocket client connected")

            # 초기 연결 시 현재 Job 목록 전송
            all_jobs = list(self.store.values())
            recent_jobs = all_jobs[-50:] if len(all_jobs) > 50 else all_jobs
            recent_jobs = list(reversed(recent_jobs))
            await websocket.send_json(
                {
                    "type": "init",
                    "jobs": [self._pydantic_to_dict(j) for j in recent_jobs],
                    "total": len(self.store),
                }
            )

            try:
                while True:
                    # 클라이언트로부터 메시지 수신
                    data = await websocket.receive_text()
                    try:
                        message = json.loads(data)
                        await self._handle_message(websocket, message)
                    except json.JSONDecodeError:
                        await websocket.send_json(
                            {"type": "error", "message": "Invalid JSON"}
                        )
                    except ValidationError as e:
                        await websocket.send_json(
                            {"type": "error", "message": f"Validation error: {e}"}
                        )
                    except Exception as e:
                        logger.error(f"Error handling message: {e}")
                        await websocket.send_json({"type": "error", "message": str(e)})
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")

    async def _handle_message(
        self, websocket: WebSocket, message: dict[str, object]
    ) -> None:
        """클라이언트 메시지를 처리합니다."""
        msg_type = message.get("type")
        if msg_type == "create_job":
            await self._handle_create_job(websocket, message)
        elif msg_type == "get_job":
            await self._handle_get_job(websocket, message)
        elif msg_type == "list_jobs":
            await self._handle_list_jobs(websocket, message)
        elif msg_type == "get_queue_status":
            await self._handle_get_queue_status(websocket)
        else:
            await websocket.send_json(
                {"type": "error", "message": f"Unknown message type: {msg_type}"}
            )

    async def _handle_create_job(
        self, websocket: WebSocket, message: dict[str, object]
    ) -> None:
        """작업 생성 요청을 처리합니다."""
        job_type = str(message.get("job_type", ""))
        params_raw = message.get("params", {})

        if not isinstance(params_raw, dict):
            await websocket.send_json(
                {"type": "error", "message": "params must be a dict"}
            )
            return

        # 동기 작업 처리
        if job_type == "echo":
            echo_handler = EchoJobHandler()
            try:
                from communication.jobs.types import EchoParams

                echo_params = EchoParams(**params_raw)
                echo_result = await echo_handler.execute(echo_params)
                await websocket.send_json(
                    {
                        "type": "job_result",
                        "job": {
                            "id": "",
                            "type": job_type,
                            "params": {"result": self._pydantic_to_dict(echo_result)},
                            "status": "done",
                        },
                    }
                )
            except Exception as e:
                await websocket.send_json({"type": "error", "message": str(e)})
            return

        elif job_type == "calc":
            calc_handler = CalcJobHandler()
            try:
                from communication.jobs.types import CalcParams

                calc_params = CalcParams(**params_raw)
                calc_result = await calc_handler.execute(calc_params)
                await websocket.send_json(
                    {
                        "type": "job_result",
                        "job": {
                            "id": "",
                            "type": job_type,
                            "params": {"result": self._pydantic_to_dict(calc_result)},
                            "status": "done",
                        },
                    }
                )
            except Exception as e:
                await websocket.send_json({"type": "error", "message": str(e)})
            return

        elif job_type == "stats":
            stats_handler = StatsJobHandler()
            try:
                from communication.jobs.types import StatsParams

                stats_params = StatsParams(**params_raw)
                stats_result = await stats_handler.execute(stats_params)
                await websocket.send_json(
                    {
                        "type": "job_result",
                        "job": {
                            "id": "",
                            "type": job_type,
                            "params": {"result": self._pydantic_to_dict(stats_result)},
                            "status": "done",
                        },
                    }
                )
            except Exception as e:
                await websocket.send_json({"type": "error", "message": str(e)})
            return

        # 비동기 작업 처리
        elif job_type == "hash":
            hash_job_id = str(uuid.uuid4())
            try:
                from communication.jobs.types import HashParams

                hash_params = HashParams(**params_raw)
                hash_job_payload: HashJobPayload = JobPayload(
                    id=hash_job_id,
                    type="hash",
                    params=hash_params,
                    status="pending",
                    result=None,
                )
                self.store[hash_job_id] = hash_job_payload

                await websocket.send_json(
                    {
                        "type": "job_created",
                        "job": self._pydantic_to_dict(hash_job_payload),
                    }
                )

                job_queue = await get_job_queue()

                async def on_complete(jid: str) -> None:
                    await self._broadcast_job_update(websocket, jid)

                hash_job = Job(
                    job_id=hash_job_id,
                    job_type="hash",
                    handler=HashJobHandler,
                    store=self.store,
                    on_complete=on_complete,
                )

                if not await job_queue.submit(hash_job):
                    hash_job_payload.status = "failed"
                    hash_job_payload.result = BaseError(error="Job queue is full")
                    await websocket.send_json(
                        {
                            "type": "job_update",
                            "job": self._pydantic_to_dict(hash_job_payload),
                        }
                    )
            except Exception as e:
                await websocket.send_json({"type": "error", "message": str(e)})

        elif job_type == "fib":
            fib_job_id = str(uuid.uuid4())
            try:
                from communication.jobs.types import FibParams

                fib_params = FibParams(**params_raw)
                fib_job_payload: FibJobPayload = JobPayload(
                    id=fib_job_id,
                    type="fib",
                    params=fib_params,
                    status="pending",
                    result=None,
                )
                self.store[fib_job_id] = fib_job_payload

                await websocket.send_json(
                    {
                        "type": "job_created",
                        "job": self._pydantic_to_dict(fib_job_payload),
                    }
                )

                job_queue = await get_job_queue()

                async def on_complete(jid: str) -> None:
                    await self._broadcast_job_update(websocket, jid)

                fib_job = Job(
                    job_id=fib_job_id,
                    job_type="fib",
                    handler=FibJobHandler,
                    store=self.store,
                    on_complete=on_complete,
                )

                if not await job_queue.submit(fib_job):
                    fib_job_payload.status = "failed"
                    fib_job_payload.result = BaseError(error="Job queue is full")
                    await websocket.send_json(
                        {
                            "type": "job_update",
                            "job": self._pydantic_to_dict(fib_job_payload),
                        }
                    )
            except Exception as e:
                await websocket.send_json({"type": "error", "message": str(e)})

        else:
            await websocket.send_json(
                {"type": "error", "message": f"Unknown job type: {job_type}"}
            )

    async def _handle_get_job(
        self, websocket: WebSocket, message: dict[str, object]
    ) -> None:
        """작업 조회 요청을 처리합니다."""
        job_id = str(message.get("job_id", ""))
        job = self.store.get(job_id)
        if job is None:
            await websocket.send_json(
                {"type": "error", "message": f"Job {job_id} not found"}
            )
        else:
            await websocket.send_json(
                {"type": "job", "job": self._pydantic_to_dict(job)}
            )

    async def _handle_list_jobs(
        self, websocket: WebSocket, message: dict[str, object]
    ) -> None:
        """작업 목록 조회 요청을 처리합니다."""
        limit_raw = message.get("limit", 50)
        try:
            if isinstance(limit_raw, (int, float)):
                limit = int(limit_raw)
            elif isinstance(limit_raw, str):
                limit = int(limit_raw)
            else:
                limit = 50
            # limit이 양수인지 확인
            if limit <= 0:
                limit = 50
        except (ValueError, TypeError):
            limit = 50

        all_jobs = list(self.store.values())
        recent_jobs = all_jobs[-limit:] if len(all_jobs) > limit else all_jobs
        recent_jobs = list(reversed(recent_jobs))
        await websocket.send_json(
            {
                "type": "jobs",
                "jobs": [self._pydantic_to_dict(j) for j in recent_jobs],
                "total": len(self.store),
            }
        )

    async def _handle_get_queue_status(self, websocket: WebSocket) -> None:
        """큐 상태 조회 요청을 처리합니다."""
        job_queue = await get_job_queue()
        await websocket.send_json(
            {
                "type": "queue_status",
                "queue_size": job_queue.get_queue_size(),
                "is_full": job_queue.is_full(),
                "max_workers": 4,  # 하드코딩된 값, 추후 개선 가능
            }
        )

    async def _broadcast_job_update(self, websocket: WebSocket, job_id: str) -> None:
        """작업 업데이트를 WebSocket으로 전송합니다."""
        job = self.store.get(job_id)
        if job is not None:
            await websocket.send_json(
                {
                    "type": "job_update",
                    "job": self._pydantic_to_dict(job),
                }
            )

    def run(self, host: str = "0.0.0.0", port: int = 8082) -> None:
        """Uvicorn 서버를 실행합니다.

        Args:
            host: 바인딩할 호스트 인터페이스
            port: 수신할 포트 번호
        """
        import uvicorn

        uvicorn.run(self.app, host=host, port=port)


def create_app(store: Optional[dict[str, AnyJobPayload]] = None) -> FastAPI:
    """테스트 호환을 위한 FastAPI 앱을 생성합니다.

    Args:
        store: 선택적 공유 스토어입니다.

    Returns:
        FastAPI: 설정된 FastAPI 애플리케이션입니다.
    """
    return WebSocketServer(store=store).app


if __name__ == "__main__":
    server = WebSocketServer()
    server.run(host="0.0.0.0", port=8082)
