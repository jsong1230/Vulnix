"""알림 설정/로그 엔드포인트 — Slack/Teams webhook 알림 관리"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import CurrentUser, DbSession
from src.models.notification import NotificationConfig, NotificationLog
from src.models.team import TeamMember
from src.schemas.common import ApiResponse
from src.schemas.notification import (
    NotificationConfigCreate,
    NotificationConfigResponse,
    NotificationConfigUpdate,
    NotificationLogResponse,
)
from src.services.notification_service import NotificationService, validate_webhook_url

router = APIRouter()

# NotificationService 싱글톤
_notification_service = NotificationService()


# ──────────────────────────────────────────────────────────────
# DB 헬퍼 함수
# ──────────────────────────────────────────────────────────────


async def get_user_team_role(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> tuple[uuid.UUID | None, str | None]:
    """(team_id, role) 반환. 팀 없으면 (None, None)."""
    result = await db.execute(
        select(TeamMember.team_id, TeamMember.role)
        .where(TeamMember.user_id == user_id)
        .limit(1)
    )
    row = result.first()
    if row is None:
        return None, None
    return row[0], row[1]


async def get_user_team_id(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> uuid.UUID | None:
    """사용자의 팀 ID만 반환한다."""
    result = await db.execute(
        select(TeamMember.team_id)
        .where(TeamMember.user_id == user_id)
        .limit(1)
    )
    return result.scalar_one_or_none()


def _require_admin_role(team_id: uuid.UUID | None, role: str | None) -> uuid.UUID:
    """팀 소속 및 owner/admin 권한을 검증한다.

    Raises:
        HTTPException: 403 - 팀 없음 또는 권한 부족
    """
    if team_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="팀에 속하지 않은 사용자입니다.",
        )
    if role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin/owner 권한이 필요합니다.",
        )
    return team_id


# ──────────────────────────────────────────────────────────────
# 엔드포인트
# ──────────────────────────────────────────────────────────────


@router.post(
    "/config",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[NotificationConfigResponse],
)
async def create_notification_config(
    data: NotificationConfigCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[NotificationConfigResponse]:
    """알림 설정 생성.

    팀의 Slack/Teams webhook 알림 설정을 등록한다.
    owner/admin 권한이 필요하다.
    webhook_url은 SSRF 방어를 위해 허용 도메인 및 내부 IP 검증을 수행한다.
    """
    team_id, role = await get_user_team_role(db, current_user.id)
    _require_admin_role(team_id, role)

    # webhook URL 유효성 검증
    if not validate_webhook_url(data.webhook_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 webhook URL입니다. HTTPS 필수, 허용 도메인: slack.com, office.com",
        )

    config = NotificationConfig(
        id=uuid.uuid4(),
        team_id=team_id,
        platform=data.platform,
        webhook_url=data.webhook_url,
        severity_threshold=data.severity_threshold,
        weekly_report_enabled=data.weekly_report_enabled,
        weekly_report_day=data.weekly_report_day,
        is_active=True,
        created_by=current_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(config)
    await db.flush()
    await db.commit()

    return ApiResponse(
        success=True,
        data=NotificationConfigResponse.model_validate(config),
        error=None,
    )


@router.get(
    "/config",
    response_model=ApiResponse[list[NotificationConfigResponse]],
)
async def list_notification_configs(
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[list[NotificationConfigResponse]]:
    """알림 설정 목록 조회.

    현재 사용자의 팀에 등록된 알림 설정 전체를 반환한다.
    팀에 소속되지 않은 경우 빈 목록을 반환한다.
    """
    team_id = await get_user_team_id(db, current_user.id)
    if team_id is None:
        return ApiResponse(success=True, data=[], error=None)

    result = await db.execute(
        select(NotificationConfig).where(NotificationConfig.team_id == team_id)
    )
    configs = list(result.scalars().all())

    return ApiResponse(
        success=True,
        data=[NotificationConfigResponse.model_validate(c) for c in configs],
        error=None,
    )


@router.patch(
    "/config/{config_id}",
    response_model=ApiResponse[NotificationConfigResponse],
)
async def update_notification_config(
    config_id: uuid.UUID,
    data: NotificationConfigUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[NotificationConfigResponse]:
    """알림 설정 수정.

    지정된 알림 설정의 필드를 부분 업데이트한다.
    owner/admin 권한이 필요하다.
    """
    team_id, role = await get_user_team_role(db, current_user.id)
    _require_admin_role(team_id, role)

    result = await db.execute(
        select(NotificationConfig).where(
            NotificationConfig.id == config_id,
            NotificationConfig.team_id == team_id,
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="알림 설정을 찾을 수 없습니다.",
        )

    # webhook_url 변경 시 유효성 재검증
    if data.webhook_url is not None:
        if not validate_webhook_url(data.webhook_url):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않은 webhook URL입니다.",
            )
        config.webhook_url = data.webhook_url

    if data.severity_threshold is not None:
        config.severity_threshold = data.severity_threshold
    if data.weekly_report_enabled is not None:
        config.weekly_report_enabled = data.weekly_report_enabled
    if data.weekly_report_day is not None:
        config.weekly_report_day = data.weekly_report_day
    if data.is_active is not None:
        config.is_active = data.is_active

    config.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()

    return ApiResponse(
        success=True,
        data=NotificationConfigResponse.model_validate(config),
        error=None,
    )


@router.delete(
    "/config/{config_id}",
    response_model=ApiResponse[NotificationConfigResponse],
)
async def delete_notification_config(
    config_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[NotificationConfigResponse]:
    """알림 설정 삭제.

    지정된 알림 설정을 영구 삭제한다.
    owner/admin 권한이 필요하다.
    """
    team_id, role = await get_user_team_role(db, current_user.id)
    _require_admin_role(team_id, role)

    result = await db.execute(
        select(NotificationConfig).where(
            NotificationConfig.id == config_id,
            NotificationConfig.team_id == team_id,
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="알림 설정을 찾을 수 없습니다.",
        )

    response_data = NotificationConfigResponse.model_validate(config)
    await db.delete(config)
    await db.commit()

    return ApiResponse(
        success=True,
        data=response_data,
        error=None,
    )


@router.post(
    "/config/{config_id}/test",
    response_model=ApiResponse[dict],
)
async def send_test_notification(
    config_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[dict]:
    """테스트 알림 발송.

    지정된 설정으로 테스트 메시지를 발송한다.
    webhook 연결 상태를 즉시 확인할 수 있다.
    """
    team_id = await get_user_team_id(db, current_user.id)
    if team_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="팀에 속하지 않은 사용자입니다.",
        )

    result = await db.execute(
        select(NotificationConfig).where(
            NotificationConfig.id == config_id,
            NotificationConfig.team_id == team_id,
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="알림 설정을 찾을 수 없습니다.",
        )

    # 플랫폼별 테스트 payload 생성
    if config.platform == "slack":
        test_payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ":white_check_mark: *Vulnix 알림 테스트* — 연결이 정상입니다.",
                    },
                }
            ]
        }
    else:
        test_payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "contentUrl": None,
                    "content": {
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": "Vulnix 알림 테스트 — 연결이 정상입니다.",
                                "weight": "Bolder",
                            }
                        ],
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    },
                }
            ],
        }

    success, http_status, error_msg = await _notification_service._send_webhook(
        url=config.webhook_url,
        payload=test_payload,
        platform=config.platform,
    )

    return ApiResponse(
        success=True,
        data={
            "sent": success,
            "http_status": http_status,
            "error": error_msg,
            "platform": config.platform,
        },
        error=None,
    )


@router.get(
    "/logs",
    response_model=ApiResponse[list[NotificationLogResponse]],
)
async def list_notification_logs(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(default=1, ge=1, description="페이지 번호"),
    per_page: int = Query(default=20, ge=1, le=100, description="페이지당 항목 수"),
    status: str | None = Query(default=None, description="상태 필터 (sent / failed)"),
) -> ApiResponse[list[NotificationLogResponse]]:
    """알림 발송 이력 조회.

    현재 사용자 팀의 알림 발송 이력을 최신순으로 반환한다.
    팀에 소속되지 않은 경우 빈 목록을 반환한다.
    """
    team_id = await get_user_team_id(db, current_user.id)
    if team_id is None:
        return ApiResponse(success=True, data=[], error=None)

    query = select(NotificationLog).where(NotificationLog.team_id == team_id)

    if status is not None:
        query = query.where(NotificationLog.status == status)

    query = (
        query.order_by(NotificationLog.sent_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )

    result = await db.execute(query)
    logs = list(result.scalars().all())

    return ApiResponse(
        success=True,
        data=[NotificationLogResponse.model_validate(log) for log in logs],
        error=None,
    )
