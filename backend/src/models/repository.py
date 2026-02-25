"""Repository 모델 — GitHub / GitLab / Bitbucket 저장소 연동 정보"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.team import Team
    from src.models.scan_job import ScanJob
    from src.models.vulnerability import Vulnerability


class Repository(UUIDMixin, TimestampMixin, Base):
    """저장소 테이블.

    GitHub / GitLab / Bitbucket 저장소 연동 정보를 관리한다.
    팀에 소속되며, 여러 스캔 작업을 가진다.
    """

    __tablename__ = "repository"
    __table_args__ = {"comment": "Git 플랫폼 연동 저장소 (GitHub / GitLab / Bitbucket)"}

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("team.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="소속 팀 ID (FK)",
    )

    # F-09: 플랫폼 정보 컬럼
    platform: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="github",
        server_default="github",
        index=True,
        comment="Git 플랫폼 구분 (github / gitlab / bitbucket)",
    )
    platform_repo_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="플랫폼별 저장소 고유 ID (GitLab: project_id, Bitbucket: workspace/slug)",
    )
    platform_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="저장소 웹 URL (GitLab/Bitbucket)",
    )
    platform_access_token_enc: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AES-256 암호화된 PAT 또는 App Password",
    )
    external_username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Bitbucket username (App Password 인증에 필요)",
    )
    platform_base_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Self-managed 인스턴스 URL (GitLab 전용, 기본 NULL)",
    )

    github_repo_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        default=0,
        server_default="0",
        comment="GitHub 저장소 ID (하위 호환성 유지, GitHub 외 플랫폼은 0)",
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="저장소 전체 이름 (예: org/repo-name)",
    )
    default_branch: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="main",
        comment="기본 브랜치 이름",
    )
    language: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="주 프로그래밍 언어",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="스캔 활성화 여부",
    )
    installation_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="GitHub App 설치 ID",
    )
    webhook_secret: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="이 저장소 Webhook 서명 검증용 시크릿",
    )
    last_scanned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="마지막 스캔 완료 시각",
    )
    security_score: Mapped[float | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="보안 점수 (0.00 ~ 100.00)",
    )

    # F-01: 초기 전체 스캔 완료 여부
    is_initial_scan_done: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="초기 전체 스캔 완료 여부",
    )

    # 관계
    team: Mapped["Team"] = relationship("Team", back_populates="repositories")  # noqa: F821
    scan_jobs: Mapped[list["ScanJob"]] = relationship(  # noqa: F821
        "ScanJob",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    vulnerabilities: Mapped[list["Vulnerability"]] = relationship(  # noqa: F821
        "Vulnerability",
        back_populates="repository",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Repository id={self.id} full_name={self.full_name}>"
