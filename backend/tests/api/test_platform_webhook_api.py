"""플랫폼 Webhook API 테스트 — F-09 RED 단계

구현이 없는 상태에서 실행하면 모두 FAIL이어야 한다.

테스트 범위:
- POST /api/v1/webhooks/gitlab — X-Gitlab-Token 서명 검증 성공/실패
- POST /api/v1/webhooks/gitlab — push 이벤트 → 스캔 트리거
- POST /api/v1/webhooks/gitlab — merge_request 이벤트 → 스캔 트리거
- POST /api/v1/webhooks/bitbucket — X-Hub-Signature HMAC-SHA256 검증 성공/실패
- POST /api/v1/webhooks/bitbucket — repo:push 이벤트 → 스캔 트리거
- POST /api/v1/webhooks/bitbucket — pullrequest:created → 스캔 트리거
- 서명 검증 함수 단위 테스트 (_verify_gitlab_token, _verify_bitbucket_signature)

인수조건:
- I-0907: GitLab Push Hook → 스캔 트리거, 202, scan_job_id 반환
- I-0908: GitLab MR Hook (open) → 스캔 트리거, 202
- I-0909: 잘못된 X-Gitlab-Token → 403
- I-0910: Bitbucket repo:push → 스캔 트리거, 202
- I-0911: Bitbucket pullrequest:created → 스캔 트리거, 202
- I-0912: 잘못된 X-Hub-Signature → 403
"""

import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────
# 페이로드 헬퍼
# ──────────────────────────────────────────────────────────────

def _make_gitlab_push_payload(
    full_name: str = "group/repo",
    ref: str = "refs/heads/main",
    python_file: bool = True,
) -> dict:
    """GitLab Push Hook 페이로드를 생성하는 헬퍼."""
    modified_files = ["src/app.py", "src/utils.py"] if python_file else ["src/main.js"]
    return {
        "object_kind": "push",
        "ref": ref,
        "checkout_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "project": {
            "id": 123,
            "path_with_namespace": full_name,
            "default_branch": "main",
        },
        "commits": [
            {
                "id": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                "added": [],
                "modified": modified_files,
                "removed": [],
            }
        ],
    }


def _make_gitlab_mr_payload(
    full_name: str = "group/repo",
    action: str = "open",
    mr_iid: int = 42,
) -> dict:
    """GitLab Merge Request Hook 페이로드를 생성하는 헬퍼."""
    return {
        "object_kind": "merge_request",
        "project": {
            "id": 123,
            "path_with_namespace": full_name,
        },
        "object_attributes": {
            "iid": mr_iid,
            "action": action,
            "state": "opened",
            "source_branch": "feature/fix-injection",
            "target_branch": "main",
            "title": "Fix SQL Injection",
        },
    }


def _make_bitbucket_push_payload(
    full_name: str = "my-workspace/my-repo",
    branch: str = "main",
    python_file: bool = True,
) -> dict:
    """Bitbucket repo:push 페이로드를 생성하는 헬퍼."""
    files = ["src/app.py", "src/utils.py"] if python_file else ["src/main.js"]
    return {
        "repository": {
            "full_name": full_name,
            "mainbranch": {"name": "main"},
        },
        "push": {
            "changes": [
                {
                    "new": {"name": branch, "type": "branch"},
                    "commits": [
                        {
                            "hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                            "message": "Fix SQL injection",
                        }
                    ],
                    "files": [{"path": f} for f in files],
                }
            ]
        },
    }


def _make_bitbucket_pr_payload(
    full_name: str = "my-workspace/my-repo",
    pr_id: int = 15,
    python_file: bool = True,
) -> dict:
    """Bitbucket pullrequest:created 페이로드를 생성하는 헬퍼."""
    return {
        "repository": {
            "full_name": full_name,
            "mainbranch": {"name": "main"},
        },
        "pullrequest": {
            "id": pr_id,
            "title": "Feature branch",
            "source": {"branch": {"name": "feature/fix-injection"}},
            "destination": {"branch": {"name": "main"}},
        },
    }


def _make_bitbucket_signature(payload_bytes: bytes, secret: str) -> str:
    """Bitbucket X-Hub-Signature HMAC-SHA256 서명을 생성하는 헬퍼."""
    digest = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


