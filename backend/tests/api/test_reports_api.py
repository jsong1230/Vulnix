"""F-10 리포트 API 통합 테스트 — RED 단계

POST /api/v1/reports/generate, GET /api/v1/reports/history,
GET /api/v1/reports/{id}/download, POST/GET/PATCH/DELETE /api/v1/reports/config
엔드포인트를 대상으로 실패하는 테스트를 작성한다.

구현이 없으므로 모두 FAIL(404 또는 AssertionError)이어야 한다.
"""

import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────
# 공통 UUID 상수
# ──────────────────────────────────────────────────────────────

TEAM_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
REPORT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CONFIG_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
NONE_ID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")


# ──────────────────────────────────────────────────────────────
# Mock 헬퍼
# ──────────────────────────────────────────────────────────────

def _make_mock_report_history(
    report_id: uuid.UUID = REPORT_ID,
    report_type: str = "ciso",
    status: str = "completed",
    format: str = "pdf",
) -> MagicMock:
    """ReportHistory Mock 생성 헬퍼."""
    history = MagicMock()
    history.id = report_id
    history.team_id = TEAM_ID
    history.config_id = CONFIG_ID
    history.report_type = report_type
    history.format = format
    history.status = status
    history.file_path = f"/data/reports/{report_id}.{format}"
    history.file_size_bytes = 245760
    history.period_start = date(2026, 2, 1)
    history.period_end = date(2026, 2, 28)
    history.email_sent_at = None
    history.email_recipients = None
    history.error_message = None
    history.metadata = {
        "security_score": 75.5,
        "total_vulnerabilities": 42,
        "critical_count": 3,
    }
    history.generated_by = USER_ID
    history.created_at = datetime(2026, 2, 25, 10, 0, 0)
    return history


def _make_mock_report_config(
    config_id: uuid.UUID = CONFIG_ID,
    report_type: str = "ciso",
    schedule: str = "monthly",
    is_active: bool = True,
) -> MagicMock:
    """ReportConfig Mock 생성 헬퍼."""
    config = MagicMock()
    config.id = config_id
    config.team_id = TEAM_ID
    config.report_type = report_type
    config.schedule = schedule
    config.email_recipients = ["ciso@company.com"]
    config.is_active = is_active
    config.last_generated_at = None
    config.next_generation_at = datetime(2026, 3, 1, 0, 0, 0)
    config.created_by = USER_ID
    config.created_at = datetime(2026, 2, 25, 10, 0, 0)
    config.updated_at = datetime(2026, 2, 25, 10, 0, 0)
    return config


# ──────────────────────────────────────────────────────────────
# 리포트 API 테스트 클라이언트 픽스처
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def reports_test_client():
    """리포트 API 테스트용 TestClient 픽스처 (admin 역할)."""
    from src.main import create_app
    from src.api.deps import get_db, get_current_user

    app = create_app()
    mock_db = _build_reports_mock_db()

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


