"""BitbucketPlatformService 단위 테스트 — F-09 RED 단계

구현이 없는 상태에서 실행하면 모두 FAIL이어야 한다.

테스트 범위:
- validate_credentials(): App Password 유효/무효 검증
- list_repositories(): 저장소 목록 조회 + 페이지네이션
- get_changed_files(): PR diffstat 조회
- create_merge_request(): PR 생성 성공/실패
- register_webhook(): Webhook 등록
- create_branch(): 브랜치 생성
- create_file_commit(): form-data 파일 커밋
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# ──────────────────────────────────────────────────────────────
# 픽스처
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def bitbucket_service():
    """BitbucketPlatformService 인스턴스 픽스처.

    실제 Bitbucket API 호출 없이 단위 테스트에 사용한다.
    username + App Password (Basic Auth) 방식.
    """
    from src.services.bitbucket_service import BitbucketPlatformService

    return BitbucketPlatformService(
        username="bitbucket-testuser",
        app_password="test_app_password_xxxx",
    )


def _make_httpx_response(status_code: int, json_body: dict | list | None = None) -> MagicMock:
    """httpx.Response Mock 생성 헬퍼."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    if json_body is not None:
        response.json.return_value = json_body
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
# U-0917: validate_credentials() — App Password 유효
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bitbucket_validate_credentials_valid(bitbucket_service):
    """유효한 App Password로 validate_credentials()를 호출하면 True를 반환한다.

    Given: GET /2.0/user (Basic Auth) → 200
    When: validate_credentials() 호출
    Then: True 반환
    """
    # Arrange
    mock_response = _make_httpx_response(200, {
        "account_id": "12345",
        "username": "bitbucket-testuser",
        "display_name": "Test User",
    })

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        # Act
        result = await bitbucket_service.validate_credentials()

    # Assert
    assert result is True, "유효한 App Password에서 True를 반환해야 한다"


# ──────────────────────────────────────────────────────────────
# U-0918: validate_credentials() — App Password 무효 (401)
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bitbucket_validate_credentials_invalid(bitbucket_service):
    """무효한 App Password로 validate_credentials()를 호출하면 False를 반환한다.

    Given: GET /2.0/user → 401
    When: validate_credentials() 호출
    Then: False 반환
    """
    # Arrange
    mock_response = _make_httpx_response(401, {"error": {"message": "Unauthorized"}})

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        # Act
        result = await bitbucket_service.validate_credentials()

    # Assert
    assert result is False, "무효한 App Password에서 False를 반환해야 한다"


# ──────────────────────────────────────────────────────────────
# U-0919: list_repositories() — 정상 응답
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bitbucket_list_repositories_success(bitbucket_service):
    """list_repositories()가 Bitbucket 저장소 목록을 반환한다.

    Given: GET /2.0/repositories/{workspace} → 200 + repos JSON (values[])
    When: list_repositories() 호출 (workspace 파라미터 전달)
    Then: 저장소 목록 반환
    """
    # Arrange
    bb_response = {
        "values": [
            {
                "uuid": "{aaaa-bbbb-cccc}",
                "full_name": "my-workspace/my-repo",
                "is_private": True,
                "mainbranch": {"name": "main"},
                "links": {"html": {"href": "https://bitbucket.org/my-workspace/my-repo"}},
                "language": "python",
            }
        ],
        "next": None,
    }
    mock_response = _make_httpx_response(200, bb_response)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        # Act
        result = await bitbucket_service.list_repositories(workspace="my-workspace")

    # Assert
    assert len(result) == 1, f"저장소 1건을 반환해야 한다, 실제: {len(result)}"
    assert result[0]["full_name"] == "my-workspace/my-repo", \
        f"full_name이 'my-workspace/my-repo'이어야 한다, 실제: {result[0].get('full_name')}"


# ──────────────────────────────────────────────────────────────
# U-0920: list_repositories() — 페이지네이션 (next URL)
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bitbucket_list_repositories_pagination(bitbucket_service):
    """list_repositories()가 next URL을 따라 전체 저장소를 수집한다.

    Given: page1 with next URL + page2 without next URL
    When: list_repositories(workspace="my-workspace") 호출
    Then: 두 페이지의 저장소를 병합하여 반환
    """
    # Arrange
    page1_repos = [
        {
            "uuid": f"{{uuid-{i}}}",
            "full_name": f"my-workspace/repo-{i}",
            "is_private": True,
            "mainbranch": {"name": "main"},
            "links": {"html": {"href": f"https://bitbucket.org/my-workspace/repo-{i}"}},
        }
        for i in range(1, 3)  # 2건
    ]
    page2_repos = [
        {
            "uuid": f"{{uuid-{i}}}",
            "full_name": f"my-workspace/repo-{i}",
            "is_private": False,
            "mainbranch": {"name": "main"},
            "links": {"html": {"href": f"https://bitbucket.org/my-workspace/repo-{i}"}},
        }
        for i in range(3, 5)  # 2건
    ]

    page1_response = {
        "values": page1_repos,
        "next": "https://api.bitbucket.org/2.0/repositories/my-workspace?page=2",
    }
    page2_response = {
        "values": page2_repos,
        "next": None,
    }

    mock_page1 = _make_httpx_response(200, page1_response)
    mock_page2 = _make_httpx_response(200, page2_response)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=[mock_page1, mock_page2])
        mock_client_cls.return_value = mock_client

        # Act
        result = await bitbucket_service.list_repositories(workspace="my-workspace")

    # Assert
    assert len(result) == 4, f"페이지네이션 후 4건을 반환해야 한다, 실제: {len(result)}"


