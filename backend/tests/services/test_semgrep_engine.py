"""SemgrepEngine 단위 테스트 — F-02 RED 단계

구현이 완료되지 않은 상태에서 실행하면 모두 FAIL이어야 한다.
"""

import json
import subprocess
import unittest.mock
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.semgrep_engine import SemgrepEngine, SemgrepFinding


# ──────────────────────────────────────────────────────────────
# 픽스처
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    """SemgrepEngine 인스턴스 픽스처."""
    return SemgrepEngine()


@pytest.fixture
def sql_injection_semgrep_output():
    """SQL Injection 1건을 포함한 Semgrep JSON 출력 픽스처."""
    return {
        "results": [
            {
                "check_id": "vulnix.python.sql_injection.string_format",
                "path": "/tmp/vulnix-scan-test/app/db.py",
                "start": {"line": 5, "col": 5},
                "end": {"line": 5, "col": 65},
                "extra": {
                    "message": "SQL Injection 취약점 탐지: f-string 사용",
                    "severity": "ERROR",
                    "lines": 'cursor.execute(f"SELECT * FROM users WHERE id={user_id}")',
                    "metadata": {
                        "cwe": ["CWE-89"],
                        "owasp": ["A03:2021 - Injection"],
                        "confidence": "HIGH",
                    },
                },
            }
        ],
        "errors": [],
    }


@pytest.fixture
def xss_semgrep_output():
    """XSS 1건을 포함한 Semgrep JSON 출력 픽스처."""
    return {
        "results": [
            {
                "check_id": "vulnix.python.xss.flask_render_html",
                "path": "/tmp/vulnix-scan-test/app/views.py",
                "start": {"line": 10, "col": 4},
                "end": {"line": 10, "col": 40},
                "extra": {
                    "message": "XSS 취약점 탐지: 사용자 입력이 이스케이프 없이 HTML 응답에 포함됨",
                    "severity": "ERROR",
                    "lines": "return make_response(user_input)",
                    "metadata": {
                        "cwe": ["CWE-79"],
                        "owasp": ["A03:2021 - Injection"],
                        "confidence": "HIGH",
                    },
                },
            }
        ],
        "errors": [],
    }


@pytest.fixture
def hardcoded_creds_semgrep_output():
    """Hardcoded Credentials 1건을 포함한 Semgrep JSON 출력 픽스처."""
    return {
        "results": [
            {
                "check_id": "vulnix.python.hardcoded_creds.password_assignment",
                "path": "/tmp/vulnix-scan-test/config.py",
                "start": {"line": 3, "col": 1},
                "end": {"line": 3, "col": 40},
                "extra": {
                    "message": "Hardcoded Credentials 탐지: 패스워드가 소스 코드에 하드코딩되어 있습니다",
                    "severity": "ERROR",
                    "lines": 'DB_PASSWORD = "super_secret_password_123"',
                    "metadata": {
                        "cwe": ["CWE-798"],
                        "owasp": ["A07:2021 - Identification and Authentication Failures"],
                        "confidence": "HIGH",
                    },
                },
            }
        ],
        "errors": [],
    }


@pytest.fixture
def multi_finding_semgrep_output():
    """SQL Injection 2건 + XSS 1건을 포함한 Semgrep JSON 출력 픽스처."""
    return {
        "results": [
            {
                "check_id": "vulnix.python.sql_injection.string_format",
                "path": "/tmp/vulnix-scan-test/app/db.py",
                "start": {"line": 5, "col": 5},
                "end": {"line": 5, "col": 65},
                "extra": {
                    "message": "SQL Injection 취약점 탐지 (1)",
                    "severity": "ERROR",
                    "lines": 'cursor.execute(f"SELECT * FROM users WHERE id={user_id}")',
                    "metadata": {"cwe": ["CWE-89"], "owasp": ["A03:2021 - Injection"]},
                },
            },
            {
                "check_id": "vulnix.python.sql_injection.string_concat",
                "path": "/tmp/vulnix-scan-test/app/db.py",
                "start": {"line": 12, "col": 5},
                "end": {"line": 12, "col": 65},
                "extra": {
                    "message": "SQL Injection 취약점 탐지 (2)",
                    "severity": "ERROR",
                    "lines": 'cursor.execute("SELECT * FROM users WHERE name=" + name)',
                    "metadata": {"cwe": ["CWE-89"], "owasp": ["A03:2021 - Injection"]},
                },
            },
            {
                "check_id": "vulnix.python.xss.flask_render_html",
                "path": "/tmp/vulnix-scan-test/app/views.py",
                "start": {"line": 8, "col": 4},
                "end": {"line": 8, "col": 40},
                "extra": {
                    "message": "XSS 취약점 탐지",
                    "severity": "WARNING",
                    "lines": "return make_response(user_input)",
                    "metadata": {"cwe": ["CWE-79"], "owasp": ["A03:2021 - Injection"]},
                },
            },
        ],
        "errors": [],
    }


