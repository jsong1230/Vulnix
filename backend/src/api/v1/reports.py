"""리포트 생성/다운로드/설정 엔드포인트 — CISO 리포트 및 인증 증적"""

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import CurrentUser, DbSession
from src.models.report_config import ReportConfig
from src.models.report_history import ReportHistory
from src.models.team import TeamMember
from src.schemas.common import ApiResponse, PaginatedMeta, PaginatedResponse
from src.schemas.report import (
    GenerateReportRequest,
    GenerateReportResponse,
    ReportConfigCreate,
    ReportConfigResponse,
    ReportConfigUpdate,
    ReportHistoryResponse,
)
from src.workers.report_scheduler import calculate_next_generation

router = APIRouter()


# ──────────────────────────────────────────────────────────────
# 유틸 헬퍼
# ──────────────────────────────────────────────────────────────


def _safe_get_metadata(history_obj: object) -> dict | None:
    """ORM history 객체에서 metadata dict를 안전하게 추출한다.

    - ORM 모델의 실제 속성명은 ``report_meta`` (SQLAlchemy 예약어 충돌 방지).
    - 테스트 mock은 ``.metadata`` 를 직접 설정하므로, dict가 아니면 fallback 탐색.
    """
    # ORM 실제 속성: report_meta
    val = getattr(history_obj, "report_meta", None)
    if isinstance(val, dict):
        return val
    # 테스트 mock fallback: .metadata
    val = getattr(history_obj, "metadata", None)
    if isinstance(val, dict):
        return val
    return None


# ──────────────────────────────────────────────────────────────
# DB 헬퍼 함수
# ──────────────────────────────────────────────────────────────


