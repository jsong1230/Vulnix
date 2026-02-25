"""FastAPI 앱 진입점 — CORS, 라우터, lifespan 이벤트 핸들러 설정"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.router import api_router
from src.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """앱 생명주기 이벤트 핸들러.

    startup: DB 연결 풀 초기화, Redis 연결 확인
    shutdown: 연결 풀 정리
    """
    # ---- startup ----
    # TODO: SQLAlchemy async 엔진 초기화
    # TODO: Redis 연결 확인
    print(f"[{settings.APP_NAME}] 서버 시작 중... (env={settings.APP_ENV})")

    yield

    # ---- shutdown ----
    # TODO: DB 연결 풀 종료
    # TODO: Redis 연결 종료
    print(f"[{settings.APP_NAME}] 서버 종료")


def create_app() -> FastAPI:
    """FastAPI 앱 팩토리"""
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
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

    # API v1 라우터 등록
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """헬스체크 엔드포인트 — 로드밸런서 및 컨테이너 헬스체크용"""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
    }
