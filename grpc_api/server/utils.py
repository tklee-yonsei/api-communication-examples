"""gRPC 서버 유틸리티 함수."""

from __future__ import annotations

from grpc_api.protos import jobs_pb2


def job_payload_to_proto(job: object) -> jobs_pb2.JobStatus:
    """JobPayload를 protobuf JobStatus로 변환합니다.

    Args:
        job: JobPayload 객체 (또는 유사한 속성을 가진 객체)

    Returns:
        jobs_pb2.JobStatus: 변환된 protobuf 메시지

    Raises:
        TypeError: job이 필요한 속성을 가지지 않은 경우
    """
    # 타입 체크: JobPayload인지 확인
    if (
        not hasattr(job, "id")
        or not hasattr(job, "type")
        or not hasattr(job, "status")
    ):
        raise TypeError(f"Expected JobPayload, got {type(job)}")

    status = jobs_pb2.JobStatus(
        id=getattr(job, "id"),
        type=getattr(job, "type"),
        status=getattr(job, "status"),
    )

    job_result = getattr(job, "result", None)
    if job_result is not None:
        job_status = getattr(job, "status", "")
        if job_status == "failed" or job_status == "error":
            if isinstance(job_result, dict):
                status.error.CopyFrom(
                    jobs_pb2.BaseError(
                        error=job_result.get("error", "Unknown error")
                    )
                )
            elif hasattr(job_result, "error"):
                status.error.CopyFrom(
                    jobs_pb2.BaseError(error=getattr(job_result, "error"))
                )
        elif getattr(job, "type", "") == "hash":
            if isinstance(job_result, dict):
                status.hash_result.CopyFrom(
                    jobs_pb2.HashResult(
                        algo=job_result.get("algo", ""),
                        input=job_result.get("input", ""),
                        digest=job_result.get("digest", ""),
                    )
                )
        elif getattr(job, "type", "") == "fib":
            if isinstance(job_result, dict):
                status.fib_result.CopyFrom(
                    jobs_pb2.FibResult(
                        n=job_result.get("n", 0),
                        fib=job_result.get("fib", 0),
                    )
                )

    return status