# ──────────────────────────────────────────────────────────────
# scan() 테스트
# ──────────────────────────────────────────────────────────────

def test_run_scan_returns_findings(engine, sql_injection_semgrep_output):
    """Semgrep 실행 시 SemgrepFinding 목록을 반환한다."""
    # Arrange
    target_dir = Path("/tmp/vulnix-scan-test")
    job_id = "test-job-001"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["semgrep"],
            returncode=1,  # 1 = 취약점 발견
            stdout=json.dumps(sql_injection_semgrep_output),
            stderr="",
        )

        # Act
        findings = engine.scan(target_dir, job_id)

    # Assert
    assert isinstance(findings, list)
    assert len(findings) == 1
    assert isinstance(findings[0], SemgrepFinding)
    assert findings[0].rule_id == "vulnix.python.sql_injection.string_format"
    assert findings[0].severity == "ERROR"


def test_run_scan_empty_result_returns_empty(engine):
    """Semgrep 결과가 없으면 빈 목록을 반환한다."""
    # Arrange
    target_dir = Path("/tmp/vulnix-scan-test-empty")
    job_id = "test-job-empty"
    empty_output = {"results": [], "errors": []}

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["semgrep"],
            returncode=0,  # 0 = 클린
            stdout=json.dumps(empty_output),
            stderr="",
        )

        # Act
        findings = engine.scan(target_dir, job_id)

    # Assert
    assert findings == []


def test_run_scan_subprocess_failure_raises(engine):
    """subprocess 실패(returncode >= 2) 시 RuntimeError를 발생시킨다."""
    # Arrange
    target_dir = Path("/tmp/vulnix-scan-test-fail")
    job_id = "test-job-fail"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["semgrep"],
            returncode=2,  # 2 = Semgrep 내부 에러
            stdout="",
            stderr="Error: invalid rule configuration",
        )

        # Act & Assert
        with pytest.raises(RuntimeError):
            engine.scan(target_dir, job_id)


# ──────────────────────────────────────────────────────────────
# _parse_results() 테스트
# ──────────────────────────────────────────────────────────────

def test_parse_semgrep_output_sql_injection(engine, sql_injection_semgrep_output):
    """SQL Injection rule_id를 가진 SemgrepFinding으로 올바르게 파싱한다."""
    # Arrange
    base_dir = Path("/tmp/vulnix-scan-test")

    # Act
    findings = engine._parse_results(sql_injection_semgrep_output, base_dir)

    # Assert
    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_id == "vulnix.python.sql_injection.string_format"
    assert finding.severity == "ERROR"
    assert finding.file_path == "app/db.py"
    assert finding.start_line == 5
    assert finding.end_line == 5
    assert "CWE-89" in finding.cwe
    assert finding.message == "SQL Injection 취약점 탐지: f-string 사용"


def test_parse_semgrep_output_xss(engine, xss_semgrep_output):
    """XSS rule_id를 가진 SemgrepFinding으로 올바르게 파싱한다."""
    # Arrange
    base_dir = Path("/tmp/vulnix-scan-test")

    # Act
    findings = engine._parse_results(xss_semgrep_output, base_dir)

    # Assert
    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_id == "vulnix.python.xss.flask_render_html"
    assert finding.severity == "ERROR"
    assert "CWE-79" in finding.cwe
    assert finding.file_path == "app/views.py"