@pytest.fixture
def reports_test_client_member():
    """리포트 API 테스트용 TestClient 픽스처 (member 역할 — 403 테스트용)."""
    from src.main import create_app
    from src.api.deps import get_db, get_current_user

    app = create_app()

    mock_db = AsyncMock()

    async def member_execute(query, *args, **kwargs):
        query_str = str(query).lower()
        result = MagicMock()
        if "team_member" in query_str:
            if "team_member.role" in query_str:
                result.scalar_one_or_none.return_value = "member"
                result.first.return_value = (TEAM_ID, "member")
            elif "team_member.team_id" in query_str:
                result.scalar_one_or_none.return_value = TEAM_ID
                result.scalars.return_value.all.return_value = [TEAM_ID]
                result.first.return_value = (TEAM_ID, "member")
            else:
                result.scalar_one_or_none.return_value = "member"
        else:
            result.scalar_one_or_none.return_value = None
            result.scalars.return_value.all.return_value = []
        return result

    mock_db.execute = AsyncMock(side_effect=member_execute)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def override_get_db():
        yield mock_db

    mock_user = MagicMock()
    mock_user.id = USER_ID

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def _build_reports_mock_db() -> AsyncMock:
    """리포트 API 테스트용 스마트 Mock DB 세션 생성."""
    mock_history = _make_mock_report_history(REPORT_ID, "ciso", "completed")
    mock_history_generating = _make_mock_report_history(
        uuid.UUID("cccccccc-0000-0000-0000-000000000001"), "ciso", "generating"
    )
    mock_config = _make_mock_report_config(CONFIG_ID, "ciso", "monthly")
    mock_config_2 = _make_mock_report_config(
        uuid.UUID("dddddddd-0000-0000-0000-000000000001"), "csap", "weekly"
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.close = AsyncMock()
    mock_db.refresh = AsyncMock()
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
                result.scalar_one_or_none.return_value = "owner"
                result.scalars.return_value.all.return_value = ["owner"]
                result.first.return_value = (TEAM_ID, "owner")
            return result

        # report_history 테이블 조회
        if "report_history" in query_str:
            if NONE_ID in all_uuids:
                return _make_result(None)
            if REPORT_ID in all_uuids:
                return _make_result(mock_history)
            if mock_history_generating.id in all_uuids:
                return _make_result(mock_history_generating)
            # 목록 조회
            return _make_result([mock_history])

        # report_config 테이블 조회
        if "report_config" in query_str:
            if NONE_ID in all_uuids:
                return _make_result(None)
            if CONFIG_ID in all_uuids:
                return _make_result(mock_config)
            # 팀 기준 중복 확인: 동일 report_type 존재 여부
            return _make_result([mock_config, mock_config_2])

        return _make_result([])

    mock_db.execute = AsyncMock(side_effect=smart_execute)
    return mock_db


# ──────────────────────────────────────────────────────────────
# POST /api/v1/reports/generate 테스트 (I-1001, I-1002, I-1003, I-1004)
# ──────────────────────────────────────────────────────────────

class TestGenerateReport:
    """리포트 수동 생성 엔드포인트 테스트"""

    def test_ciso_pdf_리포트_생성_성공(self, reports_test_client):
        """I-1001: CISO PDF 리포트 생성 요청 → 202, report_id 반환."""
        with patch("src.api.v1.reports.enqueue_report_generation", return_value=None):
            response = reports_test_client.post(
                "/api/v1/reports/generate",
                json={
                    "report_type": "ciso",
                    "period_start": "2026-02-01",
                    "period_end": "2026-02-28",
                    "format": "pdf",
                    "send_email": False,
                    "email_recipients": [],
                },
            )

        assert response.status_code == 202, \
            f"리포트 생성 요청 시 202를 반환해야 한다 (실제: {response.status_code})"
        data = response.json()
        assert data["success"] is True
        assert "report_id" in data["data"], "응답에 report_id가 포함되어야 한다"
        assert data["data"]["status"] == "generating", \
            "생성 직후 상태는 'generating'이어야 한다"

    def test_잘못된_report_type_422(self, reports_test_client):
        """I-1003: 유효하지 않은 report_type → 422 반환."""
        response = reports_test_client.post(
            "/api/v1/reports/generate",
            json={
                "report_type": "invalid_type",
                "period_start": "2026-02-01",
                "period_end": "2026-02-28",
                "format": "pdf",
                "send_email": False,
                "email_recipients": [],
            },
        )

        assert response.status_code == 422, \
            f"잘못된 report_type 시 422를 반환해야 한다 (실제: {response.status_code})"

    def test_시작일이_종료일보다_늦은_경우_422(self, reports_test_client):
        """I-1004: period_start > period_end → 422 반환."""
        response = reports_test_client.post(
            "/api/v1/reports/generate",
            json={
                "report_type": "ciso",
                "period_start": "2026-03-01",
                "period_end": "2026-02-01",
                "format": "pdf",
                "send_email": False,
                "email_recipients": [],
            },
        )

        assert response.status_code == 422, \
            f"시작일이 종료일보다 늦을 때 422를 반환해야 한다 (실제: {response.status_code})"

    def test_member_역할_리포트_생성_403(self, reports_test_client_member):
        """I-1002: member 역할은 리포트 생성 불가 → 403 반환."""
        response = reports_test_client_member.post(
            "/api/v1/reports/generate",
            json={
                "report_type": "ciso",
                "period_start": "2026-02-01",
                "period_end": "2026-02-28",
                "format": "pdf",
                "send_email": False,
                "email_recipients": [],
            },
        )

        assert response.status_code == 403, \
            f"member 역할은 리포트 생성 시 403을 반환해야 한다 (실제: {response.status_code})"

    def test_인증_없이_접근_401(self):
        """인증 없이 접근 시 401 반환."""
        from src.main import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        # dependency_overrides 없이 — 인증 미들웨어가 401 반환
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/reports/generate",
                json={
                    "report_type": "ciso",
                    "period_start": "2026-02-01",
                    "period_end": "2026-02-28",
                    "format": "pdf",
                    "send_email": False,
                    "email_recipients": [],
                },
            )

        assert response.status_code == 401, \
            f"인증 없이 접근 시 401을 반환해야 한다 (실제: {response.status_code})"

    def test_기간_1년_초과_422(self, reports_test_client):
        """period 범위가 1년 초과 시 422 반환 (경계 조건)."""
        response = reports_test_client.post(
            "/api/v1/reports/generate",
            json={
                "report_type": "ciso",
                "period_start": "2024-01-01",
                "period_end": "2026-02-28",
                "format": "pdf",
                "send_email": False,
                "email_recipients": [],
            },
        )

        assert response.status_code == 422, \
            f"1년 초과 기간 시 422를 반환해야 한다 (실제: {response.status_code})"

    def test_send_email_true이고_수신자_빈_배열_422(self, reports_test_client):
        """send_email=True이고 email_recipients 빈 배열 → 422."""
        response = reports_test_client.post(
            "/api/v1/reports/generate",
            json={
                "report_type": "ciso",
                "period_start": "2026-02-01",
                "period_end": "2026-02-28",
                "format": "pdf",
                "send_email": True,
                "email_recipients": [],
            },
        )

        assert response.status_code == 422, \
            f"send_email=True이고 수신자 없을 때 422를 반환해야 한다 (실제: {response.status_code})"

    def test_잘못된_이메일_형식_422(self, reports_test_client):
        """email_recipients에 잘못된 이메일 형식 포함 시 422."""
        response = reports_test_client.post(
            "/api/v1/reports/generate",
            json={
                "report_type": "ciso",
                "period_start": "2026-02-01",
                "period_end": "2026-02-28",
                "format": "pdf",
                "send_email": True,
                "email_recipients": ["not-an-email"],
            },
        )

        assert response.status_code == 422, \
            f"잘못된 이메일 형식 시 422를 반환해야 한다 (실제: {response.status_code})"

    def test_csap_리포트_생성_성공(self, reports_test_client):
        """CSAP 리포트 생성 요청 → 202."""
        with patch("src.api.v1.reports.enqueue_report_generation", return_value=None):
            response = reports_test_client.post(
                "/api/v1/reports/generate",
                json={
                    "report_type": "csap",
                    "period_start": "2026-02-01",
                    "period_end": "2026-02-28",
                    "format": "pdf",
                    "send_email": False,
                    "email_recipients": [],
                },
            )

        assert response.status_code == 202, \
            f"CSAP 리포트 생성 시 202를 반환해야 한다 (실제: {response.status_code})"

    def test_iso27001_리포트_생성_성공(self, reports_test_client):
        """ISO 27001 리포트 생성 요청 → 202."""
        with patch("src.api.v1.reports.enqueue_report_generation", return_value=None):
            response = reports_test_client.post(
                "/api/v1/reports/generate",
                json={
                    "report_type": "iso27001",
                    "period_start": "2026-02-01",
                    "period_end": "2026-02-28",
                    "format": "json",
                    "send_email": False,
                    "email_recipients": [],
                },
            )

        assert response.status_code == 202, \
            f"ISO 27001 리포트 생성 시 202를 반환해야 한다 (실제: {response.status_code})"


