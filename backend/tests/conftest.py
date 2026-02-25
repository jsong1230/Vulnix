"""pytest 공통 픽스처 — F-01 저장소 연동 및 스캔 트리거 테스트"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# 테스트용 환경변수를 미리 패치하여 Settings 로드 오류 방지
TEST_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test_vulnix",
    "REDIS_URL": "redis://localhost:6379",
    "GITHUB_APP_ID": "123456",
    "GITHUB_APP_PRIVATE_KEY": "-----BEGIN RSA PRIVATE KEY-----\ntest_key\n-----END RSA PRIVATE KEY-----",
    "GITHUB_WEBHOOK_SECRET": "test_webhook_secret_for_hmac",
    "GITHUB_CLIENT_ID": "test_client_id",
    "GITHUB_CLIENT_SECRET": "test_client_secret",
    "ANTHROPIC_API_KEY": "test_anthropic_key",
    "JWT_SECRET_KEY": "test_jwt_secret_key_for_testing",
}


@pytest.fixture(autouse=True, scope="session")
def patch_settings_env():
    """테스트 세션 전체에 환경변수를 패치하여 외부 서비스 연결을 차단한다."""
    with patch.dict("os.environ", TEST_ENV):
        # Settings lru_cache 초기화
        from src.config import get_settings
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()


@pytest.fixture
def test_client():
    """FastAPI TestClient 픽스처.

    실제 DB / Redis 연결 없이 HTTP 요청 테스트에 사용한다.
    DB 세션과 현재 사용자 의존성을 Mock으로 오버라이드한다.
    F-04: UUID 기반 스마트 Mock DB를 포함한다.
    """
    from src.main import create_app
    from src.api.deps import get_db, get_current_user

    app = create_app()

    # DB 세션 Mock 오버라이드 (F-04: UUID 기반 스마트 Mock)
    mock_db_session = _build_f04_mock_db()

    async def override_get_db():
        yield mock_db_session

    # 현재 사용자 Mock 오버라이드 (기본: 인증된 사용자)
    mock_user = MagicMock()
    mock_user.id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    mock_user.github_login = "test_user"
    mock_user.github_id = 999

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def _build_f04_mock_db():
    """F-04 테스트용 UUID 인식 스마트 Mock DB 세션을 생성한다.

    알려진 UUID에 대해 적절한 Mock 객체를 반환하고,
    알 수 없는 UUID(ffffffff 등)에 대해 None을 반환한다.
    """
    from src.models.scan_job import ScanJob
    from src.models.vulnerability import Vulnerability
    from src.models.repository import Repository
    from src.models.team import TeamMember

    # ── sample_repo 픽스처와 동일한 값 ──
    repo_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    team_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    scan_completed_id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    scan_running_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    none_id = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")

    # ── Mock 저장소 ──
    mock_repo = MagicMock(spec=Repository)
    mock_repo.id = repo_id
    mock_repo.team_id = team_id
    mock_repo.platform = "github"
    mock_repo.platform_repo_id = None
    mock_repo.github_repo_id = 123456
    mock_repo.full_name = "test-org/test-repo"
    mock_repo.default_branch = "main"
    mock_repo.language = "Python"
    mock_repo.is_active = True
    mock_repo.installation_id = 789
    mock_repo.webhook_secret = None
    mock_repo.last_scanned_at = None
    mock_repo.security_score = 80.0
    mock_repo.is_initial_scan_done = True
    mock_repo.created_at = datetime(2026, 2, 25, 9, 0, 0)

    # ── Mock 완료 스캔 ──
    mock_scan_completed = MagicMock(spec=ScanJob)
    mock_scan_completed.id = scan_completed_id
    mock_scan_completed.repo_id = repo_id
    mock_scan_completed.status = "completed"
    mock_scan_completed.trigger_type = "manual"
    mock_scan_completed.commit_sha = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    mock_scan_completed.branch = "main"
    mock_scan_completed.pr_number = None
    mock_scan_completed.findings_count = 15
    mock_scan_completed.true_positives_count = 8
    mock_scan_completed.false_positives_count = 7
    mock_scan_completed.duration_seconds = 120
    mock_scan_completed.error_message = None
    mock_scan_completed.started_at = datetime(2026, 2, 25, 10, 0, 0)
    mock_scan_completed.completed_at = datetime(2026, 2, 25, 10, 2, 0)
    mock_scan_completed.created_at = datetime(2026, 2, 25, 9, 59, 50)
    mock_scan_completed.repository = mock_repo

    # ── Mock 진행 중 스캔 ──
    mock_scan_running = MagicMock(spec=ScanJob)
    mock_scan_running.id = scan_running_id
    mock_scan_running.repo_id = repo_id
    mock_scan_running.status = "running"
    mock_scan_running.trigger_type = "manual"
    mock_scan_running.commit_sha = None
    mock_scan_running.branch = "main"
    mock_scan_running.pr_number = None
    mock_scan_running.findings_count = 0
    mock_scan_running.true_positives_count = 0
    mock_scan_running.false_positives_count = 0
    mock_scan_running.duration_seconds = None
    mock_scan_running.error_message = None
    mock_scan_running.started_at = datetime(2026, 2, 25, 10, 0, 0)
    mock_scan_running.completed_at = None
    mock_scan_running.created_at = datetime(2026, 2, 25, 9, 59, 50)
    mock_scan_running.repository = mock_repo

    # ── Mock 취약점 목록 (10건) ──
    severities = ["critical", "high", "high", "medium", "medium", "medium", "low", "low", "low", "low"]
    statuses = ["open", "open", "patched", "open", "false_positive", "ignored", "open", "patched", "open", "open"]
    vuln_types = [
        "sql_injection", "xss", "hardcoded_credentials", "path_traversal",
        "ssrf", "command_injection", "open_redirect", "insecure_deserialization",
        "xxe", "csrf",
    ]
    mock_vulns = []
    for i, (sev, st, vtype) in enumerate(zip(severities, statuses, vuln_types)):
        v = MagicMock(spec=Vulnerability)
        v.id = uuid.UUID(f"eeeeeeee-eeee-eeee-eeee-{str(i).zfill(12)}")
        v.scan_job_id = scan_completed_id
        v.repo_id = repo_id
        v.status = st
        v.severity = sev
        v.vulnerability_type = vtype
        v.cwe_id = f"CWE-{89 + i}"
        v.owasp_category = "A03:2021 - Injection"
        v.file_path = f"src/module_{i}/code.py"
        v.start_line = 10 + i * 5
        v.end_line = 12 + i * 5
        v.code_snippet = f"# 취약한 코드 예시 {i}"
        v.description = f"취약점 설명 {i}"
        v.llm_reasoning = f"LLM 분석 근거 {i}"
        v.llm_confidence = 0.90 - i * 0.02
        v.semgrep_rule_id = f"python.security.rule-{i}"
        v.references = [f"https://cwe.mitre.org/data/definitions/{89 + i}.html"]
        v.detected_at = datetime(2026, 2, 25, 10, i, 0)
        v.resolved_at = datetime(2026, 2, 25, 11, 0, 0) if st != "open" else None
        v.created_at = datetime(2026, 2, 25, 10, i, 0)
        v.patch_pr = None
        v.repository = mock_repo
        mock_vulns.append(v)

    # vuln_id → vuln 맵
    vuln_map = {v.id: v for v in mock_vulns}

    # ── Mock TeamMember ──
    mock_member = MagicMock(spec=TeamMember)
    mock_member.team_id = team_id
    mock_member.user_id = user_id
    mock_member.role = "owner"

    # ── 스마트 execute Mock 설정 ──
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.close = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.delete = AsyncMock()

    def _make_result(items):
        """주어진 항목 목록을 반환하는 Mock result 객체를 생성한다."""
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

    def _extract_params(query) -> dict:
        """SQLAlchemy 쿼리 객체에서 바인드 파라미터를 추출한다."""
        try:
            return dict(query.compile().params)
        except Exception:
            return {}

    def _params_contain_id(params: dict, target_id: uuid.UUID) -> bool:
        """파라미터 딕셔너리에 특정 UUID가 포함되어 있는지 확인한다."""
        for val in params.values():
            if isinstance(val, uuid.UUID) and val == target_id:
                return True
            if isinstance(val, str) and str(target_id) == val:
                return True
        return False

    async def smart_execute(query, *args, **kwargs):
        """쿼리 파라미터를 분석하여 적절한 Mock 데이터를 반환한다."""
        import re
        query_str = str(query).lower()
        params = _extract_params(query)
        all_param_uuids = {v for v in params.values() if isinstance(v, uuid.UUID)}

        # scan_job 테이블 조회 (FROM scan_job 또는 JOIN scan_job 패턴으로 식별)
        # 주의: vulnerability.scan_job_id 컬럼 때문에 단순 'scan_job' 포함으로는 구별 불가
        is_scan_job_table = bool(re.search(r'\bfrom scan_job\b|\bjoin scan_job\b', query_str))
        if is_scan_job_table:
            # none_id → None (404 케이스)
            if _params_contain_id(params, none_id):
                return _make_result(None)
            # completed 스캔 ID → mock_scan_completed
            if _params_contain_id(params, scan_completed_id):
                return _make_result(mock_scan_completed)
            # running 스캔 ID → mock_scan_running
            if _params_contain_id(params, scan_running_id):
                return _make_result(mock_scan_running)
            # 목록 조회 (WHERE IN repo_ids) → 두 스캔 모두 반환
            if repo_id in all_param_uuids or not all_param_uuids:
                return _make_result([mock_scan_completed])
            return _make_result([mock_scan_completed])

        # vulnerability 테이블 조회
        if "vulnerability" in query_str:
            # none_id → None (404 케이스)
            if _params_contain_id(params, none_id):
                return _make_result(None)
            # 특정 vuln_id 조회
            for vid, vuln in vuln_map.items():
                if _params_contain_id(params, vid):
                    return _make_result(vuln)
            # 목록 조회 (WHERE IN repo_ids) → 전체 반환
            return _make_result(mock_vulns)

        # repository 테이블 조회
        if "repository" in query_str:
            # none_id → None
            if _params_contain_id(params, none_id):
                return _make_result(None)
            # F-09: GitLab/Bitbucket platform 중복 확인 쿼리 → None 반환 (미등록 상태 시뮬레이션)
            # platform_repo_id가 string 파라미터로 포함된 경우 처리
            str_params = {k: v for k, v in params.items() if isinstance(v, str)}
            if any(v in ("gitlab", "bitbucket") for v in str_params.values()):
                # platform 필터링 쿼리는 platform_repo_id 조회이므로 None 반환 (미등록)
                # 단, platform_repo_id를 SELECT하는 목록 조회는 빈 리스트 반환
                if "platform_repo_id" in query_str and "from repository" in query_str:
                    return _make_result([])
                return _make_result(None)
            # repo_id 기반 조회
            if _params_contain_id(params, repo_id):
                return _make_result(mock_repo)
            # platform 필터 조회 (GET /repos?platform=gitlab) → 빈 목록 반환
            # platform 필터가 있으면 해당 platform 저장소가 없는 것으로 시뮬레이션
            # 단, platform 파라미터 없이 all_param_uuids 기반 조회는 기존 동작 유지
            # team_id 기반 조회 (저장소 목록)
            if _params_contain_id(params, team_id) or not all_param_uuids:
                return _make_result([mock_repo])
            return _make_result([mock_repo])

        # team_member 테이블 조회 (사용자 팀/멤버 확인)
        if "team_member" in query_str:
            result = MagicMock()
            # role 컬럼만 SELECT (get_user_team_role) → scalar로 "owner" 문자열 반환
            if "team_member.role" in query_str:
                result.scalar_one_or_none.return_value = "owner"
                result.scalars.return_value.all.return_value = ["owner"]
                result.scalars.return_value.first.return_value = "owner"
            # team_id 컬럼만 SELECT (get_user_team_ids) → scalar로 team_id UUID 반환
            elif "team_member.team_id" in query_str:
                result.scalar_one_or_none.return_value = team_id
                result.scalars.return_value.all.return_value = [team_id]
                result.scalars.return_value.first.return_value = team_id
            else:
                # 전체 TeamMember 객체 SELECT → mock_member 반환
                result.scalar_one_or_none.return_value = mock_member
                result.scalars.return_value.all.return_value = [mock_member]
                result.scalars.return_value.first.return_value = mock_member
            return result

        # 기본 빈 결과
        return _make_result([])

    mock_db.execute = AsyncMock(side_effect=smart_execute)
    mock_db.scalar_one_or_none = AsyncMock(return_value=None)

    return mock_db


@pytest.fixture
def mock_db():
    """AsyncMock DB 세션 픽스처.

    단위 테스트에서 SQLAlchemy AsyncSession을 대체한다.
    execute, scalar_one_or_none, add, commit, flush 등을 Mock 처리.
    """
    db = AsyncMock()
    db.execute = AsyncMock()
    db.scalar_one_or_none = AsyncMock(return_value=None)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def mock_github_service():
    """GitHubAppService Mock 픽스처.

    GitHub API 호출 없이 서비스 로직을 테스트할 수 있도록 한다.
    """
    service = AsyncMock()
    service.get_installation_token = AsyncMock(return_value="ghs_test_installation_token")
    service.get_installation_repos = AsyncMock(return_value=[
        {
            "id": 123456,
            "full_name": "test-org/test-repo",
            "private": True,
            "default_branch": "main",
            "language": "Python",
        }
    ])
    service.get_pr_changed_files = AsyncMock(return_value=[
        "src/app.py",
        "src/utils.py",
    ])
    service.get_default_branch_sha = AsyncMock(
        return_value="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    )
    service._generate_jwt = MagicMock(return_value="mock.jwt.token")
    return service


@pytest.fixture
def mock_orchestrator():
    """ScanOrchestrator Mock 픽스처.

    Redis / RQ 큐 연결 없이 스캔 큐 등록 로직을 테스트한다.
    """
    orchestrator = AsyncMock()
    orchestrator.enqueue_scan = AsyncMock(
        return_value=str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
    )
    orchestrator.has_active_scan = AsyncMock(return_value=False)
    orchestrator.cancel_active_scans_for_pr = AsyncMock(return_value=0)
    orchestrator.update_job_status = AsyncMock(return_value=None)
    orchestrator.get_job_status = AsyncMock(return_value="queued")
    return orchestrator


@pytest.fixture
def sample_repo():
    """Repository 모델 픽스처.

    테스트에서 기본 저장소 데이터로 사용한다.
    """
    from src.models.repository import Repository

    repo = MagicMock(spec=Repository)
    repo.id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    repo.team_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    repo.platform = "github"
    repo.platform_repo_id = None
    repo.github_repo_id = 123456
    repo.full_name = "test-org/test-repo"
    repo.default_branch = "main"
    repo.language = "Python"
    repo.is_active = True
    repo.installation_id = 789
    repo.webhook_secret = None
    repo.last_scanned_at = None
    repo.security_score = None
    repo.is_initial_scan_done = False
    repo.created_at = datetime(2026, 2, 25, 10, 0, 0)
    return repo


@pytest.fixture
def valid_webhook_payload():
    """GitHub push 이벤트 페이로드 픽스처.

    main 브랜치에 Python 파일을 포함한 push 이벤트를 시뮬레이션한다.
    """
    return {
        "ref": "refs/heads/main",
        "after": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "repository": {
            "id": 123456,
            "full_name": "test-org/test-repo",
            "default_branch": "main",
            "language": "Python",
        },
        "commits": [
            {
                "id": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                "added": ["src/new_feature.py"],
                "modified": ["src/app.py"],
                "removed": [],
            }
        ],
        "installation": {
            "id": 789,
        },
    }


@pytest.fixture
def valid_pr_payload():
    """GitHub pull_request opened 이벤트 페이로드 픽스처."""
    return {
        "action": "opened",
        "number": 42,
        "pull_request": {
            "number": 42,
            "head": {
                "ref": "feature/add-login",
                "sha": "b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3",
            },
            "base": {
                "ref": "main",
            },
        },
        "repository": {
            "id": 123456,
            "full_name": "test-org/test-repo",
            "default_branch": "main",
            "language": "Python",
        },
        "installation": {
            "id": 789,
        },
    }


@pytest.fixture
def valid_installation_created_payload():
    """GitHub installation.created 이벤트 페이로드 픽스처."""
    return {
        "action": "created",
        "installation": {
            "id": 789,
            "account": {
                "id": 11111,
                "login": "test-org",
            },
        },
        "repositories": [
            {
                "id": 123456,
                "full_name": "test-org/test-repo",
                "private": True,
            },
            {
                "id": 234567,
                "full_name": "test-org/another-repo",
                "private": False,
            },
        ],
        "sender": {
            "id": 999,
            "login": "test_user",
        },
    }


@pytest.fixture
def valid_installation_deleted_payload():
    """GitHub installation.deleted 이벤트 페이로드 픽스처."""
    return {
        "action": "deleted",
        "installation": {
            "id": 789,
            "account": {
                "id": 11111,
                "login": "test-org",
            },
        },
        "repositories": [
            {
                "id": 123456,
                "full_name": "test-org/test-repo",
                "private": True,
            },
        ],
        "sender": {
            "id": 999,
            "login": "test_user",
        },
    }


def make_github_signature(payload: dict | bytes, secret: str = "test_webhook_secret_for_hmac") -> str:
    """HMAC-SHA256 서명을 생성하는 헬퍼 함수.

    Args:
        payload: 서명할 페이로드 (dict 또는 bytes)
        secret: Webhook 시크릿 키

    Returns:
        "sha256=<hex_digest>" 형식의 서명 문자열
    """
    if isinstance(payload, dict):
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    else:
        raw = payload

    signature = hmac.new(
        key=secret.encode("utf-8"),
        msg=raw,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"sha256={signature}"


@pytest.fixture
def github_signature():
    """HMAC-SHA256 서명 생성 헬퍼 픽스처.

    테스트 케이스에서 `github_signature(payload)` 형태로 사용한다.
    """
    return make_github_signature


# ──────────────────────────────────────────────────────────────
# F-02 취약점 탐지 엔진 테스트 픽스처
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def sql_injection_code():
    """SQL Injection 취약 코드 픽스처."""
    return '''
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return db.execute(query)
'''


@pytest.fixture
def xss_code():
    """XSS 취약 코드 픽스처."""
    return '''
from flask import request, make_response
def render_name():
    name = request.args.get("name")
    return make_response(f"<h1>Hello {name}</h1>")
'''


@pytest.fixture
def hardcoded_creds_code():
    """Hardcoded Credentials 취약 코드 픽스처."""
    return '''
AWS_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
DB_PASSWORD = "super_secret_password_123"
'''


@pytest.fixture
def semgrep_json_output():
    """SQL Injection 탐지 결과 mock JSON 픽스처."""
    return {
        "results": [{
            "check_id": "python.lang.security.audit.formatted-sql-query.formatted-sql-query",
            "path": "app.py",
            "start": {"line": 2, "col": 12},
            "end": {"line": 2, "col": 50},
            "extra": {
                "message": "Detected SQL query formatted with user input...",
                "severity": "ERROR",
                "metadata": {"cwe": ["CWE-89"], "owasp": ["A03:2021"]}
            }
        }],
        "errors": []
    }


@pytest.fixture
def llm_analysis_response():
    """Claude API 응답 mock 픽스처."""
    return {
        "findings": [{
            "finding_id": "0",
            "is_true_positive": True,
            "confidence": 0.95,
            "severity": "High",
            "reasoning": "사용자 입력이 SQL 쿼리에 직접 삽입됨",
            "cwe_id": "CWE-89",
            "owasp_category": "A03:2021 - Injection"
        }]
    }


@pytest.fixture
def mock_semgrep_output():
    """Semgrep CLI mock 출력 픽스처 (SQL Injection 1건)."""
    return {
        "results": [
            {
                "check_id": "vulnix.python.sql_injection.string_format",
                "path": "/tmp/vulnix-scan-test/app/db.py",
                "start": {"line": 5, "col": 5},
                "end": {"line": 5, "col": 65},
                "extra": {
                    "message": "SQL Injection 취약점 탐지...",
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
def mock_claude_analysis_response():
    """Claude 분석 API mock 응답 픽스처."""
    return {
        "results": [
            {
                "rule_id": "vulnix.python.sql_injection.string_format",
                "is_true_positive": True,
                "confidence": 0.95,
                "severity": "High",
                "reasoning": "사용자 입력(user_id)이 f-string을 통해 SQL 쿼리에 직접 삽입되어 있어 SQL Injection 공격에 취약합니다.",
                "owasp_category": "A03:2021 - Injection",
                "vulnerability_type": "sql_injection",
            }
        ]
    }


@pytest.fixture
def mock_claude_patch_response():
    """Claude 패치 생성 API mock 응답 픽스처."""
    return {
        "patch_diff": '--- a/app/db.py\n+++ b/app/db.py\n@@ -4,3 +4,3 @@\n-    cursor.execute(f"SELECT * FROM users WHERE id={user_id}")\n+    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))',
        "patch_description": "f-string SQL 쿼리를 파라미터화된 쿼리로 변경하여 SQL Injection 취약점을 수정합니다.",
        "references": ["https://cwe.mitre.org/data/definitions/89.html"],
    }


# ──────────────────────────────────────────────────────────────
# F-03 자동 패치 PR 생성 테스트 픽스처
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_vulnerability():
    """Vulnerability 모델 픽스처 (F-02 결과물).

    SQL Injection 취약점이 탐지된 상태를 나타낸다.
    """
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
    vuln.created_at = datetime(2026, 2, 25, 10, 0, 0)
    return vuln


@pytest.fixture
def sample_patch_pr():
    """PatchPR 모델 픽스처.

    SQL Injection 취약점에 대한 자동 생성 패치 PR을 나타낸다.
    """
    from src.models.patch_pr import PatchPR

    pr = MagicMock(spec=PatchPR)
    pr.id = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
    pr.vulnerability_id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    pr.repo_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    pr.github_pr_number = 42
    pr.github_pr_url = "https://github.com/test-org/test-repo/pull/42"
    pr.branch_name = "vulnix/fix-sql-injection-a1b2c3d"
    pr.status = "created"
    pr.patch_diff = (
        '--- a/app/db.py\n'
        '+++ b/app/db.py\n'
        '@@ -4,3 +4,3 @@\n'
        '-    cursor.execute(f"SELECT * FROM users WHERE id={user_id}")\n'
        '+    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))'
    )
    pr.patch_description = "f-string SQL 쿼리를 파라미터화된 쿼리로 변경하여 SQL Injection 취약점을 수정합니다."
    pr.created_at = datetime(2026, 2, 25, 10, 30, 0)
    pr.merged_at = None
    return pr


@pytest.fixture
def mock_patch_diff():
    """unified diff 픽스처 (SQL Injection 패치).

    원본 파일에서 f-string SQL 쿼리를 파라미터화 쿼리로 변환하는 diff.
    """
    return """--- a/app.py