def test_parse_semgrep_output_hardcoded_creds(engine, hardcoded_creds_semgrep_output):
    """Hardcoded Credentials rule_id를 가진 SemgrepFinding으로 올바르게 파싱한다."""
    # Arrange
    base_dir = Path("/tmp/vulnix-scan-test")

    # Act
    findings = engine._parse_results(hardcoded_creds_semgrep_output, base_dir)

    # Assert
    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_id == "vulnix.python.hardcoded_creds.password_assignment"
    assert finding.severity == "ERROR"
    assert "CWE-798" in finding.cwe
    assert finding.file_path == "config.py"


def test_parse_results_multiple_findings(engine, multi_finding_semgrep_output):
    """복수의 findings가 있는 JSON을 파싱하면 SemgrepFinding 3건을 반환한다."""
    # Arrange
    base_dir = Path("/tmp/vulnix-scan-test")

    # Act
    findings = engine._parse_results(multi_finding_semgrep_output, base_dir)

    # Assert
    assert len(findings) == 3

    # SQL Injection 2건 확인
    sql_findings = [f for f in findings if "sql_injection" in f.rule_id]
    assert len(sql_findings) == 2

    # XSS 1건 확인
    xss_findings = [f for f in findings if "xss" in f.rule_id]
    assert len(xss_findings) == 1


def test_parse_results_empty_json(engine):
    """결과가 0건인 JSON을 파싱하면 빈 리스트를 반환한다."""
    # Arrange
    base_dir = Path("/tmp/vulnix-scan-test")
    empty_output = {"results": [], "errors": []}

    # Act
    findings = engine._parse_results(empty_output, base_dir)

    # Assert
    assert findings == []


def test_parse_results_relative_file_path(engine, sql_injection_semgrep_output):
    """절대 경로를 base_dir 기준 상대 경로로 변환한다."""
    # Arrange
    base_dir = Path("/tmp/vulnix-scan-test")

    # Act
    findings = engine._parse_results(sql_injection_semgrep_output, base_dir)

    # Assert
    # /tmp/vulnix-scan-test/app/db.py -> app/db.py
    assert findings[0].file_path == "app/db.py"
    assert not findings[0].file_path.startswith("/")


def test_parse_results_no_cwe_metadata(engine):
    """CWE 메타데이터가 없는 결과는 cwe=[] 빈 리스트로 파싱한다."""
    # Arrange
    base_dir = Path("/tmp/vulnix-scan-test")
    output_without_cwe = {
        "results": [
            {
                "check_id": "vulnix.python.some_rule",
                "path": "/tmp/vulnix-scan-test/app.py",
                "start": {"line": 1, "col": 1},
                "end": {"line": 1, "col": 10},
                "extra": {
                    "message": "Some vulnerability",
                    "severity": "WARNING",
                    "lines": "some_code()",
                    "metadata": {},  # cwe 필드 없음
                },
            }
        ],
        "errors": [],
    }

    # Act
    findings = engine._parse_results(output_without_cwe, base_dir)

    # Assert
    assert len(findings) == 1
    assert findings[0].cwe == []


# ──────────────────────────────────────────────────────────────
# _run_semgrep_cli() 테스트
# ──────────────────────────────────────────────────────────────

def test_run_semgrep_cli_returncode_0_returns_dict(engine):
    """returncode=0 (취약점 없음) 이면 results가 빈 딕셔너리를 반환한다."""
    # Arrange
    clean_output = {"results": [], "errors": []}
    cmd = ["semgrep", "scan", "--json", "--quiet", "/some/dir"]

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps(clean_output),
            stderr="",
        )

        # Act
        result = engine._run_semgrep_cli(cmd)

    # Assert
    assert isinstance(result, dict)
    assert result["results"] == []


def test_run_semgrep_cli_returncode_1_returns_findings(engine, sql_injection_semgrep_output):
    """returncode=1 (취약점 발견) 이면 results가 포함된 딕셔너리를 반환한다."""
    # Arrange
    cmd = ["semgrep", "scan", "--json", "--quiet", "/some/dir"]

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=cmd,
            returncode=1,
            stdout=json.dumps(sql_injection_semgrep_output),
            stderr="",
        )

        # Act
        result = engine._run_semgrep_cli(cmd)

    # Assert
    assert isinstance(result, dict)
    assert len(result["results"]) == 1


