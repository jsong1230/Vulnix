"""요청/응답 구조화 로깅 미들웨어"""
import json
import logging
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("vulnix.access")

# 로깅에서 제외할 경로 (헬스체크 등 반복적 요청)
_SKIP_PATHS = {"/health", "/health/detailed"}


class LoggingMiddleware(BaseHTTPMiddleware):
    """모든 HTTP 요청/응답을 구조화된 JSON으로 로깅한다.

    - 민감 헤더(Authorization, X-Api-Key)는 마스킹 처리
    - 4xx/5xx 응답은 WARNING 레벨로 기록
    - 2xx/3xx 응답은 INFO 레벨로 기록
    - 응답 헤더에 X-Request-ID 추가
    """

    async def dispatch(self, request: Request, call_next: object) -> Response:
        # 헬스체크 경로는 로깅 생략
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)  # type: ignore[operator]

        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # 민감 헤더 마스킹
        headers: dict[str, str] = dict(request.headers)
        if "authorization" in headers:
            headers["authorization"] = "Bearer ***"
        if "x-api-key" in headers:
            headers["x-api-key"] = "***"

        response: Response = await call_next(request)  # type: ignore[operator]

        duration_ms = round((time.time() - start_time) * 1000, 2)

        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": request.client.host if request.client else None,
        }

        if response.status_code >= 400:
            logger.warning(json.dumps(log_data))
        else:
            logger.info(json.dumps(log_data))

        response.headers["X-Request-ID"] = request_id
        return response
