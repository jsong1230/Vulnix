"""취약점 관련 엔드포인트"""

import uuid
from datetime import datetime, timezone
from math import ceil
from pathlib import PurePosixPath

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy import select as sa_select  # COUNT 서브쿼리 전용
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import CurrentUser, DbSession
from src.models.false_positive import FalsePositivePattern
from src.models.repository import Repository
from src.models.team import TeamMember
from src.models.vulnerability import Vulnerability
from src.schemas.common import ApiResponse, PaginatedMeta, PaginatedResponse
from src.schemas.vulnerability import (
    VulnerabilityResponse,
    VulnerabilityStatusUpdateRequest,
    VulnerabilitySummary,
)
from src.services.security_score import calc_security_score

router = APIRouter()


# ---------------------------------------------------------------------------
# DB 헬퍼 함수 (Mock 패치 가능하도록 모듈 수준으로 분리)
# ---------------------------------------------------------------------------

async def get_user_team_ids(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[uuid.UUID]:
    """현재 사용자가 속한 팀 ID 목록을 반환한다."""
    try:
        result = await db.execute(
            select(TeamMember.team_id).where(TeamMember.user_id == user_id)
        )
        rows = result.scalars().all()
        return [row for row in (rows or []) if isinstance(row, uuid.UUID)]
    except Exception:
        return []


async def get_repo_ids_by_teams(
    db: AsyncSession,
    team_ids: list[uuid.UUID],
) -> list[uuid.UUID]:
    """팀 ID 목록으로 저장소 ID 목록을 반환한다."""
    if not team_ids:
        return []
    try:
        result = await db.execute(
            select(Repository.id).where(Repository.team_id.in_(team_ids))
        )
        rows = result.scalars().all()
        return [row for row in (rows or []) if isinstance(row, uuid.UUID)]
    except Exception:
        return []


async def list_vulns_query(
    db: AsyncSession,
    repo_ids: list[uuid.UUID],
    page: int,
    per_page: int,
    status_filter: str | None,
    severity_filter: str | None,
    repo_id_filter: uuid.UUID | None,
    vulnerability_type_filter: str | None = None,
) -> tuple[list[Vulnerability], int]:
    """취약점 목록을 조회한다 (페이지네이션 + 필터 적용).

    복합 인덱스 idx_vulnerability_repo_status 활용.
    F-07: vulnerability_type 필터 추가.
    """
    base_query = select(Vulnerability)

    if repo_id_filter is not None:
        # 팀 소속 검증: repo_id_filter가 현재 사용자의 팀 저장소에 속하는지 확인
        if repo_id_filter not in repo_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="접근 권한 없음",
            )
        base_query = base_query.where(Vulnerability.repo_id == repo_id_filter)
    elif repo_ids:
        base_query = base_query.where(Vulnerability.repo_id.in_(repo_ids))
    else:
        # 접근 가능한 저장소가 없으면 빈 결과
        return [], 0

    if status_filter is not None:
        base_query = base_query.where(Vulnerability.status == status_filter)
    if severity_filter is not None:
        base_query = base_query.where(Vulnerability.severity == severity_filter)
    # F-07: vulnerability_type 필터 적용
    if vulnerability_type_filter is not None:
        base_query = base_query.where(
            Vulnerability.vulnerability_type == vulnerability_type_filter
        )

    base_query = base_query.order_by(Vulnerability.detected_at.desc())

    # COUNT 쿼리: 전체 수를 DB에서 집계 (Python 메모리 로드 방지)
    count_query = sa_select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # 페이지네이션 쿼리
    paginated = base_query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(paginated)
    items = result.scalars().all()

    return list(items) if items else [], total


async def get_vuln_by_id(
    db: AsyncSession,
    vuln_id: uuid.UUID,
) -> Vulnerability | None:
    """vuln_id로 취약점을 조회한다."""
    result = await db.execute(
        select(Vulnerability)
        .where(Vulnerability.id == vuln_id)
    )
    return result.scalar_one_or_none()


async def get_repo_by_id(
    db: AsyncSession,
    repo_id: uuid.UUID,
) -> Repository | None:
    """repo_id로 저장소를 조회한다."""
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    return result.scalar_one_or_none()


