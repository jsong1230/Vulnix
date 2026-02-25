"""F-01 Webhook 엔드포인트 테스트 — TDD RED 단계

인수조건:
- GitHub Webhook push/pull_request 이벤트 수신 시 스캔 큐 등록
- HMAC-SHA256 서명 검증 실패 시 401/403 반환
- installation.created/deleted 이벤트 처리
"""

import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import make_github_signature


# ---------------------------------------------------------------------------
# 헬퍼: TestClient로 Webhook 요청을 보낼 때 raw body와 서명을 함께 구성
# ---------------------------------------------------------------------------

def _build_webhook_headers(
    payload_bytes: bytes,
    event: str,
    secret: str = "test_webhook_secret_for_hmac",
    delivery_id: str = "test-delivery-uuid-1234",
    override_signature: str | None = None,
) -> dict:
    """Webhook 요청 헤더를 조립하는 헬퍼."""
    if override_signature is not None:
        signature = override_signature
    else:
        signature = "sha256=" + hmac.new(
            key=secret.encode("utf-8"),
            msg=payload_bytes,
            digestmod=hashlib.sha256,
        ).hexdigest()

    return {
        "X-GitHub-Event": event,
        "X-Hub-Signature-256": signature,
        "X-GitHub-Delivery": delivery_id,
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# 1. push 이벤트 → 스캔 큐 등록
# ---------------------------------------------------------------------------

def test_webhook_push_event_triggers_scan(test_client, valid_webhook_payload, sample_repo):
    """push 이벤트 수신 시 스캔 작업이 큐에 등록되고 job_id를 반환한다.

    Given: 등록된 저장소의 main 브랜치에 Python 파일이 포함된 push 이벤트
    When: POST /api/v1/webhooks/github 요청
    Then: 202 Accepted, 응답 body에 scan_job_id 포함
    """
    # Arrange
    expected_job_id = str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
    payload_bytes = json.dumps(valid_webhook_payload).encode("utf-8")
    headers = _build_webhook_headers(payload_bytes, event="push")

    with (
        patch("src.api.v1.webhooks.WebhookHandler") as mock_handler_cls,
        patch("src.api.v1.webhooks.ScanOrchestrator") as mock_orchestrator_cls,
    ):
        mock_handler = AsyncMock()
        mock_handler.handle_push = AsyncMock(return_value=expected_job_id)
        mock_handler_cls.return_value = mock_handler

        # Act
        response = test_client.post(
            "/api/v1/webhooks/github",
            content=payload_bytes,
            headers=headers,
        )

    # Assert
    assert response.status_code == 202
    body = response.json()
    assert body.get("scan_job_id") == expected_job_id
    assert body.get("event") == "push"


# ---------------------------------------------------------------------------
# 2. PR opened 이벤트 → 스캔 큐 등록
# ---------------------------------------------------------------------------

def test_webhook_pr_opened_triggers_scan(test_client, valid_pr_payload):
    """PR opened 이벤트 수신 시 스캔 작업이 큐에 등록되고 job_id를 반환한다.

    Given: 등록된 저장소에 PR이 opened된 이벤트 (Python 파일 변경 포함)
    When: POST /api/v1/webhooks/github 요청 (X-GitHub-Event: pull_request)
    Then: 202 Accepted, 응답 body에 scan_job_id 포함
    """
    # Arrange
    expected_job_id = str(uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))
    payload_bytes = json.dumps(valid_pr_payload).encode("utf-8")
    headers = _build_webhook_headers(payload_bytes, event="pull_request")

    with patch("src.api.v1.webhooks.WebhookHandler") as mock_handler_cls:
        mock_handler = AsyncMock()
        mock_handler.handle_pull_request = AsyncMock(return_value=expected_job_id)
        mock_handler_cls.return_value = mock_handler

        # Act
        response = test_client.post(
            "/api/v1/webhooks/github",
            content=payload_bytes,
            headers=headers,
        )

    # Assert
    assert response.status_code == 202
    body = response.json()
    assert body.get("scan_job_id") == expected_job_id


# ---------------------------------------------------------------------------
# 3. 잘못된 서명 → 401 또는 403
# ---------------------------------------------------------------------------

def test_webhook_invalid_signature_returns_401(test_client, valid_webhook_payload):
    """잘못된 HMAC-SHA256 서명으로 요청하면 401 또는 403을 반환한다.

    Given: 올바른 페이로드이지만 서명이 틀린 요청
    When: POST /api/v1/webhooks/github
    Then: 401 또는 403 상태 코드 (서명 검증 실패)
    """
    # Arrange
    payload_bytes = json.dumps(valid_webhook_payload).encode("utf-8")
    headers = _build_webhook_headers(
        payload_bytes,
        event="push",
        override_signature="sha256=invalid_signature_hex_value_that_does_not_match",
    )

    # Act
    response = test_client.post(
        "/api/v1/webhooks/github",
        content=payload_bytes,
        headers=headers,
    )

    # Assert — 설계 문서에서는 403이나 스캐폴딩도 403 사용 (401도 허용)
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 4. 서명 헤더 누락 → 401 또는 403
# ---------------------------------------------------------------------------

