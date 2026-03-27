"""통합 작업 큐 - asyncio 기반 비동기 작업 스케줄러."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional, Protocol

from pydantic import BaseModel

from communication.jobs.types import JobResult, BaseError

# Job 완료 시 호출될 콜백 타입
OnCompleteCallback = Callable[[str], Awaitable[None]]


class JobHandler(Protocol):
    """AsyncJobHandler 호환 프로토콜.

    모든 작업 핸들러는 이 프로토콜을 구현해야 합니다.
    params는 Pydantic BaseModel을 상속받은 타입입니다.
    """

    async def execute(self, params: BaseModel) -> JobResult: ...


class JobPayloadProtocol(Protocol):
    """JobPayload가 가져야 할 최소한의 속성을 정의하는 Protocol.

    store에 저장되는 객체는 이 Protocol을 만족해야 합니다.
    """

    params: BaseModel
    status: str
    result: Optional[object]


logger = logging.getLogger(__name__)


class Job:
    """큐에 들어갈 비동기 작업 객체."""

    def __init__(
        self,
        job_id: str,
        job_type: str,
        handler: type[Any],  # AsyncJobHandler의 모든 구현체를 받을 수 있도록
        store: dict[str, Any],  # AnyJobPayload를 포함한 모든 JobPayload 타입
        on_complete: Optional[OnCompleteCallback] = None,  # 완료 콜백
    ) -> None:
        self.job_id = job_id
        self.job_type = job_type
        self.handler = handler
        self.store = store  # 결과를 저장할 공유 스토어
        self.on_complete = on_complete  # 완료 시 호출될 콜백

    async def execute(self) -> None:
        """작업을 비동기로 실행하고 결과를 store에 저장합니다."""
        try:
            logger.info(f"Processing job {self.job_id} (type: {self.job_type})")

            # store에서 params 가져오기
            if self.job_id not in self.store:
                logger.error(f"Job {self.job_id} not found in store")
                return

            job_payload = self.store[self.job_id]
            params = job_payload.params

            # 핸들러 클래스를 실행 시점에 인스턴스화하여 실행
            handler_instance = self.handler()
            result = await handler_instance.execute(params)

            # 결과 저장 (Pydantic 모델인 경우 dict로 변환)
            if self.job_id in self.store:
                job_payload = self.store[self.job_id]
                job_payload.status = "done"
                # Pydantic 모델인 경우 model_dump()로 변환, 아니면 그대로 사용
                if hasattr(result, "model_dump"):
                    job_payload.result = result.model_dump()
                else:
                    job_payload.result = result

            logger.info(f"Job {self.job_id} completed successfully")

            # 완료 콜백 호출
            if self.on_complete is not None:
                try:
                    await self.on_complete(self.job_id)
                except Exception as cb_err:
                    logger.warning(
                        f"Job {self.job_id} on_complete callback error: {cb_err}"
                    )

        except Exception as e:
            logger.error(f"Job {self.job_id} failed: {e}")
            if self.job_id in self.store:
                job_payload = self.store[self.job_id]
                job_payload.status = "failed"
                job_payload.result = BaseError(error=str(e))

            # 실패 시에도 콜백 호출 (상태 업데이트 알림)
            if self.on_complete is not None:
                try:
                    await self.on_complete(self.job_id)
                except Exception as cb_err:
                    logger.warning(
                        f"Job {self.job_id} on_complete callback error: {cb_err}"
                    )


class JobQueue:
    """통합 작업 큐 - asyncio 기반 비동기 작업 스케줄링.

    특징:
    - asyncio.Queue 사용
    - asyncio.Task로 워커 관리
    - 동시 실행 작업 수 제한
    - 큐 크기 제한으로 백프레셔 제공
    """

    def __init__(self, max_workers: int = 4, max_queue_size: int = 100) -> None:
        """작업 큐를 초기화합니다.

        Args:
            max_workers: 동시에 실행할 최대 워커 수
            max_queue_size: 큐에 대기할 수 있는 최대 작업 수
        """
        self.queue: asyncio.Queue[Optional[Job]] = asyncio.Queue(maxsize=max_queue_size)
        self.max_workers = max_workers
        self._shutdown = False
        self._worker_tasks: list[asyncio.Task[None]] = []
        self._semaphore = asyncio.Semaphore(max_workers)

        logger.info(
            f"JobQueue initialized: {max_workers} workers, queue size {max_queue_size}"
        )

    async def start(self) -> None:
        """워커 태스크들을 시작합니다."""
        if not self._worker_tasks:
            self._shutdown = False
            for i in range(self.max_workers):
                task = asyncio.create_task(self._worker(i), name=f"job-worker-{i}")
                self._worker_tasks.append(task)
            logger.info(f"JobQueue started with {self.max_workers} workers")

    async def _worker(self, worker_id: int) -> None:
        """큐에서 작업을 가져와 실행하는 워커 루프."""
        logger.info(f"Worker {worker_id} started")
        while not self._shutdown:
            try:
                # 큐에서 작업 가져오기 (타임아웃 1초)
                job = await asyncio.wait_for(self.queue.get(), timeout=1.0)

                if job is None:  # 종료 신호
                    self.queue.task_done()
                    break

                # 작업 실행
                async with self._semaphore:
                    await job.execute()

                self.queue.task_done()

            except asyncio.TimeoutError:
                # 타임아웃 - 계속 대기
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")

        logger.info(f"Worker {worker_id} stopped")

    async def submit(self, job: Job) -> bool:
        """작업을 큐에 추가합니다.

        Args:
            job: 실행할 작업

        Returns:
            bool: 큐에 성공적으로 추가되면 True
        """
        try:
            self.queue.put_nowait(job)
            logger.debug(
                f"Job {job.job_id} added to queue (size: {self.queue.qsize()})"
            )
            return True
        except asyncio.QueueFull:
            logger.warning(f"Queue is full, cannot add job {job.job_id}")
            return False
        except Exception as e:
            logger.warning(f"Failed to add job to queue: {e}")
            return False

    async def shutdown(self, wait: bool = True) -> None:
        """작업 큐를 종료합니다.

        Args:
            wait: 진행 중인 작업이 완료될 때까지 대기할지 여부
        """
        logger.info("Shutting down JobQueue...")
        self._shutdown = True

        # 모든 워커에게 종료 신호 전송
        for _ in self._worker_tasks:
            try:
                await self.queue.put(None)
            except Exception:
                pass

        if wait:
            # 모든 워커 태스크가 완료될 때까지 대기
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        else:
            # 즉시 취소
            for task in self._worker_tasks:
                task.cancel()

        self._worker_tasks.clear()
        logger.info("JobQueue shut down")

    def get_queue_size(self) -> int:
        """현재 큐에 대기 중인 작업 수를 반환합니다."""
        return self.queue.qsize()

    def is_full(self) -> bool:
        """큐가 가득 찼는지 확인합니다."""
        return self.queue.full()


# 전역 작업 큐 인스턴스
_job_queue: Optional[JobQueue] = None


async def get_job_queue() -> JobQueue:
    """전역 작업 큐 인스턴스를 가져옵니다."""
    global _job_queue
    if _job_queue is None:
        _job_queue = JobQueue(max_workers=4, max_queue_size=100)
        await _job_queue.start()
    return _job_queue


async def shutdown_job_queue() -> None:
    """전역 작업 큐를 종료합니다."""
    global _job_queue
    if _job_queue is not None:
        await _job_queue.shutdown()
        _job_queue = None
