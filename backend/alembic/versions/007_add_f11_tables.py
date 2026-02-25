"""F-11: api_key 테이블 추가 — IDE 플러그인 인증용

Revision ID: 007_add_f11_tables
Revises: 006_add_f10_tables
Create Date: 2026-02-25

변경사항:
- api_key 테이블 신규 생성
  - idx_api_key_hash UNIQUE 인덱스 (key_hash)
  - idx_api_key_team 인덱스 (team_id)
  - idx_api_key_active 부분 인덱스 (team_id, is_active) WHERE is_active = TRUE
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007_add_f11_tables"
down_revision = "006_add_f10_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ──────────────────────────────────────────────────────────────
    # api_key 테이블 생성
    # ──────────────────────────────────────────────────────────────
    op.create_table(
        "api_key",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="기본 키 (UUID v4)",
        ),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="소속 팀 ID (FK)",
        ),
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
            comment="키 이름 (사용자 지정)",
        ),
        sa.Column(
            "key_hash",
            sa.String(64),
            nullable=False,
            comment="SHA-256 해시 (원본 키 미저장)",
        ),
        sa.Column(
            "key_prefix",
            sa.String(20),
            nullable=False,
            comment="키 앞 12자리 (조회 시 표시용)",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="활성 여부",
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="마지막 사용 시각 (UTC)",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="만료 일시 (NULL이면 무기한)",
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="발급자 ID (FK)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="생성 시각 (UTC)",
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="비활성화 시각 (논리 삭제)",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash", name="uq_api_key_hash"),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["team.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["user.id"],
            ondelete="SET NULL",
        ),
        comment="IDE 플러그인 인증용 팀 단위 API Key",
    )

    # key_hash UNIQUE 인덱스 (O(1) 조회)
    op.create_index(
        "idx_api_key_hash",
        "api_key",
        ["key_hash"],
        unique=True,
    )

    # 팀별 조회 인덱스
    op.create_index(
        "idx_api_key_team",
        "api_key",
        ["team_id"],
    )

    # 팀별 활성 Key 부분 인덱스
    op.create_index(
        "idx_api_key_active",
        "api_key",
        ["team_id", "is_active"],
        postgresql_where=sa.text("is_active = TRUE"),
    )


def downgrade() -> None:
    op.drop_index("idx_api_key_active", table_name="api_key")
    op.drop_index("idx_api_key_team", table_name="api_key")
    op.drop_index("idx_api_key_hash", table_name="api_key")
    op.drop_table("api_key")
