"""상세 헬스체크 엔드포인트"""
from fastapi import APIRouter
from sqlalchemy import text

from src.api.deps import _async_session_factory
from src.config import get_settings

router = APIRouter()

settings = get_settings()

_APP_VERSION = "1.0.0"


@router.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """기본 헬스체크 — 로드밸런서 및 컨테이너 헬스체크용"""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
    }


@router.get("/health/detailed", tags=["system"])
async def health_detailed() -> dict[str, object]:
    """DB, Redis 연결 상태 포함 상세 헬스체크.

    - database: SELECT 1 실행 결과
    - redis: PING 결과
    - overall: 모든 항목이 ok일 때 "ok", 하나라도 오류면 "degraded"
    """
    checks: dict[str, str] = {}

    # DB 연결 확인
    try:
        async with _async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {str(exc)[:50]}"

    # Redis 연결 확인
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()  # type: ignore[misc]
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {str(exc)[:50]}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {
        "status": overall,
        "checks": checks,
        "version": _APP_VERSION,
    }
