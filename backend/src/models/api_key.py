"""API Key 모델 — IDE 플러그인 인증용 팀 단위 API Key"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ApiKey(Base):
    """IDE API Key 테이블.

    팀 단위로 발급되며, 원본 키는 발급 시 한 번만 노출.
    DB에는 SHA-256 해시만 저장. (ADR-F11-004)
    """

    __tablename__ = "api_key"
    __table_args__ = {"comment": "IDE 플러그인 인증용 팀 단위 API Key"}

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
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="키 이름 (사용자 지정)",
    )
    key_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="SHA-256 해시 (원본 키 미저장)",
    )
    key_prefix: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="키 앞 12자리 (조회 시 표시용)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="활성 여부",
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="마지막 사용 시각 (UTC)",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="만료 일시 (NULL이면 무기한)",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        comment="발급자 ID (FK)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="생성 시각 (UTC)",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="비활성화 시각 (논리 삭제)",
    )

    def __repr__(self) -> str:
        return (
            f"<ApiKey id={self.id} "
            f"name={self.name} active={self.is_active}>"
        )
