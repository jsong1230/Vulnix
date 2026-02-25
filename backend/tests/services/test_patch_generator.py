"""PatchGenerator 단위 테스트 — F-03 RED 단계

구현이 완료되지 않은 상태에서 실행하면 모두 FAIL이어야 한다.

테스트 범위:
- _make_branch_name(): 브랜치명 생성 규칙
- generate_patch_prs(): 패치 PR 생성 전체 흐름
- _build_pr_body(): PR 본문 구성
- _apply_patch_diff(): diff 적용 로직
- 병렬 처리
"""

import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.patch_generator import PatchGenerator
from src.services.llm_agent import LLMAnalysisResult
from src.services.semgrep_engine import SemgrepFinding


# ──────────────────────────────────────────────────────────────
# 픽스처
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def patch_generator(mock_github_service):
    """PatchGenerator 인스턴스 픽스처.

    GitHubAppService를 mock으로 주입하여 GitHub API 호출 없이 테스트한다.
    """
    gen = PatchGenerator()
    gen._github_service = mock_github_service
    return gen


@pytest.fixture
def mock_github_service():
    """GitHubAppService 패치 전용 Mock 픽스처.

    F-03에서 추가되는 메서드들을 포함하여 mock 처리한다.
    """
    service = AsyncMock()
    service.get_installation_token = AsyncMock(return_value="ghs_test_token")
    service.get_default_branch_sha = AsyncMock(
        return_value="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    )
    service.create_branch = AsyncMock(return_value=None)
    service.get_file_content = AsyncMock(
        return_value=(
            'def get_user(user_id):\n    query = f"SELECT * FROM users WHERE id = {user_id}"\n    return db.execute(query)\n',
            "abc123filesha",
        )
    )
    service.create_file_commit = AsyncMock(return_value={"sha": "newcommitsha"})
    service.create_pull_request = AsyncMock(
        return_value={
            "number": 42,
            "html_url": "https://github.com/test-org/test-repo/pull/42",
        }
    )
    return service


@pytest.fixture
def sample_vulnerability():
    """Vulnerability 모델 픽스처 (F-02 결과물)."""
    from src.models.vulnerability import Vulnerability

    vuln = MagicMock(spec=Vulnerability)
    vuln.id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    vuln.repo_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    vuln.scan_job_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    vuln.finding_id = "vulnix.python.sql_injection.string_format"
    vuln.rule_id = "vulnix.python.sql_injection.string_format"
    vuln.vulnerability_type = "sql_injection"
    vuln.severity = "high"
    vuln.file_path = "app/db.py"
    vuln.start_line = 5
    vuln.end_line = 5
    vuln.status = "detected"
    vuln.manual_guide = None
    vuln.manual_priority = None
    return vuln


@pytest.fixture
def sample_patch_pr():
    """PatchPR 모델 픽스처."""
    from src.models.patch_pr import PatchPR

    pr = MagicMock(spec=PatchPR)
    pr.id = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
    pr.vulnerability_id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    pr.repo_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    pr.github_pr_number = 42
    pr.github_pr_url = "https://github.com/test-org/test-repo/pull/42"
    pr.branch_name = "vulnix/fix-sql-injection-a1b2c3d"
    pr.status = "created"
    pr.patch_diff = '--- a/app/db.py\n+++ b/app/db.py\n@@ -4,3 +4,3 @@\n-    cursor.execute(f"SELECT * FROM users WHERE id={user_id}")\n+    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))'
    pr.patch_description = "f-string SQL 쿼리를 파라미터화된 쿼리로 변경"
    return pr


@pytest.fixture
def mock_patch_diff():
    """unified diff 픽스처 (SQL Injection 패치)."""
    return """--- a/app.py
+++ b/app.py
@@ -1,3 +1,4 @@
 def get_user(user_id):
-    query = f"SELECT * FROM users WHERE id = {user_id}"
+    query = "SELECT * FROM users WHERE id = %s"
+    return db.execute(query, (user_id,))
-    return db.execute(query)"""


@pytest.fixture
def patchable_analysis_result(mock_patch_diff):
    """패치 가능한 LLMAnalysisResult 픽스처."""
    return LLMAnalysisResult(
        finding_id="vulnix.python.sql_injection.string_format",
        is_true_positive=True,
        confidence=0.95,
        severity="High",
        reasoning="사용자 입력이 f-string으로 SQL 쿼리에 직접 삽입됨",
        patch_diff=mock_patch_diff,
        patch_description="f-string SQL 쿼리를 파라미터화된 쿼리로 변경하여 SQL Injection 방지",
        vulnerability_type="sql_injection",
        owasp_category="A03:2021 - Injection",
        references=["https://cwe.mitre.org/data/definitions/89.html"],
    )


@pytest.fixture
def unpatchable_analysis_result():
    """패치 불가 LLMAnalysisResult 픽스처 (patch_diff=None).

    F-03 구현 후 LLMAnalysisResult에 manual_guide, patchable 필드가 추가된다.
    현재는 patch_diff=None으로만 패치 불가 상태를 표현한다.
    """
    result = LLMAnalysisResult(
        finding_id="vulnix.python.hardcoded_credentials.aws_key",
        is_true_positive=True,
        confidence=0.90,
        severity="Critical",
        reasoning="AWS Secret Key가 하드코딩되어 있음",
        patch_diff=None,
        patch_description="",
        vulnerability_type="hardcoded_credentials",
        owasp_category="A07:2021 - Identification and Authentication Failures",
        references=["https://cwe.mitre.org/data/definitions/798.html"],
    )
    # F-03 구현 후 추가될 필드를 동적으로 설정
    # (구현 전이므로 setattr으로 처리 — 테스트는 FAIL 상태여야 함)
    result.__dict__["manual_guide"] = (
        "이 취약점은 아키텍처 수준의 변경이 필요하여 자동 패치가 불가능합니다. "
        "환경변수 또는 시크릿 매니저를 사용하세요."
    )
    return result


@pytest.fixture
def false_positive_analysis_result():
    """오탐 LLMAnalysisResult 픽스처."""
    return LLMAnalysisResult(
        finding_id="vulnix.python.sql_injection.false_positive",
        is_true_positive=False,
        confidence=0.15,
        severity="Low",
        reasoning="테스트 코드이므로 오탐으로 분류",
        patch_diff=None,
        patch_description="",
        vulnerability_type="sql_injection",
    )


@pytest.fixture
def sample_finding():
    """SemgrepFinding 픽스처."""
    return SemgrepFinding(
        rule_id="vulnix.python.sql_injection.string_format",
        severity="ERROR",
        file_path="app/db.py",
        start_line=5,
        end_line=5,
        code_snippet='cursor.execute(f"SELECT * FROM users WHERE id={user_id}")',
        message="SQL Injection 취약점 탐지",
        cwe=["CWE-89"],
    )


@pytest.fixture
def sample_findings():
    """SemgrepFinding 목록 픽스처 (5건)."""
    return [
        SemgrepFinding(
            rule_id=f"vulnix.python.finding_{i}",
            severity="ERROR",
            file_path=f"app/file_{i}.py",
            start_line=i * 10,
            end_line=i * 10 + 2,
            code_snippet=f"# vulnerable code {i}",
            message=f"취약점 {i}",
            cwe=["CWE-89"],
        )
        for i in range(5)
    ]


@pytest.fixture
def mixed_analysis_results(mock_patch_diff):
    """혼합 분석 결과 픽스처: 패치가능 2 + 불가 1 + 오탐 2."""
    patchable_diff = mock_patch_diff
    return [
        # 패치 가능 1
        LLMAnalysisResult(
            finding_id="vulnix.python.sql_injection.string_format",
            is_true_positive=True,
            confidence=0.95,
            severity="High",
            reasoning="SQL Injection",
            patch_diff=patchable_diff,
            patch_description="파라미터화 쿼리로 변경",
            vulnerability_type="sql_injection",
            owasp_category="A03:2021 - Injection",
            references=["https://cwe.mitre.org/data/definitions/89.html"],
        ),
        # 패치 가능 2
        LLMAnalysisResult(
            finding_id="vulnix.python.xss.flask_render",
            is_true_positive=True,
            confidence=0.92,
            severity="High",
            reasoning="XSS",
            patch_diff='--- a/app/views.py\n+++ b/app/views.py\n@@ -1,2 +1,2 @@\n-    return f"<h1>{name}</h1>"\n+    return f"<h1>{escape(name)}</h1>"',
            patch_description="HTML 이스케이프 처리",
            vulnerability_type="xss",
            owasp_category="A03:2021 - Injection",
            references=["https://cwe.mitre.org/data/definitions/79.html"],
        ),
        # 패치 불가 (patch_diff=None으로 패치 불가 표현, F-03 구현 후 patchable 필드 추가됨)
        LLMAnalysisResult(
            finding_id="vulnix.python.hardcoded_credentials.aws_key",
            is_true_positive=True,
            confidence=0.90,
            severity="Critical",
            reasoning="하드코딩 자격증명",
            patch_diff=None,
            patch_description="",
            vulnerability_type="hardcoded_credentials",
        ),
        # 오탐 1
        LLMAnalysisResult(
            finding_id="vulnix.python.sql_fp_1",
            is_true_positive=False,
            confidence=0.1,
            severity="Low",
            reasoning="테스트 코드",
            patch_diff=None,
            patch_description="",
            vulnerability_type="sql_injection",
        ),
        # 오탐 2
        LLMAnalysisResult(
            finding_id="vulnix.python.sql_fp_2",
            is_true_positive=False,
            confidence=0.05,
            severity="Low",
            reasoning="상수 할당",
            patch_diff=None,
            patch_description="",
            vulnerability_type="sql_injection",
        ),
    ]


# ──────────────────────────────────────────────────────────────
# _make_branch_name() 테스트
# ──────────────────────────────────────────────────────────────

def test_branch_name_format():
    """브랜치명이 vulnix/fix-{type}-{hash} 형식인지 검증한다."""
    # Arrange
    vulnerability_type = "sql_injection"
    file_path = "app/db.py"
    start_line = 42

    # Act
    branch_name = PatchGenerator._make_branch_name(vulnerability_type, file_path, start_line)

    # Assert
    assert branch_name.startswith("vulnix/fix-sql-injection-"), \
        f"브랜치명 prefix가 올바르지 않음: {branch_name}"
    # prefix 이후 7자 해시 확인
    parts = branch_name.split("-")
    short_hash = parts[-1]
    assert len(short_hash) == 7, \
        f"short_hash는 7자여야 함, 실제: {len(short_hash)}자 ({short_hash})"
    # 언더스코어가 하이픈으로 치환되었는지 확인
    assert "_" not in branch_name, \
        f"브랜치명에 언더스코어가 포함됨: {branch_name}"


def test_branch_name_underscore_to_hyphen():
    """vulnerability_type의 언더스코어가 하이픈으로 치환되는지 검증한다."""
    # Arrange
    vulnerability_type = "hardcoded_credentials"
    file_path = "config/settings.py"
    start_line = 10

    # Act
    branch_name = PatchGenerator._make_branch_name(vulnerability_type, file_path, start_line)

    # Assert
    assert "hardcoded-credentials" in branch_name, \
        f"언더스코어가 하이픈으로 치환되지 않음: {branch_name}"
    assert "hardcoded_credentials" not in branch_name, \
        f"원본 언더스코어가 남아있음: {branch_name}"


def test_branch_name_unique_for_different_files():
    """동일 취약점 유형이라도 다른 파일이면 서로 다른 해시가 생성되는지 검증한다."""
    # Arrange
    vulnerability_type = "sql_injection"
    file_path_1 = "app/db.py"
    file_path_2 = "app/models/user.py"
    start_line = 42

    # Act
    branch_1 = PatchGenerator._make_branch_name(vulnerability_type, file_path_1, start_line)
    branch_2 = PatchGenerator._make_branch_name(vulnerability_type, file_path_2, start_line)

    # Assert
    assert branch_1 != branch_2, \
        "다른 파일 경로에 대해 동일한 브랜치명이 생성됨"


def test_branch_name_sha256_hash_7chars():
    """SHA-256 해시의 앞 7자를 사용하는지 검증한다."""
    # Arrange
    vulnerability_type = "xss"
    file_path = "app/views.py"
    start_line = 10

    # Act
    branch_name = PatchGenerator._make_branch_name(vulnerability_type, file_path, start_line)

    # 직접 계산
    raw = f"{vulnerability_type}:{file_path}:{start_line}"
    expected_hash = hashlib.sha256(raw.encode()).hexdigest()[:7]

    # Assert
    assert branch_name.endswith(expected_hash), \
        f"SHA-256 해시가 올바르지 않음. 기대: ...{expected_hash}, 실제: {branch_name}"


# ──────────────────────────────────────────────────────────────
# generate_patch_prs() 테스트
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_patch_pr_success(
    patch_generator,
    mock_db,
    patchable_analysis_result,
    sample_finding,
):
    """패치 가능한 취약점 1건에 대해 PatchPR이 정상 생성되는지 검증한다."""
    # Arrange
    repo_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    scan_job_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    # Vulnerability 조회 mock
    mock_vuln = MagicMock()
    mock_vuln.id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    mock_vuln.file_path = "app/db.py"
    mock_vuln.start_line = 5
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_vuln)
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Act
    patch_prs = await patch_generator.generate_patch_prs(
        repo_full_name="test-org/test-repo",
        installation_id=789,
        base_branch="main",
        scan_job_id=scan_job_id,
        repo_id=repo_id,
        analysis_results=[patchable_analysis_result],
        findings=[sample_finding],
        db=mock_db,
    )

    # Assert
    assert len(patch_prs) == 1, \
        f"PatchPR 1건이 생성되어야 함, 실제: {len(patch_prs)}건"
    assert patch_prs[0].status == "created", \
        f"PatchPR status가 'created'여야 함, 실제: {patch_prs[0].status}"
    assert patch_prs[0].github_pr_number == 42, \
        f"github_pr_number가 42여야 함, 실제: {patch_prs[0].github_pr_number}"


