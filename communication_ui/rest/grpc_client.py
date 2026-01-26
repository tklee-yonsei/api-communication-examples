"""gRPC API 클라이언트 함수."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

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
    """단일 gRPC 연결로 여러 요청을 전송합니다."""
    successes: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    
    try:
        from grpc_api.client import GrpcJobClient

        with GrpcJobClient(host=grpc_host, port=grpc_port) as client:
            # 여러 요청을 순차적으로 전송
            for _ in range(count):
                try:
                    record = client.create_job(job_type, params)

                    if record.status == "done":
                        # 동기 작업: 결과가 params["result"]에 들어있음
                        result_data = record.params.get("result") if record.params else None
                        successes.append({
                            "type": record.type,
                            "params": params,
                            "result": result_data,
                            "status": record.status,
                            "mode": "sync",
                        })
                    else:
                        # 비동기 작업: job_id 반환
                        successes.append({
                            "id": record.id,
                            "type": record.type,
                            "params": params,
                            "status": record.status,
                            "mode": "async",
                        })
                except Exception as exc:
                    failures.append({"error": str(exc)})
    except Exception as exc:
        # 연결 실패 시 모든 요청을 실패로 처리
        for _ in range(count - len(successes) - len(failures)):
            failures.append({"error": str(exc)})
    
    return BatchResult(successes=successes, failures=failures)


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
