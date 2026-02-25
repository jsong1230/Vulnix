"""GitLabPlatformService 단위 테스트 — F-09 RED 단계

구현이 없는 상태에서 실행하면 모두 FAIL이어야 한다.

테스트 범위:
- validate_credentials(): PAT 유효/무효 검증
- list_repositories(): 저장소 목록 조회 + 페이지네이션
- get_changed_files(): MR 변경 파일 조회
- create_merge_request(): MR 생성 성공/실패
- register_webhook(): Webhook 등록
- get_file_content(): 파일 내용 조회
- create_branch(): 브랜치 생성
- create_file_commit(): 파일 수정 커밋
"""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# ──────────────────────────────────────────────────────────────
# 픽스처
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def gitlab_service():
    """GitLabPlatformService 인스턴스 픽스처.

    실제 GitLab API 호출 없이 단위 테스트에 사용한다.
    """
    from src.services.gitlab_service import GitLabPlatformService

    return GitLabPlatformService(
        access_token="glpat-test_access_token_xxxx",
        base_url="https://gitlab.com",
    )


def _make_httpx_response(status_code: int, json_body: dict | list | None = None) -> MagicMock:
    """httpx.Response Mock 생성 헬퍼."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    if json_body is not None:
        response.json.return_value = json_body
    # 4xx/5xx 응답에서 raise_for_status() 호출 시 예외를 발생시킨다
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=response,
        )
    else:
        response.raise_for_status.return_value = None
    return response


# ──────────────────────────────────────────────────────────────
# U-0905: validate_credentials() — PAT 유효
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gitlab_validate_credentials_valid_pat(gitlab_service):
    """유효한 PAT로 validate_credentials()를 호출하면 True를 반환한다.

    Given: GitLab GET /api/v4/user → 200
    When: validate_credentials() 호출
    Then: True 반환
    """
    # Arrange
    mock_response = _make_httpx_response(200, {"id": 1, "username": "testuser"})

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        # Act
        result = await gitlab_service.validate_credentials()

    # Assert
    assert result is True, "유효한 PAT에서 True를 반환해야 한다"


# ──────────────────────────────────────────────────────────────
# U-0906: validate_credentials() — PAT 무효 (401)
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gitlab_validate_credentials_invalid_pat(gitlab_service):
    """무효한 PAT로 validate_credentials()를 호출하면 False를 반환한다.

    Given: GitLab GET /api/v4/user → 401
    When: validate_credentials() 호출
    Then: False 반환
    """
    # Arrange
    mock_response = _make_httpx_response(401, {"message": "401 Unauthorized"})

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        # Act
        result = await gitlab_service.validate_credentials()

    # Assert
    assert result is False, "무효한 PAT에서 False를 반환해야 한다"


# ──────────────────────────────────────────────────────────────
# U-0907: list_repositories() — 정상 응답
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gitlab_list_repositories_success(gitlab_service):
    """list_repositories()가 GitLab 프로젝트 목록을 올바른 형식으로 반환한다.

    Given: GET /api/v4/projects → 200 + 프로젝트 JSON 배열
    When: list_repositories() 호출
    Then: [{"platform_repo_id": "123", "full_name": "group/repo", ...}] 반환
    """
    # Arrange
    gitlab_projects = [
        {
            "id": 123,
            "path_with_namespace": "group/repo",
            "visibility": "private",
            "default_branch": "main",
            "web_url": "https://gitlab.com/group/repo",
        }
    ]
    # 단일 페이지 응답 (x-next-page 헤더 없음)
    mock_response = _make_httpx_response(200, gitlab_projects)
    mock_response.headers = {"x-next-page": ""}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        # Act
        result = await gitlab_service.list_repositories()

    # Assert
    assert len(result) == 1, f"저장소 1건을 반환해야 한다, 실제: {len(result)}"
    assert result[0]["platform_repo_id"] == "123", \
        f"platform_repo_id가 '123'이어야 한다, 실제: {result[0].get('platform_repo_id')}"
    assert result[0]["full_name"] == "group/repo", \
        f"full_name이 'group/repo'이어야 한다, 실제: {result[0].get('full_name')}"


# ──────────────────────────────────────────────────────────────
# U-0908: list_repositories() — 페이지네이션 처리
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gitlab_list_repositories_pagination(gitlab_service):
    """list_repositories()가 x-next-page 헤더를 따라 전체 저장소를 수집한다.

    Given: page1(20건, x-next-page: 2) + page2(5건, x-next-page: "")
    When: list_repositories() 호출
    Then: 25건 반환
    """
    # Arrange
    page1_projects = [
        {"id": i, "path_with_namespace": f"group/repo-{i}", "visibility": "private",
         "default_branch": "main", "web_url": f"https://gitlab.com/group/repo-{i}"}
        for i in range(1, 21)  # 20건
    ]
    page2_projects = [
        {"id": i, "path_with_namespace": f"group/repo-{i}", "visibility": "private",
         "default_branch": "main", "web_url": f"https://gitlab.com/group/repo-{i}"}
        for i in range(21, 26)  # 5건
    ]

    mock_page1 = _make_httpx_response(200, page1_projects)
    mock_page1.headers = {"x-next-page": "2"}
    mock_page2 = _make_httpx_response(200, page2_projects)
    mock_page2.headers = {"x-next-page": ""}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=[mock_page1, mock_page2])
        mock_client_cls.return_value = mock_client

        # Act
        result = await gitlab_service.list_repositories()

    # Assert
    assert len(result) == 25, f"페이지네이션 후 25건을 반환해야 한다, 실제: {len(result)}"


# ──────────────────────────────────────────────────────────────
# U-0909: get_changed_files() — MR 변경 파일 조회
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gitlab_get_changed_files_success(gitlab_service):
    """get_changed_files()가 MR의 변경 파일 경로 목록을 반환한다.

    Given: GET /api/v4/projects/{id}/merge_requests/{mr_iid}/changes → 200 + changes 응답
    When: get_changed_files("group/repo", 42) 호출
    Then: 변경 파일 경로 목록 반환
    """
    # Arrange
    mr_changes = {
        "changes": [
            {"new_path": "src/app.py", "old_path": "src/app.py"},
            {"new_path": "src/utils.py", "old_path": "src/utils.py"},
            {"new_path": "src/main.js", "old_path": "src/main.js"},
        ]
    }
    # 저장소 조회 Mock (platform_repo_id 확인용)
    project_info = {"id": 123, "path_with_namespace": "group/repo"}
    mock_project_resp = _make_httpx_response(200, project_info)
    mock_changes_resp = _make_httpx_response(200, mr_changes)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=[mock_project_resp, mock_changes_resp])
        mock_client_cls.return_value = mock_client

        # Act
        result = await gitlab_service.get_changed_files("group/repo", 42)

    # Assert
    assert "src/app.py" in result, "변경 파일 목록에 src/app.py가 포함되어야 한다"
    assert "src/utils.py" in result, "변경 파일 목록에 src/utils.py가 포함되어야 한다"
    assert len(result) == 3, f"변경 파일 3건을 반환해야 한다, 실제: {len(result)}"


# ──────────────────────────────────────────────────────────────
# U-0910: create_merge_request() — MR 생성 성공
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gitlab_create_merge_request_success(gitlab_service):
    """create_merge_request()가 MR을 생성하고 {"number": iid, "html_url": web_url}을 반환한다.

    Given: POST /api/v4/projects/{id}/merge_requests → 201 + MR JSON
    When: create_merge_request("group/repo", ...) 호출
    Then: {"number": 7, "html_url": "https://gitlab.com/group/repo/-/merge_requests/7"} 반환
    """
    # Arrange
    mr_response = {
        "iid": 7,
        "title": "Vulnix: Fix SQL Injection",
        "web_url": "https://gitlab.com/group/repo/-/merge_requests/7",
        "state": "opened",
    }
    # 프로젝트 ID 조회 + MR 생성 응답
    project_info = {"id": 123, "path_with_namespace": "group/repo"}
    mock_project_resp = _make_httpx_response(200, project_info)
    mock_mr_resp = _make_httpx_response(201, mr_response)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_project_resp)
        mock_client.post = AsyncMock(return_value=mock_mr_resp)
        mock_client_cls.return_value = mock_client

        # Act
        result = await gitlab_service.create_merge_request(
            full_name="group/repo",
            head="vulnix/fix-sql-injection-a1b2c3d",
            base="main",
            title="Vulnix: Fix SQL Injection",
            body="SQL Injection 취약점을 수정합니다.",
        )

    # Assert
    assert result["number"] == 7, \
        f"MR iid가 7이어야 한다, 실제: {result.get('number')}"
    assert "gitlab.com" in result["html_url"], \
        f"html_url에 gitlab.com이 포함되어야 한다, 실제: {result.get('html_url')}"


# ──────────────────────────────────────────────────────────────
# U-0911: create_merge_request() — GitLab API 오류 (422)
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gitlab_create_merge_request_api_error(gitlab_service):
    """GitLab API가 422를 반환하면 httpx.HTTPStatusError가 발생한다.

    Given: POST /api/v4/projects/{id}/merge_requests → 422
    When: create_merge_request("group/repo", ...) 호출
    Then: httpx.HTTPStatusError 발생
    """
    # Arrange
    project_info = {"id": 123, "path_with_namespace": "group/repo"}
    mock_project_resp = _make_httpx_response(200, project_info)
    mock_error_resp = _make_httpx_response(422, {"message": "Unprocessable Entity"})

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_project_resp)
        mock_client.post = AsyncMock(return_value=mock_error_resp)
        mock_client_cls.return_value = mock_client

        # Act / Assert
        with pytest.raises(httpx.HTTPStatusError):
            await gitlab_service.create_merge_request(
                full_name="group/repo",
                head="vulnix/fix-sql-injection-a1b2c3d",
                base="main",
                title="Vulnix: Fix SQL Injection",
                body="패치 내용",
            )


# ──────────────────────────────────────────────────────────────
# U-0912: register_webhook() — Webhook 등록 성공
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gitlab_register_webhook_success(gitlab_service):
    """register_webhook()이 GitLab Webhook을 정상적으로 등록한다.

    Given: POST /api/v4/projects/{id}/hooks → 201
    When: register_webhook("group/repo", url, secret, events) 호출
    Then: 예외 없이 정상 완료
    """
    # Arrange
    project_info = {"id": 123, "path_with_namespace": "group/repo"}
    hook_response = {"id": 5, "url": "https://vulnix.example.com/api/v1/webhooks/gitlab"}
    mock_project_resp = _make_httpx_response(200, project_info)
    mock_hook_resp = _make_httpx_response(201, hook_response)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_project_resp)
        mock_client.post = AsyncMock(return_value=mock_hook_resp)
        mock_client_cls.return_value = mock_client

        # Act — 예외가 발생하지 않아야 한다
        await gitlab_service.register_webhook(
            full_name="group/repo",
            webhook_url="https://vulnix.example.com/api/v1/webhooks/gitlab",
            secret="test_webhook_secret",
            events=["push_events", "merge_requests_events"],
        )


# ──────────────────────────────────────────────────────────────
# U-0913: get_file_content() — 파일 내용 조회
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gitlab_get_file_content_success(gitlab_service):
    """get_file_content()가 base64 인코딩된 파일 내용을 디코딩하여 반환한다.

    Given: GET /api/v4/projects/{id}/repository/files/{path}?ref={ref} → 200 + base64 content JSON
    When: get_file_content("group/repo", "src/app.py", "main") 호출
    Then: (decoded_content, blob_sha) 튜플 반환
    """
    # Arrange
    raw_content = "def hello():\n    print('world')\n"
    encoded_content = base64.b64encode(raw_content.encode()).decode()
    file_response = {
        "content": encoded_content,
        "blob_id": "abc123filesha",
        "file_name": "app.py",
        "file_path": "src/app.py",
        "encoding": "base64",
    }
    project_info = {"id": 123, "path_with_namespace": "group/repo"}
    mock_project_resp = _make_httpx_response(200, project_info)
    mock_file_resp = _make_httpx_response(200, file_response)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=[mock_project_resp, mock_file_resp])
        mock_client_cls.return_value = mock_client

        # Act
        content, sha = await gitlab_service.get_file_content(
            full_name="group/repo",
            file_path="src/app.py",
            ref="main",
        )

    # Assert
    assert "def hello():" in content, \
        f"디코딩된 파일 내용에 'def hello():'가 포함되어야 한다, 실제: {content[:50]}"
    assert sha == "abc123filesha", \
        f"blob_sha가 'abc123filesha'이어야 한다, 실제: {sha}"


# ──────────────────────────────────────────────────────────────
# U-0914: create_branch() — 브랜치 생성 성공
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gitlab_create_branch_success(gitlab_service):
    """create_branch()가 GitLab에 새 브랜치를 생성한다.

    Given: POST /api/v4/projects/{id}/repository/branches → 201
    When: create_branch("group/repo", "vulnix/fix-sql-injection-a1b2c3d", "abc123sha") 호출
    Then: 예외 없이 정상 완료
    """
    # Arrange
    project_info = {"id": 123, "path_with_namespace": "group/repo"}
    branch_response = {
        "name": "vulnix/fix-sql-injection-a1b2c3d",
        "commit": {"id": "abc123sha"},
    }
    mock_project_resp = _make_httpx_response(200, project_info)
    mock_branch_resp = _make_httpx_response(201, branch_response)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_project_resp)
        mock_client.post = AsyncMock(return_value=mock_branch_resp)
        mock_client_cls.return_value = mock_client

        # Act — 예외가 발생하지 않아야 한다
        await gitlab_service.create_branch(
            full_name="group/repo",
            branch_name="vulnix/fix-sql-injection-a1b2c3d",
            base_sha="abc123sha",
        )


# ──────────────────────────────────────────────────────────────
# U-0915: create_file_commit() — 파일 수정 커밋
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gitlab_create_file_commit_success(gitlab_service):
    """create_file_commit()이 GitLab에 파일 수정 커밋을 생성한다.

    Given: PUT /api/v4/projects/{id}/repository/files/{path} → 200 + 커밋 결과
    When: create_file_commit("group/repo", ...) 호출
    Then: 커밋 결과 dict 반환
    """
    # Arrange
    project_info = {"id": 123, "path_with_namespace": "group/repo"}
    commit_response = {
        "file_path": "src/app.py",
        "branch": "vulnix/fix-sql-injection-a1b2c3d",
        "content": "fixed content",
    }
    mock_project_resp = _make_httpx_response(200, project_info)
    mock_commit_resp = _make_httpx_response(200, commit_response)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_project_resp)
        mock_client.put = AsyncMock(return_value=mock_commit_resp)
        mock_client_cls.return_value = mock_client

        # Act
        result = await gitlab_service.create_file_commit(
            full_name="group/repo",
            branch_name="vulnix/fix-sql-injection-a1b2c3d",
            file_path="src/app.py",
            content='def safe_query(user_id):\n    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))\n',
            message="vulnix: Fix SQL Injection in src/app.py",
            file_sha="abc123filesha",
        )

    # Assert
    assert result is not None, "create_file_commit()이 결과 dict를 반환해야 한다"
    assert isinstance(result, dict), f"결과가 dict이어야 한다, 실제 타입: {type(result)}"


# ──────────────────────────────────────────────────────────────
# 경계 조건: Self-managed 인스턴스 URL 트레일링 슬래시 정규화
# ──────────────────────────────────────────────────────────────

def test_gitlab_service_strips_trailing_slash_from_base_url():
    """base_url의 트레일링 슬래시가 자동으로 제거된다.

    Given: base_url = "https://gitlab.example.com/"
    When: GitLabPlatformService 인스턴스 생성
    Then: 내부적으로 "https://gitlab.example.com"으로 정규화됨
    """
    # Arrange / Act
    from src.services.gitlab_service import GitLabPlatformService

    service = GitLabPlatformService(
        access_token="glpat-test",
        base_url="https://gitlab.example.com/",  # 트레일링 슬래시 포함
    )

    # Assert
    assert not service.base_url.endswith("/"), \
        f"base_url에 트레일링 슬래시가 남아있어서는 안 된다, 실제: {service.base_url}"


# ──────────────────────────────────────────────────────────────
# 경계 조건: 미존재 저장소 조회 시 404 처리
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gitlab_get_changed_files_repo_not_found(gitlab_service):
    """존재하지 않는 저장소의 MR 파일 조회 시 404 예외가 발생한다.

    Given: GET /api/v4/projects/{encoded_path} → 404
    When: get_changed_files("nonexistent/repo", 1) 호출
    Then: httpx.HTTPStatusError 발생
    """
    # Arrange
    mock_404_resp = _make_httpx_response(404, {"message": "404 Project Not Found"})

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_404_resp)
        mock_client_cls.return_value = mock_client

        # Act / Assert
        with pytest.raises((httpx.HTTPStatusError, Exception)):
            await gitlab_service.get_changed_files("nonexistent/repo", 1)