# ──────────────────────────────────────────────────────────────
# GET /api/v1/reports/history 테스트 (I-1020, I-1021)
# ──────────────────────────────────────────────────────────────

class TestGetReportHistory:
    """리포트 이력 조회 엔드포인트 테스트"""

    def test_이력_조회_성공(self, reports_test_client):
        """I-1020: 리포트 이력 조회 → 200, 리스트 반환."""
        response = reports_test_client.get("/api/v1/reports/history")

        assert response.status_code == 200, \
            f"리포트 이력 조회 시 200을 반환해야 한다 (실제: {response.status_code})"
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list), "data 필드가 리스트여야 한다"

    def test_이력_응답_필수_필드_포함(self, reports_test_client):
        """응답 항목에 id, report_type, status, created_at 필드가 포함되어야 한다."""
        response = reports_test_client.get("/api/v1/reports/history")

        assert response.status_code == 200
        data = response.json()
        if data["data"]:
            item = data["data"][0]
            assert "id" in item, "응답에 id 필드가 있어야 한다"
            assert "report_type" in item, "응답에 report_type 필드가 있어야 한다"
            assert "status" in item, "응답에 status 필드가 있어야 한다"
            assert "created_at" in item, "응답에 created_at 필드가 있어야 한다"

    def test_이력_유형별_필터링(self, reports_test_client):
        """I-1021: report_type 쿼리 파라미터 필터링 → 200."""
        response = reports_test_client.get("/api/v1/reports/history?report_type=ciso")

        assert response.status_code == 200, \
            f"report_type 필터 조회 시 200을 반환해야 한다 (실제: {response.status_code})"
        data = response.json()
        assert data["success"] is True

    def test_이력_페이지네이션(self, reports_test_client):
        """페이지네이션 파라미터 지원 확인."""
        response = reports_test_client.get("/api/v1/reports/history?page=1&per_page=10")

        assert response.status_code == 200, \
            f"페이지네이션 파라미터 요청 시 200을 반환해야 한다 (실제: {response.status_code})"

    def test_이력_인증_없이_접근_401(self):
        """인증 없이 이력 조회 시 401."""
        from src.main import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/reports/history")

        assert response.status_code == 401, \
            f"인증 없이 이력 조회 시 401을 반환해야 한다 (실제: {response.status_code})"


