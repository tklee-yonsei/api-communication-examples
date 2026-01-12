from __future__ import annotations

import threading
from typing import Iterator

import pytest
from werkzeug.serving import make_server

from communication.base import JobClient
from rest_api import RestJobClient, create_app
from tests.contract.test_job_client_contract import JobClientContractTests


class _ServerThread(threading.Thread):
    """테스트용 Flask 서버를 백그라운드 스레드로 실행합니다."""

    def __init__(self) -> None:
        self.app = create_app()
        self.server = make_server("127.0.0.1", 0, self.app)
        super().__init__(daemon=True)

    def run(self) -> None:  # pragma: no cover - 구동 코드만
        self.server.serve_forever()

    def stop(self) -> None:
        self.server.shutdown()
        self.join(timeout=2)

    @property
    def base_url(self) -> str:
        return f"http://{self.server.server_address[0]}:{self.server.server_port}"


class TestRestJobClient(JobClientContractTests):
    """REST 기반 JobClient가 인터페이스 준수 테스트를 통과하는지 검증합니다."""

    __test__ = True

    @pytest.fixture(scope="class")
    def server(self) -> Iterator[_ServerThread]:
        """테스트 전용 Flask 서버 스레드를 기동/정지합니다."""
        srv = _ServerThread()
        srv.start()
        yield srv
        srv.stop()

    @pytest.fixture
    def client(self, server: _ServerThread) -> Iterator[JobClient]:
        """테스트 대상 REST 클라이언트를 생성/정리합니다."""
        rest_client = RestJobClient(server.base_url)
        yield rest_client
        rest_client.close()
