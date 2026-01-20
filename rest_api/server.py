from __future__ import annotations

import asyncio
import json
import uuid
from typing import Optional, TypeVar, Generic, cast

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from rest_api.core.job_queue import Job, get_job_queue
from rest_api.core.jobs import (
    CalcJobHandler,
    EchoJobHandler,
    FibJobHandler,
    HashJobHandler,
    StatsJobHandler,
)
from rest_api.core.jobs.types import (
    BaseError,
    CalcError,
    CalcParams,
    CalcResult,
    EchoParams,
    EchoResult,
    FibError,
    FibParams,
    FibResult,
    HashParams,
    HashResult,
    StatsError,
    StatsParams,
    StatsResult,
)


P = TypeVar("P", bound=BaseModel)
R = TypeVar("R", bound=BaseModel)
E = TypeVar("E", bound=BaseModel)


class JobPayload(BaseModel, Generic[P, R, E]):
    """서버가 보관하는 Job 상태 레코드 (Pydantic 제네릭 모델).

    Attributes:
        id: 생성된 작업의 고유 ID
        type: 작업 종류 식별자
        params: 작업 파라미터 (Pydantic 모델)
        status: 현재 상태(pending, running, done 등)
        result: 작업 처리 결과(있을 경우에만, Pydantic 모델 또는 None)
    """

    id: str
    type: str
    params: P
    status: str
    result: Optional[R | E] = None


# Job 타입별 Payload 별칭
EchoJobPayload = JobPayload[EchoParams, EchoResult, BaseError]
CalcJobPayload = JobPayload[CalcParams, CalcResult | CalcError, BaseError]
HashJobPayload = JobPayload[HashParams, HashResult, BaseError]
StatsJobPayload = JobPayload[StatsParams, StatsResult | StatsError, BaseError]
FibJobPayload = JobPayload[FibParams, FibResult | FibError, BaseError]

# 모든 JobPayload의 Union
AnyJobPayload = (
    EchoJobPayload | CalcJobPayload | HashJobPayload | StatsJobPayload | FibJobPayload
)


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