+++ b/app.py
@@ -1,3 +1,4 @@
 def get_user(user_id):
-    query = f"SELECT * FROM users WHERE id = {user_id}"
+    query = "SELECT * FROM users WHERE id = %s"
+    return db.execute(query, (user_id,))
-    return db.execute(query)"""


# ──────────────────────────────────────────────────────────────
# F-04 스캔 결과 API 테스트 픽스처
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_scan_job(sample_repo):
    """완료된 스캔 작업 픽스처 (ScanJob completed 상태).

    test_scans_api.py, test_dashboard_api.py에서 사용한다.
    """
    from src.models.scan_job import ScanJob

    scan = MagicMock(spec=ScanJob)
    scan.id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    scan.repo_id = sample_repo.id
    scan.status = "completed"
    scan.trigger_type = "manual"
    scan.commit_sha = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    scan.branch = "main"
    scan.pr_number = None
    scan.findings_count = 15
    scan.true_positives_count = 8
    scan.false_positives_count = 7
    scan.duration_seconds = 120
    scan.error_message = None
    scan.started_at = datetime(2026, 2, 25, 10, 0, 0)
    scan.completed_at = datetime(2026, 2, 25, 10, 2, 0)
    scan.created_at = datetime(2026, 2, 25, 9, 59, 50)
    # 저장소 관계
    scan.repository = sample_repo
    return scan


@pytest.fixture
def sample_vulnerability_list(sample_repo, sample_scan_job):
    """다양한 심각도/상태의 취약점 목록 픽스처 (10건).

    test_vulns_api.py, test_dashboard_api.py에서 사용한다.
    """
    from src.models.vulnerability import Vulnerability

    severities = ["critical", "high", "high", "medium", "medium", "medium", "low", "low", "low", "low"]
    statuses = ["open", "open", "patched", "open", "false_positive", "ignored", "open", "patched", "open", "open"]
    vuln_types = [
        "sql_injection", "xss", "hardcoded_credentials", "path_traversal",
        "ssrf", "command_injection", "open_redirect", "insecure_deserialization",
        "xxe", "csrf",
    ]

    vulns = []
    for i, (severity, status, vtype) in enumerate(zip(severities, statuses, vuln_types)):
        v = MagicMock(spec=Vulnerability)
        v.id = uuid.UUID(f"eeeeeeee-eeee-eeee-eeee-{str(i).zfill(12)}")
        v.scan_job_id = sample_scan_job.id
        v.repo_id = sample_repo.id
        v.status = status
        v.severity = severity
        v.vulnerability_type = vtype
        v.cwe_id = f"CWE-{89 + i}"
        v.owasp_category = "A03:2021 - Injection"
        v.file_path = f"src/module_{i}/code.py"
        v.start_line = 10 + i * 5
        v.end_line = 12 + i * 5
        v.code_snippet = f"# 취약한 코드 예시 {i}"
        v.description = f"취약점 설명 {i}"
        v.llm_reasoning = f"LLM 분석 근거 {i}"
        v.llm_confidence = 0.90 - i * 0.02
        v.semgrep_rule_id = f"python.security.rule-{i}"
        v.references = [f"https://cwe.mitre.org/data/definitions/{89 + i}.html"]
        v.detected_at = datetime(2026, 2, 25, 10, i, 0)
        v.resolved_at = datetime(2026, 2, 25, 11, 0, 0) if status != "open" else None
        v.created_at = datetime(2026, 2, 25, 10, i, 0)
        v.patch_pr = None
        v.repository = sample_repo
        vulns.append(v)
    return vulns


@pytest.fixture
def dashboard_summary_data():
    """대시보드 요약 통계 픽스처.

    test_dashboard_api.py에서 기대값 검증에 사용한다.
    """
    return {
        "total_vulnerabilities": 42,
        "open_count": 15,
        "patched_count": 20,
        "ignored_count": 7,
        "critical_count": 3,
        "high_count": 8,
        "security_score": 72.5,
        "repos_count": 5,
        "recent_scans": [],
    }
