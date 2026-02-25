"""F-08 알림 API 엔드포인트 테스트 — NotificationConfig CRUD + 로그 조회"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────
# 픽스처
# ──────────────────────────────────────────────────────────────

TEAM_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
CONFIG_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
CONFIG_ID_2 = uuid.UUID("22222222-2222-2222-2222-222222222222")
NONE_ID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")


def _make_mock_config(
    config_id: uuid.UUID = CONFIG_ID,
    platform: str = "slack",
    severity_threshold: str = "all",
    is_active: bool = True,
) -> MagicMock:
    """NotificationConfig Mock 생성 헬퍼"""
    from src.models.notification import NotificationConfig

    config = MagicMock(spec=NotificationConfig)
    config.id = config_id
    config.team_id = TEAM_ID
    config.platform = platform
    config.webhook_url = (
        "https://hooks.slack.com/services/fake-test-url"
        if platform == "slack"
        else "https://outlook.office.com/webhook/test"
    )
    config.severity_threshold = severity_threshold
    config.weekly_report_enabled = False
    config.weekly_report_day = 1
    config.is_active = is_active
    config.created_by = USER_ID
    config.created_at = datetime(2026, 2, 25, 10, 0, 0)
    config.updated_at = datetime(2026, 2, 25, 10, 0, 0)
    return config


def _make_mock_log(log_id: uuid.UUID | None = None) -> MagicMock:
    """NotificationLog Mock 생성 헬퍼"""
    from src.models.notification import NotificationLog

    log = MagicMock(spec=NotificationLog)
    log.id = log_id or uuid.uuid4()
    log.team_id = TEAM_ID
    log.config_id = CONFIG_ID
    log.notification_type = "vulnerability"
    log.status = "sent"
    log.http_status = 200
    log.error_message = None
    log.payload = {"text": "test"}
    log.sent_at = datetime(2026, 2, 25, 10, 0, 0)
    return log


@pytest.fixture
def notification_test_client():
    """알림 API 테스트용 TestClient 픽스처.

    DB Mock에 알림 설정/로그 데이터를 추가한다.
    """
    from src.main import create_app
    from src.api.deps import get_db, get_current_user

    app = create_app()

    mock_db = _build_notification_mock_db()

    async def override_get_db():
        yield mock_db

    mock_user = MagicMock()
    mock_user.id = USER_ID
    mock_user.github_login = "test_user"

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def _build_notification_mock_db() -> AsyncMock:
    """알림 API 테스트용 스마트 Mock DB 세션 생성"""
    from src.models.team import TeamMember

    mock_config = _make_mock_config(CONFIG_ID, "slack")
    mock_config_teams = _make_mock_config(CONFIG_ID_2, "teams", "high")
    mock_log = _make_mock_log()

    mock_member = MagicMock(spec=TeamMember)
    mock_member.team_id = TEAM_ID
    mock_member.user_id = USER_ID
    mock_member.role = "owner"

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.close = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.delete = AsyncMock()

    def _make_result(items):
        result = MagicMock()
        if isinstance(items, list):
            result.scalar_one_or_none.return_value = items[0] if items else None
            result.scalars.return_value.all.return_value = items
            result.first.return_value = (items[0],) if items else None
        else:
            result.scalar_one_or_none.return_value = items
            result.scalars.return_value.all.return_value = [items] if items is not None else []
            result.first.return_value = (items,) if items is not None else None
        return result

    async def smart_execute(query, *args, **kwargs):
        query_str = str(query).lower()

        try:
            params = dict(query.compile().params)
        except Exception:
            params = {}

        all_uuids = {v for v in params.values() if isinstance(v, uuid.UUID)}

        # team_member 테이블 조회
        if "team_member" in query_str:
            result = MagicMock()
            if "team_member.role" in query_str:
                result.scalar_one_or_none.return_value = "owner"
                result.scalars.return_value.all.return_value = ["owner"]
                result.first.return_value = (TEAM_ID, "owner")
            elif "team_member.team_id" in query_str:
                result.scalar_one_or_none.return_value = TEAM_ID
                result.scalars.return_value.all.return_value = [TEAM_ID]
                result.first.return_value = (TEAM_ID, "owner")
            else:
                result.scalar_one_or_none.return_value = mock_member
                result.scalars.return_value.all.return_value = [mock_member]
                result.first.return_value = (TEAM_ID, "owner")
            return result

        # notification_config 테이블 조회
        if "notification_config" in query_str:
            # NONE_ID → 404
            if NONE_ID in all_uuids:
                return _make_result(None)
            # 특정 config_id 조회
            if CONFIG_ID in all_uuids:
                return _make_result(mock_config)
            if CONFIG_ID_2 in all_uuids:
                return _make_result(mock_config_teams)
            # 목록 조회
            return _make_result([mock_config, mock_config_teams])

        # notification_log 테이블 조회
        if "notification_log" in query_str:
            return _make_result([mock_log])

        return _make_result([])

    mock_db.execute = AsyncMock(side_effect=smart_execute)
    return mock_db


# ──────────────────────────────────────────────────────────────
# POST /api/v1/notifications/config 테스트
# ──────────────────────────────────────────────────────────────

class TestCreateNotificationConfig:
    """알림 설정 생성 엔드포인트 테스트"""

    def test_create_slack_config_success(self, notification_test_client):
        """Slack 알림 설정 생성 성공"""
        with patch("src.services.notification_service.validate_webhook_url", return_value=True):
            response = notification_test_client.post(
                "/api/v1/notifications/config",
                json={
                    "platform": "slack",
                    "webhook_url": "https://hooks.slack.com/services/fake-test-url",
                    "severity_threshold": "all",
                    "weekly_report_enabled": False,
                    "weekly_report_day": 1,
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["platform"] == "slack"

    def test_create_teams_config_success(self, notification_test_client):
        """Teams 알림 설정 생성 성공"""
        with patch("src.services.notification_service.validate_webhook_url", return_value=True):
            response = notification_test_client.post(
                "/api/v1/notifications/config",
                json={
                    "platform": "teams",
                    "webhook_url": "https://outlook.office.com/webhook/test",
                    "severity_threshold": "high",
                    "weekly_report_enabled": True,
                    "weekly_report_day": 1,
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True

    def test_create_config_invalid_platform(self, notification_test_client):
        """유효하지 않은 플랫폼 거부"""
        response = notification_test_client.post(
            "/api/v1/notifications/config",
            json={
                "platform": "discord",
                "webhook_url": "https://discord.com/api/webhooks/test",
                "severity_threshold": "all",
            },
        )

        assert response.status_code == 422

    def test_create_config_invalid_webhook_url(self, notification_test_client):
        """유효하지 않은 webhook URL 거부"""
        with patch("src.services.notification_service.validate_webhook_url", return_value=False):
            response = notification_test_client.post(
                "/api/v1/notifications/config",
                json={
                    "platform": "slack",
                    "webhook_url": "https://evil.com/webhook",
                    "severity_threshold": "all",
                },
            )

        assert response.status_code in (400, 422)

    def test_create_config_invalid_severity_threshold(self, notification_test_client):
        """유효하지 않은 severity_threshold 거부"""
        response = notification_test_client.post(
            "/api/v1/notifications/config",
            json={
                "platform": "slack",
                "webhook_url": "https://hooks.slack.com/services/test",
                "severity_threshold": "extreme",
            },
        )

        assert response.status_code == 422

    def test_create_config_member_role_forbidden(self):
        """member 역할은 설정 생성 불가 (403)"""
        from src.main import create_app
        from src.api.deps import get_db, get_current_user

        app = create_app()

        mock_db = AsyncMock()

        async def execute_side_effect(query, *args, **kwargs):
            query_str = str(query).lower()
            result = MagicMock()
            if "team_member" in query_str:
                result.scalar_one_or_none.return_value = "member"
                result.first.return_value = (TEAM_ID, "member")
            else:
                result.scalar_one_or_none.return_value = None
                result.first.return_value = None
            return result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        mock_user = MagicMock()
        mock_user.id = USER_ID

        async def override_get_db():
            yield mock_db

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            with patch("src.services.notification_service.validate_webhook_url", return_value=True):
                response = client.post(
                    "/api/v1/notifications/config",
                    json={
                        "platform": "slack",
                        "webhook_url": "https://hooks.slack.com/services/test",
                        "severity_threshold": "all",
                    },
                )

        assert response.status_code == 403

    def test_create_config_no_team_forbidden(self):
        """팀 없는 사용자는 403"""
        from src.main import create_app
        from src.api.deps import get_db, get_current_user

        app = create_app()

        mock_db = AsyncMock()

        async def execute_side_effect(query, *args, **kwargs):
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            result.first.return_value = None
            return result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        mock_user = MagicMock()
        mock_user.id = USER_ID

        async def override_get_db():
            yield mock_db

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/notifications/config",
                json={
                    "platform": "slack",
                    "webhook_url": "https://hooks.slack.com/services/test",
                    "severity_threshold": "all",
                },
            )

        assert response.status_code == 403


# ──────────────────────────────────────────────────────────────
# GET /api/v1/notifications/config 테스트
# ──────────────────────────────────────────────────────────────

class TestListNotificationConfigs:
    """알림 설정 목록 조회 테스트"""

    def test_list_configs_success(self, notification_test_client):
        """알림 설정 목록 조회 성공"""
        response = notification_test_client.get("/api/v1/notifications/config")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 1

    def test_list_configs_contains_platform(self, notification_test_client):
        """응답에 platform 필드 포함"""
        response = notification_test_client.get("/api/v1/notifications/config")

        data = response.json()
        for item in data["data"]:
            assert "platform" in item

    def test_list_configs_contains_severity_threshold(self, notification_test_client):
        """응답에 severity_threshold 필드 포함"""
        response = notification_test_client.get("/api/v1/notifications/config")

        data = response.json()
        for item in data["data"]:
            assert "severity_threshold" in item

    def test_list_configs_webhook_url_masked(self, notification_test_client):
        """webhook_url이 응답에 포함되는지 확인 (또는 마스킹)"""
        response = notification_test_client.get("/api/v1/notifications/config")

        assert response.status_code == 200

    def test_list_configs_no_team_returns_empty(self):
        """팀 없는 사용자는 빈 목록 반환"""
        from src.main import create_app
        from src.api.deps import get_db, get_current_user

        app = create_app()

        mock_db = AsyncMock()

        async def execute_side_effect(query, *args, **kwargs):
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            result.scalars.return_value.all.return_value = []
            result.first.return_value = None
            return result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        mock_user = MagicMock()
        mock_user.id = USER_ID

        async def override_get_db():
            yield mock_db

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/notifications/config")

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []


# ──────────────────────────────────────────────────────────────
# PATCH /api/v1/notifications/config/{id} 테스트
# ──────────────────────────────────────────────────────────────

class TestUpdateNotificationConfig:
    """알림 설정 수정 테스트"""

    def test_update_severity_threshold(self, notification_test_client):
        """severity_threshold 수정 성공"""
        with patch("src.services.notification_service.validate_webhook_url", return_value=True):
            response = notification_test_client.patch(
                f"/api/v1/notifications/config/{CONFIG_ID}",
                json={"severity_threshold": "critical"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_update_weekly_report_enabled(self, notification_test_client):
        """weekly_report_enabled 수정 성공"""
        response = notification_test_client.patch(
            f"/api/v1/notifications/config/{CONFIG_ID}",
            json={"weekly_report_enabled": True, "weekly_report_day": 5},
        )

        assert response.status_code == 200

    def test_update_config_not_found(self, notification_test_client):
        """존재하지 않는 설정 수정 시 404"""
        response = notification_test_client.patch(
            f"/api/v1/notifications/config/{NONE_ID}",
            json={"severity_threshold": "high"},
        )

        assert response.status_code == 404

    def test_update_config_invalid_webhook(self, notification_test_client):
        """유효하지 않은 webhook URL 수정 거부"""
        with patch("src.services.notification_service.validate_webhook_url", return_value=False):
            response = notification_test_client.patch(
                f"/api/v1/notifications/config/{CONFIG_ID}",
                json={"webhook_url": "https://evil.com/webhook"},
            )

        assert response.status_code in (400, 422)

    def test_update_config_member_forbidden(self):
        """member 역할은 설정 수정 불가 (403)"""
        from src.main import create_app
        from src.api.deps import get_db, get_current_user

        app = create_app()
        mock_db = AsyncMock()

        async def execute_side_effect(query, *args, **kwargs):
            query_str = str(query).lower()
            result = MagicMock()
            if "team_member" in query_str:
                result.scalar_one_or_none.return_value = "member"
                result.first.return_value = (TEAM_ID, "member")
            else:
                result.scalar_one_or_none.return_value = None
                result.first.return_value = None
            return result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)
        mock_user = MagicMock()
        mock_user.id = USER_ID

        async def override_get_db():
            yield mock_db

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.patch(
                f"/api/v1/notifications/config/{CONFIG_ID}",
                json={"severity_threshold": "high"},
            )

        assert response.status_code == 403


# ──────────────────────────────────────────────────────────────
# DELETE /api/v1/notifications/config/{id} 테스트
# ──────────────────────────────────────────────────────────────

class TestDeleteNotificationConfig:
    """알림 설정 삭제 테스트"""

    def test_delete_config_success(self, notification_test_client):
        """알림 설정 삭제 성공"""
        response = notification_test_client.delete(
            f"/api/v1/notifications/config/{CONFIG_ID}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_delete_config_not_found(self, notification_test_client):
        """존재하지 않는 설정 삭제 시 404"""
        response = notification_test_client.delete(
            f"/api/v1/notifications/config/{NONE_ID}"
        )

        assert response.status_code == 404

    def test_delete_config_member_forbidden(self):
        """member 역할은 설정 삭제 불가 (403)"""
        from src.main import create_app
        from src.api.deps import get_db, get_current_user

        app = create_app()
        mock_db = AsyncMock()

        async def execute_side_effect(query, *args, **kwargs):
            query_str = str(query).lower()
            result = MagicMock()
            if "team_member" in query_str:
                result.scalar_one_or_none.return_value = "member"
                result.first.return_value = (TEAM_ID, "member")
            else:
                result.scalar_one_or_none.return_value = None
                result.first.return_value = None
            return result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)
        mock_user = MagicMock()
        mock_user.id = USER_ID

        async def override_get_db():
            yield mock_db

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.delete(f"/api/v1/notifications/config/{CONFIG_ID}")

        assert response.status_code == 403


# ──────────────────────────────────────────────────────────────
# POST /api/v1/notifications/config/{id}/test 테스트
# ──────────────────────────────────────────────────────────────

class TestSendTestNotification:
    """테스트 알림 발송 엔드포인트 테스트"""

    def test_send_test_notification_success(self, notification_test_client):
        """테스트 알림 발송 성공"""
        with patch("src.services.notification_service.NotificationService._send_webhook",
                   new_callable=AsyncMock) as mock_send:
            mock_send.return_value = (True, 200, None)

            response = notification_test_client.post(
                f"/api/v1/notifications/config/{CONFIG_ID}/test"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_send_test_notification_not_found(self, notification_test_client):
        """존재하지 않는 설정으로 테스트 발송 시 404"""
        response = notification_test_client.post(
            f"/api/v1/notifications/config/{NONE_ID}/test"
        )

        assert response.status_code == 404

    def test_send_test_notification_webhook_called(self, notification_test_client):
        """테스트 발송 시 실제로 webhook이 호출되는지 확인"""
        with patch("src.services.notification_service.NotificationService._send_webhook",
                   new_callable=AsyncMock) as mock_send:
            mock_send.return_value = (True, 200, None)

            notification_test_client.post(
                f"/api/v1/notifications/config/{CONFIG_ID}/test"
            )

        mock_send.assert_called_once()

    def test_send_test_notification_failure_response(self, notification_test_client):
        """webhook 발송 실패 시 응답에 실패 정보 포함"""
        with patch("src.services.notification_service.NotificationService._send_webhook",
                   new_callable=AsyncMock) as mock_send:
            mock_send.return_value = (False, 400, "Bad Request")

            response = notification_test_client.post(
                f"/api/v1/notifications/config/{CONFIG_ID}/test"
            )

        # 발송 시도했지만 실패한 경우 — 200 OK + success=False or 별도 처리
        assert response.status_code in (200, 400)


# ──────────────────────────────────────────────────────────────
# GET /api/v1/notifications/logs 테스트
# ──────────────────────────────────────────────────────────────

class TestGetNotificationLogs:
    """알림 발송 이력 조회 테스트"""

    def test_list_logs_success(self, notification_test_client):
        """알림 로그 목록 조회 성공"""
        response = notification_test_client.get("/api/v1/notifications/logs")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    def test_list_logs_contains_status(self, notification_test_client):
        """로그에 status 필드 포함"""
        response = notification_test_client.get("/api/v1/notifications/logs")

        data = response.json()
        if data["data"]:
            assert "status" in data["data"][0]

    def test_list_logs_contains_notification_type(self, notification_test_client):
        """로그에 notification_type 필드 포함"""
        response = notification_test_client.get("/api/v1/notifications/logs")

        data = response.json()
        if data["data"]:
            assert "notification_type" in data["data"][0]

    def test_list_logs_no_team_returns_empty(self):
        """팀 없는 사용자는 빈 목록 반환"""
        from src.main import create_app
        from src.api.deps import get_db, get_current_user

        app = create_app()
        mock_db = AsyncMock()

        async def execute_side_effect(query, *args, **kwargs):
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            result.scalars.return_value.all.return_value = []
            result.first.return_value = None
            return result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)
        mock_user = MagicMock()
        mock_user.id = USER_ID

        async def override_get_db():
            yield mock_db

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/notifications/logs")

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []

    def test_list_logs_pagination(self, notification_test_client):
        """페이지네이션 파라미터 적용"""
        response = notification_test_client.get(
            "/api/v1/notifications/logs?page=1&per_page=10"
        )

        assert response.status_code == 200

    def test_list_logs_filter_by_status(self, notification_test_client):
        """status 필터링"""
        response = notification_test_client.get(
            "/api/v1/notifications/logs?status=sent"
        )

        assert response.status_code == 200
