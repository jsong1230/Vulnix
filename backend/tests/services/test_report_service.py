"""F-10 리포트 서비스 단위 테스트 — RED 단계

ReportService.collect_report_data(), CISOReportRenderer, CSAPReportRenderer,
ISO27001ReportRenderer, ISMSReportRenderer, get_report_renderer(),
calculate_next_generation() 를 대상으로 실패하는 테스트를 작성한다.

구현이 없으므로 모두 FAIL(ImportError 또는 AssertionError)이어야 한다.
"""

import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

# ──────────────────────────────────────────────────────────────
# 테스트용 ReportData 데이터클래스 (구현 모듈 import 전 사용)
# ──────────────────────────────────────────────────────────────

@dataclass
class _ReportDataStub:
    """테스트 픽스처용 ReportData 임시 구조체."""

    team_name: str
    period_start: date
    period_end: date
    repositories: list
    total_repo_count: int
    total_vulnerabilities: int
    new_vulnerabilities: int
    resolved_vulnerabilities: int
    severity_distribution: dict
    status_distribution: dict
    resolution_rate: float
    vulnerability_type_top10: list
    current_security_score: float
    previous_security_score: float
    score_trend: list
    avg_response_time_hours: float
    auto_patch_rate: float
    repo_score_ranking: list
    scan_jobs: list
    total_scans: int
    patch_prs: list
    unresolved_critical: list


# ──────────────────────────────────────────────────────────────
# 공통 픽스처
# ──────────────────────────────────────────────────────────────

TEAM_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
PERIOD_START = date(2026, 2, 1)
PERIOD_END = date(2026, 2, 28)


@pytest.fixture
def sample_report_data() -> _ReportDataStub:
    """테스트용 완성된 ReportData 픽스처."""
    return _ReportDataStub(
        team_name="테스트팀",
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        repositories=[
            {"id": str(uuid.uuid4()), "full_name": "org/repo-1", "platform": "github", "security_score": 75.0},
            {"id": str(uuid.uuid4()), "full_name": "org/repo-2", "platform": "github", "security_score": 85.0},
            {"id": str(uuid.uuid4()), "full_name": "org/repo-3", "platform": "github", "security_score": 60.0},
        ],
        total_repo_count=3,
        total_vulnerabilities=20,
        new_vulnerabilities=10,
        resolved_vulnerabilities=5,
        severity_distribution={"critical": 3, "high": 7, "medium": 5, "low": 5},
        status_distribution={"open": 15, "patched": 3, "ignored": 1, "false_positive": 1},
        resolution_rate=25.0,
        vulnerability_type_top10=[
            {"type": "sql_injection", "count": 5},
            {"type": "xss", "count": 4},
        ],
        current_security_score=72.5,
        previous_security_score=68.0,
        score_trend=[
            {"date": "2026-02-01", "score": 68.0},
            {"date": "2026-02-15", "score": 70.0},
            {"date": "2026-02-28", "score": 72.5},
        ],
        avg_response_time_hours=38.4,
        auto_patch_rate=40.0,
        repo_score_ranking=[
            {"full_name": "org/repo-2", "score": 85.0, "open_vulns": 2},
            {"full_name": "org/repo-1", "score": 75.0, "open_vulns": 5},
            {"full_name": "org/repo-3", "score": 60.0, "open_vulns": 8},
        ],
        scan_jobs=[
            {"id": str(uuid.uuid4()), "repo_name": "org/repo-1", "status": "completed",
             "created_at": "2026-02-25T10:00:00Z", "findings_count": 5},
        ],
        total_scans=10,
        patch_prs=[
            {"id": str(uuid.uuid4()), "repo_name": "org/repo-1", "pr_url": "https://github.com/org/repo-1/pull/1",
             "status": "merged", "vulnerability_type": "sql_injection"},
        ],
        unresolved_critical=[
            {"id": str(uuid.uuid4()), "file_path": "src/app.py", "type": "sql_injection",
             "severity": "critical", "detected_at": "2026-02-01T00:00:00Z"},
        ],
    )


