from __future__ import annotations

import hashlib
import json

from communication.jobs.base import AsyncJobHandler
from communication.jobs.types import HashParams, HashResult


class HashJobHandler(AsyncJobHandler[HashParams, HashResult]):
    """해시 작업 핸들러."""

    async def execute(self, params: HashParams) -> HashResult:
        """params 전체를 정렬된 JSON 문자열로 변환 후 SHA-256 해시."""
        params_dict = params.model_dump()
        serialized = json.dumps(params_dict, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return HashResult(algo="sha256", input=serialized, digest=digest)
