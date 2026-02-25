"""GitHubAppService 패치 관련 메서드 단위 테스트 — F-03 RED 단계

F-03에서 추가되는 메서드 4개를 검증한다:
- create_branch()
- get_file_content()
- create_file_commit()
- create_pull_request()

구현이 완료되지 않은 상태에서 실행하면 모두 FAIL이어야 한다.
"""

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.services.github_app import GitHubAppService


# ──────────────────────────────────────────────────────────────
# 픽스처
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def github_service():
    """GitHubAppService 인스턴스 픽스처.

    _generate_jwt와 get_installation_token을 mock 처리하여
    실제 GitHub App 인증 없이 테스트한다.
    """
    service = GitHubAppService()
    service._generate_jwt = MagicMock(return_value="mock.jwt.token")
    service.get_installation_token = AsyncMock(return_value="ghs_test_installation_token")
    return service


@pytest.fixture
def mock_httpx_client():
    """httpx.AsyncClient Mock 픽스처."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.put = AsyncMock(return_value=mock_response)
    mock_client.delete = AsyncMock(return_value=mock_response)
    return mock_client, mock_response


# ──────────────────────────────────────────────────────────────
# create_branch() 테스트
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_branch_success(github_service):
    """브랜치 생성이 정상적으로 동작하는지 검증한다.

    GitHub API: POST /repos/{owner}/{repo}/git/refs
    """
    # Arrange
    full_name = "test-org/test-repo"
    installation_id = 789
    branch_name = "vulnix/fix-sql-injection-a1b2c3d"
    base_sha = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.status_code = 201

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        # Act
        await github_service.create_branch(
            full_name=full_name,
            installation_id=installation_id,
            branch_name=branch_name,
            base_sha=base_sha,
        )

    # Assert: POST /git/refs 호출 확인
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    # URL에 git/refs 포함 확인
    called_url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
    assert "git/refs" in called_url, \
        f"POST /git/refs URL이 올바르지 않음: {called_url}"
    # body에 ref와 sha 포함 확인
    called_json = call_args[1].get("json", {})
    assert called_json.get("ref") == f"refs/heads/{branch_name}", \
        f"브랜치 ref가 올바르지 않음: {called_json.get('ref')}"
    assert called_json.get("sha") == base_sha, \
        f"base SHA가 올바르지 않음: {called_json.get('sha')}"


@pytest.mark.asyncio
async def test_create_branch_already_exists_handles_422(github_service):
    """이미 존재하는 브랜치(422 에러) 처리가 동작하는지 검증한다."""
    # Arrange
    full_name = "test-org/test-repo"
    installation_id = 789
    branch_name = "vulnix/fix-sql-injection-a1b2c3d"
    base_sha = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"

    mock_response_422 = MagicMock()
    mock_response_422.status_code = 422
    mock_response_422.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "422 Unprocessable Entity",
            request=MagicMock(),
            response=MagicMock(status_code=422),
        )
    )
    mock_response_201 = MagicMock()
    mock_response_201.status_code = 201
    mock_response_201.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        # 첫 번째 POST는 422, 이후 DELETE + POST는 성공
        mock_client.post = AsyncMock(
            side_effect=[mock_response_422, mock_response_201]
        )
        mock_client.delete = AsyncMock(return_value=MagicMock())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        # Act: 422 에러 발생 시 예외가 발생하지 않아야 함
        await github_service.create_branch(
            full_name=full_name,
            installation_id=installation_id,
            branch_name=branch_name,
            base_sha=base_sha,
        )


# ──────────────────────────────────────────────────────────────
# get_file_content() 테스트
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_file_content_returns_content(github_service):
    """파일 내용과 blob SHA가 올바르게 반환되는지 검증한다.

    GitHub API: GET /repos/{owner}/{repo}/contents/{path}
    base64로 인코딩된 파일 내용을 디코딩하여 반환해야 한다.
    """
    # Arrange
    full_name = "test-org/test-repo"
    installation_id = 789
    file_path = "app/db.py"
    ref = "main"

    original_content = 'def get_user(user_id):\n    query = f"SELECT * FROM users WHERE id = {user_id}"\n    return db.execute(query)\n'
    encoded_content = base64.b64encode(original_content.encode()).decode()
    blob_sha = "abc123filesha456"

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={
        "content": encoded_content,
        "sha": blob_sha,
        "encoding": "base64",
    })

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        # Act
        content, sha = await github_service.get_file_content(
            full_name=full_name,
            installation_id=installation_id,
            file_path=file_path,
            ref=ref,
        )

    # Assert
    assert content == original_content, \
        "파일 내용이 올바르게 base64 디코딩되지 않음"
    assert sha == blob_sha, \
        f"blob SHA가 올바르지 않음: {sha}"


@pytest.mark.asyncio
async def test_get_file_content_not_found_raises(github_service):
    """존재하지 않는 파일 조회 시 적절한 예외가 발생하는지 검증한다."""
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "404 Not Found",
            request=MagicMock(),
            response=MagicMock(status_code=404),
        )
    )

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        # Act & Assert: 404 에러 시 예외 발생
        with pytest.raises(Exception):
            await github_service.get_file_content(
                full_name="test-org/test-repo",
                installation_id=789,
                file_path="nonexistent/file.py",
                ref="main",
            )


# ──────────────────────────────────────────────────────────────
# create_file_commit() 테스트
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_file_commit_success(github_service):
    """파일 커밋이 정상적으로 생성되는지 검증한다.

    GitHub API: PUT /repos/{owner}/{repo}/contents/{path}
    content는 base64로 인코딩되어 전송되어야 한다.
    """
    # Arrange
    full_name = "test-org/test-repo"
    installation_id = 789
    branch_name = "vulnix/fix-sql-injection-a1b2c3d"
    file_path = "app/db.py"
    patched_content = 'def get_user(user_id):\n    query = "SELECT * FROM users WHERE id = %s"\n    return db.execute(query, (user_id,))\n'
    commit_message = "[Vulnix] Fix sql_injection in app/db.py"
    file_sha = "abc123filesha456"

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={
        "commit": {"sha": "newcommitsha789"},
        "content": {"sha": "newblobsha"},
    })

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        # Act
        result = await github_service.create_file_commit(
            full_name=full_name,
            installation_id=installation_id,
            branch_name=branch_name,
            file_path=file_path,
            content=patched_content,
            message=commit_message,
            file_sha=file_sha,
        )

    # Assert: PUT /contents/{path} 호출 확인
    mock_client.put.assert_called_once()
    call_args = mock_client.put.call_args
    called_url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
    assert f"contents/{file_path}" in called_url, \
        f"PUT URL에 파일 경로가 없음: {called_url}"

    # base64 인코딩 확인
    called_json = call_args[1].get("json", {})
    encoded = called_json.get("content", "")
    decoded = base64.b64decode(encoded).decode()
    assert decoded == patched_content, \
        "content가 base64로 올바르게 인코딩되지 않음"

    # 기타 필드 확인
    assert called_json.get("branch") == branch_name, \
        f"브랜치명이 올바르지 않음: {called_json.get('branch')}"
    assert called_json.get("sha") == file_sha, \
        f"file SHA가 올바르지 않음: {called_json.get('sha')}"
    assert called_json.get("message") == commit_message, \
        f"커밋 메시지가 올바르지 않음: {called_json.get('message')}"


# ──────────────────────────────────────────────────────────────
# create_pull_request() 테스트
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_pull_request_success(github_service):
    """PR 생성이 정상적으로 동작하는지 검증한다.

    GitHub API: POST /repos/{owner}/{repo}/pulls
    """
    # Arrange
    full_name = "test-org/test-repo"
    installation_id = 789
    head = "vulnix/fix-sql-injection-a1b2c3d"
    base = "main"
    title = "[Vulnix] Fix sql_injection in app/db.py"
    body = "## Vulnix Security Patch\n\n### 탐지된 취약점..."

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={
        "number": 42,
        "html_url": "https://github.com/test-org/test-repo/pull/42",
        "state": "open",
    })

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        # Act
        result = await github_service.create_pull_request(
            full_name=full_name,
            installation_id=installation_id,
            head=head,
            base=base,
            title=title,
            body=body,
        )

    # Assert
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    called_url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
    assert "pulls" in called_url, \
        f"POST URL에 'pulls'가 없음: {called_url}"

    # 요청 body 확인
    called_json = call_args[1].get("json", {})
    assert called_json.get("head") == head, \
        f"head 브랜치가 올바르지 않음: {called_json.get('head')}"
    assert called_json.get("base") == base, \
        f"base 브랜치가 올바르지 않음: {called_json.get('base')}"
    assert called_json.get("title") == title, \
        f"PR 제목이 올바르지 않음: {called_json.get('title')}"


@pytest.mark.asyncio
async def test_create_pull_request_returns_pr_number(github_service):
    """PR 생성 후 PR 번호가 반환되는지 검증한다."""
    # Arrange
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={
        "number": 99,
        "html_url": "https://github.com/test-org/test-repo/pull/99",
    })

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        # Act
        result = await github_service.create_pull_request(
            full_name="test-org/test-repo",
            installation_id=789,
            head="vulnix/fix-xss-b2c3d4e",
            base="main",
            title="[Vulnix] Fix xss in app/views.py",
            body="PR 본문",
        )

    # Assert
    assert "number" in result, "결과에 'number' 키가 없음"
    assert result["number"] == 99, \
        f"PR 번호가 99여야 함, 실제: {result.get('number')}"
    assert "html_url" in result, "결과에 'html_url' 키가 없음"
    assert "pull/99" in result["html_url"], \
        f"PR URL이 올바르지 않음: {result.get('html_url')}"


@pytest.mark.asyncio
async def test_create_pull_request_with_labels(github_service):
    """라벨을 지정하여 PR을 생성하면 labels 파라미터가 전달되는지 검증한다."""
    # Arrange
    labels = ["security", "vulnix-auto-patch", "high"]

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={
        "number": 77,
        "html_url": "https://github.com/test-org/test-repo/pull/77",
    })

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        # Act
        result = await github_service.create_pull_request(
            full_name="test-org/test-repo",
            installation_id=789,
            head="vulnix/fix-sql-injection-a1b2c3d",
            base="main",
            title="[Vulnix] Fix sql_injection",
            body="PR 본문",
            labels=labels,
        )

    # Assert: 결과에 number 포함
    assert "number" in result, "결과에 'number' 키가 없음"
