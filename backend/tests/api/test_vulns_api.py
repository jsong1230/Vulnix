"""F-04: 취약점 API 테스트 — RED 단계 (구현 전 실패 확인용)

테스트 명세: docs/specs/F-04-scan-results-ui/test-spec.md (2-2절, 2-3절, 2-4절)
인수조건: docs/project/features.md #F-04

대상 엔드포인트:
    GET  /api/v1/vulnerabilities           (목록 조회)
    GET  /api/v1/vulnerabilities/{vuln_id} (상세 조회)
    PATCH /api/v1/vulnerabilities/{vuln_id} (상태 변경)

커버하는 시나리오:
    I-07: 전체 취약점 목록 조회
    I-08: status 필터 (open)
    I-09: severity 필터 (critical)
    I-15: 잘못된 status 값 → 422
    I-17: 인증 없이 목록 요청 → 401
    I-18: 상세 조회 (patch_pr 포함)
    I-19: 상세 조회 (patch_pr 없음 → null)
    I-22: 존재하지 않는 vuln_id → 404
    I-25: open → false_positive (오탐 마킹, resolved_at 설정)
    I-27: open → patched (패치 완료, resolved_at 설정)
    I-28: false_positive → open (복원, resolved_at=null)
    I-33: 잘못된 status 값 → 422
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
def sample_vuln_id():
    """테스트용 취약점 ID."""
    return uuid.UUID("eeeeeeee-eeee-eeee-eeee-000000000000")


@pytest.fixture
def sample_patch_pr():
    """패치 PR Mock 픽스처."""
    pr = MagicMock()
    pr.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    pr.github_pr_number = 42
    pr.github_pr_url = "https://github.com/test-org/test-repo/pull/42"
    pr.status = "created"
    pr.patch_diff = "--- a/src/db.py\n+++ b/src/db.py\n@@ -1,2 +1,2 @@\n-f_string\n+param_binding"
    pr.patch_description = "파라미터 바인딩을 사용하도록 수정"
    return pr


# ──────────────────────────────────────────────────────────────
# GET /api/v1/vulnerabilities 테스트
# ──────────────────────────────────────────────────────────────

class TestListVulnerabilities:
    """GET /api/v1/vulnerabilities 목록 조회 테스트"""

    def test_list_vulnerabilities_success(
        self, test_client, auth_headers, sample_vulnerability_list
    ):
        """I-07: 필터 없이 전체 취약점 목록 조회 — 200, meta.total 정확.

        Arrange: 팀 소속 저장소에 10건의 취약점 존재.
        Act: GET /api/v1/vulnerabilities?page=1&per_page=20
        Assert: HTTP 200, success=True, data 배열, meta.total 포함.
        """
        response = test_client.get(
            "/api/v1/vulnerabilities",
            params={"page": 1, "per_page": 20},
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"RED: 취약점 목록 조회 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)
        # 페이지네이션 메타 검증
        assert "meta" in body
        meta = body["meta"]
        assert "page" in meta
        assert "per_page" in meta
        assert "total" in meta
        assert "total_pages" in meta
        assert meta["page"] == 1

    def test_list_vulnerabilities_filter_severity(
        self, test_client, auth_headers, sample_vulnerability_list
    ):
        """I-09: severity=critical 필터 — critical 취약점만 반환.

        Arrange: 다양한 심각도 취약점 목록.
        Act: GET /api/v1/vulnerabilities?severity=critical
        Assert: HTTP 200, data의 모든 항목 severity='critical'.
        """
        response = test_client.get(
            "/api/v1/vulnerabilities",
            params={"severity": "critical"},
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"RED: severity 필터 조회 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True
        # 반환된 취약점은 모두 critical이어야 함
        for vuln in body["data"]:
            assert vuln["severity"] == "critical", (
                f"severity 필터 적용 실패: {vuln['severity']} != 'critical'"
            )

    def test_list_vulnerabilities_filter_status(
        self, test_client, auth_headers, sample_vulnerability_list
    ):
        """I-08: status=open 필터 — open 취약점만 반환.

        Arrange: open/patched/ignored/false_positive 혼합 취약점 목록.
        Act: GET /api/v1/vulnerabilities?status=open
        Assert: HTTP 200, data의 모든 항목 status='open'.
        """
        response = test_client.get(
            "/api/v1/vulnerabilities",
            params={"status": "open"},
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"RED: status 필터 조회 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True
        # 반환된 취약점은 모두 open이어야 함
        for vuln in body["data"]:
            assert vuln["status"] == "open", (
                f"status 필터 적용 실패: {vuln['status']} != 'open'"
            )

    def test_list_vulns_requires_auth(self, test_client):
        """I-17: 인증 없이 목록 요청 → 401.

        Arrange: 인증 헤더 없이 요청.
        Act: GET /api/v1/vulnerabilities (Authorization 헤더 없음).
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
            response = unauthenticated_client.get("/api/v1/vulnerabilities")

        assert response.status_code == 401, (
            f"RED: 인증 없이 요청 시 401 반환해야 하지만 {response.status_code} 반환됨."
        )


