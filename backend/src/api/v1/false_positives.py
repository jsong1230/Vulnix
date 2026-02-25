"""오탐 패턴 관리 엔드포인트"""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import CurrentUser, DbSession
from src.models.false_positive import FalsePositivePattern
from src.models.team import TeamMember
from src.schemas.common import ApiResponse
from src.schemas.false_positive import FalsePositivePatternCreate, FalsePositivePatternResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# DB 헬퍼 함수
# ---------------------------------------------------------------------------

async def get_user_team_id(db: AsyncSession, user_id: uuid.UUID) -> uuid.UUID | None:
    """사용자의 첫 번째 팀 ID를 반환한다."""
    result = await db.execute(
        select(TeamMember.team_id).where(TeamMember.user_id == user_id).limit(1)
    )
    return result.scalar_one_or_none()


async def get_user_team_role(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple[uuid.UUID | None, str | None]:
    """(team_id, role) 반환. 팀 없으면 (None, None)."""
    result = await db.execute(
        select(TeamMember.team_id, TeamMember.role)
        .where(TeamMember.user_id == user_id)
        .limit(1)
    )
    row = result.first()
    if row is None:
        return None, None
    return row[0], row[1]


async def create_fp_pattern(
    db: AsyncSession,
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    data: FalsePositivePatternCreate,
) -> FalsePositivePattern:
    """오탐 패턴 레코드를 생성한다."""
    from datetime import datetime, timezone

    pattern = FalsePositivePattern(
        id=uuid.uuid4(),
        team_id=team_id,
        semgrep_rule_id=data.semgrep_rule_id,
        file_pattern=data.file_pattern,
        reason=data.reason,
        created_by=user_id,
        is_active=True,
        matched_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(pattern)
    await db.flush()
    return pattern


async def get_fp_patterns_by_team(
    db: AsyncSession,
    team_id: uuid.UUID,
) -> list[FalsePositivePattern]:
    """팀의 오탐 패턴 목록을 조회한다."""
    result = await db.execute(
        select(FalsePositivePattern).where(FalsePositivePattern.team_id == team_id)
    )
    return list(result.scalars().all())


async def soft_delete_fp_pattern(
    db: AsyncSession,
    pattern_id: uuid.UUID,
    team_id: uuid.UUID,
) -> FalsePositivePattern | None:
    """오탐 패턴을 비활성화한다 (소프트 삭제)."""
    result = await db.execute(
        select(FalsePositivePattern).where(
            FalsePositivePattern.id == pattern_id,
            FalsePositivePattern.team_id == team_id,
        )
    )
    pattern = result.scalar_one_or_none()
    if pattern is None:
        return None
    pattern.is_active = False
    await db.flush()
    return pattern


async def restore_fp_pattern(
    db: AsyncSession,
    pattern_id: uuid.UUID,
    team_id: uuid.UUID,
) -> FalsePositivePattern | None:
    """비활성화된 오탐 패턴을 복원한다."""
    result = await db.execute(
        select(FalsePositivePattern).where(
            FalsePositivePattern.id == pattern_id,
            FalsePositivePattern.team_id == team_id,
        )
    )
    pattern = result.scalar_one_or_none()
    if pattern is None:
        return None
    pattern.is_active = True
    await db.flush()
    return pattern


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[FalsePositivePatternResponse],
)
async def create_false_positive(
    data: FalsePositivePatternCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[FalsePositivePatternResponse]:
    """오탐 패턴 등록.

    현재 사용자의 팀에 오탐 패턴을 등록한다.
    팀에 소속되지 않은 사용자 또는 owner/admin이 아닌 경우 403을 받는다.
    """
    team_id, role = await get_user_team_role(db, current_user.id)
    if team_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="팀에 속하지 않은 사용자입니다.",
        )
    if role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin/owner 권한이 필요합니다.",
        )

    pattern = await create_fp_pattern(db, team_id, current_user.id, data)
    await db.commit()
    return ApiResponse(
        success=True,
        data=FalsePositivePatternResponse.model_validate(pattern),
        error=None,
    )


@router.get("", response_model=ApiResponse[list[FalsePositivePatternResponse]])
async def list_false_positives(
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[list[FalsePositivePatternResponse]]:
    """오탐 패턴 목록 조회.

    현재 사용자의 팀에 등록된 오탐 패턴 전체를 반환한다.
    팀에 소속되지 않은 경우 빈 목록을 반환한다.
    """
    team_id = await get_user_team_id(db, current_user.id)
    if team_id is None:
        return ApiResponse(success=True, data=[], error=None)

    patterns = await get_fp_patterns_by_team(db, team_id)
    return ApiResponse(
        success=True,
        data=[FalsePositivePatternResponse.model_validate(p) for p in patterns],
        error=None,
    )


@router.delete(
    "/{pattern_id}",
    response_model=ApiResponse[FalsePositivePatternResponse],
)
async def delete_false_positive(
    pattern_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[FalsePositivePatternResponse]:
    """오탐 패턴 비활성화 (소프트 삭제).

    is_active=False로 변경한다. 물리 삭제는 하지 않는다.
    owner/admin 권한이 필요하다.
    """
    team_id, role = await get_user_team_role(db, current_user.id)
    if team_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="팀에 속하지 않은 사용자입니다.",
        )
    if role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin/owner 권한이 필요합니다.",
        )

    pattern = await soft_delete_fp_pattern(db, pattern_id, team_id)
    if pattern is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="패턴을 찾을 수 없습니다.",
        )

    await db.commit()
    return ApiResponse(
        success=True,
        data=FalsePositivePatternResponse.model_validate(pattern),
        error=None,
    )


@router.put(
    "/{pattern_id}/restore",
    response_model=ApiResponse[FalsePositivePatternResponse],
)
async def restore_false_positive(
    pattern_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[FalsePositivePatternResponse]:
    """비활성화된 오탐 패턴 복원.

    is_active=True로 변경한다. 이미 활성인 패턴은 그대로 반환한다 (멱등).
    owner/admin 권한이 필요하다.
    """
    team_id, role = await get_user_team_role(db, current_user.id)
    if team_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="팀에 속하지 않은 사용자입니다.",
        )
    if role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin/owner 권한이 필요합니다.",
        )

    pattern = await restore_fp_pattern(db, pattern_id, team_id)
    if pattern is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="패턴을 찾을 수 없습니다.",
        )

    await db.commit()
    return ApiResponse(
        success=True,
        data=FalsePositivePatternResponse.model_validate(pattern),
        error=None,
    )
