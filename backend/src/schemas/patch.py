"""패치 PR 요청/응답 스키마 — F-03 자동 패치 PR 생성"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from src.schemas.vulnerability import VulnerabilitySummary


class PatchPRResponse(BaseModel):
    """패치 PR 응답 스키마"""

    id: uuid.UUID
    vulnerability_id: uuid.UUID
    repo_id: uuid.UUID
    github_pr_number: int | None
    github_pr_url: str | None
    branch_name: str | None
    status: Literal["created", "merged", "closed", "rejected"]
    patch_diff: str | None
    patch_description: str | None
    created_at: datetime
    merged_at: datetime | None

    model_config = {"from_attributes": True}


class PatchPRDetailResponse(PatchPRResponse):
    """패치 PR 상세 응답 스키마 (취약점 정보 포함)"""

    vulnerability: VulnerabilitySummary | None = None
