"""오탐 패턴 모델 — FalsePositivePattern, FalsePositiveLog"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class FalsePositivePattern(Base):
    """오탐 패턴 테이블.

    팀 단위로 공유되는 오탐 규칙.
    Semgrep rule_id + file_pattern(glob) 복합 매칭으로 자동 필터링에 활용.
    """

    __tablename__ = "false_positive_pattern"
    __table_args__ = {"comment": "오탐 패턴 (팀 단위 공유)"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="기본 키 (UUID v4)",
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="소속 팀 ID",
    )
    semgrep_rule_id: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="대상 Semgrep 룰 ID",
    )
    file_pattern: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="glob 패턴 (null이면 모든 파일 대상)",
    )
    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="오탐으로 판단한 사유",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="활성 여부 (소프트 삭제용)",
    )
    matched_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="이 패턴으로 자동 필터링된 횟수",
    )
    last_matched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="마지막 매칭 시각",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="패턴 등록자 ID",
    )
    source_vulnerability_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vulnerability.id", ondelete="SET NULL"),
        nullable=True,
        comment="원본 취약점 ID (상태 변경으로 생성된 경우)",
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
    logs: Mapped[list["FalsePositiveLog"]] = relationship(
        "FalsePositiveLog",
        back_populates="pattern",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<FalsePositivePattern id={self.id} "
            f"rule={self.semgrep_rule_id} active={self.is_active}>"
        )


class FalsePositiveLog(Base):
    """오탐 자동 필터링 이력 테이블.

    FPFilterService가 finding을 필터링할 때마다 기록.
    오탐 피드백이 탐지 엔진 정확도 향상에 반영됨을 추적.
    """

    __tablename__ = "false_positive_log"
    __table_args__ = {"comment": "오탐 자동 필터링 이력"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="기본 키 (UUID v4)",
    )
    pattern_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("false_positive_pattern.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="매칭된 패턴 ID (FK)",
    )
    scan_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_job.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="스캔 작업 ID (FK)",
    )
    semgrep_rule_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="필터링된 Semgrep 룰 ID",
    )
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="필터링된 파일 경로",
    )
    start_line: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="필터링된 코드 시작 라인",
    )
    filtered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="필터링 시각",
    )

    # 관계
    pattern: Mapped["FalsePositivePattern"] = relationship(
        "FalsePositivePattern",
        back_populates="logs",
    )

    def __repr__(self) -> str:
        return (
            f"<FalsePositiveLog id={self.id} "
            f"pattern_id={self.pattern_id} rule={self.semgrep_rule_id}>"
        )
