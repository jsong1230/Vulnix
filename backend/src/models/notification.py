"""알림 설정/로그 모델 — NotificationConfig, NotificationLog"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class NotificationConfig(Base):
    """알림 설정 테이블.

    팀 단위로 Slack/Teams webhook 알림을 설정한다.
    severity_threshold로 발송 기준 심각도를 조절한다.
    """

    __tablename__ = "notification_config"
    __table_args__ = {"comment": "알림 설정 (팀 단위 Slack/Teams webhook)"}

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
    # 플랫폼: slack / teams
    platform: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="알림 플랫폼 (slack / teams)",
    )
    webhook_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Webhook URL (HTTPS 필수)",
    )
    # 심각도 임계값: critical / high / medium / all
    severity_threshold: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="all",
        comment="알림 발송 기준 심각도 (critical / high / medium / all)",
    )
    weekly_report_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="주간 리포트 발송 여부",
    )
    # 주간 리포트 발송 요일: 1(월)~7(일) ISO 기준
    weekly_report_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="주간 리포트 발송 요일 (1=월 ~ 7=일)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="활성 여부",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        comment="등록자 ID (FK)",
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

    # 관계
    logs: Mapped[list["NotificationLog"]] = relationship(
        "NotificationLog",
        back_populates="config",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationConfig id={self.id} "
            f"platform={self.platform} threshold={self.severity_threshold}>"
        )


class NotificationLog(Base):
    """알림 발송 이력 테이블.

    NotificationService가 webhook을 발송할 때마다 결과를 기록한다.
    발송 실패 원인 추적 및 재발송 판단에 활용된다.
    """

    __tablename__ = "notification_log"
    __table_args__ = {"comment": "알림 발송 이력"}

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
    config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notification_config.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="알림 설정 ID (FK)",
    )
    # 알림 유형: vulnerability / weekly_report
    notification_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="알림 유형 (vulnerability / weekly_report)",
    )
    # 발송 상태: sent / failed
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="발송 상태 (sent / failed)",
    )
    http_status: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="HTTP 응답 상태 코드",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="오류 메시지 (실패 시)",
    )
    payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="발송된 페이로드 (JSON)",
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
        comment="발송 시각 (UTC)",
    )

    # 관계
    config: Mapped["NotificationConfig | None"] = relationship(
        "NotificationConfig",
        back_populates="logs",
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationLog id={self.id} "
            f"type={self.notification_type} status={self.status}>"
        )
