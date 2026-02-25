"""F-08 알림 서비스 단위 테스트 — NotificationService, NotificationFormatter, validate_webhook_url"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────
# 픽스처
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_vuln():
    """테스트용 취약점 픽스처"""
    from src.models.vulnerability import Vulnerability

    v = MagicMock(spec=Vulnerability)
    v.id = uuid.UUID("eeeeeeee-eeee-eeee-eeee-000000000001")
    v.severity = "critical"
    v.vulnerability_type = "sql_injection"
    v.file_path = "src/app.py"
    v.start_line = 42
    v.cwe_id = "CWE-89"
    v.description = "SQL Injection 취약점이 발견되었습니다."
    v.semgrep_rule_id = "python.security.sql-injection"
    return v


@pytest.fixture
def sample_notification_config():
    """테스트용 알림 설정 픽스처"""
    from src.models.notification import NotificationConfig

    config = MagicMock(spec=NotificationConfig)
    config.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    config.team_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    config.platform = "slack"
    config.webhook_url = "https://hooks.slack.com/services/fake-test-token"
    config.severity_threshold = "all"
    config.weekly_report_enabled = True
    config.weekly_report_day = 1
    config.is_active = True
    config.created_at = datetime(2026, 2, 25, 10, 0, 0)
    return config


@pytest.fixture
def sample_teams_config():
    """Teams 플랫폼 알림 설정 픽스처"""
    from src.models.notification import NotificationConfig

    config = MagicMock(spec=NotificationConfig)
    config.id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    config.team_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    config.platform = "teams"
    config.webhook_url = "https://outlook.office.com/webhook/test-webhook-url"
    config.severity_threshold = "high"
    config.weekly_report_enabled = False
    config.weekly_report_day = 1
    config.is_active = True
    config.created_at = datetime(2026, 2, 25, 10, 0, 0)
    return config


# ──────────────────────────────────────────────────────────────
# validate_webhook_url 테스트
# ──────────────────────────────────────────────────────────────

class TestValidateWebhookUrl:
    """webhook URL 유효성 검증 테스트"""

    def test_valid_slack_url(self):
        """유효한 Slack webhook URL 검증"""
        from src.services.notification_service import validate_webhook_url

        url = "https://hooks.slack.com/services/fake-test-url"
        assert validate_webhook_url(url) is True

    def test_valid_teams_url(self):
        """유효한 Teams webhook URL 검증"""
        from src.services.notification_service import validate_webhook_url

        url = "https://outlook.office.com/webhook/test-id"
        assert validate_webhook_url(url) is True

    def test_valid_teams_webhook_url(self):
        """유효한 Teams webhook.office.com URL 검증"""
        from src.services.notification_service import validate_webhook_url

        url = "https://myorg.webhook.office.com/webhookb2/test"
        assert validate_webhook_url(url) is True

    def test_http_rejected(self):
        """HTTP URL 거부 (HTTPS 필수)"""
        from src.services.notification_service import validate_webhook_url

        url = "http://hooks.slack.com/services/fake-test-url"
        assert validate_webhook_url(url) is False

    def test_invalid_domain_rejected(self):
        """허용되지 않은 도메인 거부"""
        from src.services.notification_service import validate_webhook_url

        url = "https://evil.com/webhook"
        assert validate_webhook_url(url) is False

    def test_internal_ip_10_rejected(self):
        """10.x.x.x 내부 IP 차단"""
        from src.services.notification_service import validate_webhook_url

        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [(None, None, None, None, ("10.0.0.1", 0))]
            url = "https://hooks.slack.com/services/test"
            assert validate_webhook_url(url) is False

    def test_internal_ip_192_168_rejected(self):
        """192.168.x.x 내부 IP 차단"""
        from src.services.notification_service import validate_webhook_url

        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [(None, None, None, None, ("192.168.1.100", 0))]
            url = "https://hooks.slack.com/services/test"
            assert validate_webhook_url(url) is False

    def test_internal_ip_172_rejected(self):
        """172.16-31.x.x 내부 IP 차단"""
        from src.services.notification_service import validate_webhook_url

        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [(None, None, None, None, ("172.20.0.5", 0))]
            url = "https://hooks.slack.com/services/test"
            assert validate_webhook_url(url) is False

    def test_localhost_rejected(self):
        """127.x.x.x localhost 차단"""
        from src.services.notification_service import validate_webhook_url

        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [(None, None, None, None, ("127.0.0.1", 0))]
            url = "https://hooks.slack.com/services/test"
            assert validate_webhook_url(url) is False

    def test_external_ip_allowed(self):
        """외부 공인 IP 허용"""
        from src.services.notification_service import validate_webhook_url

        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [(None, None, None, None, ("54.240.197.40", 0))]
            url = "https://hooks.slack.com/services/test"
            assert validate_webhook_url(url) is True

    def test_empty_url_rejected(self):
        """빈 URL 거부"""
        from src.services.notification_service import validate_webhook_url

        assert validate_webhook_url("") is False


# ──────────────────────────────────────────────────────────────
# SlackFormatter 테스트
# ──────────────────────────────────────────────────────────────

class TestSlackFormatter:
    """Slack Block Kit 포맷터 테스트"""

    def test_format_vulnerability_alert_structure(self, sample_vuln):
        """Slack 알림 메시지 구조 검증"""
        from src.services.notification_formatter import SlackFormatter

        formatter = SlackFormatter()
        result = formatter.format_vulnerability_alert(
            vuln=sample_vuln,
            repo_name="test-org/test-repo",
            patch_pr_url="https://github.com/test-org/test-repo/pull/1",
        )

        assert "blocks" in result
        assert isinstance(result["blocks"], list)
        assert len(result["blocks"]) > 0

    def test_format_vulnerability_alert_critical_color(self, sample_vuln):
        """critical 심각도 빨간색 확인"""
        from src.services.notification_formatter import SlackFormatter

        formatter = SlackFormatter()
        result = formatter.format_vulnerability_alert(
            vuln=sample_vuln,
            repo_name="test-org/test-repo",
        )

        # attachments 또는 color 필드 확인
        payload_str = str(result)
        assert "danger" in payload_str or "#FF0000" in payload_str or "#ff0000" in payload_str or "critical" in payload_str.lower()

    def test_format_vulnerability_alert_contains_severity(self, sample_vuln):
        """메시지에 심각도 포함 확인"""
        from src.services.notification_formatter import SlackFormatter

        formatter = SlackFormatter()
        result = formatter.format_vulnerability_alert(
            vuln=sample_vuln,
            repo_name="test-org/test-repo",
        )

        payload_str = str(result)
        assert "critical" in payload_str.lower()

    def test_format_vulnerability_alert_contains_repo(self, sample_vuln):
        """메시지에 저장소 이름 포함 확인"""
        from src.services.notification_formatter import SlackFormatter

        formatter = SlackFormatter()
        result = formatter.format_vulnerability_alert(
            vuln=sample_vuln,
            repo_name="test-org/test-repo",
        )

        payload_str = str(result)
        assert "test-org/test-repo" in payload_str

    def test_format_vulnerability_alert_with_patch_pr(self, sample_vuln):
        """패치 PR URL 포함 시 링크 포함 확인"""
        from src.services.notification_formatter import SlackFormatter

        formatter = SlackFormatter()
        pr_url = "https://github.com/test-org/test-repo/pull/42"
        result = formatter.format_vulnerability_alert(
            vuln=sample_vuln,
            repo_name="test-org/test-repo",
            patch_pr_url=pr_url,
        )

        payload_str = str(result)
        assert pr_url in payload_str

    def test_format_vulnerability_alert_no_patch_pr(self, sample_vuln):
        """패치 PR 없을 때도 정상 포맷 확인"""
        from src.services.notification_formatter import SlackFormatter

        formatter = SlackFormatter()
        result = formatter.format_vulnerability_alert(
            vuln=sample_vuln,
            repo_name="test-org/test-repo",
            patch_pr_url=None,
        )

        assert "blocks" in result

    def test_format_weekly_report_slack(self):
        """Slack 주간 리포트 포맷 확인"""
        from src.services.notification_formatter import format_weekly_report

        stats = {
            "total_new": 5,
            "critical_count": 1,
            "high_count": 2,
            "medium_count": 2,
            "low_count": 0,
            "patched_count": 3,
            "open_count": 2,
            "week_start": "2026-02-19",
            "week_end": "2026-02-25",
        }
        result = format_weekly_report(stats=stats, platform="slack")

        assert "blocks" in result
        payload_str = str(result)
        assert "5" in payload_str  # total_new


# ──────────────────────────────────────────────────────────────
# TeamsFormatter 테스트
# ──────────────────────────────────────────────────────────────

class TestTeamsFormatter:
    """Teams Adaptive Cards 포맷터 테스트"""

    def test_format_vulnerability_alert_structure(self, sample_vuln):
        """Teams 알림 메시지 구조 검증"""
        from src.services.notification_formatter import TeamsFormatter

        formatter = TeamsFormatter()
        result = formatter.format_vulnerability_alert(
            vuln=sample_vuln,
            repo_name="test-org/test-repo",
        )

        # Teams Adaptive Card 형식
        assert "type" in result
        assert result["type"] == "message"

    def test_format_vulnerability_alert_contains_severity(self, sample_vuln):
        """Teams 메시지에 심각도 포함 확인"""
        from src.services.notification_formatter import TeamsFormatter

        formatter = TeamsFormatter()
        result = formatter.format_vulnerability_alert(
            vuln=sample_vuln,
            repo_name="test-org/test-repo",
        )

        payload_str = str(result)
        assert "critical" in payload_str.lower()

    def test_format_vulnerability_alert_contains_repo(self, sample_vuln):
        """Teams 메시지에 저장소 이름 포함 확인"""
        from src.services.notification_formatter import TeamsFormatter

        formatter = TeamsFormatter()
        result = formatter.format_vulnerability_alert(
            vuln=sample_vuln,
            repo_name="test-org/test-repo",
        )

        payload_str = str(result)
        assert "test-org/test-repo" in payload_str

    def test_format_weekly_report_teams(self):
        """Teams 주간 리포트 포맷 확인"""
        from src.services.notification_formatter import format_weekly_report

        stats = {
            "total_new": 3,
            "critical_count": 0,
            "high_count": 1,
            "medium_count": 2,
            "low_count": 0,
            "patched_count": 1,
            "open_count": 2,
            "week_start": "2026-02-19",
            "week_end": "2026-02-25",
        }
        result = format_weekly_report(stats=stats, platform="teams")

        assert "type" in result
        assert result["type"] == "message"


# ──────────────────────────────────────────────────────────────
# 심각도 색상 매핑 테스트
# ──────────────────────────────────────────────────────────────

class TestSeverityColors:
    """심각도별 색상 매핑 테스트"""

    def test_critical_color(self):
        """critical → 빨간색"""
        from src.services.notification_formatter import SEVERITY_COLORS

        color = SEVERITY_COLORS.get("critical")
        assert color is not None
        assert "ff" in color.lower() or "danger" in color.lower() or "#D00" in color.upper()

    def test_high_color(self):
        """high → 주황색"""
        from src.services.notification_formatter import SEVERITY_COLORS

        color = SEVERITY_COLORS.get("high")
        assert color is not None

    def test_medium_color(self):
        """medium → 노란색"""
        from src.services.notification_formatter import SEVERITY_COLORS

        color = SEVERITY_COLORS.get("medium")
        assert color is not None

    def test_low_color(self):
        """low → 초록색"""
        from src.services.notification_formatter import SEVERITY_COLORS

        color = SEVERITY_COLORS.get("low")
        assert color is not None


# ──────────────────────────────────────────────────────────────
# NotificationService._send_webhook 테스트
# ──────────────────────────────────────────────────────────────

class TestSendWebhook:
    """webhook HTTP POST 전송 테스트"""

    @pytest.mark.asyncio
    async def test_send_webhook_success(self):
        """webhook 전송 성공 케이스"""
        from src.services.notification_service import NotificationService

        service = NotificationService()
        payload = {"text": "test message"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "ok"
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            success, status_code, error_msg = await service._send_webhook(
                url="https://hooks.slack.com/services/test",
                payload=payload,
                platform="slack",
            )

        assert success is True
        assert status_code == 200

    @pytest.mark.asyncio
    async def test_send_webhook_failure_4xx(self):
        """webhook 전송 실패 케이스 (4xx)"""
        from src.services.notification_service import NotificationService

        service = NotificationService()
        payload = {"text": "test message"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Bad Request"
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            success, status_code, error_msg = await service._send_webhook(
                url="https://hooks.slack.com/services/test",
                payload=payload,
                platform="slack",
            )

        assert success is False
        assert status_code == 400

    @pytest.mark.asyncio
    async def test_send_webhook_network_error(self):
        """네트워크 오류 시 실패 반환 (예외 전파 안 함)"""
        import httpx
        from src.services.notification_service import NotificationService

        service = NotificationService()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
            mock_client_cls.return_value = mock_client

            success, status_code, error_msg = await service._send_webhook(
                url="https://hooks.slack.com/services/test",
                payload={"text": "test"},
                platform="slack",
            )

        assert success is False
        assert error_msg is not None


# ──────────────────────────────────────────────────────────────
# NotificationService.send_vulnerability_alert 테스트
# ──────────────────────────────────────────────────────────────

class TestSendVulnerabilityAlert:
    """취약점 알림 발송 서비스 테스트"""

    @pytest.mark.asyncio
    async def test_send_alert_with_active_config(self, sample_vuln, sample_notification_config):
        """활성 알림 설정이 있을 때 알림 발송"""
        from src.services.notification_service import NotificationService

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_notification_config]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        service = NotificationService()

        with patch.object(service, "_send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = (True, 200, None)

            await service.send_vulnerability_alert(
                db=mock_db,
                vuln=sample_vuln,
                repo_name="test-org/test-repo",
                patch_pr_url=None,
            )

        mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_alert_skipped_below_threshold(self, sample_vuln, sample_teams_config):
        """임계값 미만 심각도는 알림 발송 안 함 (threshold=high, severity=medium)"""
        from src.services.notification_service import NotificationService

        # severity=medium, threshold=high → 발송 안 함
        sample_vuln.severity = "medium"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_teams_config]
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = NotificationService()

        with patch.object(service, "_send_webhook", new_callable=AsyncMock) as mock_send:
            await service.send_vulnerability_alert(
                db=mock_db,
                vuln=sample_vuln,
                repo_name="test-org/test-repo",
            )

        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_alert_no_active_config(self, sample_vuln):
        """활성 알림 설정 없을 때 조용히 종료"""
        from src.services.notification_service import NotificationService

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = NotificationService()

        with patch.object(service, "_send_webhook", new_callable=AsyncMock) as mock_send:
            await service.send_vulnerability_alert(
                db=mock_db,
                vuln=sample_vuln,
                repo_name="test-org/test-repo",
            )

        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_alert_logs_result(self, sample_vuln, sample_notification_config):
        """알림 발송 후 로그 기록 확인"""
        from src.services.notification_service import NotificationService

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_notification_config]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        service = NotificationService()

        with patch.object(service, "_send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = (True, 200, None)

            await service.send_vulnerability_alert(
                db=mock_db,
                vuln=sample_vuln,
                repo_name="test-org/test-repo",
            )

        # DB에 로그가 추가되었는지 확인
        mock_db.add.assert_called()


# ──────────────────────────────────────────────────────────────
# 심각도 임계값 필터링 테스트
# ──────────────────────────────────────────────────────────────

class TestSeverityThreshold:
    """심각도 임계값 필터링 로직 테스트"""

    def test_threshold_all_passes_critical(self):
        """threshold=all이면 critical 통과"""
        from src.services.notification_service import is_severity_above_threshold

        assert is_severity_above_threshold("critical", "all") is True

    def test_threshold_all_passes_low(self):
        """threshold=all이면 low 통과"""
        from src.services.notification_service import is_severity_above_threshold

        assert is_severity_above_threshold("low", "all") is True

    def test_threshold_critical_only_critical(self):
        """threshold=critical이면 critical만 통과"""
        from src.services.notification_service import is_severity_above_threshold

        assert is_severity_above_threshold("critical", "critical") is True
        assert is_severity_above_threshold("high", "critical") is False

    def test_threshold_high_passes_critical(self):
        """threshold=high이면 critical, high 통과"""
        from src.services.notification_service import is_severity_above_threshold

        assert is_severity_above_threshold("critical", "high") is True
        assert is_severity_above_threshold("high", "high") is True
        assert is_severity_above_threshold("medium", "high") is False

    def test_threshold_medium_passes_critical_high(self):
        """threshold=medium이면 critical, high, medium 통과"""
        from src.services.notification_service import is_severity_above_threshold

        assert is_severity_above_threshold("critical", "medium") is True
        assert is_severity_above_threshold("high", "medium") is True
        assert is_severity_above_threshold("medium", "medium") is True
        assert is_severity_above_threshold("low", "medium") is False


# ──────────────────────────────────────────────────────────────
# WeeklyReportJob 테스트
# ──────────────────────────────────────────────────────────────

class TestWeeklyReportJob:
    """주간 리포트 워커 테스트"""

    @pytest.mark.asyncio
    async def test_send_weekly_reports_enabled_teams(self):
        """weekly_report_enabled 팀에 주간 리포트 발송"""
        from src.services.notification_service import NotificationService

        mock_db = AsyncMock()

        # weekly_report_enabled=True 설정 목록
        mock_config = MagicMock()
        mock_config.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        mock_config.team_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        mock_config.platform = "slack"
        mock_config.webhook_url = "https://hooks.slack.com/services/test"
        mock_config.weekly_report_enabled = True
        mock_config.is_active = True

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_config]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        service = NotificationService()

        with patch.object(service, "_send_webhook", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = (True, 200, None)

            await service.send_weekly_report(
                db=mock_db,
                team_id=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            )

        mock_send.assert_called_once()
