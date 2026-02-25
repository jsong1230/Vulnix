"""F-06: false_positive_pattern, false_positive_log 테이블 추가 및 scan_job 확장

Revision ID: 003_add_f06_tables
Revises: 002_add_f03_columns
Create Date: 2026-02-25

변경사항:
- false_positive_pattern 테이블 신규 생성
- false_positive_log 테이블 신규 생성
- scan_job.auto_filtered_count 컬럼 추가
- idx_fp_pattern_team_active 인덱스 추가
- idx_fp_pattern_rule_id 인덱스 추가
- idx_fp_log_pattern 인덱스 추가
- idx_fp_log_scan 인덱스 추가
- idx_fp_log_filtered_at 인덱스 추가
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_add_f06_tables"
down_revision = "002_add_f03_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # false_positive_pattern 테이블 생성
    op.create_table(
        "false_positive_pattern",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, comment="기본 키 (UUID v4)"),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False, comment="소속 팀 ID"),
        sa.Column("semgrep_rule_id", sa.String(200), nullable=False, comment="대상 Semgrep 룰 ID"),
        sa.Column("file_pattern", sa.String(500), nullable=True, comment="glob 패턴"),
        sa.Column("reason", sa.Text(), nullable=True, comment="오탐으로 판단한 사유"),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="활성 여부",
        ),
        sa.Column(
            "matched_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="자동 필터링된 횟수",
        ),
        sa.Column(
            "last_matched_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="마지막 매칭 시각",
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="패턴 등록자 ID",
        ),
        sa.Column(
            "source_vulnerability_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="원본 취약점 ID",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="생성 시각",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="수정 시각",
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
        sa.ForeignKeyConstraint(
            ["source_vulnerability_id"],
            ["vulnerability.id"],
            ondelete="SET NULL",
        ),
        comment="오탐 패턴 (팀 단위 공유)",
    )

    # false_positive_pattern 인덱스
    op.create_index(
        "idx_fp_pattern_team_active",
        "false_positive_pattern",
        ["team_id", "is_active"],
    )
    op.create_index(
        "idx_fp_pattern_rule_id",
        "false_positive_pattern",
        ["semgrep_rule_id"],
    )

    # UNIQUE 인덱스: 동일 팀 + rule_id + file_pattern 조합으로 중복 패턴 방지 (활성 패턴만)
    op.execute("""
        CREATE UNIQUE INDEX uq_fp_pattern_team_rule_file
        ON false_positive_pattern (team_id, semgrep_rule_id, COALESCE(file_pattern, ''))
        WHERE is_active = true
    """)

    # false_positive_log 테이블 생성
    op.create_table(
        "false_positive_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, comment="기본 키 (UUID v4)"),
        sa.Column(
            "pattern_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="매칭된 패턴 ID",
        ),
        sa.Column(
            "scan_job_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="스캔 작업 ID",
        ),
        sa.Column("semgrep_rule_id", sa.String(255), nullable=False, comment="필터링된 Semgrep 룰 ID"),
        sa.Column("file_path", sa.String(500), nullable=False, comment="필터링된 파일 경로"),
        sa.Column("start_line", sa.Integer(), nullable=False, comment="필터링된 코드 시작 라인"),
        sa.Column(
            "filtered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="필터링 시각",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["pattern_id"],
            ["false_positive_pattern.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scan_job_id"],
            ["scan_job.id"],
            ondelete="CASCADE",
        ),
        comment="오탐 자동 필터링 이력",
    )

    # false_positive_log 인덱스
    op.create_index("idx_fp_log_pattern", "false_positive_log", ["pattern_id"])
    op.create_index("idx_fp_log_scan", "false_positive_log", ["scan_job_id"])
    op.create_index(
        "idx_fp_log_filtered_at",
        "false_positive_log",
        ["filtered_at"],
        postgresql_ops={"filtered_at": "DESC"},
    )

    # scan_job: auto_filtered_count 컬럼 추가
    op.add_column(
        "scan_job",
        sa.Column(
            "auto_filtered_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="오탐 패턴으로 자동 필터링된 건수",
        ),
    )


def downgrade() -> None:
    op.drop_column("scan_job", "auto_filtered_count")

    op.drop_index("idx_fp_log_filtered_at", table_name="false_positive_log")
    op.drop_index("idx_fp_log_scan", table_name="false_positive_log")
    op.drop_index("idx_fp_log_pattern", table_name="false_positive_log")
    op.drop_table("false_positive_log")

    op.execute("DROP INDEX IF EXISTS uq_fp_pattern_team_rule_file")
    op.drop_index("idx_fp_pattern_rule_id", table_name="false_positive_pattern")
    op.drop_index("idx_fp_pattern_team_active", table_name="false_positive_pattern")
    op.drop_table("false_positive_pattern")
