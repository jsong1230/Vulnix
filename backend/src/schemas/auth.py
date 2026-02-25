"""인증 관련 요청/응답 스키마"""

import uuid

from pydantic import BaseModel, Field


class GitHubOAuthRequest(BaseModel):
    """GitHub OAuth 로그인 요청"""

    code: str = Field(description="GitHub OAuth 인증 코드")
    state: str | None = Field(default=None, description="CSRF 방지용 state 파라미터")


class TokenResponse(BaseModel):
    """JWT 토큰 응답"""

    access_token: str = Field(description="Access Token (30분 유효)")
    refresh_token: str = Field(description="Refresh Token (7일 유효)")
    token_type: str = Field(default="Bearer")


class TokenRefreshRequest(BaseModel):
    """Access Token 갱신 요청"""

    refresh_token: str = Field(description="유효한 Refresh Token")


class UserMeResponse(BaseModel):
    """현재 로그인 사용자 정보 응답"""

    id: uuid.UUID
    github_login: str
    email: str | None
    avatar_url: str | None
    teams: list[dict] = Field(default_factory=list, description="소속 팀 목록")

    model_config = {"from_attributes": True}
