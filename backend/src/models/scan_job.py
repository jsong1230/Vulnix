"""ScanJob 모델 — 스캔 작업 생명주기 관리"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class ScanJob(UUIDMixin, TimestampMixin, Base):
    """스캔 작업 테이블.

    상태 머신: queued -> running -> completed / failed
    실패 시 최대 3회 재시도.
    """

    __tablename__ = "scan_job"
    __table_args__ = {"comment": "스캔 작업"}

    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repository.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="대상 저장소 ID (FK)",
    )

    # 스캔 상태: queued / running / completed / failed
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
        index=True,
        comment="스캔 상태 (queued / running / completed / failed)",
    )

    # 트리거 유형: webhook / manual / schedule
    trigger_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="스캔 트리거 유형 (webhook / manual / schedule)",
    )

    commit_sha: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        comment="대상 커밋 SHA (40자)",
    )
    branch: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="대상 브랜치 이름",
    )
    pr_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="PR 트리거 시 GitHub PR 번호",
    )

    # F-01: 스캔 유형 (full / incremental / pr / initial)
    scan_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="incremental",
        comment="스캔 유형 (full / incremental / pr / initial)",
    )

    # F-01: 재시도 횟수
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="현재 재시도 횟수",
    )

    # F-01: PR/push 시 변경된 파일 목록 (JSONB)
    changed_files: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="PR/push 시 변경된 파일 목록",
    )

    # 스캔 결과 통계
    findings_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Semgrep 탐지 건수",
    )
    true_positives_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="LLM이 확정한 실제 취약점 건수",
    )
    false_positives_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="LLM이 오탐으로 분류한 건수",
    )
    auto_filtered_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="오탐 패턴으로 자동 필터링된 건수",
    )
    duration_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="스캔 소요 시간 (초)",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="실패 시 에러 메시지",
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="스캔 시작 시각",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="스캔 완료 시각",
    )

    # 관계
    repository: Mapped["Repository"] = relationship(  # noqa: F821
        "Repository",
        back_populates="scan_jobs",
    )
    vulnerabilities: Mapped[list["Vulnerability"]] = relationship(  # noqa: F821
        "Vulnerability",
        back_populates="scan_job",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ScanJob id={self.id} status={self.status} repo_id={self.repo_id}>"
