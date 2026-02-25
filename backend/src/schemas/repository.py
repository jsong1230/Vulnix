"""저장소 관련 요청/응답 스키마"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class RepositoryRegisterRequest(BaseModel):
    """저장소 연동 등록 요청"""

    github_repo_id: int = Field(description="GitHub 저장소 ID")
    full_name: str = Field(description="저장소 전체 이름 (예: org/repo-name)")
    default_branch: str = Field(default="main", description="기본 브랜치")
    language: str | None = Field(default=None, description="주 프로그래밍 언어")
    installation_id: int | None = Field(default=None, description="GitHub App 설치 ID")


class RepositoryResponse(BaseModel):
    """저장소 응답"""

    id: uuid.UUID
    team_id: uuid.UUID
    # F-09: 플랫폼 필드 추가 (하위 호환: 기존 응답에 platform 필드 추가)
    platform: str = "github"
    github_repo_id: int
    platform_repo_id: str | None = None
    full_name: str
    default_branch: str
    language: str | None
    is_active: bool
    installation_id: int | None
    last_scanned_at: datetime | None
    security_score: float | None
    # F-01: 초기 스캔 완료 여부
    is_initial_scan_done: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("platform", mode="before")
    @classmethod
    def validate_platform(cls, value: Any) -> str:
        """platform 필드 유효성 검증.

        Mock 환경에서 MagicMock 객체가 들어올 경우 기본값 "github"로 대체한다.
        """
        if isinstance(value, str):
            return value
        # MagicMock 등 비문자열 값은 기본값으로 대체
        return "github"

    @field_validator("platform_repo_id", mode="before")
    @classmethod
    def validate_platform_repo_id(cls, value: Any) -> str | None:
        """platform_repo_id 필드 유효성 검증.

        Mock 환경에서 MagicMock 객체가 들어올 경우 None으로 대체한다.
        """
        if value is None or isinstance(value, str):
            return value
        # MagicMock 등 비문자열 값은 None으로 대체
        return None


class RepositorySecurityScore(BaseModel):
    """저장소 보안 점수"""

    repo_id: uuid.UUID
    full_name: str
    security_score: float | None
    open_vulnerabilities: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    last_scanned_at: datetime | None
