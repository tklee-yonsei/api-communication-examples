"""Message Queue API 클라이언트 함수."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional, Union, cast

import httpx
import redis.asyncio as redis

from communication_ui.rest.config import MAX_CONCURRENCY
from communication_ui.rest.types import BatchResult, JobResult


def run_mq_batch(
    mq_base_url: str,
    job_type: str,
    params: dict[str, object],
    count: int,
    concurrency: int,
    persistent: bool = False,
) -> BatchResult:
    """Message Queue 서버로 대량 요청을 전송합니다.

    Args:
        mq_base_url: MQ API 서버 URL
        job_type: 작업 타입
        params: 작업 파라미터
        count: 요청 개수
        concurrency: 동시 요청 수 (persistent=False일 때만 사용)
        persistent: True이면 단일 연결로 모든 요청 전송, False이면 각 요청마다 연결 생성

    Returns:
        BatchResult: 성공/실패 결과
    """
    if persistent:
        return asyncio.run(_run_mq_batch_persistent(mq_base_url, job_type, params, count))

    successes: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    max_workers = max(1, min(concurrency, count, MAX_CONCURRENCY))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(create_single_mq, mq_base_url, job_type, params)
            for _ in range(count)
        ]
        for future in as_completed(futures):
            result = future.result()
            if result.success:
                successes.append(result.data)
            else:
                failures.append(result.data)
    return BatchResult(successes=successes, failures=failures)


async def _run_mq_batch_persistent(
    mq_base_url: str,
    job_type: str,
    params: dict[str, object],
    count: int,
) -> BatchResult:
    """Redis에 직접 메시지를 발행하는 순수 MQ 패턴."""
    successes: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    redis_client: Optional[redis.Redis] = None
    pubsub: Optional[redis.client.PubSub] = None
    subscriber_task: Optional[asyncio.Task[None]] = None
    
    try:
        # Redis 연결 (Docker 환경에서는 redis 서비스 이름 사용)
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        redis_client = redis.from_url(redis_url, decode_responses=True)
        result_store: dict[str, dict[str, object]] = {}
        
        # 결과 구독자 시작
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("job_results")
        
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
                            data = json.loads(message["data"])
                            job_id = data.get("job_id")
                            if job_id:
                                result_store[job_id] = data
                        except Exception:
                            pass
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    await asyncio.sleep(0.1)
        
        subscriber_task = asyncio.create_task(subscriber_loop())
        
        # 여러 작업을 Redis에 발행
        import uuid
        job_ids: list[str] = []
        for _ in range(count):
            job_id = str(uuid.uuid4())
            job_ids.append(job_id)
            message = {
                "job_id": job_id,
                "job_type": job_type,
                "params": params,
            }
            await redis_client.publish("job_requests", json.dumps(message))
        
        # 결과 대기 (최대 60초)
        start_time = asyncio.get_event_loop().time()
        while job_ids and (asyncio.get_event_loop().time() - start_time) < 60.0:
            completed_ids = [jid for jid in job_ids if jid in result_store]
            if len(completed_ids) == len(job_ids):
                break
            await asyncio.sleep(0.01)
        
        # 결과 수집
        for job_id in job_ids:
            if job_id in result_store:
                result_data = result_store[job_id]
                if result_data.get("status") == "done":
                    successes.append({
                        "id": job_id,
                        "type": job_type,
                        "params": params,
                        "result": result_data.get("result"),
                        "status": "done",
                        "mode": "async" if job_type in ("hash", "fib") else "sync",
                    })
                else:
                    failures.append({
                        "error": f"Job {job_id} failed: {result_data.get('status')}",
                    })
            else:
                failures.append({"error": f"Timeout waiting for job {job_id}"})
    
    except Exception as exc:
        # 예외를 실패로 변환
        error_msg = str(exc)
        failures.append({"error": f"MQ error: {error_msg}"})
        logging.exception("Error in _run_mq_batch_persistent")
    
    finally:
        # 정리
        if subscriber_task:
            subscriber_task.cancel()
            try:
                await subscriber_task
            except asyncio.CancelledError:
                pass
        if pubsub:
            try:
                await pubsub.unsubscribe("job_results")
                await pubsub.close()
            except Exception:
                pass
        if redis_client:
            try:
                await redis_client.close()
            except Exception:
                pass
    
    return BatchResult(successes=successes, failures=failures)


async def _create_job_async(
    client: httpx.AsyncClient,
    mq_base_url: str,
    job_type: str,
    params: dict[str, object],
) -> dict[str, object]:
    """비동기로 작업을 생성합니다."""
    try:
        # 타임아웃을 줄여서 빠른 응답 처리
        response = await client.post(
            f"{mq_base_url}/jobs",
            json={"job_type": job_type, "params": params},
        )
        response.raise_for_status()
        
        # Content-Type 확인하여 JSON이 아닌 경우 에러 처리
        content_type = response.headers.get("content-type", "").lower()
        if "application/json" not in content_type:
            text_preview = response.text[:200] if response.text else ""
            return {
                "success": False,
                "data": {
                    "error": f"Expected JSON response but got {content_type}. Response preview: {text_preview}",
                },
            }
        
        data = response.json()

        # REST API와 동일한 형식: {"result": {...}} 또는 {"job_id": "...", "status": "..."}
        if "result" in data:
            # 동기 작업: 결과가 바로 반환됨
            return {
                "success": True,
                "data": {
                    "id": "",
                    "type": job_type,
                    "params": params,
                    "result": data.get("result"),
                    "status": "done",
                    "mode": "sync",
                },
            }
        elif "job_id" in data or "id" in data:
            # 비동기 작업: job_id 반환
            job_id = data.get("job_id") or data.get("id", "")
            return {
                "success": True,
                "data": {
                    "id": job_id,
                    "type": job_type,
                    "params": params,
                    "status": data.get("status", "pending"),
                    "mode": "async",
                },
            }
        else:
            # 기존 형식 지원 (하위 호환성)
            if data.get("status") == "done":
                return {
                    "success": True,
                    "data": {
                        "id": data.get("id", ""),
                        "type": data.get("type", job_type),
                        "params": params,
                        "result": data.get("result"),
                        "status": "done",
                        "mode": "sync",
                    },
                }
            else:
                return {
                    "success": True,
                    "data": {
                        "id": data.get("id", ""),
                        "type": data.get("type", job_type),
                        "params": params,
                        "status": data.get("status", "pending"),
                        "mode": "async",
                    },
                }
    except Exception as exc:
        return {"success": False, "data": {"error": str(exc)}}


def create_single_mq(
    mq_base_url: str,
    job_type: str,
    params: dict[str, object],
) -> JobResult:
    """Redis에 직접 메시지를 발행하는 순수 MQ 패턴.

    Args:
        mq_base_url: MQ API 서버 URL (사용하지 않음, 하위 호환성용)
        job_type: 작업 타입
        params: 작업 파라미터

    Returns:
        JobResult: 성공 여부와 데이터를 포함한 결과
    """
    return asyncio.run(_create_single_mq_async(job_type, params))


async def _create_single_mq_async(
    job_type: str,
    params: dict[str, object],
) -> JobResult:
    """Redis에 직접 메시지를 발행하고 결과를 기다립니다."""
    import uuid
    
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    redis_client = redis.from_url(redis_url, decode_responses=True)
    result_store: dict[str, dict[str, object]] = {}
    
    try:
        # 결과 구독자 시작
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("job_results")
        
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
                            data = json.loads(message["data"])
                            job_id = data.get("job_id")
                            if job_id:
                                result_store[job_id] = data
                        except Exception:
                            pass
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    await asyncio.sleep(0.1)
        
        subscriber_task = asyncio.create_task(subscriber_loop())
        
        # 작업 발행
        job_id = str(uuid.uuid4())
        message = {
            "job_id": job_id,
            "job_type": job_type,
            "params": params,
        }
        await redis_client.publish("job_requests", json.dumps(message))
        
        # 결과 대기 (최대 30초)
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < 30.0:
            if job_id in result_store:
                result_data = result_store[job_id]
                subscriber_task.cancel()
                try:
                    await subscriber_task
                except asyncio.CancelledError:
                    pass
                
                if result_data.get("status") == "done":
                    return JobResult(
                        success=True,
                        data={
                            "id": job_id,
                            "type": job_type,
                            "params": params,
                            "result": result_data.get("result"),
                            "status": "done",
                            "mode": "async" if job_type in ("hash", "fib") else "sync",
                        },
                    )
                else:
                    return JobResult(
                        success=False,
                        data={"error": f"Job failed: {result_data.get('status')}"},
                    )
            await asyncio.sleep(0.1)
        
        # 타임아웃
        subscriber_task.cancel()
        try:
            await subscriber_task
        except asyncio.CancelledError:
            pass
        return JobResult(
            success=False,
            data={"error": f"Timeout waiting for job {job_id}"},
        )
    
    except Exception as exc:
        return JobResult(success=False, data={"error": str(exc)})
    finally:
        await pubsub.unsubscribe("job_results")
        await pubsub.close()
        await redis_client.close()
