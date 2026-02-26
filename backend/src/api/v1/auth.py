"""인증 관련 엔드포인트 — GitHub OAuth 기반 JWT 발급"""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from src.api.deps import CurrentUser, DbSession
from src.models.user import User
from src.schemas.auth import GitHubOAuthRequest, TokenRefreshRequest, TokenResponse, UserMeResponse
from src.schemas.common import ApiResponse
from src.services.auth_service import AuthService

router = APIRouter()


@router.post("/github", response_model=ApiResponse[TokenResponse])
async def github_oauth_login(
    request: GitHubOAuthRequest,
    db: DbSession,
) -> ApiResponse[TokenResponse]:
    """GitHub OAuth 로그인.

    처리 흐름:
    1. GitHub에 code를 전달하여 access_token 교환
    2. access_token으로 GitHub 사용자 정보 조회
    3. DB에서 User 조회 또는 생성 (upsert)
    4. JWT Access Token + Refresh Token 발급
    """
    auth_service = AuthService()

    try:
        github_token = await auth_service.exchange_github_code(request.code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"GitHub 인증 코드 교환 실패: {e}")

    try:
        github_user = await auth_service.get_github_user(github_token)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"GitHub 사용자 정보 조회 실패: {e}")

    result = await db.execute(select(User).where(User.github_id == github_user["id"]))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            github_id=github_user["id"],
            github_login=github_user["login"],
            email=github_user.get("email"),
            avatar_url=github_user.get("avatar_url"),
        )
        db.add(user)
    else:
        user.github_login = github_user["login"]
        user.email = github_user.get("email")
        user.avatar_url = github_user.get("avatar_url")

    await db.flush()
    await db.refresh(user)

    access_token = auth_service.create_access_token(str(user.id))
    refresh_token = auth_service.create_refresh_token(str(user.id))

    return ApiResponse(
        success=True,
        data=TokenResponse(access_token=access_token, refresh_token=refresh_token),
    )


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
    """현재 로그인 사용자 정보 조회."""
    return ApiResponse(
        success=True,
        data=UserMeResponse(
            id=current_user.id,
            github_login=current_user.github_login,
            email=current_user.email,
            avatar_url=current_user.avatar_url,
            teams=[],
        ),
    )
