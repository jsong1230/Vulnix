"""인증 관련 엔드포인트 — GitHub OAuth 기반 JWT 발급"""

from fastapi import APIRouter

from src.api.deps import CurrentUser, DbSession
from src.schemas.auth import GitHubOAuthRequest, TokenRefreshRequest, TokenResponse, UserMeResponse
from src.schemas.common import ApiResponse

router = APIRouter()


@router.post("/github", response_model=ApiResponse[TokenResponse])
async def github_oauth_login(
    request: GitHubOAuthRequest,
    db: DbSession,
) -> ApiResponse[TokenResponse]:
    """GitHub OAuth 로그인.

    프론트엔드에서 GitHub OAuth 인증 코드(code)를 받아 JWT를 발급한다.

    처리 흐름:
    1. GitHub에 code를 전달하여 access_token 교환
    2. access_token으로 GitHub 사용자 정보 조회
    3. DB에서 User 조회 또는 생성 (upsert)
    4. JWT Access Token + Refresh Token 발급

    TODO:
    - httpx로 GitHub OAuth 토큰 교환 API 호출
    - GitHub 사용자 정보 조회 (GET /user)
    - AuthService.create_or_update_user() 호출
    - AuthService.create_jwt_token() 호출
    """
    raise NotImplementedError("TODO: GitHub OAuth 로그인 구현")


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
async def refresh_token(
    request: TokenRefreshRequest,
    db: DbSession,
) -> ApiResponse[TokenResponse]:
    """Access Token 갱신.

    유효한 Refresh Token을 받아 새로운 Access Token을 발급한다.

    TODO:
    - Refresh Token 유효성 검증
    - 새 Access Token 발급
    """
    raise NotImplementedError("TODO: 토큰 갱신 구현")


@router.get("/me", response_model=ApiResponse[UserMeResponse])
async def get_me(
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[UserMeResponse]:
    """현재 로그인 사용자 정보 조회.

    TODO:
    - current_user를 UserMeResponse로 변환
    - 팀 멤버십 정보 함께 반환
    """
    raise NotImplementedError("TODO: 현재 사용자 정보 조회 구현")
