"""ScanWorker 통합 테스트 — F-02 RED 단계

구현이 완료되지 않은 상태에서 실행하면 모두 FAIL이어야 한다.
"""

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.llm_agent import LLMAnalysisResult
from src.services.semgrep_engine import SemgrepEngine, SemgrepFinding
from src.workers.scan_worker import _run_scan_async


# scan_orchestrator는 redis 의존성이 있으므로 테스트 전용 ScanJobMessage를 직접 정의
@dataclass
class ScanJobMessage:
    """테스트 전용 ScanJobMessage (redis 의존성 우회)."""

    job_id: str
    repo_id: str
    trigger: str = "push"
    commit_sha: str | None = None
    branch: str | None = "main"
    pr_number: int | None = None
    scan_type: str = "full"
    changed_files: list[str] | None = None
    created_at: str = "2026-02-25T00:00:00Z"


# ──────────────────────────────────────────────────────────────
# 픽스처
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def job_id():
    """테스트용 스캔 작업 ID 픽스처."""
    return "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


@pytest.fixture
def repo_id():
    """테스트용 저장소 ID 픽스처."""
    return "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


@pytest.fixture
def scan_job_message(job_id, repo_id):
    """ScanJobMessage 픽스처."""
    return ScanJobMessage(
        job_id=job_id,
        repo_id=repo_id,
        commit_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        trigger="push",
    )


@pytest.fixture
def mock_repo(repo_id):
    """Repository 모델 mock 픽스처."""
    repo = MagicMock()
    repo.id = uuid.UUID(repo_id)
    repo.full_name = "test-org/test-repo"
    repo.installation_id = 789
    repo.default_branch = "main"
    return repo


@pytest.fixture
def sql_injection_finding(job_id):
    """SQL Injection SemgrepFinding 픽스처."""
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
def xss_finding():
    """XSS SemgrepFinding 픽스처."""
    return SemgrepFinding(
        rule_id="vulnix.python.xss.flask_render_html",
        severity="ERROR",
        file_path="app/views.py",
        start_line=10,
        end_line=10,
        code_snippet="return make_response(user_input)",
        message="XSS 취약점 탐지",
        cwe=["CWE-79"],
    )


@pytest.fixture
def true_positive_result(sql_injection_finding):
    """진양성 LLMAnalysisResult 픽스처."""
    return LLMAnalysisResult(
        finding_id=sql_injection_finding.rule_id,
        is_true_positive=True,
        confidence=0.95,
        severity="High",
        reasoning="사용자 입력이 SQL 쿼리에 직접 삽입됨",
        patch_diff='--- a/app/db.py\n+++ b/app/db.py\n@@ -5 +5 @@\n-bad\n+good',
        patch_description="파라미터화된 쿼리로 변경",
        references=["https://cwe.mitre.org/data/definitions/89.html"],
    )


@pytest.fixture
def false_positive_result(xss_finding):
    """오탐 LLMAnalysisResult 픽스처."""
    return LLMAnalysisResult(
        finding_id=xss_finding.rule_id,
        is_true_positive=False,
        confidence=0.85,
        severity="Low",
        reasoning="테스트 코드이므로 오탐으로 판단",
        patch_diff=None,
        patch_description="",
        references=[],
    )


# ──────────────────────────────────────────────────────────────
# 전체 파이프라인 테스트
# ──────────────────────────────────────────────────────────────

