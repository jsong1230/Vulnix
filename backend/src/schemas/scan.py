"""스캔 관련 요청/응답 스키마"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ScanTriggerRequest(BaseModel):
    """수동 스캔 트리거 요청"""

    repo_id: uuid.UUID = Field(description="스캔할 저장소 ID")
    branch: str | None = Field(default=None, description="스캔할 브랜치 (기본: default_branch)")
    commit_sha: str | None = Field(default=None, min_length=40, max_length=40, description="특정 커밋 SHA")


class ScanJobResponse(BaseModel):
    """스캔 작업 응답"""

    id: uuid.UUID
    repo_id: uuid.UUID
    status: Literal["queued", "running", "completed", "failed"]
    trigger_type: Literal["webhook", "manual", "schedule"]
    commit_sha: str | None
    branch: str | None
    pr_number: int | None
    findings_count: int
    true_positives_count: int
    false_positives_count: int
    duration_seconds: int | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScanStatusResponse(BaseModel):
    """스캔 상태 간략 응답"""

    id: uuid.UUID
    status: Literal["queued", "running", "completed", "failed"]
    progress_message: str | None = None

    model_config = {"from_attributes": True}