# ──────────────────────────────────────────────────────────────
# GitLab Webhook 서명 검증 단위 테스트 (U-0926 ~ U-0929)
# ──────────────────────────────────────────────────────────────

def test_verify_gitlab_token_valid():
    """유효한 토큰이면 _verify_gitlab_token()이 True를 반환한다.

    Given: secret="abc123", header="abc123"
    When: _verify_gitlab_token(header, secret) 호출
    Then: True 반환 (U-0926)
    """
    # Arrange
    from src.api.v1.webhooks_gitlab import _verify_gitlab_token

    # Act
    result = _verify_gitlab_token("abc123", "abc123")

    # Assert
    assert result is True, "유효한 토큰에서 True를 반환해야 한다"


def test_verify_gitlab_token_mismatch():
    """토큰이 불일치하면 _verify_gitlab_token()이 False를 반환한다.

    Given: secret="abc123", header="wrong"
    When: _verify_gitlab_token(header, secret) 호출
    Then: False 반환 (U-0927)
    """
    # Arrange
    from src.api.v1.webhooks_gitlab import _verify_gitlab_token

    # Act
    result = _verify_gitlab_token("wrong", "abc123")

    # Assert
    assert result is False, "토큰 불일치에서 False를 반환해야 한다"


def test_verify_gitlab_token_header_none():
    """헤더가 None이면 _verify_gitlab_token()이 False를 반환한다.

    Given: secret="abc123", header=None
    When: _verify_gitlab_token(None, secret) 호출
    Then: False 반환 (U-0928)
    """
    # Arrange
    from src.api.v1.webhooks_gitlab import _verify_gitlab_token

    # Act
    result = _verify_gitlab_token(None, "abc123")

    # Assert
    assert result is False, "헤더가 None이면 False를 반환해야 한다"


def test_verify_gitlab_token_uses_constant_time_comparison():
    """_verify_gitlab_token()이 타이밍 공격 방지를 위해 hmac.compare_digest를 사용한다.

    Given: 임의의 토큰 쌍
    When: _verify_gitlab_token 소스 코드 / 동작 확인
    Then: hmac.compare_digest를 통해 상수 시간 비교가 보장됨 (U-0929)
    """
    import inspect
    from src.api.v1.webhooks_gitlab import _verify_gitlab_token

    source = inspect.getsource(_verify_gitlab_token)

    # hmac.compare_digest 사용 여부 확인
    assert "compare_digest" in source, \
        "_verify_gitlab_token()에서 hmac.compare_digest를 사용해야 타이밍 공격을 방지할 수 있다"


# ──────────────────────────────────────────────────────────────
# Bitbucket Webhook 서명 검증 단위 테스트 (U-0930 ~ U-0932)
# ──────────────────────────────────────────────────────────────

def test_verify_bitbucket_signature_valid():
    """유효한 HMAC-SHA256 서명이면 _verify_bitbucket_signature()가 True를 반환한다.

    Given: payload bytes, secret, 올바른 "sha256=..." 서명
    When: _verify_bitbucket_signature(payload, sig, secret) 호출
    Then: True 반환 (U-0930)
    """
    # Arrange
    from src.api.v1.webhooks_bitbucket import _verify_bitbucket_signature

    payload = b'{"repository": {"full_name": "my-workspace/my-repo"}}'
    secret = "test_bitbucket_webhook_secret"
    valid_sig = _make_bitbucket_signature(payload, secret)

    # Act
    result = _verify_bitbucket_signature(payload, valid_sig, secret)

    # Assert
    assert result is True, "유효한 HMAC-SHA256 서명에서 True를 반환해야 한다"


def test_verify_bitbucket_signature_invalid():
    """잘못된 서명이면 _verify_bitbucket_signature()가 False를 반환한다.

    Given: payload bytes, secret, 잘못된 서명
    When: _verify_bitbucket_signature(payload, sig, secret) 호출
    Then: False 반환 (U-0931)
    """
    # Arrange
    from src.api.v1.webhooks_bitbucket import _verify_bitbucket_signature

    payload = b'{"repository": {"full_name": "my-workspace/my-repo"}}'
    secret = "test_bitbucket_webhook_secret"
    invalid_sig = "sha256=totally_wrong_signature_value_that_doesnt_match"

    # Act
    result = _verify_bitbucket_signature(payload, invalid_sig, secret)

    # Assert
    assert result is False, "잘못된 서명에서 False를 반환해야 한다"


