"""F-04 API 테스트 공통 픽스처 — redis/rq Mock 처리.

redis, rq 패키지가 설치되지 않은 환경에서도 FastAPI 앱을 로드할 수 있도록
sys.modules에 Mock을 주입한다.
"""

import sys
from unittest.mock import MagicMock

import pytest


# ──────────────────────────────────────────────────────────────
# redis / rq 모듈 Mock 주입 (패키지 미설치 환경 대응)
# ──────────────────────────────────────────────────────────────

def _inject_redis_mock() -> None:
    """redis, rq 패키지를 sys.modules에 Mock으로 주입한다.

    scan_orchestrator.py가 `import redis`와 `from rq import ...`를
    사용하므로, 해당 모듈이 설치되지 않아도 임포트가 가능해야 한다.
    rate_limit.py가 `import redis.asyncio as aioredis`를 사용하므로
    redis.asyncio 서브모듈도 Mock으로 등록한다.
    """
    if "redis" not in sys.modules:
        redis_mock = MagicMock()
        redis_mock.Redis = MagicMock()
        redis_mock.from_url = MagicMock(return_value=MagicMock())
        sys.modules["redis"] = redis_mock

    # redis.asyncio 서브모듈 Mock 등록 (rate_limit_middleware, health.py 대응)
    if "redis.asyncio" not in sys.modules:
        asyncio_mock = MagicMock()
        asyncio_mock.from_url = MagicMock(return_value=MagicMock())
        sys.modules["redis.asyncio"] = asyncio_mock
        # redis 패키지 속성으로도 등록
        sys.modules["redis"].asyncio = asyncio_mock

    if "rq" not in sys.modules:
        rq_mock = MagicMock()
        rq_mock.Queue = MagicMock()
        rq_mock.Retry = MagicMock()
        sys.modules["rq"] = rq_mock

    if "rq.job" not in sys.modules:
        sys.modules["rq.job"] = MagicMock()


# 모듈 로드 시점에 즉시 주입
_inject_redis_mock()
