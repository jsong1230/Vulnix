"""F-01 저장소 연동 및 스캔 트리거 — DB 컬럼 추가

Revision ID: 001_add_f01_columns
Revises:
Create Date: 2026-02-25

변경사항:
- repository.is_initial_scan_done 컬럼 추가
- scan_job.scan_type 컬럼 추가
- scan_job.retry_count 컬럼 추가
- scan_job.changed_files 컬럼 추가 (JSONB)
- idx_scan_job_repo_active 부분 인덱스 추가
- idx_repository_installation 인덱스 추가
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "001_add_f01_columns"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # repository 테이블: is_initial_scan_done 컬럼 추가
    op.add_column(
        "repository",
        sa.Column(
            "is_initial_scan_done",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="초기 전체 스캔 완료 여부",
        ),
    )

    # repository 테이블: installation_id 인덱스 추가
    op.create_index(
        "idx_repository_installation",
        "repository",
        ["installation_id"],
    )

    # scan_job 테이블: scan_type 컬럼 추가
    op.add_column(
        "scan_job",
        sa.Column(
            "scan_type",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'incremental'"),
            comment="스캔 유형 (full / incremental / pr / initial)",
        ),
    )

    # scan_job 테이블: retry_count 컬럼 추가
    op.add_column(
        "scan_job",
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="현재 재시도 횟수",
        ),
    )

    # scan_job 테이블: changed_files 컬럼 추가 (JSONB)
    op.add_column(
        "scan_job",
        sa.Column(
            "changed_files",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="PR/push 시 변경된 파일 목록",
        ),
    )

    # scan_job 테이블: 활성 스캔 부분 인덱스 추가
    # PostgreSQL 부분 인덱스는 op.execute로 생성
    op.execute(
        """
        CREATE INDEX idx_scan_job_repo_active
        ON scan_job(repo_id)
        WHERE status IN ('queued', 'running')
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_scan_job_repo_active")
    op.drop_index("idx_repository_installation", table_name="repository")
    op.drop_column("scan_job", "changed_files")
    op.drop_column("scan_job", "retry_count")
    op.drop_column("scan_job", "scan_type")
    op.drop_column("repository", "is_initial_scan_done")
