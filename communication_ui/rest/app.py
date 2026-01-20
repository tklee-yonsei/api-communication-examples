from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import cast

from flask import Flask, Response, jsonify, make_response, render_template, request
from requests import Session

from communication.base import JobRecord
from rest_api.client import RestJobClient

# Docker 네트워크 내부: rest-api:8080
# devcontainer/로컬: host.docker.internal:8080 또는 localhost:8080
DEFAULT_BASE_URL = os.getenv("REST_API_BASE_URL", "http://host.docker.internal:8080")
MAX_CONCURRENCY = 64
MAX_COUNT = 20000


def create_app() -> Flask:
    """REST API 부하/정확도 테스트 UI"""
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )

    # 개발 중 템플릿/정적 파일 캐싱 비활성화
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    @app.get("/health")
    def health() -> Response:  # pyright: ignore[reportUnusedFunction]
        return jsonify({"status": "ok"})

    @app.get("/")
    def index() -> str:  # pyright: ignore[reportUnusedFunction]
        return render_template(
            "index.html",
            default_base_url=DEFAULT_BASE_URL,
        )

    @app.post("/api/jobs/batch")
    def create_jobs_batch() -> Response:  # pyright: ignore[reportUnusedFunction]
        payload: dict[str, object] = request.get_json(silent=True) or {}
        base_url = str(payload.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
        job_type = str(payload.get("job_type") or "default")
        params = _parse_params(payload.get("params"))
        count = _coerce_int(
            payload.get("count"), default=1, minimum=1, maximum=MAX_COUNT
        )
        concurrency = _coerce_int(
            payload.get("concurrency"), default=8, minimum=1, maximum=MAX_CONCURRENCY
        )

        started_at = time.perf_counter()
        successes, failures = _run_batch(base_url, job_type, params, count, concurrency)
        duration = time.perf_counter() - started_at

        sample_ids = [item["id"] for item in successes[:20] if "id" in item]
        sample_failures = failures[:10]

        return jsonify(
            {
                "base_url": base_url,
                "job_type": job_type,
                "params": params,
                "requested": count,
                "concurrency": concurrency,
                "duration_ms": round(duration * 1000, 2),
                "throughput_per_sec": round(count / duration, 2) if duration else None,
                "success": len(successes),
                "failure": len(failures),
                "sample_job_ids": sample_ids,
                "sample_failures": sample_failures,
            }
        )

    @app.get("/api/jobs/<job_id>")
    def get_job(  # pyright: ignore[reportUnusedFunction]
        job_id: str,
    ) -> Response:
        base_url = str(request.args.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
        with RestJobClient(base_url) as client:
            try:
                record = client.get_job(job_id)
            except Exception as exc:  # pragma: no cover - 사용자 입력 예외만
                return make_response(jsonify({"error": str(exc)}), 404)
        return jsonify(_record_to_dict(record))

    return app


def _parse_params(raw: object) -> dict[str, object]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return cast(dict[str, object], raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return cast(dict[str, object], parsed)
    return {}


def _coerce_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    """값을 정수로 변환하고 범위 내로 제한합니다.

    Args:
        value: 정수로 변환할 값
        default: 변환 실패 시 기본값
        minimum: 허용되는 최소값
        maximum: 허용되는 최대값

    Returns:
        int: 범위 내로 제한된 정수 값
    """
    as_int: int
    if isinstance(value, int):
        as_int = value
    elif isinstance(value, (str, float)):
        try:
            as_int = int(value)
        except (ValueError, TypeError):
            as_int = default
    else:
        as_int = default
    clamped: int = max(minimum, min(maximum, as_int))
    return clamped


def _run_batch(
    base_url: str,
    job_type: str,
    params: dict[str, object],
    count: int,
    concurrency: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    successes: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    max_workers = max(1, min(concurrency, count, MAX_CONCURRENCY))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_create_single, base_url, job_type, params)
            for _ in range(count)
        ]
        for future in as_completed(futures):
            ok, data = future.result()
            if ok:
                successes.append(data)
            else:
                failures.append(data)
    return successes, failures


def _create_single(
    base_url: str, job_type: str, params: dict[str, object]
) -> tuple[bool, dict[str, object]]:
    """단일 작업 요청을 전송합니다.

    동기 작업(echo, calc, stats): 즉시 결과 반환
    비동기 작업(hash, fib): job_id 반환 후 상태 조회
    """
    session = Session()

    try:
        # job_type에 따라 다른 엔드포인트 사용
        if job_type in ("echo", "calc", "stats"):
            # 동기: 즉시 결과 반환
            resp = session.post(f"{base_url}/{job_type}", json=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return True, {
                "type": job_type,
                "params": params,
                "result": data.get("result"),
                "mode": "sync",
            }
        elif job_type in ("hash", "fib"):
            # 비동기: job_id 반환
            resp = session.post(f"{base_url}/{job_type}_jobs", json=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            job_id = data.get("job_id", "")
            return True, {
                "id": job_id,
                "type": job_type,
                "params": params,
                "status": data.get("status", "pending"),
                "mode": "async",
            }
        else:
            # 알 수 없는 타입
            return False, {"error": f"Unknown job type: {job_type}"}
    except Exception as exc:  # pragma: no cover - 네트워크/서버 오류만
        return False, {"error": str(exc)}
    finally:
        session.close()


def _record_to_dict(record: JobRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "type": record.type,
        "params": record.params,
        "status": record.status,
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", "3000"))
    create_app().run(host="0.0.0.0", port=port, debug=False)
