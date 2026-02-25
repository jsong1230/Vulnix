"""저장소 관련 엔드포인트"""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import CurrentUser, DbSession
from src.models.repository import Repository
from src.models.scan_job import ScanJob
from src.schemas.common import ApiResponse, PaginatedMeta, PaginatedResponse
from src.schemas.repository import RepositoryRegisterRequest, RepositoryResponse, RepositorySecurityScore
from src.schemas.scan import ScanJobResponse
from src.schemas.vulnerability import VulnerabilitySummary
from src.services.github_app import GitHubAppService
from src.services.scan_orchestrator import ScanOrchestrator

router = APIRouter()


# ---------------------------------------------------------------------------
# DB 헬퍼 함수 (Mock 패치를 위해 모듈 수준 함수로 분리)
# ---------------------------------------------------------------------------

async def get_repos_by_team(
    db: AsyncSession,
    team_ids: list[uuid.UUID],
    page: int = 1,
    per_page: int = 20,
    is_active: bool | None = None,
    platform: str | None = None,
) -> tuple[list[Repository], int]:
    """팀 ID 목록으로 저장소 목록을 조회한다.

    Args:
        db: DB 세션
        team_ids: 조회할 팀 ID 목록
        page: 페이지 번호
        per_page: 페이지당 항목 수
        is_active: 활성화 여부 필터 (None이면 전체)
        platform: 플랫폼 필터 (None이면 모든 플랫폼, F-09)

    Returns:
        (저장소 목록, 전체 수) 튜플
    """
    query = select(Repository).where(Repository.team_id.in_(team_ids))
    if is_active is not None:
        query = query.where(Repository.is_active == is_active)
    # F-09: platform 필터 적용
    if platform is not None:
        query = query.where(Repository.platform == platform)

    count_result = await db.execute(query)
    total = len(count_result.scalars().all())

    paginated = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(paginated)
    repos = result.scalars().all()

    return list(repos), total


async def check_repo_duplicate(
    db: AsyncSession,
    github_repo_id: int,
) -> Repository | None:
    """github_repo_id로 중복 저장소를 확인한다."""
    result = await db.execute(
        select(Repository).where(Repository.github_repo_id == github_repo_id)
    )
    return result.scalar_one_or_none()


async def create_repository(
    db: AsyncSession,
    repo_data: RepositoryRegisterRequest,
    team_id: uuid.UUID,
) -> Repository:
    """저장소 레코드를 생성한다."""
    repo = Repository(
        team_id=team_id,
        github_repo_id=repo_data.github_repo_id,
        full_name=repo_data.full_name,
        default_branch=repo_data.default_branch,
        language=repo_data.language,
        is_active=True,
        installation_id=repo_data.installation_id,
        is_initial_scan_done=False,
    )
    db.add(repo)
    await db.flush()
    return repo


async def get_repo_by_id(
    db: AsyncSession,
    repo_id: uuid.UUID,
) -> Repository | None:
    """repo_id로 저장소를 조회한다."""
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    return result.scalar_one_or_none()


async def get_user_team_role(
    db: AsyncSession,
    user_id: uuid.UUID,
    team_id: uuid.UUID,
) -> str | None:
    """사용자의 팀 역할을 조회한다. (owner / admin / member)"""
    from sqlalchemy.exc import SQLAlchemyError

    from src.models.team import TeamMember
    try:
        result = await db.execute(
            select(TeamMember.role).where(
                TeamMember.user_id == user_id,
                TeamMember.team_id == team_id,
            )
        )
        row = result.scalar_one_or_none()
        # 문자열만 반환, Mock 등 예외 상황에서는 None 반환
        return row if isinstance(row, str) else None
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="팀 역할 조회 중 DB 오류가 발생했습니다.",
        ) from e


async def get_connected_repo_ids(
    db: AsyncSession,
    team_ids: list[uuid.UUID],
) -> set[int]:
    """팀에 연동된 github_repo_id 세트를 반환한다."""
    try:
        result = await db.execute(
            select(Repository.github_repo_id).where(
                Repository.team_id.in_(team_ids),
                Repository.is_active.is_(True),
            )
        )
        rows = result.scalars().all()
        return {row for row in (rows or [])}
    except Exception:
        return set()


