"""pytest 공통 fixtures 및 설정.

이 모듈은 모든 테스트에서 공유되는 fixture들을 정의합니다:
- REST API 서버 fixture
- 클라이언트 fixture
- 테스트 데이터 fixture
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Iterator

import pytest
import uvicorn

from rest_api import RestJobClient, create_app


class _UvicornServer(uvicorn.Server):
    """테스트용 Uvicorn 서버.

    백그라운드 스레드에서 실행되며, 시그널 핸들러를 설치하지 않습니다.
    """

    def install_signal_handlers(self) -> None:
        """테스트 환경에서는 시그널 핸들러를 설치하지 않습니다."""
        pass


class ServerThread(threading.Thread):
    """FastAPI 서버를 백그라운드 스레드에서 실행하는 헬퍼 클래스.

    Attributes:
        app: FastAPI 애플리케이션 인스턴스
        server: Uvicorn 서버 인스턴스
    """

    def __init__(self) -> None:
        """서버 스레드를 초기화합니다."""
        self.app = create_app()

        # 동적으로 포트 할당을 위해 0번 포트 사용
        config = uvicorn.Config(
            self.app,
            host="127.0.0.1",
            port=0,  # OS가 자동으로 사용 가능한 포트 할당
            log_level="error",
        )
        self.server = _UvicornServer(config=config)
        super().__init__(daemon=True)

    def run(self) -> None:  # pragma: no cover - 스레드 실행 코드
        """서버를 실행합니다."""
        asyncio.run(self.server.serve())

    def stop(self) -> None:
        """서버를 중지합니다."""
        self.server.should_exit = True
        self.join(timeout=5)

    @property
    def base_url(self) -> str:
        """서버의 베이스 URL을 반환합니다.

        Returns:
            str: http://host:port 형식의 URL
        """
        # 서버가 시작될 때까지 대기
        for _ in range(50):  # 최대 5초 대기
            if self.server.started:
                break
            time.sleep(0.1)

        if self.server.servers:
            server = self.server.servers[0]
            host, port = server.sockets[0].getsockname()[:2]
            return f"http://{host}:{port}"
        return "http://127.0.0.1:8000"


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """세션 범위의 이벤트 루프를 제공합니다.

    Yields:
        asyncio.AbstractEventLoop: 테스트용 이벤트 루프
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def rest_server() -> Iterator[ServerThread]:
    """모듈 범위의 테스트용 REST API 서버를 제공합니다.

    Yields:
        ServerThread: 실행 중인 서버 스레드
    """
    srv = ServerThread()
    srv.start()

    # 서버가 완전히 시작될 때까지 대기
    time.sleep(0.5)

    yield srv
    srv.stop()


@pytest.fixture
def rest_client(rest_server: ServerThread) -> Iterator[RestJobClient]:
    """테스트용 REST 클라이언트를 생성합니다.

    Args:
        rest_server: 실행 중인 서버 fixture

    Yields:
        RestJobClient: 설정된 REST 클라이언트
    """
    client = RestJobClient(rest_server.base_url)
    yield client
    client.close()


@pytest.fixture
def base_url(rest_server: ServerThread) -> str:
    """서버의 베이스 URL을 반환합니다.

    Args:
        rest_server: 실행 중인 서버 fixture

    Returns:
        str: 서버의 베이스 URL
    """
    return rest_server.base_url