async def check_team_access(
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


async def get_user_team_id_single(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> uuid.UUID | None:
    """현재 사용자의 첫 번째 팀 ID를 반환한다."""
    try:
        result = await db.execute(
            select(TeamMember.team_id).where(TeamMember.user_id == user_id).limit(1)
        )
        return result.scalar_one_or_none()
    except Exception:
        return None


def _infer_dir_pattern(file_path: str) -> str:
    """파일 경로에서 디렉토리 기반 glob 패턴을 자동 추론한다.

    예: "tests/unit/test_auth.py" -> "tests/unit/**"
    """
    parent = str(PurePosixPath(file_path).parent)
    if parent and parent != ".":
        return f"{parent}/**"
    return "**"


async def create_fp_pattern_from_vuln(
    db: AsyncSession,
    vuln: Vulnerability,
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    file_pattern: str | None,
    reason: str | None,
) -> FalsePositivePattern | None:
    """취약점에서 오탐 패턴을 생성한다.

    semgrep_rule_id가 없으면 생성하지 않는다.
    file_pattern이 None이면 취약점 파일 경로에서 디렉토리 패턴을 추론한다.
    동일 패턴이 이미 활성 상태로 존재하면 기존 패턴을 반환한다 (중복 방지).
    """
    if not vuln.semgrep_rule_id:
        return None

    resolved_file_pattern = file_pattern
    if resolved_file_pattern is None:
        resolved_file_pattern = _infer_dir_pattern(vuln.file_path)

    # 중복 패턴 확인
    existing_result = await db.execute(
        select(FalsePositivePattern).where(
            FalsePositivePattern.team_id == team_id,
            FalsePositivePattern.semgrep_rule_id == vuln.semgrep_rule_id,
            FalsePositivePattern.file_pattern == resolved_file_pattern,
            FalsePositivePattern.is_active.is_(True),
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        return existing

    pattern = FalsePositivePattern(
        team_id=team_id,
        semgrep_rule_id=vuln.semgrep_rule_id,
        file_pattern=resolved_file_pattern,
        reason=reason,
        created_by=user_id,
        source_vulnerability_id=vuln.id,
    )
    db.add(pattern)
    await db.flush()
    return pattern


def _calc_security_score(vulns: list[Vulnerability]) -> float:
    """보안 점수를 계산한다 (F-07 설계서 공식 통일).

    공식: max(0, 100 - (critical*25 + high*10 + medium*5 + low*1))
    open 상태 취약점만 감점 대상, 취약점 0건이면 100점.
    calc_security_score 공통 유틸을 사용한다.
    """
    open_vulns = [v for v in vulns if str(v.status) == "open"]
    if not open_vulns:
        return 100.0

    sev_counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for v in open_vulns:
        sev = str(v.severity) if v.severity else "low"
        if sev in sev_counts:
            sev_counts[sev] += 1

    return calc_security_score(
        critical=sev_counts["critical"],
        high=sev_counts["high"],
        medium=sev_counts["medium"],
        low=sev_counts["low"],
    )


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------

@router.get("", response_model=PaginatedResponse[VulnerabilitySummary])
async def list_vulnerabilities(
    current_user: CurrentUser,
    db: DbSession,
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
    severity: str | None = None,
    repo_id: uuid.UUID | None = None,
    vulnerability_type: str | None = Query(default=None, description="취약점 유형 필터 (예: sql_injection, xss)"),
) -> PaginatedResponse[VulnerabilitySummary]:
    """취약점 목록 조회 (팀 전체, 설계서 4-2절).

    필터: status, severity, repo_id, vulnerability_type (F-07)
    복합 인덱스 idx_vulnerability_repo_status 활용.
    """
    # per_page 최대값 제한
    per_page = min(per_page, 100)

    # 현재 사용자의 팀 소속 저장소 ID 목록 조회
    team_ids = await get_user_team_ids(db=db, user_id=current_user.id)
    repo_ids = await get_repo_ids_by_teams(db=db, team_ids=team_ids)

    vulns, total = await list_vulns_query(
        db=db,
        repo_ids=repo_ids,
        page=page,
        per_page=per_page,
        status_filter=status,
        severity_filter=severity,
        repo_id_filter=repo_id,
        vulnerability_type_filter=vulnerability_type,
    )

    total_pages = ceil(total / per_page) if total > 0 else 0

    return PaginatedResponse(
        success=True,
        data=[VulnerabilitySummary.model_validate(v) for v in vulns],
        error=None,
        meta=PaginatedMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
        ),
    )


@router.get("/{vuln_id}", response_model=ApiResponse[VulnerabilityResponse])
async def get_vulnerability(
    vuln_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[VulnerabilityResponse]:
    """취약점 상세 조회 (설계서 4-3절).

    코드 스니펫, LLM 분석 결과, 패치 PR 정보 포함.
    repo_full_name 필드 포함.
    """
    # 취약점 조회 (patch_pr eager load)
    vuln = await get_vuln_by_id(db=db, vuln_id=vuln_id)
    if vuln is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"취약점을 찾을 수 없습니다: {vuln_id}",
        )

    # 저장소 접근 권한 확인
    repo = await get_repo_by_id(db=db, repo_id=vuln.repo_id)
    if repo is not None:
        is_member = await check_team_access(
            db=db,
            user_id=current_user.id,
            team_id=repo.team_id,
        )
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이 취약점에 접근할 권한이 없습니다.",
            )

    # VulnerabilityResponse 구성 (repo_full_name 추가)
    vuln_data = VulnerabilityResponse.model_validate(vuln)
    if repo is not None:
        vuln_data.repo_full_name = repo.full_name

    return ApiResponse(
        success=True,
        data=vuln_data,
        error=None,
    )


@router.patch("/{vuln_id}", response_model=ApiResponse[VulnerabilityResponse])
async def update_vulnerability_status(
    vuln_id: uuid.UUID,
    request: VulnerabilityStatusUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[VulnerabilityResponse]:
    """취약점 상태 변경 (설계서 4-4절).

    - patched / false_positive / ignored → resolved_at = now(UTC)
    - open으로 복원 시 resolved_at = None
    - 상태 변경 후 저장소 보안 점수 재계산 (동기)
    """
    # 취약점 조회
    vuln = await get_vuln_by_id(db=db, vuln_id=vuln_id)
    if vuln is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"취약점을 찾을 수 없습니다: {vuln_id}",
        )

    # 저장소 접근 권한 확인
    repo = await get_repo_by_id(db=db, repo_id=vuln.repo_id)
    if repo is not None:
        is_member = await check_team_access(
            db=db,
            user_id=current_user.id,
            team_id=repo.team_id,
        )
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이 취약점을 변경할 권한이 없습니다.",
            )

    # 상태 업데이트
    new_status = request.status
    vuln.status = new_status

    # resolved_at 자동 설정 (설계서 4-4절)
    if new_status in ("patched", "false_positive", "ignored"):
        vuln.resolved_at = datetime.now(timezone.utc)
    elif new_status == "open":
        vuln.resolved_at = None

    # F-06: 오탐 패턴 자동 생성 (ADR-F06-003: 옵트인)
    if new_status == "false_positive" and request.create_pattern:
        team_id = await get_user_team_id_single(db, current_user.id)
        if team_id is not None:
            await create_fp_pattern_from_vuln(
                db=db,
                vuln=vuln,
                team_id=team_id,
                user_id=current_user.id,
                file_pattern=request.file_pattern,
                reason=request.pattern_reason,
            )

    # DB 저장
    await db.flush()
    await db.commit()

    # 보안 점수 재계산 (설계서 4-4절 / ADR-F04-003: 동기적 즉시 계산)
    if repo is not None:
        try:
            all_vulns_result = await db.execute(
                select(Vulnerability).where(Vulnerability.repo_id == repo.id)
            )
            all_vulns = list(all_vulns_result.scalars().all() or [])
            new_score = _calc_security_score(all_vulns)
            repo.security_score = new_score
            await db.flush()
            await db.commit()
        except Exception:
            # 점수 계산 실패 시 무시 (상태 변경은 이미 완료됨)
            pass

    # 응답 구성 (repo_full_name 포함)
    vuln_data = VulnerabilityResponse.model_validate(vuln)
    if repo is not None:
        vuln_data.repo_full_name = repo.full_name

    return ApiResponse(
        success=True,
        data=vuln_data,
        error=None,
    )
