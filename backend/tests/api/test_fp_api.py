"""오탐 패턴 CRUD API 통합 테스트 — IT-01"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# 테스트용 Mock FalsePositivePattern 픽스처
# ---------------------------------------------------------------------------

def _make_fp_pattern(
    pattern_id: uuid.UUID | None = None,
    team_id: uuid.UUID | None = None,
    semgrep_rule_id: str = "python.flask.security.xss",
    file_pattern: str | None = "tests/**",
    reason: str | None = "테스트 코드 오탐",
    is_active: bool = True,
    matched_count: int = 0,
) -> MagicMock:
    """FalsePositivePattern Mock 객체를 생성한다."""
    from src.models.false_positive import FalsePositivePattern

    p = MagicMock(spec=FalsePositivePattern)
    p.id = pattern_id or uuid.uuid4()
    p.team_id = team_id or uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    p.semgrep_rule_id = semgrep_rule_id
    p.file_pattern = file_pattern
    p.reason = reason
    p.is_active = is_active
    p.matched_count = matched_count
    p.last_matched_at = None
    p.created_by = uuid.UUID("00000000-0000-0000-0000-000000000001")
    p.source_vulnerability_id = None
    p.created_at = datetime(2026, 2, 25, 10, 0, 0)
    p.updated_at = datetime(2026, 2, 25, 10, 0, 0)
    return p


@pytest.fixture
def fp_test_client():
    """오탐 패턴 API 전용 TestClient.

    false_positive_pattern 테이블 조회에 적절한 Mock 데이터를 반환하는
    스마트 DB Mock을 포함한다.
    """
    from src.main import create_app
    from src.api.deps import get_db, get_current_user

    app = create_app()

    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    team_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    none_id = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")

    pattern_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    inactive_pattern_id = uuid.UUID("22222222-2222-2222-2222-222222222222")

    active_pattern = _make_fp_pattern(
        pattern_id=pattern_id,
        team_id=team_id,
        is_active=True,
    )
    inactive_pattern = _make_fp_pattern(
        pattern_id=inactive_pattern_id,
        team_id=team_id,
        is_active=False,
    )

    def _make_result(items):
        result = MagicMock()
        if isinstance(items, list):
            result.scalar_one_or_none.return_value = items[0] if items else None
            result.scalars.return_value.all.return_value = items
        else:
            result.scalar_one_or_none.return_value = items
            result.scalars.return_value.all.return_value = [items] if items else []
        return result

    async def smart_execute(query, *args, **kwargs):
        query_str = str(query).lower()

        # team_member 쿼리 → 팀 ID + 역할(owner) 반환
        if "team_member" in query_str:
            result = MagicMock()
            result.scalar_one_or_none.return_value = team_id
            # get_user_team_role은 result.first()를 사용 — (team_id, role) 튜플 반환
            result.first.return_value = (team_id, "owner")
            return result

        # false_positive_pattern 쿼리
        if "false_positive_pattern" in query_str:
            # 파라미터에서 UUID 추출
            try:
                params = dict(query.compile().params)
            except Exception:
                params = {}

            all_uuids = {v for v in params.values() if isinstance(v, uuid.UUID)}

            # none_id 조회 → None (404)
            if none_id in all_uuids:
                return _make_result(None)

            # 특정 패턴 ID 조회
            if pattern_id in all_uuids:
                return _make_result(active_pattern)
            if inactive_pattern_id in all_uuids:
                return _make_result(inactive_pattern)

            # 목록 조회 (team_id 기준)
            if team_id in all_uuids or not all_uuids:
                return _make_result([active_pattern, inactive_pattern])

            return _make_result([])

        return _make_result([])

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=smart_execute)
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.close = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.add = MagicMock()

    async def override_get_db():
        yield mock_db

    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.github_login = "test_user"

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, mock_db, {
            "user_id": user_id,
            "team_id": team_id,
            "pattern_id": pattern_id,
            "inactive_pattern_id": inactive_pattern_id,
            "none_id": none_id,
            "active_pattern": active_pattern,
            "inactive_pattern": inactive_pattern,
        }


@pytest.fixture
def fp_test_client_no_team():
    """팀에 소속되지 않은 사용자용 TestClient."""
    from src.main import create_app
    from src.api.deps import get_db, get_current_user

    app = create_app()

    user_id = uuid.UUID("00000000-0000-0000-0000-000000000099")

    def _make_result(items):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        result.scalars.return_value.all.return_value = []
        return result

    async def smart_execute(query, *args, **kwargs):
        return _make_result(None)

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=smart_execute)
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.add = MagicMock()

    async def override_get_db():
        yield mock_db

    mock_user = MagicMock()
    mock_user.id = user_id

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


# ---------------------------------------------------------------------------
# IT-01: POST /api/v1/false-positives
# ---------------------------------------------------------------------------

class TestCreateFalsePositive:
    """POST /api/v1/false-positives 테스트"""

    def test_create_pattern_success(self, fp_test_client):
        """정상 패턴 등록 → 201 Created"""
        client, mock_db, ctx = fp_test_client

        payload = {
            "semgrep_rule_id": "python.flask.security.xss",
            "file_pattern": "tests/**",
            "reason": "테스트 코드 오탐",
        }
        response = client.post("/api/v1/false-positives", json=payload)

        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["data"] is not None

    def test_create_pattern_missing_rule_id(self, fp_test_client):
        """semgrep_rule_id 누락 → 422 Validation Error"""
        client, mock_db, ctx = fp_test_client

        payload = {
            "file_pattern": "tests/**",
            "reason": "사유",
        }
        response = client.post("/api/v1/false-positives", json=payload)

        assert response.status_code == 422

    def test_create_pattern_no_team(self, fp_test_client_no_team):
        """팀에 소속되지 않은 사용자 → 403 Forbidden"""
        client = fp_test_client_no_team

        payload = {
            "semgrep_rule_id": "python.flask.security.xss",
        }
        response = client.post("/api/v1/false-positives", json=payload)

        assert response.status_code == 403

    def test_create_pattern_empty_rule_id(self, fp_test_client):
        """빈 semgrep_rule_id → 422 Validation Error"""
        client, mock_db, ctx = fp_test_client

        payload = {
            "semgrep_rule_id": "",
        }
        response = client.post("/api/v1/false-positives", json=payload)

        assert response.status_code == 422

    def test_create_pattern_without_file_pattern(self, fp_test_client):
        """file_pattern 없이 등록 → 201 Created (file_pattern은 선택)"""
        client, mock_db, ctx = fp_test_client

        payload = {
            "semgrep_rule_id": "python.flask.security.xss",
        }
        response = client.post("/api/v1/false-positives", json=payload)

        assert response.status_code == 201


# ---------------------------------------------------------------------------
# IT-01: GET /api/v1/false-positives
# ---------------------------------------------------------------------------

class TestListFalsePositives:
    """GET /api/v1/false-positives 테스트"""

    def test_list_patterns_success(self, fp_test_client):
        """팀별 패턴 목록 조회 → 200 OK"""
        client, mock_db, ctx = fp_test_client

        response = client.get("/api/v1/false-positives")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)

    def test_list_patterns_no_team(self, fp_test_client_no_team):
        """팀에 소속되지 않은 사용자 → 200 OK, 빈 목록"""
        client = fp_test_client_no_team

        response = client.get("/api/v1/false-positives")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"] == []

    def test_list_returns_all_patterns(self, fp_test_client):
        """팀의 모든 패턴(활성/비활성 포함) 반환"""
        client, mock_db, ctx = fp_test_client

        response = client.get("/api/v1/false-positives")

        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) >= 1


# ---------------------------------------------------------------------------
# IT-01: DELETE /api/v1/false-positives/{pattern_id}
# ---------------------------------------------------------------------------

class TestDeleteFalsePositive:
    """DELETE /api/v1/false-positives/{pattern_id} 테스트"""

    def test_delete_pattern_success(self, fp_test_client):
        """정상 삭제 (소프트) → 200 OK"""
        client, mock_db, ctx = fp_test_client
        pattern_id = ctx["pattern_id"]

        response = client.delete(f"/api/v1/false-positives/{pattern_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

    def test_delete_pattern_not_found(self, fp_test_client):
        """존재하지 않는 패턴 삭제 → 404 Not Found"""
        client, mock_db, ctx = fp_test_client
        none_id = ctx["none_id"]

        response = client.delete(f"/api/v1/false-positives/{none_id}")

        assert response.status_code == 404

    def test_delete_pattern_no_team(self, fp_test_client_no_team):
        """팀에 소속되지 않은 사용자 → 403 Forbidden"""
        client = fp_test_client_no_team
        some_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        response = client.delete(f"/api/v1/false-positives/{some_id}")

        assert response.status_code == 403

    def test_delete_sets_inactive(self, fp_test_client):
        """삭제 시 is_active=False로 소프트 삭제"""
        client, mock_db, ctx = fp_test_client
        pattern_id = ctx["pattern_id"]
        active_pattern = ctx["active_pattern"]

        client.delete(f"/api/v1/false-positives/{pattern_id}")

        # is_active가 False로 설정됨
        assert active_pattern.is_active is False


# ---------------------------------------------------------------------------
# IT-01: PUT /api/v1/false-positives/{pattern_id}/restore
# ---------------------------------------------------------------------------

class TestRestoreFalsePositive:
    """PUT /api/v1/false-positives/{pattern_id}/restore 테스트"""

    def test_restore_pattern_success(self, fp_test_client):
        """비활성 패턴 복원 → 200 OK, is_active=True"""
        client, mock_db, ctx = fp_test_client
        inactive_pattern_id = ctx["inactive_pattern_id"]
        inactive_pattern = ctx["inactive_pattern"]

        response = client.put(f"/api/v1/false-positives/{inactive_pattern_id}/restore")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert inactive_pattern.is_active is True

    def test_restore_already_active_idempotent(self, fp_test_client):
        """이미 활성인 패턴 복원 → 200 OK (멱등)"""
        client, mock_db, ctx = fp_test_client
        pattern_id = ctx["pattern_id"]

        response = client.put(f"/api/v1/false-positives/{pattern_id}/restore")

        assert response.status_code == 200

    def test_restore_not_found(self, fp_test_client):
        """존재하지 않는 패턴 복원 → 404 Not Found"""
        client, mock_db, ctx = fp_test_client
        none_id = ctx["none_id"]

        response = client.put(f"/api/v1/false-positives/{none_id}/restore")

        assert response.status_code == 404

    def test_restore_no_team(self, fp_test_client_no_team):
        """팀에 소속되지 않은 사용자 → 403 Forbidden"""
        client = fp_test_client_no_team
        some_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        response = client.put(f"/api/v1/false-positives/{some_id}/restore")

        assert response.status_code == 403


# ---------------------------------------------------------------------------
# IT-03: GET /api/v1/dashboard/false-positive-rate
# ---------------------------------------------------------------------------

class TestDashboardFpRate:
    """GET /api/v1/dashboard/false-positive-rate 테스트"""

    def test_fp_rate_basic(self, test_client):
        """기본 조회 (30일) → 200 OK"""
        response = test_client.get("/api/v1/dashboard/false-positive-rate")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "current_fp_rate" in body["data"]
        assert "trend" in body["data"]

    def test_fp_rate_custom_days(self, test_client):
        """days=7 → 200 OK"""
        response = test_client.get("/api/v1/dashboard/false-positive-rate?days=7")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

    def test_fp_rate_days_clamped_to_90(self, test_client):
        """days=120 → 200 OK (90일로 클램핑)"""
        response = test_client.get("/api/v1/dashboard/false-positive-rate?days=120")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert len(body["data"]["trend"]) <= 90

    def test_fp_rate_no_auth(self):
        """인증 없음 → 401 Unauthorized"""
        import os
        from unittest.mock import patch as _patch

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
        with _patch.dict("os.environ", _TEST_ENV):
            from src.config import get_settings
            get_settings.cache_clear()
            from src.main import create_app
            app = create_app()
            # dependency override 없이 실제 인증 적용
            from fastapi.testclient import TestClient as _TC
            with _TC(app, raise_server_exceptions=False) as raw_client:
                response = raw_client.get("/api/v1/dashboard/false-positive-rate")
            assert response.status_code == 401
            get_settings.cache_clear()

    def test_fp_rate_returns_structure(self, test_client):
        """응답 구조 검증: current_fp_rate, total_*, trend, top_fp_rules 포함"""
        response = test_client.get("/api/v1/dashboard/false-positive-rate")

        assert response.status_code == 200
        data = response.json()["data"]
        required_keys = [
            "current_fp_rate",
            "previous_fp_rate",
            "improvement",
            "total_scanned",
            "total_true_positives",
            "total_false_positives",
            "total_auto_filtered",
            "trend",
            "top_fp_rules",
        ]
        for key in required_keys:
            assert key in data, f"응답에 '{key}' 키가 없습니다."
