"""SQLAlchemy 2.0 DeclarativeBase + 공통 컬럼 믹스인"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """모든 SQLAlchemy 모델의 기반 클래스"""
    pass


class TimestampMixin:
    """created_at / updated_at 공통 컬럼 믹스인"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="생성 시각 (UTC)",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="수정 시각 (UTC)",
    )


class UUIDMixin:
    """UUID 기본 키 믹스인"""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="기본 키 (UUID v4)",
    )