@pytest.fixture
def empty_report_data() -> _ReportDataStub:
    """취약점 0건인 빈 ReportData 픽스처."""
    return _ReportDataStub(
        team_name="빈팀",
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        repositories=[],
        total_repo_count=0,
        total_vulnerabilities=0,
        new_vulnerabilities=0,
        resolved_vulnerabilities=0,
        severity_distribution={"critical": 0, "high": 0, "medium": 0, "low": 0},
        status_distribution={"open": 0, "patched": 0, "ignored": 0, "false_positive": 0},
        resolution_rate=0.0,
        vulnerability_type_top10=[],
        current_security_score=0.0,
        previous_security_score=0.0,
        score_trend=[],
        avg_response_time_hours=0.0,
        auto_patch_rate=0.0,
        repo_score_ranking=[],
        scan_jobs=[],
        total_scans=0,
        patch_prs=[],
        unresolved_critical=[],
    )


# ──────────────────────────────────────────────────────────────
# U-1007 ~ U-1011: CISOReportRenderer 테스트
# ──────────────────────────────────────────────────────────────

class TestCISOReportRenderer:
    """CISOReportRenderer 단위 테스트"""

    def test_ciso_pdf_생성_성공(self, sample_report_data):
        """U-1007: CISO PDF 생성 시 파일이 존재하고 %PDF로 시작해야 한다."""
        from src.services.report_renderer import CISOReportRenderer

        renderer = CISOReportRenderer()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            renderer.render_pdf(sample_report_data, output_path)

            assert os.path.exists(output_path), "PDF 파일이 생성되어야 한다"
            assert os.path.getsize(output_path) > 0, "PDF 파일 크기가 0보다 커야 한다"

            with open(output_path, "rb") as f:
                header = f.read(4)
            assert header == b"%PDF", "PDF 파일은 %PDF 헤더로 시작해야 한다"
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_ciso_pdf_한글_텍스트_포함(self, sample_report_data):
        """U-1008: 한글 팀명이 포함된 ReportData로 PDF 생성 시 오류가 없어야 한다."""
        from src.services.report_renderer import CISOReportRenderer

        renderer = CISOReportRenderer()
        sample_report_data.team_name = "한국어 테스트 팀명"

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            # 한글 폰트 임베딩 오류 없이 생성되어야 한다
            renderer.render_pdf(sample_report_data, output_path)
            assert os.path.exists(output_path), "한글 포함 PDF가 생성되어야 한다"
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_ciso_pdf_페이지_수_3이상(self, sample_report_data):
        """U-1009: 차트 포함 시 PDF 페이지 수가 3 이상이어야 한다 (표지+요약+통계)."""
        from src.services.report_renderer import CISOReportRenderer

        renderer = CISOReportRenderer()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            renderer.render_pdf(sample_report_data, output_path)

            # reportlab으로 생성된 PDF의 페이지 수 확인
            # /Type /Page 패턴 또는 Page 카운트 확인
            with open(output_path, "rb") as f:
                content = f.read().decode("latin-1", errors="ignore")

            page_count = content.count("/Type /Page")
            assert page_count >= 3, f"PDF 페이지 수가 3 이상이어야 한다 (실제: {page_count})"
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_ciso_pdf_빈_데이터_처리(self, empty_report_data):
        """U-1010: 취약점 0건 데이터로 PDF 생성 시 오류 없이 처리되어야 한다."""
        from src.services.report_renderer import CISOReportRenderer

        renderer = CISOReportRenderer()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            # 빈 데이터에서도 예외 없이 PDF 생성
            renderer.render_pdf(empty_report_data, output_path)
            assert os.path.exists(output_path), "빈 데이터 PDF가 생성되어야 한다"
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_ciso_json_생성_필수_키_포함(self, sample_report_data):
        """U-1011: CISO JSON 생성 시 필수 키(security_score, vulnerabilities, scans)가 포함되어야 한다."""
        from src.services.report_renderer import CISOReportRenderer

        renderer = CISOReportRenderer()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            output_path = f.name

        try:
            renderer.render_json(sample_report_data, output_path)

            assert os.path.exists(output_path), "JSON 파일이 생성되어야 한다"
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert "security_score" in data, "JSON에 security_score 키가 있어야 한다"
            assert "vulnerabilities" in data, "JSON에 vulnerabilities 키가 있어야 한다"
            assert "scans" in data, "JSON에 scans 키가 있어야 한다"
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


