"""JobQueue 단위 테스트.

asyncio 기반 작업 큐의 기능을 테스트합니다:
- 작업 제출 및 실행
- 워커 관리
- 큐 크기 제한 (백프레셔)

테스트 대상:
- Job: 비동기 작업 객체
- JobQueue: 작업 스케줄러

Note:
    실제 비동기 워커 테스트는 통합 테스트에서 수행합니다.
    여기서는 동기적으로 테스트 가능한 부분만 다룹니다.
"""

from __future__ import annotations

from typing import Any

import pytest

from rest_api.core.job_queue import Job, JobQueue
from rest_api.core.jobs.types import BaseError


class MockJobPayload:
    """테스트용 가짜 JobPayload 클래스.

    Attributes:
        id: 작업 ID
        type: 작업 타입
        params: 작업 파라미터
        status: 작업 상태
        result: 작업 결과
    """

    def __init__(
        self,
        id: str,
        type: str,
        params: Any,
        status: str = "pending",
        result: Any = None,
    ) -> None:
        """MockJobPayload를 초기화합니다."""
        self.id = id
        self.type = type
        self.params = params
        self.status = status
        self.result = result


class MockParams:
    """테스트용 가짜 파라미터 클래스."""

    def __init__(self, **kwargs: Any) -> None:
        """MockParams를 초기화합니다."""
        self._data = kwargs

    def model_dump(self) -> dict[str, Any]:
        """Pydantic model_dump 호환 메서드."""
        return self._data


class MockResult:
    """테스트용 가짜 결과 클래스."""

    def __init__(self, **kwargs: Any) -> None:
        """MockResult를 초기화합니다."""
        self._data = kwargs

    def model_dump(self) -> dict[str, Any]:
        """Pydantic model_dump 호환 메서드."""
        return self._data


class MockHandler:
    """테스트용 가짜 핸들러 클래스."""

    async def execute(self, params: Any) -> MockResult:
        """테스트용 실행 메서드.

        Args:
            params: 작업 파라미터

        Returns:
            MockResult: 가짜 결과
        """
        return MockResult(success=True)


class FailingHandler:
    """실패하는 테스트용 핸들러 클래스."""

    async def execute(self, params: Any) -> MockResult:
        """항상 예외를 발생시킵니다.

        Args:
            params: 작업 파라미터

        Raises:
            RuntimeError: 항상 발생
        """
        raise RuntimeError("Intentional failure for testing")


class TestJob:
    """Job 클래스 테스트.

    Job은 비동기로 실행되는 작업 객체입니다.
    핸들러를 통해 작업을 실행하고 결과를 store에 저장합니다.
    """

    @pytest.mark.asyncio
    async def test_job_execute_success(self) -> None:
        """작업이 성공적으로 실행되고 결과가 저장되는지 테스트합니다."""
        # Given
        job_id = "test-job-1"
        store: dict[str, MockJobPayload] = {}
        store[job_id] = MockJobPayload(
            id=job_id,
            type="test",
            params=MockParams(value="test"),
            status="pending",
        )

        job = Job(
            job_id=job_id,
            job_type="test",
            handler=MockHandler,  # type: ignore
            store=store,  # type: ignore
        )

        # When
        await job.execute()

        # Then
        assert store[job_id].status == "done"
        assert store[job_id].result is not None

    @pytest.mark.asyncio
    async def test_job_execute_failure(self) -> None:
        """작업 실패 시 상태가 failed로 변경되는지 테스트합니다."""
        # Given
        job_id = "test-job-2"
        store: dict[str, MockJobPayload] = {}
        store[job_id] = MockJobPayload(
            id=job_id,
            type="test",
            params=MockParams(value="test"),
            status="pending",
        )

        job = Job(
            job_id=job_id,
            job_type="test",
            handler=FailingHandler,  # type: ignore
            store=store,  # type: ignore
        )

        # When
        await job.execute()

        # Then
        assert store[job_id].status == "failed"
        assert isinstance(store[job_id].result, BaseError)
        assert "Intentional failure" in store[job_id].result.error

    @pytest.mark.asyncio
    async def test_job_not_in_store(self) -> None:
        """store에 작업이 없을 때 안전하게 처리되는지 테스트합니다."""
        # Given
        job_id = "non-existent-job"
        store: dict[str, MockJobPayload] = {}  # 빈 스토어

        job = Job(
            job_id=job_id,
            job_type="test",
            handler=MockHandler,  # type: ignore
            store=store,  # type: ignore
        )

        # When / Then - 예외 없이 종료되어야 함
        await job.execute()


class TestJobQueue:
    """JobQueue 클래스 테스트.

    JobQueue는 asyncio 기반 비동기 작업 스케줄러입니다.
    """

    def test_queue_initialization(self) -> None:
        """큐가 올바르게 초기화되는지 테스트합니다."""
        queue = JobQueue(max_workers=4, max_queue_size=100)

        assert queue.max_workers == 4
        assert queue.get_queue_size() == 0
        assert queue.is_full() is False

    def test_queue_is_full_check(self) -> None:
        """큐의 is_full 상태 체크를 테스트합니다."""
        queue = JobQueue(max_workers=2, max_queue_size=5)

        assert queue.is_full() is False

    def test_queue_get_size_empty(self) -> None:
        """빈 큐의 크기가 0인지 테스트합니다."""
        queue = JobQueue(max_workers=2, max_queue_size=10)

        assert queue.get_queue_size() == 0

    @pytest.mark.asyncio
    async def test_queue_submit_returns_true(self) -> None:
        """submit()이 성공 시 True를 반환하는지 테스트합니다."""
        queue = JobQueue(max_workers=1, max_queue_size=10)

        job_id = "test-job"
        store: dict[str, MockJobPayload] = {}
        store[job_id] = MockJobPayload(
            id=job_id,
            type="test",
            params=MockParams(value="test"),
            status="pending",
        )

        job = Job(
            job_id=job_id,
            job_type="test",
            handler=MockHandler,  # type: ignore
            store=store,  # type: ignore
        )

        # 큐에만 추가 (워커 시작 안함)
        result = await queue.submit(job)

        assert result is True
        assert queue.get_queue_size() == 1

    @pytest.mark.asyncio
    async def test_queue_submit_full_returns_false(self) -> None:
        """큐가 가득 찼을 때 submit()이 False를 반환하는지 테스트합니다."""
        queue = JobQueue(max_workers=1, max_queue_size=1)

        store: dict[str, MockJobPayload] = {}

        # 첫 번째 작업
        job1_id = "job-1"
        store[job1_id] = MockJobPayload(
            id=job1_id,
            type="test",
            params=MockParams(value="test"),
            status="pending",
        )
        job1 = Job(
            job_id=job1_id,
            job_type="test",
            handler=MockHandler,  # type: ignore
            store=store,  # type: ignore
        )

        # 두 번째 작업
        job2_id = "job-2"
        store[job2_id] = MockJobPayload(
            id=job2_id,
            type="test",
            params=MockParams(value="test"),
            status="pending",
        )
        job2 = Job(
            job_id=job2_id,
            job_type="test",
            handler=MockHandler,  # type: ignore
            store=store,  # type: ignore
        )

        # 첫 번째 작업 제출 성공
        result1 = await queue.submit(job1)
        assert result1 is True

        # 두 번째 작업 제출 실패 (큐가 가득 참)
        result2 = await queue.submit(job2)
        assert result2 is False