async def test_process_scan_job_full_pipeline(
    scan_job_message,
    mock_repo,
    sql_injection_finding,
    xss_finding,
    true_positive_result,
    false_positive_result,
    job_id,
):
    """전체 스캔 파이프라인이 정상 실행되면 completed 결과를 반환한다.

    Semgrep: 2건 탐지 (sql_injection, xss)
    LLM: 1 TP (sql_injection) + 1 FP (xss)
    기대 결과: ScanJob status=completed, Vulnerability 1건 저장
    """
    # Arrange
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.scalar_one.return_value = mock_repo
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_orchestrator = AsyncMock()
    mock_orchestrator.update_job_status = AsyncMock()

    mock_semgrep = MagicMock()
    mock_semgrep.scan.return_value = [sql_injection_finding, xss_finding]

    mock_llm = AsyncMock()
    mock_llm.analyze_findings = AsyncMock(side_effect=[
        [true_positive_result],
        [false_positive_result],
    ])

    mock_github = AsyncMock()
    mock_github.clone_repository = AsyncMock()

    with (
        patch("src.workers.scan_worker.SemgrepEngine", return_value=mock_semgrep),
        patch("src.workers.scan_worker.LLMAgent", return_value=mock_llm),
        patch("src.workers.scan_worker.GitHubAppService", return_value=mock_github),
        patch("src.workers.scan_worker.get_async_session", create=True) as mock_session,
        patch("src.workers.scan_worker.ScanOrchestrator", create=True, return_value=mock_orchestrator),
        patch("src.services.semgrep_engine.SemgrepEngine.cleanup_temp_dir"),
    ):
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

        # Act
        result = await _run_scan_async(scan_job_message)

    # Assert
    assert result["status"] == "completed"
    assert result["job_id"] == job_id


async def test_process_scan_job_saves_vulnerabilities(
    scan_job_message,
    mock_repo,
    sql_injection_finding,
    true_positive_result,
):
    """진양성 취약점이 DB에 저장된다."""
    # Arrange
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.scalar_one.return_value = mock_repo
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_orchestrator = AsyncMock()
    mock_orchestrator.update_job_status = AsyncMock()

    mock_semgrep = MagicMock()
    mock_semgrep.scan.return_value = [sql_injection_finding]

    mock_llm = AsyncMock()
    mock_llm.analyze_findings = AsyncMock(return_value=[true_positive_result])

    mock_github = AsyncMock()
    mock_github.clone_repository = AsyncMock()

    with (
        patch("src.workers.scan_worker.SemgrepEngine", return_value=mock_semgrep),
        patch("src.workers.scan_worker.LLMAgent", return_value=mock_llm),
        patch("src.workers.scan_worker.GitHubAppService", return_value=mock_github),
        patch("src.workers.scan_worker.get_async_session", create=True) as mock_session,
        patch("src.workers.scan_worker.ScanOrchestrator", create=True, return_value=mock_orchestrator),
        patch("src.services.semgrep_engine.SemgrepEngine.cleanup_temp_dir"),
    ):
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

        # Act
        await _run_scan_async(scan_job_message)

    # Assert: DB에 add()가 호출되어 취약점이 저장됨
    assert mock_db.add.call_count >= 1


async def test_process_scan_job_no_findings_skips_llm(
    scan_job_message,
    mock_repo,
    job_id,
):
    """Semgrep 결과가 없으면 LLM을 호출하지 않고 completed 처리한다."""
    # Arrange
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.scalar_one.return_value = mock_repo
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_orchestrator = AsyncMock()
    mock_orchestrator.update_job_status = AsyncMock()

    mock_semgrep = MagicMock()
    mock_semgrep.scan.return_value = []  # 0건

    mock_llm = AsyncMock()
    mock_llm.analyze_findings = AsyncMock()

    mock_github = AsyncMock()
    mock_github.clone_repository = AsyncMock()

    with (
        patch("src.workers.scan_worker.SemgrepEngine", return_value=mock_semgrep),
        patch("src.workers.scan_worker.LLMAgent", return_value=mock_llm),
        patch("src.workers.scan_worker.GitHubAppService", return_value=mock_github),
        patch("src.workers.scan_worker.get_async_session", create=True) as mock_session,
        patch("src.workers.scan_worker.ScanOrchestrator", create=True, return_value=mock_orchestrator),
        patch("src.services.semgrep_engine.SemgrepEngine.cleanup_temp_dir"),
    ):
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

        # Act
        result = await _run_scan_async(scan_job_message)

    # Assert
    assert result["status"] == "completed"
    # LLM이 호출되지 않아야 함
    mock_llm.analyze_findings.assert_not_called()


