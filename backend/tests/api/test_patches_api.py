"""패치 PR API 통합 테스트 — F-03 RED 단계

GET /api/v1/patches       -- 패치 PR 목록 조회
GET /api/v1/patches/{id}  -- 패치 PR 상세 조회

구현이 완료되지 않은 상태에서 실행하면 모두 FAIL이어야 한다.
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ──────────────────────────────────────────────────────────────
# 환경변수 설정 (모듈 임포트 전)
# ──────────────────────────────────────────────────────────────

import os

_TEST_ENV = {
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

for _key, _val in _TEST_ENV.items():
    os.environ.setdefault(_key, _val)


# ──────────────────────────────────────────────────────────────
# 픽스처
# ──────────────────────────────────────────────────────────────

TEAM_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
REPO_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
VULN_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
PATCH_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
OTHER_PATCH_ID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")


@pytest.fixture
def sample_patch_pr_data():
    """PatchPR 응답 데이터 픽스처."""
    return {
        "id": str(PATCH_ID),
        "vulnerability_id": str(VULN_ID),
        "repo_id": str(REPO_ID),
        "github_pr_number": 42,
        "github_pr_url": "https://github.com/test-org/test-repo/pull/42",
        "branch_name": "vulnix/fix-sql-injection-a1b2c3d",
        "status": "created",
        "patch_diff": '--- a/app/db.py\n+++ b/app/db.py\n@@ -5,1 +5,2 @@',
        "patch_description": "f-string SQL 쿼리를 파라미터화된 쿼리로 변경",
        "created_at": "2026-02-25T10:30:00Z",
        "merged_at": None,
    }


@pytest.fixture
def mock_patch_pr_orm():
    """PatchPR ORM 객체 픽스처."""
    from src.models.patch_pr import PatchPR

    patch_pr = MagicMock(spec=PatchPR)
    patch_pr.id = PATCH_ID
    patch_pr.vulnerability_id = VULN_ID
    patch_pr.repo_id = REPO_ID
    patch_pr.github_pr_number = 42
    patch_pr.github_pr_url = "https://github.com/test-org/test-repo/pull/42"
    patch_pr.branch_name = "vulnix/fix-sql-injection-a1b2c3d"
    patch_pr.status = "created"
    patch_pr.patch_diff = '--- a/app/db.py\n+++ b/app/db.py\n@@ -5,1 +5,2 @@'
    patch_pr.patch_description = "f-string SQL 쿼리를 파라미터화된 쿼리로 변경"
    patch_pr.created_at = datetime(2026, 2, 25, 10, 30, 0)
    patch_pr.merged_at = None

    # 연관된 vulnerability mock
    mock_vuln = MagicMock()
    mock_vuln.id = VULN_ID
    mock_vuln.status = "patched"
    mock_vuln.severity = "high"
    mock_vuln.vulnerability_type = "sql_injection"
    mock_vuln.file_path = "app/db.py"
    mock_vuln.start_line = 5
    mock_vuln.detected_at = datetime(2026, 2, 25, 10, 0, 0)
    mock_vuln.created_at = datetime(2026, 2, 25, 10, 0, 0)
    patch_pr.vulnerability = mock_vuln

    return patch_pr


@pytest.fixture
def authenticated_client(mock_patch_pr_orm):
    """인증된 TestClient 픽스처.

    현재 사용자와 DB 세션을 mock으로 오버라이드한다.
    """
    from src.main import create_app
    from src.api.deps import get_db, get_current_user

    app = create_app()

    # 현재 사용자 Mock (인증됨)
    mock_user = MagicMock()
    mock_user.id = USER_ID
    mock_user.github_login = "test_user"
    mock_user.team_id = TEAM_ID

    async def override_get_current_user():
        return mock_user

    # DB 세션 Mock (PatchPR 목록/상세 반환)
    mock_db = AsyncMock()

    # 팀 소속 repo_id 목록 반환 mock
    mock_repo_result = MagicMock()
    mock_repo_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[REPO_ID])))

    # PatchPR 목록 반환 mock
    mock_patch_result = MagicMock()
    mock_patch_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[mock_patch_pr_orm]))
    )

    # count 반환 mock
    mock_count_result = MagicMock()
    mock_count_result.scalar_one = MagicMock(return_value=1)

    # 상세 조회 mock
    mock_detail_result = MagicMock()
    mock_detail_result.scalar_one_or_none = MagicMock(return_value=mock_patch_pr_orm)

    mock_db.execute = AsyncMock(side_effect=[
        mock_repo_result,
        mock_count_result,
        mock_patch_result,
    ])

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def unauthenticated_client():
    """미인증 TestClient 픽스처.

    get_current_user가 401 Unauthorized를 반환하도록 설정한다.
    """
    from src.main import create_app
    from src.api.deps import get_db, get_current_user
    from fastapi import HTTPException

    app = create_app()

    async def override_get_current_user():
        raise HTTPException(status_code=401, detail="Not authenticated")

    mock_db = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


# ──────────────────────────────────────────────────────────────
# GET /api/v1/patches 테스트
# ──────────────────────────────────────────────────────────────

def test_list_patches_returns_list(authenticated_client):
    """인증된 사용자가 패치 PR 목록을 조회할 수 있는지 검증한다."""
    # Act
    response = authenticated_client.get("/api/v1/patches")

    # Assert
    assert response.status_code == 200, \
        f"200 OK를 기대했지만 {response.status_code} 반환. 응답: {response.text[:200]}"

    data = response.json()
    assert data.get("success") is True, \
        f"success가 True여야 함: {data}"
    assert "data" in data, "응답에 'data' 키가 없음"
    assert isinstance(data["data"], list), \
        f"data가 list여야 함: {type(data['data'])}"


def test_list_patches_response_structure(authenticated_client):
    """패치 PR 목록 응답 구조가 올바른지 검증한다 (PaginatedResponse 형식)."""
    # Act
    response = authenticated_client.get("/api/v1/patches")

    # Assert
    assert response.status_code == 200
    data = response.json()

    # 페이지네이션 메타 확인
    assert "meta" in data, "응답에 'meta' 키가 없음"
    meta = data["meta"]
    assert "page" in meta, "meta에 'page' 키가 없음"
    assert "per_page" in meta, "meta에 'per_page' 키가 없음"
    assert "total" in meta, "meta에 'total' 키가 없음"
    assert "total_pages" in meta, "meta에 'total_pages' 키가 없음"


def test_list_patches_item_structure(authenticated_client):
    """패치 PR 목록 각 항목의 필드 구조가 올바른지 검증한다."""
    # Act
    response = authenticated_client.get("/api/v1/patches")

    # Assert
    assert response.status_code == 200
    data = response.json()
    items = data.get("data", [])

    if len(items) > 0:
        item = items[0]
        required_fields = [
            "id", "vulnerability_id", "repo_id",
            "github_pr_number", "github_pr_url",
            "branch_name", "status", "patch_diff",
            "patch_description", "created_at",
        ]
        for field in required_fields:
            assert field in item, f"응답 항목에 '{field}' 필드가 없음"


def test_list_patches_requires_auth(unauthenticated_client):
    """미인증 요청 시 401이 반환되는지 검증한다."""
    # Act
    response = unauthenticated_client.get("/api/v1/patches")

    # Assert
    assert response.status_code == 401, \
        f"401 Unauthorized를 기대했지만 {response.status_code} 반환"


def test_list_patches_default_pagination(authenticated_client):
    """기본 페이지네이션 파라미터(page=1, per_page=20)가 적용되는지 검증한다."""
    # Act
    response = authenticated_client.get("/api/v1/patches")

    # Assert
    assert response.status_code == 200
    data = response.json()
    meta = data.get("meta", {})
    assert meta.get("page") == 1, \
        f"기본 page는 1이어야 함, 실제: {meta.get('page')}"
    assert meta.get("per_page") == 20, \
        f"기본 per_page는 20이어야 함, 실제: {meta.get('per_page')}"


# ──────────────────────────────────────────────────────────────
# GET /api/v1/patches/{id} 테스트
# ──────────────────────────────────────────────────────────────

def test_get_patch_detail(mock_patch_pr_orm):
    """패치 PR 상세 조회가 취약점 정보를 포함하여 반환되는지 검증한다."""
    from src.main import create_app
    from src.api.deps import get_db, get_current_user

    app = create_app()

    mock_user = MagicMock()
    mock_user.id = USER_ID
    mock_user.team_id = TEAM_ID

    async def override_get_current_user():
        return mock_user

    mock_db = AsyncMock()

    # 팀 소속 repo_id 확인 mock
    mock_repo_result = MagicMock()
    mock_repo_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[REPO_ID]))
    )

    # PatchPR 상세 조회 mock
    mock_detail_result = MagicMock()
    mock_detail_result.scalar_one_or_none = MagicMock(return_value=mock_patch_pr_orm)

    mock_db.execute = AsyncMock(side_effect=[mock_repo_result, mock_detail_result])

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    # Act
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(f"/api/v1/patches/{PATCH_ID}")

    # Assert
    assert response.status_code == 200, \
        f"200 OK를 기대했지만 {response.status_code} 반환. 응답: {response.text[:200]}"

    data = response.json()
    assert data.get("success") is True
    patch_data = data.get("data", {})
    assert str(patch_data.get("id")) == str(PATCH_ID), \
        f"patch ID가 올바르지 않음: {patch_data.get('id')}"
    # 취약점 정보 포함 확인
    assert "vulnerability" in patch_data, \
        "상세 응답에 'vulnerability' 필드가 없음"
    vuln_data = patch_data.get("vulnerability", {})
    assert vuln_data is not None, "vulnerability 정보가 None임"


def test_get_patch_not_found():
    """존재하지 않는 patch_id 조회 시 404가 반환되는지 검증한다."""
    from src.main import create_app
    from src.api.deps import get_db, get_current_user

    app = create_app()

    mock_user = MagicMock()
    mock_user.id = USER_ID
    mock_user.team_id = TEAM_ID

    async def override_get_current_user():
        return mock_user

    mock_db = AsyncMock()

    # 팀 소속 repo_id mock
    mock_repo_result = MagicMock()
    mock_repo_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[REPO_ID]))
    )

    # PatchPR 조회 결과: None (존재하지 않음)
    mock_detail_result = MagicMock()
    mock_detail_result.scalar_one_or_none = MagicMock(return_value=None)

    mock_db.execute = AsyncMock(side_effect=[mock_repo_result, mock_detail_result])

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    nonexistent_id = uuid.UUID("99999999-9999-9999-9999-999999999999")

    # Act
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(f"/api/v1/patches/{nonexistent_id}")

    # Assert
    assert response.status_code == 404, \
        f"404 Not Found를 기대했지만 {response.status_code} 반환"


def test_get_patch_detail_requires_auth():
    """미인증 요청 시 패치 상세 조회에서 401이 반환되는지 검증한다."""
    from src.main import create_app
    from src.api.deps import get_db, get_current_user
    from fastapi import HTTPException

    app = create_app()

    async def override_get_current_user():
        raise HTTPException(status_code=401, detail="Not authenticated")

    mock_db = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    # Act
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(f"/api/v1/patches/{PATCH_ID}")

    # Assert
    assert response.status_code == 401, \
        f"401 Unauthorized를 기대했지만 {response.status_code} 반환"


def test_get_patch_other_team_forbidden():
    """다른 팀 소속 patch_id 조회 시 403이 반환되는지 검증한다."""
    from src.main import create_app
    from src.api.deps import get_db, get_current_user

    app = create_app()

    mock_user = MagicMock()
    mock_user.id = USER_ID
    mock_user.team_id = TEAM_ID

    async def override_get_current_user():
        return mock_user

    mock_db = AsyncMock()

    # 현재 팀에는 OTHER_PATCH_ID의 repo가 없음 -> 빈 목록
    mock_repo_result = MagicMock()
    mock_repo_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[]))
    )

    # PatchPR은 다른 팀의 것 (repo_id 불일치)
    other_patch = MagicMock()
    other_patch.id = OTHER_PATCH_ID
    other_patch.repo_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

    mock_detail_result = MagicMock()
    mock_detail_result.scalar_one_or_none = MagicMock(return_value=other_patch)

    mock_db.execute = AsyncMock(side_effect=[mock_repo_result, mock_detail_result])

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    # Act
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(f"/api/v1/patches/{OTHER_PATCH_ID}")

    # Assert
    assert response.status_code == 403, \
        f"403 Forbidden을 기대했지만 {response.status_code} 반환"
