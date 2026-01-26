from __future__ import annotations

import json
import os
import threading
import time
from typing import Optional

from flask import Flask, Response, jsonify, make_response, render_template, request
from flask_sock import Sock
from requests import Session
from simple_websocket import Server as WsServer

from communication_ui.rest.config import (
    DEFAULT_BASE_URL,
    DEFAULT_GRPC_HOST,
    DEFAULT_GRPC_PORT,
    DEFAULT_WEBSOCKET_URL,
    MAX_CONCURRENCY,
    MAX_COUNT,
)
from communication_ui.rest.grpc_client import run_grpc_batch
from communication_ui.rest.rest_client import run_batch
from communication_ui.rest.websocket_client import run_websocket_batch
from communication_ui.rest.types import BatchResult
from communication_ui.rest.utils import coerce_int, parse_params

# flask-sock 타입 정의 없음 - 타입 검사 무시
# pyright: reportUnknownMemberType=false


def create_app() -> Flask:
    """REST/gRPC API 부하/정확도 테스트 UI"""
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )
    sock = Sock(app)

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
            default_grpc_host=DEFAULT_GRPC_HOST,
            default_grpc_port=DEFAULT_GRPC_PORT,
            default_websocket_url=DEFAULT_WEBSOCKET_URL,
        )

    @app.get("/api/jobs")
    def list_jobs() -> Response:  # pyright: ignore[reportUnusedFunction]
        """전체 Job 목록을 프록시합니다."""
        base_url = str(request.args.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
        limit = request.args.get("limit", "50")
        session = Session()
        try:
            resp = session.get(f"{base_url}/jobs?limit={limit}", timeout=10)
            resp.raise_for_status()
            return jsonify(resp.json())
        except Exception as exc:  # pragma: no cover
            return make_response(jsonify({"error": str(exc)}), 500)
        finally:
            session.close()

    @sock.route("/ws/jobs")
    def websocket_jobs_proxy(  # pyright: ignore[reportUnusedFunction]
        ws: WsServer,
    ) -> None:
        """REST API의 WebSocket을 프록시합니다."""
        import websockets.sync.client as ws_client

        base_url = request.args.get("base_url") or DEFAULT_BASE_URL
        ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/ws/jobs"

        try:
            with ws_client.connect(ws_url) as upstream:
                # 양방향 프록시를 위한 스레드
                stop_event = threading.Event()

                def forward_upstream_to_client() -> None:
                    """upstream -> client 메시지 전달"""
                    try:
                        while not stop_event.is_set():
                            try:
                                msg = upstream.recv(timeout=1.0)
                                if msg:
                                    ws.send(msg)
                            except TimeoutError:
                                continue
                    except Exception:
                        pass

                # upstream -> client 스레드 시작
                forward_thread = threading.Thread(
                    target=forward_upstream_to_client, daemon=True
                )
                forward_thread.start()

                # client -> upstream 메인 루프
                try:
                    while True:
                        try:
                            data: Optional[str | bytes]
                            data = ws.receive(  # pyright: ignore[reportUnknownVariableType]
                                timeout=30
                            )
                            if data is None:
                                break
                            upstream.send(
                                data  # pyright: ignore[reportUnknownArgumentType]
                            )
                        except TimeoutError:
                            # ping 전송
                            ws.send(
                                json.dumps({"type": "ping"})
                            )  # pyright: ignore[reportUnknownMemberType]
                except Exception:
                    pass
                finally:
                    stop_event.set()
                    forward_thread.join(timeout=2.0)
        except Exception as e:
            try:
                ws.send(json.dumps({"type": "error", "message": str(e)}))
            except Exception:
                pass

    @app.post("/api/jobs/batch")
    def create_jobs_batch() -> Response:  # pyright: ignore[reportUnusedFunction]
        payload: dict[str, object] = request.get_json(silent=True) or {}
        base_url = str(payload.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
        job_type = str(payload.get("job_type") or "default")
        params = parse_params(payload.get("params"))
        count = coerce_int(
            payload.get("count"), default=1, minimum=1, maximum=MAX_COUNT
        )
        concurrency = coerce_int(
            payload.get("concurrency"), default=8, minimum=1, maximum=MAX_CONCURRENCY
        )

        started_at = time.perf_counter()
        result: BatchResult = run_batch(base_url, job_type, params, count, concurrency)
        duration = time.perf_counter() - started_at

        sample_ids: list[str] = [
            str(item["id"]) for item in result.successes[:20] if "id" in item
        ]
        sample_results: list[object] = [
            item["result"] for item in result.successes[:20] if "result" in item
        ]
        sample_failures: list[dict[str, object]] = result.failures[:10]

        return jsonify(
            {
                "base_url": base_url,
                "job_type": job_type,
                "params": params,
                "requested": count,
                "concurrency": concurrency,
                "duration_ms": round(duration * 1000, 2),
                "throughput_per_sec": round(count / duration, 2) if duration else None,
                "success": len(result.successes),
                "failure": len(result.failures),
                "sample_job_ids": sample_ids,
                "sample_results": sample_results,
                "sample_failures": sample_failures,
            }
        )

    @app.get("/api/jobs/<job_id>")
    def get_job(  # pyright: ignore[reportUnusedFunction]
        job_id: str,
    ) -> Response:
        base_url = str(request.args.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
        # REST API를 직접 호출하여 result 필드를 포함한 전체 응답 반환
        session = Session()
        try:
            resp = session.get(f"{base_url}/jobs/{job_id}", timeout=10)
            if resp.status_code == 404:
                return make_response(jsonify({"error": f"Job {job_id} not found"}), 404)
            resp.raise_for_status()
            return jsonify(resp.json())
        except Exception as exc:  # pragma: no cover - 네트워크/서버 오류만
            return make_response(jsonify({"error": str(exc)}), 500)
        finally:
            session.close()

    # ==========================================
    # WebSocket API 프록시 엔드포인트
    # ==========================================

    @app.post("/api/websocket/batch")
    def websocket_batch() -> Response:  # pyright: ignore[reportUnusedFunction]
        """WebSocket 서버로 대량 요청을 전송합니다."""
        payload: dict[str, object] = request.get_json(silent=True) or {}
        websocket_url = str(payload.get("websocket_url") or DEFAULT_WEBSOCKET_URL)
        job_type = str(payload.get("job_type") or "echo")
        params = parse_params(payload.get("params"))
        count = coerce_int(
            payload.get("count"), default=1, minimum=1, maximum=MAX_COUNT
        )
        concurrency = coerce_int(
            payload.get("concurrency"), default=8, minimum=1, maximum=MAX_CONCURRENCY
        )
        persistent = bool(payload.get("persistent", False))

        started_at = time.perf_counter()
        result: BatchResult = run_websocket_batch(
            websocket_url, job_type, params, count, concurrency, persistent
        )
        duration = time.perf_counter() - started_at

        sample_ids: list[str] = [
            str(item["id"]) for item in result.successes[:20] if "id" in item
        ]
        sample_results: list[object] = [
            item["result"] for item in result.successes[:20] if "result" in item
        ]
        sample_failures: list[dict[str, object]] = result.failures[:10]

        return jsonify(
            {
                "websocket_url": websocket_url,
                "job_type": job_type,
                "params": params,
                "requested": count,
                "concurrency": concurrency,
                "persistent": persistent,
                "duration_ms": round(duration * 1000, 2),
                "throughput_per_sec": round(count / duration, 2) if duration else None,
                "success": len(result.successes),
                "failure": len(result.failures),
                "sample_job_ids": sample_ids,
                "sample_results": sample_results,
                "sample_failures": sample_failures,
            }
        )

    # ==========================================
    # gRPC API 프록시 엔드포인트
    # ==========================================

    @app.post("/api/grpc/batch")
    def grpc_batch() -> Response:  # pyright: ignore[reportUnusedFunction]
        """gRPC 서버로 대량 요청을 전송합니다."""
        payload: dict[str, object] = request.get_json(silent=True) or {}
        grpc_host = str(payload.get("grpc_host") or DEFAULT_GRPC_HOST)
        grpc_port = coerce_int(
            payload.get("grpc_port"),
            default=DEFAULT_GRPC_PORT,
            minimum=1,
            maximum=65535,
        )
        job_type = str(payload.get("job_type") or "echo")
        params = parse_params(payload.get("params"))
        count = coerce_int(
            payload.get("count"), default=1, minimum=1, maximum=MAX_COUNT
        )
        concurrency = coerce_int(
            payload.get("concurrency"), default=8, minimum=1, maximum=MAX_CONCURRENCY
        )
        persistent = bool(payload.get("persistent", False))

        started_at = time.perf_counter()
        result: BatchResult = run_grpc_batch(
            grpc_host, grpc_port, job_type, params, count, concurrency, persistent
        )
        duration = time.perf_counter() - started_at

        sample_ids: list[str] = [
            str(item["id"]) for item in result.successes[:20] if "id" in item
        ]
        sample_results: list[object] = [
            item["result"] for item in result.successes[:20] if "result" in item
        ]
        sample_failures: list[dict[str, object]] = result.failures[:10]

        return jsonify(
            {
                "grpc_host": grpc_host,
                "grpc_port": grpc_port,
                "job_type": job_type,
                "params": params,
                "requested": count,
                "concurrency": concurrency,
                "persistent": persistent,
                "duration_ms": round(duration * 1000, 2),
                "throughput_per_sec": round(count / duration, 2) if duration else None,
                "success": len(result.successes),
                "failure": len(result.failures),
                "sample_job_ids": sample_ids,
                "sample_results": sample_results,
                "sample_failures": sample_failures,
            }
        )

    @app.get("/api/grpc/jobs/<job_id>")
    def grpc_get_job(  # pyright: ignore[reportUnusedFunction]
        job_id: str,
    ) -> Response:
        """gRPC 서버에서 Job 상태를 조회합니다."""
        grpc_host = str(request.args.get("grpc_host") or DEFAULT_GRPC_HOST)
        grpc_port = coerce_int(
            request.args.get("grpc_port"),
            default=DEFAULT_GRPC_PORT,
            minimum=1,
            maximum=65535,
        )

        try:
            from grpc_api.client import GrpcJobClient

            with GrpcJobClient(host=grpc_host, port=grpc_port) as client:
                record = client.get_job(job_id)
                return jsonify(
                    {
                        "id": record.id,
                        "type": record.type,
                        "status": record.status,
                        "params": record.params,
                    }
                )
        except Exception as exc:
            error_msg = str(exc)
            if "not found" in error_msg.lower():
                return make_response(jsonify({"error": f"Job {job_id} not found"}), 404)
            return make_response(jsonify({"error": error_msg}), 500)

    @app.get("/api/grpc/jobs")
    def grpc_list_jobs() -> Response:  # pyright: ignore[reportUnusedFunction]
        """gRPC 서버에서 전체 Job 목록을 조회합니다."""
        grpc_host = str(request.args.get("grpc_host") or DEFAULT_GRPC_HOST)
        grpc_port = coerce_int(
            request.args.get("grpc_port"),
            default=DEFAULT_GRPC_PORT,
            minimum=1,
            maximum=65535,
        )
        limit = coerce_int(
            request.args.get("limit"), default=50, minimum=1, maximum=1000
        )

        try:
            from grpc_api.client import GrpcJobClient

            client = GrpcJobClient(host=grpc_host, port=grpc_port)
            try:
                result = client.list_jobs(limit=limit)
                return jsonify(result)
            finally:
                client.close()
        except Exception as exc:
            return make_response(jsonify({"error": str(exc)}), 500)

    @app.get("/api/grpc/queue/status")
    def grpc_queue_status() -> Response:  # pyright: ignore[reportUnusedFunction]
        """gRPC 서버의 작업 큐 상태를 조회합니다."""
        grpc_host = str(request.args.get("grpc_host") or DEFAULT_GRPC_HOST)
        grpc_port = coerce_int(
            request.args.get("grpc_port"),
            default=DEFAULT_GRPC_PORT,
            minimum=1,
            maximum=65535,
        )

        try:
            from grpc_api.client import GrpcJobClient

            client = GrpcJobClient(host=grpc_host, port=grpc_port)
            try:
                result = client.get_queue_status()
                return jsonify(result)
            finally:
                client.close()
        except Exception as exc:
            return make_response(jsonify({"error": str(exc)}), 500)

    return app


if __name__ == "__main__":
    port = int(os.getenv("PORT", "3000"))
    create_app().run(host="0.0.0.0", port=port, debug=False)
