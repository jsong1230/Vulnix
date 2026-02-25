"""GitLab 저장소 연동 엔드포인트"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import CurrentUser, DbSession
from src.models.repository import Repository
from src.schemas.common import ApiResponse
from src.schemas.repository import RepositoryResponse
from src.services.gitlab_service import GitLabPlatformService
from src.services.scan_orchestrator import ScanOrchestrator
from src.services.token_crypto import encrypt_token, validate_git_platform_url

router = APIRouter()


# ---------------------------------------------------------------------------
# 요청/응답 스키마
# ---------------------------------------------------------------------------

class GitLabRegisterRequest(BaseModel):
    """GitLab 저장소 연동 요청"""

    gitlab_project_id: int = Field(description="GitLab 프로젝트 ID")
    full_name: str = Field(description="저장소 전체 이름 (예: group/project-name)")
    default_branch: str = Field(default="main", description="기본 브랜치")
    language: str | None = Field(default=None, description="주 프로그래밍 언어")
    gitlab_url: str = Field(default="https://gitlab.com", description="GitLab 인스턴스 URL")
    access_token: str = Field(description="GitLab Personal Access Token")


# ---------------------------------------------------------------------------
# DB 헬퍼 함수 (Mock 패치를 위해 모듈 수준 함수로 분리)
# ---------------------------------------------------------------------------

async def check_gitlab_repo_duplicate(
    db: AsyncSession,
    platform_repo_id: str,
) -> Repository | None:
    """platform_repo_id로 GitLab 저장소 중복을 확인한다."""
    result = await db.execute(
        select(Repository).where(
            Repository.platform == "gitlab",
            Repository.platform_repo_id == platform_repo_id,
        )
    )
    return result.scalar_one_or_none()


async def create_gitlab_repository(
    db: AsyncSession,
    request: GitLabRegisterRequest,
    team_id: uuid.UUID,
) -> Repository:
    """GitLab 저장소 레코드를 생성한다."""
    now = datetime.now(tz=timezone.utc)
    repo = Repository(
        id=uuid.uuid4(),
        team_id=team_id,
        platform="gitlab",
        platform_repo_id=str(request.gitlab_project_id),
        platform_url=f"{request.gitlab_url.rstrip('/')}/{request.full_name}",
        platform_access_token_enc=encrypt_token(request.access_token),  # 암호화 저장
        platform_base_url=request.gitlab_url.rstrip("/"),
        github_repo_id=0,
        full_name=request.full_name,
        default_branch=request.default_branch,
        language=request.language,
        is_active=True,
        is_initial_scan_done=False,
        created_at=now,
        updated_at=now,
    )
    db.add(repo)
    await db.flush()
    return repo


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------

@router.get("/projects", response_model=ApiResponse[dict])
async def list_gitlab_projects(
    current_user: CurrentUser,
    db: DbSession,
    access_token: str = "",
    gitlab_url: str = "https://gitlab.com",
) -> ApiResponse[dict]:
    """GitLab PAT로 접근 가능한 프로젝트 목록을 조회한다.

    이미 연동된 저장소는 already_connected=True로 표시한다.

    Query Params:
        access_token: GitLab Personal Access Token
        gitlab_url: GitLab 인스턴스 URL
    """
    service = GitLabPlatformService(
        access_token=access_token,
        base_url=gitlab_url,
    )

    projects = await service.list_repositories()

    # 이미 연동된 platform_repo_id 세트 조회
    connected_ids: set[str] = set()
    try:
        result = await db.execute(
            select(Repository.platform_repo_id).where(
                Repository.platform == "gitlab",
                Repository.is_active.is_(True),
            )
        )
        connected_ids = {row for row in (result.scalars().all() or []) if row}
    except Exception:
        pass

    # already_connected 플래그 설정
    repositories = []
    for project in projects:
        repositories.append({
            **project,
            "already_connected": project.get("platform_repo_id") in connected_ids,
        })

    return ApiResponse(
        success=True,
        data={"repositories": repositories},
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[RepositoryResponse])
async def register_gitlab_repo(
    request: GitLabRegisterRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[RepositoryResponse]:
    """GitLab PAT로 저장소를 연동 등록하고 초기 스캔을 큐에 등록한다.

    처리 순서:
    1. PAT 유효성 검증
    2. 중복 확인
    3. Repository 레코드 생성
    4. Webhook 등록
    5. 초기 스캔 큐 등록
    """
    # 0. GitLab URL SSRF 방어 검증
    if request.gitlab_url and not validate_git_platform_url(request.gitlab_url):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="유효하지 않은 GitLab URL입니다. HTTPS URL만 허용됩니다.",
        )

    # 1. PAT 유효성 검증
    service = GitLabPlatformService(
        access_token=request.access_token,
        base_url=request.gitlab_url,
    )
    is_valid = await service.validate_credentials()
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="GitLab 자격증명 검증 실패: PAT가 유효하지 않습니다.",
        )

    # 2. 중복 확인
    existing = await check_gitlab_repo_duplicate(
        db=db,
        platform_repo_id=str(request.gitlab_project_id),
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 등록된 GitLab 저장소입니다: project_id={request.gitlab_project_id}",
        )

    # 현재 사용자의 팀 조회 (첫 번째 팀 사용, 없으면 임시 UUID)
    from src.models.team import TeamMember
    try:
        team_result = await db.execute(
            select(TeamMember.team_id).where(TeamMember.user_id == current_user.id).limit(1)
        )
        raw_team_id = team_result.scalar_one_or_none()
        team_id = raw_team_id if isinstance(raw_team_id, uuid.UUID) else uuid.uuid4()
    except Exception:
        team_id = uuid.uuid4()

    # 3. Repository 레코드 생성
    repo = await create_gitlab_repository(db=db, request=request, team_id=team_id)

    # 4. GitLab Webhook 등록 (실패해도 저장소 등록은 유지)
    try:
        from src.config import get_settings
        settings = get_settings()
        webhook_secret = getattr(settings, "GITLAB_WEBHOOK_SECRET", "")
        # APP_BASE_URL이 없으면 기본값 사용
        base_url = getattr(settings, "APP_BASE_URL", "https://vulnix.example.com")
        webhook_url = f"{base_url}/api/v1/webhooks/gitlab"
        await service.register_webhook(
            full_name=request.full_name,
            webhook_url=webhook_url,
            secret=webhook_secret,
            events=["push_events", "merge_requests_events"],
        )
    except Exception:
        # Webhook 등록 실패는 치명적이지 않음 (저장소 등록은 성공으로 처리)
        pass

    # 5. 초기 스캔 큐 등록
    orchestrator = ScanOrchestrator(db=db)
    await orchestrator.enqueue_scan(
        repo_id=repo.id,
        trigger="manual",
        scan_type="initial",
    )

    await db.commit()

    return ApiResponse(
        success=True,
        data=RepositoryResponse.model_validate(repo),
        error=None,
    )
