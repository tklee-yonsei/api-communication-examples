"""gRPC API 서버 통합 테스트.

실제 gRPC 요청을 통해 gRPC API 서버의 RPC를 테스트합니다.

테스트 대상:
- 동기 RPC: Echo, Calc, Stats
- 비동기 RPC: CreateHashJob, CreateFibJob, GetJob
- 목록/상태 RPC: ListJobs, GetQueueStatus
- 스트리밍 RPC: WatchJobs
"""

from __future__ import annotations

import concurrent.futures
import time
from typing import Any, Iterator, Optional, cast

import pytest

from grpc_api.client import GrpcJobClient
from tests.conftest import GrpcServerThread


def _get_result(params: Optional[dict[str, object]]) -> Optional[dict[str, Any]]:
    """params에서 result를 추출합니다."""
    if params is None:
        return None
    result = params.get("result")
    if result is None:
        return None
    return cast(dict[str, Any], result)


class TestSyncRpcs:
    """동기 RPC 테스트.

    즉시 결과를 반환하는 동기 RPC를 테스트합니다.
    """

    @pytest.fixture(scope="class")
    def server(self) -> Iterator[GrpcServerThread]:
        """테스트용 gRPC 서버를 시작합니다.

        Yields:
            GrpcServerThread: 실행 중인 서버 스레드
        """
        srv = GrpcServerThread()
        srv.start()
        time.sleep(0.5)
        yield srv
        srv.stop()

    @pytest.fixture
    def client(self, server: GrpcServerThread) -> Iterator[GrpcJobClient]:
        """gRPC 클라이언트를 생성합니다.

        Args:
            server: 실행 중인 테스트 서버

        Yields:
            GrpcJobClient: 테스트 대상 클라이언트
        """
        cli = GrpcJobClient(host=server.host, port=server.port)
        yield cli
        cli.close()

    def test_echo_rpc(self, client: GrpcJobClient) -> None:
        """Echo RPC를 테스트합니다.

        입력 데이터가 그대로 반환되는지 확인합니다.

        Args:
            client: gRPC 클라이언트
        """
        created = client.create_job("echo", {"message": "hello", "count": "42"})

        assert created.status == "done"
        result = _get_result(created.params)
        assert result is not None
        assert "echo" in result

    def test_echo_empty_payload(self, client: GrpcJobClient) -> None:
        """빈 페이로드로 Echo RPC를 테스트합니다.

        Args:
            client: gRPC 클라이언트
        """
        created = client.create_job("echo", {})

        assert created.status == "done"

    def test_calc_add(self, client: GrpcJobClient) -> None:
        """Calc RPC 덧셈 연산을 테스트합니다.

        Args:
            client: gRPC 클라이언트
        """
        created = client.create_job("calc", {"op": "add", "a": 10.0, "b": 5.0})

        assert created.status == "done"
        result = _get_result(created.params)
        assert result is not None
        assert result["op"] == "add"
        assert result["result"] == 15.0

    def test_calc_subtract(self, client: GrpcJobClient) -> None:
        """Calc RPC 뺄셈 연산을 테스트합니다.

        Args:
            client: gRPC 클라이언트
        """
        created = client.create_job("calc", {"op": "sub", "a": 10.0, "b": 3.0})

        assert created.status == "done"
        result = _get_result(created.params)
        assert result is not None
        assert result["result"] == 7.0

    def test_calc_multiply(self, client: GrpcJobClient) -> None:
        """Calc RPC 곱셈 연산을 테스트합니다.

        Args:
            client: gRPC 클라이언트
        """
        created = client.create_job("calc", {"op": "mul", "a": 4.0, "b": 3.0})

        assert created.status == "done"
        result = _get_result(created.params)
        assert result is not None
        assert result["result"] == 12.0

    def test_calc_divide(self, client: GrpcJobClient) -> None:
        """Calc RPC 나눗셈 연산을 테스트합니다.

        Args:
            client: gRPC 클라이언트
        """
        created = client.create_job("calc", {"op": "div", "a": 20.0, "b": 4.0})

        assert created.status == "done"
        result = _get_result(created.params)
        assert result is not None
        assert result["result"] == 5.0

    def test_calc_divide_by_zero(self, client: GrpcJobClient) -> None:
        """Calc RPC 0으로 나누기 시 에러를 테스트합니다.

        Args:
            client: gRPC 클라이언트
        """
        created = client.create_job("calc", {"op": "div", "a": 10.0, "b": 0.0})

        assert created.status == "done"
        result = _get_result(created.params)
        assert result is not None
        assert "error" in result
        assert "division" in str(result["error"]).lower()

    def test_stats_basic(self, client: GrpcJobClient) -> None:
        """Stats RPC 기본 통계 계산을 테스트합니다.

        Args:
            client: gRPC 클라이언트
        """
        created = client.create_job("stats", {"values": [1, 2, 3, 4, 5]})

        assert created.status == "done"
        result = _get_result(created.params)
        assert result is not None
        assert result["count"] == 5
        assert result["min"] == 1
        assert result["max"] == 5
        assert result["sum"] == 15
        assert result["mean"] == 3.0
        assert result["median"] == 3.0

    def test_stats_empty_values(self, client: GrpcJobClient) -> None:
        """빈 리스트로 Stats RPC 호출 시 에러를 테스트합니다.

        Args:
            client: gRPC 클라이언트
        """
        created = client.create_job("stats", {"values": []})

        assert created.status == "done"
        result = _get_result(created.params)
        assert result is not None
        assert "error" in result


