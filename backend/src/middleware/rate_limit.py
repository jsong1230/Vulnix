"""Redis 기반 슬라이딩 윈도우 Rate Limit 미들웨어 (IDE 엔드포인트 전용)"""
import time
from collections.abc import Callable, Awaitable

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, Response

# 경로별 rate limit 설정: (최대 요청 수, 윈도우 초)
RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/ide/analyze": (60, 60),
    "/api/v1/ide/patch-suggestion": (10, 60),
    "/api/v1/ide/false-positive-patterns": (30, 60),
}


async def rate_limit_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """슬라이딩 윈도우 방식으로 IDE API rate limit을 적용한다.

    - API Key 앞 12자 또는 클라이언트 IP를 식별자로 사용
    - Redis 오류 발생 시 graceful degradation (rate limit 우회)
    - 초과 시 429 + Retry-After 헤더 반환
    """
    path = request.url.path

    limit_config: tuple[int, int] | None = None
    for pattern, config in RATE_LIMITS.items():
        if path.startswith(pattern):
            limit_config = config
            break

    if limit_config is None:
        return await call_next(request)

    max_requests, window = limit_config

    # API Key 또는 IP 기반 식별자
    api_key = request.headers.get("x-api-key", "")
    identifier = (
        api_key[:12] if api_key else (request.client.host if request.client else "unknown")
    )

    # Redis 슬라이딩 윈도우 카운팅
    try:
        redis_url: str = request.app.state.redis_url
        r = await aioredis.from_url(redis_url)
        key = f"ratelimit:{path}:{identifier}"
        now = int(time.time())
        window_start = now - window

        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window)
        results = await pipe.execute()
        await r.aclose()

        count: int = results[2]
        if count > max_requests:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(window)},
            )
    except HTTPException:
        raise
    except Exception:
        # Redis 오류 시 graceful degradation — rate limit 미적용
        pass

    return await call_next(request)
