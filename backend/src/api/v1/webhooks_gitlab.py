"""GitLab Webhook 핸들러 — X-Gitlab-Token 직접 비교 검증"""

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

# GitLab Webhook 서명 시크릿 (환경변수에서 로드, 없으면 기본값)
_GITLAB_WEBHOOK_SECRET: str = getattr(settings, "GITLAB_WEBHOOK_SECRET", "test_gitlab_webhook_secret")


def _verify_gitlab_token(token: str | None, secret: str) -> bool:
    """GitLab Webhook X-Gitlab-Token 헤더를 검증한다.

    GitLab은 X-Gitlab-Token 헤더에 설정한 시크릿 문자열을 그대로 전달한다.
    타이밍 공격 방지를 위해 hmac.compare_digest로 상수 시간 비교한다.

    Args:
        token: X-Gitlab-Token 헤더 값 (None이면 즉시 False)
        secret: 저장소에 설정된 webhook_secret

    Returns:
        토큰이 일치하면 True
    """
    if token is None:
        return False
    # hmac.compare_digest로 타이밍 공격 방지
    return hmac.compare_digest(token, secret)


@router.post("/gitlab", status_code=status.HTTP_202_ACCEPTED)
async def receive_gitlab_webhook(
    request: Request,
    db: DbSession,
    x_gitlab_event: Annotated[str | None, Header()] = None,
    x_gitlab_token: Annotated[str | None, Header()] = None,
) -> dict:
    """GitLab Webhook 이벤트를 수신하고 스캔 작업을 큐에 등록한다.

    지원 이벤트:
    - Push Hook: 기본 브랜치 push 시 스캔 트리거
    - Merge Request Hook (open/update): MR 스캔 트리거

    보안:
    - X-Gitlab-Token 헤더 검증 (상수 시간 비교)
    - 토큰 불일치 시 403 반환
    - 이벤트 헤더 누락 시 400 반환
    """
    # 1. raw body 읽기
    raw_body = await request.body()

    # 2. X-Gitlab-Token 검증
    if not _verify_gitlab_token(x_gitlab_token, _GITLAB_WEBHOOK_SECRET):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="GitLab Webhook 토큰 검증 실패",
        )

    # 3. X-Gitlab-Event 헤더 확인
    if not x_gitlab_event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Gitlab-Event 헤더가 없습니다.",
        )

    payload = json.loads(raw_body)

    # 4. WebhookHandler 생성
    orchestrator = ScanOrchestrator(db=db)
    handler = WebhookHandler(db=db, orchestrator=orchestrator)

    # 5. 이벤트별 처리 분기
    if x_gitlab_event == "Push Hook":
        scan_job_id = await handler.handle_gitlab_push(payload)
        return {
            "message": "이벤트가 수신되었습니다.",
            "event": "push",
            "scan_job_id": scan_job_id,
        }

    elif x_gitlab_event == "Merge Request Hook":
        scan_job_id = await handler.handle_gitlab_mr(payload)
        return {
            "message": "이벤트가 수신되었습니다.",
            "event": "merge_request",
            "scan_job_id": scan_job_id,
        }

    # 지원하지 않는 이벤트는 무시 (200 반환)
    return {
        "message": "지원하지 않는 이벤트입니다.",
        "event": x_gitlab_event,
        "scan_job_id": None,
    }
