"""F-11 IDE 플러그인 — IDE API 엔드포인트 통합 테스트 (RED 단계)

테스트 대상 엔드포인트:
  - POST /api/v1/ide/analyze          코드 스니펫 Semgrep 분석
  - GET  /api/v1/ide/false-positive-patterns  팀 오탐 패턴 목록
  - POST /api/v1/ide/patch-suggestion  LLM 기반 패치 diff 생성

인증 방식: X-Api-Key 헤더 (JWT 아님)
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ──────────────────────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────────────────────

TEAM_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
API_KEY_ID = uuid.UUID("aaaa1111-aaaa-aaaa-aaaa-aaaa11111111")
API_KEY_VALUE = "vx_live_a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
DISABLED_API_KEY_VALUE = "vx_live_deadbeefdeadbeefdeadbeefdeadbeef"
NONE_API_KEY_VALUE = "vx_live_nonexistentkeythatdoesnotexist"

# 취약한 Python 코드 (SQL Injection)
SQL_INJECTION_CODE = '''
import sqlite3

def get_user(user_id):
    conn = sqlite3.connect("db.sqlite")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    return cursor.fetchone()
'''

# 안전한 Python 코드
SAFE_CODE = '''
import sqlite3

def get_user(user_id):
    conn = sqlite3.connect("db.sqlite")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cursor.fetchone()
'''

# JavaScript 취약 코드 (eval injection)
EVAL_INJECTION_CODE = '''
function runUserCode(userInput) {
    eval(userInput);
}
'''

# 패치 제안 요청용 finding 객체
SAMPLE_FINDING = {
    "rule_id": "python.sqlalchemy.security.sql-injection",
    "start_line": 6,
    "end_line": 6,
    "code_snippet": 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
    "message": "사용자 입력이 SQL 쿼리에 직접 삽입됩니다.",
}


# ──────────────────────────────────────────────────────────────
# 픽스처 헬퍼
# ──────────────────────────────────────────────────────────────

def _make_mock_api_key(
    key_id: uuid.UUID = API_KEY_ID,
    team_id: uuid.UUID = TEAM_ID,
    is_active: bool = True,
    expired: bool = False,
) -> MagicMock:
    """ApiKey Mock 생성 헬퍼"""
    api_key = MagicMock()
    api_key.id = key_id
    api_key.team_id = team_id
    api_key.is_active = is_active
    api_key.expires_at = (
        datetime(2020, 1, 1, tzinfo=timezone.utc) if expired else None
    )
    api_key.revoked_at = None
    api_key.created_at = datetime(2026, 2, 25, tzinfo=timezone.utc)
    return api_key


def _make_mock_fp_pattern(
    pattern_id: uuid.UUID | None = None,
    semgrep_rule_id: str = "python.flask.security.xss",
    file_pattern: str = "tests/**",
) -> MagicMock:
    """FalsePositivePattern Mock 생성 헬퍼"""
    pattern = MagicMock()
    pattern.id = pattern_id or uuid.uuid4()
    pattern.team_id = TEAM_ID
    pattern.semgrep_rule_id = semgrep_rule_id
    pattern.file_pattern = file_pattern
    pattern.reason = "테스트 코드에서 XSS 탐지 무시"
    pattern.is_active = True
    pattern.updated_at = datetime(2026, 2, 25, 10, 0, 0, tzinfo=timezone.utc)
    return pattern


def _build_ide_mock_db(
    api_key_active: bool = True,
    api_key_expired: bool = False,
    api_key_exists: bool = True,
    fp_patterns: list | None = None,
) -> AsyncMock:
    """IDE API 테스트용 Mock DB 세션 생성.

    Args:
        api_key_active: API Key 활성 여부
        api_key_expired: API Key 만료 여부
        api_key_exists: API Key DB 존재 여부
        fp_patterns: 반환할 FP 패턴 목록
    """
    mock_api_key = _make_mock_api_key(
        is_active=api_key_active,
        expired=api_key_expired,
    ) if api_key_exists else None

    patterns = fp_patterns if fp_patterns is not None else [
        _make_mock_fp_pattern(
            pattern_id=uuid.UUID("bbbb1111-bbbb-bbbb-bbbb-bbbb11111111"),
        ),
        _make_mock_fp_pattern(
            pattern_id=uuid.UUID("bbbb2222-bbbb-bbbb-bbbb-bbbb22222222"),
            semgrep_rule_id="python.security.injection.tainted-sql-string",
            file_pattern="src/tests/**",
        ),
        _make_mock_fp_pattern(
            pattern_id=uuid.UUID("bbbb3333-bbbb-bbbb-bbbb-bbbb33333333"),
            semgrep_rule_id="javascript.browser.security.eval-detected",
            file_pattern="**/*.test.js",
        ),
    ]

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
            result.scalars.return_value.first.return_value = items[0] if items else None
        else:
            result.scalar_one_or_none.return_value = items
            result.scalars.return_value.all.return_value = [items] if items is not None else []
            result.scalars.return_value.first.return_value = items
        return result

    async def smart_execute(query, *args, **kwargs):
        query_str = str(query).lower()

        # api_key 테이블 조회
        if "api_key" in query_str:
            return _make_result(mock_api_key)

        # false_positive 테이블 조회 (FP 패턴)
        if "false_positive" in query_str:
            return _make_result(patterns)

        return _make_result([])

    mock_db.execute = AsyncMock(side_effect=smart_execute)
    return mock_db


@pytest.fixture
def ide_test_client():
    """IDE API 테스트용 TestClient 픽스처.

    유효한 API Key로 인증된 상태를 시뮬레이션한다.
    DB에는 활성 ApiKey와 3개의 FP 패턴이 존재한다.
    """
    from src.main import create_app
    from src.api.deps import get_db

    app = create_app()
    mock_db = _build_ide_mock_db()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def ide_test_client_no_key():
    """API Key 없이 요청하는 경우를 위한 TestClient 픽스처."""
    from src.main import create_app
    from src.api.deps import get_db

    app = create_app()
    mock_db = _build_ide_mock_db(api_key_exists=False)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def ide_test_client_disabled_key():
    """비활성화된 API Key 상태를 시뮬레이션하는 TestClient 픽스처."""
    from src.main import create_app
    from src.api.deps import get_db

    app = create_app()
    mock_db = _build_ide_mock_db(api_key_active=False)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def ide_test_client_expired_key():
    """만료된 API Key 상태를 시뮬레이션하는 TestClient 픽스처."""
    from src.main import create_app
    from src.api.deps import get_db

    app = create_app()
    mock_db = _build_ide_mock_db(api_key_expired=True)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def ide_test_client_no_fp_patterns():
    """FP 패턴이 없는 팀 상태를 시뮬레이션하는 TestClient 픽스처."""
    from src.main import create_app
    from src.api.deps import get_db

    app = create_app()
    mock_db = _build_ide_mock_db(fp_patterns=[])

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


# ──────────────────────────────────────────────────────────────
# POST /api/v1/ide/analyze 테스트
# ──────────────────────────────────────────────────────────────

class TestIdeAnalyze:
    """POST /api/v1/ide/analyze — 코드 스니펫 Semgrep 분석"""

    def test_analyze_sql_injection_returns_findings(self, ide_test_client):
        """SQL Injection 코드 분석 시 findings 배열을 반환한다 (I-01)

        Arrange: 취약한 Python 코드 (SQL Injection)
        Act: POST /api/v1/ide/analyze (유효한 API Key)
        Assert: 200, findings 배열 존재, 취약점 항목 포함
        """
        with patch(
            "src.services.ide_analyzer.IdeAnalyzerService.analyze",
            new_callable=AsyncMock,
        ) as mock_analyze:
            mock_analyze.return_value = {
                "findings": [
                    {
                        "rule_id": "python.sqlalchemy.security.sql-injection",
                        "severity": "high",
                        "message": "사용자 입력이 SQL 쿼리에 직접 삽입됩니다.",
                        "file_path": "src/api/routes/users.py",
                        "start_line": 6,
                        "end_line": 6,
                        "start_col": 4,
                        "end_col": 60,
                        "code_snippet": 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
                        "cwe_id": "CWE-89",
                        "owasp_category": "A03:2021 - Injection",
                        "vulnerability_type": "sql_injection",
                        "is_false_positive_filtered": False,
                    }
                ],
                "analysis_duration_ms": 187,
                "semgrep_version": "1.56.0",
            }

            response = ide_test_client.post(
                "/api/v1/ide/analyze",
                headers={"X-Api-Key": API_KEY_VALUE},
                json={
                    "file_path": "src/api/routes/users.py",
                    "language": "python",
                    "content": SQL_INJECTION_CODE,
                    "context": {
                        "workspace_name": "my-project",
                        "git_branch": "feature/login",
                    },
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "findings" in data["data"]
        assert isinstance(data["data"]["findings"], list)
        assert len(data["data"]["findings"]) >= 1
        finding = data["data"]["findings"][0]
        assert finding["vulnerability_type"] == "sql_injection"
        assert finding["severity"] == "high"

    def test_analyze_empty_code_returns_empty_findings(self, ide_test_client):
        """빈 코드 분석 시 findings 빈 배열을 반환한다 (U-BS-04, I-03)

        Arrange: content=""
        Act: POST /api/v1/ide/analyze
        Assert: 200, findings=[]
        """
        with patch(
            "src.services.ide_analyzer.IdeAnalyzerService.analyze",
            new_callable=AsyncMock,
        ) as mock_analyze:
            mock_analyze.return_value = {
                "findings": [],
                "analysis_duration_ms": 10,
                "semgrep_version": "1.56.0",
            }

            response = ide_test_client.post(
                "/api/v1/ide/analyze",
                headers={"X-Api-Key": API_KEY_VALUE},
                json={
                    "file_path": "src/empty.py",
                    "language": "python",
                    "content": "",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["findings"] == []

    def test_analyze_valid_api_key_authentication(self, ide_test_client):
        """유효한 X-Api-Key 헤더로 인증이 성공한다 (ADR-F11-004)

        Arrange: 유효한 API Key (vx_live_... 형식)
        Act: POST /api/v1/ide/analyze
        Assert: 401이 아닌 응답 (인증 통과)
        """
        with patch(
            "src.services.ide_analyzer.IdeAnalyzerService.analyze",
            new_callable=AsyncMock,
        ) as mock_analyze:
            mock_analyze.return_value = {
                "findings": [],
                "analysis_duration_ms": 50,
                "semgrep_version": "1.56.0",
            }

            response = ide_test_client.post(
                "/api/v1/ide/analyze",
                headers={"X-Api-Key": API_KEY_VALUE},
                json={
                    "file_path": "src/app.py",
                    "language": "python",
                    "content": SAFE_CODE,
                },
            )

        assert response.status_code != 401

    def test_analyze_without_api_key_returns_401(self, ide_test_client_no_key):
        """X-Api-Key 헤더 없이 요청하면 401을 반환한다 (I-06, S-01)

        Arrange: X-Api-Key 헤더 누락
        Act: POST /api/v1/ide/analyze
        Assert: 401, INVALID_API_KEY
        """
        response = ide_test_client_no_key.post(
            "/api/v1/ide/analyze",
            json={
                "file_path": "src/app.py",
                "language": "python",
                "content": SQL_INJECTION_CODE,
            },
        )

        assert response.status_code == 401
        data = response.json()
        assert "INVALID_API_KEY" in str(data).upper() or "error" in data

    def test_analyze_with_invalid_api_key_returns_401(self, ide_test_client_no_key):
        """유효하지 않은 API Key로 요청하면 401을 반환한다 (I-07, S-02)

        Arrange: X-Api-Key: invalid_key (DB에 존재하지 않는 키)
        Act: POST /api/v1/ide/analyze
        Assert: 401
        """
        response = ide_test_client_no_key.post(
            "/api/v1/ide/analyze",
            headers={"X-Api-Key": "invalid_key_that_does_not_exist"},
            json={
                "file_path": "src/app.py",
                "language": "python",
                "content": SQL_INJECTION_CODE,
            },
        )

        assert response.status_code == 401

    def test_analyze_with_jwt_bearer_returns_401(self, ide_test_client_no_key):
        """JWT Bearer 토큰으로 요청하면 401을 반환한다 (S-03)

        IDE 엔드포인트는 X-Api-Key 헤더만 허용하고 JWT를 거부해야 한다.

        Arrange: Authorization: Bearer <jwt>
        Act: POST /api/v1/ide/analyze
        Assert: 401 (X-API-Key 헤더 필수)
        """
        response = ide_test_client_no_key.post(
            "/api/v1/ide/analyze",
            headers={"Authorization": "Bearer fake.jwt.token"},
            json={
                "file_path": "src/app.py",
                "language": "python",
                "content": SQL_INJECTION_CODE,
            },
        )

        assert response.status_code == 401

    def test_analyze_with_disabled_api_key_returns_403(self, ide_test_client_disabled_key):
        """비활성화된 API Key로 요청하면 403을 반환한다 (I-08, S-02)

        Arrange: is_active=False인 API Key
        Act: POST /api/v1/ide/analyze
        Assert: 403, API_KEY_DISABLED
        """
        response = ide_test_client_disabled_key.post(
            "/api/v1/ide/analyze",
            headers={"X-Api-Key": DISABLED_API_KEY_VALUE},
            json={
                "file_path": "src/app.py",
                "language": "python",
                "content": SQL_INJECTION_CODE,
            },
        )

        assert response.status_code == 403

    def test_analyze_with_expired_api_key_returns_401(self, ide_test_client_expired_key):
        """만료된 API Key로 요청하면 401을 반환한다 (I-09, S-02)

        Arrange: expires_at이 과거인 API Key
        Act: POST /api/v1/ide/analyze
        Assert: 401, INVALID_API_KEY
        """
        response = ide_test_client_expired_key.post(
            "/api/v1/ide/analyze",
            headers={"X-Api-Key": API_KEY_VALUE},
            json={
                "file_path": "src/app.py",
                "language": "python",
                "content": SQL_INJECTION_CODE,
            },
        )

        assert response.status_code == 401

    def test_analyze_unsupported_language_returns_422(self, ide_test_client):
        """지원하지 않는 언어 요청 시 422를 반환한다 (I-10, U-BS-03)

        Arrange: language="ruby" (지원 언어 목록에 없음)
        Act: POST /api/v1/ide/analyze
        Assert: 400 또는 422, INVALID_LANGUAGE
        """
        response = ide_test_client.post(
            "/api/v1/ide/analyze",
            headers={"X-Api-Key": API_KEY_VALUE},
            json={
                "file_path": "src/app.rb",
                "language": "ruby",
                "content": "def hello; puts 'hello'; end",
            },
        )

        assert response.status_code in (400, 422)

    def test_analyze_content_too_large_returns_400(self, ide_test_client):
        """content가 1MB를 초과하면 400을 반환한다 (I-11, U-BS-05)

        Arrange: 1.5MB 크기의 content
        Act: POST /api/v1/ide/analyze
        Assert: 400, CONTENT_TOO_LARGE
        """
        large_content = "x = 1\n" * 250_000  # ~1.5MB

        response = ide_test_client.post(
            "/api/v1/ide/analyze",
            headers={"X-Api-Key": API_KEY_VALUE},
            json={
                "file_path": "src/large_file.py",
                "language": "python",
                "content": large_content,
            },
        )

        assert response.status_code == 400

    def test_analyze_response_contains_analysis_duration(self, ide_test_client):
        """응답에 analysis_duration_ms 필드가 포함된다

        Arrange: 정상 분석 요청
        Act: POST /api/v1/ide/analyze
        Assert: 200, data에 analysis_duration_ms 필드 존재
        """
        with patch(
            "src.services.ide_analyzer.IdeAnalyzerService.analyze",
            new_callable=AsyncMock,
        ) as mock_analyze:
            mock_analyze.return_value = {
                "findings": [],
                "analysis_duration_ms": 250,
                "semgrep_version": "1.56.0",
            }

            response = ide_test_client.post(
                "/api/v1/ide/analyze",
                headers={"X-Api-Key": API_KEY_VALUE},
                json={
                    "file_path": "src/app.py",
                    "language": "python",
                    "content": SAFE_CODE,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "analysis_duration_ms" in data["data"]

    def test_analyze_finding_has_required_fields(self, ide_test_client):
        """findings 각 항목에 필수 필드가 모두 포함된다

        Arrange: SQL Injection finding을 반환하는 분석기
        Act: POST /api/v1/ide/analyze
        Assert: finding에 rule_id, severity, message, file_path, start_line, cwe_id, is_false_positive_filtered 포함
        """
        required_fields = [
            "rule_id", "severity", "message", "file_path",
            "start_line", "end_line", "cwe_id", "is_false_positive_filtered",
        ]

        with patch(
            "src.services.ide_analyzer.IdeAnalyzerService.analyze",
            new_callable=AsyncMock,
        ) as mock_analyze:
            mock_analyze.return_value = {
                "findings": [
                    {
                        "rule_id": "python.sqlalchemy.security.sql-injection",
                        "severity": "high",
                        "message": "SQL Injection 탐지",
                        "file_path": "src/api/routes/users.py",
                        "start_line": 6,
                        "end_line": 6,
                        "start_col": 4,
                        "end_col": 60,
                        "code_snippet": 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
                        "cwe_id": "CWE-89",
                        "owasp_category": "A03:2021 - Injection",
                        "vulnerability_type": "sql_injection",
                        "is_false_positive_filtered": False,
                    }
                ],
                "analysis_duration_ms": 180,
                "semgrep_version": "1.56.0",
            }

            response = ide_test_client.post(
                "/api/v1/ide/analyze",
                headers={"X-Api-Key": API_KEY_VALUE},
                json={
                    "file_path": "src/api/routes/users.py",
                    "language": "python",
                    "content": SQL_INJECTION_CODE,
                },
            )

        assert response.status_code == 200
        findings = response.json()["data"]["findings"]
        assert len(findings) >= 1
        for field in required_fields:
            assert field in findings[0], f"필수 필드 누락: {field}"

    def test_analyze_fp_filtered_finding_marked(self, ide_test_client):
        """FP 패턴에 매칭된 finding은 is_false_positive_filtered=true로 표시된다 (I-04, U-BS-06)

        Arrange: 팀에 FP 패턴이 등록된 상태, 해당 패턴에 매칭되는 finding
        Act: POST /api/v1/ide/analyze
        Assert: 해당 finding의 is_false_positive_filtered=True
        """
        with patch(
            "src.services.ide_analyzer.IdeAnalyzerService.analyze",
            new_callable=AsyncMock,
        ) as mock_analyze:
            mock_analyze.return_value = {
                "findings": [
                    {
                        "rule_id": "python.flask.security.xss",
                        "severity": "medium",
                        "message": "XSS 탐지",
                        "file_path": "tests/test_views.py",
                        "start_line": 10,
                        "end_line": 10,
                        "start_col": 0,
                        "end_col": 40,
                        "code_snippet": "return f'<p>{name}</p>'",
                        "cwe_id": "CWE-79",
                        "owasp_category": "A03:2021 - Injection",
                        "vulnerability_type": "xss",
                        "is_false_positive_filtered": True,
                    }
                ],
                "analysis_duration_ms": 200,
                "semgrep_version": "1.56.0",
            }

            response = ide_test_client.post(
                "/api/v1/ide/analyze",
                headers={"X-Api-Key": API_KEY_VALUE},
                json={
                    "file_path": "tests/test_views.py",
                    "language": "python",
                    "content": "from flask import request\ndef render():\n    name = request.args.get('name')\n    return f'<p>{name}</p>'",
                },
            )

        assert response.status_code == 200
        findings = response.json()["data"]["findings"]
        fp_filtered = [f for f in findings if f.get("is_false_positive_filtered") is True]
        assert len(fp_filtered) >= 1

    def test_analyze_javascript_code(self, ide_test_client):
        """JavaScript 파일도 분석할 수 있다 (I-05)

        Arrange: eval() 사용하는 JavaScript 코드
        Act: POST /api/v1/ide/analyze (language="javascript")
        Assert: 200, findings에 code_injection 관련 항목
        """
        with patch(
            "src.services.ide_analyzer.IdeAnalyzerService.analyze",
            new_callable=AsyncMock,
        ) as mock_analyze:
            mock_analyze.return_value = {
                "findings": [
                    {
                        "rule_id": "javascript.browser.security.eval-detected",
                        "severity": "high",
                        "message": "eval() 사용 탐지 — 코드 인젝션 위험",
                        "file_path": "src/utils.js",
                        "start_line": 2,
                        "end_line": 2,
                        "start_col": 4,
                        "end_col": 20,
                        "code_snippet": "    eval(userInput);",
                        "cwe_id": "CWE-94",
                        "owasp_category": "A03:2021 - Injection",
                        "vulnerability_type": "code_injection",
                        "is_false_positive_filtered": False,
                    }
                ],
                "analysis_duration_ms": 150,
                "semgrep_version": "1.56.0",
            }

            response = ide_test_client.post(
                "/api/v1/ide/analyze",
                headers={"X-Api-Key": API_KEY_VALUE},
                json={
                    "file_path": "src/utils.js",
                    "language": "javascript",
                    "content": EVAL_INJECTION_CODE,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["findings"]) >= 1


# ──────────────────────────────────────────────────────────────
# GET /api/v1/ide/false-positive-patterns 테스트
# ──────────────────────────────────────────────────────────────

class TestIdeFalsePositivePatterns:
    """GET /api/v1/ide/false-positive-patterns — 팀 오탐 패턴 목록"""

    def test_get_fp_patterns_returns_team_patterns(self, ide_test_client):
        """팀의 FP 패턴 목록을 반환한다 (I-13)

        Arrange: 팀에 FP 패턴 3개 등록된 상태, 유효한 API Key
        Act: GET /api/v1/ide/false-positive-patterns
        Assert: 200, patterns 배열에 3개 항목, ETag 헤더 포함
        """
        response = ide_test_client.get(
            "/api/v1/ide/false-positive-patterns",
            headers={"X-Api-Key": API_KEY_VALUE},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "patterns" in data["data"]
        assert isinstance(data["data"]["patterns"], list)
        assert len(data["data"]["patterns"]) == 3

    def test_get_fp_patterns_response_has_etag(self, ide_test_client):
        """FP 패턴 응답에 ETag 헤더가 포함된다 (I-13)

        Arrange: 유효한 API Key
        Act: GET /api/v1/ide/false-positive-patterns
        Assert: 200, ETag 헤더 존재
        """
        response = ide_test_client.get(
            "/api/v1/ide/false-positive-patterns",
            headers={"X-Api-Key": API_KEY_VALUE},
        )

        assert response.status_code == 200
        assert "etag" in response.headers or "ETag" in response.headers or "etag" in response.json().get("data", {})

    def test_get_fp_patterns_pattern_has_required_fields(self, ide_test_client):
        """FP 패턴 각 항목에 필수 필드가 포함된다

        Arrange: 유효한 API Key
        Act: GET /api/v1/ide/false-positive-patterns
        Assert: 패턴에 id, semgrep_rule_id, file_pattern, is_active, updated_at 포함
        """
        response = ide_test_client.get(
            "/api/v1/ide/false-positive-patterns",
            headers={"X-Api-Key": API_KEY_VALUE},
        )

        assert response.status_code == 200
        patterns = response.json()["data"]["patterns"]
        assert len(patterns) >= 1
        required_fields = ["id", "semgrep_rule_id", "file_pattern", "is_active", "updated_at"]
        for field in required_fields:
            assert field in patterns[0], f"필수 필드 누락: {field}"

    def test_get_fp_patterns_without_api_key_returns_401(self, ide_test_client_no_key):
        """API Key 없이 요청하면 401을 반환한다 (I-06, S-01)

        Arrange: X-Api-Key 헤더 누락
        Act: GET /api/v1/ide/false-positive-patterns
        Assert: 401
        """
        response = ide_test_client_no_key.get(
            "/api/v1/ide/false-positive-patterns",
        )

        assert response.status_code == 401

    def test_get_fp_patterns_empty_team_returns_empty_list(self, ide_test_client_no_fp_patterns):
        """FP 패턴 미등록 팀은 빈 패턴 배열을 반환한다 (I-15)

        Arrange: FP 패턴 없는 팀의 유효한 API Key
        Act: GET /api/v1/ide/false-positive-patterns
        Assert: 200, patterns=[]
        """
        response = ide_test_client_no_fp_patterns.get(
            "/api/v1/ide/false-positive-patterns",
            headers={"X-Api-Key": API_KEY_VALUE},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["patterns"] == []

    def test_get_fp_patterns_etag_cache_hit_returns_304(self, ide_test_client):
        """If-None-Match 헤더가 ETag와 일치하면 304를 반환한다 (I-14)

        Arrange: 첫 요청으로 ETag 획득
        Act: GET /api/v1/ide/false-positive-patterns (If-None-Match: <etag>)
        Assert: 304 (변경 없음, 본문 없음)
        """
        # 1단계: 첫 요청으로 ETag 획득
        first_response = ide_test_client.get(
            "/api/v1/ide/false-positive-patterns",
            headers={"X-Api-Key": API_KEY_VALUE},
        )
        assert first_response.status_code == 200

        # ETag 추출 (헤더 또는 응답 바디에서)
        etag = (
            first_response.headers.get("ETag")
            or first_response.headers.get("etag")
            or first_response.json().get("data", {}).get("etag", '"test-etag"')
        )

        # 2단계: If-None-Match 헤더로 조건부 요청
        second_response = ide_test_client.get(
            "/api/v1/ide/false-positive-patterns",
            headers={
                "X-Api-Key": API_KEY_VALUE,
                "If-None-Match": etag,
            },
        )

        assert second_response.status_code == 304


# ──────────────────────────────────────────────────────────────
# POST /api/v1/ide/patch-suggestion 테스트
# ──────────────────────────────────────────────────────────────

class TestIdePatchSuggestion:
    """POST /api/v1/ide/patch-suggestion — LLM 기반 패치 diff 생성"""

    def test_patch_suggestion_returns_diff(self, ide_test_client):
        """패치 제안 요청 시 patch_diff, patch_description, vulnerability_detail을 반환한다 (I-16)

        Arrange: SQL Injection finding + 코드, 유효한 API Key
        Act: POST /api/v1/ide/patch-suggestion
        Assert: 200, patch_diff (unified diff), patch_description, vulnerability_detail 포함
        """
        with patch(
            "src.services.ide_analyzer.IdeAnalyzerService.generate_patch",
            new_callable=AsyncMock,
        ) as mock_patch:
            mock_patch.return_value = {
                "patch_diff": (
                    '--- a/src/api/routes/users.py\n'
                    '+++ b/src/api/routes/users.py\n'
                    '@@ -6,1 +6,1 @@\n'
                    '-    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")\n'
                    '+    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))'
                ),
                "patch_description": "f-string SQL 쿼리를 파라미터 바인딩 방식으로 변경하여 SQL Injection을 방지합니다.",
                "vulnerability_detail": {
                    "type": "sql_injection",
                    "severity": "high",
                    "cwe_id": "CWE-89",
                    "owasp_category": "A03:2021 - Injection",
                    "description": "사용자 입력값이 SQL 쿼리에 직접 삽입되면 공격자가 임의의 SQL을 실행할 수 있습니다.",
                    "references": [
                        "https://cwe.mitre.org/data/definitions/89.html",
                        "https://owasp.org/Top10/",
                    ],
                },
            }

            response = ide_test_client.post(
                "/api/v1/ide/patch-suggestion",
                headers={"X-Api-Key": API_KEY_VALUE},
                json={
                    "file_path": "src/api/routes/users.py",
                    "language": "python",
                    "content": SQL_INJECTION_CODE,
                    "finding": SAMPLE_FINDING,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "patch_diff" in data["data"]
        assert "patch_description" in data["data"]
        assert "vulnerability_detail" in data["data"]
        assert "---" in data["data"]["patch_diff"]

    def test_patch_suggestion_diff_has_unified_format(self, ide_test_client):
        """patch_diff는 unified diff 형식이어야 한다

        Arrange: 정상 패치 제안 요청
        Act: POST /api/v1/ide/patch-suggestion
        Assert: patch_diff에 '--- a/' 및 '+++ b/' 접두사 포함
        """
        with patch(
            "src.services.ide_analyzer.IdeAnalyzerService.generate_patch",
            new_callable=AsyncMock,
        ) as mock_patch:
            mock_patch.return_value = {
                "patch_diff": (
                    '--- a/src/api/routes/users.py\n'
                    '+++ b/src/api/routes/users.py\n'
                    '@@ -6,1 +6,1 @@\n'
                    '-    old_line\n'
                    '+    new_line\n'
                ),
                "patch_description": "패치 설명",
                "vulnerability_detail": {
                    "type": "sql_injection",
                    "severity": "high",
                    "cwe_id": "CWE-89",
                    "owasp_category": "A03:2021 - Injection",
                    "description": "설명",
                    "references": [],
                },
            }

            response = ide_test_client.post(
                "/api/v1/ide/patch-suggestion",
                headers={"X-Api-Key": API_KEY_VALUE},
                json={
                    "file_path": "src/api/routes/users.py",
                    "language": "python",
                    "content": SQL_INJECTION_CODE,
                    "finding": SAMPLE_FINDING,
                },
            )

        assert response.status_code == 200
        patch_diff = response.json()["data"]["patch_diff"]
        assert "---" in patch_diff
        assert "+++" in patch_diff

    def test_patch_suggestion_without_api_key_returns_401(self, ide_test_client_no_key):
        """API Key 없이 패치 제안 요청 시 401을 반환한다 (S-01)

        Arrange: X-Api-Key 헤더 누락
        Act: POST /api/v1/ide/patch-suggestion
        Assert: 401
        """
        response = ide_test_client_no_key.post(
            "/api/v1/ide/patch-suggestion",
            json={
                "file_path": "src/api/routes/users.py",
                "language": "python",
                "content": SQL_INJECTION_CODE,
                "finding": SAMPLE_FINDING,
            },
        )

        assert response.status_code == 401

    def test_patch_suggestion_incomplete_finding_returns_400(self, ide_test_client):
        """불완전한 finding 정보 (rule_id 누락) 시 400을 반환한다 (I-18)

        Arrange: finding에 rule_id 누락
        Act: POST /api/v1/ide/patch-suggestion
        Assert: 400 또는 422, INVALID_FINDING
        """
        incomplete_finding = {
            # rule_id 누락
            "start_line": 6,
            "end_line": 6,
            "code_snippet": 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
            "message": "SQL Injection",
        }

        response = ide_test_client.post(
            "/api/v1/ide/patch-suggestion",
            headers={"X-Api-Key": API_KEY_VALUE},
            json={
                "file_path": "src/api/routes/users.py",
                "language": "python",
                "content": SQL_INJECTION_CODE,
                "finding": incomplete_finding,
            },
        )

        assert response.status_code in (400, 422)

    def test_patch_suggestion_missing_finding_returns_422(self, ide_test_client):
        """finding 필드 자체가 누락되면 422를 반환한다

        Arrange: finding 필드 없이 요청
        Act: POST /api/v1/ide/patch-suggestion
        Assert: 422 (유효성 검사 실패)
        """
        response = ide_test_client.post(
            "/api/v1/ide/patch-suggestion",
            headers={"X-Api-Key": API_KEY_VALUE},
            json={
                "file_path": "src/api/routes/users.py",
                "language": "python",
                "content": SQL_INJECTION_CODE,
                # finding 필드 없음
            },
        )

        assert response.status_code == 422

    def test_patch_suggestion_vulnerability_detail_has_cwe(self, ide_test_client):
        """vulnerability_detail에 cwe_id와 owasp_category가 포함된다

        Arrange: 정상 패치 제안 요청
        Act: POST /api/v1/ide/patch-suggestion
        Assert: vulnerability_detail에 cwe_id, owasp_category, references 포함
        """
        with patch(
            "src.services.ide_analyzer.IdeAnalyzerService.generate_patch",
            new_callable=AsyncMock,
        ) as mock_patch:
            mock_patch.return_value = {
                "patch_diff": "--- a/src/file.py\n+++ b/src/file.py\n@@ -1 +1 @@\n-old\n+new",
                "patch_description": "설명",
                "vulnerability_detail": {
                    "type": "sql_injection",
                    "severity": "high",
                    "cwe_id": "CWE-89",
                    "owasp_category": "A03:2021 - Injection",
                    "description": "상세 설명",
                    "references": ["https://cwe.mitre.org/data/definitions/89.html"],
                },
            }

            response = ide_test_client.post(
                "/api/v1/ide/patch-suggestion",
                headers={"X-Api-Key": API_KEY_VALUE},
                json={
                    "file_path": "src/file.py",
                    "language": "python",
                    "content": SQL_INJECTION_CODE,
                    "finding": SAMPLE_FINDING,
                },
            )

        assert response.status_code == 200
        detail = response.json()["data"]["vulnerability_detail"]
        assert "cwe_id" in detail
        assert "owasp_category" in detail
        assert "references" in detail
        assert isinstance(detail["references"], list)
