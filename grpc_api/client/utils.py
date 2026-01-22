"""gRPC 클라이언트 공통 유틸리티 함수."""

from __future__ import annotations

import uuid
from typing import cast

from communication.types import JobParams
from grpc_api.protos import jobs_pb2


def create_echo_request(params: JobParams) -> jobs_pb2.EchoRequest:
    """Echo 요청을 생성합니다."""
    request = jobs_pb2.EchoRequest()
    for key, value in params.items():
        request.data[key] = str(value)
    return request


def create_calc_request(params: JobParams) -> jobs_pb2.CalcRequest:
    """Calc 요청을 생성합니다."""
    a_val = params.get("a", 0)
    b_val = params.get("b", 0)
    return jobs_pb2.CalcRequest(
        op=str(params.get("op", "add")),
        a=float(a_val) if isinstance(a_val, (int, float, str)) else 0.0,
        b=float(b_val) if isinstance(b_val, (int, float, str)) else 0.0,
    )


def create_stats_request(params: JobParams) -> jobs_pb2.StatsRequest:
    """Stats 요청을 생성합니다."""
    values_raw = params.get("values", [])
    if not isinstance(values_raw, list):
        values: list[object] = []
    else:
        values = cast(list[object], values_raw)
    return jobs_pb2.StatsRequest(
        values=[float(v) if isinstance(v, (int, float, str)) else 0.0 for v in values]
    )


def create_hash_request(params: JobParams) -> jobs_pb2.HashRequest:
    """Hash 요청을 생성합니다."""
    request = jobs_pb2.HashRequest()
    for key, value in params.items():
        request.data[key] = str(value)
    return request


def create_fib_request(params: JobParams) -> jobs_pb2.FibRequest:
    """Fib 요청을 생성합니다."""
    n_val = params.get("n", 0)
    n = int(n_val) if isinstance(n_val, (int, float, str)) else 0
    return jobs_pb2.FibRequest(n=n)


def generate_fallback_job_id() -> str:
    """알 수 없는 작업 타입에 대한 fallback job_id를 생성합니다."""
    return str(uuid.uuid4())
