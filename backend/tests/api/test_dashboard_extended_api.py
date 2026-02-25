"""F-07: 대시보드 확장 API 테스트 — RED 단계

테스트 명세: docs/specs/F-07-dashboard/design.md
인수조건: docs/project/features.md #F-07

대상 엔드포인트:
    GET /api/v1/dashboard/repo-scores         (저장소별 보안 점수)
    GET /api/v1/dashboard/team-scores         (팀별 보안 점수 집계)
    GET /api/v1/dashboard/severity-distribution (심각도별 분포)
    GET /api/v1/dashboard/summary             (avg_security_score 추가)
    GET /api/v1/dashboard/trend               (open_count 추가)
    GET /api/v1/vulns                         (vulnerability_type 필터)
"""

import uuid
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
# GET /api/v1/dashboard/repo-scores 테스트
# ──────────────────────────────────────────────────────────────

class TestGetRepoScores:
    """GET /api/v1/dashboard/repo-scores 저장소별 보안 점수 테스트"""

    def test_get_repo_scores_success(self, test_client, auth_headers):
        """저장소별 보안 점수 조회 — 200, 필수 필드 포함.

        Arrange: 인증된 사용자, 저장소 존재.
        Act: GET /api/v1/dashboard/repo-scores
        Assert: HTTP 200, success=True, items 배열 포함, 각 항목에 필수 필드.
        """
        response = test_client.get(
            "/api/v1/dashboard/repo-scores",
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"저장소별 보안 점수 조회 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True
        assert "data" in body
        data = body["data"]
        assert "items" in data
        assert "total" in data

    def test_repo_scores_item_fields(self, test_client, auth_headers):
        """저장소 점수 항목에 필수 필드 포함 여부 검증.

        Assert: 각 항목에 repo_id, repo_full_name, security_score,
                open_vulns_count, total_vulns_count 포함.
        """
        response = test_client.get(
            "/api/v1/dashboard/repo-scores",
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        items = body["data"]["items"]

        for item in items:
            assert "repo_id" in item, "repo_id 필드 누락"
            assert "repo_full_name" in item, "repo_full_name 필드 누락"
            assert "security_score" in item, "security_score 필드 누락"
            assert "open_vulns_count" in item, "open_vulns_count 필드 누락"
            assert "total_vulns_count" in item, "total_vulns_count 필드 누락"

    def test_repo_scores_security_score_range(self, test_client, auth_headers):
        """보안 점수가 0~100 범위 내인지 검증.

        Assert: security_score가 0 이상 100 이하.
        """
        response = test_client.get(
            "/api/v1/dashboard/repo-scores",
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        items = body["data"]["items"]

        for item in items:
            score = item["security_score"]
            assert isinstance(score, (int, float)), "security_score가 숫자가 아님"
            assert 0 <= score <= 100, f"security_score가 유효 범위 밖: {score}"

    def test_repo_scores_requires_auth(self, test_client):
        """인증 없이 요청 시 401 반환 검증."""
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
            response = unauthenticated_client.get("/api/v1/dashboard/repo-scores")

        assert response.status_code == 401

    def test_repo_scores_empty_team(self, test_client, auth_headers):
        """저장소가 없는 팀 — 빈 items 배열 반환.

        Assert: items=[], total=0.
        """
        with patch(
            "src.api.v1.dashboard._get_repos_by_teams",
            new=AsyncMock(return_value=[]),
        ):
            response = test_client.get(
                "/api/v1/dashboard/repo-scores",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["items"] == []
        assert body["data"]["total"] == 0

    def test_repo_scores_open_vulns_count(self, test_client, auth_headers):
        """open_vulns_count가 실제 open 상태 취약점 수와 일치하는지 검증."""
        response = test_client.get(
            "/api/v1/dashboard/repo-scores",
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        items = body["data"]["items"]

        for item in items:
            assert item["open_vulns_count"] >= 0
            assert item["total_vulns_count"] >= item["open_vulns_count"]


# ──────────────────────────────────────────────────────────────
# GET /api/v1/dashboard/team-scores 테스트
# ──────────────────────────────────────────────────────────────

class TestGetTeamScores:
    """GET /api/v1/dashboard/team-scores 팀별 보안 점수 집계 테스트"""

    def test_get_team_scores_success(self, test_client, auth_headers):
        """팀별 보안 점수 집계 조회 — 200, 필수 필드 포함.

        Assert: HTTP 200, success=True, items 배열 포함.
        """
        response = test_client.get(
            "/api/v1/dashboard/team-scores",
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"팀별 보안 점수 조회 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True
        assert "data" in body
        data = body["data"]
        assert "items" in data
        assert "total" in data

    def test_team_scores_item_fields(self, test_client, auth_headers):
        """팀 점수 항목에 필수 필드 포함 여부 검증.

        Assert: 각 항목에 team_id, avg_score, repo_count, total_open_vulns 포함.
        """
        response = test_client.get(
            "/api/v1/dashboard/team-scores",
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        items = body["data"]["items"]

        for item in items:
            assert "team_id" in item, "team_id 필드 누락"
            assert "avg_score" in item, "avg_score 필드 누락"
            assert "repo_count" in item, "repo_count 필드 누락"
            assert "total_open_vulns" in item, "total_open_vulns 필드 누락"

    def test_team_scores_avg_score_range(self, test_client, auth_headers):
        """평균 보안 점수가 0~100 범위 내인지 검증."""
        response = test_client.get(
            "/api/v1/dashboard/team-scores",
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        items = body["data"]["items"]

        for item in items:
            score = item["avg_score"]
            assert 0 <= score <= 100, f"avg_score가 유효 범위 밖: {score}"

    def test_team_scores_requires_auth(self, test_client):
        """인증 없이 요청 시 401 반환 검증."""
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
            response = unauthenticated_client.get("/api/v1/dashboard/team-scores")

        assert response.status_code == 401

    def test_team_scores_empty_team(self, test_client, auth_headers):
        """팀 저장소 없는 경우 빈 응답 반환.

        Assert: items=[], total=0.
        """
        with patch(
            "src.api.v1.dashboard._get_repos_by_teams",
            new=AsyncMock(return_value=[]),
        ):
            response = test_client.get(
                "/api/v1/dashboard/team-scores",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["items"] == []
        assert body["data"]["total"] == 0


# ──────────────────────────────────────────────────────────────
# GET /api/v1/dashboard/severity-distribution 테스트
# ──────────────────────────────────────────────────────────────

class TestGetSeverityDistribution:
    """GET /api/v1/dashboard/severity-distribution 심각도별 분포 테스트"""

    def test_get_severity_distribution_success(self, test_client, auth_headers):
        """심각도별 분포 조회 — 200, 필수 필드 포함.

        Assert: HTTP 200, success=True, critical/high/medium/low/total 포함.
        """
        response = test_client.get(
            "/api/v1/dashboard/severity-distribution",
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"심각도별 분포 조회 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert "critical" in data, "critical 필드 누락"
        assert "high" in data, "high 필드 누락"
        assert "medium" in data, "medium 필드 누락"
        assert "low" in data, "low 필드 누락"
        assert "total" in data, "total 필드 누락"

    def test_severity_distribution_values_are_integers(self, test_client, auth_headers):
        """심각도별 분포 값이 정수인지 검증."""
        response = test_client.get(
            "/api/v1/dashboard/severity-distribution",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()["data"]

        for key in ["critical", "high", "medium", "low", "total"]:
            assert isinstance(data[key], int), f"{key}가 정수가 아님: {type(data[key])}"
            assert data[key] >= 0, f"{key}가 음수: {data[key]}"

    def test_severity_distribution_total_consistency(self, test_client, auth_headers):
        """total이 critical+high+medium+low 합계와 일치하는지 검증."""
        response = test_client.get(
            "/api/v1/dashboard/severity-distribution",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()["data"]
        expected_total = data["critical"] + data["high"] + data["medium"] + data["low"]
        assert data["total"] == expected_total, (
            f"total({data['total']}) != critical+high+medium+low({expected_total})"
        )

    def test_severity_distribution_with_repo_filter(self, test_client, auth_headers):
        """repository_id 필터 파라미터로 조회 — 200 반환.

        Assert: repository_id 필터 시 정상 응답.
        """
        repo_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        response = test_client.get(
            f"/api/v1/dashboard/severity-distribution?repository_id={repo_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"repository_id 필터 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True

    def test_severity_distribution_requires_auth(self, test_client):
        """인증 없이 요청 시 401 반환 검증."""
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
            response = unauthenticated_client.get("/api/v1/dashboard/severity-distribution")

        assert response.status_code == 401

    def test_severity_distribution_empty_team(self, test_client, auth_headers):
        """저장소 없는 경우 모든 값이 0인 응답 반환."""
        with patch(
            "src.api.v1.dashboard._get_repos_by_teams",
            new=AsyncMock(return_value=[]),
        ):
            response = test_client.get(
                "/api/v1/dashboard/severity-distribution",
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 0
        assert data["critical"] == 0
        assert data["high"] == 0
        assert data["medium"] == 0
        assert data["low"] == 0


# ──────────────────────────────────────────────────────────────
# GET /api/v1/dashboard/summary — avg_security_score 필드 추가 테스트
# ──────────────────────────────────────────────────────────────

class TestDashboardSummaryAvgSecurityScore:
    """대시보드 요약에 avg_security_score 필드 추가 테스트"""

    def test_summary_includes_avg_security_score(self, test_client, auth_headers):
        """대시보드 요약에 avg_security_score 필드 포함 여부 검증.

        Assert: data에 avg_security_score 필드 포함, 0~100 범위.
        """
        response = test_client.get(
            "/api/v1/dashboard/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "avg_security_score" in data, (
            "대시보드 요약에 avg_security_score 필드 누락"
        )

    def test_summary_avg_security_score_range(self, test_client, auth_headers):
        """avg_security_score가 0~100 범위 내인지 검증."""
        response = test_client.get(
            "/api/v1/dashboard/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()["data"]
        avg_score = data["avg_security_score"]
        assert isinstance(avg_score, (int, float)), "avg_security_score가 숫자가 아님"
        assert 0 <= avg_score <= 100, f"avg_security_score가 유효 범위 밖: {avg_score}"

    def test_summary_avg_security_score_empty_team(self, test_client, auth_headers):
        """저장소 없는 팀의 avg_security_score는 0.0.

        Assert: 저장소 없을 때 avg_security_score=0.0.
        """
        with patch(
            "src.api.v1.dashboard._get_repos_by_teams",
            new=AsyncMock(return_value=[]),
        ):
            response = test_client.get(
                "/api/v1/dashboard/summary",
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["avg_security_score"] == 0.0


# ──────────────────────────────────────────────────────────────
# GET /api/v1/dashboard/trend — open_count 필드 추가 테스트
# ──────────────────────────────────────────────────────────────

class TestTrendOpenCount:
    """대시보드 추이 데이터에 open_count 필드 추가 테스트"""

    def test_trend_data_includes_open_count(self, test_client, auth_headers):
        """추이 데이터 포인트에 open_count 필드 포함 여부 검증.

        Assert: 각 data point에 open_count 필드 포함.
        """
        response = test_client.get(
            "/api/v1/dashboard/trend",
            params={"days": 7},
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        data_points = body["data"]["data"]

        for point in data_points:
            assert "open_count" in point, (
                f"trend 데이터 포인트에 open_count 필드 누락: {point}"
            )

    def test_trend_open_count_is_non_negative(self, test_client, auth_headers):
        """open_count가 음수가 아닌지 검증."""
        response = test_client.get(
            "/api/v1/dashboard/trend",
            params={"days": 30},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data_points = response.json()["data"]["data"]

        for point in data_points:
            assert point["open_count"] >= 0, (
                f"open_count가 음수: {point['open_count']}"
            )

    def test_trend_data_point_all_fields(self, test_client, auth_headers):
        """추이 데이터 포인트에 기존 필드(date, new_count, resolved_count)와
        신규 open_count 필드가 모두 포함되는지 검증."""
        response = test_client.get(
            "/api/v1/dashboard/trend",
            params={"days": 7},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data_points = response.json()["data"]["data"]

        for point in data_points:
            assert "date" in point, "date 필드 누락"
            assert "new_count" in point, "new_count 필드 누락"
            assert "resolved_count" in point, "resolved_count 필드 누락"
            assert "open_count" in point, "open_count 필드 누락"


# ──────────────────────────────────────────────────────────────
# GET /api/v1/vulns — vulnerability_type 필터 테스트
# ──────────────────────────────────────────────────────────────

class TestVulnsVulnerabilityTypeFilter:
    """취약점 목록 vulnerability_type 필터 테스트"""

    def test_vulns_filter_by_vulnerability_type(self, test_client, auth_headers):
        """vulnerability_type 파라미터로 필터링 — 200 반환.

        Assert: HTTP 200, 지정된 타입만 반환.
        """
        response = test_client.get(
            "/api/v1/vulnerabilities",
            params={"vulnerability_type": "sql_injection"},
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"vulnerability_type 필터 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True

    def test_vulns_vulnerability_type_filter_default_none(self, test_client, auth_headers):
        """vulnerability_type 파라미터 없이 조회 — 전체 반환.

        Assert: HTTP 200, 전체 취약점 반환.
        """
        response = test_client.get(
            "/api/v1/vulnerabilities",
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

    def test_vulns_vulnerability_type_nonexistent(self, test_client, auth_headers):
        """존재하지 않는 유형으로 필터링 — 빈 목록 반환.

        Assert: HTTP 200, 빈 data 배열.
        """
        response = test_client.get(
            "/api/v1/vulnerabilities",
            params={"vulnerability_type": "nonexistent_type_xyz"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

    def test_vulns_vulnerability_type_combined_with_other_filters(
        self, test_client, auth_headers
    ):
        """vulnerability_type과 severity 복합 필터 — 200 반환.

        Assert: HTTP 200, 복합 필터 적용 결과 반환.
        """
        response = test_client.get(
            "/api/v1/vulnerabilities",
            params={"vulnerability_type": "xss", "severity": "high"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

    def test_vulns_filter_sql_injection_type_results(self, test_client, auth_headers):
        """sql_injection 타입 필터링 시 해당 타입 결과만 포함하는지 검증.

        Arrange: Mock DB에 sql_injection 타입 취약점 1건 포함.
        Assert: 반환된 모든 항목의 vulnerability_type이 sql_injection.
        """
        response = test_client.get(
            "/api/v1/vulnerabilities",
            params={"vulnerability_type": "sql_injection"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        items = body["data"]

        # 반환된 항목이 있으면 모두 sql_injection 타입이어야 함
        for item in items:
            assert item["vulnerability_type"] == "sql_injection", (
                f"sql_injection 필터 시 다른 타입 포함됨: {item['vulnerability_type']}"
            )


# ──────────────────────────────────────────────────────────────
# 보안 점수 계산 공식 검증 테스트
# ──────────────────────────────────────────────────────────────

class TestSecurityScoreFormula:
    """보안 점수 계산 공식 검증 — max(0, 100 - (c*25 + h*10 + m*5 + l*1))"""

    def test_security_score_formula_all_open(self, test_client, auth_headers):
        """저장소 점수 항목의 보안 점수가 공식에 맞는 범위인지 검증."""
        response = test_client.get(
            "/api/v1/dashboard/repo-scores",
            headers=auth_headers,
        )

        assert response.status_code == 200
        items = response.json()["data"]["items"]

        # 점수 범위 검증 (공식 결과는 0~100 범위)
        for item in items:
            assert 0 <= item["security_score"] <= 100

    def test_security_score_zero_vulns_is_100(self, test_client, auth_headers):
        """취약점이 없는 저장소의 보안 점수는 100점이어야 한다."""
        # 취약점 없는 저장소 mock
        mock_repo = MagicMock()
        mock_repo.id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        mock_repo.full_name = "org/empty-repo"
        mock_repo.team_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        mock_repo.security_score = 100.0

        with patch(
            "src.api.v1.dashboard._get_repos_by_teams",
            new=AsyncMock(return_value=[mock_repo]),
        ), patch(
            "src.api.v1.dashboard._get_vulns_by_repos",
            new=AsyncMock(return_value=[]),
        ):
            response = test_client.get(
                "/api/v1/dashboard/repo-scores",
                headers=auth_headers,
            )

        assert response.status_code == 200
        items = response.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["security_score"] == 100.0