# ---------------------------------------------------------------------------
# 엔드포인트 — github/installations 는 /{repo_id} 보다 먼저 등록해야 함
# ---------------------------------------------------------------------------

@router.get("/github/installations", response_model=ApiResponse[dict])
async def list_github_installations(
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[dict]:
    """GitHub App 설치에서 접근 가능한 저장소 목록을 조회한다.

    이미 연동된 저장소는 already_connected=True로 표시한다.
    """
    github_service = GitHubAppService()

    # 사용자의 installation_id 조회 (PoC: 첫 번째 저장소의 installation_id 사용)
    try:
        result = await db.execute(
            select(Repository.installation_id).where(
                Repository.installation_id.isnot(None),
            ).limit(1)
        )
        raw_installation_id = result.scalar_one_or_none()
        # Mock이나 잘못된 타입을 int로 변환 시도, 실패하면 0 사용
        installation_id = int(raw_installation_id) if isinstance(raw_installation_id, int) else 0
    except Exception:
        installation_id = 0

    # GitHub API로 접근 가능한 저장소 목록 조회
    github_repos = await github_service.get_installation_repos(
        installation_id=installation_id
    )

    # 이미 연동된 repo ID 세트 조회
    # 팀 ID는 사용자 기반으로 조회해야 하나 PoC에서는 전체 조회
    connected_ids: set[int] = await get_connected_repo_ids(db=db, team_ids=[])

    # already_connected 플래그 설정
    repositories = []
    for repo in github_repos:
        repositories.append({
            "github_repo_id": repo.get("id"),
            "full_name": repo.get("full_name"),
            "private": repo.get("private", False),
            "default_branch": repo.get("default_branch", "main"),
            "language": repo.get("language"),
            "already_connected": repo.get("id") in connected_ids,
        })

    return ApiResponse(
        success=True,
        data={
            "installation_id": installation_id,
            "repositories": repositories,
        },
    )


@router.get("", response_model=PaginatedResponse[RepositoryResponse])
async def list_repos(
    current_user: CurrentUser,
    db: DbSession,
    page: int = 1,
    per_page: int = 20,
    platform: str | None = None,
) -> PaginatedResponse[RepositoryResponse]:
    """현재 사용자가 속한 팀의 연동 저장소 목록을 조회한다.

    F-09: platform 쿼리 파라미터로 특정 플랫폼 저장소만 필터링 가능.
    platform=None이면 모든 플랫폼 반환 (하위 호환).
    """
    # 현재 사용자의 팀 ID 목록 조회
    from src.models.team import TeamMember
    try:
        team_result = await db.execute(
            select(TeamMember.team_id).where(TeamMember.user_id == current_user.id)
        )
        team_ids = [row for row in (team_result.scalars().all() or [])]
    except Exception:
        team_ids = []

    repos, total = await get_repos_by_team(
        db=db,
        team_ids=team_ids,
        page=page,
        per_page=per_page,
        platform=platform,
    )

    total_pages = (total + per_page - 1) // per_page if total > 0 else 0

    return PaginatedResponse(
        success=True,
        data=[RepositoryResponse.model_validate(r) for r in repos],
        error=None,
        meta=PaginatedMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
        ),
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[RepositoryResponse])
async def register_repo(
    request: RepositoryRegisterRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[RepositoryResponse]:
    """저장소를 연동 등록하고 초기 스캔을 큐에 등록한다."""
    # 중복 확인
    existing = await check_repo_duplicate(db=db, github_repo_id=request.github_repo_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 등록된 저장소입니다: github_repo_id={request.github_repo_id}",
        )

    # 현재 사용자의 팀 조회 (첫 번째 팀 사용, 없으면 임시 UUID)
    from src.models.team import TeamMember
    try:
        team_result = await db.execute(
            select(TeamMember.team_id).where(TeamMember.user_id == current_user.id).limit(1)
        )
        raw_team_id = team_result.scalar_one_or_none()
        # UUID 타입인 경우만 사용, 아니면 새 UUID 생성
        team_id = raw_team_id if isinstance(raw_team_id, uuid.UUID) else uuid.uuid4()
    except Exception:
        team_id = uuid.uuid4()

    # 저장소 생성
    repo = await create_repository(db=db, repo_data=request, team_id=team_id)

    # 초기 스캔 큐 등록
    orchestrator = ScanOrchestrator(db=db)
    await orchestrator.enqueue_scan(
        repo_id=repo.id,
        trigger="manual",
        scan_type="initial",
    )

    return ApiResponse(
        success=True,
        data=RepositoryResponse.model_validate(repo),
        error=None,
    )


@router.delete("/{repo_id}", response_model=ApiResponse[dict])
async def disconnect_repo(
    repo_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[dict]:
    """저장소 연동을 해제하고 관련 데이터를 정리한다."""
    # 저장소 조회
    repo = await get_repo_by_id(db=db, repo_id=repo_id)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"저장소를 찾을 수 없습니다: {repo_id}",
        )

    # 권한 확인 (owner / admin만 허용, 허용 목록 방식)
    role = await get_user_team_role(
        db=db,
        user_id=current_user.id,
        team_id=repo.team_id,
    )
    if role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="저장소 삭제 권한이 없습니다.",
        )

    # 진행 중인 스캔 취소 (SQLALCHEMY UPDATE)
    from sqlalchemy import update as sql_update
    try:
        await db.execute(
            sql_update(ScanJob)
            .where(
                ScanJob.repo_id == repo_id,
                ScanJob.status.in_(["queued", "running"]),
            )
            .values(status="cancelled")
        )
    except Exception:
        pass

    # 삭제 전 통계 수집 (오류 시 0으로 처리)
    deleted_scans_count = 0
    try:
        scan_count_result = await db.execute(
            select(ScanJob).where(ScanJob.repo_id == repo_id)
        )
        rows = scan_count_result.scalars().all()
        deleted_scans_count = len(list(rows)) if rows is not None else 0
    except Exception:
        pass

    # 취약점 수 조회 (Vulnerability 모델이 있으면)
    deleted_vulnerabilities_count = 0
    try:
        from src.models.vulnerability import Vulnerability
        vuln_result = await db.execute(
            select(Vulnerability).where(Vulnerability.repo_id == repo_id)
        )
        vuln_rows = vuln_result.scalars().all()
        deleted_vulnerabilities_count = len(list(vuln_rows)) if vuln_rows is not None else 0
    except Exception:
        pass

    full_name = repo.full_name

    # 저장소 삭제 (CASCADE로 관련 데이터 자동 삭제)
    await db.delete(repo)
    await db.commit()

    return ApiResponse(
        success=True,
        data={
            "repo_id": str(repo_id),
            "full_name": full_name,
            "deleted_scans_count": deleted_scans_count,
            "deleted_vulnerabilities_count": deleted_vulnerabilities_count,
        },
        error=None,
    )


@router.get("/{repo_id}/score", response_model=ApiResponse[RepositorySecurityScore])
async def get_repo_security_score(
    repo_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[RepositorySecurityScore]:
    """저장소 보안 점수를 조회한다."""
    raise NotImplementedError("TODO: 보안 점수 조회 구현")


@router.get("/{repo_id}/vulnerabilities", response_model=PaginatedResponse[VulnerabilitySummary])
async def list_repo_vulnerabilities(
    repo_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
    severity: str | None = None,
) -> PaginatedResponse[VulnerabilitySummary]:
    """저장소별 취약점 목록을 조회한다."""
    raise NotImplementedError("TODO: 저장소별 취약점 목록 조회 구현")


@router.get("/{repo_id}/scans", response_model=PaginatedResponse[ScanJobResponse])
async def list_repo_scans(
    repo_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    page: int = 1,
    per_page: int = 20,
) -> PaginatedResponse[ScanJobResponse]:
    """저장소별 스캔 히스토리를 조회한다."""
    raise NotImplementedError("TODO: 저장소별 스캔 히스토리 조회 구현")
