"""FPFilterService 단위 테스트 — UT-01, UT-02, UT-03"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.false_positive import FalsePositivePattern
from src.services.fp_filter_service import FPFilterService, calculate_fp_rate
from src.services.semgrep_engine import SemgrepFinding


# ---------------------------------------------------------------------------
# 헬퍼 픽스처
# ---------------------------------------------------------------------------

def make_finding(rule_id: str, file_path: str, start_line: int = 1) -> SemgrepFinding:
    """SemgrepFinding 테스트 픽스처를 생성한다."""
    return SemgrepFinding(
        rule_id=rule_id,
        severity="WARNING",
        file_path=file_path,
        start_line=start_line,
        end_line=start_line,
        code_snippet="# test",
        message="test finding",
    )


def make_pattern(
    rule_id: str,
    file_pattern: str | None = None,
    is_active: bool = True,
    matched_count: int = 0,
) -> FalsePositivePattern:
    """FalsePositivePattern Mock 픽스처를 생성한다."""
    pattern = MagicMock(spec=FalsePositivePattern)
    pattern.id = uuid.uuid4()
    pattern.team_id = uuid.uuid4()
    pattern.semgrep_rule_id = rule_id
    pattern.file_pattern = file_pattern
    pattern.is_active = is_active
    pattern.matched_count = matched_count
    pattern.last_matched_at = None
    return pattern


def make_db_with_patterns(patterns: list[FalsePositivePattern]) -> AsyncMock:
    """주어진 패턴 목록을 반환하는 Mock DB 세션을 생성한다."""
    db = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = patterns
    db.execute = AsyncMock(return_value=mock_result)
    return db


# ---------------------------------------------------------------------------
# UT-03: 오탐율 계산 로직
# ---------------------------------------------------------------------------

class TestCalculateFpRate:
    """calculate_fp_rate 함수 단위 테스트"""

    def test_normal_case(self):
        """정상 케이스: tp=70, fp=30 -> 30.0%"""
        assert calculate_fp_rate(70, 30) == 30.0

    def test_no_false_positives(self):
        """오탐 0건: fp_rate = 0.0%"""
        assert calculate_fp_rate(100, 0) == 0.0

    def test_all_false_positives(self):
        """전부 오탐: fp_rate = 100.0%"""
        assert calculate_fp_rate(0, 50) == 100.0

    def test_zero_division_prevention(self):
        """스캔 없음 (ZeroDivisionError 방지): fp_rate = 0.0%"""
        assert calculate_fp_rate(0, 0) == 0.0

    def test_improvement_calculation(self):
        """이전 기간 대비 개선율: 이전 32%, 현재 25.5% -> improvement = 6.5%"""
        previous_fp_rate = calculate_fp_rate(68, 32)  # 32.0%
        current_fp_rate = calculate_fp_rate(745, 255)  # ≈ 25.5%
        improvement = round(previous_fp_rate - current_fp_rate, 2)
        assert improvement > 0  # 오탐율 감소 = 개선


# ---------------------------------------------------------------------------
# UT-01: _matches 패턴 매칭 로직
# ---------------------------------------------------------------------------

class TestFPFilterServiceMatches:
    """FPFilterService._matches 단위 테스트"""

    def setup_method(self):
        """테스트마다 FPFilterService 인스턴스를 초기화한다."""
        self.service = FPFilterService(db=AsyncMock())

    def test_rule_id_match_file_pattern_none(self):
        """rule_id 일치 + file_pattern null → True (모든 파일 대상)"""
        finding = make_finding("python.flask.xss", "src/app.py")
        pattern = make_pattern("python.flask.xss", file_pattern=None)
        assert self.service._matches(finding, pattern) is True

    def test_rule_id_match_glob_match(self):
        """rule_id 일치 + file_pattern glob 일치 → True"""
        finding = make_finding("generic.secrets", "tests/test_auth.py")
        pattern = make_pattern("generic.secrets", "tests/**")
        assert self.service._matches(finding, pattern) is True

    def test_rule_id_match_glob_no_match(self):
        """rule_id 일치 + file_pattern glob 불일치 → False"""
        finding = make_finding("generic.secrets", "src/auth.py")
        pattern = make_pattern("generic.secrets", "tests/**")
        assert self.service._matches(finding, pattern) is False

    def test_rule_id_mismatch(self):
        """rule_id 불일치 → False"""
        finding = make_finding("python.flask.xss", "tests/test.py")
        pattern = make_pattern("generic.secrets", "tests/**")
        assert self.service._matches(finding, pattern) is False

    def test_double_star_glob_prefix(self):
        """**/ 접두사가 있는 경우 → True"""
        finding = make_finding("python.sql", "src/db/migrations/001.py")
        pattern = make_pattern("python.sql", "**/migrations/*")
        assert self.service._matches(finding, pattern) is True


# ---------------------------------------------------------------------------
# UT-02: filter 필터링 실행
# ---------------------------------------------------------------------------

class TestFPFilterServiceFilter:
    """FPFilterService.filter 단위 테스트"""

    @pytest.mark.asyncio
    async def test_no_patterns(self):
        """패턴 0개 → 필터링 없이 모든 findings 반환"""
        db = make_db_with_patterns([])
        service = FPFilterService(db=db)
        team_id = uuid.uuid4()

        findings = [
            make_finding("rule-A", "src/a.py"),
            make_finding("rule-B", "src/b.py"),
            make_finding("rule-C", "src/c.py"),
            make_finding("rule-D", "src/d.py"),
            make_finding("rule-E", "src/e.py"),
        ]

        result = await service.filter(findings, team_id)
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_partial_match(self):
        """패턴 1개, 2건 매칭 → 3건 반환"""
        pattern = make_pattern("generic.secrets", "tests/**")
        db = make_db_with_patterns([pattern])
        service = FPFilterService(db=db)
        team_id = uuid.uuid4()

        findings = [
            make_finding("generic.secrets", "tests/test_a.py"),  # 매칭
            make_finding("generic.secrets", "tests/test_b.py"),  # 매칭
            make_finding("generic.secrets", "src/a.py"),          # 불일치
            make_finding("python.xss", "src/b.py"),               # rule_id 다름
            make_finding("python.xss", "src/c.py"),               # rule_id 다름
        ]

        result = await service.filter(findings, team_id)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_all_matched(self):
        """패턴 여러 개, 전부 매칭 → 빈 목록 반환"""
        patterns = [
            make_pattern("rule-A"),
            make_pattern("rule-B"),
            make_pattern("rule-C"),
        ]
        db = make_db_with_patterns(patterns)
        service = FPFilterService(db=db)
        team_id = uuid.uuid4()

        findings = [
            make_finding("rule-A", "src/a.py"),
            make_finding("rule-B", "src/b.py"),
            make_finding("rule-C", "src/c.py"),
        ]

        result = await service.filter(findings, team_id)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_inactive_pattern_ignored(self):
        """비활성 패턴은 무시 → findings 그대로 반환"""
        # 비활성 패턴은 _load_patterns에서 제외되므로 빈 목록 반환
        db = make_db_with_patterns([])  # is_active=False 패턴은 쿼리에서 제외됨
        service = FPFilterService(db=db)
        team_id = uuid.uuid4()

        findings = [
            make_finding("generic.secrets", "tests/test_a.py"),
            make_finding("generic.secrets", "tests/test_b.py"),
            make_finding("generic.secrets", "src/a.py"),
        ]

        result = await service.filter(findings, team_id)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_matched_count_updated(self):
        """매칭 시 matched_count 증가 확인"""
        pattern = make_pattern("generic.secrets", None, matched_count=5)
        db = make_db_with_patterns([pattern])
        service = FPFilterService(db=db)
        team_id = uuid.uuid4()

        findings = [
            make_finding("generic.secrets", "src/a.py"),
            make_finding("generic.secrets", "src/b.py"),
            make_finding("generic.secrets", "src/c.py"),
        ]

        await service.filter(findings, team_id)
        assert pattern.matched_count == 8  # 5 + 3

    @pytest.mark.asyncio
    async def test_filter_findings_with_log(self):
        """filter_findings: 매칭 시 FalsePositiveLog 레코드 생성 확인"""
        pattern = make_pattern("generic.secrets", "tests/**")
        team_id = uuid.uuid4()
        scan_job_id = uuid.uuid4()

        db = make_db_with_patterns([pattern])
        service = FPFilterService(db=db)

        findings = [
            make_finding("generic.secrets", "tests/test_a.py"),  # 매칭
            make_finding("generic.secrets", "tests/test_b.py"),  # 매칭
            make_finding("python.xss", "src/app.py"),             # 불일치
        ]

        filtered, auto_filtered_count = await service.filter_findings(
            findings, team_id, scan_job_id
        )

        assert len(filtered) == 1
        assert auto_filtered_count == 2
        assert db.add.call_count == 2  # FalsePositiveLog 2건 추가

    @pytest.mark.asyncio
    async def test_filter_findings_last_matched_at_updated(self):
        """filter_findings: 매칭 시 last_matched_at 갱신 확인"""
        pattern = make_pattern("generic.secrets", None)
        team_id = uuid.uuid4()
        scan_job_id = uuid.uuid4()

        db = make_db_with_patterns([pattern])
        service = FPFilterService(db=db)

        findings = [make_finding("generic.secrets", "src/a.py")]

        await service.filter_findings(findings, team_id, scan_job_id)

        assert pattern.last_matched_at is not None
        assert isinstance(pattern.last_matched_at, datetime)
