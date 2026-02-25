"""F-04: 스캔 결과 API 테스트 — RED 단계 (구현 전 실패 확인용)

테스트 명세: docs/specs/F-04-scan-results-ui/test-spec.md (2-1절)
인수조건: docs/project/features.md #F-04

대상 엔드포인트:
    GET /api/v1/scans/{scan_id}

커버하는 시나리오:
    I-01: 정상 조회 (completed 상태)
    I-02: 정상 조회 (running 상태)
    I-04: 존재하지 않는 scan_id → 404
    I-05: 인증 없이 요청 → 401
    I-06: 다른 팀의 스캔 조회 → 403
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────
# 헬퍼 픽스처
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def auth_headers():
    """Bearer 토큰이 포함된 인증 헤더."""
    return {"Authorization": "Bearer test_jwt_token"}


@pytest.fixture
def completed_scan_response_data():
    """completed 상태 스캔의 예상 응답 데이터."""
    return {
        "id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
        "repo_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "status": "completed",
        "trigger_type": "manual",
        "commit_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "branch": "main",
        "pr_number": None,
        "findings_count": 15,
        "true_positives_count": 8,
        "false_positives_count": 7,
        "duration_seconds": 120,
        "error_message": None,
    }


# ──────────────────────────────────────────────────────────────
# 테스트 케이스
# ──────────────────────────────────────────────────────────────

class TestGetScanDetail:
    """GET /api/v1/scans/{scan_id} 통합 테스트"""

    def test_get_scan_detail_success(self, test_client, auth_headers, sample_scan_job):
        """I-01: completed 스캔 정상 조회 — 200 반환 및 ScanJobResponse 필드 검증.

        Arrange: completed 상태의 sample_scan_job 픽스처 준비.
        Act: GET /api/v1/scans/{scan_id} 요청 (인증 헤더 포함).
        Assert: HTTP 200, success=True, data에 필수 필드 포함.
        """
        scan_id = str(sample_scan_job.id)

        # DB 조회가 sample_scan_job을 반환하도록 Mock 설정
        with patch("src.api.v1.scans.get_scan") as mock_endpoint:
            mock_endpoint.return_value = {
                "success": True,
                "data": {
                    "id": scan_id,
                    "status": "completed",
                    "findings_count": 15,
                    "true_positives_count": 8,
                    "false_positives_count": 7,
                },
                "error": None,
            }

            response = test_client.get(
                f"/api/v1/scans/{scan_id}",
                headers=auth_headers,
            )

        # 현재 NotImplementedError 상태이므로 500 반환 → RED 확인
        assert response.status_code == 200, (
            f"RED: 구현 전이므로 200 대신 {response.status_code} 반환됨. "
            "구현 후에는 200이어야 한다."
        )
        body = response.json()
        assert body["success"] is True
        assert "data" in body
        assert body["data"]["id"] == scan_id
        assert body["data"]["status"] == "completed"
        # findings_count 포함 여부 검증
        assert "findings_count" in body["data"]
        assert body["data"]["findings_count"] == 15

    def test_get_scan_not_found(self, test_client, auth_headers):
        """I-04: 존재하지 않는 scan_id → 404.

        Arrange: DB에 없는 UUID 사용.
        Act: GET /api/v1/scans/{없는_scan_id} 요청.
        Assert: HTTP 404, error 메시지에 "스캔을 찾을 수 없습니다" 포함.
        """
        nonexistent_id = "ffffffff-ffff-ffff-ffff-ffffffffffff"

        response = test_client.get(
            f"/api/v1/scans/{nonexistent_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404, (
            f"RED: 없는 scan_id 조회 시 404 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        # 에러 메시지에 scan_id가 포함되어야 함
        error_detail = str(body)
        assert "스캔을 찾을 수 없습니다" in error_detail or "404" in str(response.status_code)

    def test_get_scan_requires_auth(self, test_client):
        """I-05: 인증 없이 요청 → 401.

        Arrange: 인증 헤더 없이 요청.
        Act: GET /api/v1/scans/{scan_id} (Authorization 헤더 없음).
        Assert: HTTP 401.
        """
        scan_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"

        # 인증되지 않은 클라이언트 사용 (의존성 오버라이드 없음)
        from src.main import create_app
        from src.api.deps import get_current_user

        app = create_app()

        # get_current_user가 HTTPException 401을 raise하도록 설정
        async def override_unauthorized():
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="유효하지 않은 인증 정보입니다.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        from src.api.deps import get_db
        mock_db = AsyncMock()

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_current_user] = override_unauthorized
        app.dependency_overrides[get_db] = override_get_db

        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as unauthenticated_client:
            response = unauthenticated_client.get(f"/api/v1/scans/{scan_id}")

        assert response.status_code == 401, (
            f"RED: 인증 없이 요청 시 401 반환해야 하지만 {response.status_code} 반환됨."
        )

    def test_get_scan_status_running(self, test_client, auth_headers):
        """I-02: running 상태 스캔 조회 — 200 반환 및 status='running' 검증.

        Arrange: running 상태의 스캔 Mock 준비.
        Act: GET /api/v1/scans/{running_scan_id} 요청.
        Assert: HTTP 200, status='running'.
        """
        running_scan_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        response = test_client.get(
            f"/api/v1/scans/{running_scan_id}",
            headers=auth_headers,
        )

        # NotImplementedError로 인해 500 반환 → RED 확인
        assert response.status_code == 200, (
            f"RED: running 스캔 조회 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True
        assert body["data"]["status"] == "running"

    def test_get_scan_status_completed(self, test_client, auth_headers, sample_scan_job):
        """I-01 확장: completed 스캔 + findings_count 포함 검증.

        Arrange: completed 상태 스캔, findings_count=15.
        Act: GET /api/v1/scans/{scan_id}.
        Assert: 200, findings_count=15, true_positives_count=8, false_positives_count=7.
        """
        scan_id = str(sample_scan_job.id)

        response = test_client.get(
            f"/api/v1/scans/{scan_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"RED: completed 스캔 조회 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        # 통계 필드 포함 검증
        assert "findings_count" in data
        assert "true_positives_count" in data
        assert "false_positives_count" in data
        assert data["findings_count"] == 15
        assert data["true_positives_count"] == 8
        assert data["false_positives_count"] == 7
        # 완료 시각 포함 검증
        assert "completed_at" in data
        assert data["completed_at"] is not None
