"""API Key 서비스 — 생성/검증/비활성화"""

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.api_key import ApiKey
from src.models.team import TeamMember

logger = logging.getLogger(__name__)

# API Key 형식 접두사
_KEY_PREFIX_LIVE = "vx_live_"


class ApiKeyService:
    """API Key CRUD 서비스."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_key(
        self,
        team_id: uuid.UUID,
        name: str,
        created_by: uuid.UUID,
        expires_in_days: int | None = None,
    ) -> dict:
        """팀용 API Key를 생성하고 원본 key를 포함한 응답을 반환한다.

        Args:
            team_id: 소속 팀 ID
            name: 키 이름
            created_by: 발급자 User ID
            expires_in_days: 만료 기간 (일, None이면 무기한)

        Returns:
            {id, name, key(원본), key_prefix, expires_at, created_at}
        """
        # key 생성: vx_live_ + 32바이트 랜덤 (URL-safe base64)
        raw_token = secrets.token_urlsafe(32)
        key_value = f"{_KEY_PREFIX_LIVE}{raw_token}"
        key_prefix = key_value[:12]  # "vx_live_xxxx" (12자)

        # SHA-256 해시
        key_hash = hashlib.sha256(key_value.encode()).hexdigest()

        # 만료 일시 계산
        expires_at = None
        if expires_in_days is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        api_key = ApiKey(
            team_id=team_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            is_active=True,
            created_by=created_by,
            expires_at=expires_at,
        )
        self._db.add(api_key)
        await self._db.flush()
        await self._db.refresh(api_key)

        return {
            "id": str(api_key.id),
            "name": api_key.name,
            "key": key_value,
            "key_prefix": key_prefix,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "created_at": api_key.created_at.isoformat() if api_key.created_at else None,
        }

    async def list_keys(self, team_id: uuid.UUID) -> list[ApiKey]:
        """팀의 API Key 목록을 반환한다 (key 원본 미포함).

        Args:
            team_id: 팀 ID

        Returns:
            ApiKey ORM 객체 목록
        """
        result = await self._db.execute(
            select(ApiKey).where(
                ApiKey.team_id == team_id,
                ApiKey.revoked_at == None,  # noqa: E711
            )
        )
        return result.scalars().all()

    async def revoke_key(
        self,
        key_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> dict:
        """API Key를 논리 삭제(비활성화)한다.

        Args:
            key_id: 비활성화할 API Key ID
            team_id: 팀 ID (교차 팀 접근 방지)

        Returns:
            {id, name, is_active, revoked_at}

        Raises:
            ValueError: 해당 Key가 존재하지 않거나 다른 팀 소속일 때
        """
        result = await self._db.execute(
            select(ApiKey).where(
                ApiKey.id == key_id,
                ApiKey.team_id == team_id,
            )
        )
        api_key = result.scalar_one_or_none()

        if api_key is None:
            raise ValueError(f"API Key를 찾을 수 없습니다: {key_id}")

        now = datetime.now(timezone.utc)
        api_key.is_active = False
        api_key.revoked_at = now

        return {
            "id": str(api_key.id),
            "name": api_key.name,
            "is_active": False,
            "revoked_at": now.isoformat(),
        }

    async def get_team_id_for_user(self, user_id: uuid.UUID) -> uuid.UUID | None:
        """사용자의 팀 ID를 조회한다.

        Args:
            user_id: 사용자 ID

        Returns:
            팀 ID 또는 None
        """
        result = await self._db.execute(
            select(TeamMember.team_id).where(TeamMember.user_id == user_id).limit(1)
        )
        row = result.scalar_one_or_none()
        return row

    async def get_user_role_in_team(
        self, user_id: uuid.UUID, team_id: uuid.UUID
    ) -> str | None:
        """사용자의 팀 내 역할을 조회한다.

        Args:
            user_id: 사용자 ID
            team_id: 팀 ID

        Returns:
            역할 문자열 (owner/admin/member) 또는 None
        """
        result = await self._db.execute(
            select(TeamMember.role).where(
                TeamMember.user_id == user_id,
                TeamMember.team_id == team_id,
            )
        )
        return result.scalar_one_or_none()