# ──────────────────────────────────────────────────────────────
# GET /api/v1/reports/{id}/download 테스트 (I-1022, I-1023, I-1024, I-1025)
# ──────────────────────────────────────────────────────────────

class TestDownloadReport:
    """리포트 파일 다운로드 엔드포인트 테스트"""

    def test_pdf_다운로드_성공(self, reports_test_client, tmp_path):
        """I-1022: PDF 리포트 다운로드 → 200, Content-Type: application/pdf."""
        import tempfile, os

        # 임시 PDF 파일 생성
        pdf_file = tmp_path / "test_report.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%%EOF\n")

        # Mock DB에서 파일 경로를 tmp 파일로 설정
        mock_history = _make_mock_report_history(REPORT_ID, "ciso", "completed", "pdf")
        mock_history.file_path = str(pdf_file)

        with patch("src.api.v1.reports.get_report_by_id", return_value=mock_history):
            response = reports_test_client.get(f"/api/v1/reports/{REPORT_ID}/download")

        assert response.status_code == 200, \
            f"PDF 다운로드 시 200을 반환해야 한다 (실제: {response.status_code})"
        assert "application/pdf" in response.headers.get("content-type", ""), \
            f"Content-Type이 application/pdf이어야 한다 (실제: {response.headers.get('content-type')})"

    def test_존재하지_않는_id_404(self, reports_test_client):
        """I-1024 (변형): 존재하지 않는 리포트 ID 다운로드 → 404."""
        response = reports_test_client.get(f"/api/v1/reports/{NONE_ID}/download")

        assert response.status_code == 404, \
            f"존재하지 않는 리포트 다운로드 시 404를 반환해야 한다 (실제: {response.status_code})"

    def test_생성중_리포트_다운로드_409(self, reports_test_client):
        """I-1023: status='generating' 리포트 다운로드 시도 → 409."""
        generating_id = uuid.UUID("cccccccc-0000-0000-0000-000000000001")

        mock_history_generating = _make_mock_report_history(
            generating_id, "ciso", "generating"
        )

        with patch("src.api.v1.reports.get_report_by_id", return_value=mock_history_generating):
            response = reports_test_client.get(f"/api/v1/reports/{generating_id}/download")

        assert response.status_code == 409, \
            f"생성 중 리포트 다운로드 시 409를 반환해야 한다 (실제: {response.status_code})"

    def test_다른_팀_리포트_404(self, reports_test_client):
        """I-1024: 다른 팀의 리포트 접근 → 404."""
        other_team_report_id = uuid.UUID("eeeeeeee-0000-0000-0000-000000000001")

        mock_other_history = _make_mock_report_history(other_team_report_id, "ciso", "completed")
        mock_other_history.team_id = uuid.UUID("11111111-0000-0000-0000-000000000001")

        with patch("src.api.v1.reports.get_report_by_id", return_value=mock_other_history):
            response = reports_test_client.get(f"/api/v1/reports/{other_team_report_id}/download")

        assert response.status_code == 404, \
            f"다른 팀의 리포트 접근 시 404를 반환해야 한다 (실제: {response.status_code})"

    def test_json_다운로드_성공(self, reports_test_client, tmp_path):
        """I-1025: JSON 리포트 다운로드 → 200, Content-Type: application/json."""
        json_report_id = uuid.UUID("55555555-0000-0000-0000-000000000001")

        # 임시 JSON 파일 생성
        json_file = tmp_path / "test_report.json"
        json_file.write_text('{"security_score": 75.5}', encoding="utf-8")

        mock_json_history = _make_mock_report_history(json_report_id, "csap", "completed", "json")
        mock_json_history.file_path = str(json_file)

        with patch("src.api.v1.reports.get_report_by_id", return_value=mock_json_history):
            response = reports_test_client.get(f"/api/v1/reports/{json_report_id}/download")

        assert response.status_code == 200, \
            f"JSON 다운로드 시 200을 반환해야 한다 (실제: {response.status_code})"
        assert "application/json" in response.headers.get("content-type", ""), \
            f"JSON 리포트의 Content-Type이 application/json이어야 한다 (실제: {response.headers.get('content-type')})"

    def test_다운로드_인증_없이_접근_401(self):
        """인증 없이 다운로드 시도 → 401."""
        from src.main import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(f"/api/v1/reports/{REPORT_ID}/download")

        assert response.status_code == 401, \
            f"인증 없이 다운로드 시 401을 반환해야 한다 (실제: {response.status_code})"


