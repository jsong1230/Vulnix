"""F-08: notification_config, notification_log 테이블 추가

Revision ID: 004_add_f08_tables
Revises: 004_add_f07_indexes
Create Date: 2026-02-25

변경사항:
- notification_config 테이블 신규 생성
- notification_log 테이블 신규 생성
- idx_notification_config_team 인덱스 추가
- idx_notification_config_team_active 인덱스 추가
- idx_notification_log_team 인덱스 추가
- idx_notification_log_config 인덱스 추가
- idx_notification_log_sent_at 인덱스 추가
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004_add_f08_tables"
down_revision = "004_add_f07_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # notification_config 테이블 생성
    op.create_table(
        "notification_config",
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
            "platform",
            sa.String(20),
            nullable=False,
            comment="알림 플랫폼 (slack / teams)",
        ),
        sa.Column(
            "webhook_url",
            sa.Text(),
            nullable=False,
            comment="Webhook URL (HTTPS 필수)",
        ),
        sa.Column(
            "severity_threshold",
            sa.String(20),
            nullable=False,
            server_default="all",
            comment="알림 발송 기준 심각도 (critical / high / medium / all)",
        ),
        sa.Column(
            "weekly_report_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="주간 리포트 발송 여부",
        ),
        sa.Column(
            "weekly_report_day",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="주간 리포트 발송 요일 (1=월 ~ 7=일)",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="활성 여부",
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
        comment="알림 설정 (팀 단위 Slack/Teams webhook)",
    )

    # notification_config 인덱스
    op.create_index(
        "idx_notification_config_team",
        "notification_config",
        ["team_id"],
    )
    op.create_index(
        "idx_notification_config_team_active",
        "notification_config",
        ["team_id", "is_active"],
    )

    # notification_log 테이블 생성
    op.create_table(
        "notification_log",
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
            comment="알림 설정 ID (FK)",
        ),
        sa.Column(
            "notification_type",
            sa.String(30),
            nullable=False,
            comment="알림 유형 (vulnerability / weekly_report)",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            comment="발송 상태 (sent / failed)",
        ),
        sa.Column(
            "http_status",
            sa.Integer(),
            nullable=True,
            comment="HTTP 응답 상태 코드",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="오류 메시지 (실패 시)",
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="발송된 페이로드 (JSON)",
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="발송 시각 (UTC)",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["team.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["config_id"],
            ["notification_config.id"],
            ondelete="CASCADE",
        ),
        comment="알림 발송 이력",
    )

    # notification_log 인덱스
    op.create_index(
        "idx_notification_log_team",
        "notification_log",
        ["team_id"],
    )
    op.create_index(
        "idx_notification_log_config",
        "notification_log",
        ["config_id"],
    )
    op.create_index(
        "idx_notification_log_sent_at",
        "notification_log",
        ["sent_at"],
        postgresql_ops={"sent_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("idx_notification_log_sent_at", table_name="notification_log")
    op.drop_index("idx_notification_log_config", table_name="notification_log")
    op.drop_index("idx_notification_log_team", table_name="notification_log")
    op.drop_table("notification_log")

    op.drop_index("idx_notification_config_team_active", table_name="notification_config")
    op.drop_index("idx_notification_config_team", table_name="notification_config")
    op.drop_table("notification_config")
