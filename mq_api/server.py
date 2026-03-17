"""Message Queue API 서버 구현 (Redis Pub/Sub)."""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Optional, Union, cast

import redis.asyncio as aioredis
from redis.asyncio.client import PubSub as AioPubSub
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from fastapi import FastAPI, HTTPException
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
from mq_api.job_types import (
    AnyJobPayload,
    HashJobPayload,
    FibJobPayload,
    JobPayload,
)
from communication.jobs.types import BaseError

logger = logging.getLogger(__name__)


class CreateJobRequest(BaseModel):
    """작업 생성 요청."""

    job_type: str
    params: dict[str, object]


class MQServer:
    """FastAPI 기반 Message Queue API 서버 (Redis Pub/Sub)."""

    def __init__(
        self,
        store: Optional[dict[str, AnyJobPayload]] = None,
        redis_url: str = "redis://localhost:6379/0",
    ) -> None:
        """MQ 서버를 초기화합니다.

        Args:
            store: 작업 상태를 저장할 공유 스토어
            redis_url: Redis 연결 URL
        """
        self.store: dict[str, AnyJobPayload] = store if store is not None else {}
        self.redis_url = redis_url
        self.redis_client: Optional[aioredis.Redis] = None
        self.pubsub: Optional[AioPubSub] = None
        self._subscriber_task: Optional[asyncio.Task[None]] = None
        self._worker_task: Optional[asyncio.Task[None]] = None
        self._subscriber_lock = asyncio.Lock()
        self._redis_lock = asyncio.Lock()

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncIterator[None]:
            await self._start_worker()
            yield
            if self._worker_task:
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    pass
            await self._disconnect_redis()

        self.app = FastAPI(title="MQ API Server", version="1.0.0", lifespan=lifespan)
        self._register_routes()

    @staticmethod
    def _pydantic_to_dict(
        obj: Union[BaseModel, dict[str, object]],
    ) -> dict[str, object]:
        """Pydantic 모델을 dict로 변환합니다."""
        if isinstance(obj, BaseModel):
            return cast(dict[str, object], obj.model_dump())
        return obj

    async def _connect_redis(self) -> None:
        """Redis에 연결합니다."""
        async with self._redis_lock:
            if self.redis_client is None:
                self.redis_client = aioredis.from_url(
                    self.redis_url, decode_responses=True
                )
                logger.info("Connected to Redis")

    async def _disconnect_redis(self) -> None:
        """Redis 연결을 종료합니다."""
        if self.pubsub:
            await self.pubsub.unsubscribe("job_requests")
            await self.pubsub.unsubscribe("job_results")
            await self.pubsub.close()
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Disconnected from Redis")

    async def _start_worker(self) -> None:
        """Redis에서 작업 요청을 구독하고 처리하는 Worker 시작."""
        async with self._subscriber_lock:
            # 이미 Worker가 실행 중이면 다시 시작하지 않음
            if self._worker_task is not None and not self._worker_task.done():
                return

            await self._connect_redis()
            if self.redis_client is None:
                return

            # job_requests 채널을 구독
            worker_pubsub = self.redis_client.pubsub()
            await worker_pubsub.subscribe("job_requests")
            logger.info("MQ Worker started, subscribing to job_requests")

            async def worker_loop() -> None:
                while True:
                    try:
                        message = cast(
                            dict[str, object] | None,
                            await worker_pubsub.get_message(
                                ignore_subscribe_messages=True, timeout=1.0
                            ),
                        )
                        if message is None:
                            continue

                        if message["type"] == "message":
                            try:
                                request_data = json.loads(str(message["data"]))
                                job_type = request_data.get("job_type")
                                params_raw = request_data.get("params", {})
                                job_id = request_data.get("job_id", str(uuid.uuid4()))

                                # 작업 처리
                                await self._process_job_request(
                                    job_id, job_type, params_raw
                                )
                            except Exception as e:
                                logger.error(f"Error processing job request: {e}")
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        logger.error(f"Worker error: {e}")
                        await asyncio.sleep(1)

            self._worker_task = asyncio.create_task(worker_loop())

    async def _process_job_request(
        self, job_id: str, job_type: str, params_raw: dict[str, Any]
    ) -> None:
        """작업 요청을 처리합니다."""
        try:
            # 동기 작업 처리
            if job_type == "echo":
                from communication.jobs.types import EchoParams

                echo_params = EchoParams.model_validate(params_raw)
                echo_handler = EchoJobHandler()
                echo_result = await echo_handler.execute(echo_params)

                # 결과를 Redis에 발행
                await self._publish_job_result(
                    job_id, "done", self._pydantic_to_dict(echo_result)
                )

            elif job_type == "calc":
                from communication.jobs.types import CalcParams

                calc_params = CalcParams.model_validate(params_raw)
                calc_handler = CalcJobHandler()
                calc_result = await calc_handler.execute(calc_params)

                await self._publish_job_result(
                    job_id, "done", self._pydantic_to_dict(calc_result)
                )

            elif job_type == "stats":
                from communication.jobs.types import StatsParams

                stats_params = StatsParams.model_validate(params_raw)
                stats_handler = StatsJobHandler()
                stats_result = await stats_handler.execute(stats_params)

                await self._publish_job_result(
                    job_id, "done", self._pydantic_to_dict(stats_result)
                )

            # 비동기 작업 처리
            elif job_type == "hash":
                from communication.jobs.types import HashParams

                hash_params = HashParams.model_validate(params_raw)
                hash_job_payload: HashJobPayload = JobPayload(
                    id=job_id,
                    type="hash",
                    params=hash_params,
                    status="pending",
                    result=None,
                )
                self.store[job_id] = hash_job_payload

                job_queue = await get_job_queue()

                async def on_complete(jid: str) -> None:
                    job = self.store.get(jid)
                    if job:
                        result_dict = None
                        if job.result:
                            result_dict = self._pydantic_to_dict(job.result)
                        await self._publish_job_result(jid, job.status, result_dict)

                hash_job = Job(
                    job_id=job_id,
                    job_type="hash",
                    handler=HashJobHandler,
                    store=self.store,
                    on_complete=on_complete,
                )

                if not await job_queue.submit(hash_job):
                    hash_job_payload.status = "failed"
                    hash_job_payload.result = BaseError(error="Job queue is full")
                    await self._publish_job_result(
                        job_id, "failed", {"error": "Job queue is full"}
                    )

            elif job_type == "fib":
                from communication.jobs.types import FibParams

                fib_params = FibParams.model_validate(params_raw)
                fib_job_payload: FibJobPayload = JobPayload(
                    id=job_id,
                    type="fib",
                    params=fib_params,
                    status="pending",
                    result=None,
                )
                self.store[job_id] = fib_job_payload

                job_queue = await get_job_queue()

                async def on_complete(jid: str) -> None:
                    job = self.store.get(jid)
                    if job:
                        result_dict = None
                        if job.result:
                            result_dict = self._pydantic_to_dict(job.result)
                        await self._publish_job_result(jid, job.status, result_dict)

                fib_job = Job(
                    job_id=job_id,
                    job_type="fib",
                    handler=FibJobHandler,
                    store=self.store,
                    on_complete=on_complete,
                )

                if not await job_queue.submit(fib_job):
                    fib_job_payload.status = "failed"
                    fib_job_payload.result = BaseError(error="Job queue is full")
                    await self._publish_job_result(
                        job_id, "failed", {"error": "Job queue is full"}
                    )
            else:
                await self._publish_job_result(
                    job_id, "failed", {"error": f"Unknown job type: {job_type}"}
                )

        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}")
            await self._publish_job_result(job_id, "failed", {"error": str(e)})

    async def _publish_job_result(
        self, job_id: str, status: str, result: Optional[dict[str, object]] = None
    ) -> None:
        """작업 결과를 Redis에 발행합니다."""
        if self.redis_client is None:
            await self._connect_redis()

        if self.redis_client:
            message: dict[str, object] = {
                "job_id": job_id,
                "status": status,
            }
            if result:
                message["result"] = result
            # Redis publish는 thread-safe하므로 별도 lock 불필요
            await self.redis_client.publish("job_results", json.dumps(message))

    def _register_routes(self) -> None:
        """MQ 라우트를 등록합니다."""
        app = self.app

        @app.post("/jobs")
        async def create_job(  # pyright: ignore[reportUnusedFunction]
            request: CreateJobRequest,
        ) -> JSONResponse:
            """작업을 생성합니다. (하위 호환성을 위해 유지, 내부적으로는 Redis를 통해 처리)

            참고: 순수 MQ 패턴을 사용하려면 클라이언트가 Redis에 직접 메시지를 발행해야 합니다.
            """
            job_id = str(uuid.uuid4())
            job_type = request.job_type
            params_raw = request.params

            # Redis에 작업 요청 발행
            await self._connect_redis()
            if self.redis_client:
                message = {
                    "job_id": job_id,
                    "job_type": job_type,
                    "params": params_raw,
                }
                await self.redis_client.publish("job_requests", json.dumps(message))
                logger.info(f"Published job request {job_id} to Redis")

            # 비동기 작업의 경우 job_id 반환
            if job_type in ("hash", "fib"):
                return JSONResponse(
                    {
                        "id": job_id,
                        "type": job_type,
                        "params": params_raw,
                        "status": "pending",
                    },
                    status_code=202,
                )
            else:
                # 동기 작업의 경우 결과를 기다려야 함 (간단한 구현을 위해 즉시 처리)
                # 실제로는 Redis를 통해 처리되지만, HTTP 응답을 위해 직접 처리
                try:
                    if job_type == "echo":
                        from communication.jobs.types import EchoParams

                        echo_params = EchoParams.model_validate(params_raw)
                        echo_handler = EchoJobHandler()
                        echo_result = await echo_handler.execute(echo_params)
                        return JSONResponse(
                            {"result": self._pydantic_to_dict(echo_result)}
                        )
                    elif job_type == "calc":
                        from communication.jobs.types import CalcParams

                        calc_params = CalcParams.model_validate(params_raw)
                        calc_handler = CalcJobHandler()
                        calc_result = await calc_handler.execute(calc_params)
                        return JSONResponse(
                            {"result": self._pydantic_to_dict(calc_result)}
                        )
                    elif job_type == "stats":
                        from communication.jobs.types import StatsParams

                        stats_params = StatsParams.model_validate(params_raw)
                        stats_handler = StatsJobHandler()
                        stats_result = await stats_handler.execute(stats_params)
                        return JSONResponse(
                            {"result": self._pydantic_to_dict(stats_result)}
                        )
                    else:
                        raise HTTPException(
                            status_code=400, detail=f"Unknown job type: {job_type}"
                        )
                except Exception as e:
                    raise HTTPException(status_code=400, detail=str(e))

        @app.get("/jobs/{job_id}")
        async def get_job(  # pyright: ignore[reportUnusedFunction]
            job_id: str,
        ) -> JSONResponse:
            """작업 상태를 조회합니다."""
            job = self.store.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

            result_dict = None
            if job.result:
                result_dict = self._pydantic_to_dict(job.result)

            return JSONResponse(
                {
                    "id": job.id,
                    "type": job.type,
                    "params": self._pydantic_to_dict(job.params),
                    "status": job.status,
                    "result": result_dict,
                }
            )

        @app.get("/jobs")
        async def list_jobs(  # pyright: ignore[reportUnusedFunction]
            limit: int = 50,
        ) -> JSONResponse:
            """전체 작업 목록을 조회합니다."""
            all_jobs = list(self.store.values())
            recent_jobs = all_jobs[-limit:] if len(all_jobs) > limit else all_jobs
            recent_jobs = list(reversed(recent_jobs))

            jobs_data = []
            for job in recent_jobs:
                result_dict = None
                if job.result:
                    result_dict = self._pydantic_to_dict(job.result)

                jobs_data.append(
                    {
                        "id": job.id,
                        "type": job.type,
                        "params": self._pydantic_to_dict(job.params),
                        "status": job.status,
                        "result": result_dict,
                    }
                )

            return JSONResponse({"jobs": jobs_data, "total": len(self.store)})

    def run(self, host: str = "0.0.0.0", port: int = 8083) -> None:
        """서버를 실행합니다."""
        import uvicorn

        uvicorn.run(self.app, host=host, port=port)
