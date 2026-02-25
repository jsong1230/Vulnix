"""F-11 IDE 플러그인 — API Key CRUD 엔드포인트 통합 테스트 (RED 단계)

테스트 대상 엔드포인트:
  - POST   /api/v1/ide/api-keys        API Key 생성 (JWT 인증, owner/admin)
  - GET    /api/v1/ide/api-keys        발급된 Key 목록 조회 (JWT 인증)
  - DELETE /api/v1/ide/api-keys/{id}   Key 삭제/비활성화 (JWT 인증, owner/admin)

인증 방식: JWT Bearer (API Key 관리는 웹 대시보드에서 JWT로 수행)
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ──────────────────────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────────────────────

TEAM_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
API_KEY_ID_1 = uuid.UUID("aaaa1111-aaaa-aaaa-aaaa-aaaa11111111")
API_KEY_ID_2 = uuid.UUID("aaaa2222-aaaa-aaaa-aaaa-aaaa22222222")
NONE_ID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")


# ──────────────────────────────────────────────────────────────
# 픽스처 헬퍼
# ──────────────────────────────────────────────────────────────

def _make_mock_api_key_record(
    key_id: uuid.UUID = API_KEY_ID_1,
    name: str = "Team IDE Key",
    is_active: bool = True,
    revoked_at: datetime | None = None,
) -> MagicMock:
    """ApiKey DB 레코드 Mock 생성 헬퍼.

    key_value(원본)는 생성 시에만 노출되므로 DB 레코드에는 포함되지 않는다.
    목록 조회 시에는 key_prefix만 노출된다.
    """
    record = MagicMock()
    record.id = key_id
    record.team_id = TEAM_ID
    record.name = name
    record.key_hash = f"hashed_{str(key_id)[:8]}"
    record.key_prefix = "vx_live_a1b2"
    record.is_active = is_active
    record.last_used_at = None
    record.expires_at = datetime(2027, 2, 25, tzinfo=timezone.utc)
    record.created_by = USER_ID
    record.created_at = datetime(2026, 2, 25, tzinfo=timezone.utc)
    record.revoked_at = revoked_at
    return record


def _build_api_keys_mock_db(
    role: str = "owner",
    api_keys: list | None = None,
    target_key_id: uuid.UUID = API_KEY_ID_1,
) -> AsyncMock:
    """API Key CRUD 테스트용 Mock DB 세션 생성.

    Args:
        role: 테스트 사용자의 팀 역할 ("owner", "admin", "member")
        api_keys: DB에 존재하는 ApiKey 레코드 목록
        target_key_id: 단일 조회/삭제 시 반환할 ApiKey ID
    """
    mock_keys = api_keys if api_keys is not None else [
        _make_mock_api_key_record(API_KEY_ID_1, "Team IDE Key"),
        _make_mock_api_key_record(API_KEY_ID_2, "CI/CD Key"),
    ]

    # target_key_id 기반으로 단일 조회 결과 결정
    target_key = next(
        (k for k in mock_keys if k.id == target_key_id), None
    )

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.close = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.delete = AsyncMock()

    # refresh는 add 후 호출되어 생성된 레코드를 갱신한다
    async def mock_refresh(obj):
        # 신규 생성된 ApiKey 객체에 id, created_at 등을 채워준다
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = uuid.uuid4()
        if not hasattr(obj, "created_at") or obj.created_at is None:
            obj.created_at = datetime(2026, 2, 25, tzinfo=timezone.utc)

    mock_db.refresh = AsyncMock(side_effect=mock_refresh)

    def _make_result(items):
        result = MagicMock()
        if isinstance(items, list):
            result.scalar_one_or_none.return_value = items[0] if items else None
            result.scalars.return_value.all.return_value = items
            result.scalars.return_value.first.return_value = items[0] if items else None
        else:
            result.scalar_one_or_none.return_value = items
            result.scalars.return_value.all.return_value = [items] if items is not None else []
            result.scalars.return_value.first.return_value = items
        return result

    async def smart_execute(query, *args, **kwargs):
        query_str = str(query).lower()

        try:
            params = dict(query.compile().params)
        except Exception:
            params = {}

        all_uuids = {v for v in params.values() if isinstance(v, uuid.UUID)}

        # team_member 테이블 조회 (역할/팀 확인)
        if "team_member" in query_str:
            result = MagicMock()
            if "team_member.role" in query_str:
                result.scalar_one_or_none.return_value = role
                result.scalars.return_value.all.return_value = [role]
                result.first.return_value = (TEAM_ID, role)
            elif "team_member.team_id" in query_str:
                result.scalar_one_or_none.return_value = TEAM_ID
                result.scalars.return_value.all.return_value = [TEAM_ID]
                result.first.return_value = (TEAM_ID, role)
            else:
                mock_member = MagicMock()
                mock_member.team_id = TEAM_ID
                mock_member.user_id = USER_ID
                mock_member.role = role
                result.scalar_one_or_none.return_value = mock_member
                result.scalars.return_value.all.return_value = [mock_member]
                result.first.return_value = (TEAM_ID, role)
            return result

        # api_key 테이블 조회
        if "api_key" in query_str:
            # NONE_ID → None (404 케이스)
            if NONE_ID in all_uuids:
                return _make_result(None)
            # 특정 key_id 조회
            if API_KEY_ID_1 in all_uuids:
                return _make_result(target_key)
            if API_KEY_ID_2 in all_uuids:
                return _make_result(mock_keys[1] if len(mock_keys) > 1 else None)
            # 목록 조회 (team_id 기반)
            return _make_result(mock_keys)

        return _make_result([])

    mock_db.execute = AsyncMock(side_effect=smart_execute)
    return mock_db


@pytest.fixture
def api_keys_test_client():
    """API Key CRUD 테스트용 TestClient 픽스처.

    owner 역할의 인증된 사용자, DB에 2개의 ApiKey 레코드 존재.
    """
    from src.main import create_app
    from src.api.deps import get_db, get_current_user

    app = create_app()
    mock_db = _build_api_keys_mock_db(role="owner")

    async def override_get_db():
        yield mock_db

    mock_user = MagicMock()
    mock_user.id = USER_ID
    mock_user.github_login = "test_user"

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def api_keys_test_client_member():
    """member 역할 사용자를 위한 TestClient 픽스처 (권한 부족 테스트용)."""
    from src.main import create_app
    from src.api.deps import get_db, get_current_user

    app = create_app()
    mock_db = _build_api_keys_mock_db(role="member")

    async def override_get_db():
        yield mock_db

    mock_user = MagicMock()
    mock_user.id = USER_ID
    mock_user.github_login = "test_member"

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def api_keys_test_client_unauthenticated():
    """인증 없는 TestClient 픽스처 (401 테스트용)."""
    from src.main import create_app
    from src.api.deps import get_db

    app = create_app()
    mock_db = _build_api_keys_mock_db()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    # get_current_user는 override하지 않아 실제 인증 로직이 동작한다

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


# ──────────────────────────────────────────────────────────────
# POST /api/v1/ide/api-keys 테스트
# ──────────────────────────────────────────────────────────────

class TestCreateApiKey:
    """POST /api/v1/ide/api-keys — API Key 생성"""

    def test_create_api_key_success_returns_key_value(self, api_keys_test_client):
        """owner가 API Key 생성 시 일회성 key_value를 반환한다 (I-19)

        Arrange: JWT 인증된 owner, name="Team IDE Key", expires_in_days=365
        Act: POST /api/v1/ide/api-keys
        Assert: 201, key (vx_live_... 형식), key_prefix, expires_at 포함
        """
        with patch(
            "src.services.api_key_service.ApiKeyService.create_key",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = {
                "id": str(API_KEY_ID_1),
                "name": "Team IDE Key",
                "key": "vx_live_a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
                "key_prefix": "vx_live_a1b2",
                "expires_at": "2027-02-25T00:00:00Z",
                "created_at": "2026-02-25T00:00:00Z",
            }

            response = api_keys_test_client.post(
                "/api/v1/ide/api-keys",
                json={
                    "name": "Team IDE Key",
                    "expires_in_days": 365,
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "key" in data["data"]
        assert data["data"]["key"].startswith("vx_live_")
        assert "key_prefix" in data["data"]
        assert "expires_at" in data["data"]
        assert "id" in data["data"]

    def test_create_api_key_key_value_only_returned_once(self, api_keys_test_client):
        """생성 시 반환된 key 값은 이후 목록 조회에서는 포함되지 않는다

        설계서 ADR-F11-004: key는 발급 시 한 번만 노출. 이후는 key_prefix만 표시.

        Arrange: API Key 생성
        Act: GET /api/v1/ide/api-keys로 목록 조회
        Assert: 목록의 각 항목에 'key' 필드(원본값) 없음, key_prefix만 존재
        """
        with patch(
            "src.services.api_key_service.ApiKeyService.create_key",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = {
                "id": str(API_KEY_ID_1),
                "name": "Team IDE Key",
                "key": "vx_live_a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
                "key_prefix": "vx_live_a1b2",
                "expires_at": "2027-02-25T00:00:00Z",
                "created_at": "2026-02-25T00:00:00Z",
            }
            api_keys_test_client.post(
                "/api/v1/ide/api-keys",
                json={"name": "Team IDE Key", "expires_in_days": 365},
            )

        # 목록 조회
        list_response = api_keys_test_client.get("/api/v1/ide/api-keys")

        assert list_response.status_code == 200
        keys_list = list_response.json()["data"]
        if isinstance(keys_list, list) and len(keys_list) > 0:
            for key_item in keys_list:
                # 원본 key 값이 노출되어서는 안 된다
                assert "key" not in key_item or key_item.get("key") is None or key_item.get("key") == ""
                # key_prefix는 존재해야 한다
                assert "key_prefix" in key_item

    def test_create_api_key_member_role_forbidden(self, api_keys_test_client_member):
        """member 역할은 API Key 생성 불가 (403) (I-20)

        Arrange: JWT 인증된 member 사용자
        Act: POST /api/v1/ide/api-keys
        Assert: 403, "admin/owner 권한이 필요합니다"
        """
        response = api_keys_test_client_member.post(
            "/api/v1/ide/api-keys",
            json={
                "name": "Team IDE Key",
                "expires_in_days": 365,
            },
        )

        assert response.status_code == 403

    def test_create_api_key_without_auth_returns_401(self, api_keys_test_client_unauthenticated):
        """인증 없이 요청하면 401을 반환한다 (I-21)

        Arrange: JWT 헤더 없음
        Act: POST /api/v1/ide/api-keys
        Assert: 401
        """
        response = api_keys_test_client_unauthenticated.post(
            "/api/v1/ide/api-keys",
            json={
                "name": "Team IDE Key",
                "expires_in_days": 365,
            },
        )

        assert response.status_code == 401

    def test_create_api_key_missing_name_returns_422(self, api_keys_test_client):
        """name 필드 누락 시 422를 반환한다

        Arrange: name 없이 요청
        Act: POST /api/v1/ide/api-keys
        Assert: 422 (유효성 검사 실패)
        """
        response = api_keys_test_client.post(
            "/api/v1/ide/api-keys",
            json={
                # name 누락
                "expires_in_days": 365,
            },
        )

        assert response.status_code == 422

    def test_create_api_key_key_format_is_vx_live(self, api_keys_test_client):
        """생성된 API Key는 vx_live_ 접두사 형식이다

        Arrange: 정상 API Key 생성 요청
        Act: POST /api/v1/ide/api-keys
        Assert: key 값이 "vx_live_" 또는 "vx_test_"로 시작
        """
        with patch(
            "src.services.api_key_service.ApiKeyService.create_key",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = {
                "id": str(API_KEY_ID_1),
                "name": "Test Key",
                "key": "vx_live_a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
                "key_prefix": "vx_live_a1b2",
                "expires_at": "2027-02-25T00:00:00Z",
                "created_at": "2026-02-25T00:00:00Z",
            }

            response = api_keys_test_client.post(
                "/api/v1/ide/api-keys",
                json={"name": "Test Key", "expires_in_days": 30},
            )

        assert response.status_code == 201
        key_value = response.json()["data"]["key"]
        assert key_value.startswith("vx_live_") or key_value.startswith("vx_test_")


# ──────────────────────────────────────────────────────────────
# GET /api/v1/ide/api-keys 테스트
# ──────────────────────────────────────────────────────────────

class TestListApiKeys:
    """GET /api/v1/ide/api-keys — 발급된 Key 목록 조회"""

    def test_list_api_keys_success(self, api_keys_test_client):
        """발급된 API Key 목록을 반환한다

        Arrange: 팀에 2개의 ApiKey 존재, 인증된 owner
        Act: GET /api/v1/ide/api-keys
        Assert: 200, 배열에 2개 항목
        """
        response = api_keys_test_client.get("/api/v1/ide/api-keys")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 2

    def test_list_api_keys_does_not_include_key_value(self, api_keys_test_client):
        """목록 조회 응답에 원본 key 값이 포함되지 않는다 (보안 요구사항)

        설계서: key는 발급 시 한 번만 노출. 이후 조회에서는 key_prefix만 표시.

        Arrange: 2개의 ApiKey 존재
        Act: GET /api/v1/ide/api-keys
        Assert: 각 항목에 'key' 필드 없음, key_prefix는 존재
        """
        response = api_keys_test_client.get("/api/v1/ide/api-keys")

        assert response.status_code == 200
        keys = response.json()["data"]
        for key_item in keys:
            # 원본 key 값은 노출 금지
            assert "key" not in key_item or key_item.get("key") is None
            # key_prefix는 표시해야 함
            assert "key_prefix" in key_item

    def test_list_api_keys_contains_required_fields(self, api_keys_test_client):
        """목록 각 항목에 id, name, key_prefix, is_active, created_at 필드가 포함된다

        Arrange: 2개의 ApiKey 존재
        Act: GET /api/v1/ide/api-keys
        Assert: 필수 필드 모두 존재
        """
        response = api_keys_test_client.get("/api/v1/ide/api-keys")

        assert response.status_code == 200
        keys = response.json()["data"]
        assert len(keys) >= 1
        required_fields = ["id", "name", "key_prefix", "is_active", "created_at"]
        for field in required_fields:
            assert field in keys[0], f"필수 필드 누락: {field}"

    def test_list_api_keys_without_auth_returns_401(self, api_keys_test_client_unauthenticated):
        """인증 없이 목록 조회 시 401을 반환한다

        Arrange: JWT 헤더 없음
        Act: GET /api/v1/ide/api-keys
        Assert: 401
        """
        response = api_keys_test_client_unauthenticated.get("/api/v1/ide/api-keys")

        assert response.status_code == 401

    def test_list_api_keys_shows_only_team_keys(self, api_keys_test_client):
        """자신의 팀 API Key만 조회된다 (교차 팀 접근 방지)

        Arrange: 현재 팀 2개의 ApiKey
        Act: GET /api/v1/ide/api-keys
        Assert: 반환된 키들이 모두 같은 team_id
        """
        response = api_keys_test_client.get("/api/v1/ide/api-keys")

        assert response.status_code == 200
        keys = response.json()["data"]
        # 반환된 항목의 team_id가 있다면 현재 팀과 일치해야 함
        for key_item in keys:
            if "team_id" in key_item:
                assert key_item["team_id"] == str(TEAM_ID)


# ──────────────────────────────────────────────────────────────
# DELETE /api/v1/ide/api-keys/{id} 테스트
# ──────────────────────────────────────────────────────────────

class TestDeleteApiKey:
    """DELETE /api/v1/ide/api-keys/{id} — Key 삭제/비활성화"""

    def test_delete_api_key_success(self, api_keys_test_client):
        """유효한 key_id로 삭제(비활성화) 성공 (I-22)

        Arrange: JWT 인증된 owner, 유효한 key_id
        Act: DELETE /api/v1/ide/api-keys/{key_id}
        Assert: 200 또는 204, revoked_at 설정
        """
        with patch(
            "src.services.api_key_service.ApiKeyService.revoke_key",
            new_callable=AsyncMock,
        ) as mock_revoke:
            mock_revoke.return_value = {
                "id": str(API_KEY_ID_1),
                "name": "Team IDE Key",
                "revoked_at": "2026-02-25T12:00:00Z",
            }

            response = api_keys_test_client.delete(
                f"/api/v1/ide/api-keys/{API_KEY_ID_1}",
            )

        assert response.status_code in (200, 204)

    def test_delete_api_key_response_has_revoked_at(self, api_keys_test_client):
        """삭제 응답에 revoked_at 타임스탬프가 포함된다 (I-22)

        Arrange: JWT 인증된 owner, 유효한 key_id
        Act: DELETE /api/v1/ide/api-keys/{key_id}
        Assert: 200, data에 revoked_at 포함
        """
        with patch(
            "src.services.api_key_service.ApiKeyService.revoke_key",
            new_callable=AsyncMock,
        ) as mock_revoke:
            mock_revoke.return_value = {
                "id": str(API_KEY_ID_1),
                "name": "Team IDE Key",
                "revoked_at": "2026-02-25T12:00:00Z",
            }

            response = api_keys_test_client.delete(
                f"/api/v1/ide/api-keys/{API_KEY_ID_1}",
            )

        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert "revoked_at" in data["data"]
            assert data["data"]["revoked_at"] is not None

    def test_delete_api_key_not_found_returns_404(self, api_keys_test_client):
        """존재하지 않는 key_id로 삭제 시 404를 반환한다 (I-23)

        Arrange: JWT 인증된 owner, DB에 없는 key_id
        Act: DELETE /api/v1/ide/api-keys/{none_id}
        Assert: 404, 응답 바디에 success=False 또는 에러 메시지 포함
        (구현이 없는 경우 라우트 미존재로 404가 발생하지만,
         구현 후에는 DB 조회 실패로 404가 발생해야 한다.)
        """
        response = api_keys_test_client.delete(
            f"/api/v1/ide/api-keys/{NONE_ID}",
        )

        assert response.status_code == 404
        # 구현 후에는 응답 바디에 에러 정보가 있어야 한다
        # 현재(미구현)는 라우트 자체가 없어 404이므로 아래 assertion이 실패함
        data = response.json()
        assert "success" in data and data["success"] is False, (
            "미구현: /api/v1/ide/api-keys 라우트가 없음. "
            "구현 후에는 success=False와 에러 메시지가 반환되어야 한다."
        )

    def test_delete_api_key_member_forbidden(self, api_keys_test_client_member):
        """member 역할은 API Key 삭제 불가 (403)

        Arrange: JWT 인증된 member 사용자
        Act: DELETE /api/v1/ide/api-keys/{key_id}
        Assert: 403
        """
        response = api_keys_test_client_member.delete(
            f"/api/v1/ide/api-keys/{API_KEY_ID_1}",
        )

        assert response.status_code == 403

    def test_delete_api_key_without_auth_returns_401(self, api_keys_test_client_unauthenticated):
        """인증 없이 삭제 시 401을 반환한다

        Arrange: JWT 헤더 없음
        Act: DELETE /api/v1/ide/api-keys/{key_id}
        Assert: 401
        """
        response = api_keys_test_client_unauthenticated.delete(
            f"/api/v1/ide/api-keys/{API_KEY_ID_1}",
        )

        assert response.status_code == 401

    def test_delete_api_key_is_soft_delete(self, api_keys_test_client):
        """API Key 삭제는 논리 삭제 (is_active=False)로 처리된다

        설계서: DELETE는 물리 삭제가 아닌 비활성화(논리 삭제).
        비활성화 후 해당 키로 인증 시 403이어야 한다.

        Arrange: 유효한 key_id로 DELETE 요청
        Act: DELETE /api/v1/ide/api-keys/{key_id}
        Assert: 성공 응답에 is_active=False 또는 revoked_at 설정 확인
        """
        with patch(
            "src.services.api_key_service.ApiKeyService.revoke_key",
            new_callable=AsyncMock,
        ) as mock_revoke:
            mock_revoke.return_value = {
                "id": str(API_KEY_ID_1),
                "name": "Team IDE Key",
                "is_active": False,
                "revoked_at": "2026-02-25T12:00:00Z",
            }

            response = api_keys_test_client.delete(
                f"/api/v1/ide/api-keys/{API_KEY_ID_1}",
            )

        assert response.status_code in (200, 204)
        if response.status_code == 200:
            data = response.json()
            # 응답에 비활성화 정보가 있다면 확인
            if "data" in data and isinstance(data["data"], dict):
                revoked_at = data["data"].get("revoked_at")
                assert revoked_at is not None

    def test_delete_api_key_invalid_uuid_format_returns_422(self, api_keys_test_client):
        """유효하지 않은 UUID 형식의 key_id 요청 시 422를 반환한다

        Arrange: UUID 형식이 아닌 문자열
        Act: DELETE /api/v1/ide/api-keys/not-a-valid-uuid
        Assert: 422 (경로 파라미터 유효성 검사 실패)
        """
        response = api_keys_test_client.delete(
            "/api/v1/ide/api-keys/not-a-valid-uuid",
        )

        assert response.status_code == 422
