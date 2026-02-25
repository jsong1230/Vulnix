"""FastAPI 앱 진입점 — CORS, 라우터, lifespan 이벤트 핸들러 설정"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.v1.health import router as health_router
from src.api.v1.router import api_router
from src.config import get_settings
from src.middleware.logging_middleware import LoggingMiddleware
from src.middleware.rate_limit import rate_limit_middleware

settings = get_settings()

# 구조화 로깅 기본 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """앱 생명주기 이벤트 핸들러.

    startup: DB 연결 풀 초기화, Redis 연결 확인
    shutdown: 연결 풀 정리
    """
    # ---- startup ----
    # Redis URL을 app.state에 저장 (rate_limit_middleware에서 참조)
    app.state.redis_url = settings.REDIS_URL
    logging.getLogger("vulnix").info(
        "[%s] 서버 시작 중... (env=%s)", settings.APP_NAME, settings.APP_ENV
    )

    yield

    # ---- shutdown ----
    logging.getLogger("vulnix").info("[%s] 서버 종료", settings.APP_NAME)


def create_app() -> FastAPI:
    """FastAPI 앱 팩토리"""
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description="GitHub 코드 보안 취약점 자동 탐지 및 패치 에이전트 API",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # CORS 미들웨어 설정
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 구조화 로깅 미들웨어 (CORS 다음에 등록 — 실제 요청만 로깅)
    app.add_middleware(LoggingMiddleware)

    # IDE Rate Limit 미들웨어 (함수형 — BaseHTTPMiddleware로 래핑)
    app.add_middleware(BaseHTTPMiddleware, dispatch=rate_limit_middleware)

    # 헬스체크 라우터 등록 (prefix 없이 최상위 경로)
    app.include_router(health_router)

    # API v1 라우터 등록
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
