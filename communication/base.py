from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Optional, TypeAlias
from types import TracebackType


JobId: TypeAlias = str
JobParams: TypeAlias = Mapping[str, Any]
JobStatus = Literal["pending", "running", "done", "failed", "error"]


class JobClientError(Exception):
    """기본 JobClient 예외"""


class JobNotFoundError(JobClientError):
    """요청한 작업을 찾을 수 없음 예외"""


@dataclass(frozen=True)
class JobRequest:
    """작업 요청 데이터

    Attributes:
        type (str): 작업 종류 식별자
        params (JobParams): 작업 실행에 필요한 파라미터
    """

    type: str
    params: JobParams


@dataclass(frozen=True)
class JobRecord:
    """작업 상태 데이터

    Attributes:
        id (JobId): 작업 고유 식별자
        type (str): 작업 종류
        params (JobParams): 요청 시 전달된 파라미터
        status (JobStatus): 현재 작업 상태
    """

    id: JobId
    type: str
    params: JobParams
    status: JobStatus


class JobClient(ABC):
    """통신 방식과 무관하게 공통으로 사용하는 클라이언트 인터페이스"""

    @abstractmethod
    def create_job(self, job_type: str, params: JobParams) -> JobRecord:
        """새로운 작업을 생성하고 초기 상태를 반환합니다.

        Args:
            job_type (str): 작업 종류 식별자
            params (JobParams): 작업 실행에 필요한 파라미터

        Returns:
            JobRecord: 생성된 작업 기록
        """

    @abstractmethod
    def get_job(self, job_id: str) -> JobRecord:
        """작업 ID로 현재 상태를 조회합니다.

        Args:
            job_id (str): 조회할 작업의 식별자

        Returns:
            JobRecord: 요청한 작업의 현재 상태
        """

    def close(self) -> None:
        """연결이나 세션을 정리합니다."""

    def __enter__(self) -> "JobClient":
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """컨텍스트 매니저 종료 시 호출됩니다.

        Args:
            exc_type (Optional[type[BaseException]]): 발생한 예외 타입
            exc_val (Optional[BaseException]): 발생한 예외 인스턴스
            exc_tb (Optional[TracebackType]): 예외 트레이스백 정보
        """
        self.close()
