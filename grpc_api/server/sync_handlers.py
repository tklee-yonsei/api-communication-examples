"""동기 작업 처리 헬퍼 함수."""

from __future__ import annotations

import logging
from typing import Literal

from grpc_api.protos import jobs_pb2
from rest_api.core.jobs import CalcJobHandler, EchoJobHandler, StatsJobHandler
from rest_api.core.jobs.types import (
    CalcParams,
    EchoParams,
    StatsParams,
)

logger = logging.getLogger(__name__)


async def handle_echo(request: jobs_pb2.EchoRequest) -> jobs_pb2.EchoResponse:
    """Echo 작업을 처리합니다.

    Args:
        request: Echo 요청

    Returns:
        EchoResponse: Echo 결과
    """
    logger.info("Echo request received")

    # map을 dict로 변환
    data = dict(request.data)

    # EchoJobHandler 사용
    handler = EchoJobHandler()
    params = EchoParams(**data)
    result = await handler.execute(params)

    # 결과를 protobuf로 변환
    response = jobs_pb2.EchoResponse()
    for key, value in result.echo.items():
        response.echo[key] = str(value)

    return response


async def handle_calc(request: jobs_pb2.CalcRequest) -> jobs_pb2.CalcResponse:
    """Calc 작업을 처리합니다.

    Args:
        request: Calc 요청

    Returns:
        CalcResponse: Calc 결과
    """
    logger.info(f"Calc request: {request.op} {request.a} {request.b}")

    handler = CalcJobHandler()
    # protobuf string을 Literal 타입으로 변환
    op_str = str(request.op)
    # 타입 가드: 유효한 op 값인지 확인
    if op_str == "add":
        op: Literal["add", "sub", "mul", "div"] = "add"
    elif op_str == "sub":
        op = "sub"
    elif op_str == "mul":
        op = "mul"
    elif op_str == "div":
        op = "div"
    else:
        op = "add"  # 기본값
    params = CalcParams(op=op, a=float(request.a), b=float(request.b))
    result = await handler.execute(params)

    # 에러 체크
    if hasattr(result, "error"):
        return jobs_pb2.CalcResponse(
            op=request.op,
            a=request.a,
            b=request.b,
            result=0.0,
            error=result.error,
        )

    return jobs_pb2.CalcResponse(
        op=result.op,
        a=result.a,
        b=result.b,
        result=result.result,
    )


async def handle_stats(request: jobs_pb2.StatsRequest) -> jobs_pb2.StatsResponse:
    """Stats 작업을 처리합니다.

    Args:
        request: Stats 요청

    Returns:
        StatsResponse: Stats 결과
    """
    logger.info(f"Stats request: {len(request.values)} values")

    handler = StatsJobHandler()
    params = StatsParams(values=list(request.values))
    result = await handler.execute(params)

    # 에러 체크
    if hasattr(result, "error"):
        return jobs_pb2.StatsResponse(error=result.error)

    return jobs_pb2.StatsResponse(
        count=result.count,
        min=result.min,
        max=result.max,
        sum=result.sum,
        mean=result.mean,
        median=result.median,
    )
