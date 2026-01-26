"""WebSocket API 클라이언트 구현."""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Optional, cast

import websockets
from websockets.exceptions import ConnectionClosed

from communication.base import JobClient, JobNotFoundError, JobRecord
from communication.types import JobParams, JobStatus

# websockets 16.0의 타입 정의
# websockets.connect()가 반환하는 타입은 asyncio.client.ClientConnection입니다
# 타입 스텁이 완전하지 않으므로 타입 체커 오류는 무시
from typing import Any

logger = logging.getLogger(__name__)


class WebSocketJobClient(JobClient):
    """WebSocket 서비스를 사용하는 JobClient 구현.

    REST API 클라이언트와 동일한 인터페이스(JobClient)를 구현하여
    통신 방식에 관계없이 동일한 방식으로 작업을 생성/조회할 수 있습니다.
    """

    def __init__(self, url: str = "ws://localhost:8082/ws") -> None:
        """클라이언트를 초기화합니다.

        Args:
            url: WebSocket 서버 URL (예: ws://localhost:8082/ws)
        """
        self.url = url
        # websockets.connect()는 async context manager를 반환하지만,
        # 연결을 유지하기 위해 직접 사용합니다
        self.websocket: Optional[Any] = None
        self._message_queue: Optional[asyncio.Queue[dict[str, object]]] = None
        self._listener_task: Optional[asyncio.Task[None]] = None

    async def _connect(self) -> None:
        """WebSocket 연결을 설정합니다."""
        if self.websocket is None:
            # 기존 리스너 태스크가 있으면 취소
            if self._listener_task is not None:
                self._listener_task.cancel()
                try:
                    await self._listener_task
                except asyncio.CancelledError:
                    pass
                self._listener_task = None

            # 이벤트 루프가 실행 중일 때만 큐를 생성 (매번 새로 생성하여 이벤트 루프 문제 방지)
            # 현재 이벤트 루프에서 새 큐 생성 (기존 큐는 무시)
            self._message_queue = asyncio.Queue()
            try:
                self.websocket = await websockets.connect(self.url)
                # 메시지 리스너 시작
                self._listener_task = asyncio.create_task(self._listen_messages())

                # 초기 연결 시 서버가 보내는 init 메시지 소비
                # 타임아웃을 짧게 설정하여 init 메시지가 없어도 계속 진행
                try:
                    init_message = await asyncio.wait_for(
                        self._message_queue.get(), timeout=2.0
                    )
                    if init_message.get("type") == "init":
                        # init 메시지는 무시하고 계속 진행
                        logger.debug("Received init message, ignoring")
                except asyncio.TimeoutError:
                    # init 메시지가 없어도 계속 진행 (서버가 보내지 않을 수 있음)
                    logger.debug("No init message received, continuing")
            except Exception as e:
                # 연결 실패 시 더 명확한 오류 메시지
                raise RuntimeError(
                    f"WebSocket 서버에 연결할 수 없습니다. URL: {self.url}\n"
                    f"원인: {str(e)}\n"
                    f"해결: WebSocket 서버가 실행 중인지 확인하고, URL이 올바른지 확인하세요."
                ) from e

    async def _listen_messages(self) -> None:
        """서버로부터 메시지를 수신하고 큐에 추가합니다."""
        if self.websocket is None:
            return

        # 큐가 없거나 다른 이벤트 루프에 바인딩되어 있으면 새로 생성
        if self._message_queue is None:
            self._message_queue = asyncio.Queue()
        else:
            try:
                current_loop = asyncio.get_running_loop()
                # 큐의 이벤트 루프 확인 (private 속성 대신 _get_loop() 메서드 사용)
                queue_loop = getattr(self._message_queue, "_get_loop", lambda: None)()
                if queue_loop is not None and queue_loop is not current_loop:
                    # 다른 이벤트 루프에 바인딩되어 있으면 새로 생성
                    self._message_queue = asyncio.Queue()
            except (AttributeError, RuntimeError):
                # 큐가 닫혔거나 문제가 있으면 새로 생성
                self._message_queue = asyncio.Queue()

        try:
            async for message in self.websocket:
                try:
                    # HTML 응답 체크 (WebSocket 서버가 아닌 HTTP 서버 응답)
                    if isinstance(message, str) and message.strip().lower().startswith(
                        "<!doctype"
                    ):
                        error_msg = (
                            f"WebSocket 서버가 아닌 HTTP 서버로부터 HTML 응답을 받았습니다.\n"
                            f"URL: {self.url}\n"
                            f"해결: WebSocket 서버가 실행 중인지, URL이 올바른지 확인하세요."
                        )
                        logger.error(error_msg)
                        await self._message_queue.put(
                            {"type": "error", "message": error_msg}
                        )
                        break
                    data = json.loads(message)
                    await self._message_queue.put(data)
                except json.JSONDecodeError as e:
                    # HTML 응답이 JSON 파싱 오류로 나타날 수 있음
                    if isinstance(message, str) and (
                        "<!doctype" in message.lower() or "<html" in message.lower()
                    ):
                        error_msg = (
                            f"WebSocket 서버가 아닌 HTTP 서버로부터 HTML 응답을 받았습니다.\n"
                            f"URL: {self.url}\n"
                            f"응답 시작: {message[:100]}...\n"
                            f"해결: WebSocket 서버가 실행 중인지, URL이 올바른지 확인하세요."
                        )
                        logger.error(error_msg)
                        await self._message_queue.put(
                            {"type": "error", "message": error_msg}
                        )
                        break
                    logger.warning(f"Invalid JSON received: {message[:100]}")
        except ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error listening to messages: {e}")

    async def _wait_for_message(
        self, message_type: str, timeout: float = 10.0
    ) -> dict[str, object]:
        """특정 타입의 메시지를 기다립니다.

        Args:
            message_type: 기다릴 메시지 타입
            timeout: 타임아웃 시간(초)

        Returns:
            dict[str, object]: 수신한 메시지

        Raises:
            TimeoutError: 타임아웃 발생 시
        """
        if self._message_queue is None:
            raise RuntimeError("Message queue not initialized. Call _connect() first.")

        # 큐가 다른 이벤트 루프에 바인딩되어 있는지 확인
        # asyncio.Queue는 생성 시점의 이벤트 루프에 바인딩되므로,
        # 다른 루프에서 사용하려고 하면 오류가 발생함
        # 이 경우 _connect()를 다시 호출하여 새 큐를 생성해야 함

        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            try:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    raise TimeoutError(f"Timeout waiting for {message_type}")

                message = await asyncio.wait_for(
                    self._message_queue.get(), timeout=remaining
                )
                if message.get("type") == message_type:
                    return message
                elif message.get("type") == "error":
                    error_msg = message.get("message", "Unknown error")
                    raise RuntimeError(str(error_msg))
            except RuntimeError as e:
                # 큐가 다른 이벤트 루프에 바인딩되어 있는 경우
                if "bound to a different event loop" in str(e):
                    # 큐를 None으로 설정하고 재연결 시도
                    self._message_queue = None
                    self.websocket = None
                    if self._listener_task is not None:
                        self._listener_task.cancel()
                        self._listener_task = None
                    await self._connect()
                    # 재연결 후 큐가 생성되었는지 확인
                    if self._message_queue is None:
                        raise RuntimeError(
                            "Failed to recreate message queue after reconnection"
                        )
                    # 재시도
                    continue
                raise
            except asyncio.TimeoutError:
                raise TimeoutError(f"Timeout waiting for {message_type}")

    def create_job(self, job_type: str, params: JobParams) -> JobRecord:
        """작업을 생성하고 레코드를 반환합니다.

        동기 작업(echo, calc, stats): 즉시 결과 반환
        비동기 작업(hash, fib): job_id 반환

        Args:
            job_type: 작업 종류 식별자
            params: 작업 수행에 필요한 파라미터

        Returns:
            JobRecord: 생성된 작업에 대한 기록
        """
        # asyncio.run()은 새로운 이벤트 루프를 생성하므로,
        # 기존 연결과 큐를 완전히 정리하여 새 루프에서 새로 생성되도록 함
        # close()를 호출하여 기존 연결 정리
        if self.websocket is not None or self._listener_task is not None:
            # 기존 연결이 있으면 정리
            try:
                if self._listener_task is not None:
                    self._listener_task.cancel()
                if self.websocket is not None:
                    # 동기적으로는 close할 수 없으므로 None으로 설정
                    self.websocket = None
                self._listener_task = None
                self._message_queue = None
            except Exception:
                # 정리 중 오류가 발생해도 무시하고 계속 진행
                self.websocket = None
                self._listener_task = None
                self._message_queue = None

        return asyncio.run(self._create_job_async(job_type, params))

    async def _create_job_async(self, job_type: str, params: JobParams) -> JobRecord:
        """비동기로 작업을 생성합니다."""
        # 기존 연결이 있으면 정리 (다른 이벤트 루프에 바인딩되어 있을 수 있음)
        if self.websocket is not None:
            self.websocket = None
        if self._listener_task is not None:
            self._listener_task.cancel()
            self._listener_task = None
        if self._message_queue is not None:
            self._message_queue = None

        await self._connect()
        if self.websocket is None:
            raise RuntimeError("WebSocket not connected")

        # 작업 생성 요청 전송
        await self.websocket.send(
            json.dumps({"type": "create_job", "job_type": job_type, "params": params})
        )

        if job_type in ("echo", "calc", "stats"):
            # 동기 작업: 즉시 결과 반환
            response = await self._wait_for_message("job_result")
            job_data_raw = response.get("job", {})
            job_data = cast(dict[str, object], job_data_raw)
            params_raw = job_data.get("params", {})
            params = cast(JobParams, params_raw)
            return JobRecord(
                id="",  # 동기 작업은 job_id 없음
                type=job_type,
                params=params,
                status="done",
            )
        else:
            # 비동기 작업: job_created 메시지 대기
            response = await self._wait_for_message("job_created")
            job_data_raw = response.get("job", {})
            job_data = cast(dict[str, object], job_data_raw)
            params_raw = job_data.get("params", {})
            params = cast(JobParams, params_raw)
            return JobRecord(
                id=str(job_data.get("id", "")),
                type=str(job_data.get("type", job_type)),
                params=params,
                status=cast(JobStatus, job_data.get("status", "pending")),
            )

    def get_job(self, job_id: str) -> JobRecord:
        """작업 상태를 조회합니다.

        Args:
            job_id: 조회 대상 작업의 식별자

        Returns:
            JobRecord: 요청한 작업의 현재 기록

        Raises:
            JobNotFoundError: 작업이 존재하지 않으면 발생
        """
        # asyncio.run()은 새로운 이벤트 루프를 생성하므로,
        # 기존 연결과 큐를 완전히 정리하여 새 루프에서 새로 생성되도록 함
        if self.websocket is not None or self._listener_task is not None:
            try:
                if self._listener_task is not None:
                    self._listener_task.cancel()
                self.websocket = None
                self._listener_task = None
                self._message_queue = None
            except Exception:
                self.websocket = None
                self._listener_task = None
                self._message_queue = None

        return asyncio.run(self._get_job_async(job_id))

    async def _get_job_async(self, job_id: str) -> JobRecord:
        """비동기로 작업 상태를 조회합니다."""
        await self._connect()
        if self.websocket is None:
            raise RuntimeError("WebSocket not connected")

        # 작업 조회 요청 전송
        await self.websocket.send(json.dumps({"type": "get_job", "job_id": job_id}))

        # 응답 대기 - error 타입 메시지도 확인
        try:
            response = await self._wait_for_message("job")
        except RuntimeError as e:
            # 서버가 error 타입 메시지를 보낸 경우
            error_msg = str(e)
            if "not found" in error_msg.lower():
                raise JobNotFoundError(f"Job {job_id} not found") from e
            raise

        job_data_raw = response.get("job", {})
        job_data = cast(dict[str, object], job_data_raw)

        if not job_data:
            raise JobNotFoundError(f"Job {job_id} not found")

        params_raw = job_data.get("params", {})
        params = cast(JobParams, params_raw)
        return JobRecord(
            id=str(job_data.get("id", job_id)),
            type=str(job_data.get("type", "")),
            params=params,
            status=cast(JobStatus, job_data.get("status", "pending")),
        )

    def list_jobs(self, limit: int = 50) -> dict[str, object]:
        """전체 작업 목록을 조회합니다.

        Args:
            limit: 반환할 최대 작업 수

        Returns:
            dict: 작업 목록과 총 개수
        """
        # asyncio.run()은 새로운 이벤트 루프를 생성하므로,
        # 기존 연결과 큐를 완전히 정리하여 새 루프에서 새로 생성되도록 함
        if self.websocket is not None or self._listener_task is not None:
            try:
                if self._listener_task is not None:
                    self._listener_task.cancel()
                self.websocket = None
                self._listener_task = None
                self._message_queue = None
            except Exception:
                self.websocket = None
                self._listener_task = None
                self._message_queue = None

        return asyncio.run(self._list_jobs_async(limit))

    async def _list_jobs_async(self, limit: int) -> dict[str, object]:
        """비동기로 작업 목록을 조회합니다."""
        await self._connect()
        if self.websocket is None:
            raise RuntimeError("WebSocket not connected")

        # 작업 목록 조회 요청 전송
        await self.websocket.send(json.dumps({"type": "list_jobs", "limit": limit}))

        # 응답 대기
        response = await self._wait_for_message("jobs")
        return response

    def get_queue_status(self) -> dict[str, object]:
        """작업 큐 상태를 조회합니다.

        Returns:
            dict: 큐 상태 정보
        """
        return asyncio.run(self._get_queue_status_async())

    async def _get_queue_status_async(self) -> dict[str, object]:
        """비동기로 큐 상태를 조회합니다."""
        await self._connect()
        if self.websocket is None:
            raise RuntimeError("WebSocket not connected")

        # 큐 상태 조회 요청 전송
        await self.websocket.send(json.dumps({"type": "get_queue_status"}))

        # 응답 대기
        response = await self._wait_for_message("queue_status")
        return response

    def close(self) -> None:
        """WebSocket 연결을 종료합니다."""
        # 리스너 태스크 취소
        if self._listener_task is not None:
            self._listener_task.cancel()
            self._listener_task = None

        # WebSocket 연결 정리
        # asyncio.run()을 사용하면 새로운 이벤트 루프가 생성되므로,
        # 대신 연결 객체를 None으로 설정하여 다음 연결 시 새로 생성되도록 함
        if self.websocket is not None:
            # 연결을 비동기적으로 닫을 수 없으므로, 단순히 None으로 설정
            # 실제 연결은 서버 측에서 타임아웃으로 닫힐 것임
            self.websocket = None

        # 큐를 None으로 설정하여 다음 연결 시 새로 생성되도록 함
        self._message_queue = None

    async def watch_jobs(self) -> AsyncIterator[JobRecord]:
        """작업 상태 변경을 스트리밍으로 수신합니다.

        Yields:
            JobRecord: 상태가 변경된 작업
        """
        await self._connect()
        if self.websocket is None or self._message_queue is None:
            raise RuntimeError("WebSocket not connected")

        while True:
            try:
                message = await self._message_queue.get()
                if message.get("type") == "job_update":
                    job_data_raw = message.get("job", {})
                    job_data = cast(dict[str, object], job_data_raw)
                    params_raw = job_data.get("params", {})
                    params = cast(JobParams, params_raw)
                    yield JobRecord(
                        id=str(job_data.get("id", "")),
                        type=str(job_data.get("type", "")),
                        params=params,
                        status=cast(JobStatus, job_data.get("status", "pending")),
                    )
            except Exception as e:
                logger.error(f"Error watching jobs: {e}")
                break