class TestAsyncRpcs:
    """비동기 RPC 테스트.

    비동기 작업 생성 및 조회를 테스트합니다.
    """

    @pytest.fixture(scope="class")
    def server(self) -> Iterator[GrpcServerThread]:
        """테스트용 gRPC 서버를 시작합니다.

        Yields:
            GrpcServerThread: 실행 중인 서버 스레드
        """
        srv = GrpcServerThread()
        srv.start()
        time.sleep(0.5)
        yield srv
        srv.stop()

    @pytest.fixture
    def client(self, server: GrpcServerThread) -> Iterator[GrpcJobClient]:
        """gRPC 클라이언트를 생성합니다.

        Args:
            server: 실행 중인 테스트 서버

        Yields:
            GrpcJobClient: 테스트 대상 클라이언트
        """
        cli = GrpcJobClient(host=server.host, port=server.port)
        yield cli
        cli.close()

    def test_hash_job_creation(self, client: GrpcJobClient) -> None:
        """CreateHashJob RPC 작업 생성을 테스트합니다.

        Args:
            client: gRPC 클라이언트
        """
        created = client.create_job("hash", {"data": "test-data"})

        assert created.id != ""
        assert created.status in ("pending", "running", "done")

    def test_fib_job_creation(self, client: GrpcJobClient) -> None:
        """CreateFibJob RPC 작업 생성을 테스트합니다.

        Args:
            client: gRPC 클라이언트
        """
        created = client.create_job("fib", {"n": 10})

        assert created.id != ""
        assert created.status in ("pending", "running", "done")

    def test_get_job_not_found(self, client: GrpcJobClient) -> None:
        """존재하지 않는 작업 조회 시 예외를 테스트합니다.

        Args:
            client: gRPC 클라이언트
        """
        from communication.base import JobNotFoundError

        with pytest.raises(JobNotFoundError):
            client.get_job("non-existent-job-id")

    def test_list_jobs(self, client: GrpcJobClient) -> None:
        """ListJobs RPC를 테스트합니다.

        Args:
            client: gRPC 클라이언트
        """
        # 작업 생성
        client.create_job("hash", {"data": "list-test"})

        # 목록 조회
        result = client.list_jobs(limit=10)

        assert "jobs" in result
        assert "total" in result

    def test_queue_status(self, client: GrpcJobClient) -> None:
        """GetQueueStatus RPC를 테스트합니다.

        Args:
            client: gRPC 클라이언트
        """
        result = client.get_queue_status()

        assert "queue_size" in result
        assert "is_full" in result
        assert "max_workers" in result


