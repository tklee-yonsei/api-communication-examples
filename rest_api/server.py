from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Optional, Tuple, TypedDict, cast

from flask import Flask, jsonify, request


class JobPayload(TypedDict):
    """서버가 보관하는 Job 상태 레코드 스키마

    Attributes:
        id (str): 생성된 작업의 고유 ID
        type (str): 작업 종류 식별자
        params (Mapping[str, Any]): 요청으로 전달된 파라미터
        status (str): 현재 상태(pending, running, done 등)
    """

    id: str
    type: str
    params: Mapping[str, Any]
    status: str


class RestApiServer:
    """테스트와 확장을 위한 클래스형 Flask 서버 래퍼"""

    def __init__(self, store: Optional[MutableMapping[str, JobPayload]] = None) -> None:
        """Flask 앱을 초기화하고 라우트를 등록합니다.

        Args:
            store (Optional[MutableMapping[str, JobPayload]]): 작업 상태를 저장할 공유 스토어
        """
        self.store: MutableMapping[str, JobPayload] = store if store is not None else {}
        self.app = Flask(__name__)
        self._register_routes()

    def _register_routes(self) -> None:
        """Flask 앱에 POST/GET 라우트를 등록합니다."""
        app = self.app
        jobs: MutableMapping[str, JobPayload] = self.store

        @app.post("/jobs")
        def create_job() -> Tuple[Any, int]:
            """POST /jobs 요청을 처리하여 새 작업을 생성합니다.

            Returns:
                Tuple[Any, int]: Flask 응답 튜플
            """
            data_raw: Any = request.get_json(silent=True)
            if not isinstance(data_raw, Mapping):
                return jsonify({"error": "Invalid payload"}), 400
            data = cast(Mapping[str, Any], data_raw)
            if "type" not in data or "params" not in data:
                return jsonify({"error": "Invalid payload"}), 400

            job_id = request.headers.get("X-Job-Id") or request.args.get("job_id")
            if not job_id:
                # 요청 간 충돌을 피하기 위해 flask.request가 아닌 uuid를 사용.
                import uuid

                job_id = str(uuid.uuid4())

            params: Mapping[str, Any] = cast(Mapping[str, Any], data.get("params", {}))

            jobs[job_id] = {
                "id": job_id,
                "type": str(data["type"]),
                "params": params,
                "status": "pending",
            }
            return jsonify({"job_id": job_id, "status": "pending"}), 201

        @app.get("/jobs/<job_id>")
        def get_job(job_id: str) -> Tuple[Any, int]:
            """GET /jobs/<job_id> 요청으로 작업 상태를 반환합니다.

            Args:
                job_id (str): 조회할 작업의 식별자

            Returns:
                Tuple[Any, int]: Flask 응답 튜플
            """
            job = jobs.get(job_id)
            if job is None:
                return jsonify({"error": "Job not found"}), 404
            return jsonify(job), 200

        # Flask 데코레이터로 등록되므로 린터가 미사용으로 판단하지 않도록 명시.
        _ = (create_job, get_job)

    def run(self, host: str = "0.0.0.0", port: int = 8080, debug: bool = False) -> None:
        """Flask 개발 서버를 실행합니다.

        Args:
            host (str): 바인딩할 호스트 인터페이스
            port (int): 수신할 포트 번호
            debug (bool): Flask 디버그 모드 활성 여부
        """
        self.app.run(host=host, port=port, debug=debug)


def create_app(store: Optional[MutableMapping[str, JobPayload]] = None) -> Flask:
    """테스트 호환을 위한 Flask 앱을 생성합니다.

    Args:
        store (Optional[MutableMapping[str, JobPayload]]): 선택적 공유 스토어입니다.

    Returns:
        Flask: 설정된 Flask 애플리케이션입니다.
    """
    return RestApiServer(store=store).app


if __name__ == "__main__":
    server = RestApiServer()
    server.run(host="0.0.0.0", port=8080, debug=False)