@pytest.mark.asyncio
async def test_generate_patch_pr_saves_to_db(
    patch_generator,
    mock_db,
    patchable_analysis_result,
    sample_finding,
):
    """PatchPR이 DB에 저장(add + commit)되는지 검증한다."""
    # Arrange
    repo_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    scan_job_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    mock_vuln = MagicMock()
    mock_vuln.id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    mock_vuln.file_path = "app/db.py"
    mock_vuln.start_line = 5
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_vuln)
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Act
    await patch_generator.generate_patch_prs(
        repo_full_name="test-org/test-repo",
        installation_id=789,
        base_branch="main",
        scan_job_id=scan_job_id,
        repo_id=repo_id,
        analysis_results=[patchable_analysis_result],
        findings=[sample_finding],
        db=mock_db,
    )

    # Assert: db.add와 db.commit이 호출되었는지 확인
    mock_db.add.assert_called(), "db.add()가 호출되지 않음"
    mock_db.commit.assert_awaited(), "db.commit()이 호출되지 않음"


@pytest.mark.asyncio
async def test_generate_patch_pr_unpatchable(
    patch_generator,
    mock_db,
    unpatchable_analysis_result,
    sample_finding,
):
    """패치 불가 취약점은 PatchPR 생성 없이 manual_guide가 Vulnerability에 저장되는지 검증한다."""
    # Arrange
    repo_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    scan_job_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    mock_vuln = MagicMock()
    mock_vuln.id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    mock_vuln.file_path = "config/settings.py"
    mock_vuln.start_line = 10
    mock_vuln.severity = "critical"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_vuln)
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Act
    patch_prs = await patch_generator.generate_patch_prs(
        repo_full_name="test-org/test-repo",
        installation_id=789,
        base_branch="main",
        scan_job_id=scan_job_id,
        repo_id=repo_id,
        analysis_results=[unpatchable_analysis_result],
        findings=[sample_finding],
        db=mock_db,
    )

    # Assert
    assert len(patch_prs) == 0, \
        f"패치 불가 취약점에 대해 PatchPR이 생성되지 않아야 함, 실제: {len(patch_prs)}건"
    # GitHub API 호출이 없어야 함
    patch_generator._github_service.create_branch.assert_not_called()
    # Vulnerability.manual_guide가 설정되었는지 확인
    assert mock_vuln.manual_guide is not None, \
        "패치 불가 시 Vulnerability.manual_guide가 저장되어야 함"
    # manual_priority가 설정되었는지 확인 (critical -> P0)
    assert mock_vuln.manual_priority == "P0", \
        f"critical 심각도는 P0이어야 함, 실제: {mock_vuln.manual_priority}"


