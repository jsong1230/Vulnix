"""인증 서비스 — GitHub OAuth, JWT 발급/검증"""

from datetime import datetime, timedelta

import httpx
from jose import JWTError, jwt

from src.config import get_settings

settings = get_settings()

# GitHub OAuth 토큰 교환 URL
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
# GitHub 사용자 정보 URL
GITHUB_USER_API_URL = "https://api.github.com/user"


class AuthService:
    """GitHub OAuth 로그인 및 JWT 토큰 관리 서비스."""

    async def exchange_github_code(self, code: str) -> str:
        """GitHub OAuth 코드를 Access Token으로 교환한다.

        Args:
            code: GitHub OAuth 인증 코드

        Returns:
            GitHub Access Token

        TODO:
        - httpx로 GitHub token endpoint POST 호출
        - access_token 추출 및 반환
        """
        raise NotImplementedError("TODO: GitHub 코드 교환 구현")

    async def get_github_user(self, access_token: str) -> dict:
        """GitHub Access Token으로 사용자 정보를 조회한다.

        Returns:
            GitHub 사용자 정보 (id, login, email, avatar_url 등)

        TODO:
        - GET /user API 호출
        - GET /user/emails API 호출 (이메일 공개 여부에 따라)
        """
        raise NotImplementedError("TODO: GitHub 사용자 정보 조회 구현")

    def create_access_token(self, user_id: str) -> str:
        """JWT Access Token을 발급한다.

        Args:
            user_id: 사용자 UUID

        Returns:
            JWT Access Token (30분 유효)

        TODO:
        - python-jose로 JWT 생성
        - exp: 현재 시각 + JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        - sub: user_id
        """
        expire = datetime.utcnow() + timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )
        payload = {
            "sub": user_id,
            "exp": expire,
            "type": "access",
        }
        return jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

    def create_refresh_token(self, user_id: str) -> str:
        """JWT Refresh Token을 발급한다.

        Args:
            user_id: 사용자 UUID

        Returns:
            JWT Refresh Token (7일 유효)
        """
        expire = datetime.utcnow() + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
        payload = {
            "sub": user_id,
            "exp": expire,
            "type": "refresh",
        }
        return jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

    def verify_token(self, token: str) -> dict:
        """JWT 토큰을 검증하고 페이로드를 반환한다.

        Args:
            token: JWT 토큰 문자열

        Returns:
            토큰 페이로드 (sub, exp, type 포함)

        Raises:
            JWTError: 유효하지 않은 토큰

        TODO:
        - 만료 시간 검증
        - 서명 검증
        """
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
