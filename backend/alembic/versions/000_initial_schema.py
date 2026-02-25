"""초기 스키마 생성 — 모든 기본 테이블 CREATE TABLE

Revision ID: 000_initial_schema
Revises: None
Create Date: 2026-02-26

변경사항:
- user 테이블 생성
- team 테이블 생성
- team_member 테이블 생성
- repository 테이블 생성
- scan_job 테이블 생성
- vulnerability 테이블 생성
- patch_pr 테이블 생성
- 기본 인덱스 추가

주의:
- is_initial_scan_done (repository), scan_type/retry_count/changed_files (scan_job)은
  001_add_f01_columns.py 에서 ADD COLUMN으로 추가됩니다.
- manual_guide/manual_priority (vulnerability), test_suggestion (patch_pr)은
  002_add_f03_columns.py 에서 ADD COLUMN으로 추가됩니다.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "000_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # user 테이블
    # ------------------------------------------------------------------ #
    op.create_table(
        "user",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="기본 키 (UUID v4)",
        ),
        sa.Column(
            "github_id",
            sa.BigInteger(),
            nullable=False,
            comment="GitHub 사용자 ID",
        ),
        sa.Column(
            "github_login",
            sa.String(255),
            nullable=False,
            comment="GitHub 로그인명 (username)",
        ),
        sa.Column(
            "email",
            sa.String(255),
            nullable=True,
            comment="이메일 (GitHub에서 공개된 경우)",
        ),
        sa.Column(
            "avatar_url",
            sa.Text(),
            nullable=True,
            comment="GitHub 프로필 이미지 URL",
        ),
        sa.Column(
            "access_token_enc",
            sa.Text(),
            nullable=True,
            comment="암호화된 GitHub Access Token (AES-256)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="생성 시각 (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="수정 시각 (UTC)",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("github_id"),
        comment="GitHub OAuth 사용자",
    )
    op.create_index("ix_user_github_id", "user", ["github_id"])

    # ------------------------------------------------------------------ #
    # team 테이블
    # ------------------------------------------------------------------ #
    op.create_table(
        "team",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="기본 키 (UUID v4)",
        ),
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
            comment="팀명",
        ),
        sa.Column(
            "plan",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'starter'"),
            comment="플랜 (starter / growth / scale / enterprise)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="생성 시각 (UTC)",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="사용자 팀",
    )

    # ------------------------------------------------------------------ #
    # team_member 테이블
    # ------------------------------------------------------------------ #
    op.create_table(
        "team_member",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="기본 키 (UUID v4)",
        ),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("team.id", ondelete="CASCADE"),
            nullable=False,
            comment="팀 ID (FK)",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            comment="사용자 ID (FK)",
        ),
        sa.Column(
            "role",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'member'"),
            comment="역할 (owner / admin / member)",
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="팀 가입 시각",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="팀-사용자 멤버십",
    )
    op.create_index("ix_team_member_team_id", "team_member", ["team_id"])
    op.create_index("ix_team_member_user_id", "team_member", ["user_id"])

    # ------------------------------------------------------------------ #
    # repository 테이블
    # (is_initial_scan_done 은 001_add_f01_columns 에서 추가)
    # ------------------------------------------------------------------ #
    op.create_table(
        "repository",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="기본 키 (UUID v4)",
        ),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("team.id", ondelete="CASCADE"),
            nullable=False,
            comment="소속 팀 ID (FK)",
        ),
        sa.Column(
            "platform",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'github'"),
            comment="Git 플랫폼 구분 (github / gitlab / bitbucket)",
        ),
        sa.Column(
            "platform_repo_id",
            sa.String(255),
            nullable=True,
            comment="플랫폼별 저장소 고유 ID",
        ),
        sa.Column(
            "platform_url",
            sa.Text(),
            nullable=True,
            comment="저장소 웹 URL (GitLab/Bitbucket)",
        ),
        sa.Column(
            "platform_access_token_enc",
            sa.Text(),
            nullable=True,
            comment="AES-256 암호화된 PAT 또는 App Password",
        ),
        sa.Column(
            "external_username",
            sa.String(255),
            nullable=True,
            comment="Bitbucket username",
        ),
        sa.Column(
            "platform_base_url",
            sa.String(500),
            nullable=True,
            comment="Self-managed 인스턴스 URL (GitLab 전용)",
        ),
        sa.Column(
            "github_repo_id",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
            comment="GitHub 저장소 ID (하위 호환성 유지, GitHub 외는 0)",
        ),
        sa.Column(
            "full_name",
            sa.String(255),
            nullable=False,
            comment="저장소 전체 이름 (예: org/repo-name)",
        ),
        sa.Column(
            "default_branch",
            sa.String(255),
            nullable=False,
            server_default=sa.text("'main'"),
            comment="기본 브랜치 이름",
        ),
        sa.Column(
            "language",
            sa.String(50),
            nullable=True,
            comment="주 프로그래밍 언어",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="스캔 활성화 여부",
        ),
        sa.Column(
            "installation_id",
            sa.BigInteger(),
            nullable=True,
            comment="GitHub App 설치 ID",
        ),
        sa.Column(
            "webhook_secret",
            sa.Text(),
            nullable=True,
            comment="Webhook 서명 검증용 시크릿",
        ),
        sa.Column(
            "last_scanned_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="마지막 스캔 완료 시각",
        ),
        sa.Column(
            "security_score",
            sa.Numeric(5, 2),
            nullable=True,
            comment="보안 점수 (0.00 ~ 100.00)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="생성 시각 (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="수정 시각 (UTC)",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("github_repo_id"),
        comment="Git 플랫폼 연동 저장소 (GitHub / GitLab / Bitbucket)",
    )
    op.create_index("ix_repository_team_id", "repository", ["team_id"])
    op.create_index("ix_repository_platform", "repository", ["platform"])

    # ------------------------------------------------------------------ #
    # scan_job 테이블
    # (scan_type, retry_count, changed_files 는 001_add_f01_columns 에서 추가)
    # ------------------------------------------------------------------ #
    op.create_table(
        "scan_job",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="기본 키 (UUID v4)",
        ),
        sa.Column(
            "repo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repository.id", ondelete="CASCADE"),
            nullable=False,
            comment="대상 저장소 ID (FK)",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'queued'"),
            comment="스캔 상태 (queued / running / completed / failed)",
        ),
        sa.Column(
            "trigger_type",
            sa.String(20),
            nullable=False,
            comment="스캔 트리거 유형 (webhook / manual / schedule)",
        ),
        sa.Column(
            "commit_sha",
            sa.String(40),
            nullable=True,
            comment="대상 커밋 SHA (40자)",
        ),
        sa.Column(
            "branch",
            sa.String(255),
            nullable=True,
            comment="대상 브랜치 이름",
        ),
        sa.Column(
            "pr_number",
            sa.Integer(),
            nullable=True,
            comment="PR 트리거 시 GitHub PR 번호",
        ),
        sa.Column(
            "findings_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Semgrep 탐지 건수",
        ),
        sa.Column(
            "true_positives_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="LLM이 확정한 실제 취약점 건수",
        ),
        sa.Column(
            "false_positives_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="LLM이 오탐으로 분류한 건수",
        ),
        sa.Column(
            "auto_filtered_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="오탐 패턴으로 자동 필터링된 건수",
        ),
        sa.Column(
            "duration_seconds",
            sa.Integer(),
            nullable=True,
            comment="스캔 소요 시간 (초)",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="실패 시 에러 메시지",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="스캔 시작 시각",
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="스캔 완료 시각",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="생성 시각 (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="수정 시각 (UTC)",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="스캔 작업",
    )
    op.create_index("ix_scan_job_repo_id", "scan_job", ["repo_id"])
    op.create_index("ix_scan_job_status", "scan_job", ["status"])

    # ------------------------------------------------------------------ #
    # vulnerability 테이블
    # (manual_guide, manual_priority 는 002_add_f03_columns 에서 추가)
    # ------------------------------------------------------------------ #
    op.create_table(
        "vulnerability",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="기본 키 (UUID v4)",
        ),
        sa.Column(
            "scan_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scan_job.id", ondelete="CASCADE"),
            nullable=False,
            comment="발견된 스캔 작업 ID (FK)",
        ),
        sa.Column(
            "repo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repository.id", ondelete="CASCADE"),
            nullable=False,
            comment="저장소 ID (FK)",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'open'"),
            comment="취약점 상태 (open / patched / ignored / false_positive)",
        ),
        sa.Column(
            "severity",
            sa.String(20),
            nullable=False,
            comment="심각도 (critical / high / medium / low)",
        ),
        sa.Column(
            "vulnerability_type",
            sa.String(100),
            nullable=False,
            comment="취약점 유형",
        ),
        sa.Column(
            "cwe_id",
            sa.String(20),
            nullable=True,
            comment="CWE 분류 (예: CWE-89)",
        ),
        sa.Column(
            "owasp_category",
            sa.String(50),
            nullable=True,
            comment="OWASP Top 10 분류",
        ),
        sa.Column(
            "file_path",
            sa.String(500),
            nullable=False,
            comment="취약 파일 경로",
        ),
        sa.Column(
            "start_line",
            sa.Integer(),
            nullable=False,
            comment="취약 코드 시작 라인",
        ),
        sa.Column(
            "end_line",
            sa.Integer(),
            nullable=False,
            comment="취약 코드 끝 라인",
        ),
        sa.Column(
            "code_snippet",
            sa.Text(),
            nullable=True,
            comment="취약 코드 조각 (전후 5줄 포함)",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="취약점 설명",
        ),
        sa.Column(
            "llm_reasoning",
            sa.Text(),
            nullable=True,
            comment="LLM 분석 근거",
        ),
        sa.Column(
            "llm_confidence",
            sa.Numeric(3, 2),
            nullable=True,
            comment="LLM 확신도 (0.00 ~ 1.00)",
        ),
        sa.Column(
            "semgrep_rule_id",
            sa.String(255),
            nullable=True,
            comment="탐지에 사용된 Semgrep 룰 ID",
        ),
        sa.Column(
            "references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="참고 링크 목록 (CVE, OWASP 등)",
        ),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="최초 탐지 시각",
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="해결 시각",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="생성 시각 (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="수정 시각 (UTC)",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="탐지된 취약점",
    )
    op.create_index("ix_vulnerability_scan_job_id", "vulnerability", ["scan_job_id"])
    op.create_index("ix_vulnerability_repo_id", "vulnerability", ["repo_id"])
    op.create_index("ix_vulnerability_status", "vulnerability", ["status"])
    op.create_index("ix_vulnerability_severity", "vulnerability", ["severity"])

    # ------------------------------------------------------------------ #
    # patch_pr 테이블
    # (test_suggestion 은 002_add_f03_columns 에서 추가)
    # ------------------------------------------------------------------ #
    op.create_table(
        "patch_pr",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="기본 키 (UUID v4)",
        ),
        sa.Column(
            "vulnerability_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vulnerability.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            comment="대상 취약점 ID (FK, 1:1)",
        ),
        sa.Column(
            "repo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repository.id", ondelete="CASCADE"),
            nullable=False,
            comment="저장소 ID (FK)",
        ),
        sa.Column(
            "github_pr_number",
            sa.Integer(),
            nullable=True,
            comment="GitHub PR 번호",
        ),
        sa.Column(
            "github_pr_url",
            sa.Text(),
            nullable=True,
            comment="GitHub PR URL",
        ),
        sa.Column(
            "branch_name",
            sa.String(255),
            nullable=True,
            comment="패치 브랜치명",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'created'"),
            comment="PR 상태 (created / merged / closed / rejected)",
        ),
        sa.Column(
            "patch_diff",
            sa.Text(),
            nullable=True,
            comment="unified diff 형식 패치 내용",
        ),
        sa.Column(
            "patch_description",
            sa.Text(),
            nullable=True,
            comment="패치 설명 (PR 본문에 포함)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="PR 생성 시각",
        ),
        sa.Column(
            "merged_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="PR 머지 시각",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="자동 생성 보안 패치 PR",
    )
    op.create_index("ix_patch_pr_repo_id", "patch_pr", ["repo_id"])
    op.create_index("ix_patch_pr_vulnerability_id", "patch_pr", ["vulnerability_id"])


def downgrade() -> None:
    # 생성 역순으로 DROP TABLE
    op.drop_table("patch_pr")
    op.drop_table("vulnerability")
    op.drop_table("scan_job")
    op.drop_table("repository")
    op.drop_table("team_member")
    op.drop_table("team")
    op.drop_table("user")
