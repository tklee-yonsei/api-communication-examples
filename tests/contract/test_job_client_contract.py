"""JobClient 인터페이스 계약 테스트.

이 모듈은 모든 JobClient 구현체가 준수해야 하는 인터페이스 계약을 정의합니다.
계약 테스트는 구현체가 인터페이스를 올바르게 구현했는지 검증합니다.

주요 계약:
1. create_job(): 작업 생성 후 JobRecord 반환
2. get_job(): 존재하는 작업 조회 시 JobRecord 반환
3. get_job(): 존재하지 않는 작업 조회 시 JobNotFoundError 발생
4. 컨텍스트 매니저 프로토콜 지원

테스트 방식:
- ABC 기반 추상 테스트 클래스 제공
- 구체 구현체가 이 클래스를 상속하여 테스트 실행
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import uuid4

import pytest

from communication.base import JobClient, JobNotFoundError
from communication.types import JobParams


class JobClientContractTests(ABC):
    """모든 JobClient 구현체가 따라야 할 인터페이스 준수 테스트 모음.

    이 클래스를 상속받은 테스트 클래스는 client fixture를 구현해야 합니다.
    각 테스트 메서드는 JobClient 인터페이스의 계약을 검증합니다.

    Attributes:
        __test__ (bool): False로 설정하여 pytest가 이 클래스를 직접 수집하지 않도록 함
    """

    __test__ = False  # 베이스 클래스는 pytest 수집 대상이 아님

    @pytest.fixture
    @abstractmethod
    def client(self) -> JobClient:
        """구체 클라이언트를 반환하는 픽스처.

        각 구현체 테스트 클래스에서 오버라이드해야 합니다.

        Returns:
            JobClient: 테스트할 클라이언트 인스턴스
        """

    def _random_payload(self) -> tuple[str, JobParams]:
        """임의의 작업 타입/파라미터 페어를 생성합니다.

        테스트 간 격리를 위해 고유한 값을 생성합니다.
        기본 구현은 인메모리 클라이언트용으로 임의의 작업 타입을 생성합니다.

        REST 클라이언트 등 특정 작업 타입이 필요한 경우 오버라이드하세요.

        Returns:
            tuple[str, JobParams]: (작업 타입, 파라미터) 튜플
        """
        job_type = f"job-{uuid4()}"
        params: JobParams = {"payload": f"data-{uuid4()}"}
        return job_type, params

    def test_create_and_get_job(self, client: JobClient) -> None:
        """작업 생성 후 동일 ID로 조회하면 동일 데이터가 반환되는지 검증합니다.

        이 테스트는 다음 계약을 검증합니다:
        1. create_job()이 JobRecord를 반환함
        2. 반환된 JobRecord에 id, type, params, status 속성이 있음
        3. get_job()으로 조회 시 동일한 데이터가 반환됨

        Args:
            client: 테스트할 JobClient 인스턴스
        """
        job_type, params = self._random_payload()

        # 작업 생성
        created = client.create_job(job_type, params)

        # 생성된 작업 검증
        assert created.id is not None, "생성된 작업은 ID를 가져야 합니다"
        assert created.type == job_type, "작업 타입이 일치해야 합니다"
        assert created.params == params, "파라미터가 일치해야 합니다"
        assert created.status is not None, "상태가 있어야 합니다"

        # 동일 ID로 조회
        fetched = client.get_job(created.id)

        # 조회된 작업 검증
        assert fetched.id == created.id, "조회된 ID가 생성된 ID와 일치해야 합니다"
        assert fetched.type == job_type, "조회된 타입이 원본과 일치해야 합니다"
        assert fetched.params == params, "조회된 파라미터가 원본과 일치해야 합니다"
        # 비동기 작업의 경우 상태가 변경될 수 있음 (pending -> done)
        valid_statuses = {"pending", "running", "done", "failed", "error"}
        assert (
            fetched.status in valid_statuses
        ), f"조회된 상태가 유효해야 합니다: {fetched.status}"

    def test_missing_job_raises(self, client: JobClient) -> None:
        """존재하지 않는 작업을 조회할 때 JobNotFoundError가 발생하는지 검증합니다.

        이 테스트는 다음 계약을 검증합니다:
        1. 존재하지 않는 job_id로 get_job() 호출 시 예외 발생
        2. 발생하는 예외가 JobNotFoundError 타입임

        Args:
            client: 테스트할 JobClient 인스턴스
        """
        non_existent_id = f"non-existent-{uuid4()}"

        with pytest.raises(JobNotFoundError) as exc_info:
            client.get_job(non_existent_id)

        # 예외 메시지에 ID가 포함되어 있으면 더 좋음
        assert (
            non_existent_id in str(exc_info.value)
            or "not found" in str(exc_info.value).lower()
        )

    def test_create_job_returns_pending_or_done_status(self, client: JobClient) -> None:
        """create_job이 유효한 상태를 반환하는지 검증합니다.

        작업 생성 직후 상태는 일반적으로 'pending' 또는 'done' (동기 작업)입니다.

        Args:
            client: 테스트할 JobClient 인스턴스
        """
        job_type, params = self._random_payload()
        created = client.create_job(job_type, params)

        valid_statuses = {"pending", "running", "done", "failed", "error"}
        assert (
            created.status in valid_statuses
        ), f"상태는 {valid_statuses} 중 하나여야 합니다, 실제: {created.status}"

    def test_job_id_is_string(self, client: JobClient) -> None:
        """작업 ID가 문자열 타입인지 검증합니다.

        Args:
            client: 테스트할 JobClient 인스턴스
        """
        job_type, params = self._random_payload()
        created = client.create_job(job_type, params)

        assert isinstance(
            created.id, str
        ), f"작업 ID는 문자열이어야 합니다, 실제 타입: {type(created.id)}"
        assert len(created.id) > 0, "작업 ID는 빈 문자열이 아니어야 합니다"

    def test_multiple_jobs_have_unique_ids(self, client: JobClient) -> None:
        """여러 작업을 생성할 때 각각 고유한 ID를 갖는지 검증합니다.

        Args:
            client: 테스트할 JobClient 인스턴스
        """
        job_ids: set[str] = set()

        for _ in range(5):
            job_type, params = self._random_payload()
            created = client.create_job(job_type, params)
            job_ids.add(created.id)

        assert len(job_ids) == 5, "각 작업은 고유한 ID를 가져야 합니다"
