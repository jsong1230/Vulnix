"""IDE 플러그인 전용 API 엔드포인트 (F-11)

엔드포인트 목록:
  - POST /api/v1/ide/analyze                 코드 스니펫 Semgrep 분석 (X-Api-Key 인증)
  - GET  /api/v1/ide/false-positive-patterns 팀 오탐 패턴 목록 (X-Api-Key 인증)
  - POST /api/v1/ide/patch-suggestion        LLM 패치 diff 생성 (X-Api-Key 인증)
  - POST /api/v1/ide/api-keys                API Key 생성 (JWT 인증, owner/admin)
  - GET  /api/v1/ide/api-keys                API Key 목록 조회 (JWT 인증)
  - DELETE /api/v1/ide/api-keys/{id}         API Key 비활성화 (JWT 인증, owner/admin)
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import CurrentUser, DbSession, IdeApiKey, get_db
from src.models.api_key import ApiKey
from src.models.false_positive import FalsePositivePattern
from src.models.team import Team, TeamMember
from src.schemas.api_key import (
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    ApiKeyRevokeResponse,
)
from src.schemas.ide import (
    IdeAnalyzeRequest,
    IdeAnalyzeResponse,
    IdeFalsePositivePattern,
    IdeFalsePositivePatternsResponse,
    IdePatchSuggestionRequest,
    IdePatchSuggestionResponse,
    VulnerabilityDetail,
)
from src.services.api_key_service import ApiKeyService
from src.services.ide_analyzer import IdeAnalyzerService

logger = logging.getLogger(__name__)

router = APIRouter()


# ──────────────────────────────────────────────────────────────
# IDE 분석 엔드포인트 (X-Api-Key 인증)
# ──────────────────────────────────────────────────────────────

@router.post(
    "/analyze",
    summary="코드 스니펫 Semgrep 분석",
    description="단일 파일 코드 스니펫을 Semgrep으로 실시간 분석하여 취약점을 반환한다.",
    tags=["ide"],
)
async def analyze_code(
    request_body: IdeAnalyzeRequest,
    api_key: IdeApiKey,
    db: DbSession,
) -> dict:
    """POST /api/v1/ide/analyze — X-Api-Key 인증."""
    # content 크기 검증 (1MB 초과 시 400)
    from src.schemas.ide import MAX_CONTENT_SIZE_BYTES
    if len(request_body.content.encode("utf-8")) > MAX_CONTENT_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "CONTENT_TOO_LARGE", "message": "content가 1MB를 초과합니다."},
        )

    # ApiKey에서 team_id 직접 추출 (User 조회 불필요)
    team_id = api_key.team_id

    service = IdeAnalyzerService(db)
    result = await service.analyze(
        content=request_body.content,
        language=request_body.language,
        file_path=request_body.file_path,
        team_id=team_id,
    )

    return {
        "success": True,
        "data": result,
        "error": None,
    }


@router.get(
    "/false-positive-patterns",
    summary="팀 오탐 패턴 목록 조회",
    description="팀의 활성 오탐 패턴 목록을 반환한다. ETag 캐싱 지원.",
    tags=["ide"],
)
async def get_false_positive_patterns(
    request: Request,
    response: Response,
    api_key: IdeApiKey,
    db: DbSession,
) -> dict:
    """GET /api/v1/ide/false-positive-patterns — X-Api-Key 인증, ETag 캐싱 지원."""
    # ApiKey에서 team_id 직접 추출
    team_id = api_key.team_id

    # 활성 FP 패턴 조회
    result = await db.execute(
        select(FalsePositivePattern).where(
            FalsePositivePattern.team_id == team_id,
            FalsePositivePattern.is_active == True,  # noqa: E712
        )
    )
    patterns = result.scalars().all()

    # ETag 계산 (패턴 ID + updated_at 기반)
    etag_content = "|".join(
        f"{p.id}:{p.updated_at.isoformat()}"
        for p in patterns
    )
    etag = f'"{hashlib.sha256(etag_content.encode()).hexdigest()[:16]}"'

    # If-None-Match 헤더 확인 (조건부 요청)
    if_none_match = request.headers.get("If-None-Match") or request.headers.get("if-none-match")
    if if_none_match and if_none_match == etag:
        return Response(status_code=304)  # type: ignore[return-value]

    # ETag 헤더 설정
    response.headers["ETag"] = etag

    # last_updated: 패턴 중 가장 최신 updated_at
    last_updated = None
    if patterns:
        last_updated = max(p.updated_at for p in patterns)

    serialized_patterns = [
        {
            "id": str(p.id),
            "semgrep_rule_id": p.semgrep_rule_id,
            "file_pattern": p.file_pattern,
            "reason": p.reason,
            "is_active": p.is_active,
            "updated_at": p.updated_at.isoformat(),
        }
        for p in patterns
    ]

    return {
        "success": True,
        "data": {
            "patterns": serialized_patterns,
            "last_updated": last_updated.isoformat() if last_updated else None,
            "etag": etag,
        },
        "error": None,
    }


@router.post(
    "/patch-suggestion",
    summary="LLM 기반 패치 diff 생성",
    description="특정 취약점에 대해 LLM 기반 패치 diff를 생성한다.",
    tags=["ide"],
)
async def patch_suggestion(
    request_body: IdePatchSuggestionRequest,
    api_key: IdeApiKey,
    db: DbSession,
) -> dict:
    """POST /api/v1/ide/patch-suggestion — X-Api-Key 인증."""
    service = IdeAnalyzerService(db)
    result = await service.generate_patch(
        content=request_body.content,
        language=request_body.language,
        file_path=request_body.file_path,
        finding=request_body.finding.model_dump(),
    )

    return {
        "success": True,
        "data": result,
        "error": None,
    }


# ──────────────────────────────────────────────────────────────
# API Key CRUD 엔드포인트 (JWT 인증)
# ──────────────────────────────────────────────────────────────

@router.post(
    "/api-keys",
    status_code=status.HTTP_201_CREATED,
    summary="API Key 생성",
    description="팀용 IDE API Key를 생성한다. owner/admin 역할만 허용.",
    tags=["ide", "api-keys"],
)
async def create_api_key(
    request_body: ApiKeyCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """POST /api/v1/ide/api-keys — JWT 인증, owner/admin 전용."""
    # team_id 조회
    team_result = await db.execute(
        select(TeamMember.team_id, TeamMember.role).where(
            TeamMember.user_id == current_user.id
        ).limit(1)
    )
    row = team_result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "NO_TEAM", "message": "소속된 팀이 없습니다."},
        )

    team_id, role = row

    # owner/admin 권한 확인
    if role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "FORBIDDEN", "message": "admin/owner 권한이 필요합니다."},
        )

    service = ApiKeyService(db)
    result = await service.create_key(
        team_id=team_id,
        name=request_body.name,
        created_by=current_user.id,
        expires_in_days=request_body.expires_in_days,
    )

    return {
        "success": True,
        "data": result,
        "error": None,
    }


@router.get(
    "/api-keys",
    summary="API Key 목록 조회",
    description="팀의 발급된 API Key 목록을 반환한다. key 원본 값은 미포함.",
    tags=["ide", "api-keys"],
)
async def list_api_keys(
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """GET /api/v1/ide/api-keys — JWT 인증."""
    # team_id 조회
    team_result = await db.execute(
        select(TeamMember.team_id).where(
            TeamMember.user_id == current_user.id
        ).limit(1)
    )
    team_id = team_result.scalar_one_or_none()
    if team_id is None:
        return {"success": True, "data": [], "error": None}

    # API Key 목록 조회 (revoked_at이 없는 것만)
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.team_id == team_id,
            ApiKey.revoked_at == None,  # noqa: E711
            ApiKey.is_active == True,  # noqa: E712
        )
    )
    api_keys = result.scalars().all()

    serialized = [
        {
            "id": str(k.id),
            "name": k.name,
            "key_prefix": k.key_prefix,
            "is_active": k.is_active,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "expires_at": k.expires_at.isoformat() if k.expires_at else None,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        }
        for k in api_keys
    ]

    return {
        "success": True,
        "data": serialized,
        "error": None,
    }


@router.delete(
    "/api-keys/{key_id}",
    summary="API Key 비활성화",
    description="API Key를 논리 삭제(비활성화)한다. owner/admin 역할만 허용.",
    tags=["ide", "api-keys"],
)
async def revoke_api_key(
    key_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """DELETE /api/v1/ide/api-keys/{key_id} — JWT 인증, owner/admin 전용."""
    # team_id + 역할 조회
    team_result = await db.execute(
        select(TeamMember.team_id, TeamMember.role).where(
            TeamMember.user_id == current_user.id
        ).limit(1)
    )
    row = team_result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "NO_TEAM", "message": "소속된 팀이 없습니다."},
        )

    team_id, role = row

    # owner/admin 권한 확인
    if role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "FORBIDDEN", "message": "admin/owner 권한이 필요합니다."},
        )

    service = ApiKeyService(db)
    try:
        result = await service.revoke_key(key_id=key_id, team_id=team_id)
    except ValueError:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "data": None,
                "error": {"code": "NOT_FOUND", "message": f"API Key를 찾을 수 없습니다: {key_id}"},
            },
        )

    return {
        "success": True,
        "data": result,
        "error": None,
    }
