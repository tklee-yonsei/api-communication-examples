from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping, Tuple
from uuid import uuid4

import pytest

from communication.base import JobClient, JobNotFoundError


class JobClientContractTests(ABC):
    """모든 JobClient 구현체가 따라야 할 인터페이스 준수 테스트 모음입니다."""

    __test__ = False  # 베이스 클래스는 수집 대상이 아님

    @pytest.fixture
    @abstractmethod
    def client(self) -> JobClient:
        """구체 클라이언트를 반환하는 픽스처입니다."""

    def _random_payload(self) -> Tuple[str, Mapping[str, str]]:
        """임의의 작업 타입/파라미터 페어를 생성합니다."""
        job_type = f"job-{uuid4()}"
        params = {"payload": f"data-{uuid4()}"}
        return job_type, params

    def test_create_and_get_job(self, client: JobClient) -> None:
        """작업 생성 후 동일 ID로 조회하면 동일 데이터가 반환되는지 검증합니다."""
        job_type, params = self._random_payload()

        created = client.create_job(job_type, params)
        fetched = client.get_job(created.id)

        assert fetched.id == created.id
        assert fetched.type == job_type
        assert fetched.params == params
        assert fetched.status == created.status

    def test_missing_job_raises(self, client: JobClient) -> None:
        """존재하지 않는 작업을 조회할 때 JobNotFoundError가 발생하는지 검증합니다."""
        with pytest.raises(JobNotFoundError):
            client.get_job("non-existent-id")
