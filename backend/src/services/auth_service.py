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
        """GitHub OAuth 코드를 Access Token으로 교환한다."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GITHUB_TOKEN_URL,
                json={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                raise ValueError(data.get("error_description", data["error"]))
            return data["access_token"]

    async def get_github_user(self, access_token: str) -> dict:
        """GitHub Access Token으로 사용자 정보를 조회한다."""
        async with httpx.AsyncClient() as client:
            user_resp = await client.get(
                GITHUB_USER_API_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            user_resp.raise_for_status()
            user_data = user_resp.json()

            # 이메일이 비공개인 경우 /user/emails에서 primary 이메일 조회
            if not user_data.get("email"):
                emails_resp = await client.get(
                    "https://api.github.com/user/emails",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                )
                if emails_resp.status_code == 200:
                    primary = next(
                        (e["email"] for e in emails_resp.json() if e.get("primary") and e.get("verified")),
                        None,
                    )
                    user_data["email"] = primary

            return user_data

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