# ──────────────────────────────────────────────────────────────
# GET /api/v1/vulnerabilities/{vuln_id} 테스트
# ──────────────────────────────────────────────────────────────

class TestGetVulnerabilityDetail:
    """GET /api/v1/vulnerabilities/{vuln_id} 상세 조회 테스트"""

    def test_get_vulnerability_detail(
        self, test_client, auth_headers, sample_vulnerability_list, sample_patch_pr
    ):
        """I-18, I-20, I-21: 취약점 상세 조회 — patch_pr 포함, repo_full_name 포함, 전체 필드 검증.

        Arrange: patch_pr이 연결된 취약점.
        Act: GET /api/v1/vulnerabilities/{vuln_id}
        Assert: HTTP 200, patch_pr 필드 포함, repo_full_name 포함, 전체 필드 검증.
        """
        vuln = sample_vulnerability_list[0]
        vuln.patch_pr = sample_patch_pr
        vuln_id = str(vuln.id)

        response = test_client.get(
            f"/api/v1/vulnerabilities/{vuln_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"RED: 취약점 상세 조회 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True
        data = body["data"]

        # 필수 필드 포함 검증
        required_fields = [
            "id", "scan_job_id", "repo_id", "status", "severity",
            "vulnerability_type", "file_path", "start_line", "end_line",
            "code_snippet", "description", "llm_reasoning", "llm_confidence",
            "references", "detected_at", "resolved_at", "created_at",
        ]
        for field in required_fields:
            assert field in data, f"필드 누락: {field}"

        # patch_pr 필드 포함 검증 (설계서 4-3절)
        assert "patch_pr" in data, "patch_pr 필드가 응답에 없음"
        if data["patch_pr"] is not None:
            patch_pr_fields = ["id", "github_pr_number", "github_pr_url", "status", "patch_diff"]
            for field in patch_pr_fields:
                assert field in data["patch_pr"], f"patch_pr.{field} 필드 누락"

        # repo_full_name 필드 포함 검증 (설계서 4-3절)
        assert "repo_full_name" in data, "repo_full_name 필드가 응답에 없음"

    def test_get_vulnerability_detail_no_patch_pr(
        self, test_client, auth_headers, sample_vulnerability_list
    ):
        """I-19: 패치 PR 없는 취약점 상세 조회 — patch_pr = null.

        Arrange: patch_pr이 없는 취약점.
        Act: GET /api/v1/vulnerabilities/{vuln_id}
        Assert: HTTP 200, patch_pr=null.
        """
        vuln = sample_vulnerability_list[1]
        vuln.patch_pr = None
        vuln_id = str(vuln.id)

        response = test_client.get(
            f"/api/v1/vulnerabilities/{vuln_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"RED: 취약점 상세 조회 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True
        assert body["data"]["patch_pr"] is None, (
            "patch_pr 없는 취약점에서 patch_pr이 null이어야 함"
        )

    def test_get_vulnerability_not_found(self, test_client, auth_headers):
        """I-22: 존재하지 않는 vuln_id → 404.

        Arrange: DB에 없는 UUID.
        Act: GET /api/v1/vulnerabilities/{없는_id}
        Assert: HTTP 404, "취약점을 찾을 수 없습니다" 포함.
        """
        nonexistent_id = "ffffffff-ffff-ffff-ffff-ffffffffffff"

        response = test_client.get(
            f"/api/v1/vulnerabilities/{nonexistent_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404, (
            f"RED: 없는 vuln_id 조회 시 404 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        error_detail = str(body)
        assert "취약점을 찾을 수 없습니다" in error_detail or "404" in str(response.status_code)


# ──────────────────────────────────────────────────────────────
# PATCH /api/v1/vulnerabilities/{vuln_id} 테스트
# ──────────────────────────────────────────────────────────────

class TestPatchVulnerabilityStatus:
    """PATCH /api/v1/vulnerabilities/{vuln_id} 상태 변경 테스트"""

    def test_patch_vulnerability_status_ignored(
        self, test_client, auth_headers, sample_vulnerability_list
    ):
        """I-26: open → ignored 오탐 마킹 — 200, resolved_at 설정.

        Arrange: open 상태의 취약점.
        Act: PATCH /api/v1/vulnerabilities/{vuln_id} { status: "ignored" }
        Assert: HTTP 200, status='ignored', resolved_at이 null이 아님.
        """
        vuln = sample_vulnerability_list[0]  # open 상태
        vuln_id = str(vuln.id)

        response = test_client.patch(
            f"/api/v1/vulnerabilities/{vuln_id}",
            json={"status": "ignored"},
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"RED: 취약점 ignored 마킹 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert data["status"] == "ignored"
        # ignored로 변경 시 resolved_at이 자동 설정되어야 함 (설계서 4-4절)
        assert data["resolved_at"] is not None, (
            "ignored 상태로 변경 시 resolved_at이 자동 설정되어야 함"
        )

    def test_patch_vulnerability_status_patched(
        self, test_client, auth_headers, sample_vulnerability_list
    ):
        """I-27: open → patched 마킹 — 200, resolved_at 설정.

        Arrange: open 상태의 취약점.
        Act: PATCH /api/v1/vulnerabilities/{vuln_id} { status: "patched" }
        Assert: HTTP 200, status='patched', resolved_at이 null이 아님.
        """
        vuln = sample_vulnerability_list[1]  # open 상태 (index 1)
        vuln_id = str(vuln.id)

        response = test_client.patch(
            f"/api/v1/vulnerabilities/{vuln_id}",
            json={"status": "patched"},
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"RED: 취약점 patched 마킹 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert data["status"] == "patched"
        assert data["resolved_at"] is not None, (
            "patched 상태로 변경 시 resolved_at이 자동 설정되어야 함"
        )

    def test_patch_vulnerability_status_false_positive(
        self, test_client, auth_headers, sample_vulnerability_list
    ):
        """I-25: open → false_positive 마킹 — 200, resolved_at 설정.

        Arrange: open 상태의 취약점, reason 포함.
        Act: PATCH /api/v1/vulnerabilities/{vuln_id} { status: "false_positive", reason: "..." }
        Assert: HTTP 200, status='false_positive', resolved_at이 null이 아님.
        """
        vuln = sample_vulnerability_list[0]
        vuln_id = str(vuln.id)

        response = test_client.patch(
            f"/api/v1/vulnerabilities/{vuln_id}",
            json={"status": "false_positive", "reason": "테스트 코드에서만 사용되는 값"},
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"RED: false_positive 마킹 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert data["status"] == "false_positive"
        assert data["resolved_at"] is not None, (
            "false_positive 상태로 변경 시 resolved_at이 자동 설정되어야 함"
        )

    def test_patch_vulnerability_status_reopen(
        self, test_client, auth_headers, sample_vulnerability_list
    ):
        """I-28: false_positive → open 복원 — 200, resolved_at=null.

        Arrange: false_positive 상태의 취약점.
        Act: PATCH /api/v1/vulnerabilities/{vuln_id} { status: "open" }
        Assert: HTTP 200, status='open', resolved_at=null.
        """
        vuln = sample_vulnerability_list[4]  # false_positive 상태 (index 4)
        vuln_id = str(vuln.id)

        response = test_client.patch(
            f"/api/v1/vulnerabilities/{vuln_id}",
            json={"status": "open"},
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"RED: open으로 복원 시 200 반환해야 하지만 {response.status_code} 반환됨."
        )
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert data["status"] == "open"
        # open으로 되돌릴 때 resolved_at이 null이어야 함 (설계서 4-4절)
        assert data["resolved_at"] is None, (
            "open으로 복원 시 resolved_at이 null로 리셋되어야 함"
        )

    def test_patch_vulnerability_invalid_status(
        self, test_client, auth_headers, sample_vulnerability_list
    ):
        """I-33: 잘못된 status 값 → 422 Pydantic validation error.

        Arrange: 허용되지 않는 status 값 사용.
        Act: PATCH /api/v1/vulnerabilities/{vuln_id} { status: "unknown" }
        Assert: HTTP 422.
        """
        vuln = sample_vulnerability_list[0]
        vuln_id = str(vuln.id)

        response = test_client.patch(
            f"/api/v1/vulnerabilities/{vuln_id}",
            json={"status": "unknown"},
            headers=auth_headers,
        )

        assert response.status_code == 422, (
            f"RED: 잘못된 status 값에 422 반환해야 하지만 {response.status_code} 반환됨."
        )

    def test_patch_vulnerability_not_found(self, test_client, auth_headers):
        """I-31: 존재하지 않는 vuln_id → 404.

        Arrange: DB에 없는 UUID.
        Act: PATCH /api/v1/vulnerabilities/{없는_id} { status: "patched" }
        Assert: HTTP 404.
        """
        nonexistent_id = "ffffffff-ffff-ffff-ffff-ffffffffffff"

        response = test_client.patch(
            f"/api/v1/vulnerabilities/{nonexistent_id}",
            json={"status": "patched"},
            headers=auth_headers,
        )

        assert response.status_code == 404, (
            f"RED: 없는 vuln_id PATCH 시 404 반환해야 하지만 {response.status_code} 반환됨."
        )

    def test_patch_vulnerability_requires_auth(self, test_client):
        """I-17 유추: 인증 없이 PATCH 요청 → 401.

        Arrange: 인증 헤더 없이 요청.
        Act: PATCH /api/v1/vulnerabilities/{vuln_id} (Authorization 헤더 없음).
        Assert: HTTP 401.
        """
        vuln_id = "eeeeeeee-eeee-eeee-eeee-000000000000"

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
            response = unauthenticated_client.patch(
                f"/api/v1/vulnerabilities/{vuln_id}",
                json={"status": "patched"},
            )

        assert response.status_code == 401, (
            f"RED: 인증 없이 PATCH 요청 시 401 반환해야 하지만 {response.status_code} 반환됨."
        )

    def test_patch_vulnerability_reason_max_length(
        self, test_client, auth_headers, sample_vulnerability_list
    ):
        """I-34: reason 최대 길이(500자) 초과 → 422.

        Arrange: 501자 reason 문자열.
        Act: PATCH /api/v1/vulnerabilities/{vuln_id} { status: "ignored", reason: "501자" }
        Assert: HTTP 422 (Pydantic max_length=500 제약).
        """
        vuln = sample_vulnerability_list[0]
        vuln_id = str(vuln.id)
        long_reason = "사" * 501  # 501자

        response = test_client.patch(
            f"/api/v1/vulnerabilities/{vuln_id}",
            json={"status": "ignored", "reason": long_reason},
            headers=auth_headers,
        )

        assert response.status_code == 422, (
            f"RED: reason 501자 초과 시 422 반환해야 하지만 {response.status_code} 반환됨."
        )
