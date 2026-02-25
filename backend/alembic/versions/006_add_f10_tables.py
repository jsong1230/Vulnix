"""F-10: report_config, report_history 테이블 추가

Revision ID: 006_add_f10_tables
Revises: 005_add_f09_platform_columns
Create Date: 2026-02-25

변경사항:
- report_config 테이블 신규 생성
  - uq_report_config_team_type (team_id, report_type) UNIQUE 제약
  - idx_report_config_team 인덱스
  - idx_report_config_team_active 인덱스
- report_history 테이블 신규 생성
  - idx_report_history_team 인덱스
  - idx_report_history_team_created_at 인덱스
  - idx_report_history_status 인덱스
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "006_add_f10_tables"
down_revision = "005_add_f09_platform_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ──────────────────────────────────────────────────────────────
    # report_config 테이블 생성
    # ──────────────────────────────────────────────────────────────
    op.create_table(
        "report_config",
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
            "report_type",
            sa.String(30),
            nullable=False,
            comment="리포트 유형 (ciso / csap / iso27001 / isms)",
        ),
        sa.Column(
            "schedule",
            sa.String(20),
            nullable=False,
            comment="주기 (weekly / monthly / quarterly)",
        ),
        sa.Column(
            "email_recipients",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="수신 이메일 목록 (JSON 배열)",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="활성 여부",
        ),
        sa.Column(
            "last_generated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="마지막 생성 시각 (UTC)",
        ),
        sa.Column(
            "next_generation_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="다음 생성 예정 시각 (UTC)",
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="등록자 ID (FK)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="생성 시각 (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="수정 시각 (UTC)",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "report_type", name="uq_report_config_team_type"),
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
        comment="리포트 자동 생성 스케줄 설정 (팀 단위)",
    )

    op.create_index(
        "idx_report_config_team",
        "report_config",
        ["team_id"],
    )
    op.create_index(
        "idx_report_config_team_active",
        "report_config",
        ["team_id", "is_active"],
    )

    # ──────────────────────────────────────────────────────────────
    # report_history 테이블 생성
    # ──────────────────────────────────────────────────────────────
    op.create_table(
        "report_history",
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
            "config_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="스케줄 설정 ID (FK, 수동 생성 시 NULL)",
        ),
        sa.Column(
            "report_type",
            sa.String(30),
            nullable=False,
            comment="리포트 유형 (ciso / csap / iso27001 / isms)",
        ),
        sa.Column(
            "format",
            sa.String(10),
            nullable=False,
            server_default="pdf",
            comment="출력 형식 (pdf / json)",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="generating",
            comment="생성 상태 (generating / completed / failed)",
        ),
        sa.Column(
            "file_path",
            sa.Text(),
            nullable=True,
            comment="생성된 파일 경로 (서버 로컬)",
        ),
        sa.Column(
            "file_size_bytes",
            sa.BigInteger(),
            nullable=True,
            comment="파일 크기 (bytes)",
        ),
        sa.Column(
            "period_start",
            sa.Date(),
            nullable=False,
            comment="리포트 기간 시작일",
        ),
        sa.Column(
            "period_end",
            sa.Date(),
            nullable=False,
            comment="리포트 기간 종료일",
        ),
        sa.Column(
            "email_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="이메일 발송 시각 (UTC)",
        ),
        sa.Column(
            "email_recipients",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="이메일 수신자 목록 (JSON 배열)",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="오류 메시지 (failed 상태 시)",
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="리포트 메타데이터 (보안 점수, 취약점 수 등)",
        ),
        sa.Column(
            "generated_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="수동 생성자 ID (FK, 스케줄 자동 생성 시 NULL)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="생성 시각 (UTC)",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["team.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["config_id"],
            ["report_config.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["generated_by"],
            ["user.id"],
            ondelete="SET NULL",
        ),
        comment="리포트 생성 이력",
    )

    op.create_index(
        "idx_report_history_team",
        "report_history",
        ["team_id"],
    )
    op.create_index(
        "idx_report_history_team_created_at",
        "report_history",
        ["team_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "idx_report_history_status",
        "report_history",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("idx_report_history_status", table_name="report_history")
    op.drop_index("idx_report_history_team_created_at", table_name="report_history")
    op.drop_index("idx_report_history_team", table_name="report_history")
    op.drop_table("report_history")

    op.drop_index("idx_report_config_team_active", table_name="report_config")
    op.drop_index("idx_report_config_team", table_name="report_config")
    op.drop_table("report_config")
