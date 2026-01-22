"""gRPC 서버 래퍼 및 실행 함수."""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false

from __future__ import annotations

import asyncio
import logging
from concurrent import futures
from typing import Optional

import grpc

from grpc_api.protos import jobs_pb2_grpc
from grpc_api.server.servicer import JobServiceServicer

logger = logging.getLogger(__name__)


class GrpcServer:
    """gRPC 서버 래퍼 클래스."""

    def __init__(self, host: str = "[::]", port: int = 50051) -> None:
        """서버를 초기화합니다.

        Args:
            host: 서버가 바인딩할 호스트 (기본값: [::] 모든 인터페이스)
            port: 서버가 수신할 포트 번호
        """
        self.host = host
        self.port = port
        self.server: Optional[grpc.aio.Server] = None
        self.servicer = JobServiceServicer()

    async def start(self) -> None:
        """서버를 시작합니다."""
        self.server = grpc.aio.server(
            futures.ThreadPoolExecutor(max_workers=10),
            options=[
                ("grpc.max_send_message_length", 50 * 1024 * 1024),
                ("grpc.max_receive_message_length", 50 * 1024 * 1024),
            ],
        )
        jobs_pb2_grpc.add_JobServiceServicer_to_server(self.servicer, self.server)
        self.server.add_insecure_port(f"{self.host}:{self.port}")

        await self.server.start()
        logger.info(f"gRPC server started on port {self.port}")

    async def stop(self, grace: float = 5.0) -> None:
        """서버를 종료합니다.

        Args:
            grace: 정상 종료 대기 시간(초)
        """
        if self.server is not None:
            await self.server.stop(grace)
            logger.info("gRPC server stopped")

    async def wait_for_termination(self) -> None:
        """서버가 종료될 때까지 대기합니다."""
        if self.server is not None:
            await self.server.wait_for_termination()


async def serve(port: int = 50051) -> None:
    """gRPC 서버를 실행합니다.

    Args:
        port: 서버가 수신할 포트 번호
    """
    server = GrpcServer(port=port)
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop()


def run_server(port: int = 50051) -> None:
    """동기적으로 서버를 실행합니다.

    Args:
        port: 서버가 수신할 포트 번호
    """
    asyncio.run(serve(port))


if __name__ == "__main__":
    run_server(port=50051)
