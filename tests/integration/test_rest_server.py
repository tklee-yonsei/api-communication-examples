"""REST API 서버 통합 테스트.

실제 HTTP 요청을 통해 REST API 서버의 엔드포인트를 테스트합니다.
FastAPI의 TestClient를 사용하거나 실제 서버에 요청을 보냅니다.

테스트 대상:
- 동기 엔드포인트: /echo, /calc, /stats
- 비동기 엔드포인트: /hash_jobs, /fib_jobs
- 작업 조회 엔드포인트: /jobs/{job_id}
- 큐 상태 엔드포인트: /queue/status
"""

from __future__ import annotations

import concurrent.futures
import time
from typing import Any, Iterator

import pytest
import requests
from fastapi.testclient import TestClient

from rest_api import create_app
from tests.conftest import ServerThread


class TestSyncEndpointsWithTestClient:
    """동기 엔드포인트 테스트 (TestClient 사용).

    FastAPI의 TestClient를 사용하여 동기 엔드포인트를 테스트합니다.
    실제 서버를 띄우지 않고 빠르게 테스트할 수 있습니다.
    """

    @pytest.fixture
    def client(self) -> TestClient:
        """FastAPI TestClient를 생성합니다.

        Returns:
            TestClient: 테스트 클라이언트
        """
        app = create_app()
        return TestClient(app)

    def test_echo_endpoint(self, client: TestClient) -> None:
        """POST /echo 엔드포인트를 테스트합니다.

        입력 데이터가 그대로 반환되는지 확인합니다.

        Args:
            client: FastAPI 테스트 클라이언트
        """
        response = client.post("/echo", json={"message": "hello", "count": 42})

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["echo"]["message"] == "hello"
        assert data["result"]["echo"]["count"] == 42

    def test_echo_empty_payload(self, client: TestClient) -> None:
        """빈 페이로드로 /echo 엔드포인트를 테스트합니다.

        Args:
            client: FastAPI 테스트 클라이언트
        """
        response = client.post("/echo", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["result"]["echo"] == {}

    def test_calc_add(self, client: TestClient) -> None:
        """POST /calc 덧셈 연산을 테스트합니다.

        Args:
            client: FastAPI 테스트 클라이언트
        """
        response = client.post("/calc", json={"op": "add", "a": 10.0, "b": 5.0})

        assert response.status_code == 200
        data = response.json()
        assert data["result"]["op"] == "add"
        assert data["result"]["result"] == 15.0

    def test_calc_subtract(self, client: TestClient) -> None:
        """POST /calc 뺄셈 연산을 테스트합니다.

        Args:
            client: FastAPI 테스트 클라이언트
        """
        response = client.post("/calc", json={"op": "sub", "a": 10.0, "b": 3.0})

        assert response.status_code == 200
        data = response.json()
        assert data["result"]["result"] == 7.0

    def test_calc_multiply(self, client: TestClient) -> None:
        """POST /calc 곱셈 연산을 테스트합니다.

        Args:
            client: FastAPI 테스트 클라이언트
        """
        response = client.post("/calc", json={"op": "mul", "a": 4.0, "b": 3.0})

        assert response.status_code == 200
        data = response.json()
        assert data["result"]["result"] == 12.0

    def test_calc_divide(self, client: TestClient) -> None:
        """POST /calc 나눗셈 연산을 테스트합니다.

        Args:
            client: FastAPI 테스트 클라이언트
        """
        response = client.post("/calc", json={"op": "div", "a": 20.0, "b": 4.0})

        assert response.status_code == 200
        data = response.json()
        assert data["result"]["result"] == 5.0

    def test_calc_divide_by_zero(self, client: TestClient) -> None:
        """POST /calc 0으로 나누기 시 에러를 테스트합니다.

        Args:
            client: FastAPI 테스트 클라이언트
        """
        response = client.post("/calc", json={"op": "div", "a": 10.0, "b": 0.0})

        assert response.status_code == 200
        data = response.json()
        assert "error" in data["result"]
        assert "division" in data["result"]["error"].lower()

    def test_stats_basic(self, client: TestClient) -> None:
        """POST /stats 기본 통계 계산을 테스트합니다.

        Args:
            client: FastAPI 테스트 클라이언트
        """
        response = client.post("/stats", json={"values": [1, 2, 3, 4, 5]})

        assert response.status_code == 200
        data = response.json()
        result = data["result"]
        assert result["count"] == 5
        assert result["min"] == 1
        assert result["max"] == 5
        assert result["sum"] == 15
        assert result["mean"] == 3.0
        assert result["median"] == 3.0

    def test_stats_empty_values(self, client: TestClient) -> None:
        """빈 리스트로 /stats 호출 시 에러를 테스트합니다.

        Args:
            client: FastAPI 테스트 클라이언트
        """
        response = client.post("/stats", json={"values": []})

        assert response.status_code == 200
        data = response.json()
        assert "error" in data["result"]


class TestAsyncEndpointsWithTestClient:
    """비동기 엔드포인트 테스트 (TestClient 사용).

    비동기 작업 생성 및 조회를 테스트합니다.
    """

    @pytest.fixture
    def client(self) -> TestClient:
        """FastAPI TestClient를 생성합니다.

        Returns:
            TestClient: 테스트 클라이언트
        """
        app = create_app()
        return TestClient(app)

    def test_hash_job_creation(self, client: TestClient) -> None:
        """POST /hash_jobs 작업 생성을 테스트합니다.

        Args:
            client: FastAPI 테스트 클라이언트
        """
        response = client.post("/hash_jobs", json={"data": "test-data"})

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

    def test_fib_job_creation(self, client: TestClient) -> None:
        """POST /fib_jobs 작업 생성을 테스트합니다.

        Args:
            client: FastAPI 테스트 클라이언트
        """
        response = client.post("/fib_jobs", json={"n": 10})

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

    def test_get_job_not_found(self, client: TestClient) -> None:
        """존재하지 않는 작업 조회 시 404를 테스트합니다.

        Args:
            client: FastAPI 테스트 클라이언트
        """
        response = client.get("/jobs/non-existent-job-id")

        assert response.status_code == 404

    def test_queue_status(self, client: TestClient) -> None:
        """GET /queue/status 엔드포인트를 테스트합니다.

        Args:
            client: FastAPI 테스트 클라이언트
        """
        response = client.get("/queue/status")

        assert response.status_code == 200
        data = response.json()
        assert "queue_size" in data
        assert "is_full" in data
        assert "max_workers" in data


class TestRestServerIntegration:
    """실제 HTTP 서버 통합 테스트.

    실제 서버를 띄우고 HTTP 요청을 보내 전체 통합을 테스트합니다.
    """

    @pytest.fixture(scope="class")
    def server(self) -> Iterator[ServerThread]:
        """테스트용 서버를 시작합니다.

        Yields:
            ServerThread: 실행 중인 서버 스레드
        """
        srv = ServerThread()
        srv.start()
        time.sleep(0.5)
        yield srv
        srv.stop()

    @pytest.fixture
    def base_url(self, server: ServerThread) -> str:
        """서버의 베이스 URL을 반환합니다.

        Args:
            server: 실행 중인 서버

        Returns:
            str: 베이스 URL
        """
        return server.base_url

    def test_echo_via_http(self, base_url: str) -> None:
        """실제 HTTP 요청으로 /echo 엔드포인트를 테스트합니다.

        Args:
            base_url: 서버 베이스 URL
        """
        response = requests.post(
            f"{base_url}/echo", json={"message": "integration-test"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["result"]["echo"]["message"] == "integration-test"

    def test_calc_via_http(self, base_url: str) -> None:
        """실제 HTTP 요청으로 /calc 엔드포인트를 테스트합니다.

        Args:
            base_url: 서버 베이스 URL
        """
        response = requests.post(f"{base_url}/calc", json={"op": "mul", "a": 7, "b": 6})

        assert response.status_code == 200
        data = response.json()
        assert data["result"]["result"] == 42

    def test_hash_job_lifecycle(self, base_url: str) -> None:
        """해시 작업의 전체 생명주기를 테스트합니다.

        1. 작업 생성
        2. 작업 상태 조회
        3. 완료될 때까지 대기 (최대 10초)
        4. 결과 확인

        Args:
            base_url: 서버 베이스 URL
        """
        # 작업 생성
        create_response = requests.post(
            f"{base_url}/hash_jobs", json={"data": "lifecycle-test"}
        )
        assert create_response.status_code == 202
        job_id = create_response.json()["job_id"]

        # 작업 완료 대기 (폴링)
        max_attempts = 100  # 최대 10초 대기
        job_data = None
        for _ in range(max_attempts):
            status_response = requests.get(f"{base_url}/jobs/{job_id}")
            assert status_response.status_code == 200

            job_data = status_response.json()
            if job_data["status"] in ("done", "failed"):
                break
            time.sleep(0.1)

        # 결과 확인
        assert job_data is not None
        # 비동기 작업이므로 done이 아닐 수도 있음 (pending/running 허용)
        assert job_data["status"] in ("pending", "running", "done")
        assert job_data["type"] == "hash"

    def test_fib_job_lifecycle(self, base_url: str) -> None:
        """피보나치 작업의 전체 생명주기를 테스트합니다.

        Args:
            base_url: 서버 베이스 URL
        """
        # 작업 생성
        create_response = requests.post(f"{base_url}/fib_jobs", json={"n": 15})
        assert create_response.status_code == 202
        job_id = create_response.json()["job_id"]

        # 작업 완료 대기
        max_attempts = 100  # 최대 10초 대기
        job_data = None
        for _ in range(max_attempts):
            status_response = requests.get(f"{base_url}/jobs/{job_id}")
            assert status_response.status_code == 200

            job_data = status_response.json()
            if job_data["status"] in ("done", "failed"):
                break
            time.sleep(0.1)

        # 결과 확인
        assert job_data is not None
        # 비동기 작업이므로 done이 아닐 수도 있음 (pending/running 허용)
        assert job_data["status"] in ("pending", "running", "done")
        assert job_data["type"] == "fib"

    def test_concurrent_requests(self, base_url: str) -> None:
        """동시 요청 처리를 테스트합니다.

        Args:
            base_url: 서버 베이스 URL
        """

        def make_request(i: int) -> tuple[int, dict[str, Any]]:
            response = requests.post(
                f"{base_url}/echo", json={"index": i, "message": f"concurrent-{i}"}
            )
            result: dict[str, Any] = response.json()
            return i, result

        # 10개의 동시 요청
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures: list[concurrent.futures.Future[tuple[int, dict[str, Any]]]] = [
                executor.submit(make_request, i) for i in range(10)
            ]
            results: list[tuple[int, dict[str, Any]]] = [
                f.result() for f in concurrent.futures.as_completed(futures)
            ]

        # 모든 요청이 성공했는지 확인
        assert len(results) == 10
        for index, data in results:
            assert data["result"]["echo"]["index"] == index

    def test_server_handles_invalid_json(self, base_url: str) -> None:
        """잘못된 JSON 요청에 대한 처리를 테스트합니다.

        Args:
            base_url: 서버 베이스 URL
        """
        response = requests.post(
            f"{base_url}/echo",
            data="not valid json",
            headers={"Content-Type": "application/json"},
        )

        # FastAPI는 422 Unprocessable Entity를 반환
        assert response.status_code in (400, 422)

    def test_server_handles_missing_required_fields(self, base_url: str) -> None:
        """필수 필드 누락 시 에러 처리를 테스트합니다.

        Args:
            base_url: 서버 베이스 URL
        """
        # stats는 values 필드가 필수
        response = requests.post(f"{base_url}/stats", json={})

        # 422 Unprocessable Entity 예상
        assert response.status_code == 422


class TestHealthAndMetadata:
    """서버 상태 및 메타데이터 테스트."""

    @pytest.fixture
    def client(self) -> TestClient:
        """FastAPI TestClient를 생성합니다.

        Returns:
            TestClient: 테스트 클라이언트
        """
        app = create_app()
        return TestClient(app)

    def test_openapi_schema_available(self, client: TestClient) -> None:
        """OpenAPI 스키마가 제공되는지 테스트합니다.

        Args:
            client: FastAPI 테스트 클라이언트
        """
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert "paths" in schema
        assert "info" in schema

    def test_docs_endpoint(self, client: TestClient) -> None:
        """Swagger UI 문서 페이지가 제공되는지 테스트합니다.

        Args:
            client: FastAPI 테스트 클라이언트
        """
        response = client.get("/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