def test_webhook_missing_signature_returns_401(test_client, valid_webhook_payload):
    """X-Hub-Signature-256 헤더가 없으면 401 또는 403을 반환한다.

    Given: 서명 헤더가 아예 없는 요청
    When: POST /api/v1/webhooks/github
    Then: 401 또는 403 상태 코드
    """
    # Arrange
    payload_bytes = json.dumps(valid_webhook_payload).encode("utf-8")
    headers = {
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": "test-delivery-1234",
        "Content-Type": "application/json",
        # X-Hub-Signature-256 헤더 의도적으로 누락
    }

    # Act
    response = test_client.post(
        "/api/v1/webhooks/github",
        content=payload_bytes,
        headers=headers,
    )

    # Assert
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 5. installation.created → 저장소 등록
# ---------------------------------------------------------------------------

def test_webhook_installation_created_registers_repo(
    test_client,
    valid_installation_created_payload,
):
    """installation.created 이벤트 수신 시 저장소가 등록되고 초기 스캔이 큐에 등록된다.

    Given: GitHub App 설치로 2개 저장소에 접근 권한이 부여된 이벤트
    When: POST /api/v1/webhooks/github (X-GitHub-Event: installation)
    Then: 202 Accepted, 등록된 저장소 목록 반환
    """
    # Arrange
    payload_bytes = json.dumps(valid_installation_created_payload).encode("utf-8")
    headers = _build_webhook_headers(payload_bytes, event="installation")
    expected_repo_ids = [
        str(uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")),
        str(uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")),
    ]

    with patch("src.api.v1.webhooks.WebhookHandler") as mock_handler_cls:
        mock_handler = AsyncMock()
        mock_handler.handle_installation_created = AsyncMock(return_value=expected_repo_ids)
        mock_handler_cls.return_value = mock_handler

        # Act
        response = test_client.post(
            "/api/v1/webhooks/github",
            content=payload_bytes,
            headers=headers,
        )

    # Assert
    assert response.status_code == 202
    body = response.json()
    # installation.created 응답에는 등록된 저장소 목록이 포함되어야 함
    assert "repo_ids" in body or "repositories" in body or body.get("event") == "installation"


# ---------------------------------------------------------------------------
# 6. installation.deleted → 저장소 제거
# ---------------------------------------------------------------------------

def test_webhook_installation_deleted_removes_repo(
    test_client,
    valid_installation_deleted_payload,
):
    """installation.deleted 이벤트 수신 시 저장소가 비활성화된다.

    Given: GitHub App 삭제 이벤트
    When: POST /api/v1/webhooks/github (X-GitHub-Event: installation, action: deleted)
    Then: 202 Accepted, 비활성화된 저장소 목록 반환
    """
    # Arrange
    payload_bytes = json.dumps(valid_installation_deleted_payload).encode("utf-8")
    headers = _build_webhook_headers(payload_bytes, event="installation")
    deactivated_repo_ids = [str(uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))]

    with patch("src.api.v1.webhooks.WebhookHandler") as mock_handler_cls:
        mock_handler = AsyncMock()
        mock_handler.handle_installation_deleted = AsyncMock(return_value=deactivated_repo_ids)
        mock_handler_cls.return_value = mock_handler

        # Act
        response = test_client.post(
            "/api/v1/webhooks/github",
            content=payload_bytes,
            headers=headers,
        )

    # Assert
    assert response.status_code == 202
    body = response.json()
    assert body.get("event") == "installation"


# ---------------------------------------------------------------------------
# 7. 미등록 저장소 push 이벤트 → 무시 (스캔 트리거 안 함)
# ---------------------------------------------------------------------------

def test_webhook_push_skips_if_repo_not_registered(test_client, valid_webhook_payload):
    """등록되지 않은 저장소의 push 이벤트는 스캔 큐 등록 없이 202를 반환한다.

    Given: DB에 등록되지 않은 저장소의 push 이벤트
    When: POST /api/v1/webhooks/github
    Then: 202 Accepted, scan_job_id가 없음 (또는 None)

    인수조건 참조: 미등록 저장소 이벤트 수신 시 조용히 무시
    """
    # Arrange
    payload_bytes = json.dumps(valid_webhook_payload).encode("utf-8")
    headers = _build_webhook_headers(payload_bytes, event="push")

    with patch("src.api.v1.webhooks.WebhookHandler") as mock_handler_cls:
        mock_handler = AsyncMock()
        # handle_push가 None을 반환하면 스캔이 등록되지 않은 것
        mock_handler.handle_push = AsyncMock(return_value=None)
        mock_handler_cls.return_value = mock_handler

        # Act
        response = test_client.post(
            "/api/v1/webhooks/github",
            content=payload_bytes,
            headers=headers,
        )

    # Assert
    assert response.status_code == 202
    body = response.json()
    # scan_job_id 가 없거나 None이어야 함
    assert body.get("scan_job_id") is None or "scan_job_id" not in body


# ---------------------------------------------------------------------------
# 8. 서명 검증 함수 단위 테스트
# ---------------------------------------------------------------------------

def test_verify_github_signature_valid():
    """유효한 HMAC-SHA256 서명이면 True를 반환한다.

    Given: 올바른 시크릿과 페이로드로 생성한 서명
    When: _verify_github_signature 호출
    Then: True 반환
    """
    # Arrange
    from src.api.v1.webhooks import _verify_github_signature

    payload = b'{"ref": "refs/heads/main"}'
    secret = "test_webhook_secret_for_hmac"
    valid_signature = "sha256=" + hmac.new(
        key=secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Act
    result = _verify_github_signature(payload, valid_signature)

    # Assert
    assert result is True


def test_verify_github_signature_invalid():
    """잘못된 서명이면 False를 반환한다.

    Given: 올바른 페이로드이지만 잘못된 서명
    When: _verify_github_signature 호출
    Then: False 반환
    """
    # Arrange
    from src.api.v1.webhooks import _verify_github_signature

    payload = b'{"ref": "refs/heads/main"}'

    # Act
    result = _verify_github_signature(payload, "sha256=wrong_signature_value")

    # Assert
    assert result is False


def test_verify_github_signature_missing():
    """서명 헤더가 None이면 False를 반환한다.

    Given: signature_header가 None
    When: _verify_github_signature 호출
    Then: False 반환
    """
    # Arrange
    from src.api.v1.webhooks import _verify_github_signature

    payload = b'{"ref": "refs/heads/main"}'

    # Act
    result = _verify_github_signature(payload, None)

    # Assert
    assert result is False


def test_verify_github_signature_no_prefix():
    """sha256= 접두사 없는 서명이면 False를 반환한다.

    Given: sha256= 접두사가 없는 서명 헤더 값
    When: _verify_github_signature 호출
    Then: False 반환
    """
    # Arrange
    from src.api.v1.webhooks import _verify_github_signature

    payload = b'{"ref": "refs/heads/main"}'
    # 접두사 없이 hex만 전달
    raw_hex = hmac.new(
        key="test_webhook_secret_for_hmac".encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Act
    result = _verify_github_signature(payload, raw_hex)  # "sha256=" 없음

    # Assert
    assert result is False


# ---------------------------------------------------------------------------
# 9. ping 이벤트 → pong 응답
# ---------------------------------------------------------------------------

def test_webhook_ping_event_returns_pong(test_client):
    """ping 이벤트 수신 시 pong 응답을 반환한다.

    Given: GitHub Webhook 등록 시 전송되는 ping 이벤트
    When: POST /api/v1/webhooks/github (X-GitHub-Event: ping)
    Then: 200 또는 202, message=pong 포함
    """
    # Arrange
    ping_payload = {"zen": "Responsive is better than fast.", "hook_id": 12345}
    payload_bytes = json.dumps(ping_payload).encode("utf-8")
    headers = _build_webhook_headers(payload_bytes, event="ping")

    # Act
    response = test_client.post(
        "/api/v1/webhooks/github",
        content=payload_bytes,
        headers=headers,
    )

    # Assert
    assert response.status_code in (200, 202)
    body = response.json()
    assert body.get("message") == "pong"


# ---------------------------------------------------------------------------
# 10. X-GitHub-Event 헤더 누락 → 400
# ---------------------------------------------------------------------------

def test_webhook_missing_event_header_returns_400(test_client, valid_webhook_payload):
    """X-GitHub-Event 헤더가 없으면 400 Bad Request를 반환한다.

    Given: 서명은 유효하지만 X-GitHub-Event 헤더 누락
    When: POST /api/v1/webhooks/github
    Then: 400 Bad Request
    """
    # Arrange
    payload_bytes = json.dumps(valid_webhook_payload).encode("utf-8")
    signature = "sha256=" + hmac.new(
        key="test_webhook_secret_for_hmac".encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()

    headers = {
        "X-Hub-Signature-256": signature,
        "X-GitHub-Delivery": "test-delivery-5678",
        "Content-Type": "application/json",
        # X-GitHub-Event 헤더 의도적으로 누락
    }

    # Act
    response = test_client.post(
        "/api/v1/webhooks/github",
        content=payload_bytes,
        headers=headers,
    )

    # Assert
    assert response.status_code == 400