# ──────────────────────────────────────────────────────────────
# U-1012 ~ U-1013: CSAPReportRenderer 테스트
# ──────────────────────────────────────────────────────────────

class TestCSAPReportRenderer:
    """CSAPReportRenderer 단위 테스트"""

    def test_csap_pdf_생성_성공(self, sample_report_data):
        """U-1012: CSAP 증적 PDF 생성 성공 — 취약점 관리 프로세스 섹션 포함."""
        from src.services.report_renderer import CSAPReportRenderer

        renderer = CSAPReportRenderer()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            renderer.render_pdf(sample_report_data, output_path)

            assert os.path.exists(output_path), "CSAP PDF 파일이 생성되어야 한다"
            assert os.path.getsize(output_path) > 0, "CSAP PDF 파일 크기가 0보다 커야 한다"

            with open(output_path, "rb") as f:
                header = f.read(4)
            assert header == b"%PDF", "CSAP PDF 파일은 %PDF 헤더로 시작해야 한다"
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_csap_json_필수_키_포함(self, sample_report_data):
        """U-1013: CSAP JSON 생성 시 vulnerability_management, scan_history, patch_history 키 포함."""
        from src.services.report_renderer import CSAPReportRenderer

        renderer = CSAPReportRenderer()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            output_path = f.name

        try:
            renderer.render_json(sample_report_data, output_path)

            assert os.path.exists(output_path), "CSAP JSON 파일이 생성되어야 한다"
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert "vulnerability_management" in data, "JSON에 vulnerability_management 키가 있어야 한다"
            assert "scan_history" in data, "JSON에 scan_history 키가 있어야 한다"
            assert "patch_history" in data, "JSON에 patch_history 키가 있어야 한다"
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


# ──────────────────────────────────────────────────────────────
# U-1014 ~ U-1015: ISO27001ReportRenderer 테스트
# ──────────────────────────────────────────────────────────────

class TestISO27001ReportRenderer:
    """ISO27001ReportRenderer 단위 테스트"""

    def test_iso27001_pdf_생성_항목번호_포함(self, sample_report_data):
        """U-1014: ISO 27001 증적 PDF 생성 시 A.12.6.1, A.14.2.1 항목 번호 포함."""
        from src.services.report_renderer import ISO27001ReportRenderer

        renderer = ISO27001ReportRenderer()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            renderer.render_pdf(sample_report_data, output_path)

            assert os.path.exists(output_path), "ISO 27001 PDF 파일이 생성되어야 한다"
            assert os.path.getsize(output_path) > 0

            # PDF 텍스트에 항목 번호 포함 여부 확인
            with open(output_path, "rb") as f:
                content = f.read().decode("latin-1", errors="ignore")

            assert "A.12.6.1" in content or "A.14.2.1" in content, \
                "ISO 27001 PDF에 항목 번호(A.12.6.1 또는 A.14.2.1)가 포함되어야 한다"
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_iso27001_json_cwe_owasp_매핑_포함(self, sample_report_data):
        """U-1015: ISO 27001 JSON 생성 시 CWE/OWASP 매핑 데이터 포함."""
        from src.services.report_renderer import ISO27001ReportRenderer

        renderer = ISO27001ReportRenderer()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            output_path = f.name

        try:
            renderer.render_json(sample_report_data, output_path)

            assert os.path.exists(output_path), "ISO 27001 JSON 파일이 생성되어야 한다"
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # CWE/OWASP 매핑 데이터가 JSON에 포함되어야 한다
            assert any(
                key in data for key in ["cwe_mapping", "owasp_mapping", "A12_6_1", "vulnerabilities"]
            ), "ISO 27001 JSON에 CWE/OWASP 매핑 데이터가 포함되어야 한다"
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


