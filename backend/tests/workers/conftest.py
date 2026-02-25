"""tests/workers 디렉토리 공통 픽스처.

모듈 임포트 시점에 환경변수와 외부 의존성이 설정되어야 한다.
redis, rq 등 설치되지 않은 패키지는 sys.modules에 mock으로 등록한다.
"""

import os
import sys
from unittest.mock import MagicMock

# 테스트 모듈 임포트 전에 환경변수를 설정한다 (conftest 최상단에서 실행)
_TEST_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test_vulnix",
    "REDIS_URL": "redis://localhost:6379",
    "GITHUB_APP_ID": "123456",
    "GITHUB_APP_PRIVATE_KEY": "-----BEGIN RSA PRIVATE KEY-----\ntest_key\n-----END RSA PRIVATE KEY-----",
    "GITHUB_WEBHOOK_SECRET": "test_webhook_secret_for_hmac",
    "GITHUB_CLIENT_ID": "test_client_id",
    "GITHUB_CLIENT_SECRET": "test_client_secret",
    "ANTHROPIC_API_KEY": "test_anthropic_key",
    "JWT_SECRET_KEY": "test_jwt_secret_key_for_testing",
}

for _key, _val in _TEST_ENV.items():
    os.environ.setdefault(_key, _val)

# redis, rq가 설치되어 있지 않은 환경을 대비해 mock 모듈 등록
if "redis" not in sys.modules:
    sys.modules["redis"] = MagicMock()
if "rq" not in sys.modules:
    _rq_mock = MagicMock()
    _rq_mock.Queue = MagicMock()
    _rq_mock.Worker = MagicMock()
    _rq_mock.Retry = MagicMock()
    sys.modules["rq"] = _rq_mock
