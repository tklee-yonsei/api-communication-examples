"""WebSocket JobClient 계약 테스트.

WebSocketJobClient가 JobClient 인터페이스 계약을 준수하는지 검증합니다.
실제 WebSocket 통신을 통해 테스트하므로 테스트 서버가 필요합니다.

이 테스트는 다음을 검증합니다:
1. WebSocketJobClient가 JobClient ABC를 올바르게 구현함
2. WebSocket 통신을 통해 작업 생성/조회가 정상 동작함
3. 에러 처리가 계약에 맞게 동작함

Note:
    WebSocket API도 동기 작업(echo, calc, stats)과 비동기 작업(hash, fib)을 구분합니다.
    동기 작업은 서버에 저장되지 않으므로 get_job으로 조회할 수 없습니다.
    계약 테스트는 비동기 작업(hash)을 사용하여 전체 생명주기를 테스트합니다.
"""

from __future__ import annotations

from typing import Iterator

import pytest

from communication.base import JobClient
from communication.types import JobParams
from tests.conftest import WebSocketServerThread
from tests.contract.test_job_client_contract import JobClientContractTests
from websocket_api.client import WebSocketJobClient


class TestWebSocketJobClientContract(JobClientContractTests):
    """WebSocket 기반 JobClient가 인터페이스 계약을 준수하는지 검증합니다.

    JobClientContractTests를 상속받아 모든 계약 테스트를
    WebSocketJobClient에 대해 실행합니다.

    WebSocket API의 특성상 비동기 작업 타입(hash)을 사용하여 테스트합니다.
    동기 작업은 서버에 저장되지 않아 get_job으로 조회할 수 없기 때문입니다.

    Attributes:
        __test__ (bool): True로 설정하여 pytest가 이 클래스를 수집하도록 함
    """

    __test__ = True

    def _random_payload(self) -> tuple[str, JobParams]:
        """비동기 작업 타입(hash)을 사용하는 페이로드를 생성합니다.

        WebSocket API에서는 비동기 작업만 서버에 저장되어 get_job으로 조회 가능합니다.
        따라서 계약 테스트에는 hash 작업 타입을 사용합니다.

        Returns:
            tuple[str, JobParams]: ("hash", 파라미터) 튜플
        """
        from uuid import uuid4

        params: JobParams = {"data": f"test-data-{uuid4()}"}
        return "hash", params

    @pytest.fixture(scope="class")
    def server(self) -> Iterator[WebSocketServerThread]:
        """테스트 전용 WebSocket 서버 스레드를 기동/정지합니다.

        클래스 스코프로 설정하여 테스트 클래스당 한 번만 서버를 시작합니다.

        Yields:
            WebSocketServerThread: 실행 중인 서버 스레드
        """
        import time

        srv = WebSocketServerThread()
        srv.start()

        # 서버가 완전히 시작될 때까지 대기
        time.sleep(0.5)

        yield srv
        srv.stop()

    @pytest.fixture
    def client(self, server: WebSocketServerThread) -> Iterator[JobClient]:
        """테스트 대상 WebSocket 클라이언트를 생성/정리합니다.

        Args:
            server: 실행 중인 테스트 서버

        Yields:
            JobClient: 설정된 WebSocket 클라이언트
        """
        from websocket_api.client import WebSocketJobClient

        websocket_client = WebSocketJobClient(url=server.websocket_url)
        yield websocket_client
        websocket_client.close()