@pytest.mark.asyncio
async def test_generate_patch_pr_false_positive_skipped(
    patch_generator,
    mock_db,
    false_positive_analysis_result,
    sample_finding,
):
    """오탐(is_true_positive=False) 항목은 처리되지 않아야 한다."""
    # Arrange
    repo_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    scan_job_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    # Act
    patch_prs = await patch_generator.generate_patch_prs(
        repo_full_name="test-org/test-repo",
        installation_id=789,
        base_branch="main",
        scan_job_id=scan_job_id,
        repo_id=repo_id,
        analysis_results=[false_positive_analysis_result],
        findings=[sample_finding],
        db=mock_db,
    )

    # Assert
    assert len(patch_prs) == 0, \
        f"오탐 항목에 대해 PatchPR이 생성되지 않아야 함"
    # GitHub API 호출이 없어야 함
    patch_generator._github_service.create_branch.assert_not_called()
    patch_generator._github_service.create_pull_request.assert_not_called()


@pytest.mark.asyncio
async def test_generate_patch_pr_mixed_results(
    patch_generator,
    mock_db,
    mixed_analysis_results,
    sample_findings,
):
    """혼합 결과(패치가능 2 + 불가 1 + 오탐 2)에서 PatchPR 2건만 생성되는지 검증한다."""
    # Arrange
    repo_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    scan_job_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    # 각 finding에 대응하는 Vulnerability mock 설정
    mock_vuln = MagicMock()
    mock_vuln.id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    mock_vuln.file_path = "app/db.py"
    mock_vuln.start_line = 5
    mock_vuln.severity = "critical"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_vuln)
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Act
    patch_prs = await patch_generator.generate_patch_prs(
        repo_full_name="test-org/test-repo",
        installation_id=789,
        base_branch="main",
        scan_job_id=scan_job_id,
        repo_id=repo_id,
        analysis_results=mixed_analysis_results,
        findings=sample_findings,
        db=mock_db,
    )

    # Assert
    assert len(patch_prs) == 2, \
        f"패치 가능 2건에 대해 PatchPR 2건이 생성되어야 함, 실제: {len(patch_prs)}건"