# ──────────────────────────────────────────────────────────────
# U-1016 ~ U-1017: ISMSReportRenderer 테스트
# ──────────────────────────────────────────────────────────────

class TestISMSReportRenderer:
    """ISMSReportRenderer 단위 테스트"""

    def test_isms_pdf_생성_항목번호_포함(self, sample_report_data):
        """U-1016: ISMS 증적 PDF 생성 시 2.10.4, 2.11.5 항목 번호 포함."""
        from src.services.report_renderer import ISMSReportRenderer

        renderer = ISMSReportRenderer()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            renderer.render_pdf(sample_report_data, output_path)

            assert os.path.exists(output_path), "ISMS PDF 파일이 생성되어야 한다"
            assert os.path.getsize(output_path) > 0

            with open(output_path, "rb") as f:
                content = f.read().decode("latin-1", errors="ignore")

            assert "2.10.4" in content or "2.11.5" in content, \
                "ISMS PDF에 항목 번호(2.10.4 또는 2.11.5)가 포함되어야 한다"
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_isms_json_조치율_포함(self, sample_report_data):
        """U-1017: ISMS JSON 생성 시 취약점 조치율/평균 조치일 포함."""
        from src.services.report_renderer import ISMSReportRenderer

        renderer = ISMSReportRenderer()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            output_path = f.name

        try:
            renderer.render_json(sample_report_data, output_path)

            assert os.path.exists(output_path), "ISMS JSON 파일이 생성되어야 한다"
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 취약점 조치율 또는 평균 조치 소요일 관련 키 포함
            assert any(
                key in data for key in [
                    "resolution_rate", "avg_response_time_hours",
                    "2_10_4", "vulnerability_resolution", "avg_resolution_days"
                ]
            ), "ISMS JSON에 취약점 조치율/평균 조치일 데이터가 포함되어야 한다"
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


# ──────────────────────────────────────────────────────────────
# U-1018 ~ U-1022: get_report_renderer 팩토리 테스트
# ──────────────────────────────────────────────────────────────

class TestGetReportRendererFactory:
    """get_report_renderer() 팩토리 함수 테스트"""

    def test_ciso_유형_반환(self):
        """U-1018: 'ciso' 유형 → CISOReportRenderer 인스턴스 반환."""
        from src.services.report_renderer import CISOReportRenderer, get_report_renderer

        renderer = get_report_renderer("ciso")
        assert isinstance(renderer, CISOReportRenderer), \
            "'ciso' 유형 요청 시 CISOReportRenderer가 반환되어야 한다"

    def test_csap_유형_반환(self):
        """U-1019: 'csap' 유형 → CSAPReportRenderer 인스턴스 반환."""
        from src.services.report_renderer import CSAPReportRenderer, get_report_renderer

        renderer = get_report_renderer("csap")
        assert isinstance(renderer, CSAPReportRenderer), \
            "'csap' 유형 요청 시 CSAPReportRenderer가 반환되어야 한다"

    def test_iso27001_유형_반환(self):
        """U-1020: 'iso27001' 유형 → ISO27001ReportRenderer 인스턴스 반환."""
        from src.services.report_renderer import ISO27001ReportRenderer, get_report_renderer

        renderer = get_report_renderer("iso27001")
        assert isinstance(renderer, ISO27001ReportRenderer), \
            "'iso27001' 유형 요청 시 ISO27001ReportRenderer가 반환되어야 한다"

    def test_isms_유형_반환(self):
        """U-1021: 'isms' 유형 → ISMSReportRenderer 인스턴스 반환."""
        from src.services.report_renderer import ISMSReportRenderer, get_report_renderer

        renderer = get_report_renderer("isms")
        assert isinstance(renderer, ISMSReportRenderer), \
            "'isms' 유형 요청 시 ISMSReportRenderer가 반환되어야 한다"

    def test_미지원_유형_ValueError_발생(self):
        """U-1022: 지원하지 않는 유형 'soc2' → ValueError 발생."""
        from src.services.report_renderer import get_report_renderer

        with pytest.raises(ValueError, match="soc2"):
            get_report_renderer("soc2")


