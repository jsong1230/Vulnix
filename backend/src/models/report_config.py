"""리포트 설정 모델 — ReportConfig"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ReportConfig(Base):
    """리포트 자동 생성 스케줄 설정 테이블.

    팀 단위로 리포트 유형, 생성 주기, 수신자를 설정한다.
    (team_id, report_type) 쌍은 유일해야 한다.
    """

    __tablename__ = "report_config"
    __table_args__ = (
        UniqueConstraint("team_id", "report_type", name="uq_report_config_team_type"),
        {"comment": "리포트 자동 생성 스케줄 설정"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="기본 키 (UUID v4)",
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("team.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="소속 팀 ID (FK)",
    )
    # 리포트 유형: ciso / csap / iso27001 / isms
    report_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="리포트 유형 (ciso / csap / iso27001 / isms)",
    )
    # 생성 주기: weekly / monthly / quarterly
    schedule: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="생성 주기 (weekly / monthly / quarterly)",
    )
    email_recipients: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment="수신자 이메일 목록 (JSON 배열)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=lambda: True,
        server_default="true",
        comment="스케줄 활성화 여부",
    )
    last_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="마지막 생성 시각 (UTC)",
    )
    next_generation_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="다음 생성 예정 시각 (UTC)",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        comment="설정 생성 사용자 ID (FK)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="생성 시각 (UTC)",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="수정 시각 (UTC)",
    )

    def __init__(self, **kwargs: object) -> None:
        # Python 레벨 기본값 설정 (DB flush 전에도 적용)
        if "is_active" not in kwargs:
            kwargs["is_active"] = True
        if "email_recipients" not in kwargs:
            kwargs["email_recipients"] = []
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return (
            f"<ReportConfig id={self.id} "
            f"type={self.report_type} schedule={self.schedule}>"
        )
