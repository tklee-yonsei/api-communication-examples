"""gRPC 서버 실행 진입점.

이 모듈은 `python -m grpc_api.server`로 서버를 실행할 수 있도록 합니다.
"""

from __future__ import annotations

from grpc_api.server.server import run_server

if __name__ == "__main__":
    run_server(port=50051)