class RestApiServer:
    """FastAPI 기반 비동기 REST API 서버"""

    def __init__(self, store: Optional[dict[str, AnyJobPayload]] = None) -> None:
        """FastAPI 앱을 초기화하고 라우트를 등록합니다.

        Args:
            store: 작업 상태를 저장할 공유 스토어
        """
        self.store: dict[str, AnyJobPayload] = store if store is not None else {}
        self.app = FastAPI(title="REST API Server", version="1.0.0")
        self._register_routes()

    @staticmethod
    def _pydantic_to_dict(obj: BaseModel | dict[str, object]) -> dict[str, object]:
        """Pydantic 모델을 dict로 변환합니다.

        Args:
            obj: Pydantic 모델 또는 일반 dict

        Returns:
            dict[str, object]: 변환된 dict
        """
        if isinstance(obj, BaseModel):
            return cast(dict[str, object], obj.model_dump())
        return obj

    @staticmethod
    def _json_response(
        result: BaseModel | dict[str, object],
        status_code: int = 200,
        key: str = "result",
    ) -> JSONResponse:
        """작업 결과를 JSONResponse로 반환합니다.

        Args:
            result: Pydantic 모델 또는 dict 형태의 결과
            status_code: HTTP 상태 코드
            key: 응답 JSON의 키 이름 (기본값: "result")

        Returns:
            JSONResponse: FastAPI JSONResponse 객체
        """
        result_dict = RestApiServer._pydantic_to_dict(result)
        return JSONResponse({key: result_dict}, status_code=status_code)

    async def _on_job_complete(self, job_id: str) -> None:
        """Job 완료 시 WebSocket으로 브로드캐스트합니다.

        Args:
            job_id: 완료된 작업의 ID
        """
        job = self.store.get(job_id)
        if job is not None:
            await ws_manager.broadcast(
                {
                    "type": "update",
                    "job": self._pydantic_to_dict(job),
                }
            )

    def _register_routes(self) -> None:
        """FastAPI 앱에 라우트를 등록합니다."""
        app = self.app
        jobs: dict[str, AnyJobPayload] = self.store

        # ========================================
        # 동기 엔드포인트: 즉시 결과 반환
        # ========================================

        @app.post("/echo")
        async def echo(  # pyright: ignore[reportUnusedFunction]
            params: EchoParams,
        ) -> JSONResponse:
            """POST /echo: 입력을 그대로 반환합니다. (비동기)

            Args:
                params: Echo 작업 파라미터

            Returns:
                JSONResponse: 결과 또는 에러
            """
            handler = EchoJobHandler()
            result = await handler.execute(params)
            return self._json_response(result, status_code=200)

        @app.post("/calc")
        async def calc(  # pyright: ignore[reportUnusedFunction]
            params: CalcParams,
        ) -> JSONResponse:
            """POST /calc: 사칙연산을 수행하고 즉시 결과를 반환합니다. (비동기)

            Args:
                params: 계산 작업 파라미터

            Returns:
                JSONResponse: 결과 또는 에러
            """
            handler = CalcJobHandler()
            result = await handler.execute(params)
            return self._json_response(result, status_code=200)

        @app.post("/stats")
        async def stats(  # pyright: ignore[reportUnusedFunction]
            params: StatsParams,
        ) -> JSONResponse:
            """POST /stats: 리스트 통계를 계산하고 즉시 결과를 반환합니다. (비동기)

            Args:
                params: 통계 작업 파라미터

            Returns:
                JSONResponse: 결과 또는 에러
            """
            handler = StatsJobHandler()
            result = await handler.execute(params)
            return self._json_response(result, status_code=200)

        # ========================================
        # 비동기 엔드포인트: job_id 반환 후 조회
        # ========================================

        @app.post("/hash_jobs")
        async def create_hash_job(  # pyright: ignore[reportUnusedFunction]
            params: HashParams,
        ) -> JSONResponse:
            """POST /hash_jobs: 해시 작업을 통합 작업 큐에 등록합니다. (비동기)

            즉시 job_id를 반환하고, 워커 풀에서 작업을 처리합니다.
            GET /jobs/{job_id}로 완료 상태를 확인할 수 있습니다.

            Args:
                params: 해시 작업 파라미터

            Returns:
                JSONResponse: job_id와 상태
            """

            job_id = str(uuid.uuid4())

            # 1. 즉시 pending 상태로 저장
            hash_payload: HashJobPayload = JobPayload(
                id=job_id,
                type="hash",
                params=params,  # Pydantic 모델 그대로 저장
                status="pending",
                result=None,
            )
            jobs[job_id] = hash_payload

            # WebSocket으로 새 Job 알림
            await ws_manager.broadcast(
                {
                    "type": "created",
                    "job": self._pydantic_to_dict(hash_payload),
                }
            )

            # 2. 통합 작업 큐에 제출
            job_queue = await get_job_queue()
            job = Job(
                job_id=job_id,
                job_type="hash",
                handler=HashJobHandler,  # 클래스 자체를 전달
                store=jobs,  # params는 jobs[job_id].params에서 가져옴
                on_complete=self._on_job_complete,  # 완료 콜백
            )

            if not await job_queue.submit(job):
                # 큐가 가득 찬 경우
                jobs[job_id].status = "failed"
                jobs[job_id].result = BaseError(error="Job queue is full")
                await ws_manager.broadcast(
                    {
                        "type": "update",
                        "job": self._pydantic_to_dict(jobs[job_id]),
                    }
                )
                raise HTTPException(
                    status_code=503, detail="Job queue is full, try again later"
                )

            # 3. 즉시 job_id 반환 (202 Accepted)
            return JSONResponse(
                {"job_id": job_id, "status": "pending"}, status_code=202
            )

        @app.post("/fib_jobs")
        async def create_fib_job(  # pyright: ignore[reportUnusedFunction]
            params: FibParams,
        ) -> JSONResponse:
            """POST /fib_jobs: 피보나치 작업을 통합 작업 큐에 등록합니다. (비동기)

            즉시 job_id를 반환하고, 워커 풀에서 작업을 처리합니다.
            GET /jobs/{job_id}로 완료 상태를 확인할 수 있습니다.

            Args:
                params: 피보나치 작업 파라미터

            Returns:
                JSONResponse: job_id와 상태
            """

            job_id = str(uuid.uuid4())

            # 1. 즉시 pending 상태로 저장
            fib_payload: FibJobPayload = JobPayload(
                id=job_id,
                type="fib",
                params=params,  # Pydantic 모델 그대로 저장
                status="pending",
                result=None,
            )
            jobs[job_id] = fib_payload

            # WebSocket으로 새 Job 알림
            await ws_manager.broadcast(
                {
                    "type": "created",
                    "job": self._pydantic_to_dict(fib_payload),
                }
            )

            # 2. 통합 작업 큐에 제출
            job_queue = await get_job_queue()
            job = Job(
                job_id=job_id,
                job_type="fib",
                handler=FibJobHandler,  # 클래스 자체를 전달
                store=jobs,  # params는 jobs[job_id].params에서 가져옴
                on_complete=self._on_job_complete,  # 완료 콜백
            )

            if not await job_queue.submit(job):
                # 큐가 가득 찬 경우
                jobs[job_id].status = "failed"
                jobs[job_id].result = BaseError(error="Job queue is full")
                await ws_manager.broadcast(
                    {
                        "type": "update",
                        "job": self._pydantic_to_dict(jobs[job_id]),
                    }
                )
                raise HTTPException(
                    status_code=503, detail="Job queue is full, try again later"
                )

            # 3. 즉시 job_id 반환 (202 Accepted)
            return JSONResponse(
                {"job_id": job_id, "status": "pending"}, status_code=202
            )

        @app.get("/jobs")
        async def list_jobs(  # pyright: ignore[reportUnusedFunction]
            limit: int = 50,
        ) -> JSONResponse:
            """GET /jobs: 전체 Job 목록을 반환합니다 (최근 N개).

            Args:
                limit: 반환할 최대 Job 수 (기본값: 50)

            Returns:
                JSONResponse: Job 목록
            """
            # 최근 N개만 반환 (dict는 삽입 순서 유지)
            all_jobs = list(jobs.values())
            recent_jobs = all_jobs[-limit:] if len(all_jobs) > limit else all_jobs
            # 최신순으로 정렬 (역순)
            recent_jobs = list(reversed(recent_jobs))
            return JSONResponse(
                {
                    "jobs": [self._pydantic_to_dict(j) for j in recent_jobs],
                    "total": len(jobs),
                },
                status_code=200,
            )

        @app.get("/jobs/{job_id}")
        async def get_job(  # pyright: ignore[reportUnusedFunction]
            job_id: str,
        ) -> JSONResponse:
            """GET /jobs/<job_id>: 비동기 작업의 상태를 조회합니다.

            Args:
                job_id: 조회할 작업의 식별자

            Returns:
                JSONResponse: 작업 정보
            """
            job = jobs.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Job not found")
            # Pydantic 모델을 dict로 변환하여 반환
            return JSONResponse(self._pydantic_to_dict(job), status_code=200)

        @app.get("/queue/status")
        async def queue_status() -> (  # pyright: ignore[reportUnusedFunction]
            JSONResponse
        ):
            """GET /queue/status: 작업 큐의 현재 상태를 조회합니다.

            Returns:
                JSONResponse: 큐 크기, 워커 정보 등
            """
            job_queue = await get_job_queue()
            return JSONResponse(
                {
                    "queue_size": job_queue.get_queue_size(),
                    "is_full": job_queue.is_full(),
                    "max_workers": 4,  # 하드코딩된 값, 추후 개선 가능
                },
                status_code=200,
            )

        # ========================================
        # WebSocket 엔드포인트: 실시간 Job 상태 스트리밍
        # ========================================

        @app.websocket("/ws/jobs")
        async def websocket_jobs(  # pyright: ignore[reportUnusedFunction]
            websocket: WebSocket,
        ) -> None:
            """WebSocket /ws/jobs: 실시간 Job 상태를 스트리밍합니다.

            연결 시 현재 Job 목록을 전송하고, 이후 상태 변경을 실시간으로 전달합니다.
            """
            await ws_manager.connect(websocket)
            try:
                # 초기 연결 시 현재 Job 목록 전송
                all_jobs = list(jobs.values())
                recent_jobs = all_jobs[-50:] if len(all_jobs) > 50 else all_jobs
                recent_jobs = list(reversed(recent_jobs))
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "init",
                            "jobs": [self._pydantic_to_dict(j) for j in recent_jobs],
                            "total": len(jobs),
                        },
                        default=str,
                    )
                )

                # 연결 유지 (클라이언트가 끊을 때까지)
                while True:
                    # 클라이언트로부터의 메시지 대기 (ping/pong 또는 연결 확인)
                    try:
                        await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    except asyncio.TimeoutError:
                        # 타임아웃 시 ping 전송
                        await websocket.send_text(json.dumps({"type": "ping"}))
            except WebSocketDisconnect:
                pass
            finally:
                await ws_manager.disconnect(websocket)

    def run(self, host: str = "0.0.0.0", port: int = 8080) -> None:
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
    return RestApiServer(store=store).app


if __name__ == "__main__":
    server = RestApiServer()
    server.run(host="0.0.0.0", port=8080)