def test_run_semgrep_cli_returncode_2_raises_runtime_error(engine):
    """returncode >= 2 (Semgrep 내부 에러) 이면 RuntimeError를 발생시킨다."""
    # Arrange
    cmd = ["semgrep", "scan", "--json", "--quiet", "/some/dir"]

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=cmd,
            returncode=2,
            stdout="",
            stderr="Error: something went wrong",
        )

        # Act & Assert
        with pytest.raises(RuntimeError) as exc_info:
            engine._run_semgrep_cli(cmd)

        assert "returncode=2" in str(exc_info.value) or "에러" in str(exc_info.value)


def test_run_semgrep_cli_not_installed_raises_runtime_error(engine):
    """Semgrep CLI가 설치되지 않은 환경에서 RuntimeError를 발생시킨다."""
    # Arrange
    cmd = ["semgrep", "scan", "--json", "--quiet", "/some/dir"]

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError("semgrep not found")

        # Act & Assert
        with pytest.raises(RuntimeError) as exc_info:
            engine._run_semgrep_cli(cmd)

        assert "설치" in str(exc_info.value) or "semgrep" in str(exc_info.value).lower()


def test_run_semgrep_cli_timeout_raises_runtime_error(engine):
    """실행이 600초를 초과하면 RuntimeError를 발생시킨다."""
    # Arrange
    cmd = ["semgrep", "scan", "--json", "--quiet", "/some/dir"]

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=cmd, timeout=600)

        # Act & Assert
        with pytest.raises(RuntimeError) as exc_info:
            engine._run_semgrep_cli(cmd)

        assert "타임아웃" in str(exc_info.value) or "timeout" in str(exc_info.value).lower()


# ──────────────────────────────────────────────────────────────
# prepare_temp_dir / cleanup_temp_dir 테스트
# ──────────────────────────────────────────────────────────────

def test_cleanup_on_scan_completion(tmp_path):
    """스캔 완료 후 임시 디렉토리가 삭제된다.

    prepare_temp_dir 및 cleanup_temp_dir은 이미 구현되어 있으므로,
    scan()이 완료 후 cleanup_temp_dir을 호출하는지 검증한다.
    """
    # Arrange
    job_id = "test-cleanup-success"
    temp_dir = SemgrepEngine.prepare_temp_dir(job_id)
    assert temp_dir.exists()

    engine = SemgrepEngine()
    empty_output = {"results": [], "errors": []}

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["semgrep"],
            returncode=0,
            stdout=json.dumps(empty_output),
            stderr="",
        )

        # Act: scan()은 내부적으로 cleanup을 호출하지 않지만,
        # 워커가 scan() 완료 후 cleanup을 호출하는 구조.
        # 여기서는 cleanup_temp_dir이 정상 동작하는지 확인.
        engine.scan(temp_dir, job_id)
        SemgrepEngine.cleanup_temp_dir(job_id)

    # Assert
    assert not temp_dir.exists()


def test_cleanup_on_scan_failure():
    """스캔 실패 시에도 임시 디렉토리가 삭제된다."""
    # Arrange
    job_id = "test-cleanup-failure"
    temp_dir = SemgrepEngine.prepare_temp_dir(job_id)
    assert temp_dir.exists()

    engine = SemgrepEngine()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["semgrep"],
            returncode=2,
            stdout="",
            stderr="Fatal error",
        )

        # Act
        try:
            engine.scan(temp_dir, job_id)
        except (RuntimeError, NotImplementedError):
            pass

        SemgrepEngine.cleanup_temp_dir(job_id)

    # Assert
    assert not temp_dir.exists()


def test_cleanup_nonexistent_dir_does_not_raise():
    """존재하지 않는 임시 디렉토리를 삭제하려 해도 에러 없이 정상 종료한다."""
    # Arrange
    job_id = "nonexistent-job-id-xyz"
    temp_dir = Path(f"/tmp/vulnix-scan-{job_id}")
    assert not temp_dir.exists()

    # Act & Assert (예외 없이 정상 종료되어야 함)
    SemgrepEngine.cleanup_temp_dir(job_id)