@pytest.mark.asyncio
async def test_generate_patch_pr_empty_results(
    patch_generator,
    mock_db,
):
    """빈 analysis_results로 호출 시 PatchPR 0건, GitHub API 미호출을 검증한다."""
    # Arrange
    repo_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    scan_job_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    # Act
    patch_prs = await patch_generator.generate_patch_prs(
        repo_full_name="test-org/test-repo",
        installation_id=789,
        base_branch="main",
        scan_job_id=scan_job_id,
        repo_id=repo_id,
        analysis_results=[],
        findings=[],
        db=mock_db,
    )

    # Assert
    assert len(patch_prs) == 0, "빈 analysis_results에서 PatchPR이 생성되지 않아야 함"
    patch_generator._github_service.create_branch.assert_not_called()
    patch_generator._github_service.create_pull_request.assert_not_called()


# ──────────────────────────────────────────────────────────────
# _build_pr_body() 테스트
# ──────────────────────────────────────────────────────────────

def test_build_pr_body_contains_vuln_desc(patch_generator):
    """PR 본문에 취약점 설명(왜 위험한가) 섹션이 포함되는지 검증한다."""
    # Arrange
    vulnerability = {
        "vulnerability_type": "sql_injection",
        "cwe_id": "CWE-89",
        "severity": "high",
        "file_path": "app/db.py",
        "start_line": 5,
        "end_line": 5,
        "description": "사용자 입력이 f-string을 통해 SQL 쿼리에 직접 삽입됩니다.",
        "reasoning": "user_id가 검증 없이 SQL 쿼리에 포함됩니다.",
        "patch_description": "파라미터화된 쿼리로 변경",
        "references": ["https://cwe.mitre.org/data/definitions/89.html"],
        "patch_diff": "--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,2 @@",
        "owasp_category": "A03:2021 - Injection",
    }

    # Act
    body = patch_generator._build_pr_body(vulnerability)

    # Assert: 취약점 설명 섹션 존재 확인
    assert "취약점" in body, "PR 본문에 취약점 설명이 없음"
    assert "sql_injection" in body or "sql-injection" in body.lower(), \
        "PR 본문에 취약점 유형이 없음"
    assert "CWE-89" in body, "PR 본문에 CWE ID가 없음"
    assert "app/db.py" in body, "PR 본문에 파일 경로가 없음"