async def test_process_scan_job_updates_job_status(
    scan_job_message,
    mock_repo,
    sql_injection_finding,
    true_positive_result,
):
    """파이프라인 완료 후 ScanJob 상태가 'completed'로 업데이트된다."""
    # Arrange
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.scalar_one.return_value = mock_repo
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_orchestrator = AsyncMock()
    mock_orchestrator.update_job_status = AsyncMock()

    mock_semgrep = MagicMock()
    mock_semgrep.scan.return_value = [sql_injection_finding]

    mock_llm = AsyncMock()
    mock_llm.analyze_findings = AsyncMock(return_value=[true_positive_result])

    mock_github = AsyncMock()
    mock_github.clone_repository = AsyncMock()

    with (
        patch("src.workers.scan_worker.SemgrepEngine", return_value=mock_semgrep),
        patch("src.workers.scan_worker.LLMAgent", return_value=mock_llm),
        patch("src.workers.scan_worker.GitHubAppService", return_value=mock_github),
        patch("src.workers.scan_worker.get_async_session", create=True) as mock_session,
        patch("src.workers.scan_worker.ScanOrchestrator", create=True, return_value=mock_orchestrator),
        patch("src.services.semgrep_engine.SemgrepEngine.cleanup_temp_dir"),
    ):
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

        # Act
        await _run_scan_async(scan_job_message)

    # Assert: completed 상태 업데이트 호출 확인
    calls = mock_orchestrator.update_job_status.call_args_list
    completed_calls = [c for c in calls if "completed" in str(c)]
    assert len(completed_calls) >= 1


async def test_process_scan_job_failure_marks_failed(
    scan_job_message,
    mock_repo,
    job_id,
):
    """파이프라인 실패 시 ScanJob 상태가 'failed'로 업데이트된다."""
    # Arrange
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.scalar_one.return_value = mock_repo
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_orchestrator = AsyncMock()
    mock_orchestrator.update_job_status = AsyncMock()

    mock_semgrep = MagicMock()
    mock_semgrep.scan.side_effect = RuntimeError("Semgrep 실행 에러 (returncode=2)")

    mock_github = AsyncMock()
    mock_github.clone_repository = AsyncMock()

    with (
        patch("src.workers.scan_worker.SemgrepEngine", return_value=mock_semgrep),
        patch("src.workers.scan_worker.GitHubAppService", return_value=mock_github),
        patch("src.workers.scan_worker.get_async_session", create=True) as mock_session,
        patch("src.workers.scan_worker.ScanOrchestrator", create=True, return_value=mock_orchestrator),
        patch("src.services.semgrep_engine.SemgrepEngine.cleanup_temp_dir"),
    ):
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

        # Act: 예외가 발생해야 함
        with pytest.raises(RuntimeError):
            await _run_scan_async(scan_job_message)

    # Assert: failed 상태 업데이트 호출 확인
    calls = mock_orchestrator.update_job_status.call_args_list
    failed_calls = [c for c in calls if "failed" in str(c)]
    assert len(failed_calls) >= 1


