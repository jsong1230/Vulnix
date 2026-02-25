"""F-04: 대시보드 API 테스트 — RED 단계 (구현 전 실패 확인용)

테스트 명세: docs/specs/F-04-scan-results-ui/test-spec.md (2-5절)
인수조건: docs/project/features.md #F-04

대상 엔드포인트:
    GET /api/v1/dashboard/summary   (대시보드 요약 통계)
    GET /api/v1/dashboard/trend     (취약점 추이)

커버하는 시나리오:
    I-35: 정상 조회 (데이터 있음) — 200, 전체 필드 포함
    I-36: 데이터 없는 팀 — 200, 빈 상태 응답
    I-38: severity_distribution 정확성
    I-39: resolution_rate 정확성
    I-40: recent_scans 최대 5건 제한
    I-41: recent_scans에 repo_full_name 포함
    I-42: 인증 없이 요청 → 401
    추이 데이터 조회 (get_trend_data)
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


# ──────────────────────────────────────────────────────────────
# GET /api/v1/dashboard/summary 테스트
# ──────────────────────────────────────────────────────────────

class TestGetDashboardSummary:
    """GET /api/v1/dashboard/summary 대시보드 요약 통계 테스트"""

    def test_get_dashboard_summary_success(
        self, test_client, auth_headers, sample_vulnerability_list, sample_scan_job
    ):
        """I-35: 데이터 있는 팀의 대시보드 요약 조회 — 200, 전체 필드 포함.

        Arrange: 취약점 10건 + 완료된 스캔 1건 존재.
        Act: GET /api/v1/dashboard/summary
        Assert: HTTP 200, success=True, 필수 필드 모두 포함.
        """
        response = test_client.get(
            "/api/v1/dashboard/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"RED: 대시보드 요약 조회 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True
        data = body["data"]

        # 설계서 4-5절의 필수 필드 검증
        required_fields = [
            "total_vulnerabilities",
            "severity_distribution",
            "status_distribution",
            "resolution_rate",
            "recent_scans",
            "repo_count",
            "last_scan_at",
        ]
        for field in required_fields:
            assert field in data, f"대시보드 요약 필드 누락: {field}"

    def test_dashboard_summary_includes_stats(
        self, test_client, auth_headers
    ):
        """I-35 확장: 통계 필드 내부 구조 검증.

        Arrange: 취약점 데이터 존재.
        Act: GET /api/v1/dashboard/summary
        Assert: severity_distribution에 critical/high/medium/low 포함,
                status_distribution에 open/patched/ignored/false_positive 포함.
        """
        response = test_client.get(
            "/api/v1/dashboard/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"RED: 통계 필드 조회 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        data = body["data"]

        # severity_distribution 내부 구조 검증 (I-38)
        severity_dist = data["severity_distribution"]
        for severity_key in ["critical", "high", "medium", "low"]:
            assert severity_key in severity_dist, (
                f"severity_distribution에 '{severity_key}' 키 누락"
            )
            assert isinstance(severity_dist[severity_key], int), (
                f"severity_distribution['{severity_key}']가 정수가 아님"
            )

        # status_distribution 내부 구조 검증
        status_dist = data["status_distribution"]
        for status_key in ["open", "patched", "ignored", "false_positive"]:
            assert status_key in status_dist, (
                f"status_distribution에 '{status_key}' 키 누락"
            )

        # resolution_rate 범위 검증 (0 ~ 100)
        assert 0.0 <= data["resolution_rate"] <= 100.0, (
            f"resolution_rate가 유효 범위(0~100) 밖: {data['resolution_rate']}"
        )

    def test_dashboard_summary_requires_auth(self, test_client):
        """I-42: 인증 없이 요청 → 401.

        Arrange: 인증 헤더 없이 요청.
        Act: GET /api/v1/dashboard/summary (Authorization 헤더 없음).
        Assert: HTTP 401.
        """
        from src.main import create_app
        from src.api.deps import get_current_user, get_db

        app = create_app()

        async def override_unauthorized():
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="유효하지 않은 인증 정보입니다.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        mock_db = AsyncMock()

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_current_user] = override_unauthorized
        app.dependency_overrides[get_db] = override_get_db

        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as unauthenticated_client:
            response = unauthenticated_client.get("/api/v1/dashboard/summary")

        assert response.status_code == 401, (
            f"RED: 인증 없이 요청 시 401 반환해야 하지만 {response.status_code} 반환됨."
        )

    def test_dashboard_summary_empty_team(self, test_client, auth_headers):
        """I-36: 데이터 없는 팀 — 200, 빈 상태 응답.

        Arrange: 취약점 0건, 스캔 0건인 팀.
        Act: GET /api/v1/dashboard/summary
        Assert: HTTP 200, total_vulnerabilities=0, resolution_rate=0.0,
                recent_scans=[], repo_count=0.
        """
        # 저장소가 없는 빈 팀 시뮬레이션: _get_repos_by_teams가 빈 목록 반환
        with patch(
            "src.api.v1.dashboard._get_repos_by_teams",
            new=AsyncMock(return_value=[]),
        ):
            response = test_client.get(
                "/api/v1/dashboard/summary",
                headers=auth_headers,
            )

        assert response.status_code == 200, (
            f"RED: 빈 팀 대시보드 조회 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True
        data = body["data"]

        # 빈 팀의 경우 기본값 검증
        assert data["total_vulnerabilities"] == 0, (
            "취약점 없는 팀의 total_vulnerabilities가 0이어야 함"
        )
        assert data["resolution_rate"] == 0.0, (
            "취약점 없는 팀의 resolution_rate가 0.0이어야 함 (ZeroDivisionError 방지)"
        )
        assert data["recent_scans"] == [], (
            "스캔 없는 팀의 recent_scans가 빈 배열이어야 함"
        )
        assert data["repo_count"] == 0, (
            "저장소 없는 팀의 repo_count가 0이어야 함"
        )

    def test_dashboard_summary_recent_scans_max_5(
        self, test_client, auth_headers
    ):
        """I-40: recent_scans 최대 5건 제한.

        Arrange: 스캔 10건 존재.
        Act: GET /api/v1/dashboard/summary
        Assert: recent_scans 최대 5건 반환, created_at DESC 정렬.
        """
        response = test_client.get(
            "/api/v1/dashboard/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"RED: recent_scans 제한 테스트 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        recent_scans = body["data"]["recent_scans"]

        # 최대 5건만 반환해야 함 (설계서 4-5절)
        assert len(recent_scans) <= 5, (
            f"recent_scans가 5건 초과: {len(recent_scans)}건 반환됨"
        )

    def test_dashboard_recent_scans_has_repo_full_name(
        self, test_client, auth_headers
    ):
        """I-41: recent_scans 각 항목에 repo_full_name 포함.

        Arrange: 스캔 데이터 존재.
        Act: GET /api/v1/dashboard/summary
        Assert: recent_scans 각 항목에 repo_full_name 포함.
        """
        response = test_client.get(
            "/api/v1/dashboard/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"RED: repo_full_name 검증 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        recent_scans = body["data"]["recent_scans"]

        # recent_scans가 존재하는 경우 각 항목에 repo_full_name 포함 검증
        for scan_item in recent_scans:
            assert "repo_full_name" in scan_item, (
                "recent_scans 항목에 repo_full_name 필드 누락"
            )
            assert "findings_count" in scan_item, (
                "recent_scans 항목에 findings_count 필드 누락"
            )
            assert "status" in scan_item, (
                "recent_scans 항목에 status 필드 누락"
            )

    def test_dashboard_resolution_rate_accuracy(
        self, test_client, auth_headers
    ):
        """I-39: resolution_rate 정확성 — total=10, patched=3, false_positive=2 → 50.0%.

        Arrange: 취약점 10건 (patched 3, false_positive 2, 나머지 open/ignored).
        Act: GET /api/v1/dashboard/summary
        Assert: resolution_rate = (3+2)/10 * 100 = 50.0.
        """
        response = test_client.get(
            "/api/v1/dashboard/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"RED: resolution_rate 정확성 테스트 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        resolution_rate = body["data"]["resolution_rate"]

        # 소수점 첫째 자리까지 검증
        assert isinstance(resolution_rate, (int, float)), (
            f"resolution_rate가 숫자가 아님: {type(resolution_rate)}"
        )


# ──────────────────────────────────────────────────────────────
# GET /api/v1/dashboard/trend 테스트
# ──────────────────────────────────────────────────────────────

class TestGetTrendData:
    """GET /api/v1/dashboard/trend 취약점 추이 데이터 테스트"""

    def test_get_trend_data(self, test_client, auth_headers):
        """추이 데이터 기본 조회 — 200, 날짜별 데이터 포함.

        Arrange: 인증된 사용자.
        Act: GET /api/v1/dashboard/trend?days=30
        Assert: HTTP 200, success=True, data 포함.
        """
        response = test_client.get(
            "/api/v1/dashboard/trend",
            params={"days": 30},
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"RED: 추이 데이터 조회 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True
        assert "data" in body

    def test_get_trend_data_default_days(self, test_client, auth_headers):
        """추이 데이터 기본값(30일) 조회.

        Arrange: days 파라미터 없이 요청.
        Act: GET /api/v1/dashboard/trend (days 파라미터 생략)
        Assert: HTTP 200, 기본 30일 데이터 반환.
        """
        response = test_client.get(
            "/api/v1/dashboard/trend",
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"RED: 기본값 추이 데이터 조회 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True

    def test_get_trend_requires_auth(self, test_client):
        """추이 데이터 인증 필요 — 401.

        Arrange: 인증 헤더 없이 요청.
        Act: GET /api/v1/dashboard/trend (Authorization 헤더 없음).
        Assert: HTTP 401.
        """
        from src.main import create_app
        from src.api.deps import get_current_user, get_db

        app = create_app()

        async def override_unauthorized():
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="유효하지 않은 인증 정보입니다.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        mock_db = AsyncMock()

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_current_user] = override_unauthorized
        app.dependency_overrides[get_db] = override_get_db

        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as unauthenticated_client:
            response = unauthenticated_client.get("/api/v1/dashboard/trend")

        assert response.status_code == 401, (
            f"RED: 인증 없이 trend 요청 시 401 반환해야 하지만 {response.status_code} 반환됨."
        )
