"""F-09: repository 테이블에 플랫폼 컬럼 추가 (GitLab/Bitbucket 연동)

Revision ID: 005_add_f09_platform_columns
Revises: 004_add_f08_tables
Create Date: 2026-02-25

변경사항:
- repository 테이블에 platform 컬럼 추가 (DEFAULT 'github')
- repository 테이블에 platform_repo_id 컬럼 추가
- repository 테이블에 platform_url 컬럼 추가
- repository 테이블에 platform_access_token_enc 컬럼 추가
- repository 테이블에 external_username 컬럼 추가
- repository 테이블에 platform_base_url 컬럼 추가
- idx_repository_platform 인덱스 추가
- uq_repository_platform_repo_id 유니크 인덱스 추가

하위 호환성:
- 기존 github_repo_id, installation_id 컬럼은 유지 (GitHub 연동 호환)
- 기존 행의 platform 컬럼은 'github'로 자동 설정됨
"""

from alembic import op
import sqlalchemy as sa

revision = "005_add_f09_platform_columns"
down_revision = "004_add_f08_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # repository 테이블에 플랫폼 컬럼 추가
    op.add_column(
        "repository",
        sa.Column(
            "platform",
            sa.String(20),
            nullable=False,
            server_default="github",
            comment="Git 플랫폼 구분 (github / gitlab / bitbucket)",
        ),
    )
    op.add_column(
        "repository",
        sa.Column(
            "platform_repo_id",
            sa.String(255),
            nullable=True,
            comment="플랫폼별 저장소 고유 ID (GitLab: project_id, Bitbucket: workspace/slug)",
        ),
    )
    op.add_column(
        "repository",
        sa.Column(
            "platform_url",
            sa.Text(),
            nullable=True,
            comment="저장소 웹 URL (GitLab/Bitbucket)",
        ),
    )
    op.add_column(
        "repository",
        sa.Column(
            "platform_access_token_enc",
            sa.Text(),
            nullable=True,
            comment="AES-256 암호화된 PAT 또는 App Password",
        ),
    )
    op.add_column(
        "repository",
        sa.Column(
            "external_username",
            sa.String(255),
            nullable=True,
            comment="Bitbucket username (App Password 인증에 필요)",
        ),
    )
    op.add_column(
        "repository",
        sa.Column(
            "platform_base_url",
            sa.String(500),
            nullable=True,
            comment="Self-managed 인스턴스 URL (GitLab 전용, 기본 NULL)",
        ),
    )

    # github_repo_id UNIQUE 제약을 플랫폼별로 분리하기 위해
    # 기존 unique 제약을 제거하고 NOT NULL → nullable로 변경
    # 하위 호환성을 위해 기존 제약은 유지하고 DEFAULT 0 추가
    op.alter_column(
        "repository",
        "github_repo_id",
        nullable=False,
        server_default="0",
    )

    # 플랫폼별 저장소 조회 최적화 인덱스
    op.create_index(
        "idx_repository_platform",
        "repository",
        ["platform"],
    )

    # 플랫폼 + 저장소 ID 복합 유니크 인덱스
    # WHERE platform_repo_id IS NOT NULL 조건 포함 (partial index)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_repository_platform_repo_id
        ON repository(platform, platform_repo_id)
        WHERE platform_repo_id IS NOT NULL
        """
    )


def downgrade() -> None:
    # 인덱스 삭제
    op.execute("DROP INDEX IF EXISTS uq_repository_platform_repo_id")
    op.drop_index("idx_repository_platform", table_name="repository")

    # 컬럼 삭제
    op.drop_column("repository", "platform_base_url")
    op.drop_column("repository", "external_username")
    op.drop_column("repository", "platform_access_token_enc")
    op.drop_column("repository", "platform_url")
    op.drop_column("repository", "platform_repo_id")
    op.drop_column("repository", "platform")
