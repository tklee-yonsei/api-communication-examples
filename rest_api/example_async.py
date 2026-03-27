"""FastAPI 비동기 서버 사용 예제"""

from __future__ import annotations

import asyncio

from communication.jobs import (
    CalcJobHandler,
    EchoJobHandler,
    HashJobHandler,
    StatsJobHandler,
)
from communication.jobs.types import (
    CalcParams,
    EchoParams,
    HashParams,
    StatsParams,
)


async def main() -> None:
    """비동기 작업 처리 예제"""

    # 핸들러 인스턴스 생성
    echo_handler = EchoJobHandler()
    calc_handler = CalcJobHandler()
    stats_handler = StatsJobHandler()
    hash_handler = HashJobHandler()

    print("=== FastAPI 비동기 작업 예제 ===\n")

    # 1. Echo 작업
    print("1. Echo 작업:")
    echo_result = await echo_handler.execute(EchoParams(message="Hello FastAPI!"))
    print(f"   결과: {echo_result}\n")

    # 2. Calc 작업
    print("2. Calc 작업 (덧셈):")
    calc_result = await calc_handler.execute(CalcParams(op="add", a=10, b=5))
    print(f"   결과: {calc_result}\n")

    # 3. Stats 작업
    print("3. Stats 작업:")
    stats_result = await stats_handler.execute(StatsParams(values=[1, 2, 3, 4, 5]))
    print(f"   결과: {stats_result}\n")

    # 4. Hash 작업
    print("4. Hash 작업:")
    hash_result = await hash_handler.execute(
        HashParams.model_validate({"data": "test data", "key": "value"})
    )
    print(f"   결과: {hash_result}\n")

    # 5. 병렬 실행
    print("5. 여러 작업 병렬 실행:")
    results = await asyncio.gather(
        echo_handler.execute(EchoParams(message="Task 1")),
        calc_handler.execute(CalcParams(op="mul", a=3, b=4)),
        stats_handler.execute(StatsParams(values=[10, 20, 30])),
    )
    for i, r in enumerate(results, 1):
        print(f"   Task {i}: {r}")

    print("\n✓ 모든 작업 완료!")


if __name__ == "__main__":
    asyncio.run(main())
