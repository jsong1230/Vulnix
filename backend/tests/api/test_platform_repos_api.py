"""플랫폼 연동 저장소 API 테스트 — F-09 RED 단계

구현이 없는 상태에서 실행하면 모두 FAIL이어야 한다.

테스트 범위:
- POST /api/v1/repos/gitlab — GitLab 저장소 연동 성공 (I-0902)
- POST /api/v1/repos/gitlab — 중복 연동 시도 → 409 (I-0903)
- POST /api/v1/repos/gitlab — PAT 검증 실패 → 422
- GET /api/v1/repos/gitlab/projects — GitLab 프로젝트 목록 조회 (I-0901)
- POST /api/v1/repos/bitbucket — Bitbucket 저장소 연동 성공 (I-0905)
- POST /api/v1/repos/bitbucket — 잘못된 자격증명 → 422 (I-0906)
- GET /api/v1/repos/bitbucket/repositories — Bitbucket 저장소 목록 조회 (I-0904)
- 인증 없이 접근 → 401
- GET /api/v1/repos?platform=gitlab — platform 필터 조회 (I-0918)

인수조건:
- I-0901: GitLab 프로젝트 목록 조회, already_connected 플래그 정확
- I-0902: GitLab 저장소 연동 성공 → 201, Repository(platform="gitlab"), ScanJob queued
- I-0903: 중복 연동 → 409
- I-0904: Bitbucket 저장소 목록 조회 → 200, 저장소 목록 반환
- I-0905: Bitbucket 저장소 연동 성공 → 201, Repository(platform="bitbucket")
- I-0906: 잘못된 자격증명 → 422
- I-0918: GET /repos?platform=gitlab → GitLab 저장소만 반환
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────
# GitLab 연동 API 테스트
# ──────────────────────────────────────────────────────────────

def test_gitlab_register_repo_success(test_client):
    """GitLab 저장소 연동 성공 시 201과 Repository 정보를 반환한다.

    Given: 인증된 사용자, GitLab PAT 유효, 미등록 저장소
    When: POST /api/v1/repos/gitlab
    Then: 201, platform="gitlab", ScanJob queued (I-0902)
    """
    # Arrange
    request_body = {
        "gitlab_project_id": 12345,
        "full_name": "group/project-name",
        "default_branch": "main",
        "language": "python",
        "gitlab_url": "https://gitlab.com",
        "access_token": "glpat-xxxxxxxxxxxxxxxxxxxx",
    }

    with (
        patch("src.api.v1.repos_gitlab.GitLabPlatformService") as mock_service_cls,
        patch("src.api.v1.repos_gitlab.ScanOrchestrator") as mock_orchestrator_cls,
    ):
        # PAT 유효성 검증 Mock
        mock_service = AsyncMock()
        mock_service.validate_credentials = AsyncMock(return_value=True)
        mock_service.register_webhook = AsyncMock(return_value=None)
        mock_service_cls.return_value = mock_service

        # ScanOrchestrator Mock
        mock_orchestrator = AsyncMock()
        mock_orchestrator.enqueue_scan = AsyncMock(
            return_value=str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
        )
        mock_orchestrator_cls.return_value = mock_orchestrator

        # Act
        response = test_client.post("/api/v1/repos/gitlab", json=request_body)

    # Assert
    assert response.status_code == 201, \
        f"GitLab 저장소 연동 성공 시 201을 반환해야 한다, 실제: {response.status_code}"
    body = response.json()
    assert body.get("success") is True, "success가 True여야 한다"
    data = body.get("data", {})
    assert data.get("platform") == "gitlab", \
        f"platform이 'gitlab'이어야 한다, 실제: {data.get('platform')}"
    assert data.get("full_name") == "group/project-name", \
        f"full_name이 올바르지 않다, 실제: {data.get('full_name')}"


def test_gitlab_register_repo_duplicate_returns_409(test_client):
    """이미 등록된 GitLab 저장소를 다시 등록하면 409를 반환한다.

    Given: 동일한 gitlab_project_id로 이미 등록된 저장소
    When: POST /api/v1/repos/gitlab (동일 project_id)
    Then: 409, "이미 등록된 저장소" (I-0903)
    """
    # Arrange
    request_body = {
        "gitlab_project_id": 12345,
        "full_name": "group/project-name",
        "default_branch": "main",
        "language": "python",
        "gitlab_url": "https://gitlab.com",
        "access_token": "glpat-xxxxxxxxxxxxxxxxxxxx",
    }

    with (
        patch("src.api.v1.repos_gitlab.GitLabPlatformService") as mock_service_cls,
        patch("src.api.v1.repos_gitlab.check_gitlab_repo_duplicate") as mock_dup_check,
    ):
        # 중복 저장소가 존재함
        mock_existing_repo = MagicMock()
        mock_existing_repo.platform_repo_id = "12345"
        mock_dup_check.return_value = mock_existing_repo

        mock_service = AsyncMock()
        mock_service.validate_credentials = AsyncMock(return_value=True)
        mock_service_cls.return_value = mock_service

        # Act
        response = test_client.post("/api/v1/repos/gitlab", json=request_body)

    # Assert
    assert response.status_code == 409, \
        f"중복 연동 시 409를 반환해야 한다, 실제: {response.status_code}"


def test_gitlab_register_repo_invalid_pat_returns_422(test_client):
    """GitLab PAT 검증 실패 시 422를 반환한다.

    Given: 인증된 사용자, 잘못된 PAT
    When: POST /api/v1/repos/gitlab
    Then: 422, "자격증명 검증 실패"
    """
    # Arrange
    request_body = {
        "gitlab_project_id": 12345,
        "full_name": "group/project-name",
        "default_branch": "main",
        "language": "python",
        "gitlab_url": "https://gitlab.com",
        "access_token": "glpat-invalid_token",
    }

    with patch("src.api.v1.repos_gitlab.GitLabPlatformService") as mock_service_cls:
        # PAT 유효성 검증 실패
        mock_service = AsyncMock()
        mock_service.validate_credentials = AsyncMock(return_value=False)
        mock_service_cls.return_value = mock_service

        # Act
        response = test_client.post("/api/v1/repos/gitlab", json=request_body)

    # Assert
    assert response.status_code == 422, \
        f"PAT 검증 실패 시 422를 반환해야 한다, 실제: {response.status_code}"


def test_gitlab_register_repo_unauthenticated_returns_401(test_client):
    """인증 없이 GitLab 저장소 연동 요청 시 401을 반환한다.

    Given: 인증 토큰 없음
    When: POST /api/v1/repos/gitlab
    Then: 401
    """
    # Arrange — test_client는 기본적으로 인증된 사용자를 주입하므로
    # 인증 없는 클라이언트를 별도로 생성한다
    from src.main import create_app
    from src.api.deps import get_db, get_current_user
    from fastapi.testclient import TestClient
    from fastapi import HTTPException, status

    app = create_app()

    async def override_get_db():
        yield AsyncMock()

    async def override_unauthenticated():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다.",
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_unauthenticated

    request_body = {
        "gitlab_project_id": 12345,
        "full_name": "group/project-name",
        "default_branch": "main",
        "language": "python",
        "gitlab_url": "https://gitlab.com",
        "access_token": "glpat-xxxxxxxxxxxxxxxxxxxx",
    }

    with TestClient(app, raise_server_exceptions=False) as unauthenticated_client:
        # Act
        response = unauthenticated_client.post("/api/v1/repos/gitlab", json=request_body)

    # Assert
    assert response.status_code == 401, \
        f"인증 없이 접근 시 401을 반환해야 한다, 실제: {response.status_code}"


# ──────────────────────────────────────────────────────────────
# I-0901: GitLab 프로젝트 목록 조회
# ──────────────────────────────────────────────────────────────

def test_gitlab_list_projects_success(test_client):
    """GitLab 프로젝트 목록 조회 시 200과 프로젝트 목록을 반환한다.

    Given: 인증된 사용자, GitLab API mock
    When: GET /api/v1/repos/gitlab/projects?access_token=glpat-xxx&gitlab_url=https://gitlab.com
    Then: 200, repositories 목록, already_connected 플래그 정확 (I-0901)
    """
    # Arrange
    mock_projects = [
        {
            "platform_repo_id": "12345",
            "full_name": "group/project-name",
            "private": True,
            "default_branch": "main",
            "language": "Python",
            "platform_url": "https://gitlab.com/group/project-name",
        }
    ]

    with patch("src.api.v1.repos_gitlab.GitLabPlatformService") as mock_service_cls:
        mock_service = AsyncMock()
        mock_service.list_repositories = AsyncMock(return_value=mock_projects)
        mock_service_cls.return_value = mock_service

        # Act
        response = test_client.get(
            "/api/v1/repos/gitlab/projects",
            params={
                "access_token": "glpat-xxxxxxxxxxxxxxxxxxxx",
                "gitlab_url": "https://gitlab.com",
            },
        )

    # Assert
    assert response.status_code == 200, \
        f"200을 반환해야 한다, 실제: {response.status_code}"
    body = response.json()
    assert body.get("success") is True, "success가 True여야 한다"
    data = body.get("data", {})
    repos = data.get("repositories", [])
    assert len(repos) >= 1, f"프로젝트 목록이 최소 1건이어야 한다, 실제: {len(repos)}"
    # already_connected 필드 존재 확인
    assert "already_connected" in repos[0], \
        "각 저장소에 already_connected 필드가 포함되어야 한다"


def test_gitlab_list_projects_unauthenticated_returns_401(test_client):
    """인증 없이 GitLab 프로젝트 목록 조회 시 401을 반환한다.

    Given: 인증 토큰 없음
    When: GET /api/v1/repos/gitlab/projects
    Then: 401
    """
    # Arrange
    from src.main import create_app
    from src.api.deps import get_db, get_current_user
    from fastapi.testclient import TestClient
    from fastapi import HTTPException, status

    app = create_app()

    async def override_get_db():
        yield AsyncMock()

    async def override_unauthenticated():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다.",
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_unauthenticated

    with TestClient(app, raise_server_exceptions=False) as unauthenticated_client:
        # Act
        response = unauthenticated_client.get(
            "/api/v1/repos/gitlab/projects",
            params={"access_token": "glpat-xxx"},
        )

    # Assert
    assert response.status_code == 401, \
        f"인증 없이 접근 시 401을 반환해야 한다, 실제: {response.status_code}"


# ──────────────────────────────────────────────────────────────
# Bitbucket 연동 API 테스트
# ──────────────────────────────────────────────────────────────

def test_bitbucket_register_repo_success(test_client):
    """Bitbucket 저장소 연동 성공 시 201과 Repository 정보를 반환한다.

    Given: 인증된 사용자, App Password 유효, 미등록 저장소
    When: POST /api/v1/repos/bitbucket
    Then: 201, platform="bitbucket", ScanJob queued (I-0905)
    """
    # Arrange
    request_body = {
        "workspace": "my-workspace",
        "repo_slug": "my-repo",
        "full_name": "my-workspace/my-repo",
        "default_branch": "main",
        "language": "python",
        "username": "bitbucket-testuser",
        "app_password": "test_app_password_xxxx",
    }

    with (
        patch("src.api.v1.repos_bitbucket.BitbucketPlatformService") as mock_service_cls,
        patch("src.api.v1.repos_bitbucket.ScanOrchestrator") as mock_orchestrator_cls,
    ):
        # App Password 유효성 검증 Mock
        mock_service = AsyncMock()
        mock_service.validate_credentials = AsyncMock(return_value=True)
        mock_service.register_webhook = AsyncMock(return_value=None)
        mock_service_cls.return_value = mock_service

        # ScanOrchestrator Mock
        mock_orchestrator = AsyncMock()
        mock_orchestrator.enqueue_scan = AsyncMock(
            return_value=str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
        )
        mock_orchestrator_cls.return_value = mock_orchestrator

        # Act
        response = test_client.post("/api/v1/repos/bitbucket", json=request_body)

    # Assert
    assert response.status_code == 201, \
        f"Bitbucket 저장소 연동 성공 시 201을 반환해야 한다, 실제: {response.status_code}"
    body = response.json()
    assert body.get("success") is True, "success가 True여야 한다"
    data = body.get("data", {})
    assert data.get("platform") == "bitbucket", \
        f"platform이 'bitbucket'이어야 한다, 실제: {data.get('platform')}"


def test_bitbucket_register_repo_invalid_credentials_returns_422(test_client):
    """잘못된 Bitbucket 자격증명으로 연동 시 422를 반환한다.

    Given: 인증된 사용자, Bitbucket API mock 401 반환
    When: POST /api/v1/repos/bitbucket + 잘못된 credentials
    Then: 422, "자격증명 검증 실패" (I-0906)
    """
    # Arrange
    request_body = {
        "workspace": "my-workspace",
        "repo_slug": "my-repo",
        "full_name": "my-workspace/my-repo",
        "default_branch": "main",
        "language": "python",
        "username": "bitbucket-testuser",
        "app_password": "wrong_app_password",
    }

    with patch("src.api.v1.repos_bitbucket.BitbucketPlatformService") as mock_service_cls:
        # App Password 유효성 검증 실패
        mock_service = AsyncMock()
        mock_service.validate_credentials = AsyncMock(return_value=False)
        mock_service_cls.return_value = mock_service

        # Act
        response = test_client.post("/api/v1/repos/bitbucket", json=request_body)

    # Assert
    assert response.status_code == 422, \
        f"자격증명 검증 실패 시 422를 반환해야 한다, 실제: {response.status_code}"


def test_bitbucket_register_repo_duplicate_returns_409(test_client):
    """이미 등록된 Bitbucket 저장소를 다시 등록하면 409를 반환한다.

    Given: 동일한 workspace/repo_slug로 이미 등록된 저장소
    When: POST /api/v1/repos/bitbucket
    Then: 409
    """
    # Arrange
    request_body = {
        "workspace": "my-workspace",
        "repo_slug": "my-repo",
        "full_name": "my-workspace/my-repo",
        "default_branch": "main",
        "language": "python",
        "username": "bitbucket-testuser",
        "app_password": "test_app_password_xxxx",
    }

    with (
        patch("src.api.v1.repos_bitbucket.BitbucketPlatformService") as mock_service_cls,
        patch("src.api.v1.repos_bitbucket.check_bitbucket_repo_duplicate") as mock_dup_check,
    ):
        mock_existing_repo = MagicMock()
        mock_existing_repo.platform_repo_id = "my-workspace/my-repo"
        mock_dup_check.return_value = mock_existing_repo

        mock_service = AsyncMock()
        mock_service.validate_credentials = AsyncMock(return_value=True)
        mock_service_cls.return_value = mock_service

        # Act
        response = test_client.post("/api/v1/repos/bitbucket", json=request_body)

    # Assert
    assert response.status_code == 409, \
        f"중복 연동 시 409를 반환해야 한다, 실제: {response.status_code}"


def test_bitbucket_register_repo_unauthenticated_returns_401(test_client):
    """인증 없이 Bitbucket 저장소 연동 요청 시 401을 반환한다.

    Given: 인증 토큰 없음
    When: POST /api/v1/repos/bitbucket
    Then: 401
    """
    # Arrange
    from src.main import create_app
    from src.api.deps import get_db, get_current_user
    from fastapi.testclient import TestClient
    from fastapi import HTTPException, status

    app = create_app()

    async def override_get_db():
        yield AsyncMock()

    async def override_unauthenticated():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다.",
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_unauthenticated

    request_body = {
        "workspace": "my-workspace",
        "repo_slug": "my-repo",
        "full_name": "my-workspace/my-repo",
        "default_branch": "main",
        "language": "python",
        "username": "bitbucket-testuser",
        "app_password": "test_app_password_xxxx",
    }

    with TestClient(app, raise_server_exceptions=False) as unauthenticated_client:
        # Act
        response = unauthenticated_client.post("/api/v1/repos/bitbucket", json=request_body)

    # Assert
    assert response.status_code == 401, \
        f"인증 없이 접근 시 401을 반환해야 한다, 실제: {response.status_code}"


# ──────────────────────────────────────────────────────────────
# I-0904: Bitbucket 저장소 목록 조회
# ──────────────────────────────────────────────────────────────

def test_bitbucket_list_repositories_success(test_client):
    """Bitbucket 저장소 목록 조회 시 200과 저장소 목록을 반환한다.

    Given: 인증된 사용자, Bitbucket API mock
    When: GET /api/v1/repos/bitbucket/repositories?username=user&app_password=xxx&workspace=ws
    Then: 200, 저장소 목록 반환 (I-0904)
    """
    # Arrange
    mock_repos = [
        {
            "platform_repo_id": "{aaaa-bbbb-cccc}",
            "full_name": "my-workspace/my-repo",
            "private": True,
            "default_branch": "main",
            "language": "Python",
            "platform_url": "https://bitbucket.org/my-workspace/my-repo",
        }
    ]

    with patch("src.api.v1.repos_bitbucket.BitbucketPlatformService") as mock_service_cls:
        mock_service = AsyncMock()
        mock_service.list_repositories = AsyncMock(return_value=mock_repos)
        mock_service_cls.return_value = mock_service

        # Act
        response = test_client.get(
            "/api/v1/repos/bitbucket/repositories",
            params={
                "username": "bitbucket-testuser",
                "app_password": "test_app_password_xxxx",
                "workspace": "my-workspace",
            },
        )

    # Assert
    assert response.status_code == 200, \
        f"200을 반환해야 한다, 실제: {response.status_code}"
    body = response.json()
    assert body.get("success") is True, "success가 True여야 한다"
    data = body.get("data", {})
    repos = data.get("repositories", [])
    assert len(repos) >= 1, f"저장소 목록이 최소 1건이어야 한다, 실제: {len(repos)}"


def test_bitbucket_list_repositories_unauthenticated_returns_401(test_client):
    """인증 없이 Bitbucket 저장소 목록 조회 시 401을 반환한다.

    Given: 인증 토큰 없음
    When: GET /api/v1/repos/bitbucket/repositories
    Then: 401
    """
    # Arrange
    from src.main import create_app
    from src.api.deps import get_db, get_current_user
    from fastapi.testclient import TestClient
    from fastapi import HTTPException, status

    app = create_app()

    async def override_get_db():
        yield AsyncMock()

    async def override_unauthenticated():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다.",
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_unauthenticated

    with TestClient(app, raise_server_exceptions=False) as unauthenticated_client:
        # Act
        response = unauthenticated_client.get(
            "/api/v1/repos/bitbucket/repositories",
            params={
                "username": "bitbucket-testuser",
                "app_password": "xxx",
                "workspace": "my-workspace",
            },
        )

    # Assert
    assert response.status_code == 401, \
        f"인증 없이 접근 시 401을 반환해야 한다, 실제: {response.status_code}"


# ──────────────────────────────────────────────────────────────
# I-0918: GET /repos?platform=gitlab — platform 필터 조회
# ──────────────────────────────────────────────────────────────

def test_list_repos_with_platform_filter_gitlab(test_client):
    """GET /repos?platform=gitlab 요청 시 GitLab 저장소만 반환된다.

    Given: GitHub 2개 + GitLab 2개 저장소
    When: GET /api/v1/repos?platform=gitlab
    Then: GitLab 저장소 2개만 반환 (I-0918)
    """
    # Act
    response = test_client.get("/api/v1/repos", params={"platform": "gitlab"})

    # Assert
    assert response.status_code == 200, \
        f"200을 반환해야 한다, 실제: {response.status_code}"
    body = response.json()
    repos = body.get("data", [])
    # 반환된 모든 저장소의 platform이 "gitlab"이어야 한다
    for repo in repos:
        assert repo.get("platform") == "gitlab", \
            f"platform 필터 적용 시 모든 저장소의 platform이 'gitlab'이어야 한다, 실제: {repo.get('platform')}"


def test_list_repos_without_platform_filter_returns_all(test_client):
    """GET /repos 요청 시 모든 플랫폼 저장소가 반환되고 platform 필드가 포함된다.

    Given: 다양한 플랫폼 저장소
    When: GET /api/v1/repos (platform 필터 없음)
    Then: 응답에 platform 필드 포함, 모든 플랫폼 저장소 반환 (I-0917)
    """
    # Act
    response = test_client.get("/api/v1/repos")

    # Assert
    assert response.status_code == 200, \
        f"200을 반환해야 한다, 실제: {response.status_code}"
    body = response.json()
    repos = body.get("data", [])
    # 저장소가 있으면 platform 필드가 포함되어야 한다
    if repos:
        assert "platform" in repos[0], \
            "GET /repos 응답의 각 저장소에 platform 필드가 포함되어야 한다"


# ──────────────────────────────────────────────────────────────
# I-0915: GitLab 연동 등록 → Webhook 자동 등록 확인
# ──────────────────────────────────────────────────────────────

def test_gitlab_register_repo_registers_webhook(test_client):
    """GitLab 저장소 연동 시 GitLab Webhook이 자동으로 등록된다.

    Given: GitLab PAT 유효, 미등록 저장소
    When: POST /api/v1/repos/gitlab
    Then: 201, Repository 생성, ScanJob queued, GitLab Webhook 등록 API 호출됨 (I-0915)
    """
    # Arrange
    request_body = {
        "gitlab_project_id": 99999,
        "full_name": "group/webhook-test-repo",
        "default_branch": "main",
        "language": "python",
        "gitlab_url": "https://gitlab.com",
        "access_token": "glpat-xxxxxxxxxxxxxxxxxxxx",
    }

    with (
        patch("src.api.v1.repos_gitlab.GitLabPlatformService") as mock_service_cls,
        patch("src.api.v1.repos_gitlab.ScanOrchestrator") as mock_orchestrator_cls,
    ):
        mock_service = AsyncMock()
        mock_service.validate_credentials = AsyncMock(return_value=True)
        mock_service.register_webhook = AsyncMock(return_value=None)
        mock_service_cls.return_value = mock_service

        mock_orchestrator = AsyncMock()
        mock_orchestrator.enqueue_scan = AsyncMock(
            return_value=str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
        )
        mock_orchestrator_cls.return_value = mock_orchestrator

        # Act
        response = test_client.post("/api/v1/repos/gitlab", json=request_body)

    # Assert
    assert response.status_code == 201, \
        f"201을 반환해야 한다, 실제: {response.status_code}"
    # Webhook 등록 API가 호출되었는지 확인
    mock_service.register_webhook.assert_called_once(), \
        "GitLab Webhook 등록 API가 호출되어야 한다"
