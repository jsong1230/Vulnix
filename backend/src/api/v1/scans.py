"""스캔 관련 엔드포인트"""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import CurrentUser, DbSession
from src.models.scan_job import ScanJob
from src.models.repository import Repository
from src.models.team import TeamMember
from src.schemas.common import ApiResponse
from src.schemas.scan import ScanJobResponse, ScanTriggerRequest
from src.services.scan_orchestrator import ScanOrchestrator

router = APIRouter()


# ---------------------------------------------------------------------------
# DB 헬퍼 함수 (Mock 패치 가능하도록 모듈 수준으로 분리)
# ---------------------------------------------------------------------------

async def get_scan_job_by_id(
    db: AsyncSession,
    scan_id: uuid.UUID,
) -> ScanJob | None:
    """scan_id로 ScanJob을 조회한다."""
    result = await db.execute(
        select(ScanJob).where(ScanJob.id == scan_id)
    )
    return result.scalar_one_or_none()


async def get_repo_team_id(
    db: AsyncSession,
    repo_id: uuid.UUID,
) -> uuid.UUID | None:
    """repo_id로 저장소의 team_id를 조회한다."""
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    repo = result.scalar_one_or_none()
    if repo is None:
        return None
    return repo.team_id


async def check_team_member(
    db: AsyncSession,
    user_id: uuid.UUID,
    team_id: uuid.UUID,
) -> bool:
    """사용자가 팀 멤버인지 확인한다."""
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.user_id == user_id,
            TeamMember.team_id == team_id,
        )
    )
    member = result.scalar_one_or_none()
    return member is not None


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------

@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=ApiResponse[ScanJobResponse])
async def trigger_scan(
    request: ScanTriggerRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[ScanJobResponse]:
    """수동 스캔 트리거 (설계서 4-1절).

    저장소 ID와 선택적 브랜치/커밋을 받아 스캔 작업을 Redis 큐에 등록한다.
    응답으로 생성된 ScanJob의 ID를 반환한다.

    1. 저장소 조회 및 팀 소속 확인
    2. 현재 사용자의 팀 멤버 여부 확인
    3. 이미 active 스캔이 있으면 409 반환
    4. ScanOrchestrator.enqueue_scan() 호출
    5. 생성된 ScanJobResponse 반환
    """
    # 저장소 조회
    repo_team_id = await get_repo_team_id(db=db, repo_id=request.repo_id)
    if repo_team_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"저장소를 찾을 수 없습니다: {request.repo_id}",
        )

    # 팀 멤버 여부 확인
    is_member = await check_team_member(
        db=db,
        user_id=current_user.id,
        team_id=repo_team_id,
    )
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 저장소에 접근할 권한이 없습니다.",
        )

    # 저장소 상세 조회 (default_branch 사용)
    repo_result = await db.execute(
        select(Repository).where(Repository.id == request.repo_id)
    )
    repo = repo_result.scalar_one_or_none()

    # 브랜치 결정 (요청에 없으면 default_branch 사용)
    branch = request.branch
    if branch is None and repo is not None:
        branch = repo.default_branch

    # 이미 active 스캔이 있으면 409 반환
    orchestrator = ScanOrchestrator(db=db)
    has_active = await orchestrator.has_active_scan(repo_id=request.repo_id)
    if has_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 진행 중인 스캔이 있습니다.",
        )

    # 스캔 유형 결정 (full_scan 파라미터 미지원 시 incremental 기본값 유지)
    scan_type = "full" if getattr(request, "full_scan", False) else "incremental"

    # 스캔 작업 큐 등록
    job_id = await orchestrator.enqueue_scan(
        repo_id=request.repo_id,
        trigger="manual",
        commit_sha=request.commit_sha,
        branch=branch,
        scan_type=scan_type,
    )
    await db.commit()

    # 생성된 ScanJob 조회
    scan = await get_scan_job_by_id(db=db, scan_id=uuid.UUID(job_id))
    if scan is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="스캔 작업 생성에 실패했습니다.",
        )

    return ApiResponse(
        success=True,
        data=ScanJobResponse.model_validate(scan),
        error=None,
    )


@router.get("/{scan_id}", response_model=ApiResponse[ScanJobResponse])
async def get_scan(
    scan_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[ScanJobResponse]:
    """스캔 작업 상태 및 결과 조회 (설계서 4-1절).

    1. scan_id로 ScanJob 조회
    2. ScanJob의 repo_id -> Repository의 team_id -> TeamMember에서 접근 권한 확인
    3. ScanJobResponse 스키마로 직렬화하여 반환
    """
    # 스캔 작업 조회
    scan = await get_scan_job_by_id(db=db, scan_id=scan_id)
    if scan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"스캔을 찾을 수 없습니다: {scan_id}",
        )

    # 저장소 접근 권한 확인 (팀 멤버 여부)
    team_id = await get_repo_team_id(db=db, repo_id=scan.repo_id)
    if team_id is not None:
        is_member = await check_team_member(
            db=db,
            user_id=current_user.id,
            team_id=team_id,
        )
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이 스캔에 접근할 권한이 없습니다.",
            )

    return ApiResponse(
        success=True,
        data=ScanJobResponse.model_validate(scan),
        error=None,
    )
