"""Bitbucket 저장소 연동 엔드포인트"""

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
from src.services.bitbucket_service import BitbucketPlatformService
from src.services.scan_orchestrator import ScanOrchestrator
from src.services.token_crypto import encrypt_token

router = APIRouter()


# ---------------------------------------------------------------------------
# 요청/응답 스키마
# ---------------------------------------------------------------------------

class BitbucketRegisterRequest(BaseModel):
    """Bitbucket 저장소 연동 요청"""

    workspace: str = Field(description="Bitbucket workspace 이름")
    repo_slug: str = Field(description="저장소 slug")
    full_name: str = Field(description="저장소 전체 이름 (예: workspace/repo-slug)")
    default_branch: str = Field(default="main", description="기본 브랜치")
    language: str | None = Field(default=None, description="주 프로그래밍 언어")
    username: str = Field(description="Bitbucket 사용자명")
    app_password: str = Field(description="Bitbucket App Password")


# ---------------------------------------------------------------------------
# DB 헬퍼 함수 (Mock 패치를 위해 모듈 수준 함수로 분리)
# ---------------------------------------------------------------------------

async def check_bitbucket_repo_duplicate(
    db: AsyncSession,
    platform_repo_id: str,
) -> Repository | None:
    """platform_repo_id로 Bitbucket 저장소 중복을 확인한다."""
    result = await db.execute(
        select(Repository).where(
            Repository.platform == "bitbucket",
            Repository.platform_repo_id == platform_repo_id,
        )
    )
    return result.scalar_one_or_none()


async def create_bitbucket_repository(
    db: AsyncSession,
    request: BitbucketRegisterRequest,
    team_id: uuid.UUID,
) -> Repository:
    """Bitbucket 저장소 레코드를 생성한다."""
    now = datetime.now(tz=timezone.utc)
    repo = Repository(
        id=uuid.uuid4(),
        team_id=team_id,
        platform="bitbucket",
        # Bitbucket platform_repo_id = "workspace/repo-slug" 형식
        platform_repo_id=f"{request.workspace}/{request.repo_slug}",
        platform_url=f"https://bitbucket.org/{request.workspace}/{request.repo_slug}",
        platform_access_token_enc=encrypt_token(request.app_password),  # 암호화 저장
        external_username=request.username,
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

@router.get("/repositories", response_model=ApiResponse[dict])
async def list_bitbucket_repositories(
    current_user: CurrentUser,
    db: DbSession,
    username: str = "",
    app_password: str = "",
    workspace: str = "",
) -> ApiResponse[dict]:
    """Bitbucket App Password로 접근 가능한 저장소 목록을 조회한다.

    Query Params:
        username: Bitbucket 사용자명
        app_password: Bitbucket App Password
        workspace: Bitbucket workspace 이름
    """
    service = BitbucketPlatformService(
        username=username,
        app_password=app_password,
    )

    repos = await service.list_repositories(workspace=workspace)

    # already_connected 플래그 설정 (선택적)
    repositories = []
    connected_ids: set[str] = set()
    try:
        result = await db.execute(
            select(Repository.platform_repo_id).where(
                Repository.platform == "bitbucket",
                Repository.is_active.is_(True),
            )
        )
        connected_ids = {row for row in (result.scalars().all() or []) if row}
    except Exception:
        pass

    for repo in repos:
        repositories.append({
            **repo,
            "already_connected": repo.get("full_name") in connected_ids,
        })

    return ApiResponse(
        success=True,
        data={"repositories": repositories},
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[RepositoryResponse])
async def register_bitbucket_repo(
    request: BitbucketRegisterRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[RepositoryResponse]:
    """Bitbucket App Password로 저장소를 연동 등록하고 초기 스캔을 큐에 등록한다.

    처리 순서:
    1. App Password 유효성 검증
    2. 중복 확인
    3. Repository 레코드 생성
    4. Webhook 등록
    5. 초기 스캔 큐 등록
    """
    # 1. App Password 유효성 검증
    service = BitbucketPlatformService(
        username=request.username,
        app_password=request.app_password,
    )
    is_valid = await service.validate_credentials()
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Bitbucket 자격증명 검증 실패: App Password가 유효하지 않습니다.",
        )

    # 2. 중복 확인 (workspace/repo_slug 복합 ID)
    platform_repo_id = f"{request.workspace}/{request.repo_slug}"
    existing = await check_bitbucket_repo_duplicate(
        db=db,
        platform_repo_id=platform_repo_id,
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 등록된 Bitbucket 저장소입니다: {platform_repo_id}",
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
    repo = await create_bitbucket_repository(db=db, request=request, team_id=team_id)

    # 4. Bitbucket Webhook 등록 (실패해도 저장소 등록은 유지)
    try:
        from src.config import get_settings
        settings = get_settings()
        webhook_secret = getattr(settings, "BITBUCKET_WEBHOOK_SECRET", "")
        if webhook_secret:
            base_url = getattr(settings, "APP_BASE_URL", "https://vulnix.example.com")
            webhook_url = f"{base_url}/api/v1/webhooks/bitbucket"
            await service.register_webhook(
                full_name=request.full_name,
                webhook_url=webhook_url,
                secret=webhook_secret,
                events=["repo:push", "pullrequest:created", "pullrequest:updated"],
            )
    except Exception:
        # Webhook 등록 실패는 치명적이지 않음
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