def test_verify_bitbucket_signature_header_none():
    """서명 헤더가 None이면 _verify_bitbucket_signature()가 False를 반환한다.

    Given: payload bytes, secret, header=None
    When: _verify_bitbucket_signature(payload, None, secret) 호출
    Then: False 반환 (U-0932)
    """
    # Arrange
    from src.api.v1.webhooks_bitbucket import _verify_bitbucket_signature

    payload = b'{"repository": {"full_name": "my-workspace/my-repo"}}'
    secret = "test_bitbucket_webhook_secret"

    # Act
    result = _verify_bitbucket_signature(payload, None, secret)

    # Assert
    assert result is False, "서명 헤더가 None이면 False를 반환해야 한다"


# ──────────────────────────────────────────────────────────────
# I-0907: GitLab Push Hook → 202, scan_job_id 반환
# ──────────────────────────────────────────────────────────────

def test_gitlab_webhook_push_triggers_scan(test_client):
    """GitLab Push Hook 수신 시 스캔이 트리거되고 202와 scan_job_id를 반환한다.

    Given: GitLab repo 등록, 유효한 X-Gitlab-Token
    When: POST /api/v1/webhooks/gitlab (X-Gitlab-Event: Push Hook)
    Then: 202, scan_job_id 포함 응답 (I-0907)
    """
    # Arrange
    expected_job_id = str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
    payload = _make_gitlab_push_payload()
    payload_bytes = json.dumps(payload).encode("utf-8")
    secret = "test_gitlab_webhook_secret"

    headers = {
        "X-Gitlab-Event": "Push Hook",
        "X-Gitlab-Token": secret,
        "Content-Type": "application/json",
    }

    with patch("src.api.v1.webhooks_gitlab.WebhookHandler") as mock_handler_cls:
        mock_handler = AsyncMock()
        mock_handler.handle_gitlab_push = AsyncMock(return_value=expected_job_id)
        mock_handler_cls.return_value = mock_handler

        # Act
        response = test_client.post(
            "/api/v1/webhooks/gitlab",
            content=payload_bytes,
            headers=headers,
        )

    # Assert
    assert response.status_code == 202, \
        f"202를 반환해야 한다, 실제: {response.status_code}"
    body = response.json()
    assert body.get("scan_job_id") == expected_job_id, \
        f"scan_job_id가 {expected_job_id}이어야 한다, 실제: {body.get('scan_job_id')}"
    assert body.get("event") == "push", \
        f"event가 'push'이어야 한다, 실제: {body.get('event')}"


# ──────────────────────────────────────────────────────────────
# I-0908: GitLab MR Hook (open) → 202, scan_job_id 반환
# ──────────────────────────────────────────────────────────────

def test_gitlab_webhook_mr_open_triggers_scan(test_client):
    """GitLab MR Hook (action=open) 수신 시 스캔이 트리거되고 202와 scan_job_id를 반환한다.

    Given: GitLab repo 등록, GitLab API mock (MR 변경 파일 Python 포함)
    When: POST /api/v1/webhooks/gitlab (X-Gitlab-Event: Merge Request Hook, action=open)
    Then: 202, scan_job_id 반환 (I-0908)
    """
    # Arrange
    expected_job_id = str(uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))
    payload = _make_gitlab_mr_payload(action="open")
    payload_bytes = json.dumps(payload).encode("utf-8")
    secret = "test_gitlab_webhook_secret"

    headers = {
        "X-Gitlab-Event": "Merge Request Hook",
        "X-Gitlab-Token": secret,
        "Content-Type": "application/json",
    }

    with patch("src.api.v1.webhooks_gitlab.WebhookHandler") as mock_handler_cls:
        mock_handler = AsyncMock()
        mock_handler.handle_gitlab_mr = AsyncMock(return_value=expected_job_id)
        mock_handler_cls.return_value = mock_handler

        # Act
        response = test_client.post(
            "/api/v1/webhooks/gitlab",
            content=payload_bytes,
            headers=headers,
        )

    # Assert
    assert response.status_code == 202, \
        f"202를 반환해야 한다, 실제: {response.status_code}"
    body = response.json()
    assert body.get("scan_job_id") == expected_job_id, \
        f"scan_job_id가 {expected_job_id}이어야 한다, 실제: {body.get('scan_job_id')}"
    assert body.get("event") == "merge_request", \
        f"event가 'merge_request'이어야 한다, 실제: {body.get('event')}"