# ──────────────────────────────────────────────────────────────
# POST /api/v1/reports/config 테스트 (I-1014, I-1015, I-1016)
# ──────────────────────────────────────────────────────────────

class TestCreateReportConfig:
    """리포트 스케줄 설정 생성 테스트"""

    def test_주간_스케줄_설정_생성_성공(self, reports_test_client):
        """I-1014: 주간 스케줄 설정 생성 → 201, next_generation_at 포함."""
        response = reports_test_client.post(
            "/api/v1/reports/config",
            json={
                "report_type": "ciso",
                "schedule": "weekly",
                "email_recipients": ["ciso@company.com"],
                "is_active": True,
            },
        )

        assert response.status_code in (200, 201), \
            f"주간 스케줄 설정 생성 시 200 또는 201을 반환해야 한다 (실제: {response.status_code})"
        data = response.json()
        assert data["success"] is True
        assert "next_generation_at" in data["data"], \
            "응답에 next_generation_at이 포함되어야 한다"

    def test_월간_스케줄_설정_생성_성공(self, reports_test_client):
        """I-1015: 월간 스케줄 설정 생성 → 201."""
        response = reports_test_client.post(
            "/api/v1/reports/config",
            json={
                "report_type": "csap",
                "schedule": "monthly",
                "email_recipients": ["csap@company.com"],
                "is_active": True,
            },
        )

        assert response.status_code in (200, 201), \
            f"월간 스케줄 설정 생성 시 200 또는 201을 반환해야 한다 (실제: {response.status_code})"

    def test_분기_스케줄_설정_생성_성공(self, reports_test_client):
        """I-1016: 분기 스케줄 설정 생성 → 201."""
        response = reports_test_client.post(
            "/api/v1/reports/config",
            json={
                "report_type": "iso27001",
                "schedule": "quarterly",
                "email_recipients": ["iso@company.com"],
                "is_active": True,
            },
        )

        assert response.status_code in (200, 201), \
            f"분기 스케줄 설정 생성 시 200 또는 201을 반환해야 한다 (실제: {response.status_code})"

    def test_잘못된_schedule_422(self, reports_test_client):
        """지원하지 않는 schedule 값 → 422."""
        response = reports_test_client.post(
            "/api/v1/reports/config",
            json={
                "report_type": "ciso",
                "schedule": "daily",
                "email_recipients": [],
                "is_active": True,
            },
        )

        assert response.status_code == 422, \
            f"지원하지 않는 schedule 시 422를 반환해야 한다 (실제: {response.status_code})"

    def test_member_역할_설정_생성_403(self, reports_test_client_member):
        """member 역할은 설정 생성 불가 → 403."""
        response = reports_test_client_member.post(
            "/api/v1/reports/config",
            json={
                "report_type": "ciso",
                "schedule": "monthly",
                "email_recipients": [],
                "is_active": True,
            },
        )

        assert response.status_code == 403, \
            f"member 역할은 설정 생성 시 403을 반환해야 한다 (실제: {response.status_code})"

    def test_중복_config_생성_409(self, reports_test_client):
        """동일 team_id + report_type으로 중복 config 생성 시 409."""
        from sqlalchemy.exc import IntegrityError

        with patch("src.api.v1.reports.create_report_config",
                   side_effect=IntegrityError("unique violation", {}, None)):
            response = reports_test_client.post(
                "/api/v1/reports/config",
                json={
                    "report_type": "ciso",
                    "schedule": "monthly",
                    "email_recipients": [],
                    "is_active": True,
                },
            )

        assert response.status_code == 409, \
            f"중복 config 생성 시 409를 반환해야 한다 (실제: {response.status_code})"


