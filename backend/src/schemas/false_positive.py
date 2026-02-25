"""오탐 패턴 요청/응답 스키마"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FalsePositivePatternCreate(BaseModel):
    """오탐 패턴 생성 요청 스키마"""

    semgrep_rule_id: str = Field(
        min_length=1,
        max_length=200,
        description="대상 Semgrep 룰 ID",
    )
    file_pattern: str | None = Field(
        default=None,
        max_length=500,
        description="glob 패턴 (null이면 모든 파일 대상)",
    )
    reason: str | None = Field(
        default=None,
        description="오탐으로 판단한 사유",
    )


class FalsePositivePatternResponse(BaseModel):
    """오탐 패턴 응답 스키마"""

    id: uuid.UUID
    team_id: uuid.UUID
    semgrep_rule_id: str
    file_pattern: str | None
    reason: str | None
    is_active: bool
    matched_count: int
    last_matched_at: datetime | None = None
    created_by: uuid.UUID | None = None
    source_vulnerability_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