# ──────────────────────────────────────────────────────────────
# I-0909: GitLab Webhook — 잘못된 X-Gitlab-Token → 403
# ──────────────────────────────────────────────────────────────

def test_gitlab_webhook_invalid_token_returns_403(test_client):
    """잘못된 X-Gitlab-Token으로 요청하면 403 Forbidden을 반환한다.

    Given: 잘못된 토큰 헤더
    When: POST /api/v1/webhooks/gitlab
    Then: 403 (I-0909)
    """
    # Arrange
    payload = _make_gitlab_push_payload()
    payload_bytes = json.dumps(payload).encode("utf-8")

    headers = {
        "X-Gitlab-Event": "Push Hook",
        "X-Gitlab-Token": "wrong_token_value",  # 잘못된 토큰
        "Content-Type": "application/json",
    }

    # Act
    response = test_client.post(
        "/api/v1/webhooks/gitlab",
        content=payload_bytes,
        headers=headers,
    )

    # Assert
    assert response.status_code == 403, \
        f"잘못된 토큰에서 403을 반환해야 한다, 실제: {response.status_code}"


def test_gitlab_webhook_missing_token_returns_403(test_client):
    """X-Gitlab-Token 헤더 누락 시 403을 반환한다.

    Given: X-Gitlab-Token 헤더 없음
    When: POST /api/v1/webhooks/gitlab
    Then: 403
    """
    # Arrange
    payload = _make_gitlab_push_payload()
    payload_bytes = json.dumps(payload).encode("utf-8")

    headers = {
        "X-Gitlab-Event": "Push Hook",
        # X-Gitlab-Token 헤더 의도적으로 누락
        "Content-Type": "application/json",
    }

    # Act
    response = test_client.post(
        "/api/v1/webhooks/gitlab",
        content=payload_bytes,
        headers=headers,
    )

    # Assert
    assert response.status_code == 403, \
        f"토큰 헤더 누락 시 403을 반환해야 한다, 실제: {response.status_code}"


def test_gitlab_webhook_missing_event_header_returns_400(test_client):
    """X-Gitlab-Event 헤더 누락 시 400을 반환한다.

    Given: 유효한 토큰이지만 X-Gitlab-Event 헤더 없음
    When: POST /api/v1/webhooks/gitlab
    Then: 400
    """
    # Arrange
    payload = _make_gitlab_push_payload()
    payload_bytes = json.dumps(payload).encode("utf-8")
    secret = "test_gitlab_webhook_secret"

    headers = {
        # X-Gitlab-Event 헤더 의도적으로 누락
        "X-Gitlab-Token": secret,
        "Content-Type": "application/json",
    }

    # Act
    response = test_client.post(
        "/api/v1/webhooks/gitlab",
        content=payload_bytes,
        headers=headers,
    )

    # Assert
    assert response.status_code == 400, \
        f"이벤트 헤더 누락 시 400을 반환해야 한다, 실제: {response.status_code}"


# ──────────────────────────────────────────────────────────────
# I-0910: Bitbucket repo:push → 202, scan_job_id 반환
# ──────────────────────────────────────────────────────────────

