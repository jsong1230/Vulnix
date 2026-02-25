"""GitHub Webhook 핸들러 — HMAC-SHA256 서명 검증 포함"""

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


def _verify_github_signature(payload: bytes, signature_header: str | None) -> bool:
    """GitHub Webhook HMAC-SHA256 서명을 검증한다.

    GitHub는 요청 헤더 X-Hub-Signature-256에 sha256=<hex> 형식으로 서명을 전달한다.

    Args:
        payload: 요청 body (raw bytes)
        signature_header: X-Hub-Signature-256 헤더 값

    Returns:
        서명이 유효하면 True
    """
    if not signature_header:
        return False

    if not signature_header.startswith("sha256="):
        return False

    expected_signature = "sha256=" + hmac.new(
        key=settings.GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # 타이밍 공격 방지: hmac.compare_digest 사용
    return hmac.compare_digest(expected_signature, signature_header)


@router.post("/github", status_code=status.HTTP_202_ACCEPTED)
async def receive_github_webhook(
    request: Request,
    db: DbSession,
    x_github_event: Annotated[str | None, Header()] = None,
    x_hub_signature_256: Annotated[str | None, Header()] = None,
    x_github_delivery: Annotated[str | None, Header()] = None,
) -> dict:
    """GitHub Webhook 이벤트를 수신하고 스캔 작업을 큐에 등록한다.

    지원 이벤트:
    - push: 지정 브랜치 푸시 시 스캔 트리거
    - pull_request (opened, synchronize): PR 시 스캔 트리거
    - installation (created, deleted): GitHub App 설치/삭제 처리

    보안:
    - HMAC-SHA256 서명 검증 (GitHub Webhook Secret 사용)
    - 서명 불일치 시 403 반환
    """
    # 1. raw body 읽기 (서명 검증 전에 소비해야 함)
    raw_body = await request.body()

    # 2. HMAC-SHA256 서명 검증
    if not _verify_github_signature(raw_body, x_hub_signature_256):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Webhook 서명 검증 실패",
        )

    # 3. 이벤트 타입 파싱
    if not x_github_event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-GitHub-Event 헤더가 없습니다.",
        )

    payload = json.loads(raw_body)

    # 4. WebhookHandler 생성 (db, orchestrator 주입)
    orchestrator = ScanOrchestrator(db=db)
    handler = WebhookHandler(db=db, orchestrator=orchestrator)

    # 5. 이벤트별 처리 분기
    if x_github_event == "push":
        scan_job_id = await handler.handle_push(payload)
        return {
            "message": "이벤트가 수신되었습니다.",
            "event": "push",
            "delivery": x_github_delivery or "",
            "scan_job_id": scan_job_id,
        }

    elif x_github_event == "pull_request":
        action = payload.get("action")
        if action in ("opened", "synchronize"):
            scan_job_id = await handler.handle_pull_request(payload, action)
            return {
                "message": "이벤트가 수신되었습니다.",
                "event": "pull_request",
                "delivery": x_github_delivery or "",
                "scan_job_id": scan_job_id,
            }

    elif x_github_event == "installation":
        action = payload.get("action")
        if action == "created":
            repo_ids = await handler.handle_installation_created(payload)
            return {
                "message": "이벤트가 수신되었습니다.",
                "event": "installation",
                "delivery": x_github_delivery or "",
                "repo_ids": repo_ids,
            }
        elif action == "deleted":
            repo_ids = await handler.handle_installation_deleted(payload)
            return {
                "message": "이벤트가 수신되었습니다.",
                "event": "installation",
                "delivery": x_github_delivery or "",
                "repo_ids": repo_ids,
            }

    elif x_github_event == "ping":
        # GitHub가 Webhook 등록 시 ping을 보냄
        return {"message": "pong", "delivery": x_github_delivery or ""}

    return {
        "message": "이벤트가 수신되었습니다.",
        "event": x_github_event,
        "delivery": x_github_delivery or "",
    }