async def _get_user_team_role(
    db: AsyncSession,
    user_id: uuid.UUID,
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


async def _get_user_team_id(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> uuid.UUID | None:
    """사용자의 팀 ID만 반환한다."""
    result = await db.execute(
        select(TeamMember.team_id)
        .where(TeamMember.user_id == user_id)
        .limit(1)
    )
    return result.scalar_one_or_none()


def _require_admin_role(team_id: uuid.UUID | None, role: str | None) -> uuid.UUID:
    """팀 소속 및 owner/admin 권한을 검증한다.

    Raises:
        HTTPException: 403 - 팀 없음 또는 권한 부족
    """
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
    return team_id


async def get_report_by_id(
    db: AsyncSession,
    report_id: uuid.UUID,
) -> ReportHistory | None:
    """report_id로 ReportHistory를 조회한다."""
    result = await db.execute(
        select(ReportHistory).where(ReportHistory.id == report_id)
    )
    return result.scalar_one_or_none()


async def create_report_config(
    db: AsyncSession,
    config: ReportConfig,
) -> ReportConfig:
    """ReportConfig를 DB에 저장한다."""
    db.add(config)
    await db.flush()
    await db.commit()
    return config


# ──────────────────────────────────────────────────────────────
# RQ 큐 등록 헬퍼 (실제 RQ 미설치 시 no-op)
# ──────────────────────────────────────────────────────────────


def enqueue_report_generation(
    report_id: uuid.UUID,
    report_type: str,
    team_id: uuid.UUID,
    period_start: object,
    period_end: object,
    report_format: str = "pdf",
) -> None:
    """리포트 생성 작업을 RQ 큐에 등록한다.

    RQ가 설치되지 않은 환경(PoC)에서는 no-op.
    """
    try:
        import redis
        from rq import Queue

        from src.config import get_settings
        settings = get_settings()
        redis_conn = redis.from_url(settings.REDIS_URL)
        queue = Queue("reports", connection=redis_conn)
        queue.enqueue(
            "src.workers.report_worker.generate_report_task",
            report_id=str(report_id),
            report_type=report_type,
            team_id=str(team_id),
            period_start=str(period_start),
            period_end=str(period_end),
            report_format=report_format,
        )
    except Exception:
        # RQ 미설치 또는 Redis 연결 실패 시 무시
        pass


# ──────────────────────────────────────────────────────────────
# POST /generate — 리포트 수동 생성
# ──────────────────────────────────────────────────────────────


@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[GenerateReportResponse],
)
async def generate_report(
    data: GenerateReportRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[GenerateReportResponse]:
    """리포트를 수동으로 생성한다 (비동기).

    owner/admin 권한이 필요하다.
    report_history 레코드를 생성하고 RQ 큐에 생성 작업을 등록한다.
    202를 즉시 반환하며, 완료 여부는 GET /history로 확인한다.
    """
    team_id, role = await _get_user_team_role(db, current_user.id)
    team_id = _require_admin_role(team_id, role)

    report_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # report_history 레코드 생성
    history = ReportHistory(
        id=report_id,
        config_id=None,
        team_id=team_id,
        report_type=data.report_type,
        format=data.format,
        file_path=None,
        period_start=data.period_start,
        period_end=data.period_end,
        status="generating",
        generated_by=current_user.id,
    )
    db.add(history)
    await db.flush()
    await db.commit()

    # RQ 큐에 생성 작업 등록
    enqueue_report_generation(
        report_id=report_id,
        report_type=data.report_type,
        team_id=team_id,
        period_start=data.period_start,
        period_end=data.period_end,
        report_format=data.format,
    )

    return ApiResponse(
        success=True,
        data=GenerateReportResponse(
            report_id=report_id,
            status="generating",
            report_type=data.report_type,
            estimated_completion_seconds=30,
        ),
        error=None,
    )


# ──────────────────────────────────────────────────────────────
# GET /history — 리포트 이력 조회
# ──────────────────────────────────────────────────────────────


@router.get(
    "/history",
    response_model=ApiResponse[list[ReportHistoryResponse]],
)
async def list_report_history(
    current_user: CurrentUser,
    db: DbSession,
    report_type: str | None = Query(default=None, description="리포트 유형 필터"),
    report_status: str | None = Query(default=None, alias="status", description="상태 필터"),
    page: int = Query(default=1, ge=1, description="페이지 번호"),
    per_page: int = Query(default=20, ge=1, le=100, description="페이지당 항목 수"),
) -> ApiResponse[list[ReportHistoryResponse]]:
    """팀의 리포트 생성 이력을 조회한다.

    팀에 소속되지 않은 경우 빈 목록을 반환한다.
    """
    team_id = await _get_user_team_id(db, current_user.id)
    if team_id is None:
        return ApiResponse(success=True, data=[], error=None)

    query = select(ReportHistory).where(ReportHistory.team_id == team_id)

    if report_type is not None:
        query = query.where(ReportHistory.report_type == report_type)

    if report_status is not None:
        query = query.where(ReportHistory.status == report_status)

    query = (
        query.order_by(ReportHistory.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )

    result = await db.execute(query)
    histories = list(result.scalars().all())

    return ApiResponse(
        success=True,
        data=[
            ReportHistoryResponse(
                id=h.id,
                config_id=h.config_id,
                team_id=h.team_id,
                report_type=h.report_type,
                format=h.format,
                file_path=h.file_path,
                file_size_bytes=h.file_size_bytes,
                period_start=h.period_start,
                period_end=h.period_end,
                status=h.status,
                email_sent_at=h.email_sent_at,
                email_recipients=h.email_recipients,
                error_message=h.error_message,
                # ORM 속성은 report_meta (SQLAlchemy 예약어 충돌 방지)
                # Mock/실제 모두 호환하기 위해 fallback 처리 — dict인 경우만 반환
                metadata=_safe_get_metadata(h),
                generated_by=h.generated_by,
                created_at=h.created_at,
            )
            for h in histories
        ],
        error=None,
    )


# ──────────────────────────────────────────────────────────────
# GET /{report_id}/download — 리포트 다운로드
# ──────────────────────────────────────────────────────────────


@router.get("/{report_id}/download")
async def download_report(
    report_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> FileResponse:
    """생성된 리포트 파일을 다운로드한다.

    - 404: 존재하지 않거나 다른 팀의 리포트
    - 409: 아직 생성 중 (status='generating')
    - 410: 파일이 삭제됨
    """
    team_id = await _get_user_team_id(db, current_user.id)

    history = await get_report_by_id(db, report_id)

    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="리포트를 찾을 수 없습니다.",
        )

    # 다른 팀 리포트 접근 차단
    if team_id is None or history.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="리포트를 찾을 수 없습니다.",
        )

    # 생성 중인 경우
    if history.status == "generating":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="리포트가 아직 생성 중입니다.",
        )

    # 파일이 없거나 삭제된 경우
    if history.file_path is None or not os.path.exists(history.file_path):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="리포트 파일이 삭제되었습니다.",
        )

    # Content-Type 결정
    if history.format == "json":
        media_type = "application/json"
    else:
        media_type = "application/pdf"

    filename = f"{history.report_type}_report_{history.period_start}.{history.format}"

    return FileResponse(
        path=history.file_path,
        media_type=media_type,
        filename=filename,
    )


# ──────────────────────────────────────────────────────────────
# POST /config — 리포트 스케줄 설정 생성
# ──────────────────────────────────────────────────────────────