def test_bitbucket_webhook_push_triggers_scan(test_client):
    """Bitbucket repo:push 이벤트 수신 시 스캔이 트리거되고 202와 scan_job_id를 반환한다.

    Given: Bitbucket repo 등록, 유효한 X-Hub-Signature
    When: POST /api/v1/webhooks/bitbucket (X-Event-Key: repo:push)
    Then: 202, scan_job_id 반환 (I-0910)
    """
    # Arrange
    expected_job_id = str(uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"))
    payload = _make_bitbucket_push_payload()
    payload_bytes = json.dumps(payload).encode("utf-8")
    secret = "test_bitbucket_webhook_secret"
    valid_sig = _make_bitbucket_signature(payload_bytes, secret)

    headers = {
        "X-Event-Key": "repo:push",
        "X-Hub-Signature": valid_sig,
        "Content-Type": "application/json",
    }

    with patch("src.api.v1.webhooks_bitbucket.WebhookHandler") as mock_handler_cls:
        mock_handler = AsyncMock()
        mock_handler.handle_bitbucket_push = AsyncMock(return_value=expected_job_id)
        mock_handler_cls.return_value = mock_handler

        # Act
        response = test_client.post(
            "/api/v1/webhooks/bitbucket",
            content=payload_bytes,
            headers=headers,
        )

    # Assert
    assert response.status_code == 202, \
        f"202를 반환해야 한다, 실제: {response.status_code}"
    body = response.json()
    assert body.get("scan_job_id") == expected_job_id, \
        f"scan_job_id가 {expected_job_id}이어야 한다, 실제: {body.get('scan_job_id')}"


# ──────────────────────────────────────────────────────────────
# I-0911: Bitbucket pullrequest:created → 202, scan_job_id 반환
# ──────────────────────────────────────────────────────────────

def test_bitbucket_webhook_pr_created_triggers_scan(test_client):
    """Bitbucket pullrequest:created 이벤트 수신 시 스캔이 트리거된다.

    Given: Bitbucket repo 등록, Bitbucket API mock (PR 변경 파일 Python 포함)
    When: POST /api/v1/webhooks/bitbucket (X-Event-Key: pullrequest:created)
    Then: 202, scan_job_id 반환 (I-0911)
    """
    # Arrange
    expected_job_id = str(uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"))
    payload = _make_bitbucket_pr_payload()
    payload_bytes = json.dumps(payload).encode("utf-8")
    secret = "test_bitbucket_webhook_secret"
    valid_sig = _make_bitbucket_signature(payload_bytes, secret)

    headers = {
        "X-Event-Key": "pullrequest:created",
        "X-Hub-Signature": valid_sig,
        "Content-Type": "application/json",
    }

    with patch("src.api.v1.webhooks_bitbucket.WebhookHandler") as mock_handler_cls:
        mock_handler = AsyncMock()
        mock_handler.handle_bitbucket_pr = AsyncMock(return_value=expected_job_id)
        mock_handler_cls.return_value = mock_handler

        # Act
        response = test_client.post(
            "/api/v1/webhooks/bitbucket",
            content=payload_bytes,
            headers=headers,
        )

    # Assert
    assert response.status_code == 202, \
        f"202를 반환해야 한다, 실제: {response.status_code}"
    body = response.json()
    assert body.get("scan_job_id") == expected_job_id, \
        f"scan_job_id가 {expected_job_id}이어야 한다, 실제: {body.get('scan_job_id')}"


# ──────────────────────────────────────────────────────────────
# I-0912: Bitbucket Webhook — 잘못된 X-Hub-Signature → 403
# ──────────────────────────────────────────────────────────────

def test_bitbucket_webhook_invalid_signature_returns_403(test_client):
    """잘못된 X-Hub-Signature로 요청하면 403을 반환한다.

    Given: 잘못된 HMAC 서명 헤더
    When: POST /api/v1/webhooks/bitbucket
    Then: 403 (I-0912)
    """
    # Arrange
    payload = _make_bitbucket_push_payload()
    payload_bytes = json.dumps(payload).encode("utf-8")

    headers = {
        "X-Event-Key": "repo:push",
        "X-Hub-Signature": "sha256=invalid_signature_that_does_not_match_payload",
        "Content-Type": "application/json",
    }

    # Act
    response = test_client.post(
        "/api/v1/webhooks/bitbucket",
        content=payload_bytes,
        headers=headers,
    )

    # Assert
    assert response.status_code == 403, \
        f"잘못된 서명에서 403을 반환해야 한다, 실제: {response.status_code}"


def test_bitbucket_webhook_missing_signature_returns_403(test_client):
    """X-Hub-Signature 헤더 누락 시 403을 반환한다.

    Given: X-Hub-Signature 헤더 없음
    When: POST /api/v1/webhooks/bitbucket
    Then: 403
    """
    # Arrange
    payload = _make_bitbucket_push_payload()
    payload_bytes = json.dumps(payload).encode("utf-8")

    headers = {
        "X-Event-Key": "repo:push",
        # X-Hub-Signature 헤더 의도적으로 누락
        "Content-Type": "application/json",
    }

    # Act
    response = test_client.post(
        "/api/v1/webhooks/bitbucket",
        content=payload_bytes,
        headers=headers,
    )

    # Assert
    assert response.status_code == 403, \
        f"서명 헤더 누락 시 403을 반환해야 한다, 실제: {response.status_code}"


def test_bitbucket_webhook_missing_event_key_returns_400(test_client):
    """X-Event-Key 헤더 누락 시 400을 반환한다.

    Given: 유효한 서명이지만 X-Event-Key 헤더 없음
    When: POST /api/v1/webhooks/bitbucket
    Then: 400
    """
    # Arrange
    payload = _make_bitbucket_push_payload()
    payload_bytes = json.dumps(payload).encode("utf-8")
    secret = "test_bitbucket_webhook_secret"
    valid_sig = _make_bitbucket_signature(payload_bytes, secret)

    headers = {
        # X-Event-Key 헤더 의도적으로 누락
        "X-Hub-Signature": valid_sig,
        "Content-Type": "application/json",
    }

    # Act
    response = test_client.post(
        "/api/v1/webhooks/bitbucket",
        content=payload_bytes,
        headers=headers,
    )

    # Assert
    assert response.status_code == 400, \
        f"이벤트 키 헤더 누락 시 400을 반환해야 한다, 실제: {response.status_code}"


# ──────────────────────────────────────────────────────────────
# 경계 조건: Webhook payload에 알 수 없는 이벤트 타입 → 200으로 무시
# ──────────────────────────────────────────────────────────────

def test_gitlab_webhook_unknown_event_returns_200(test_client):
    """GitLab Webhook에 알 수 없는 이벤트 타입이 오면 에러 없이 200으로 무시한다.

    Given: 유효한 토큰, 지원하지 않는 이벤트 타입 (e.g. "Pipeline Hook")
    When: POST /api/v1/webhooks/gitlab
    Then: 200 또는 202, 오류 없음
    """
    # Arrange
    payload = {"object_kind": "pipeline", "project": {"id": 123}}
    payload_bytes = json.dumps(payload).encode("utf-8")
    secret = "test_gitlab_webhook_secret"

    headers = {
        "X-Gitlab-Event": "Pipeline Hook",  # 미지원 이벤트
        "X-Gitlab-Token": secret,
        "Content-Type": "application/json",
    }

    with patch("src.api.v1.webhooks_gitlab.WebhookHandler") as mock_handler_cls:
        mock_handler = AsyncMock()
        mock_handler_cls.return_value = mock_handler

        # Act
        response = test_client.post(
            "/api/v1/webhooks/gitlab",
            content=payload_bytes,
            headers=headers,
        )

    # Assert
    assert response.status_code in (200, 202), \
        f"미지원 이벤트는 200 또는 202로 무시되어야 한다, 실제: {response.status_code}"


def test_bitbucket_webhook_unknown_event_returns_200(test_client):
    """Bitbucket Webhook에 알 수 없는 이벤트 타입이 오면 에러 없이 200으로 무시한다.

    Given: 유효한 서명, 지원하지 않는 이벤트 타입 (e.g. "issue:created")
    When: POST /api/v1/webhooks/bitbucket
    Then: 200 또는 202
    """
    # Arrange
    payload = {"repository": {"full_name": "my-workspace/my-repo"}}
    payload_bytes = json.dumps(payload).encode("utf-8")
    secret = "test_bitbucket_webhook_secret"
    valid_sig = _make_bitbucket_signature(payload_bytes, secret)

    headers = {
        "X-Event-Key": "issue:created",  # 미지원 이벤트
        "X-Hub-Signature": valid_sig,
        "Content-Type": "application/json",
    }

    with patch("src.api.v1.webhooks_bitbucket.WebhookHandler") as mock_handler_cls:
        mock_handler = AsyncMock()
        mock_handler_cls.return_value = mock_handler

        # Act
        response = test_client.post(
            "/api/v1/webhooks/bitbucket",
            content=payload_bytes,
            headers=headers,
        )

    # Assert
    assert response.status_code in (200, 202), \
        f"미지원 이벤트는 200 또는 202로 무시되어야 한다, 실제: {response.status_code}"
