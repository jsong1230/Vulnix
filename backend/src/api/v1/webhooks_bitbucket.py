"""Bitbucket Webhook 핸들러 — X-Hub-Signature HMAC-SHA256 검증"""

import hashlib
import hmac
import json
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status

from src.api.deps import DbSession
from src.config import get_settings
from src.services.scan_orchestrator import ScanOrchestrator
from src.services.webhook_handler import WebhookHandler

router = APIRouter()
settings = get_settings()

# Bitbucket Webhook 서명 시크릿 (환경변수에서 로드, 없으면 기본값)
_BITBUCKET_WEBHOOK_SECRET: str = getattr(
    settings, "BITBUCKET_WEBHOOK_SECRET", "test_bitbucket_webhook_secret"
)


def _verify_bitbucket_signature(
    payload: bytes, signature: str | None, secret: str
) -> bool:
    """Bitbucket Webhook X-Hub-Signature HMAC-SHA256 서명을 검증한다.

    Bitbucket은 X-Hub-Signature 헤더에 sha256=<hex> 형식으로 서명을 전달한다.
    타이밍 공격 방지를 위해 hmac.compare_digest로 상수 시간 비교한다.

    Args:
        payload: 요청 body (raw bytes)
        signature: X-Hub-Signature 헤더 값 (None이면 즉시 False)
        secret: 저장소에 설정된 webhook_secret

    Returns:
        서명이 유효하면 True
    """
    if signature is None:
        return False

    if not signature.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(
        key=secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # hmac.compare_digest로 타이밍 공격 방지
    return hmac.compare_digest(expected, signature)


@router.post("/bitbucket", status_code=status.HTTP_202_ACCEPTED)
async def receive_bitbucket_webhook(
    request: Request,
    db: DbSession,
    x_event_key: Annotated[str | None, Header()] = None,
    x_hub_signature: Annotated[str | None, Header()] = None,
) -> dict:
    """Bitbucket Webhook 이벤트를 수신하고 스캔 작업을 큐에 등록한다.

    지원 이벤트:
    - repo:push: 기본 브랜치 push 시 스캔 트리거
    - pullrequest:created: PR 생성 시 스캔 트리거
    - pullrequest:updated: PR 업데이트 시 기존 스캔 취소 후 재등록

    보안:
    - X-Hub-Signature HMAC-SHA256 검증
    - 서명 불일치 시 403 반환
    - 이벤트 헤더 누락 시 400 반환
    """
    # 1. raw body 읽기
    raw_body = await request.body()

    # 2. X-Hub-Signature HMAC-SHA256 검증
    if not _verify_bitbucket_signature(raw_body, x_hub_signature, _BITBUCKET_WEBHOOK_SECRET):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bitbucket Webhook 서명 검증 실패",
        )

    # 3. X-Event-Key 헤더 확인
    if not x_event_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Event-Key 헤더가 없습니다.",
        )

    payload = json.loads(raw_body)

    # 4. WebhookHandler 생성
    orchestrator = ScanOrchestrator(db=db)
    handler = WebhookHandler(db=db, orchestrator=orchestrator)

    # 5. 이벤트별 처리 분기
    if x_event_key == "repo:push":
        scan_job_id = await handler.handle_bitbucket_push(payload)
        return {
            "message": "이벤트가 수신되었습니다.",
            "event": "push",
            "scan_job_id": scan_job_id,
        }

    elif x_event_key in ("pullrequest:created", "pullrequest:updated"):
        scan_job_id = await handler.handle_bitbucket_pr(payload)
        return {
            "message": "이벤트가 수신되었습니다.",
            "event": "pull_request",
            "scan_job_id": scan_job_id,
        }

    # 지원하지 않는 이벤트는 무시 (200 반환)
    return {
        "message": "지원하지 않는 이벤트입니다.",
        "event": x_event_key,
        "scan_job_id": None,
    }
