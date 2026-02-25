"""F-07: 대시보드 성능 인덱스 추가

Revision ID: 004_add_f07_indexes
Revises: 003_add_f06_tables
Create Date: 2026-02-25

변경사항:
- idx_vulnerability_type 인덱스 추가 (vulnerability_type 필터 성능 향상)
- idx_vulnerability_detected_at 인덱스 추가 (날짜 기반 추이 쿼리 성능 향상)
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "004_add_f07_indexes"
down_revision = "003_add_f06_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """F-07 대시보드 쿼리 성능 향상을 위한 인덱스 추가."""
    # vulnerability_type 필터 인덱스
    op.create_index(
        "idx_vulnerability_type",
        "vulnerability",
        ["vulnerability_type"],
        unique=False,
    )

    # detected_at 날짜 기반 추이 쿼리 인덱스
    op.create_index(
        "idx_vulnerability_detected_at",
        "vulnerability",
        ["detected_at"],
        unique=False,
    )


def downgrade() -> None:
    """F-07 인덱스 제거."""
    op.drop_index("idx_vulnerability_detected_at", table_name="vulnerability")
    op.drop_index("idx_vulnerability_type", table_name="vulnerability")
