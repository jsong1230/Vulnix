"""앱 설정 — pydantic-settings 기반 환경변수 관리"""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """앱 전역 설정. 환경변수 또는 .env 파일에서 로드."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ---- 앱 기본 설정 ----
    APP_NAME: str = "Vulnix"
    APP_ENV: str = Field(default="development", pattern="^(development|staging|production)$")
    DEBUG: bool = False

    # ---- Database ----
    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL 연결 URL (asyncpg 드라이버)",
        examples=["postgresql+asyncpg://user:pass@localhost:5432/vulnix"],
    )

    # ---- Redis ----
    REDIS_URL: str = Field(
        ...,
        description="Redis 연결 URL",
        examples=["redis://localhost:6379"],
    )

    # ---- GitHub App ----
    GITHUB_APP_ID: int = Field(..., description="GitHub App ID")
    GITHUB_APP_PRIVATE_KEY: str = Field(
        ...,
        description="GitHub App Private Key (PEM 형식)",
    )
    GITHUB_WEBHOOK_SECRET: str = Field(..., description="Webhook HMAC-SHA256 서명 시크릿")
    GITHUB_CLIENT_ID: str = Field(..., description="GitHub OAuth App Client ID")
    GITHUB_CLIENT_SECRET: str = Field(..., description="GitHub OAuth App Client Secret")

    # ---- Claude API ----
    ANTHROPIC_API_KEY: str = Field(..., description="Anthropic Claude API 키")

    # ---- JWT ----
    JWT_SECRET_KEY: str = Field(..., description="JWT 서명 비밀키")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT 알고리즘")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=1)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1)

    # ---- CORS ----
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000"],
        description="허용할 오리진 목록",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        """환경변수 문자열을 리스트로 변환 (JSON 배열 또는 쉼표 구분 지원)"""
        if isinstance(value, str):
            import json
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(o).strip() for o in parsed if str(o).strip()]
            except (json.JSONDecodeError, ValueError):
                pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("GITHUB_APP_PRIVATE_KEY", mode="before")
    @classmethod
    def normalize_private_key(cls, value: str) -> str:
        """\\n 이스케이프를 실제 줄바꿈으로 변환"""
        return value.replace("\\n", "\n")

    # ---- SMTP (이메일 발송) ----
    SMTP_HOST: str = Field(default="", description="SMTP 서버 호스트")
    SMTP_PORT: int = Field(default=587, description="SMTP 포트 (기본 587, STARTTLS)")
    SMTP_USERNAME: str = Field(default="", description="SMTP 인증 사용자명")
    SMTP_PASSWORD: str = Field(default="", description="SMTP 인증 비밀번호")
    SMTP_FROM_EMAIL: str = Field(default="", description="발신자 이메일")
    SMTP_FROM_NAME: str = Field(default="Vulnix Security", description="발신자 이름")

    # ---- 리포트 저장 경로 ----
    REPORT_STORAGE_PATH: str = Field(
        default="/data/reports",
        description="리포트 파일 저장 경로 (PoC: 로컬 파일시스템)",
    )

    @property
    def is_production(self) -> bool:
        """프로덕션 환경 여부"""
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    """설정 싱글톤 반환 (앱 시작 시 한 번만 로드)"""
    return Settings()  # type: ignore[call-arg]
