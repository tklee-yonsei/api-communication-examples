from __future__ import annotations

from typing import Any, Mapping
from uuid import uuid4

import pytest

from communication.base import JobClient, JobNotFoundError, JobRecord
from tests.contract.test_job_client_contract import JobClientContractTests


class InMemoryJobClient(JobClient):
    """테스트용 간단 인메모리 구현"""

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}

    def create_job(self, job_type: str, params: Mapping[str, Any]) -> JobRecord:
        job_id = str(uuid4())
        record = JobRecord(
            id=job_id, type=job_type, params=dict(params), status="pending"
        )
        self._jobs[job_id] = record
        return record

    def get_job(self, job_id: str) -> JobRecord:
        record = self._jobs.get(job_id)
        if record is None:
            raise JobNotFoundError(f"Job {job_id} not found")
        return record


class TestInMemoryJobClient(JobClientContractTests):
    """인메모리 구현이 인터페이스 준수 테스트를 통과하는지 검증"""

    __test__ = True

    @pytest.fixture
    def client(self) -> JobClient:
        return InMemoryJobClient()