# ──────────────────────────────────────────────────────────────
# U-1027 ~ U-1031: calculate_next_generation 테스트
# ──────────────────────────────────────────────────────────────

class TestCalculateNextGeneration:
    """calculate_next_generation() 스케줄러 헬퍼 테스트"""

    def test_weekly_다음_생성일(self):
        """U-1027: weekly 스케줄 — 현재 2026-02-25 → 다음 2026-03-04 (+7일)."""
        from src.workers.report_scheduler import calculate_next_generation

        current = datetime(2026, 2, 25, 0, 0, 0, tzinfo=timezone.utc)
        result = calculate_next_generation("weekly", current)

        expected = datetime(2026, 3, 4, 0, 0, 0, tzinfo=timezone.utc)
        assert result == expected, f"weekly 다음 생성일이 2026-03-04이어야 한다 (실제: {result})"

    def test_monthly_다음_생성일(self):
        """U-1028: monthly 스케줄 — 현재 2026-02-25 → 다음 2026-03-01 00:00:00 UTC."""
        from src.workers.report_scheduler import calculate_next_generation

        current = datetime(2026, 2, 25, 0, 0, 0, tzinfo=timezone.utc)
        result = calculate_next_generation("monthly", current)

        expected = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert result == expected, f"monthly 다음 생성일이 2026-03-01이어야 한다 (실제: {result})"

    def test_quarterly_다음_생성일(self):
        """U-1029: quarterly 스케줄 — 현재 2026-02-25 → 다음 분기 2026-04-01 00:00:00 UTC."""
        from src.workers.report_scheduler import calculate_next_generation

        current = datetime(2026, 2, 25, 0, 0, 0, tzinfo=timezone.utc)
        result = calculate_next_generation("quarterly", current)

        expected = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert result == expected, f"quarterly 다음 생성일이 2026-04-01이어야 한다 (실제: {result})"

    def test_quarterly_12월_연도_넘김(self):
        """U-1030: quarterly 스케줄 — 현재 2026-12-15 → 다음 분기 2027-01-01 00:00:00 UTC."""
        from src.workers.report_scheduler import calculate_next_generation

        current = datetime(2026, 12, 15, 0, 0, 0, tzinfo=timezone.utc)
        result = calculate_next_generation("quarterly", current)

        expected = datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert result == expected, f"12월 quarterly 다음 생성일이 2027-01-01이어야 한다 (실제: {result})"

    def test_미지원_주기_ValueError_발생(self):
        """U-1031: 지원하지 않는 주기 'daily' → ValueError 발생."""
        from src.workers.report_scheduler import calculate_next_generation

        current = datetime(2026, 2, 25, 0, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="daily"):
            calculate_next_generation("daily", current)


# ──────────────────────────────────────────────────────────────
# U-1034 ~ U-1036: 모델 테스트
# ──────────────────────────────────────────────────────────────

class TestReportModels:
    """ReportConfig, ReportHistory 모델 단위 테스트"""

    def test_report_config_기본_생성(self):
        """U-1034: ReportConfig 기본 생성 시 is_active=True."""
        from src.models.report_config import ReportConfig

        config = ReportConfig(
            team_id=TEAM_ID,
            report_type="ciso",
            schedule="monthly",
            email_recipients=[],
            created_by=uuid.uuid4(),
        )
        assert config.is_active is True, "ReportConfig 기본 is_active는 True여야 한다"

    def test_report_history_기본_상태_generating(self):
        """U-1036: ReportHistory 생성 시 기본 status='generating'."""
        from src.models.report_history import ReportHistory

        history = ReportHistory(
            config_id=uuid.uuid4(),
            team_id=TEAM_ID,
            report_type="ciso",
            format="pdf",
            file_path="/data/reports/test.pdf",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )
        assert history.status == "generating", \
            "ReportHistory 기본 status는 'generating'이어야 한다"


# ──────────────────────────────────────────────────────────────
# ReportService.collect_report_data() 단위 테스트
# (DB mock 기반 — 실제 DB 불필요)
# ──────────────────────────────────────────────────────────────

