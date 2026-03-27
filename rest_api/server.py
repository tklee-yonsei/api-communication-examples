from __future__ import annotations

from typing import Optional, Union, cast

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from rest_api.routes import register_routes
from rest_api.types import AnyJobPayload
from rest_api.websocket import ws_manager


class RestApiServer:
    """FastAPI 기반 비동기 REST API 서버"""

    def __init__(self, store: Optional[dict[str, AnyJobPayload]] = None) -> None:
        """FastAPI 앱을 초기화하고 라우트를 등록합니다.

        Args:
            store: 작업 상태를 저장할 공유 스토어
        """
        self.store: dict[str, AnyJobPayload] = store if store is not None else {}
        self.app = FastAPI(title="REST API Server", version="1.0.0")
        self._register_routes()

    @staticmethod
    def _pydantic_to_dict(
        obj: Union[BaseModel, dict[str, object]],
    ) -> dict[str, object]:
        """Pydantic 모델을 dict로 변환합니다.

        Args:
            obj: Pydantic 모델 또는 일반 dict

        Returns:
            dict[str, object]: 변환된 dict
        """
        if isinstance(obj, BaseModel):
            return cast(dict[str, object], obj.model_dump())
        return obj

    @staticmethod
    def _json_response(
        result: Union[BaseModel, dict[str, object]],
        status_code: int = 200,
        key: str = "result",
    ) -> JSONResponse:
        """작업 결과를 JSONResponse로 반환합니다.

        Args:
            result: Pydantic 모델 또는 dict 형태의 결과
            status_code: HTTP 상태 코드
            key: 응답 JSON의 키 이름 (기본값: "result")

        Returns:
            JSONResponse: FastAPI JSONResponse 객체
        """
        result_dict = RestApiServer._pydantic_to_dict(result)
        return JSONResponse({key: result_dict}, status_code=status_code)

    async def _on_job_complete(self, job_id: str) -> None:
        """Job 완료 시 WebSocket으로 브로드캐스트합니다.

        Args:
            job_id: 완료된 작업의 ID
        """
        job = self.store.get(job_id)
        if job is not None:
            await ws_manager.broadcast(
                {
                    "type": "update",
                    "job": self._pydantic_to_dict(job),
                }
            )

    def _register_routes(self) -> None:
        """FastAPI 앱에 라우트를 등록합니다."""
        register_routes(
            app=self.app,
            jobs=self.store,
            pydantic_to_dict=self._pydantic_to_dict,
            json_response=self._json_response,
            on_job_complete=self._on_job_complete,
        )

    def run(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        """Uvicorn 서버를 실행합니다.

        Args:
            host: 바인딩할 호스트 인터페이스
            port: 수신할 포트 번호
        """
        import uvicorn

        uvicorn.run(self.app, host=host, port=port)


def create_app(store: Optional[dict[str, AnyJobPayload]] = None) -> FastAPI:
    """테스트 호환을 위한 FastAPI 앱을 생성합니다.

    Args:
        store: 선택적 공유 스토어입니다.

    Returns:
        FastAPI: 설정된 FastAPI 애플리케이션입니다.
    """
    return RestApiServer(store=store).app


if __name__ == "__main__":
    server = RestApiServer()
    server.run(host="0.0.0.0", port=8080)