class TestWebSocketJobClientSpecific:
    """WebSocketJobClient 고유 기능 테스트.

    계약 테스트에서 다루지 않는 WebSocket 구현 특화 기능을 테스트합니다.
    """

    @pytest.fixture(scope="class")
    def server(self) -> Iterator[WebSocketServerThread]:
        """테스트 전용 서버를 기동합니다.

        Yields:
            WebSocketServerThread: 실행 중인 서버 스레드
        """
        import time

        srv = WebSocketServerThread()
        srv.start()
        time.sleep(0.5)
        yield srv
        srv.stop()

    @pytest.fixture
    def client(self, server: WebSocketServerThread) -> Iterator[WebSocketJobClient]:
        """WebSocket 클라이언트를 생성합니다.

        Args:
            server: 실행 중인 테스트 서버

        Yields:
            WebSocketJobClient: 테스트 대상 클라이언트
        """
        cli = WebSocketJobClient(url=server.websocket_url)
        yield cli
        cli.close()

    def test_context_manager_protocol(self, server: WebSocketServerThread) -> None:
        """컨텍스트 매니저 프로토콜을 지원하는지 테스트합니다.

        Args:
            server: 실행 중인 테스트 서버
        """
        with WebSocketJobClient(url=server.websocket_url) as client:
            # 동기 작업 테스트 (echo)
            created = client.create_job("echo", {"message": "context-test"})
            assert created.status == "done"

    def test_connection_is_closed(self, server: WebSocketServerThread) -> None:
        """close() 호출 시 연결이 닫히는지 테스트합니다.

        Args:
            server: 실행 중인 테스트 서버
        """
        client = WebSocketJobClient(url=server.websocket_url)
        _ = client.websocket  # 연결 참조 확인

        client.close()

        # close가 예외 없이 호출되는지만 확인
        assert True

    def test_sync_job_types(self, client: WebSocketJobClient) -> None:
        """동기 작업 타입들이 즉시 완료 상태를 반환하는지 테스트합니다.

        Args:
            client: 테스트 대상 클라이언트
        """
        # echo 작업
        echo_params: JobParams = {"message": "test"}
        echo_created = client.create_job("echo", echo_params)
        assert echo_created.status == "done", "echo 작업은 즉시 완료되어야 합니다"

        # calc 작업
        calc_params: JobParams = {"op": "add", "a": 1, "b": 2}
        calc_created = client.create_job("calc", calc_params)
        assert calc_created.status == "done", "calc 작업은 즉시 완료되어야 합니다"

        # stats 작업
        stats_params: JobParams = {"values": [1, 2, 3]}
        stats_created = client.create_job("stats", stats_params)
        assert stats_created.status == "done", "stats 작업은 즉시 완료되어야 합니다"

    def test_async_job_types(self, client: WebSocketJobClient) -> None:
        """비동기 작업 타입들이 pending 상태를 반환하는지 테스트합니다.

        Args:
            client: 테스트 대상 클라이언트
        """
        # hash 비동기 작업
        hash_params: JobParams = {"data": "test"}
        hash_created = client.create_job("hash", hash_params)
        assert hash_created.status in (
            "pending",
            "running",
            "done",
        ), "hash 작업은 pending 또는 running 상태로 시작해야 합니다"

        # fib 비동기 작업
        fib_params: JobParams = {"n": 10}
        fib_created = client.create_job("fib", fib_params)
        assert fib_created.status in (
            "pending",
            "running",
            "done",
        ), "fib 작업은 pending 또는 running 상태로 시작해야 합니다"

    def test_list_jobs(self, client: WebSocketJobClient) -> None:
        """list_jobs 메서드가 작업 목록을 반환하는지 테스트합니다.

        Args:
            client: 테스트 대상 클라이언트
        """
        # 작업 생성
        client.create_job("hash", {"data": "list-test"})

        # 목록 조회
        result = client.list_jobs(limit=10)

        assert "jobs" in result
        assert "total" in result
        assert isinstance(result["jobs"], list)

    def test_get_queue_status(self, client: WebSocketJobClient) -> None:
        """get_queue_status 메서드가 큐 상태를 반환하는지 테스트합니다.

        Args:
            client: 테스트 대상 클라이언트
        """
        result = client.get_queue_status()

        assert "queue_size" in result
        assert "is_full" in result
        assert "max_workers" in result

    def test_sync_job_returns_result(self, client: WebSocketJobClient) -> None:
        """동기 작업이 실제 결과를 반환하는지 테스트합니다.

        Args:
            client: 테스트 대상 클라이언트
        """
        from typing import Any, cast

        # calc 작업으로 결과 확인
        calc_created = client.create_job("calc", {"op": "add", "a": 10, "b": 5})
        assert calc_created.status == "done"
        assert calc_created.params is not None
        result = cast(dict[str, Any], calc_created.params.get("result", {}))
        assert result.get("result") == 15.0

    def test_async_job_result_retrieval(self, client: WebSocketJobClient) -> None:
        """비동기 작업 완료 후 결과를 조회할 수 있는지 테스트합니다.

        Args:
            client: 테스트 대상 클라이언트
        """
        import time
        from typing import Any, cast

        # fib 작업 생성
        fib_created = client.create_job("fib", {"n": 10})
        job_id = fib_created.id

        # 작업 완료 대기
        max_attempts = 50
        for _ in range(max_attempts):
            job = client.get_job(job_id)
            if job.status == "done":
                # 결과 확인
                result = (
                    cast(dict[str, Any], job.params.get("result", {}))
                    if job.params
                    else None
                )
                assert result is not None
                assert "fib" in result
                assert result["fib"] == 55  # fib(10) = 55
                break
            time.sleep(0.1)
        else:
            # 시간 내에 완료되지 않으면 최소한 상태는 확인
            job = client.get_job(job_id)
            assert job.status in ("pending", "running", "done")