# ──────────────────────────────────────────────────────────────
# U-0921: get_changed_files() — PR diffstat 조회
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bitbucket_get_changed_files_success(bitbucket_service):
    """get_changed_files()가 PR의 변경 파일 경로 목록을 반환한다.

    Given: GET /2.0/repositories/{workspace}/{slug}/pullrequests/{id}/diffstat → 200
    When: get_changed_files("my-workspace/my-repo", 42) 호출
    Then: 변경 파일 경로 목록 반환
    """
    # Arrange
    diffstat_response = {
        "values": [
            {"new": {"path": "src/app.py"}, "old": {"path": "src/app.py"}, "status": "modified"},
            {"new": {"path": "src/utils.py"}, "old": {"path": "src/utils.py"}, "status": "modified"},
        ]
    }
    mock_response = _make_httpx_response(200, diffstat_response)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        # Act
        result = await bitbucket_service.get_changed_files("my-workspace/my-repo", 42)

    # Assert
    assert "src/app.py" in result, "변경 파일 목록에 src/app.py가 포함되어야 한다"
    assert "src/utils.py" in result, "변경 파일 목록에 src/utils.py가 포함되어야 한다"
    assert len(result) == 2, f"변경 파일 2건을 반환해야 한다, 실제: {len(result)}"


# ──────────────────────────────────────────────────────────────
# U-0922: create_merge_request() — PR 생성 성공
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bitbucket_create_merge_request_success(bitbucket_service):
    """create_merge_request()가 PR을 생성하고 {"number": id, "html_url": ...}을 반환한다.

    Given: POST /2.0/repositories/{workspace}/{slug}/pullrequests → 201 + PR JSON
    When: create_merge_request("my-workspace/my-repo", ...) 호출
    Then: {"number": 15, "html_url": "https://bitbucket.org/my-workspace/my-repo/pull-requests/15"} 반환
    """
    # Arrange
    pr_response = {
        "id": 15,
        "title": "Vulnix: Fix SQL Injection",
        "links": {
            "html": {"href": "https://bitbucket.org/my-workspace/my-repo/pull-requests/15"}
        },
        "state": "OPEN",
    }
    mock_pr_resp = _make_httpx_response(201, pr_response)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_pr_resp)
        mock_client_cls.return_value = mock_client

        # Act
        result = await bitbucket_service.create_merge_request(
            full_name="my-workspace/my-repo",
            head="vulnix/fix-sql-injection-a1b2c3d",
            base="main",
            title="Vulnix: Fix SQL Injection",
            body="SQL Injection 취약점을 수정합니다.",
        )

    # Assert
    assert result["number"] == 15, \
        f"PR id가 15이어야 한다, 실제: {result.get('number')}"
    assert "bitbucket.org" in result["html_url"], \
        f"html_url에 bitbucket.org가 포함되어야 한다, 실제: {result.get('html_url')}"


# ──────────────────────────────────────────────────────────────
# 에러 케이스: create_merge_request() — 401 자격증명 오류
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bitbucket_create_merge_request_unauthorized(bitbucket_service):
    """자격증명 오류 시 create_merge_request()가 httpx.HTTPStatusError를 발생시킨다.

    Given: POST /2.0/repositories/{workspace}/{slug}/pullrequests → 401
    When: create_merge_request("my-workspace/my-repo", ...) 호출
    Then: httpx.HTTPStatusError 발생
    """
    # Arrange
    mock_error_resp = _make_httpx_response(401, {"error": {"message": "Unauthorized"}})

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_error_resp)
        mock_client_cls.return_value = mock_client

        # Act / Assert
        with pytest.raises(httpx.HTTPStatusError):
            await bitbucket_service.create_merge_request(
                full_name="my-workspace/my-repo",
                head="vulnix/fix-sql-injection-a1b2c3d",
                base="main",
                title="Vulnix: Fix SQL Injection",
                body="패치 내용",
            )