# ──────────────────────────────────────────────────────────────
# GET /api/v1/reports/config 테스트 (I-1016a)
# ──────────────────────────────────────────────────────────────

class TestGetReportConfigs:
    """리포트 스케줄 설정 목록 조회 테스트"""

    def test_설정_목록_조회_성공(self, reports_test_client):
        """I-1016a: 설정 목록 조회 → 200, 리스트 반환."""
        response = reports_test_client.get("/api/v1/reports/config")

        assert response.status_code == 200, \
            f"설정 목록 조회 시 200을 반환해야 한다 (실제: {response.status_code})"
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list), "data 필드가 리스트여야 한다"

    def test_설정_목록_필수_필드_포함(self, reports_test_client):
        """응답 항목에 id, report_type, schedule, next_generation_at 포함."""
        response = reports_test_client.get("/api/v1/reports/config")

        assert response.status_code == 200
        data = response.json()
        if data["data"]:
            item = data["data"][0]
            assert "id" in item, "응답에 id 필드가 있어야 한다"
            assert "report_type" in item, "응답에 report_type 필드가 있어야 한다"
            assert "schedule" in item, "응답에 schedule 필드가 있어야 한다"

    def test_설정_조회_인증_없이_401(self):
        """인증 없이 설정 목록 조회 → 401."""
        from src.main import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/reports/config")

        assert response.status_code == 401, \
            f"인증 없이 설정 조회 시 401을 반환해야 한다 (실제: {response.status_code})"