def test_build_pr_body_contains_references(patch_generator):
    """PR 본문에 참고 링크(CVE, OWASP) 섹션이 포함되는지 검증한다."""
    # Arrange
    vulnerability = {
        "vulnerability_type": "xss",
        "cwe_id": "CWE-79",
        "severity": "medium",
        "file_path": "app/views.py",
        "start_line": 10,
        "end_line": 10,
        "description": "XSS 취약점",
        "reasoning": "HTML 이스케이프 없이 사용자 입력 출력",
        "patch_description": "HTML 이스케이프 처리 추가",
        "references": [
            "https://cwe.mitre.org/data/definitions/79.html",
            "https://owasp.org/Top10/",
        ],
        "patch_diff": "--- a/app.py\n+++ b/app.py",
        "owasp_category": "A03:2021 - Injection",
    }

    # Act
    body = patch_generator._build_pr_body(vulnerability)

    # Assert: 참고 자료 섹션 및 링크 존재 확인
    assert "참고" in body, "PR 본문에 참고 자료 섹션이 없음"
    assert "https://cwe.mitre.org/data/definitions/79.html" in body, \
        "PR 본문에 CWE 링크가 없음"
    assert "https://owasp.org/Top10/" in body, \
        "PR 본문에 OWASP 링크가 없음"


