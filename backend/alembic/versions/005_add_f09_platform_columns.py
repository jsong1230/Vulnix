"""F-09: repository 테이블에 플랫폼 컬럼 추가 (GitLab/Bitbucket 연동)

Revision ID: 005_add_f09_platform_columns
Revises: 004_add_f08_tables
Create Date: 2026-02-25

변경사항:
- repository 플랫폼 컬럼들(platform, platform_repo_id, platform_url,
  platform_access_token_enc, external_username, platform_base_url)은
  000_initial_schema 에서 이미 생성됨 (여기서는 생략)
- ix_repository_platform 인덱스도 000_initial_schema 에서 이미 생성됨
- uq_repository_platform_repo_id 유니크 부분 인덱스 추가 (신규)

하위 호환성:
- 기존 github_repo_id, installation_id 컬럼은 유지 (GitHub 연동 호환)
- 기존 행의 platform 컬럼은 'github'로 자동 설정됨
"""

from alembic import op

revision = "005_add_f09_platform_columns"
down_revision = "004_add_f08_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # repository 테이블의 플랫폼 컬럼들(platform, platform_repo_id, platform_url,
    # platform_access_token_enc, external_username, platform_base_url)은
    # 000_initial_schema 에서 이미 생성됨 — ADD COLUMN 불필요
    #
    # github_repo_id DEFAULT 0 도 000_initial_schema 에서 이미 설정됨 — alter_column 불필요
    #
    # ix_repository_platform 인덱스도 000_initial_schema 에서 이미 생성됨 (이름: ix_repository_platform)

    # 플랫폼 + 저장소 ID 복합 유니크 인덱스 (부분 인덱스, 000 에 없음)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_repository_platform_repo_id
        ON repository(platform, platform_repo_id)
        WHERE platform_repo_id IS NOT NULL
        """
    )


def downgrade() -> None:
    # 이 마이그레이션에서 추가한 부분 인덱스만 제거
    # (플랫폼 컬럼들은 000_initial_schema 에서 생성됐으므로 여기서 drop 불필요)
    op.execute("DROP INDEX IF EXISTS uq_repository_platform_repo_id")
