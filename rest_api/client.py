from __future__ import annotations

from typing import Any, Mapping, Optional, TypedDict, cast

import requests

from communication.base import (
    JobClient,
    JobNotFoundError,
    JobParams,
    JobRecord,
    JobStatus,
)


class _CreateJobResponse(TypedDict):
    """REST /jobs POST 응답 스키마

    Attributes:
        job_id (str): 생성된 작업의 UUID
        status (str): 즉시 보고된 상태(pending 등)
    """

    job_id: str
    status: str


class _GetJobResponse(TypedDict):
    """REST /jobs/{id} GET 응답 스키마

    Attributes:
        id (str): 조회하려는 작업 ID
        type (str): 작업 종류
        params (Mapping[str, Any]): 원래 요청된 파라미터
        status (str): 현재 상태 정보
    """

    id: str
    type: str
    params: Mapping[str, Any]
    status: str


class RestJobClient(JobClient):
    """REST 서비스를 사용하는 JobClient 구현."""

    def __init__(
        self, base_url: str, session: Optional[requests.Session] = None
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def create_job(self, job_type: str, params: JobParams) -> JobRecord:
        """POST /jobs로 작업을 생성하고 레코드를 반환합니다.

        Args:
            job_type (str): 작업 종류 식별자
            params (JobParams): 작업 수행에 필요한 파라미터

        Returns:
            JobRecord: 생성된 작업에 대한 기록
        """
        response = self.session.post(
            f"{self.base_url}/jobs", json={"type": job_type, "params": params}
        )
        self._raise_for_status(response)
        data = cast(_CreateJobResponse, response.json())
        return JobRecord(
            id=str(data["job_id"]),
            type=job_type,
            params=params,
            status=cast(JobStatus, data["status"]),
        )

    def get_job(self, job_id: str) -> JobRecord:
        """GET /jobs/{job_id}로 작업 상태를 조회합니다.

        Args:
            job_id (str): 조회 대상 작업의 식별자

        Returns:
            JobRecord: 요청한 작업의 현재 기록

        Raises:
            JobNotFoundError: 작업이 존재하지 않으면 발생
        """
        response = self.session.get(f"{self.base_url}/jobs/{job_id}")
        if response.status_code == 404:
            raise JobNotFoundError(f"Job {job_id} not found")
        self._raise_for_status(response)
        data = cast(_GetJobResponse, response.json())
        return JobRecord(
            id=str(data["id"]),
            type=str(data["type"]),
            params=data.get("params", {}),
            status=cast(JobStatus, data["status"]),
        )

    def close(self) -> None:
        """세션을 닫아 네트워크 리소스를 해제합니다."""
        self.session.close()

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        """``raise_for_status``를 호출하여 HTTP 오류를 전파합니다."""
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:  # pragma: no cover - pass-through
            raise exc
