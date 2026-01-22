"""작업 상태 변경 구독 관리."""

from __future__ import annotations

import asyncio

from grpc_api.protos import jobs_pb2


class WatcherManager:
    """작업 상태 변경을 구독하는 클라이언트를 관리합니다."""

    def __init__(self) -> None:
        self._watchers: list[asyncio.Queue[jobs_pb2.JobStatus]] = []
        self._lock = asyncio.Lock()

    async def add_watcher(self) -> asyncio.Queue[jobs_pb2.JobStatus]:
        """새로운 watcher를 추가합니다."""
        queue: asyncio.Queue[jobs_pb2.JobStatus] = asyncio.Queue()
        async with self._lock:
            self._watchers.append(queue)
        return queue

    async def remove_watcher(self, queue: asyncio.Queue[jobs_pb2.JobStatus]) -> None:
        """watcher를 제거합니다."""
        async with self._lock:
            if queue in self._watchers:
                self._watchers.remove(queue)

    async def broadcast(self, job_status: jobs_pb2.JobStatus) -> None:
        """모든 watcher에게 작업 상태를 브로드캐스트합니다."""
        async with self._lock:
            for queue in self._watchers:
                try:
                    await queue.put(job_status)
                except Exception:
                    pass
