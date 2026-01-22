"""REST API 클라이언트 함수."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from requests import Session

from communication_ui.rest.config import MAX_CONCURRENCY
from communication_ui.rest.types import BatchResult, JobResult


def run_batch(
    base_url: str,
    job_type: str,
    params: dict[str, object],
    count: int,
    concurrency: int,
) -> BatchResult:
    """REST API로 대량 요청을 전송합니다.

    Args:
        base_url: REST API 기본 URL
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
            executor.submit(create_single, base_url, job_type, params)
            for _ in range(count)
        ]
        for future in as_completed(futures):
            result = future.result()
            if result.success:
                successes.append(result.data)
            else:
                failures.append(result.data)
    return BatchResult(successes=successes, failures=failures)


def create_single(base_url: str, job_type: str, params: dict[str, object]) -> JobResult:
    """단일 작업 요청을 전송합니다.

    동기 작업(echo, calc, stats): 즉시 결과 반환
    비동기 작업(hash, fib): job_id 반환 후 상태 조회

    Args:
        base_url: REST API 기본 URL
        job_type: 작업 타입
        params: 작업 파라미터

    Returns:
        JobResult: 성공 여부와 데이터를 포함한 결과
    """
    session = Session()

    try:
        # job_type에 따라 다른 엔드포인트 사용
        if job_type in ("echo", "calc", "stats"):
            # 동기: 즉시 결과 반환
            resp = session.post(f"{base_url}/{job_type}", json=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return JobResult(
                success=True,
                data={
                    "type": job_type,
                    "params": params,
                    "result": data.get("result"),
                    "mode": "sync",
                },
            )
        elif job_type in ("hash", "fib"):
            # 비동기: job_id 반환
            resp = session.post(f"{base_url}/{job_type}_jobs", json=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            job_id = data.get("job_id", "")
            return JobResult(
                success=True,
                data={
                    "id": job_id,
                    "type": job_type,
                    "params": params,
                    "status": data.get("status", "pending"),
                    "mode": "async",
                },
            )
        else:
            # 알 수 없는 타입
            return JobResult(
                success=False, data={"error": f"Unknown job type: {job_type}"}
            )
    except Exception as exc:  # pragma: no cover - 네트워크/서버 오류만
        return JobResult(success=False, data={"error": str(exc)})
    finally:
        session.close()
