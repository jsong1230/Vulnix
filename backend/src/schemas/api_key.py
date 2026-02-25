"""API Key Pydantic 스키마 — 생성/응답 데이터 검증"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    """API Key 생성 요청 스키마."""

    name: str = Field(..., min_length=1, max_length=255, description="키 이름")
    expires_in_days: int | None = Field(
        default=None,
        ge=1,
        le=36500,
        description="만료 기간 (일 단위, 미입력 시 무기한)",
    )


class ApiKeyResponse(BaseModel):
    """API Key 응답 스키마 — key_value 미포함 (목록 조회용)."""

    id: uuid.UUID
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApiKeyCreateResponse(ApiKeyResponse):
    """API Key 생성 응답 스키마 — 발급 시 한 번만 반환되는 원본 key 포함."""

    key: str = Field(..., description="원본 API Key (vx_live_... 형식, 일회성 표시)")
    key_prefix: str = Field(..., description="앞 12자리 (이후 조회 시 이 값만 노출)")


class ApiKeyRevokeResponse(BaseModel):
    """API Key 비활성화 응답 스키마."""

    id: uuid.UUID
    name: str
    is_active: bool
    revoked_at: datetime | None = None

    model_config = {"from_attributes": True}
