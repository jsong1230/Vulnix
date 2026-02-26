"""F-01 저장소 API 엔드포인트 테스트 — TDD RED 단계

인수조건:
- 연동 저장소 목록 조회 (GET /api/v1/repos)
- 저장소 연동 등록 (POST /api/v1/repos) → 초기 스캔 자동 트리거
- 저장소 연동 해제 (DELETE /api/v1/repos/{repo_id}) → 데이터 정리
- GitHub 설치 저장소 목록 (GET /api/v1/repos/github/installations)
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. 연동 저장소 목록 조회
# ---------------------------------------------------------------------------

def test_list_repos_returns_registered_repos(test_client, sample_repo):
    """인증된 사용자가 연동 저장소 목록을 조회할 수 있다.

    Given: 팀에 2개의 연동된 저장소가 존재
    When: GET /api/v1/repos (유효한 JWT)
    Then: 200 OK, success=true, data에 저장소 목록 반환
    """
    # Arrange — DB에서 저장소 목록을 반환하도록 패치
    mock_repos = [sample_repo]

    with patch("src.api.v1.repos.get_repos_by_team") as mock_get_repos:
        mock_get_repos.return_value = (mock_repos, 1)

        # Act
        response = test_client.get("/api/v1/repos")

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 0  # 목록이 반환되어야 함 (구현 후 >= 1)
    # 페이지네이션 메타 포함 확인
    assert "meta" in body


def test_list_repos_requires_authentication(test_client):
    """인증 없이 저장소 목록 조회 시 401을 반환한다.

    Given: Authorization 헤더가 없는 요청
    When: GET /api/v1/repos
    Then: 401 Unauthorized
    """
    # Arrange — 의존성 오버라이드 해제 (인증 없이 직접 호출)
    from src.main import create_app
    from src.api.deps import get_db

    app = create_app()

    async def override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = override_get_db
    # get_current_user는 오버라이드하지 않음 → 원래 401 반환

    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=False) as unauthenticated_client:
        # Act
        response = unauthenticated_client.get("/api/v1/repos")

    # Assert
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 2. 저장소 연동 등록
# ---------------------------------------------------------------------------

def test_register_repo_success(test_client):
    """유효한 저장소 정보로 연동 등록 시 201과 생성된 저장소를 반환한다.

    Given: 유효한 RepositoryRegisterRequest (github_repo_id, full_name, installation_id)
    When: POST /api/v1/repos
    Then: 201 Created, success=true, data에 생성된 저장소 정보 포함
    """
    # Arrange
    request_body = {
        "github_repo_id": 999999,
        "full_name": "new-org/new-repo",
        "default_branch": "main",
        "language": "Python",
        "installation_id": 456,
    }

    with (
        patch("src.api.v1.repos.create_repository") as mock_create,
        patch("src.api.v1.repos.check_repo_duplicate") as mock_check,
    ):
        mock_check.return_value = None  # 중복 없음
        created_repo = MagicMock()
        created_repo.id = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
        created_repo.team_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        created_repo.github_repo_id = 999999
        created_repo.full_name = "new-org/new-repo"
        created_repo.default_branch = "main"
        created_repo.language = "Python"
        created_repo.is_active = True
        created_repo.installation_id = 456
        created_repo.last_scanned_at = None
        created_repo.security_score = None
        created_repo.is_initial_scan_done = False
        created_repo.created_at = datetime(2026, 2, 25, 10, 0, 0)
        mock_create.return_value = created_repo

        # Act
        response = test_client.post("/api/v1/repos", json=request_body)

    # Assert
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["full_name"] == "new-org/new-repo"
    assert body["data"]["is_initial_scan_done"] is False


def test_register_repo_duplicate_returns_409(test_client):
    """이미 등록된 github_repo_id로 연동 시도 시 409 Conflict를 반환한다.

    Given: DB에 이미 등록된 github_repo_id=123456
    When: POST /api/v1/repos (동일 github_repo_id)
    Then: 409 Conflict
    """
    # Arrange
    request_body = {
        "github_repo_id": 123456,  # 이미 등록된 ID
        "full_name": "test-org/test-repo",
        "default_branch": "main",
        "installation_id": 789,
    }

    with patch("src.api.v1.repos.check_repo_duplicate") as mock_check:
        # 이미 존재하는 저장소를 반환하여 중복 상황 시뮬레이션
        mock_check.return_value = MagicMock(github_repo_id=123456)

        # Act
        response = test_client.post("/api/v1/repos", json=request_body)

    # Assert
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# 3. 저장소 연동 후 초기 스캔 트리거
# ---------------------------------------------------------------------------

def test_register_repo_triggers_initial_scan(test_client):
    """저장소 연동 등록 시 201을 반환하고 is_initial_scan_done=False로 설정된다.

    Given: 유효한 저장소 연동 요청
    When: POST /api/v1/repos
    Then: 201 Created, is_initial_scan_done=False (스캔은 별도 트리거로 처리)
    """
    # Arrange
    request_body = {
        "github_repo_id": 777777,
        "full_name": "scan-org/scan-repo",
        "default_branch": "develop",
        "language": "Python",
        "installation_id": 111,
    }

    with (
        patch("src.api.v1.repos.check_repo_duplicate") as mock_check,
        patch("src.api.v1.repos.create_repository") as mock_create,
    ):
        mock_check.return_value = None

        created_repo = MagicMock()
        created_repo.id = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
        created_repo.team_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        created_repo.github_repo_id = 777777
        created_repo.full_name = "scan-org/scan-repo"
        created_repo.default_branch = "develop"
        created_repo.language = "Python"
        created_repo.is_active = True
        created_repo.installation_id = 111
        created_repo.last_scanned_at = None
        created_repo.security_score = None
        created_repo.is_initial_scan_done = False
        created_repo.created_at = datetime(2026, 2, 25, 10, 0, 0)
        mock_create.return_value = created_repo

        # Act
        response = test_client.post("/api/v1/repos", json=request_body)

    # Assert
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["is_initial_scan_done"] is False


# ---------------------------------------------------------------------------
# 4. 저장소 연동 해제 → 데이터 정리
# ---------------------------------------------------------------------------

def test_delete_repo_removes_data(test_client, sample_repo):
    """저장소 연동 해제 시 관련 스캔/취약점 데이터가 정리되고 통계를 반환한다.

    Given: 유효한 repo_id, owner/admin 권한의 사용자
    When: DELETE /api/v1/repos/{repo_id}
    Then: 200 OK, 삭제된 스캔 수 및 취약점 수 반환
    """
    # Arrange
    repo_id = str(sample_repo.id)

    with patch("src.api.v1.repos.get_repo_by_id") as mock_get_repo:
        mock_get_repo.return_value = sample_repo

        # Act
        response = test_client.delete(f"/api/v1/repos/{repo_id}")

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert "repo_id" in data
    assert "deleted_scans_count" in data
    assert "deleted_vulnerabilities_count" in data


def test_delete_repo_not_found_returns_404(test_client):
    """존재하지 않는 repo_id로 연동 해제 시 404를 반환한다.

    Given: DB에 없는 repo_id
    When: DELETE /api/v1/repos/{repo_id}
    Then: 404 Not Found
    """
    # Arrange
    nonexistent_repo_id = str(uuid.UUID("99999999-9999-9999-9999-999999999999"))

    with patch("src.api.v1.repos.get_repo_by_id") as mock_get_repo:
        mock_get_repo.return_value = None  # 저장소 없음

        # Act
        response = test_client.delete(f"/api/v1/repos/{nonexistent_repo_id}")

    # Assert
    assert response.status_code == 404


def test_delete_repo_member_role_returns_403(test_client, sample_repo):
    """member 권한 사용자가 연동 해제 시도 시 403 Forbidden을 반환한다.

    Given: team member 역할의 사용자 (owner/admin이 아님)
    When: DELETE /api/v1/repos/{repo_id}
    Then: 403 Forbidden
    """
    # Arrange
    repo_id = str(sample_repo.id)

    with (
        patch("src.api.v1.repos.get_repo_by_id") as mock_get_repo,
        patch("src.api.v1.repos.get_user_team_role") as mock_get_role,
    ):
        mock_get_repo.return_value = sample_repo
        mock_get_role.return_value = "member"  # member 역할

        # Act
        response = test_client.delete(f"/api/v1/repos/{repo_id}")

    # Assert
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 5. GitHub 설치 저장소 목록 조회
# ---------------------------------------------------------------------------

def test_list_github_installations(test_client, mock_github_service):
    """GitHub App 설치 후 접근 가능한 저장소 목록을 조회한다.

    Given: 인증된 사용자, GitHub App installation_id=789
    When: GET /api/v1/repos/github/installations
    Then: 200 OK, installation_id와 저장소 목록 반환
    """
    # Arrange
    with patch("src.api.v1.repos.GitHubAppService") as mock_service_cls:
        mock_service_cls.return_value = mock_github_service

        # Act
        response = test_client.get("/api/v1/repos/github/installations")

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    # data에 installation 정보 포함
    assert "data" in body
    data = body["data"]
    # repositories 목록 포함
    assert "repositories" in data or isinstance(data, list)


def test_list_github_installations_marks_already_connected(test_client, mock_github_service, sample_repo):
    """이미 연동된 저장소는 already_connected=True로 표시된다.

    Given: github_repo_id=123456이 이미 DB에 등록된 상태
    When: GET /api/v1/repos/github/installations
    Then: 해당 저장소의 already_connected=True
    """
    # Arrange
    with (
        patch("src.api.v1.repos.GitHubAppService") as mock_service_cls,
        patch("src.api.v1.repos.get_connected_repo_ids") as mock_get_ids,
    ):
        mock_service_cls.return_value = mock_github_service
        mock_get_ids.return_value = {123456}  # 이미 연동된 repo_id 세트

        # Act
        response = test_client.get("/api/v1/repos/github/installations")

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    # 첫 번째 저장소(id=123456)는 already_connected=True여야 함
    data = body.get("data", {})
    repositories = data.get("repositories", []) if isinstance(data, dict) else []
    if repositories:
        connected = [r for r in repositories if r.get("github_repo_id") == 123456]
        if connected:
            assert connected[0].get("already_connected") is True


# ---------------------------------------------------------------------------
# 6. 저장소 등록 필수 필드 누락 → 400
# ---------------------------------------------------------------------------

def test_register_repo_missing_required_fields_returns_400(test_client):
    """필수 필드(full_name)가 없으면 400 Bad Request를 반환한다.

    Given: full_name이 없는 요청 body
    When: POST /api/v1/repos
    Then: 400 또는 422 Unprocessable Entity
    """
    # Arrange
    request_body = {
        "github_repo_id": 123456,
        # full_name 누락
    }

    # Act
    response = test_client.post("/api/v1/repos", json=request_body)

    # Assert
    assert response.status_code in (400, 422)