class TestReportServiceCollectData:
    """ReportService.collect_report_data() 테스트"""

    @pytest.mark.asyncio
    async def test_정상_데이터_수집(self):
        """U-1001: DB에 저장소 3개, 취약점 20개, 스캔 10건 → ReportData 반환."""
        from src.services.report_service import ReportService

        # Mock DB 세션 구성
        mock_db = AsyncMock()

        # 저장소 3개 mock
        repos = [MagicMock() for _ in range(3)]
        for i, r in enumerate(repos):
            r.id = uuid.uuid4()
            r.team_id = TEAM_ID
            r.full_name = f"org/repo-{i+1}"
            r.security_score = 70.0 + i * 5

        # 취약점 20개 mock
        vulns = []
        severities = ["critical"] * 3 + ["high"] * 7 + ["medium"] * 5 + ["low"] * 5
        for i in range(20):
            v = MagicMock()
            v.id = uuid.uuid4()
            v.repo_id = repos[i % 3].id
            v.severity = severities[i]
            v.status = "open"
            v.detected_at = datetime(2026, 2, 1 + i, tzinfo=timezone.utc)
            v.resolved_at = None
            v.vulnerability_type = "sql_injection"
            vulns.append(v)

        # 스캔 10건 mock
        scans = []
        for i in range(10):
            s = MagicMock()
            s.id = uuid.uuid4()
            s.repo_id = repos[i % 3].id
            s.status = "completed"
            s.created_at = datetime(2026, 2, 1 + i, tzinfo=timezone.utc)
            s.findings_count = i
            scans.append(s)

        # TeamMember mock
        member_result = MagicMock()
        member_result.scalars.return_value.all.return_value = [TEAM_ID]

        repo_result = MagicMock()
        repo_result.scalars.return_value.all.return_value = repos

        vuln_result = MagicMock()
        vuln_result.scalars.return_value.all.return_value = vulns

        scan_result = MagicMock()
        scan_result.scalars.return_value.all.return_value = scans

        # Team 이름 조회를 위한 mock
        team_result = MagicMock()
        team_mock = MagicMock()
        team_mock.name = "테스트팀"
        team_result.scalar_one_or_none.return_value = team_mock

        call_count = [0]

        async def mock_execute(query, *args, **kwargs):
            query_str = str(query).lower()
            call_count[0] += 1
            if "team_member" in query_str:
                return member_result
            elif "repository" in query_str:
                return repo_result
            elif "vulnerability" in query_str:
                return vuln_result
            elif "scan_job" in query_str or "scan" in query_str:
                return scan_result
            elif "team" in query_str:
                return team_result
            return MagicMock()

        mock_db.execute = AsyncMock(side_effect=mock_execute)

        service = ReportService(mock_db)
        result = await service.collect_report_data(
            team_id=TEAM_ID,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )

        assert result is not None, "collect_report_data가 ReportData를 반환해야 한다"
        assert result.total_vulnerabilities == 20, \
            f"총 취약점 수가 20이어야 한다 (실제: {result.total_vulnerabilities})"
        assert result.total_repo_count == 3, \
            f"저장소 수가 3이어야 한다 (실제: {result.total_repo_count})"
        assert result.total_scans == 10, \
            f"총 스캔 수가 10이어야 한다 (실제: {result.total_scans})"

    @pytest.mark.asyncio
    async def test_빈_팀_데이터_수집(self):
        """U-1002: 저장소 없는 팀 → total_vulnerabilities=0, total_repo_count=0."""
        from src.services.report_service import ReportService

        mock_db = AsyncMock()

        empty_result = MagicMock()
        empty_result.scalars.return_value.all.return_value = []
        empty_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(return_value=empty_result)

        service = ReportService(mock_db)
        result = await service.collect_report_data(
            team_id=uuid.uuid4(),
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )

        assert result is not None, "빈 팀의 경우에도 ReportData를 반환해야 한다"
        assert result.total_vulnerabilities == 0, "빈 팀의 총 취약점 수는 0이어야 한다"
        assert result.total_repo_count == 0, "빈 팀의 저장소 수는 0이어야 한다"

    @pytest.mark.asyncio
    async def test_평균_대응_시간_계산(self):
        """U-1005: 5건 취약점 대응 시간 (24h, 48h, 72h, 12h, 36h) → avg=38.4h."""
        from src.services.report_service import ReportService

        mock_db = AsyncMock()

        # 해결된 취약점 5건 (대응 시간: 24h, 48h, 72h, 12h, 36h)
        base_detected = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        response_hours = [24, 48, 72, 12, 36]
        vulns = []
        for i, hours in enumerate(response_hours):
            v = MagicMock()
            v.id = uuid.uuid4()
            v.repo_id = uuid.uuid4()
            v.severity = "high"
            v.status = "patched"
            v.detected_at = base_detected + timedelta(days=i)
            v.resolved_at = v.detected_at + timedelta(hours=hours)
            v.vulnerability_type = "sql_injection"
            vulns.append(v)

        repos = [MagicMock()]
        repos[0].id = vulns[0].repo_id
        repos[0].full_name = "org/repo"
        repos[0].team_id = TEAM_ID
        repos[0].security_score = 75.0

        call_map = {
            "team_member": [TEAM_ID],
            "repository": repos,
            "vulnerability": vulns,
            "scan_job": [],
        }

        async def mock_execute(query, *args, **kwargs):
            query_str = str(query).lower()
            result = MagicMock()
            for key, items in call_map.items():
                if key in query_str:
                    result.scalars.return_value.all.return_value = items
                    result.scalar_one_or_none.return_value = items[0] if items else None
                    return result
            result.scalars.return_value.all.return_value = []
            return result

        mock_db.execute = AsyncMock(side_effect=mock_execute)

        service = ReportService(mock_db)
        result = await service.collect_report_data(
            team_id=TEAM_ID,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )

        # avg = (24 + 48 + 72 + 12 + 36) / 5 = 192 / 5 = 38.4
        assert abs(result.avg_response_time_hours - 38.4) < 0.1, \
            f"평균 대응 시간이 38.4h이어야 한다 (실제: {result.avg_response_time_hours})"

    @pytest.mark.asyncio
    async def test_자동_패치_적용률_계산(self):
        """U-1006: 전체 20건 중 자동 패치 8건 → auto_patch_rate=40.0%."""
        from src.services.report_service import ReportService

        mock_db = AsyncMock()

        vulns = []
        for i in range(20):
            v = MagicMock()
            v.id = uuid.uuid4()
            v.repo_id = uuid.uuid4()
            v.severity = "medium"
            v.status = "patched" if i < 8 else "open"
            v.detected_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
            v.resolved_at = datetime(2026, 2, 2, tzinfo=timezone.utc) if i < 8 else None
            v.vulnerability_type = "xss"
            # patch_pr가 있으면 자동 패치로 간주
            if i < 8:
                v.patch_pr = MagicMock()
                v.patch_pr.id = uuid.uuid4()
            else:
                v.patch_pr = None
            vulns.append(v)

        repos = [MagicMock()]
        repos[0].id = uuid.uuid4()
        repos[0].full_name = "org/repo"
        repos[0].team_id = TEAM_ID
        repos[0].security_score = 75.0
        # 각 vuln의 repo_id를 동일하게 설정
        for v in vulns:
            v.repo_id = repos[0].id

        async def mock_execute(query, *args, **kwargs):
            query_str = str(query).lower()
            result = MagicMock()
            if "team_member" in query_str:
                result.scalars.return_value.all.return_value = [TEAM_ID]
            elif "repository" in query_str:
                result.scalars.return_value.all.return_value = repos
            elif "vulnerability" in query_str:
                result.scalars.return_value.all.return_value = vulns
            else:
                result.scalars.return_value.all.return_value = []
            return result

        mock_db.execute = AsyncMock(side_effect=mock_execute)

        service = ReportService(mock_db)
        result = await service.collect_report_data(
            team_id=TEAM_ID,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )

        assert abs(result.auto_patch_rate - 40.0) < 0.1, \
            f"자동 패치 적용률이 40.0%이어야 한다 (실제: {result.auto_patch_rate})"