class TestGrpcServerIntegration:
    """실제 gRPC 서버 통합 테스트.

    실제 서버를 띄우고 gRPC 요청을 보내 전체 통합을 테스트합니다.
    """

    @pytest.fixture(scope="class")
    def server(self) -> Iterator[GrpcServerThread]:
        """테스트용 서버를 시작합니다.

        Yields:
            GrpcServerThread: 실행 중인 서버 스레드
        """
        srv = GrpcServerThread()
        srv.start()
        time.sleep(0.5)
        yield srv
        srv.stop()

    @pytest.fixture
    def client(self, server: GrpcServerThread) -> Iterator[GrpcJobClient]:
        """gRPC 클라이언트를 생성합니다.

        Args:
            server: 실행 중인 테스트 서버

        Yields:
            GrpcJobClient: 테스트 대상 클라이언트
        """
        cli = GrpcJobClient(host=server.host, port=server.port)
        yield cli
        cli.close()

    def test_hash_job_lifecycle(self, client: GrpcJobClient) -> None:
        """해시 작업의 전체 생명주기를 테스트합니다.

        1. 작업 생성
        2. 작업 상태 조회
        3. 완료될 때까지 대기 (최대 10초)
        4. 결과 확인

        Args:
            client: gRPC 클라이언트
        """
        # 작업 생성
        created = client.create_job("hash", {"data": "lifecycle-test"})
        job_id = created.id
        assert job_id != ""

        # 작업 완료 대기 (폴링)
        max_attempts = 100  # 최대 10초 대기
        job = None
        for _ in range(max_attempts):
            job = client.get_job(job_id)
            if job.status in ("done", "failed"):
                break
            time.sleep(0.1)

        # 결과 확인
        assert job is not None
        assert job.status in ("pending", "running", "done")
        assert job.type == "hash"

        # 완료 시 결과 확인
        if job.status == "done":
            result = _get_result(job.params)
            assert result is not None
            assert "digest" in result

    def test_fib_job_lifecycle(self, client: GrpcJobClient) -> None:
        """피보나치 작업의 전체 생명주기를 테스트합니다.

        Args:
            client: gRPC 클라이언트
        """
        # 작업 생성
        created = client.create_job("fib", {"n": 15})
        job_id = created.id
        assert job_id != ""

        # 작업 완료 대기
        max_attempts = 100  # 최대 10초 대기
        job = None
        for _ in range(max_attempts):
            job = client.get_job(job_id)
            if job.status in ("done", "failed"):
                break
            time.sleep(0.1)

        # 결과 확인
        assert job is not None
        assert job.status in ("pending", "running", "done")
        assert job.type == "fib"

        # 완료 시 결과 확인
        if job.status == "done":
            result = _get_result(job.params)
            assert result is not None
            assert "fib" in result
            assert result["fib"] == 610  # fib(15) = 610

    def test_concurrent_requests(self, server: GrpcServerThread) -> None:
        """동시 요청 처리를 테스트합니다.

        Args:
            server: 실행 중인 테스트 서버
        """

        def make_request(i: int) -> tuple[int, str]:
            with GrpcJobClient(host=server.host, port=server.port) as client:
                created = client.create_job(
                    "echo", {"index": str(i), "message": f"concurrent-{i}"}
                )
                return i, created.status

        # 10개의 동시 요청
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, i) for i in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # 모든 요청이 성공했는지 확인
        assert len(results) == 10
        for _, status in results:
            assert status == "done"

    def test_multiple_async_jobs(self, client: GrpcJobClient) -> None:
        """여러 비동기 작업을 동시에 생성하고 추적할 수 있는지 테스트합니다.

        Args:
            client: gRPC 클라이언트
        """
        job_ids = []

        # 여러 작업 생성
        for i in range(5):
            created = client.create_job("hash", {"data": f"multi-{i}"})
            job_ids.append(created.id)

        # 모든 작업 ID가 고유한지 확인
        assert len(set(job_ids)) == 5

        # 모든 작업 상태 조회 가능한지 확인
        for job_id in job_ids:
            job = client.get_job(job_id)
            assert job.id == job_id
            assert job.status in ("pending", "running", "done", "failed")