@router.post(
    "/config",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[ReportConfigResponse],
)
async def create_config(
    data: ReportConfigCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[ReportConfigResponse]:
    """리포트 자동 생성 스케줄 설정을 생성한다.

    owner/admin 권한이 필요하다.
    같은 팀에 동일 report_type이 존재하면 409를 반환한다.
    """
    team_id, role = await _get_user_team_role(db, current_user.id)
    team_id = _require_admin_role(team_id, role)

    now = datetime.now(timezone.utc)
    next_gen = calculate_next_generation(data.schedule, now)

    config = ReportConfig(
        id=uuid.uuid4(),
        team_id=team_id,
        report_type=data.report_type,
        schedule=data.schedule,
        email_recipients=list(map(str, data.email_recipients)),
        is_active=data.is_active,
        next_generation_at=next_gen,
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )

    try:
        config = await create_report_config(db, config)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="동일한 리포트 유형의 설정이 이미 존재합니다.",
        )

    return ApiResponse(
        success=True,
        data=ReportConfigResponse(
            id=config.id,
            team_id=config.team_id,
            report_type=config.report_type,
            schedule=config.schedule,
            email_recipients=config.email_recipients,
            is_active=config.is_active,
            last_generated_at=config.last_generated_at,
            next_generation_at=config.next_generation_at,
            created_by=config.created_by,
            created_at=config.created_at,
            updated_at=config.updated_at,
        ),
        error=None,
    )


# ──────────────────────────────────────────────────────────────
# GET /config — 설정 목록 조회
# ──────────────────────────────────────────────────────────────


@router.get(
    "/config",
    response_model=ApiResponse[list[ReportConfigResponse]],
)
async def list_configs(
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[list[ReportConfigResponse]]:
    """팀의 리포트 스케줄 설정 목록을 조회한다."""
    team_id = await _get_user_team_id(db, current_user.id)
    if team_id is None:
        return ApiResponse(success=True, data=[], error=None)

    result = await db.execute(
        select(ReportConfig).where(ReportConfig.team_id == team_id)
    )
    configs = list(result.scalars().all())

    return ApiResponse(
        success=True,
        data=[
            ReportConfigResponse(
                id=c.id,
                team_id=c.team_id,
                report_type=c.report_type,
                schedule=c.schedule,
                email_recipients=c.email_recipients,
                is_active=c.is_active,
                last_generated_at=c.last_generated_at,
                next_generation_at=c.next_generation_at,
                created_by=c.created_by,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in configs
        ],
        error=None,
    )


# ──────────────────────────────────────────────────────────────
# PATCH /config/{config_id} — 설정 수정
# ──────────────────────────────────────────────────────────────


@router.patch(
    "/config/{config_id}",
    response_model=ApiResponse[ReportConfigResponse],
)
async def update_config(
    config_id: uuid.UUID,
    data: ReportConfigUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[ReportConfigResponse]:
    """리포트 스케줄 설정을 수정한다.

    owner/admin 권한이 필요하다.
    부분 업데이트를 지원한다.
    """
    team_id, role = await _get_user_team_role(db, current_user.id)
    team_id = _require_admin_role(team_id, role)

    result = await db.execute(
        select(ReportConfig).where(
            ReportConfig.id == config_id,
            ReportConfig.team_id == team_id,
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="리포트 설정을 찾을 수 없습니다.",
        )

    now = datetime.now(timezone.utc)

    if data.schedule is not None:
        config.schedule = data.schedule
        # 스케줄 변경 시 next_generation_at 재계산
        config.next_generation_at = calculate_next_generation(data.schedule, now)

    if data.email_recipients is not None:
        config.email_recipients = list(map(str, data.email_recipients))

    if data.is_active is not None:
        config.is_active = data.is_active

    config.updated_at = now

    await db.flush()
    await db.commit()

    return ApiResponse(
        success=True,
        data=ReportConfigResponse(
            id=config.id,
            team_id=config.team_id,
            report_type=config.report_type,
            schedule=config.schedule,
            email_recipients=config.email_recipients,
            is_active=config.is_active,
            last_generated_at=config.last_generated_at,
            next_generation_at=config.next_generation_at,
            created_by=config.created_by,
            created_at=config.created_at,
            updated_at=config.updated_at,
        ),
        error=None,
    )


# ──────────────────────────────────────────────────────────────
# DELETE /config/{config_id} — 설정 삭제
# ──────────────────────────────────────────────────────────────


@router.delete(
    "/config/{config_id}",
    response_model=ApiResponse[dict],
)
async def delete_config(
    config_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[dict]:
    """리포트 스케줄 설정을 삭제한다.

    owner/admin 권한이 필요하다.
    """
    team_id, role = await _get_user_team_role(db, current_user.id)
    team_id = _require_admin_role(team_id, role)

    result = await db.execute(
        select(ReportConfig).where(
            ReportConfig.id == config_id,
            ReportConfig.team_id == team_id,
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="리포트 설정을 찾을 수 없습니다.",
        )

    await db.delete(config)
    await db.commit()

    return ApiResponse(
        success=True,
        data={"deleted_id": str(config_id)},
        error=None,
    )
