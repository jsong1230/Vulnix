"""공통 의존성 — DB 세션, 현재 사용자 인증 등 FastAPI Depends로 주입"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Annotated, AsyncGenerator

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings
from src.models.api_key import ApiKey
from src.models.team import TeamMember
from src.models.user import User

settings = get_settings()

# ---- DB 세션 팩토리 ----
# TODO: 앱 시작 시(lifespan) 엔진을 생성하고, app.state에 저장하는 방식으로 개선
_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)
_async_session_factory = async_sessionmaker(
    _engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """비동기 DB 세션을 생성하고 요청 완료 후 자동으로 닫는다."""
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---- 인증 의존성 ----
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """JWT Bearer 토큰을 검증하고 현재 사용자를 반환한다.

    Raises:
        HTTPException: 401 - 유효하지 않은 토큰 또는 사용자 없음
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="유효하지 않은 인증 정보입니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    # Bearer 토큰에서 JWT 디코드
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        raise credentials_exception

    # payload에서 sub(user_id) 추출
    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    # UUID 파싱
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    # DB에서 User 조회
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    return user


async def get_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-Api-Key")] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> "ApiKey":
    """X-Api-Key 헤더로 인증하고 ApiKey 객체를 반환한다. IDE 전용 엔드포인트에서 사용.

    인증 흐름:
    1. X-Api-Key 헤더 존재 여부 확인
    2. SHA-256 해시 후 api_key 테이블 조회
    3. 비활성화 여부 확인 (is_active=False → 403)
    4. 만료 여부 확인 (expires_at 초과 → 401)
    5. last_used_at 업데이트

    Raises:
        HTTPException: 401 - API Key 누락 또는 유효하지 않음
        HTTPException: 403 - 비활성화된 API Key
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "INVALID_API_KEY", "message": "X-Api-Key 헤더가 필요합니다."},
        )

    # SHA-256 해시 후 DB 조회
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "INVALID_API_KEY", "message": "유효하지 않은 API Key입니다."},
        )

    # 비활성화 확인 (is_active=False → 403)
    if not api_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "API_KEY_DISABLED", "message": "비활성화된 API Key입니다."},
        )

    # 만료 확인 (expires_at이 설정되어 있고 현재 시각보다 이전 → 401)
    if api_key.expires_at is not None:
        now = datetime.now(timezone.utc)
        expires = api_key.expires_at
        # timezone-aware 비교 보장
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "INVALID_API_KEY", "message": "만료된 API Key입니다."},
            )

    # last_used_at 업데이트
    api_key.last_used_at = datetime.now(timezone.utc)
    await db.flush()

    return api_key


# 타입 별칭 — 라우터에서 간결하게 사용
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
IdeApiKey = Annotated["ApiKey", Depends(get_api_key)]
