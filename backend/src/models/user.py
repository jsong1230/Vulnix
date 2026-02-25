"""User 모델 — GitHub OAuth 사용자"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from src.models.team import TeamMember

from src.models.base import Base, TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    """사용자 테이블.

    GitHub OAuth 로그인으로 생성되며, 팀 소속을 통해 저장소에 접근한다.
    """

    __tablename__ = "user"
    __table_args__ = {"comment": "GitHub OAuth 사용자"}

    # GitHub 식별자
    github_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
        comment="GitHub 사용자 ID",
    )
    github_login: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="GitHub 로그인명 (username)",
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="이메일 (GitHub에서 공개된 경우)",
    )
    avatar_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="GitHub 프로필 이미지 URL",
    )

    # 암호화된 GitHub Access Token (AES-256)
    # TODO: 저장 시 암호화, 조회 시 복호화 처리
    access_token_enc: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="암호화된 GitHub Access Token (AES-256)",
    )

    # 관계 (역참조)
    team_memberships: Mapped[list["TeamMember"]] = relationship(  # noqa: F821
        "TeamMember",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} github_login={self.github_login}>"