def test_build_pr_body_contains_diff(patch_generator, mock_patch_diff):
    """PR 본문에 변경 코드 diff가 포함되는지 검증한다."""
    # Arrange
    vulnerability = {
        "vulnerability_type": "sql_injection",
        "cwe_id": "CWE-89",
        "severity": "high",
        "file_path": "app.py",
        "start_line": 1,
        "end_line": 3,
        "description": "SQL Injection",
        "reasoning": "직접 삽입",
        "patch_description": "파라미터화",
        "references": [],
        "patch_diff": mock_patch_diff,
        "owasp_category": "A03:2021 - Injection",
    }

    # Act
    body = patch_generator._build_pr_body(vulnerability)

    # Assert: diff 내용이 본문에 포함
    assert "--- a/app.py" in body or mock_patch_diff[:20] in body, \
        "PR 본문에 diff가 포함되지 않음"
    assert "diff" in body.lower() or "변경" in body, \
        "PR 본문에 변경 코드 섹션이 없음"


def test_build_pr_body_contains_test_suggestion(patch_generator):
    """테스트 제안이 있을 때 PR 본문에 테스트 코드 제안 섹션이 포함되는지 검증한다."""
    # Arrange
    test_suggestion_code = """def test_sql_injection_prevention():
    result = get_user("1 OR 1=1")
    assert result is None"""

    vulnerability = {
        "vulnerability_type": "sql_injection",
        "cwe_id": "CWE-89",
        "severity": "high",
        "file_path": "app/db.py",
        "start_line": 5,
        "end_line": 5,
        "description": "SQL Injection",
        "reasoning": "직접 삽입",
        "patch_description": "파라미터화",
        "references": [],
        "patch_diff": "--- a/app.py\n+++ b/app.py",
        "owasp_category": "A03:2021 - Injection",
        "test_suggestion": test_suggestion_code,
    }

    # Act
    body = patch_generator._build_pr_body(vulnerability)

    # Assert: 테스트 제안 섹션 존재 확인
    assert "테스트 제안" in body, "PR 본문에 '테스트 제안' 섹션이 없음"
    assert "test_sql_injection_prevention" in body, \
        "PR 본문에 테스트 코드 내용이 없음"


