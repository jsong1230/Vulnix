"""알림 설정/로그 요청·응답 스키마"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# 허용 플랫폼 타입
PlatformType = Literal["slack", "teams"]
# 심각도 임계값 타입
SeverityThresholdType = Literal["critical", "high", "medium", "all"]


class NotificationConfigCreate(BaseModel):
    """알림 설정 생성 요청 스키마"""

    platform: PlatformType = Field(description="알림 플랫폼 (slack / teams)")
    webhook_url: str = Field(
        min_length=10,
        max_length=2000,
        description="Webhook URL (HTTPS 필수, slack.com 또는 office.com 도메인)",
    )
    severity_threshold: SeverityThresholdType = Field(
        default="all",
        description="알림 발송 기준 심각도 (critical / high / medium / all)",
    )
    weekly_report_enabled: bool = Field(
        default=False,
        description="주간 리포트 발송 여부",
    )
    weekly_report_day: int = Field(
        default=1,
        ge=1,
        le=7,
        description="주간 리포트 발송 요일 (1=월 ~ 7=일)",
    )


class NotificationConfigUpdate(BaseModel):
    """알림 설정 수정 요청 스키마 (부분 업데이트)"""

    webhook_url: str | None = Field(
        default=None,
        min_length=10,
        max_length=2000,
        description="Webhook URL (HTTPS 필수)",
    )
    severity_threshold: SeverityThresholdType | None = Field(
        default=None,
        description="알림 발송 기준 심각도",
    )
    weekly_report_enabled: bool | None = Field(
        default=None,
        description="주간 리포트 발송 여부",
    )
    weekly_report_day: int | None = Field(
        default=None,
        ge=1,
        le=7,
        description="주간 리포트 발송 요일 (1=월 ~ 7=일)",
    )
    is_active: bool | None = Field(
        default=None,
        description="활성 여부",
    )


class NotificationConfigResponse(BaseModel):
    """알림 설정 응답 스키마"""

    id: uuid.UUID
    team_id: uuid.UUID
    platform: str
    webhook_url: str
    severity_threshold: str
    weekly_report_enabled: bool
    weekly_report_day: int
    is_active: bool
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotificationLogResponse(BaseModel):
    """알림 발송 이력 응답 스키마"""

    id: uuid.UUID
    team_id: uuid.UUID
    config_id: uuid.UUID | None = None
    notification_type: str
    status: str
    http_status: int | None = None
    error_message: str | None = None
    payload: dict | None = None
    sent_at: datetime

    model_config = {"from_attributes": True}