# ──────────────────────────────────────────────────────────────
# PATCH /api/v1/reports/config/{id} 테스트 (I-1016b)
# ──────────────────────────────────────────────────────────────

class TestUpdateReportConfig:
    """리포트 스케줄 설정 수정 테스트"""

    def test_스케줄_변경_성공(self, reports_test_client):
        """I-1016b: weekly → monthly 스케줄 변경 → 200."""
        response = reports_test_client.patch(
            f"/api/v1/reports/config/{CONFIG_ID}",
            json={
                "schedule": "monthly",
            },
        )

        assert response.status_code == 200, \
            f"스케줄 변경 시 200을 반환해야 한다 (실제: {response.status_code})"
        data = response.json()
        assert data["success"] is True

    def test_수신자_목록_변경_성공(self, reports_test_client):
        """이메일 수신자 목록 변경 → 200."""
        response = reports_test_client.patch(
            f"/api/v1/reports/config/{CONFIG_ID}",
            json={
                "email_recipients": ["ciso@company.com", "cto@company.com"],
            },
        )

        assert response.status_code == 200, \
            f"수신자 목록 변경 시 200을 반환해야 한다 (실제: {response.status_code})"

    def test_존재하지_않는_설정_수정_404(self, reports_test_client):
        """존재하지 않는 설정 수정 → 404."""
        response = reports_test_client.patch(
            f"/api/v1/reports/config/{NONE_ID}",
            json={"schedule": "weekly"},
        )

        assert response.status_code == 404, \
            f"존재하지 않는 설정 수정 시 404를 반환해야 한다 (실제: {response.status_code})"

    def test_member_역할_설정_수정_403(self, reports_test_client_member):
        """member 역할은 설정 수정 불가 → 403."""
        response = reports_test_client_member.patch(
            f"/api/v1/reports/config/{CONFIG_ID}",
            json={"schedule": "monthly"},
        )

        assert response.status_code == 403, \
            f"member 역할은 설정 수정 시 403을 반환해야 한다 (실제: {response.status_code})"


# ──────────────────────────────────────────────────────────────
# DELETE /api/v1/reports/config/{id} 테스트 (I-1016c)
# ──────────────────────────────────────────────────────────────

class TestDeleteReportConfig:
    """리포트 스케줄 설정 삭제 테스트"""

    def test_설정_삭제_성공(self, reports_test_client):
        """I-1016c: 설정 삭제 → 200 또는 204."""
        response = reports_test_client.delete(f"/api/v1/reports/config/{CONFIG_ID}")

        assert response.status_code in (200, 204), \
            f"설정 삭제 시 200 또는 204를 반환해야 한다 (실제: {response.status_code})"

    def test_존재하지_않는_설정_삭제_404(self, reports_test_client):
        """존재하지 않는 설정 삭제 → 404."""
        response = reports_test_client.delete(f"/api/v1/reports/config/{NONE_ID}")

        assert response.status_code == 404, \
            f"존재하지 않는 설정 삭제 시 404를 반환해야 한다 (실제: {response.status_code})"

    def test_member_역할_설정_삭제_403(self, reports_test_client_member):
        """member 역할은 설정 삭제 불가 → 403."""
        response = reports_test_client_member.delete(f"/api/v1/reports/config/{CONFIG_ID}")

        assert response.status_code == 403, \
            f"member 역할은 설정 삭제 시 403을 반환해야 한다 (실제: {response.status_code})"

    def test_설정_삭제_인증_없이_401(self):
        """인증 없이 설정 삭제 → 401."""
        from src.main import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.delete(f"/api/v1/reports/config/{CONFIG_ID}")

        assert response.status_code == 401, \
            f"인증 없이 설정 삭제 시 401을 반환해야 한다 (실제: {response.status_code})"