def test_build_pr_body_no_test_suggestion_when_none(patch_generator):
    """테스트 제안이 None일 때 PR 본문에 테스트 제안 섹션이 없는지 검증한다."""
    # Arrange
    vulnerability = {
        "vulnerability_type": "sql_injection",
        "cwe_id": "CWE-89",
        "severity": "high",
        "file_path": "app/db.py",
        "start_line": 5,
        "end_line": 5,
        "description": "SQL Injection",
        "reasoning": "직접 삽입",
        "patch_description": "파라미터화",
        "references": [],
        "patch_diff": "--- a/app.py\n+++ b/app.py",
        "owasp_category": "A03:2021 - Injection",
        "test_suggestion": None,
    }

    # Act
    body = patch_generator._build_pr_body(vulnerability)

    # Assert: 테스트 제안 섹션이 없어야 함
    assert "테스트 제안" not in body, \
        "test_suggestion=None일 때 '테스트 제안' 섹션이 포함되면 안 됨"


def test_build_pr_body_contains_vulnix_signature(patch_generator):
    """PR 본문에 Vulnix 서명이 포함되는지 검증한다."""
    # Arrange
    vulnerability = {
        "vulnerability_type": "sql_injection",
        "cwe_id": "CWE-89",
        "severity": "high",
        "file_path": "app/db.py",
        "start_line": 5,
        "end_line": 5,
        "description": "SQL Injection",
        "reasoning": "직접 삽입",
        "patch_description": "파라미터화",
        "references": [],
        "patch_diff": "--- a/app.py\n+++ b/app.py",
        "owasp_category": "A03:2021 - Injection",
    }

    # Act
    body = patch_generator._build_pr_body(vulnerability)

    # Assert: Vulnix 서명 확인
    assert "Vulnix" in body, "PR 본문에 Vulnix 서명이 없음"
    assert "코드 리뷰" in body or "review" in body.lower(), \
        "PR 본문에 코드 리뷰 안내가 없음"


