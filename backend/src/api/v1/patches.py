"""패치 PR 관련 엔드포인트 — F-03 자동 패치 PR 생성"""

import math
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.api.deps import CurrentUser, DbSession
from src.models.patch_pr import PatchPR
from src.models.repository import Repository
from src.models.team import TeamMember
from src.schemas.common import ApiResponse, PaginatedMeta, PaginatedResponse
from src.schemas.patch import PatchPRDetailResponse, PatchPRResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[PatchPRResponse])
async def list_patches(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(default=1, ge=1, description="페이지 번호"),
    per_page: int = Query(default=20, ge=1, le=100, description="페이지당 항목 수"),
    status: str | None = Query(default=None, description="상태 필터 (created/merged/closed/rejected)"),
    repo_id: uuid.UUID | None = Query(default=None, description="저장소 ID 필터"),
) -> PaginatedResponse[PatchPRResponse]:
    """현재 사용자 팀의 패치 PR 목록을 조회한다.

    인증 필요: Bearer JWT

    Query Parameters:
        page: 페이지 번호 (기본 1)
        per_page: 페이지당 항목 수 (기본 20, 최대 100)
        status: 상태 필터 (created / merged / closed / rejected)
        repo_id: 특정 저장소로 필터

    Returns:
        PaginatedResponse[PatchPRResponse]
    """
    # 1. 현재 사용자의 팀 소속 저장소 ID 목록 조회
    team_repo_result = await db.execute(
        select(Repository.id).join(
            TeamMember,
            TeamMember.team_id == Repository.team_id,
        ).where(
            TeamMember.user_id == current_user.id,
        )
    )
    team_repo_ids = team_repo_result.scalars().all()

    # 2. PatchPR 쿼리 구성
    base_query = select(PatchPR).where(
        PatchPR.repo_id.in_(team_repo_ids)
    )

    if status:
        base_query = base_query.where(PatchPR.status == status)

    if repo_id is not None:
        base_query = base_query.where(PatchPR.repo_id == repo_id)

    # 3. 전체 건수 조회
    count_result = await db.execute(
        select(func.count()).select_from(
            base_query.subquery()
        )
    )
    total = count_result.scalar_one()

    # 4. 페이지네이션 적용 + 정렬
    offset = (page - 1) * per_page
    items_result = await db.execute(
        base_query.order_by(PatchPR.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    items = items_result.scalars().all()

    total_pages = math.ceil(total / per_page) if total > 0 else 0

    return PaginatedResponse[PatchPRResponse](
        success=True,
        data=[PatchPRResponse.model_validate(item) for item in items],
        meta=PaginatedMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
        ),
    )


@router.get("/{patch_id}", response_model=ApiResponse[PatchPRDetailResponse])
async def get_patch(
    patch_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[PatchPRDetailResponse]:
    """패치 PR 상세 조회 (취약점 정보 포함).

    인증 필요: Bearer JWT

    Path Parameters:
        patch_id: 패치 PR UUID

    Returns:
        ApiResponse[PatchPRDetailResponse] — vulnerability 정보 포함

    Raises:
        401: 미인증 요청
        403: 팀 소속이 아닌 저장소의 패치 조회 시도
        404: 존재하지 않는 patch_id
    """
    # 1. 현재 사용자의 팀 소속 저장소 ID 목록 조회
    team_repo_result = await db.execute(
        select(Repository.id).join(
            TeamMember,
            TeamMember.team_id == Repository.team_id,
        ).where(
            TeamMember.user_id == current_user.id,
        )
    )
    team_repo_ids = team_repo_result.scalars().all()

    # 2. PatchPR 조회 (vulnerability 관계 포함)
    patch_result = await db.execute(
        select(PatchPR)
        .options(selectinload(PatchPR.vulnerability))
        .where(PatchPR.id == patch_id)
    )
    patch_pr = patch_result.scalar_one_or_none()

    if patch_pr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"패치 PR을 찾을 수 없습니다: {patch_id}",
        )

    # 3. 팀 소속 저장소인지 확인
    if patch_pr.repo_id not in team_repo_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 패치 PR에 접근할 권한이 없습니다.",
        )

    return ApiResponse[PatchPRDetailResponse](
        success=True,
        data=PatchPRDetailResponse.model_validate(patch_pr),
    )