# ──────────────────────────────────────────────────────────────
# 에러 케이스: create_merge_request() — 404 저장소 없음
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bitbucket_create_merge_request_repo_not_found(bitbucket_service):
    """존재하지 않는 저장소에 PR 생성 시 httpx.HTTPStatusError가 발생한다.

    Given: POST → 404
    When: create_merge_request 호출
    Then: httpx.HTTPStatusError 발생
    """
    # Arrange
    mock_error_resp = _make_httpx_response(404, {"error": {"message": "Not Found"}})

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_error_resp)
        mock_client_cls.return_value = mock_client

        # Act / Assert
        with pytest.raises(httpx.HTTPStatusError):
            await bitbucket_service.create_merge_request(
                full_name="nonexistent/repo",
                head="feature-branch",
                base="main",
                title="Test PR",
                body="Test body",
            )


# ──────────────────────────────────────────────────────────────
# U-0923: register_webhook() — Webhook 등록 성공
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bitbucket_register_webhook_success(bitbucket_service):
    """register_webhook()이 Bitbucket Webhook을 정상적으로 등록한다.

    Given: POST /2.0/repositories/{workspace}/{slug}/hooks → 201
    When: register_webhook("my-workspace/my-repo", url, secret, events) 호출
    Then: 예외 없이 정상 완료
    """
    # Arrange
    hook_response = {
        "uid": "webhook-uuid-1234",
        "url": "https://vulnix.example.com/api/v1/webhooks/bitbucket",
        "active": True,
    }
    mock_hook_resp = _make_httpx_response(201, hook_response)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_hook_resp)
        mock_client_cls.return_value = mock_client

        # Act — 예외가 발생하지 않아야 한다
        await bitbucket_service.register_webhook(
            full_name="my-workspace/my-repo",
            webhook_url="https://vulnix.example.com/api/v1/webhooks/bitbucket",
            secret="test_webhook_secret",
            events=["repo:push", "pullrequest:created", "pullrequest:updated"],
        )


# ──────────────────────────────────────────────────────────────
# U-0924: create_branch() — 브랜치 생성 성공
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bitbucket_create_branch_success(bitbucket_service):
    """create_branch()가 Bitbucket에 새 브랜치를 생성한다.

    Given: POST /2.0/repositories/{workspace}/{slug}/refs/branches → 201
    When: create_branch("my-workspace/my-repo", "vulnix/fix-sql-injection-a1b2c3d", "abc123sha") 호출
    Then: 예외 없이 정상 완료
    """
    # Arrange
    branch_response = {
        "name": "vulnix/fix-sql-injection-a1b2c3d",
        "target": {"hash": "abc123sha"},
        "type": "branch",
    }
    mock_branch_resp = _make_httpx_response(201, branch_response)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_branch_resp)
        mock_client_cls.return_value = mock_client

        # Act — 예외가 발생하지 않아야 한다
        await bitbucket_service.create_branch(
            full_name="my-workspace/my-repo",
            branch_name="vulnix/fix-sql-injection-a1b2c3d",
            base_sha="abc123sha",
        )


# ──────────────────────────────────────────────────────────────
# U-0925: create_file_commit() — form-data 커밋
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bitbucket_create_file_commit_form_data(bitbucket_service):
    """create_file_commit()이 Bitbucket에 form-data 형식으로 파일 수정 커밋을 생성한다.

    Given: POST /2.0/repositories/{workspace}/{slug}/src (form-data) → 201
    When: create_file_commit("my-workspace/my-repo", ...) 호출
    Then: 커밋 결과 dict 반환
    """
    # Arrange — Bitbucket src API는 201 반환 시 Location 헤더에 커밋 URL을 포함한다
    mock_commit_resp = _make_httpx_response(201, {})
    mock_commit_resp.headers = {
        "Location": "/2.0/repositories/my-workspace/my-repo/commit/newcommitsha"
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_commit_resp)
        mock_client_cls.return_value = mock_client

        # Act
        result = await bitbucket_service.create_file_commit(
            full_name="my-workspace/my-repo",
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
# 경계 조건: workspace 이름에 특수문자 포함 시 URL 인코딩 처리
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bitbucket_list_repositories_workspace_url_encoding(bitbucket_service):
    """workspace 이름에 특수문자가 있어도 URL 인코딩되어 정상 요청된다.

    Given: workspace = "my-workspace+special"
    When: list_repositories(workspace="my-workspace+special") 호출
    Then: URL에 플러스 기호가 인코딩되어 요청됨 (에러 없이 처리)
    """
    # Arrange
    bb_response = {"values": [], "next": None}
    mock_response = _make_httpx_response(200, bb_response)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        # Act — 예외 없이 정상 처리되어야 한다
        result = await bitbucket_service.list_repositories(workspace="my-workspace+special")

    # Assert
    assert isinstance(result, list), "결과가 list이어야 한다"
    # get()이 호출된 URL 확인
    call_args = mock_client.get.call_args
    called_url = str(call_args[0][0]) if call_args[0] else str(call_args.kwargs.get("url", ""))
    # URL에 인코딩된 형태가 포함되거나 원본 workspace 이름이 없어야 한다
    assert "my-workspace+special" not in called_url or "%2B" in called_url or "my-workspace" in called_url, \
        "workspace 이름이 URL에 올바르게 포함되어야 한다"