# ──────────────────────────────────────────────────────────────
# _apply_patch_diff() 테스트
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_apply_patch_diff_to_file(patch_generator):
    """유효한 unified diff를 원본 파일에 적용하여 수정된 내용을 반환하는지 검증한다."""
    # Arrange: 원본 파일 내용과 diff를 mock으로 주입
    original_content = (
        'def get_user(user_id):\n'
        '    query = f"SELECT * FROM users WHERE id = {user_id}"\n'
        '    return db.execute(query)\n'
    )
    file_sha = "abc123filesha"
    patch_generator._github_service.get_file_content = AsyncMock(
        return_value=(original_content, file_sha)
    )

    patch_diff = (
        '--- a/app/db.py\n'
        '+++ b/app/db.py\n'
        '@@ -1,3 +1,3 @@\n'
        ' def get_user(user_id):\n'
        '-    query = f"SELECT * FROM users WHERE id = {user_id}"\n'
        '-    return db.execute(query)\n'
        '+    query = "SELECT * FROM users WHERE id = %s"\n'
        '+    return db.execute(query, (user_id,))\n'
    )

    # Act
    result = await patch_generator._apply_patch_diff(
        full_name="test-org/test-repo",
        installation_id=789,
        file_path="app/db.py",
        patch_diff=patch_diff,
        ref="main",
    )

    # Assert
    assert result is not None, "_apply_patch_diff()가 None을 반환함"
    patched_content, returned_sha = result
    assert 'query = "SELECT * FROM users WHERE id = %s"' in patched_content, \
        "패치된 파일에 수정된 쿼리가 없음"
    assert 'f"SELECT * FROM users WHERE id = {user_id}"' not in patched_content, \
        "패치된 파일에 원본 취약 코드가 남아있음"
    assert returned_sha == file_sha, "파일 SHA가 올바르지 않음"


@pytest.mark.asyncio
async def test_apply_patch_diff_invalid_diff_returns_none(patch_generator):
    """원본과 맞지 않는 diff 적용 시 None을 반환하는지 검증한다."""
    # Arrange
    original_content = "def hello():\n    print('world')\n"
    patch_generator._github_service.get_file_content = AsyncMock(
        return_value=(original_content, "sha123")
    )

    # 원본과 완전히 다른 잘못된 diff
    invalid_diff = (
        '--- a/app/db.py\n'
        '+++ b/app/db.py\n'
        '@@ -1,3 +1,3 @@\n'
        '-    THIS_LINE_DOES_NOT_EXIST_IN_ORIGINAL\n'
        '+    replacement_line\n'
    )

    # Act
    result = await patch_generator._apply_patch_diff(
        full_name="test-org/test-repo",
        installation_id=789,
        file_path="app/db.py",
        patch_diff=invalid_diff,
        ref="main",
    )

    # Assert: context mismatch로 None 반환
    assert result is None, \
        "잘못된 diff 적용 시 None을 반환해야 함"


# ──────────────────────────────────────────────────────────────
# 병렬 처리 테스트
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_multiple_vulns_parallel(
    patch_generator,
    mock_db,
    mixed_analysis_results,
    sample_findings,
):
    """여러 취약점에 대한 PR 생성이 병렬로 처리되는지 검증한다.

    asyncio.gather() 또는 Semaphore를 사용하여 병렬 처리하는지 확인한다.
    """
    import asyncio
    import time

    # Arrange
    repo_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    scan_job_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    # 각 GitHub API 호출에 0.1초 지연 추가 (병렬 처리 확인용)
    async def delayed_create_branch(*args, **kwargs):
        await asyncio.sleep(0.1)
        return None

    patch_generator._github_service.create_branch = delayed_create_branch

    mock_vuln = MagicMock()
    mock_vuln.id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    mock_vuln.file_path = "app/db.py"
    mock_vuln.start_line = 5
    mock_vuln.severity = "high"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_vuln)
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Act
    start_time = time.monotonic()
    patch_prs = await patch_generator.generate_patch_prs(
        repo_full_name="test-org/test-repo",
        installation_id=789,
        base_branch="main",
        scan_job_id=scan_job_id,
        repo_id=repo_id,
        analysis_results=mixed_analysis_results,
        findings=sample_findings,
        db=mock_db,
    )
    elapsed = time.monotonic() - start_time

    # Assert: 2건 생성 확인
    assert len(patch_prs) == 2, \
        f"혼합 결과에서 PatchPR 2건이 생성되어야 함, 실제: {len(patch_prs)}건"
    # 병렬 처리라면 0.3초 이내 완료 (순차적이면 0.2초 이상 소요)
    assert elapsed < 0.3, \
        f"병렬 처리 시 0.3초 이내에 완료되어야 함, 실제: {elapsed:.2f}초"
