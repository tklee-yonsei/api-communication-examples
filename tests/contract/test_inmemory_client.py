"""InMemory JobClient 구현 및 계약 테스트.

이 모듈은 테스트용 간단한 인메모리 JobClient 구현과
해당 구현이 JobClient 계약을 준수하는지 검증하는 테스트를 포함합니다.

InMemoryJobClient는 실제 네트워크 통신 없이 메모리에서
작업을 관리하므로 빠른 테스트에 적합합니다.
"""

from __future__ import annotations

from typing import Iterator
from uuid import uuid4

import pytest

from communication.base import JobClient, JobNotFoundError, JobRecord
from communication.types import JobParams
from tests.contract.test_job_client_contract import JobClientContractTests


class InMemoryJobClient(JobClient):
    """테스트용 간단 인메모리 JobClient 구현.

    네트워크 통신 없이 메모리에서 작업을 관리합니다.
    주로 계약 테스트의 참조 구현으로 사용됩니다.

    Attributes:
        jobs (dict[str, JobRecord]): 작업 ID를 키로 하는 작업 저장소
    """

    def __init__(self) -> None:
        """InMemoryJobClient를 초기화합니다.

        빈 작업 저장소로 시작합니다.
        """
        self.jobs: dict[str, JobRecord] = {}

    def create_job(self, job_type: str, params: JobParams) -> JobRecord:
        """새 작업을 생성하고 저장합니다.

        UUID를 기반으로 고유한 작업 ID를 생성하고,
        'pending' 상태의 JobRecord를 생성하여 저장합니다.

        Args:
            job_type: 작업 종류 식별자
            params: 작업 실행에 필요한 파라미터

        Returns:
            JobRecord: 생성된 작업 기록
        """
        job_id = str(uuid4())
        record = JobRecord(id=job_id, type=job_type, params=params, status="pending")
        self.jobs[job_id] = record
        return record

    def get_job(self, job_id: str) -> JobRecord:
        """작업 ID로 작업을 조회합니다.

        Args:
            job_id: 조회할 작업의 식별자

        Returns:
            JobRecord: 요청한 작업의 현재 기록

        Raises:
            JobNotFoundError: 해당 ID의 작업이 없을 경우
        """
        record = self.jobs.get(job_id)
        if record is None:
            raise JobNotFoundError(f"Job {job_id} not found")
        return record

    def close(self) -> None:
        """리소스를 정리합니다.

        인메모리 구현에서는 특별히 정리할 리소스가 없습니다.
        """
        pass


class TestInMemoryJobClient(JobClientContractTests):
    """인메모리 구현이 JobClient 인터페이스 계약을 준수하는지 검증합니다.

    JobClientContractTests를 상속받아 모든 계약 테스트를
    InMemoryJobClient에 대해 실행합니다.

    Attributes:
        __test__ (bool): True로 설정하여 pytest가 이 클래스를 수집하도록 함
    """

    __test__ = True

    @pytest.fixture
    def client(self) -> Iterator[JobClient]:
        """InMemoryJobClient 인스턴스를 생성합니다.

        Yields:
            JobClient: 테스트용 인메모리 클라이언트

        Note:
            컨텍스트 매니저 패턴 테스트를 위해 Iterator로 반환합니다.
        """
        cli = InMemoryJobClient()
        yield cli
        cli.close()


class TestInMemoryJobClientSpecific:
    """InMemoryJobClient 고유 기능 테스트.

    계약 테스트에서 다루지 않는 인메모리 구현 특화 기능을 테스트합니다.
    """

    @pytest.fixture
    def client(self) -> InMemoryJobClient:
        """테스트용 클라이언트를 생성합니다.

        Returns:
            InMemoryJobClient: 새 인스턴스
        """
        return InMemoryJobClient()

    def test_initial_storage_is_empty(self, client: InMemoryJobClient) -> None:
        """초기 상태에서 저장소가 비어있는지 테스트합니다.

        Args:
            client: 테스트 대상 클라이언트
        """
        assert len(client.jobs) == 0

    def test_job_is_stored_after_create(self, client: InMemoryJobClient) -> None:
        """작업 생성 후 내부 저장소에 저장되는지 테스트합니다.

        Args:
            client: 테스트 대상 클라이언트
        """
        created = client.create_job("test", {"key": "value"})

        assert created.id in client.jobs
        assert client.jobs[created.id] == created

    def test_context_manager_protocol(self) -> None:
        """컨텍스트 매니저 프로토콜을 지원하는지 테스트합니다."""
        with InMemoryJobClient() as client:
            created = client.create_job("test", {"data": "context-test"})
            fetched = client.get_job(created.id)
            assert fetched.id == created.id

    def test_close_is_idempotent(self, client: InMemoryJobClient) -> None:
        """close()를 여러 번 호출해도 안전한지 테스트합니다.

        Args:
            client: 테스트 대상 클라이언트
        """
        # 여러 번 close 호출해도 예외가 발생하지 않아야 함
        client.close()
        client.close()
        client.close()
