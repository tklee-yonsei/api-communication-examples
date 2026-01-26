"""gRPC API 클라이언트 함수."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Union, cast

from communication_ui.rest.config import MAX_CONCURRENCY
from communication_ui.rest.types import BatchResult, JobResult


def run_grpc_batch(
    grpc_host: str,
    grpc_port: int,
    job_type: str,
    params: dict[str, object],
    count: int,
    concurrency: int,
    persistent: bool = False,
) -> BatchResult:
    """gRPC 서버로 대량 요청을 전송합니다.

    Args:
        grpc_host: gRPC 서버 호스트
        grpc_port: gRPC 서버 포트
        job_type: 작업 타입
        params: 작업 파라미터
        count: 요청 개수
        concurrency: 동시 요청 수 (persistent=False일 때만 사용)
        persistent: True이면 단일 연결로 모든 요청 전송, False이면 각 요청마다 연결 생성

    Returns:
        BatchResult: 성공/실패 결과
    """
    if persistent:
        return _run_grpc_batch_persistent(grpc_host, grpc_port, job_type, params, count)

    successes: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    max_workers = max(1, min(concurrency, count, MAX_CONCURRENCY))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(create_single_grpc, grpc_host, grpc_port, job_type, params)
            for _ in range(count)
        ]
        for future in as_completed(futures):
            result = future.result()
            if result.success:
                successes.append(result.data)
            else:
                failures.append(result.data)
    return BatchResult(successes=successes, failures=failures)


def _run_grpc_batch_persistent(
    grpc_host: str,
    grpc_port: int,
    job_type: str,
    params: dict[str, object],
    count: int,
) -> BatchResult:
    """단일 gRPC 연결로 여러 요청을 전송합니다 (비동기 병렬 처리)."""
    from grpc_api.client.async_client import AsyncGrpcJobClient

    async def run_async() -> BatchResult:
        successes: list[dict[str, object]] = []
        failures: list[dict[str, object]] = []

        try:
            async with AsyncGrpcJobClient(host=grpc_host, port=grpc_port) as client:
                # 여러 요청을 비동기로 병렬 전송 (gRPC HTTP/2 멀티플렉싱 활용)
                tasks: list[asyncio.Task[dict[str, object]]] = []
                for _ in range(count):
                    task = asyncio.create_task(
                        _create_job_async(client, job_type, params)
                    )
                    tasks.append(task)

                results: list[Union[dict[str, object], BaseException]] = (
                    await asyncio.gather(*tasks, return_exceptions=True)
                )

                for result in results:
                    if isinstance(result, Exception):
                        failures.append({"error": str(result)})
                    elif isinstance(result, dict):
                        success_flag = result.get("success")
                        data = result.get("data", {})
                        if success_flag and isinstance(data, dict):
                            successes.append(cast(dict[str, object], data))
                        elif not success_flag and isinstance(data, dict):
                            failures.append(cast(dict[str, object], data))
        except Exception as exc:
            # 연결 실패 시 모든 요청을 실패로 처리
            for _ in range(count - len(successes) - len(failures)):
                failures.append({"error": str(exc)})

        return BatchResult(successes=successes, failures=failures)

    async def _create_job_async(
        client: AsyncGrpcJobClient,
        job_type: str,
        params: dict[str, object],
    ) -> dict[str, object]:
        """비동기로 작업을 생성합니다."""
        try:
            # 비동기 클라이언트는 응답에서 result를 추출하지 않으므로
            # 동기 클라이언트처럼 직접 호출하여 result를 얻어야 함
            from grpc_api.client.utils import (
                create_calc_request,
                create_echo_request,
                create_stats_request,
            )

            if client.stub is None:
                raise RuntimeError("Client not connected")

            if job_type == "echo":
                request = create_echo_request(params)
                response = await client.stub.Echo(request)  # type: ignore[assignment, misc]
                # protobuf 응답 타입은 런타임에 확인됨
                response_any: Any = cast(Any, response)
                echo_dict = (
                    dict(response_any.echo) if hasattr(response_any, "echo") else {}
                )
                echo_result_data: dict[str, Any] = {"echo": echo_dict}
                return {
                    "success": True,
                    "data": {
                        "type": job_type,
                        "params": params,
                        "result": echo_result_data,
                        "status": "done",
                        "mode": "sync",
                    },
                }
            elif job_type == "calc":
                request = create_calc_request(params)
                response = await client.stub.Calc(request)  # type: ignore[assignment, misc]
                # protobuf 응답 타입은 런타임에 확인됨
                response_any = cast(Any, response)
                calc_result_data: dict[str, Any] = {
                    "op": str(response_any.op) if hasattr(response_any, "op") else "",
                    "a": float(response_any.a) if hasattr(response_any, "a") else 0.0,
                    "b": float(response_any.b) if hasattr(response_any, "b") else 0.0,
                    "result": (
                        float(response_any.result)
                        if hasattr(response_any, "result")
                        else 0.0
                    ),
                }
                if hasattr(response_any, "error") and response_any.error:
                    calc_result_data["error"] = str(response_any.error)
                return {
                    "success": True,
                    "data": {
                        "type": job_type,
                        "params": params,
                        "result": calc_result_data,
                        "status": "done",
                        "mode": "sync",
                    },
                }
            elif job_type == "stats":
                request = create_stats_request(params)
                response = await client.stub.Stats(request)  # type: ignore[assignment, misc]
                # protobuf 응답 타입은 런타임에 확인됨
                response_any = cast(Any, response)
                if hasattr(response_any, "error") and response_any.error:
                    stats_result_data: dict[str, Any] = {
                        "error": str(response_any.error)
                    }
                else:
                    stats_result_data = {
                        "count": (
                            int(response_any.count)
                            if hasattr(response_any, "count")
                            else 0
                        ),
                        "min": (
                            float(response_any.min)
                            if hasattr(response_any, "min")
                            else 0.0
                        ),
                        "max": (
                            float(response_any.max)
                            if hasattr(response_any, "max")
                            else 0.0
                        ),
                        "sum": (
                            float(response_any.sum)
                            if hasattr(response_any, "sum")
                            else 0.0
                        ),
                        "mean": (
                            float(response_any.mean)
                            if hasattr(response_any, "mean")
                            else 0.0
                        ),
                        "median": (
                            float(response_any.median)
                            if hasattr(response_any, "median")
                            else 0.0
                        ),
                    }
                return {
                    "success": True,
                    "data": {
                        "type": job_type,
                        "params": params,
                        "result": stats_result_data,
                        "status": "done",
                        "mode": "sync",
                    },
                }
            else:
                # 비동기 작업: create_job 사용
                record = await client.create_job(job_type, params)
                return {
                    "success": True,
                    "data": {
                        "id": record.id,
                        "type": record.type,
                        "params": params,
                        "status": record.status,
                        "mode": "async",
                    },
                }
        except Exception as exc:
            return {"success": False, "data": {"error": str(exc)}}

    return asyncio.run(run_async())


def create_single_grpc(
    grpc_host: str,
    grpc_port: int,
    job_type: str,
    params: dict[str, object],
) -> JobResult:
    """gRPC로 단일 작업 요청을 전송합니다.

    Args:
        grpc_host: gRPC 서버 호스트
        grpc_port: gRPC 서버 포트
        job_type: 작업 타입
        params: 작업 파라미터

    Returns:
        JobResult: 성공 여부와 데이터를 포함한 결과
    """
    try:
        from grpc_api.client import GrpcJobClient

        with GrpcJobClient(host=grpc_host, port=grpc_port) as client:
            record = client.create_job(job_type, params)

            if record.status == "done":
                # 동기 작업: 결과가 params["result"]에 들어있음
                result_data = record.params.get("result") if record.params else None
                return JobResult(
                    success=True,
                    data={
                        "type": record.type,
                        "params": params,
                        "result": result_data,
                        "status": record.status,
                        "mode": "sync",
                    },
                )
            else:
                # 비동기 작업: job_id 반환
                return JobResult(
                    success=True,
                    data={
                        "id": record.id,
                        "type": record.type,
                        "params": params,
                        "status": record.status,
                        "mode": "async",
                    },
                )
    except Exception as exc:
        return JobResult(success=False, data={"error": str(exc)})
