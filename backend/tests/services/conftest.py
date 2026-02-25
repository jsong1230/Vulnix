"""tests/services 디렉토리 공통 픽스처.

모듈 임포트 시점에 환경변수가 설정되어야 하므로
pytest-env 또는 os.environ 직접 패치로 처리한다.
"""

import os

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
