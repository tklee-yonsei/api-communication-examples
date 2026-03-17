"""Message Queue API 클라이언트 구현 (Redis Pub/Sub)."""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional, cast

import httpx
import redis.asyncio as aioredis
from redis.asyncio.client import PubSub as AioPubSub

from communication.base import JobClient, JobNotFoundError, JobRecord
from communication.types import JobParams, JobStatus

logger = logging.getLogger(__name__)


class MQJobClient(JobClient):
    """Message Queue 서비스를 사용하는 JobClient 구현.

    Redis Pub/Sub을 사용하여 작업을 생성하고 결과를 수신합니다.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8083",
        redis_url: str = "redis://localhost:6379/0",
    ) -> None:
        """클라이언트를 초기화합니다.

        Args:
            base_url: MQ API 서버 URL
            redis_url: Redis 연결 URL
        """
        self.base_url = base_url.rstrip("/")
        self.redis_url = redis_url
        self.redis_client: Optional[aioredis.Redis] = None
        self.pubsub: Optional[AioPubSub] = None
        self._subscriber_task: Optional[asyncio.Task[None]] = None
        self._result_store: dict[str, dict[str, object]] = {}

    async def _connect_redis(self) -> None:
        """Redis에 연결합니다."""
        if self.redis_client is None:
            self.redis_client = aioredis.from_url(self.redis_url, decode_responses=True)
            self.pubsub = self.redis_client.pubsub()
            await self.pubsub.subscribe("job_results")
            logger.info("Connected to Redis for job results")

    async def _start_subscriber(self) -> None:
        """Redis에서 작업 결과를 수신하는 구독자 시작."""
        await self._connect_redis()
        pubsub = self.pubsub
        if pubsub is None:
            return

        async def subscriber_loop() -> None:
            while True:
                try:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=1.0
                    )
                    if message is None:
                        continue

                    if message["type"] == "message":
                        try:
                            data = json.loads(str(message["data"]))
                            job_id = data.get("job_id")
                            if job_id:
                                self._result_store[job_id] = data
                                logger.debug(f"Received result for job {job_id}")
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Subscriber error: {e}")
                    await asyncio.sleep(1)

        self._subscriber_task = asyncio.create_task(subscriber_loop())

    async def _wait_for_result(
        self, job_id: str, timeout: float = 30.0
    ) -> Optional[dict[str, object]]:
        """작업 결과를 기다립니다."""
        if self._subscriber_task is None:
            await self._start_subscriber()

        start_time = asyncio.get_event_loop().time()
        while True:
            if job_id in self._result_store:
                return self._result_store.pop(job_id)

            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                return None

            await asyncio.sleep(0.1)

    def create_job(self, job_type: str, params: JobParams) -> JobRecord:
        """작업을 생성하고 레코드를 반환합니다.

        동기 작업(echo, calc, stats): 즉시 결과 반환
        비동기 작업(hash, fib): job_id 반환

        Args:
            job_type: 작업 종류 식별자
            params: 작업 수행에 필요한 파라미터

        Returns:
            JobRecord: 생성된 작업에 대한 기록
        """
        return asyncio.run(self._create_job_async(job_type, params))

    async def _create_job_async(self, job_type: str, params: JobParams) -> JobRecord:
        """비동기로 작업을 생성합니다."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/jobs",
                    json={"job_type": job_type, "params": params},
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                if data.get("status") == "done":
                    # 동기 작업: 결과가 바로 반환됨
                    return JobRecord(
                        id=data.get("id", ""),
                        type=data.get("type", job_type),
                        params=params,
                        status="done",
                    )
                else:
                    # 비동기 작업: job_id 반환
                    job_id = data.get("id", "")
                    if not job_id:
                        raise RuntimeError("No job_id returned from server")

                    # 결과를 기다림
                    result = await self._wait_for_result(job_id, timeout=30.0)
                    if result:
                        status = result.get("status", "pending")
                        return JobRecord(
                            id=job_id,
                            type=job_type,
                            params=params,
                            status=cast(JobStatus, status),
                        )
                    else:
                        # 타임아웃 - pending 상태로 반환
                        return JobRecord(
                            id=job_id,
                            type=job_type,
                            params=params,
                            status="pending",
                        )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise JobNotFoundError(f"Job not found: {e}")
                raise RuntimeError(f"HTTP error: {e}") from e
            except Exception as e:
                raise RuntimeError(f"Failed to create job: {e}") from e

    def get_job(self, job_id: str) -> JobRecord:
        """작업 상태를 조회합니다.

        Args:
            job_id: 조회 대상 작업의 식별자

        Returns:
            JobRecord: 요청한 작업의 현재 기록

        Raises:
            JobNotFoundError: 작업이 존재하지 않으면 발생
        """
        return asyncio.run(self._get_job_async(job_id))

    async def _get_job_async(self, job_id: str) -> JobRecord:
        """비동기로 작업 상태를 조회합니다."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/jobs/{job_id}",
                    timeout=10.0,
                )
                if response.status_code == 404:
                    raise JobNotFoundError(f"Job {job_id} not found")
                response.raise_for_status()
                data = response.json()

                return JobRecord(
                    id=data.get("id", job_id),
                    type=data.get("type", ""),
                    params=cast(JobParams, data.get("params", {})),
                    status=cast(JobStatus, data.get("status", "pending")),
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise JobNotFoundError(f"Job {job_id} not found") from e
                raise RuntimeError(f"HTTP error: {e}") from e
            except Exception as e:
                raise RuntimeError(f"Failed to get job: {e}") from e

    def close(self) -> None:
        """연결을 종료합니다."""
        if self._subscriber_task:
            self._subscriber_task.cancel()
        if self.pubsub:
            asyncio.run(self.pubsub.close())
        if self.redis_client:
            asyncio.run(self.redis_client.close())
