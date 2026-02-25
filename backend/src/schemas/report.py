"""리포트 관련 요청·응답 스키마 및 데이터클래스"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


# 허용 리포트 유형
ReportTypeEnum = Literal["ciso", "csap", "iso27001", "isms"]
# 허용 스케줄 주기
ScheduleEnum = Literal["weekly", "monthly", "quarterly"]
# 허용 포맷
FormatEnum = Literal["pdf", "json"]


# ──────────────────────────────────────────────────────────────
# ReportData 데이터클래스 (서비스 레이어 내부 사용)
# ──────────────────────────────────────────────────────────────


@dataclass
class ReportData:
    """리포트 생성에 필요한 집계 데이터."""

    team_name: str
    period_start: date
    period_end: date

    # 저장소 정보
    repositories: list = field(default_factory=list)
    total_repo_count: int = 0

    # 취약점 통계
    total_vulnerabilities: int = 0
    new_vulnerabilities: int = 0
    resolved_vulnerabilities: int = 0
    severity_distribution: dict = field(
        default_factory=lambda: {"critical": 0, "high": 0, "medium": 0, "low": 0}
    )
    status_distribution: dict = field(
        default_factory=lambda: {"open": 0, "patched": 0, "ignored": 0, "false_positive": 0}
    )
    resolution_rate: float = 0.0
    vulnerability_type_top10: list = field(default_factory=list)

    # 보안 점수
    current_security_score: float = 0.0
    previous_security_score: float = 0.0
    score_trend: list = field(default_factory=list)

    # 대응 현황
    avg_response_time_hours: float = 0.0
    auto_patch_rate: float = 0.0
    repo_score_ranking: list = field(default_factory=list)

    # 스캔 이력
    scan_jobs: list = field(default_factory=list)
    total_scans: int = 0

    # 패치 이력
    patch_prs: list = field(default_factory=list)

    # 미조치 취약점 (인증 증적용)
    unresolved_critical: list = field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# ReportConfig 스키마
# ──────────────────────────────────────────────────────────────


class ReportConfigCreate(BaseModel):
    """리포트 스케줄 설정 생성 요청 스키마"""

    report_type: ReportTypeEnum = Field(
        description="리포트 유형 (ciso / csap / iso27001 / isms)"
    )
    schedule: ScheduleEnum = Field(
        description="생성 주기 (weekly / monthly / quarterly)"
    )
    email_recipients: list[EmailStr] = Field(
        default_factory=list,
        description="수신자 이메일 목록",
    )
    is_active: bool = Field(
        default=True,
        description="스케줄 활성화 여부",
    )


class ReportConfigUpdate(BaseModel):
    """리포트 스케줄 설정 수정 요청 스키마 (부분 업데이트)"""

    schedule: ScheduleEnum | None = Field(
        default=None,
        description="생성 주기",
    )
    email_recipients: list[EmailStr] | None = Field(
        default=None,
        description="수신자 이메일 목록",
    )
    is_active: bool | None = Field(
        default=None,
        description="스케줄 활성화 여부",
    )


class ReportConfigResponse(BaseModel):
    """리포트 스케줄 설정 응답 스키마"""

    id: uuid.UUID
    team_id: uuid.UUID
    report_type: str
    schedule: str
    email_recipients: list
    is_active: bool
    last_generated_at: datetime | None = None
    next_generation_at: datetime | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────────────────────
# ReportHistory 스키마
# ──────────────────────────────────────────────────────────────


class ReportHistoryResponse(BaseModel):
    """리포트 이력 응답 스키마"""

    id: uuid.UUID
    config_id: uuid.UUID | None = None
    team_id: uuid.UUID
    report_type: str
    format: str
    file_path: str | None = None
    file_size_bytes: int | None = None
    period_start: date
    period_end: date
    status: str
    email_sent_at: datetime | None = None
    email_recipients: list | None = None
    error_message: str | None = None
    # ORM 속성명은 report_meta (SQLAlchemy 예약어 충돌 방지), API 응답은 metadata
    metadata: dict | None = None
    generated_by: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


# ──────────────────────────────────────────────────────────────
# 리포트 생성 요청/응답 스키마
# ──────────────────────────────────────────────────────────────


class GenerateReportRequest(BaseModel):
    """리포트 수동 생성 요청 스키마"""

    report_type: ReportTypeEnum = Field(
        description="리포트 유형 (ciso / csap / iso27001 / isms)"
    )
    period_start: date = Field(description="리포트 대상 기간 시작일")
    period_end: date = Field(description="리포트 대상 기간 종료일")
    format: FormatEnum = Field(
        default="pdf",
        description="파일 포맷 (pdf / json)",
    )
    send_email: bool = Field(
        default=False,
        description="이메일 발송 여부",
    )
    email_recipients: list[EmailStr] = Field(
        default_factory=list,
        description="이메일 수신자 목록 (send_email=True 시 필수)",
    )

    @model_validator(mode="after")
    def validate_period_and_email(self) -> "GenerateReportRequest":
        """기간 유효성 및 이메일 수신자 검증."""
        # 시작일이 종료일보다 늦으면 오류
        if self.period_start > self.period_end:
            raise ValueError("period_start는 period_end보다 이전이어야 합니다.")

        # 1년 초과 기간 금지
        delta_days = (self.period_end - self.period_start).days
        if delta_days > 366:
            raise ValueError("리포트 기간은 1년을 초과할 수 없습니다.")

        # send_email=True이면 수신자 필수
        if self.send_email and not self.email_recipients:
            raise ValueError("send_email=True 시 email_recipients가 필요합니다.")

        return self


class GenerateReportResponse(BaseModel):
    """리포트 생성 요청 응답 스키마 (202 반환용)"""

    report_id: uuid.UUID
    status: str
    report_type: str
    estimated_completion_seconds: int = 30
