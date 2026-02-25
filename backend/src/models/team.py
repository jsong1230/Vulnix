"""Team / TeamMember 모델 — 팀 및 멤버 관계"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.repository import Repository
    from src.models.user import User


class Team(UUIDMixin, Base):
    """팀 테이블.

    여러 사용자가 하나의 팀에 소속되어 저장소를 공유한다.
    """

    __tablename__ = "team"
    __table_args__ = {"comment": "사용자 팀"}

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="팀명",
    )
    plan: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="starter",
        comment="플랜 (starter / growth / scale / enterprise)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="생성 시각 (UTC)",
    )

    # 관계
    members: Mapped[list["TeamMember"]] = relationship(
        "TeamMember",
        back_populates="team",
        cascade="all, delete-orphan",
    )
    repositories: Mapped[list["Repository"]] = relationship(  # noqa: F821
        "Repository",
        back_populates="team",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Team id={self.id} name={self.name}>"


class TeamMember(UUIDMixin, Base):
    """팀 멤버 관계 테이블.

    User와 Team의 다대다 관계를 나타내며, 역할(role)을 포함한다.
    """

    __tablename__ = "team_member"
    __table_args__ = {"comment": "팀-사용자 멤버십"}

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("team.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="팀 ID (FK)",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="사용자 ID (FK)",
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="member",
        comment="역할 (owner / admin / member)",
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="팀 가입 시각",
    )

    # 관계
    team: Mapped["Team"] = relationship("Team", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="team_memberships")  # noqa: F821

    def __repr__(self) -> str:
        return f"<TeamMember team_id={self.team_id} user_id={self.user_id} role={self.role}>"
