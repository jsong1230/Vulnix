"""F-03 자동 패치 PR 생성 — DB 컬럼 추가

Revision ID: 002_add_f03_columns
Revises: 001_add_f01_columns
Create Date: 2026-02-25

변경사항:
- vulnerability.manual_guide 컬럼 추가 (TEXT, nullable)
- vulnerability.manual_priority 컬럼 추가 (VARCHAR(10), nullable)
- patch_pr.test_suggestion 컬럼 추가 (TEXT, nullable)
- idx_patch_pr_status 인덱스 추가
- idx_patch_pr_created 인덱스 추가
- idx_vulnerability_manual_priority 부분 인덱스 추가
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "002_add_f03_columns"
down_revision = "001_add_f01_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # vulnerability 테이블: manual_guide 컬럼 추가
    op.add_column(
        "vulnerability",
        sa.Column(
            "manual_guide",
            sa.Text(),
            nullable=True,
            comment="패치 불가 시 수동 수정 가이드 (LLM 생성)",
        ),
    )

    # vulnerability 테이블: manual_priority 컬럼 추가
    op.add_column(
        "vulnerability",
        sa.Column(
            "manual_priority",
            sa.String(10),
            nullable=True,
            comment="수동 수정 우선순위 (P0=critical / P1=high / P2=medium / P3=low)",
        ),
    )

    # patch_pr 테이블: test_suggestion 컬럼 추가
    op.add_column(
        "patch_pr",
        sa.Column(
            "test_suggestion",
            sa.Text(),
            nullable=True,
            comment="LLM이 제안한 테스트 코드 (선택적)",
        ),
    )

    # 인덱스 추가
    op.create_index(
        "idx_patch_pr_status",
        "patch_pr",
        ["status"],
    )

    op.create_index(
        "idx_patch_pr_created",
        "patch_pr",
        ["created_at"],
    )

    # vulnerability.manual_priority 부분 인덱스 (PostgreSQL 부분 인덱스)
    op.execute(
        """
        CREATE INDEX idx_vulnerability_manual_priority
        ON vulnerability(manual_priority)
        WHERE manual_priority IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_vulnerability_manual_priority")
    op.drop_index("idx_patch_pr_created", table_name="patch_pr")
    op.drop_index("idx_patch_pr_status", table_name="patch_pr")
    op.drop_column("patch_pr", "test_suggestion")
    op.drop_column("vulnerability", "manual_priority")
    op.drop_column("vulnerability", "manual_guide")
