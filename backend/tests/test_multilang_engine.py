"""F-05 다국어 탐지 엔진 확장 — RED 단계 테스트

구현 전에 실행하면 모든 테스트가 FAIL이어야 한다.
(ImportError, AttributeError, AssertionError 모두 FAIL로 간주)

대상 범위:
- VulnerabilityMapper 신규 다국어 rule_id 매핑
- detect_language_from_rule_id() 헬퍼 함수 (신규)
- LLMAgent._detect_language_from_path() 헬퍼 함수 (신규)
- LLMAgent._build_analysis_prompt() 다국어 언어명 주입
- Semgrep 룰 디렉토리 존재 여부 (javascript, java, go)
- JavaScript SQL Injection 룰 파일 YAML 형식 유효성
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 테스트 모듈 임포트 전 환경변수 설정 (Settings 로드 오류 방지)
_TEST_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test_vulnix",
    "REDIS_URL": "redis://localhost:6379",
    "GITHUB_APP_ID": "123456",
    "GITHUB_APP_PRIVATE_KEY": (
        "-----BEGIN RSA PRIVATE KEY-----\ntest_key\n-----END RSA PRIVATE KEY-----"
    ),
    "GITHUB_WEBHOOK_SECRET": "test_webhook_secret_for_hmac",
    "GITHUB_CLIENT_ID": "test_client_id",
    "GITHUB_CLIENT_SECRET": "test_client_secret",
    "ANTHROPIC_API_KEY": "test_anthropic_key",
    "JWT_SECRET_KEY": "test_jwt_secret_key_for_testing",
}
for _key, _val in _TEST_ENV.items():
    os.environ.setdefault(_key, _val)


# ──────────────────────────────────────────────────────────────
# 공통 임포트 (모듈 레벨에서 수행하여 ImportError도 FAIL로 노출)
# ──────────────────────────────────────────────────────────────

from src.services.vulnerability_mapper import map_finding_to_vulnerability  # noqa: E402
from src.services.semgrep_engine import SemgrepFinding  # noqa: E402


# ──────────────────────────────────────────────────────────────
# 픽스처
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def agent():
    """LLMAgent 인스턴스 픽스처.

    anthropic.AsyncAnthropic 생성을 Mock하여 외부 네트워크 연결 없이 테스트한다.
    """
    from src.services.llm_agent import LLMAgent

    with patch("anthropic.AsyncAnthropic") as mock_async_cls:
        mock_async_cls.return_value = MagicMock()
        a = LLMAgent()

    mock_async_client = MagicMock()
    a._client = mock_async_client
    return a


@pytest.fixture
def js_sql_finding():
    """JavaScript SQL Injection SemgrepFinding 픽스처."""
    return SemgrepFinding(
        rule_id="vulnix.javascript.injection.sql_string_concat",
        severity="ERROR",
        file_path="src/routes/user.js",
        start_line=3,
        end_line=3,
        code_snippet='db.query("SELECT * FROM users WHERE id=" + userId)',
        message="SQL Injection: 문자열 연결로 쿼리 조합",
        cwe=["CWE-89"],
    )


@pytest.fixture
def java_xss_finding():
    """Java XSS SemgrepFinding 픽스처."""
    return SemgrepFinding(
        rule_id="vulnix.java.xss.servlet_print_unsanitized",
        severity="ERROR",
        file_path="src/UserServlet.java",
        start_line=20,
        end_line=20,
        code_snippet='response.getWriter().print(request.getParameter("name"))',
        message="XSS: 미이스케이프 출력",
        cwe=["CWE-79"],
    )


@pytest.fixture
def go_command_injection_finding():
    """Go Command Injection SemgrepFinding 픽스처."""
    return SemgrepFinding(
        rule_id="vulnix.go.injection.command_exec",
        severity="ERROR",
        file_path="internal/runner/exec.go",
        start_line=15,
        end_line=15,
        code_snippet='exec.Command("bash", "-c", userInput)',
        message="Command Injection: 쉘 명령에 사용자 입력 포함",
        cwe=["CWE-78"],
    )


# ──────────────────────────────────────────────────────────────
# 1. VulnerabilityMapper 신규 rule_id 매핑 테스트
# ──────────────────────────────────────────────────────────────

class TestVulnerabilityMapperNewRules:
    """F-05 신규 다국어 rule_id 매핑 테스트."""

    def test_js_sql_injection_rule_mapping(self):
        """vulnix.javascript.injection.sql_string_concat 룰이 올바르게 매핑된다."""
        # Arrange
        rule_id = "vulnix.javascript.injection.sql_string_concat"
        semgrep_severity = "ERROR"

        # Act
        mapping = map_finding_to_vulnerability(rule_id, semgrep_severity)

        # Assert
        assert mapping["vulnerability_type"] == "sql_injection"
        assert mapping["cwe_id"] == "CWE-89"

    def test_js_sql_injection_owasp_category(self):
        """vulnix.javascript.injection.sql_string_concat 룰의 OWASP 카테고리가 A03이다."""
        mapping = map_finding_to_vulnerability(
            "vulnix.javascript.injection.sql_string_concat", "ERROR"
        )
        assert mapping["owasp_category"] is not None
        assert "A03" in mapping["owasp_category"]

    def test_java_xss_rule_mapping(self):
        """vulnix.java.xss.servlet_print_unsanitized 룰이 올바르게 매핑된다."""
        # Arrange
        rule_id = "vulnix.java.xss.servlet_print_unsanitized"
        semgrep_severity = "ERROR"

        # Act
        mapping = map_finding_to_vulnerability(rule_id, semgrep_severity)

        # Assert
        assert mapping["vulnerability_type"] == "xss"
        assert mapping["cwe_id"] == "CWE-79"

    def test_go_hardcoded_creds_rule_mapping(self):
        """vulnix.go.crypto.hardcoded_key 룰이 올바르게 매핑된다."""
        # Arrange
        rule_id = "vulnix.go.crypto.hardcoded_key"
        semgrep_severity = "ERROR"

        # Act
        mapping = map_finding_to_vulnerability(rule_id, semgrep_severity)

        # Assert
        assert mapping["vulnerability_type"] == "hardcoded_credentials"
        assert mapping["cwe_id"] == "CWE-798"

    def test_ts_insecure_jwt_rule_mapping(self):
        """vulnix.javascript.auth.jwt_no_verify 룰이 올바르게 매핑된다."""
        # Arrange
        rule_id = "vulnix.javascript.auth.jwt_no_verify"
        semgrep_severity = "ERROR"

        # Act
        mapping = map_finding_to_vulnerability(rule_id, semgrep_severity)

        # Assert
        assert mapping["vulnerability_type"] == "insecure_jwt"
        assert mapping["cwe_id"] == "CWE-347"

    def test_java_weak_crypto_rule_mapping(self):
        """vulnix.java.crypto.weak_hash 룰이 올바르게 매핑된다."""
        # Arrange
        rule_id = "vulnix.java.crypto.weak_hash"
        semgrep_severity = "WARNING"

        # Act
        mapping = map_finding_to_vulnerability(rule_id, semgrep_severity)

        # Assert
        assert mapping["vulnerability_type"] == "weak_crypto"
        assert mapping["cwe_id"] == "CWE-328"
        assert mapping["severity"] == "medium"

    def test_go_command_injection_rule_mapping(self):
        """vulnix.go.injection.command_exec 룰이 올바르게 매핑된다."""
        # Arrange
        rule_id = "vulnix.go.injection.command_exec"
        semgrep_severity = "ERROR"

        # Act
        mapping = map_finding_to_vulnerability(rule_id, semgrep_severity)

        # Assert
        assert mapping["vulnerability_type"] == "command_injection"
        assert mapping["cwe_id"] == "CWE-78"

    def test_java_insecure_random_rule_mapping(self):
        """vulnix.java.crypto.insecure_random 룰이 올바르게 매핑된다."""
        mapping = map_finding_to_vulnerability("vulnix.java.crypto.insecure_random", "WARNING")
        assert mapping["vulnerability_type"] == "insecure_random"
        assert mapping["cwe_id"] == "CWE-330"

    def test_go_weak_hash_rule_mapping(self):
        """vulnix.go.crypto.weak_hash_md5 룰이 올바르게 매핑된다."""
        mapping = map_finding_to_vulnerability("vulnix.go.crypto.weak_hash_md5", "WARNING")
        assert mapping["vulnerability_type"] == "weak_crypto"
        assert mapping["cwe_id"] == "CWE-328"

    def test_js_cors_wildcard_rule_mapping(self):
        """vulnix.javascript.misconfig.cors_wildcard 룰이 올바르게 매핑된다."""
        mapping = map_finding_to_vulnerability("vulnix.javascript.misconfig.cors_wildcard", "WARNING")
        assert mapping["vulnerability_type"] == "security_misconfiguration"
        assert mapping["cwe_id"] == "CWE-942"

    def test_unknown_rule_id_returns_unknown(self):
        """미등록 rule_id는 unknown 타입을 반환한다."""
        # Arrange / Act
        mapping = map_finding_to_vulnerability("unknown.rule.xyz", "WARNING")

        # Assert — 기존 동작: unknown 반환 (회귀 방지)
        assert mapping["vulnerability_type"] == "unknown"
        assert mapping["cwe_id"] is None
        assert mapping["owasp_category"] is None


# ──────────────────────────────────────────────────────────────
# 2. detect_language_from_rule_id() 헬퍼 함수 테스트
# ──────────────────────────────────────────────────────────────

class TestDetectLanguageFromRuleId:
    """detect_language_from_rule_id() 신규 헬퍼 함수 테스트."""

    def test_detect_language_from_js_rule_id(self):
        """JS rule_id에서 언어 감지가 가능하다."""
        # Arrange
        from src.services.vulnerability_mapper import detect_language_from_rule_id

        # Act / Assert
        assert detect_language_from_rule_id("vulnix.javascript.sql_injection") == "javascript"

    def test_detect_language_from_java_rule_id(self):
        """Java rule_id에서 언어 감지가 가능하다."""
        from src.services.vulnerability_mapper import detect_language_from_rule_id

        assert detect_language_from_rule_id("vulnix.java.xss") == "java"

    def test_detect_language_from_go_rule_id(self):
        """Go rule_id에서 언어 감지가 가능하다."""
        from src.services.vulnerability_mapper import detect_language_from_rule_id

        assert detect_language_from_rule_id("vulnix.go.hardcoded_credentials") == "go"

    def test_detect_language_from_python_rule_id(self):
        """Python rule_id에서 언어 감지가 가능하다 (기존 동작 회귀 방지)."""
        from src.services.vulnerability_mapper import detect_language_from_rule_id

        assert detect_language_from_rule_id("vulnix.python.xss.flask_render_html") == "python"

    def test_detect_language_unknown_returns_unknown(self):
        """미인식 rule_id는 'unknown'을 반환한다."""
        from src.services.vulnerability_mapper import detect_language_from_rule_id

        assert detect_language_from_rule_id("unknown.rule") == "unknown"

    def test_detect_language_non_vulnix_prefix_returns_unknown(self):
        """vulnix 접두사가 없는 rule_id는 'unknown'을 반환한다."""
        from src.services.vulnerability_mapper import detect_language_from_rule_id

        assert detect_language_from_rule_id("p/default") == "unknown"

    def test_detect_language_empty_string_returns_unknown(self):
        """빈 문자열 rule_id는 'unknown'을 반환한다."""
        from src.services.vulnerability_mapper import detect_language_from_rule_id

        assert detect_language_from_rule_id("") == "unknown"

    def test_detect_language_dots_less_than_three_returns_unknown(self):
        """점(.)이 2개 미만인 rule_id는 'unknown'을 반환한다."""
        from src.services.vulnerability_mapper import detect_language_from_rule_id

        # 점이 1개 (세그먼트 2개)
        assert detect_language_from_rule_id("vulnix.python") == "unknown"


# ──────────────────────────────────────────────────────────────
# 3. LLMAgent 다국어 프롬프트 테스트
# ──────────────────────────────────────────────────────────────

class TestLLMAgentDetectLanguageFromPath:
    """LLMAgent._detect_language_from_path() 신규 헬퍼 함수 테스트."""

    def test_detect_python_file(self, agent):
        """Python 파일 경로에서 'Python'을 반환한다."""
        result = agent._detect_language_from_path("app/main.py")
        assert result == "Python"

    def test_detect_javascript_file(self, agent):
        """JavaScript 파일 경로에서 'JavaScript'를 반환한다."""
        result = agent._detect_language_from_path("src/index.js")
        assert result == "JavaScript"

    def test_detect_typescript_file(self, agent):
        """TypeScript 파일 경로에서 'TypeScript'를 반환한다."""
        result = agent._detect_language_from_path("src/app.ts")
        assert result == "TypeScript"

    def test_detect_tsx_file(self, agent):
        """TSX React 파일 경로에서 'TypeScript (React)'를 반환한다."""
        result = agent._detect_language_from_path("src/Component.tsx")
        assert result == "TypeScript (React)"

    def test_detect_jsx_file(self, agent):
        """JSX React 파일 경로에서 'JavaScript (React)'를 반환한다."""
        result = agent._detect_language_from_path("src/App.jsx")
        assert result == "JavaScript (React)"

    def test_detect_java_file(self, agent):
        """Java 파일 경로에서 'Java'를 반환한다."""
        result = agent._detect_language_from_path("src/Main.java")
        assert result == "Java"

    def test_detect_go_file(self, agent):
        """Go 파일 경로에서 'Go'를 반환한다."""
        result = agent._detect_language_from_path("main.go")
        assert result == "Go"

    def test_detect_unknown_extension_returns_source(self, agent):
        """미인식 확장자는 '소스'를 반환한다."""
        result = agent._detect_language_from_path("config.toml")
        assert result == "소스"

    def test_detect_no_extension_returns_source(self, agent):
        """확장자 없는 파일(Makefile)은 '소스'를 반환한다."""
        result = agent._detect_language_from_path("Makefile")
        assert result == "소스"


class TestLLMAgentMultilangPrompt:
    """LLMAgent._build_analysis_prompt() 다국어 언어명 주입 테스트."""

    def test_llm_agent_prompt_contains_javascript_language(self, agent, js_sql_finding):
        """JavaScript 파일 분석 시 프롬프트에 '다음 JavaScript 코드에서' 구문이 포함된다.

        현재 구현은 'Python'이 하드코딩되어 있으므로 이 테스트는 FAIL이어야 한다.
        """
        # Arrange
        file_content = "const x = req.query.id;\ndb.query(x);"
        file_path = "src/routes/user.js"
        findings = [js_sql_finding]

        # Act
        prompt = agent._build_analysis_prompt(file_content, file_path, findings)

        # Assert — rule_id에 'javascript'가 소문자로 있어도 통과하지 않도록
        # '다음 JavaScript 코드에서' 정확한 한국어 구문을 확인한다
        assert "다음 JavaScript 코드에서" in prompt

    def test_llm_agent_prompt_contains_java_language(self, agent, java_xss_finding):
        """Java 파일 분석 시 프롬프트에 '다음 Java 코드에서' 구문이 포함된다.

        현재 구현은 'Python'이 하드코딩되어 있으므로 이 테스트는 FAIL이어야 한다.
        """
        # Arrange
        file_content = 'String query = "SELECT * FROM users WHERE id=" + id;'
        file_path = "src/UserService.java"
        findings = [java_xss_finding]

        # Act
        prompt = agent._build_analysis_prompt(file_content, file_path, findings)

        # Assert — '다음 Java 코드에서' 정확한 한국어 구문을 확인한다
        assert "다음 Java 코드에서" in prompt

    def test_llm_agent_prompt_contains_go_language(self, agent, go_command_injection_finding):
        """Go 파일 분석 시 프롬프트에 'Go'가 포함된다."""
        # Arrange
        file_content = 'password := "hardcoded_secret"'
        file_path = "internal/auth/auth.go"
        findings = [go_command_injection_finding]

        # Act
        prompt = agent._build_analysis_prompt(file_content, file_path, findings)

        # Assert — 정확히 "Go"가 포함되어야 함 (대소문자 구분)
        assert "Go" in prompt

    def test_llm_agent_prompt_python_unchanged(self, agent):
        """Python 파일은 여전히 'Python'이 프롬프트에 포함된다 (하위 호환)."""
        # Arrange
        from src.services.semgrep_engine import SemgrepFinding

        finding = SemgrepFinding(
            rule_id="vulnix.python.sql_injection.string_format",
            severity="ERROR",
            file_path="app/views.py",
            start_line=5,
            end_line=5,
            code_snippet='query = f"SELECT * FROM users WHERE id={user_id}"',
            message="SQL Injection 탐지",
            cwe=["CWE-89"],
        )
        file_content = 'query = f"SELECT * FROM users WHERE id={user_id}"'
        file_path = "app/views.py"
        findings = [finding]

        # Act
        prompt = agent._build_analysis_prompt(file_content, file_path, findings)

        # Assert
        assert "Python" in prompt

    def test_llm_agent_prompt_js_contains_korean_prefix(self, agent, js_sql_finding):
        """JavaScript 파일 프롬프트에 '다음 JavaScript 코드에서' 구문이 포함된다."""
        # Arrange
        file_content = "const x = req.query.id;\ndb.query(x);"
        file_path = "src/routes/user.js"
        findings = [js_sql_finding]

        # Act
        prompt = agent._build_analysis_prompt(file_content, file_path, findings)

        # Assert
        assert "다음 JavaScript 코드에서" in prompt

    def test_llm_agent_prompt_java_contains_korean_prefix(self, agent, java_xss_finding):
        """Java 파일 프롬프트에 '다음 Java 코드에서' 구문이 포함된다."""
        # Arrange
        file_content = 'response.getWriter().print(request.getParameter("name"));'
        file_path = "src/Main.java"
        findings = [java_xss_finding]

        # Act
        prompt = agent._build_analysis_prompt(file_content, file_path, findings)

        # Assert
        assert "다음 Java 코드에서" in prompt

    def test_llm_agent_prompt_go_contains_korean_prefix(self, agent, go_command_injection_finding):
        """Go 파일 프롬프트에 '다음 Go 코드에서' 구문이 포함된다."""
        # Arrange
        file_content = 'exec.Command("bash", "-c", userInput)'
        file_path = "main.go"
        findings = [go_command_injection_finding]

        # Act
        prompt = agent._build_analysis_prompt(file_content, file_path, findings)

        # Assert
        assert "다음 Go 코드에서" in prompt

    def test_llm_agent_prompt_typescript_contains_language(self, agent):
        """TypeScript 파일 프롬프트에 'TypeScript'가 포함된다."""
        # Arrange
        from src.services.semgrep_engine import SemgrepFinding

        finding = SemgrepFinding(
            rule_id="vulnix.javascript.injection.sql_string_concat",
            severity="ERROR",
            file_path="src/routes/user.ts",
            start_line=10,
            end_line=10,
            code_snippet="db.query(`SELECT * FROM users WHERE id=${userId}`)",
            message="SQL Injection: 템플릿 리터럴 쿼리 조합",
            cwe=["CWE-89"],
        )
        file_content = "const userId = req.params.id;\ndb.query(`SELECT * FROM users WHERE id=${userId}`);"
        file_path = "src/routes/user.ts"
        findings = [finding]

        # Act
        prompt = agent._build_analysis_prompt(file_content, file_path, findings)

        # Assert
        assert "TypeScript" in prompt


# ──────────────────────────────────────────────────────────────
# 4. Semgrep 룰 파일 존재 여부 테스트
# ──────────────────────────────────────────────────────────────

class TestSemgrepRulesDirectoryExists:
    """Semgrep 룰 디렉토리 및 파일 존재 테스트.

    테스트는 backend/ 디렉토리에서 실행됨을 가정한다.
    (pytest.ini 또는 pyproject.toml의 testpaths 기준)
    """

    def test_javascript_rules_directory_exists(self):
        """backend/src/rules/javascript/ 디렉토리가 존재한다."""
        rules_dir = Path("src/rules/javascript")
        assert rules_dir.exists(), "rules/javascript/ 디렉토리가 없음"
        assert any(rules_dir.glob("*.yml")), "rules/javascript/*.yml 파일이 없음"

    def test_java_rules_directory_exists(self):
        """backend/src/rules/java/ 디렉토리가 존재한다."""
        rules_dir = Path("src/rules/java")
        assert rules_dir.exists(), "rules/java/ 디렉토리가 없음"
        assert any(rules_dir.glob("*.yml")), "rules/java/*.yml 파일이 없음"

    def test_go_rules_directory_exists(self):
        """backend/src/rules/go/ 디렉토리가 존재한다."""
        rules_dir = Path("src/rules/go")
        assert rules_dir.exists(), "rules/go/ 디렉토리가 없음"
        assert any(rules_dir.glob("*.yml")), "rules/go/*.yml 파일이 없음"

    def test_python_rules_directory_still_exists(self):
        """기존 backend/src/rules/python/ 디렉토리가 여전히 존재한다 (회귀 방지)."""
        rules_dir = Path("src/rules/python")
        assert rules_dir.exists(), "rules/python/ 디렉토리가 사라짐 — 회귀 발생"
        assert any(rules_dir.glob("*.yml")), "rules/python/*.yml 파일이 없음"

    def test_js_sql_injection_rule_file_exists(self):
        """rules/javascript/sql_injection.yml 파일이 존재한다."""
        rule_file = Path("src/rules/javascript/sql_injection.yml")
        assert rule_file.exists(), "rules/javascript/sql_injection.yml 파일이 없음"

    def test_js_xss_rule_file_exists(self):
        """rules/javascript/xss.yml 파일이 존재한다."""
        rule_file = Path("src/rules/javascript/xss.yml")
        assert rule_file.exists(), "rules/javascript/xss.yml 파일이 없음"

    def test_java_sql_injection_rule_file_exists(self):
        """rules/java/sql_injection.yml 파일이 존재한다."""
        rule_file = Path("src/rules/java/sql_injection.yml")
        assert rule_file.exists(), "rules/java/sql_injection.yml 파일이 없음"

    def test_go_sql_injection_rule_file_exists(self):
        """rules/go/sql_injection.yml 파일이 존재한다."""
        rule_file = Path("src/rules/go/sql_injection.yml")
        assert rule_file.exists(), "rules/go/sql_injection.yml 파일이 없음"

    def test_js_sql_injection_rule_file_valid_semgrep_yaml(self):
        """rules/javascript/sql_injection.yml이 유효한 Semgrep 룰 YAML 형식이다."""
        import yaml

        rule_file = Path("src/rules/javascript/sql_injection.yml")
        assert rule_file.exists(), "sql_injection.yml 파일이 없음"

        content = yaml.safe_load(rule_file.read_text())

        # Semgrep 룰 형식 검증
        assert "rules" in content, "YAML에 'rules' 키가 없음"
        assert len(content["rules"]) > 0, "rules 배열이 비어 있음"

        first_rule = content["rules"][0]
        assert "id" in first_rule, "룰에 'id' 필드가 없음"

        # pattern, patterns, pattern-either 중 하나 이상 존재해야 함
        has_pattern = (
            "pattern" in first_rule
            or "patterns" in first_rule
            or "pattern-either" in first_rule
        )
        assert has_pattern, "룰에 pattern/patterns/pattern-either 필드가 없음"

    def test_java_sql_injection_rule_file_valid_semgrep_yaml(self):
        """rules/java/sql_injection.yml이 유효한 Semgrep 룰 YAML 형식이다."""
        import yaml

        rule_file = Path("src/rules/java/sql_injection.yml")
        assert rule_file.exists(), "java/sql_injection.yml 파일이 없음"

        content = yaml.safe_load(rule_file.read_text())
        assert "rules" in content
        assert len(content["rules"]) > 0

        first_rule = content["rules"][0]
        assert "id" in first_rule
        has_pattern = (
            "pattern" in first_rule
            or "patterns" in first_rule
            or "pattern-either" in first_rule
        )
        assert has_pattern

    def test_go_sql_injection_rule_file_valid_semgrep_yaml(self):
        """rules/go/sql_injection.yml이 유효한 Semgrep 룰 YAML 형식이다."""
        import yaml

        rule_file = Path("src/rules/go/sql_injection.yml")
        assert rule_file.exists(), "go/sql_injection.yml 파일이 없음"

        content = yaml.safe_load(rule_file.read_text())
        assert "rules" in content
        assert len(content["rules"]) > 0

        first_rule = content["rules"][0]
        assert "id" in first_rule
        has_pattern = (
            "pattern" in first_rule
            or "patterns" in first_rule
            or "pattern-either" in first_rule
        )
        assert has_pattern

    def test_js_rule_has_correct_languages_field(self):
        """rules/javascript/sql_injection.yml의 룰에 languages: [javascript, typescript]가 포함된다."""
        import yaml

        rule_file = Path("src/rules/javascript/sql_injection.yml")
        assert rule_file.exists()

        content = yaml.safe_load(rule_file.read_text())
        first_rule = content["rules"][0]

        assert "languages" in first_rule, "룰에 'languages' 필드가 없음"
        languages = first_rule["languages"]
        assert "javascript" in languages or "typescript" in languages, (
            f"languages에 javascript/typescript가 없음: {languages}"
        )

    def test_java_rule_has_java_language_field(self):
        """rules/java/sql_injection.yml의 룰에 languages: [java]가 포함된다."""
        import yaml

        rule_file = Path("src/rules/java/sql_injection.yml")
        assert rule_file.exists()

        content = yaml.safe_load(rule_file.read_text())
        first_rule = content["rules"][0]

        assert "languages" in first_rule
        assert "java" in first_rule["languages"]

    def test_go_rule_has_go_language_field(self):
        """rules/go/sql_injection.yml의 룰에 languages: [go]가 포함된다."""
        import yaml

        rule_file = Path("src/rules/go/sql_injection.yml")
        assert rule_file.exists()

        content = yaml.safe_load(rule_file.read_text())
        first_rule = content["rules"][0]

        assert "languages" in first_rule
        assert "go" in first_rule["languages"]


# ──────────────────────────────────────────────────────────────
# 5. 경계 조건 / 에러 케이스 테스트
# ──────────────────────────────────────────────────────────────

class TestEdgeCases:
    """경계 조건 및 에러 케이스 테스트."""

    def test_empty_rule_id_returns_unknown(self):
        """빈 문자열 rule_id는 vulnerability_type='unknown'을 반환한다."""
        mapping = map_finding_to_vulnerability("", "WARNING")
        assert mapping["vulnerability_type"] == "unknown"
        assert mapping["cwe_id"] is None

    def test_map_finding_returns_severity_medium_for_warning(self):
        """semgrep_severity 'WARNING'은 severity='medium'으로 매핑된다."""
        mapping = map_finding_to_vulnerability("vulnix.java.crypto.weak_hash", "WARNING")
        assert mapping["severity"] == "medium"

    def test_map_finding_returns_severity_high_for_error(self):
        """semgrep_severity 'ERROR'는 severity='high'로 매핑된다."""
        mapping = map_finding_to_vulnerability("vulnix.javascript.injection.sql_string_concat", "ERROR")
        assert mapping["severity"] == "high"

    def test_detect_language_from_path_unknown_extension(self, agent):
        """미인식 확장자(.rb)는 '소스'를 반환한다."""
        result = agent._detect_language_from_path("app/controller.rb")
        assert result == "소스"

    def test_detect_language_from_path_php_extension(self, agent):
        """미인식 확장자(.php)는 '소스'를 반환한다."""
        result = agent._detect_language_from_path("app/index.php")
        assert result == "소스"

    def test_js_rule_mapping_with_full_hierarchy_rule_id(self):
        """계층적 rule_id (vulnix.javascript.injection.command_exec)도 올바르게 매핑된다."""
        mapping = map_finding_to_vulnerability(
            "vulnix.javascript.injection.command_exec", "ERROR"
        )
        assert mapping["vulnerability_type"] == "command_injection"
        assert mapping["cwe_id"] == "CWE-78"
