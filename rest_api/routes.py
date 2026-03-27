"""REST API 라우트 핸들러."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Protocol, Union

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from communication.job_queue import Job, get_job_queue
from communication.jobs import (
    CalcJobHandler,
    EchoJobHandler,
    FibJobHandler,
    HashJobHandler,
    StatsJobHandler,
)
from communication.jobs.types import BaseError
from rest_api.types import (
    AnyJobPayload,
    EchoParams,
    CalcParams,
    FibParams,
    HashParams,
    HashJobPayload,
    FibJobPayload,
    JobPayload,
    StatsParams,
)
from rest_api.websocket import ws_manager


class JsonResponseFunc(Protocol):
    """JSONResponse 생성 함수 프로토콜."""

    def __call__(
        self,
        result: Union[BaseModel, dict[str, object]],
        status_code: int = 200,
        key: str = "result",
    ) -> JSONResponse: ...


def register_routes(
    app: FastAPI,
    jobs: dict[str, AnyJobPayload],
    pydantic_to_dict: Callable[
        [Union[BaseModel, dict[str, object]]], dict[str, object]
    ],
    json_response: JsonResponseFunc,
    on_job_complete: Callable[[str], Awaitable[None]],
) -> None:
    """FastAPI 앱에 라우트를 등록합니다.

    Args:
        app: FastAPI 애플리케이션
        jobs: 작업 저장소
        pydantic_to_dict: Pydantic 모델을 dict로 변환하는 함수
        json_response: JSONResponse를 생성하는 함수
        on_job_complete: 작업 완료 콜백
    """

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
        return json_response(result, status_code=200)

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
        return json_response(result, status_code=200)

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
        return json_response(result, status_code=200)

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
                "job": pydantic_to_dict(hash_payload),
            }
        )

        # 2. 통합 작업 큐에 제출
        job_queue = await get_job_queue()
        job = Job(
            job_id=job_id,
            job_type="hash",
            handler=HashJobHandler,  # 클래스 자체를 전달
            store=jobs,  # params는 jobs[job_id].params에서 가져옴
            on_complete=on_job_complete,  # 완료 콜백
        )

        if not await job_queue.submit(job):
            # 큐가 가득 찬 경우
            jobs[job_id].status = "failed"
            jobs[job_id].result = BaseError(error="Job queue is full")
            await ws_manager.broadcast(
                {
                    "type": "update",
                    "job": pydantic_to_dict(jobs[job_id]),
                }
            )
            raise HTTPException(
                status_code=503, detail="Job queue is full, try again later"
            )

        # 3. 즉시 job_id 반환 (202 Accepted)
        return JSONResponse({"job_id": job_id, "status": "pending"}, status_code=202)

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
                "job": pydantic_to_dict(fib_payload),
            }
        )

        # 2. 통합 작업 큐에 제출
        job_queue = await get_job_queue()
        job = Job(
            job_id=job_id,
            job_type="fib",
            handler=FibJobHandler,  # 클래스 자체를 전달
            store=jobs,  # params는 jobs[job_id].params에서 가져옴
            on_complete=on_job_complete,  # 완료 콜백
        )

        if not await job_queue.submit(job):
            # 큐가 가득 찬 경우
            jobs[job_id].status = "failed"
            jobs[job_id].result = BaseError(error="Job queue is full")
            await ws_manager.broadcast(
                {
                    "type": "update",
                    "job": pydantic_to_dict(jobs[job_id]),
                }
            )
            raise HTTPException(
                status_code=503, detail="Job queue is full, try again later"
            )

        # 3. 즉시 job_id 반환 (202 Accepted)
        return JSONResponse({"job_id": job_id, "status": "pending"}, status_code=202)

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
                "jobs": [pydantic_to_dict(j) for j in recent_jobs],
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
        return JSONResponse(pydantic_to_dict(job), status_code=200)

    @app.get("/queue/status")
    async def queue_status() -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
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
                        "jobs": [pydantic_to_dict(j) for j in recent_jobs],
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
