"""리포트 이력 모델 — ReportHistory"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ReportHistory(Base):
    """리포트 생성 이력 테이블.

    생성된 리포트의 파일 경로, 상태, 이메일 발송 결과를 기록한다.
    """

    __tablename__ = "report_history"
    __table_args__ = {"comment": "리포트 생성 이력"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="기본 키 (UUID v4)",
    )
    config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("report_config.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="설정 ID (FK, 스케줄 생성 시 참조)",
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
    # 파일 포맷: pdf / json
    format: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="파일 포맷 (pdf / json)",
    )
    file_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="파일 경로 (로컬) 또는 S3 URL",
    )
    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="파일 크기 (bytes)",
    )
    period_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="리포트 대상 기간 시작일",
    )
    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="리포트 대상 기간 종료일",
    )
    # 상태: generating / completed / failed / sent
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=lambda: "generating",
        server_default="generating",
        comment="리포트 생성 상태 (generating / completed / failed / sent)",
    )
    email_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="이메일 발송 시각 (UTC)",
    )
    email_recipients: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="실제 발송된 수신자 목록 (JSON 배열)",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="생성 실패 시 에러 메시지",
    )
    # SQLAlchemy 예약어 'metadata' 충돌 방지: ORM 속성명은 report_meta
    report_meta: Mapped[dict | None] = mapped_column(
        "metadata",  # 실제 DB 컬럼명
        JSONB,
        nullable=True,
        comment="리포트 요약 메타데이터 (보안 점수, 취약점 수 등)",
    )
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        comment="수동 생성 사용자 ID (스케줄 생성은 NULL)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
        comment="생성 시각 (UTC)",
    )

    def __init__(self, **kwargs: object) -> None:
        # Python 레벨 기본값 설정 (DB flush 전에도 적용)
        if "status" not in kwargs:
            kwargs["status"] = "generating"
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return (
            f"<ReportHistory id={self.id} "
            f"type={self.report_type} status={self.status}>"
        )