async def test_process_scan_job_cleans_temp_dir(
    scan_job_message,
    mock_repo,
    sql_injection_finding,
    true_positive_result,
    job_id,
):
    """파이프라인 완료 후 임시 디렉토리가 삭제된다 (finally 블록)."""
    # Arrange
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.scalar_one.return_value = mock_repo
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_orchestrator = AsyncMock()
    mock_orchestrator.update_job_status = AsyncMock()

    mock_semgrep = MagicMock()
    mock_semgrep.scan.return_value = [sql_injection_finding]

    mock_llm = AsyncMock()
    mock_llm.analyze_findings = AsyncMock(return_value=[true_positive_result])

    mock_github = AsyncMock()
    mock_github.clone_repository = AsyncMock()

    with (
        patch("src.workers.scan_worker.SemgrepEngine", return_value=mock_semgrep),
        patch("src.workers.scan_worker.LLMAgent", return_value=mock_llm),
        patch("src.workers.scan_worker.GitHubAppService", return_value=mock_github),
        patch("src.workers.scan_worker.get_async_session", create=True) as mock_session,
        patch("src.workers.scan_worker.ScanOrchestrator", create=True, return_value=mock_orchestrator),
        patch.object(
            SemgrepEngine,
            "cleanup_temp_dir",
        ) as mock_cleanup,
    ):
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

        # Act
        await _run_scan_async(scan_job_message)

    # Assert: cleanup이 job_id를 인자로 호출되어야 함
    mock_cleanup.assert_called_once_with(job_id)


async def test_vulnerability_deduplication(
    scan_job_message,
    mock_repo,
    job_id,
):
    """동일 위치의 취약점이 중복 저장되지 않는다.

    같은 파일/라인에서 다른 rule_id로 2건이 탐지되어도
    각각 별도 레코드로 저장되되, 완전히 동일한 취약점은 1건만 저장되어야 한다.
    """
    # Arrange: 동일한 rule_id를 가진 finding이 2개인 경우
    duplicate_finding_1 = SemgrepFinding(
        rule_id="vulnix.python.sql_injection.string_format",
        severity="ERROR",
        file_path="app/db.py",
        start_line=5,
        end_line=5,
        code_snippet='cursor.execute(f"SELECT...")',
        message="SQL Injection 취약점",
        cwe=["CWE-89"],
    )
    duplicate_finding_2 = SemgrepFinding(
        rule_id="vulnix.python.sql_injection.string_format",  # 동일 rule_id
        severity="ERROR",
        file_path="app/db.py",
        start_line=5,
        end_line=5,
        code_snippet='cursor.execute(f"SELECT...")',
        message="SQL Injection 취약점",
        cwe=["CWE-89"],
    )

    tp_result_1 = LLMAnalysisResult(
        finding_id="vulnix.python.sql_injection.string_format",
        is_true_positive=True,
        confidence=0.95,
        severity="High",
        reasoning="SQL Injection",
        patch_diff=None,
        patch_description="",
        references=[],
    )

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.scalar_one.return_value = mock_repo
    add_calls = []
    mock_db.add = MagicMock(side_effect=lambda obj: add_calls.append(obj))
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_orchestrator = AsyncMock()
    mock_orchestrator.update_job_status = AsyncMock()

    mock_semgrep = MagicMock()
    mock_semgrep.scan.return_value = [duplicate_finding_1, duplicate_finding_2]

    mock_llm = AsyncMock()
    mock_llm.analyze_findings = AsyncMock(return_value=[tp_result_1])

    mock_github = AsyncMock()
    mock_github.clone_repository = AsyncMock()

    with (
        patch("src.workers.scan_worker.SemgrepEngine", return_value=mock_semgrep),
        patch("src.workers.scan_worker.LLMAgent", return_value=mock_llm),
        patch("src.workers.scan_worker.GitHubAppService", return_value=mock_github),
        patch("src.workers.scan_worker.get_async_session", create=True) as mock_session,
        patch("src.workers.scan_worker.ScanOrchestrator", create=True, return_value=mock_orchestrator),
        patch("src.services.semgrep_engine.SemgrepEngine.cleanup_temp_dir"),
    ):
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

        # Act
        await _run_scan_async(scan_job_message)

    # Assert: 동일 finding_id를 가진 LLMAnalysisResult는 중복 저장되지 않음
    # (finding_map은 rule_id 기준으로 인덱싱되므로 1건만 저장)
    from src.models.vulnerability import Vulnerability
    vuln_records = [c for c in add_calls if hasattr(c, "vulnerability_type")]
    assert len(vuln_records) == 1
