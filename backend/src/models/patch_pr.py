"""PatchPR 모델 — 자동 생성된 보안 패치 PR"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.vulnerability import Vulnerability
    from src.models.repository import Repository


class PatchPR(UUIDMixin, Base):
    """패치 PR 테이블.

    LLM이 생성한 패치를 GitHub PR로 자동 제출한 기록.
    취약점 1개당 최대 1개의 패치 PR.
    """

    __tablename__ = "patch_pr"
    __table_args__ = {"comment": "자동 생성 보안 패치 PR"}

    vulnerability_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vulnerability.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        comment="대상 취약점 ID (FK, 1:1)",
    )
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repository.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="저장소 ID (FK)",
    )

    # GitHub PR 정보
    github_pr_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="GitHub PR 번호",
    )
    github_pr_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="GitHub PR URL",
    )
    branch_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="패치 브랜치명 (예: vulnix/fix-sql-injection-a1b2c3)",
    )

    # PR 상태: created / merged / closed / rejected
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="created",
        comment="PR 상태 (created / merged / closed / rejected)",
    )

    # 패치 내용
    patch_diff: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="unified diff 형식 패치 내용",
    )
    patch_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="패치 설명 (PR 본문에 포함)",
    )
    test_suggestion: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="LLM이 제안한 테스트 코드 (선택적)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="PR 생성 시각",
    )
    merged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="PR 머지 시각",
    )

    # 관계
    vulnerability: Mapped["Vulnerability"] = relationship(  # noqa: F821
        "Vulnerability",
        back_populates="patch_pr",
    )
    repository: Mapped["Repository"] = relationship("Repository")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<PatchPR id={self.id} github_pr_number={self.github_pr_number} "
            f"status={self.status}>"
        )
