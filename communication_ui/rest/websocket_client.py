"""WebSocket API 클라이언트 함수."""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import websockets
from websockets.exceptions import ConnectionClosed  # type: ignore[import-untyped]

from communication_ui.rest.config import MAX_CONCURRENCY
from communication_ui.rest.types import BatchResult, JobResult


def run_websocket_batch(
    websocket_url: str,
    job_type: str,
    params: dict[str, object],
    count: int,
    concurrency: int,
) -> BatchResult:
    """WebSocket 서버로 대량 요청을 전송합니다.

    Args:
        websocket_url: WebSocket 서버 URL
        job_type: 작업 타입
        params: 작업 파라미터
        count: 요청 개수
        concurrency: 동시 요청 수

    Returns:
        BatchResult: 성공/실패 결과
    """
    successes: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    max_workers = max(1, min(concurrency, count, MAX_CONCURRENCY))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(create_single_websocket, websocket_url, job_type, params)
            for _ in range(count)
        ]
        for future in as_completed(futures):
            result = future.result()
            if result.success:
                successes.append(result.data)
            else:
                failures.append(result.data)
    return BatchResult(successes=successes, failures=failures)


def create_single_websocket(
    websocket_url: str,
    job_type: str,
    params: dict[str, object],
) -> JobResult:
    """WebSocket으로 단일 작업 요청을 전송합니다.

    Args:
        websocket_url: WebSocket 서버 URL
        job_type: 작업 타입
        params: 작업 파라미터

    Returns:
        JobResult: 성공 여부와 데이터를 포함한 결과
    """
    try:
        # websockets 라이브러리를 직접 사용하여 WebSocket 통신
        result = asyncio.run(_create_job_async(websocket_url, job_type, params))
        return result
    except Exception as exc:
        error_msg = str(exc)
        # WebSocket 연결 오류에 대한 더 자세한 메시지
        if any(keyword in error_msg.lower() for keyword in ["connection", "connect", "html", "<!doctype", "json", "unexpected token", "module"]):
            error_msg = (
                f"WebSocket 서버에 연결할 수 없습니다.\n"
                f"URL: {websocket_url}\n"
                f"원인: {error_msg}\n"
                f"\n해결 방법:\n"
                f"  1. WebSocket 서버가 실행 중인지 확인:\n"
                f"     docker compose ps (외부 터미널에서)\n"
                f"  2. URL 확인:\n"
                f"     - 개발 컨테이너에서: ws://localhost:8082/ws\n"
                f"     - Docker 네트워크 내부: ws://websocket-api-dev:8082/ws\n"
                f"  3. 서버 로그 확인:\n"
                f"     docker compose logs websocket-api-dev"
            )
        return JobResult(success=False, data={"error": error_msg})


async def _create_job_async(
    websocket_url: str,
    job_type: str,
    params: dict[str, object],
) -> JobResult:
    """비동기로 WebSocket 작업을 생성합니다."""
    try:
        async with websockets.connect(websocket_url) as websocket:
            # 초기 메시지 수신 (init 메시지 무시)
            try:
                init_msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                init_data = json.loads(init_msg)
                if init_data.get("type") != "init":
                    # init이 아니면 나중에 처리할 수 있도록 큐에 저장
                    pass
            except (asyncio.TimeoutError, json.JSONDecodeError):
                pass  # init 메시지가 없거나 파싱 실패는 무시

            # 작업 생성 요청 전송
            request = {
                "type": "create_job",
                "job_type": job_type,
                "params": params,
            }
            await websocket.send(json.dumps(request))

            # 응답 대기
            if job_type in ("echo", "calc", "stats"):
                # 동기 작업: job_result 메시지 대기
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                response_data = json.loads(response)
                
                if response_data.get("type") == "job_result":
                    job_data = response_data.get("job", {})
                    result_data = job_data.get("params", {}).get("result") if isinstance(job_data.get("params"), dict) else None
                    return JobResult(
                        success=True,
                        data={
                            "type": job_type,
                            "params": params,
                            "result": result_data,
                            "status": "done",
                            "mode": "sync",
                        },
                    )
                elif response_data.get("type") == "error":
                    return JobResult(
                        success=False,
                        data={"error": response_data.get("message", "Unknown error")},
                    )
                else:
                    return JobResult(
                        success=False,
                        data={"error": f"Unexpected response type: {response_data.get('type')}"},
                    )
            else:
                # 비동기 작업: job_created 메시지 대기
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                response_data = json.loads(response)
                
                if response_data.get("type") == "job_created":
                    job_data = response_data.get("job", {})
                    return JobResult(
                        success=True,
                        data={
                            "id": job_data.get("id", ""),
                            "type": job_data.get("type", job_type),
                            "params": params,
                            "status": job_data.get("status", "pending"),
                            "mode": "async",
                        },
                    )
                elif response_data.get("type") == "error":
                    return JobResult(
                        success=False,
                        data={"error": response_data.get("message", "Unknown error")},
                    )
                else:
                    return JobResult(
                        success=False,
                        data={"error": f"Unexpected response type: {response_data.get('type')}"},
                    )
    except Exception as e:
        error_str = str(e)
        error_type = type(e).__name__
        # WebSocket 관련 예외 처리
        if isinstance(e, ConnectionClosed):
            raise RuntimeError(f"WebSocket 연결이 종료되었습니다. URL: {websocket_url}") from e
        elif "InvalidURI" in error_type or "invalid uri" in error_str.lower():
            raise RuntimeError(f"Invalid WebSocket URL: {websocket_url}") from e
        elif "StatusCode" in error_type or "status code" in error_str.lower() or "http" in error_str.lower():
            raise RuntimeError(
                f"WebSocket 서버가 HTTP 응답을 반환했습니다. 서버가 실행 중인지 확인하세요. URL: {websocket_url}"
            ) from e
        else:
            raise
