#!/usr/bin/env python3
"""gRPC 비동기 클라이언트 사용 예제.

이 스크립트는 gRPC 서버에 연결하여 동기/비동기 작업을 실행하는 방법을 보여줍니다.

사용법:
    # gRPC 서버가 실행 중인 상태에서
    python -m grpc_api.example_async

    # 또는 Docker Compose 사용
    docker compose --profile dev up -d
    python -m grpc_api.example_async
"""

import asyncio

from grpc_api.client import AsyncGrpcJobClient


async def main() -> None:
    """gRPC 클라이언트 예제를 실행합니다."""
    print("=== gRPC 비동기 클라이언트 예제 ===\n")

    async with AsyncGrpcJobClient(host="localhost", port=50051) as client:
        # 1. Echo 동기 작업
        print("1. Echo 작업 (동기)")
        record = await client.create_job("echo", {"message": "Hello, gRPC!"})
        print(f"   결과: {record}")
        print()

        # 2. Calc 동기 작업
        print("2. Calc 작업 (동기)")
        record = await client.create_job("calc", {"op": "mul", "a": 6, "b": 7})
        print(f"   결과: {record}")
        print()

        # 3. Stats 동기 작업
        print("3. Stats 작업 (동기)")
        record = await client.create_job(
            "stats", {"values": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]}
        )
        print(f"   결과: {record}")
        print()

        # 4. Hash 비동기 작업
        print("4. Hash 작업 (비동기)")
        record = await client.create_job("hash", {"data": "test data for hashing"})
        print(f"   작업 생성: {record}")

        # 작업 완료 대기
        for _ in range(10):
            await asyncio.sleep(0.5)
            status = await client.get_job(record.id)
            print(f"   상태: {status.status}")
            if status.status in ("done", "failed"):
                break
        print()

        # 5. Fib 비동기 작업
        print("5. Fib 작업 (비동기)")
        record = await client.create_job("fib", {"n": 20})
        print(f"   작업 생성: {record}")

        # 작업 완료 대기
        for _ in range(10):
            await asyncio.sleep(0.5)
            status = await client.get_job(record.id)
            print(f"   상태: {status.status}")
            if status.status in ("done", "failed"):
                break
        print()

        print("=== 예제 완료 ===")


if __name__ == "__main__":
    asyncio.run(main())
