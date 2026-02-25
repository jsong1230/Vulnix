# F-04: 스캔 결과 API 및 기본 UI -- 기술 설계서

**버전**: v1.0
**작성일**: 2026-02-25
**상태**: 초안

---

## 1. 참조

- 인수조건: `docs/project/features.md` #F-04
- 시스템 설계: `docs/system/system-design.md` (3-1, 3-6, 3-7절)

## 2. 구현 범위

### 2-1. F-04 인수조건 매핑

| 인수조건 | 구현 대상 | 유형 |
|----------|-----------|------|
| 스캔 결과 목록 조회 REST API 제공 | `GET /api/v1/scans/{scan_id}`, `GET /api/v1/repos/{repo_id}/scans` | Backend |
| 취약점 상세 정보 조회 API 제공 | `GET /api/v1/vulnerabilities/{vuln_id}` | Backend |
| 저장소별 스캔 히스토리 조회 API 제공 | `GET /api/v1/repos/{repo_id}/scans` | Backend |
| 웹 UI에서 취약점 목록 확인 가능 | `dashboard/page.tsx`, `GET /api/v1/vulnerabilities` | Frontend + Backend |
| 웹 UI에서 취약점 상세 확인 가능 | `vulnerabilities/[id]/page.tsx` | Frontend |
| 웹 UI에서 수동 스캔 트리거 버튼 동작 | `scan-trigger-button.tsx` (기 구현), `scans/[id]/page.tsx` | Frontend |

### 2-2. 현재 상태 분석

기존 코드베이스에 이미 **라우터 스캐폴드**와 **Pydantic 스키마**, **프론트엔드 페이지 껍데기**가 존재한다. 모든 엔드포인트는 `raise NotImplementedError("TODO: ...")` 상태이고, 프론트엔드 페이지는 하드코딩된 더미 데이터를 표시하고 있다. 이번 구현은 **스캐폴드를 실제 동작하는 코드로 채우는 작업**이다.

---

## 3. 아키텍처 결정

### ADR-F04-001: 프론트엔드 데이터 페칭 패턴

- **선택지**: A) React Query (TanStack Query) / B) SWR / C) useEffect + useState 수동 관리
- **결정**: A) React Query
- **근거**: system-design.md 3-7절에서 TanStack Query를 명시. 폴링(refetchInterval), 캐시 무효화, 옵티미스틱 업데이트 등 F-04에서 필요한 기능을 네이티브 지원. 스캔 상태 폴링(2초 간격)을 `refetchInterval`로 깔끔하게 구현 가능.

### ADR-F04-002: 대시보드 요약 통계 캐싱

- **선택지**: A) Redis 캐시 (TTL: 5분) / B) DB 직접 조회 매번
- **결정**: A) Redis 캐시 (TTL: 5분)
- **근거**: dashboard/summary는 집계 쿼리 (COUNT, GROUP BY)를 여러 테이블에서 수행. 동시 사용자가 대시보드를 열 때마다 무거운 쿼리를 실행하는 것은 비효율적. Redis TTL 5분이면 거의 실시간에 가깝고, 스캔 완료 이벤트 시 캐시를 수동 무효화할 수도 있다.

### ADR-F04-003: 취약점 상태 변경 시 보안 점수 재계산 타이밍

- **선택지**: A) 동기적 즉시 계산 / B) 비동기 워커에서 계산
- **결정**: A) 동기적 즉시 계산
- **근거**: PoC 단계에서 저장소당 취약점 수가 많지 않으므로 (수십~수백 건) 즉시 계산해도 응답 시간에 큰 영향 없음. 사용자가 상태 변경 직후 대시보드에서 반영된 점수를 바로 확인할 수 있어 UX 우수.

### ADR-F04-004: 코드 뷰어 구현 방식

- **선택지**: A) `<pre>` + CSS 줄 번호 / B) Monaco Editor (읽기 전용) / C) Prism.js 구문 강조
- **결정**: A) `<pre>` + CSS 줄 번호 (PoC), 패치 diff는 unified diff 색상 파싱
- **근거**: PoC 단계에서 Monaco Editor는 번들 크기가 과도 (약 2MB). Prism.js도 의존성 추가 필요. 코드 스니펫이 전후 5줄 정도로 짧으므로 `<pre>` 태그에 줄 번호와 취약 라인 하이라이트(배경색)만 표시하면 충분. 패치 diff는 `+` / `-` 접두사 기반 줄별 색상 처리로 구현.

---

## 4. API 설계

### 4-1. GET /api/v1/scans/{scan_id}

**파일**: `backend/src/api/v1/scans.py` (기 스캐폴드, `get_scan` 함수)

**목적**: 특정 스캔 작업의 상태 및 결과 상세 조회

**인증**: Bearer JWT 필수

**Path Parameter**:

| 이름 | 타입 | 설명 |
|------|------|------|
| scan_id | UUID | 조회할 스캔 작업 ID |

**Response 200**:

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "repo_id": "uuid",
    "status": "completed",
    "trigger_type": "manual",
    "commit_sha": "a1b2c3d4...",
    "branch": "main",
    "pr_number": null,
    "findings_count": 15,
    "true_positives_count": 8,
    "false_positives_count": 7,
    "duration_seconds": 120,
    "error_message": null,
    "started_at": "2026-02-25T10:00:00Z",
    "completed_at": "2026-02-25T10:02:00Z",
    "created_at": "2026-02-25T09:59:50Z"
  },
  "error": null
}
```

**에러 케이스**:

| HTTP 코드 | 상황 | error 메시지 |
|-----------|------|-------------|
| 401 | 인증 토큰 없음/만료 | "유효하지 않은 인증 정보입니다." |
| 403 | 해당 저장소가 속한 팀의 멤버가 아님 | "이 스캔에 접근할 권한이 없습니다." |
| 404 | scan_id가 존재하지 않음 | "스캔을 찾을 수 없습니다: {scan_id}" |

**구현 로직**:

1. `scan_id`로 ScanJob 테이블 조회
2. ScanJob의 `repo_id` -> Repository의 `team_id` -> TeamMember에서 `current_user.id`와 매칭하여 접근 권한 확인
3. `ScanJobResponse` 스키마로 직렬화하여 반환

### 4-2. GET /api/v1/vulnerabilities

**파일**: `backend/src/api/v1/vulns.py` (기 스캐폴드, `list_vulnerabilities` 함수)

**목적**: 팀 전체 취약점 목록 조회 (필터링/페이지네이션 포함)

**인증**: Bearer JWT 필수

**Query Parameters**:

| 이름 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| page | int | N | 1 | 페이지 번호 (1-based) |
| per_page | int | N | 20 | 페이지당 항목 수 (최대 100) |
| status | string | N | null | 상태 필터: open / patched / ignored / false_positive |
| severity | string | N | null | 심각도 필터: critical / high / medium / low |
| repo_id | UUID | N | null | 특정 저장소 필터 |

**Response 200**:

```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "status": "open",
      "severity": "high",
      "vulnerability_type": "sql_injection",
      "file_path": "src/db/queries.py",
      "start_line": 42,
      "detected_at": "2026-02-25T10:00:00Z",
      "created_at": "2026-02-25T10:00:00Z"
    }
  ],
  "error": null,
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 45,
    "total_pages": 3
  }
}
```

**에러 케이스**:

| HTTP 코드 | 상황 | error 메시지 |
|-----------|------|-------------|
| 401 | 인증 토큰 없음/만료 | "유효하지 않은 인증 정보입니다." |
| 422 | 잘못된 status/severity 값 | Pydantic validation error |

**구현 로직**:

1. `current_user.id` -> TeamMember -> team_ids 목록 조회
2. Vulnerability 테이블에서 `repo_id IN (SELECT id FROM repository WHERE team_id IN (:team_ids))` 조건으로 필터
3. 추가 필터 (status, severity, repo_id) 적용
4. `idx_vulnerability_repo_status` 복합 인덱스 활용을 위해 repo_id + status 순서로 WHERE 조건 구성
5. `detected_at DESC` 정렬 (최근 탐지 먼저)
6. 페이지네이션 적용 (OFFSET/LIMIT)

### 4-3. GET /api/v1/vulnerabilities/{vuln_id}

**파일**: `backend/src/api/v1/vulns.py` (기 스캐폴드, `get_vulnerability` 함수)

**목적**: 취약점 상세 정보 조회 (코드 스니펫, LLM 분석 결과, 패치 PR 정보 포함)

**인증**: Bearer JWT 필수

**Path Parameter**:

| 이름 | 타입 | 설명 |
|------|------|------|
| vuln_id | UUID | 조회할 취약점 ID |

**Response 200**:

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "scan_job_id": "uuid",
    "repo_id": "uuid",
    "status": "open",
    "severity": "high",
    "vulnerability_type": "sql_injection",
    "cwe_id": "CWE-89",
    "owasp_category": "A03:2021 - Injection",
    "file_path": "src/db/queries.py",
    "start_line": 42,
    "end_line": 48,
    "code_snippet": "def get_user(user_id: str):\n    query = f\"SELECT * FROM users WHERE id = {user_id}\"\n    return db.execute(query)",
    "description": "SQL 쿼리에 사용자 입력값이 직접 삽입되어 SQL Injection 공격에 취약합니다.",
    "llm_reasoning": "사용자 입력값(user_id)이 f-string으로 직접 SQL 쿼리에 삽입됩니다.",
    "llm_confidence": 0.95,
    "semgrep_rule_id": "python.sqlalchemy.security.sql-injection",
    "references": ["https://owasp.org/A03_2021-Injection", "https://cwe.mitre.org/data/definitions/89.html"],
    "detected_at": "2026-02-25T10:00:00Z",
    "resolved_at": null,
    "created_at": "2026-02-25T10:00:00Z",
    "patch_pr": {
      "id": "uuid",
      "github_pr_number": 42,
      "github_pr_url": "https://github.com/org/repo/pull/42",
      "status": "created",
      "patch_diff": "--- a/src/db/queries.py\n+++ b/src/db/queries.py\n...",
      "patch_description": "파라미터 바인딩을 사용하도록 수정"
    },
    "repo_full_name": "org/repo-name"
  },
  "error": null
}
```

**에러 케이스**:

| HTTP 코드 | 상황 | error 메시지 |
|-----------|------|-------------|
| 401 | 인증 토큰 없음/만료 | "유효하지 않은 인증 정보입니다." |
| 403 | 해당 저장소 팀 멤버가 아님 | "이 취약점에 접근할 권한이 없습니다." |
| 404 | vuln_id가 존재하지 않음 | "취약점을 찾을 수 없습니다: {vuln_id}" |

**구현 로직**:

1. `vuln_id`로 Vulnerability 테이블 조회 (`selectinload(Vulnerability.patch_pr)` 로 패치 PR eager load)
2. `Vulnerability.repo_id` -> Repository -> `team_id` -> TeamMember에서 접근 권한 확인
3. Repository의 `full_name`을 추가 조회하여 `repo_full_name` 필드로 응답에 포함
4. `VulnerabilityResponse` 스키마로 직렬화

**스키마 수정 필요 사항**:

`VulnerabilityResponse`에 다음 필드를 추가해야 한다:

```python
# 패치 PR 정보 (관계 데이터, null 가능)
patch_pr: PatchPRSummary | None = None
# 저장소 전체 이름 (표시용)
repo_full_name: str | None = None
```

새 스키마 `PatchPRSummary`:

```python
class PatchPRSummary(BaseModel):
    """패치 PR 요약 (취약점 상세에 포함)"""
    id: uuid.UUID
    github_pr_number: int | None
    github_pr_url: str | None
    status: str
    patch_diff: str | None
    patch_description: str | None

    model_config = {"from_attributes": True}
```

### 4-4. PATCH /api/v1/vulnerabilities/{vuln_id}

**파일**: `backend/src/api/v1/vulns.py` (기 스캐폴드, `update_vulnerability_status` 함수)

**목적**: 취약점 상태 변경 (오탐 마킹, 무시, 패치 완료 등)

**인증**: Bearer JWT 필수

**Path Parameter**:

| 이름 | 타입 | 설명 |
|------|------|------|
| vuln_id | UUID | 상태를 변경할 취약점 ID |

**Request Body** (기존 스키마 `VulnerabilityStatusUpdateRequest` 재사용):

```json
{
  "status": "false_positive",
  "reason": "테스트 코드에서만 사용되는 값으로 실제 위험 없음"
}
```

**Response 200**:

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "status": "false_positive",
    "resolved_at": "2026-02-25T12:00:00Z",
    "...": "(VulnerabilityResponse 전체 필드)"
  },
  "error": null
}
```

**에러 케이스**:

| HTTP 코드 | 상황 | error 메시지 |
|-----------|------|-------------|
| 401 | 인증 토큰 없음/만료 | "유효하지 않은 인증 정보입니다." |
| 403 | 해당 저장소 팀 멤버가 아님 | "이 취약점을 변경할 권한이 없습니다." |
| 404 | vuln_id가 존재하지 않음 | "취약점을 찾을 수 없습니다: {vuln_id}" |
| 422 | 잘못된 status 값 | Pydantic validation error |

**구현 로직**:

1. `vuln_id`로 Vulnerability 테이블 조회
2. 접근 권한 확인 (팀 멤버 여부)
3. `status` 값 업데이트
4. `patched` 또는 `false_positive` 또는 `ignored`로 변경 시 `resolved_at = datetime.now(UTC)` 자동 설정
5. `open`으로 되돌릴 경우 `resolved_at = None`으로 리셋
6. DB commit 후 보안 점수 재계산 트리거 (동기)
7. Redis 대시보드 캐시 무효화

**보안 점수 재계산 로직**:

```
score = (1 - (open_vulns_weighted / total_vulns_weighted)) * 100

weight: critical=10, high=5, medium=2, low=1
open_vulns_weighted = sum(weight[v.severity] for v in open_vulns)
total_vulns_weighted = sum(weight[v.severity] for v in all_vulns)
```

점수가 0~100 범위를 벗어나면 `max(0, min(100, score))`로 클램핑. 취약점이 0건이면 100점.

### 4-5. GET /api/v1/dashboard/summary

**파일**: `backend/src/api/v1/dashboard.py` (기 스캐폴드, `get_dashboard_summary` 함수)

**목적**: 대시보드 전체 요약 통계

**인증**: Bearer JWT 필수

**Response 200**:

```json
{
  "success": true,
  "data": {
    "total_vulnerabilities": 45,
    "severity_distribution": {
      "critical": 3,
      "high": 12,
      "medium": 20,
      "low": 10
    },
    "status_distribution": {
      "open": 25,
      "patched": 15,
      "ignored": 3,
      "false_positive": 2
    },
    "resolution_rate": 44.4,
    "recent_scans": [
      {
        "id": "uuid",
        "repo_full_name": "org/repo-name",
        "status": "completed",
        "findings_count": 5,
        "true_positives_count": 3,
        "created_at": "2026-02-25T10:00:00Z"
      }
    ],
    "repo_count": 5,
    "last_scan_at": "2026-02-25T10:00:00Z"
  },
  "error": null
}
```

**구현 로직**:

1. Redis 캐시 키 확인: `dashboard:summary:{team_id_hash}` (TTL 5분)
2. 캐시 히트 시 즉시 반환
3. 캐시 미스 시:
   - `current_user` -> team_ids -> 해당 팀의 모든 repo_ids 조회
   - Vulnerability 테이블에서 `repo_id IN (:repo_ids)` 조건으로 집계 쿼리:
     - `COUNT(*)` GROUP BY severity -> severity_distribution
     - `COUNT(*)` GROUP BY status -> status_distribution
     - resolution_rate = `(patched + false_positive) / total * 100`
   - ScanJob 테이블에서 최근 5건 조회 (created_at DESC, LIMIT 5)
     - scan과 repository JOIN으로 `repo_full_name` 포함
   - Repository 테이블에서 `COUNT(*)` -> repo_count
   - ScanJob 테이블에서 `MAX(completed_at)` -> last_scan_at
4. 결과를 Redis에 JSON 직렬화하여 캐시 저장

**스키마 추가 필요**:

```python
class DashboardSummary(BaseModel):
    """대시보드 요약 통계"""
    total_vulnerabilities: int
    severity_distribution: dict[str, int]
    status_distribution: dict[str, int]
    resolution_rate: float
    recent_scans: list[RecentScanItem]
    repo_count: int
    last_scan_at: datetime | None

class RecentScanItem(BaseModel):
    """최근 스캔 항목"""
    id: uuid.UUID
    repo_full_name: str
    status: str
    findings_count: int
    true_positives_count: int
    created_at: datetime
```

`dashboard.py`의 응답 타입을 `ApiResponse[dict]`에서 `ApiResponse[DashboardSummary]`로 변경.

### 4-6. GET /api/v1/repos/{repo_id}/scans

**파일**: `backend/src/api/v1/repos.py` (기 스캐폴드, `list_repo_scans` 함수)

**목적**: 저장소별 스캔 히스토리 조회

**인증**: Bearer JWT 필수

**Path Parameter**:

| 이름 | 타입 | 설명 |
|------|------|------|
| repo_id | UUID | 조회할 저장소 ID |

**Query Parameters**:

| 이름 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| page | int | N | 1 | 페이지 번호 |
| per_page | int | N | 20 | 페이지당 항목 수 (최대 100) |

**Response 200**:

```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "repo_id": "uuid",
      "status": "completed",
      "trigger_type": "webhook",
      "commit_sha": "a1b2c3d4...",
      "branch": "main",
      "pr_number": null,
      "findings_count": 15,
      "true_positives_count": 8,
      "false_positives_count": 7,
      "duration_seconds": 120,
      "error_message": null,
      "started_at": "2026-02-25T10:00:00Z",
      "completed_at": "2026-02-25T10:02:00Z",
      "created_at": "2026-02-25T09:59:50Z"
    }
  ],
  "error": null,
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 12,
    "total_pages": 1
  }
}
```

**에러 케이스**:

| HTTP 코드 | 상황 | error 메시지 |
|-----------|------|-------------|
| 401 | 인증 토큰 없음/만료 | "유효하지 않은 인증 정보입니다." |
| 403 | 해당 저장소 팀 멤버가 아님 | "이 저장소에 접근할 권한이 없습니다." |
| 404 | repo_id가 존재하지 않음 | "저장소를 찾을 수 없습니다: {repo_id}" |

**구현 로직**:

1. `repo_id`로 Repository 조회 -> 존재 확인 + team_id 추출
2. 접근 권한 확인 (팀 멤버 여부)
3. ScanJob 테이블에서 `repo_id` 필터, `created_at DESC` 정렬
4. `idx_scan_job_repo_status` 인덱스 활용
5. 페이지네이션 적용

### 4-7. GET /api/v1/repos/{repo_id}/vulnerabilities

**파일**: `backend/src/api/v1/repos.py` (기 스캐폴드, `list_repo_vulnerabilities` 함수)

**목적**: 저장소별 취약점 목록 조회

**인증**: Bearer JWT 필수

**Path Parameter / Query Parameters**: repo_id(UUID), page, per_page, status, severity -- `GET /api/v1/vulnerabilities`와 동일한 필터 파라미터

**구현 로직**:

1. `repo_id`로 Repository 조회 -> 존재 확인 + 접근 권한
2. Vulnerability 테이블에서 `repo_id` 필터 + 추가 필터 적용
3. `idx_vulnerability_repo_status` 인덱스 활용
4. `detected_at DESC` 정렬 + 페이지네이션

---

## 5. 프론트엔드 구현 상세

### 5-1. React Query 설정

**신규 파일**: `frontend/src/lib/hooks/use-scans.ts`

```typescript
// useScanDetail(scanId): GET /api/v1/scans/{scanId}
//   - refetchInterval: scan.status가 'queued' 또는 'running'이면 2000ms, 그 외 false
//   - staleTime: 0 (항상 최신 데이터 확인)

// useScanTrigger(): POST /api/v1/scans (mutation)
//   - onSuccess: 쿼리 캐시 무효화 (queryClient.invalidateQueries(['scans']))
```

**신규 파일**: `frontend/src/lib/hooks/use-vulnerabilities.ts`

```typescript
// useVulnerabilityList(filters): GET /api/v1/vulnerabilities
//   - filters: { page, perPage, status, severity, repoId }
//   - staleTime: 30000 (30초)
//   - keepPreviousData: true (페이지네이션 시 깜빡임 방지)

// useVulnerabilityDetail(vulnId): GET /api/v1/vulnerabilities/{vulnId}
//   - staleTime: 30000

// useUpdateVulnerabilityStatus(): PATCH /api/v1/vulnerabilities/{vulnId} (mutation)
//   - onSuccess: 해당 취약점 쿼리 + 목록 쿼리 + 대시보드 쿼리 무효화
```

**신규 파일**: `frontend/src/lib/hooks/use-dashboard.ts`

```typescript
// useDashboardSummary(): GET /api/v1/dashboard/summary
//   - staleTime: 60000 (1분, 서버에서 5분 TTL 캐시이므로)
//   - refetchOnWindowFocus: true
```

### 5-2. dashboard/page.tsx 수정

**파일**: `frontend/src/app/dashboard/page.tsx`

**변경 내용**:

1. 'use client' 디렉티브 추가 (React Query hook 사용을 위해)
2. 하드코딩된 `summaryStats` 제거 -> `useDashboardSummary()` 훅으로 교체
3. "최근 탐지된 취약점" 섹션에 실제 데이터 렌더링:
   - `useVulnerabilityList({ page: 1, perPage: 5, status: 'open' })` 호출
   - 각 항목을 `<Link href="/vulnerabilities/{id}">` 로 감싸서 상세 페이지로 연결
   - SeverityBadge 컴포넌트 재활용
4. "최근 스캔 기록" 섹션에 `summary.recent_scans` 데이터 렌더링:
   - 각 항목을 `<Link href="/scans/{id}">` 로 감싸서 상세 페이지로 연결
   - 상태 배지 (queued/running/completed/failed) 표시
5. 로딩 상태: 스켈레톤 UI (Tailwind animate-pulse 카드)
6. 에러 상태: "데이터를 불러오지 못했습니다" + 재시도 버튼

**신규 컴포넌트**: `frontend/src/components/dashboard/recent-vulnerabilities.tsx`

- Props: `vulnerabilities: VulnerabilitySummary[]`
- 취약점 목록을 SeverityBadge + 파일 경로 + 탐지 시각으로 렌더링
- 빈 상태 표시 (기존 SVG 아이콘 재활용)

**신규 컴포넌트**: `frontend/src/components/dashboard/recent-scans.tsx`

- Props: `scans: RecentScanItem[]`
- 스캔 목록을 상태 배지 + 저장소명 + 결과 수로 렌더링
- 빈 상태 표시

### 5-3. vulnerabilities/[id]/page.tsx 수정

**파일**: `frontend/src/app/vulnerabilities/[id]/page.tsx`

**변경 내용**:

1. 'use client' 디렉티브 추가
2. 하드코딩된 `vuln` 객체 제거 -> `useVulnerabilityDetail(id)` 훅으로 교체
3. "오탐으로 표시" / "무시" 버튼에 `useUpdateVulnerabilityStatus()` 뮤테이션 연결
   - 클릭 시 확인 다이얼로그 표시 (window.confirm)
   - 뮤테이션 성공 시 상태 배지 즉시 반영 (옵티미스틱 업데이트 또는 리페치)
4. 패치 diff 렌더링 개선:
   - `+` 줄: `bg-green-900/30 text-green-300`
   - `-` 줄: `bg-red-900/30 text-red-300`
   - `@@` 줄: `text-blue-400`
   - 나머지: `text-gray-400`
5. 패치 PR 링크 표시:
   - `patch_pr`이 존재하고 `github_pr_url`이 있으면 GitHub PR 링크 버튼 표시
   - 외부 링크 아이콘 (ArrowTopRightOnSquare) 포함
6. 코드 스니펫에 줄 번호 표시:
   - `start_line`부터 줄 번호 시작
   - 취약 라인 범위 (`start_line ~ end_line`) 배경색 하이라이트 (`bg-red-900/20`)

**신규 컴포넌트**: `frontend/src/components/vulnerability/code-viewer.tsx`

- Props: `codeSnippet: string, startLine: number, endLine: number, highlightStart: number, highlightEnd: number`
- 줄 번호 표시 + 취약 라인 하이라이트

**신규 컴포넌트**: `frontend/src/components/vulnerability/patch-diff-viewer.tsx`

- Props: `diff: string`
- unified diff 색상 파싱 렌더링

**신규 컴포넌트**: `frontend/src/components/vulnerability/status-actions.tsx`

- Props: `vulnId: string, currentStatus: string, onStatusChange: (newStatus) => void`
- 드롭다운 또는 버튼 그룹으로 상태 변경 액션 제공
- 현재 상태에 따라 가능한 액션만 노출:
  - open -> false_positive, ignored, patched
  - false_positive -> open
  - ignored -> open
  - patched -> open

### 5-4. scans/[id]/page.tsx 수정

**파일**: `frontend/src/app/scans/[id]/page.tsx`

**변경 내용**:

1. 'use client' 디렉티브 추가
2. 하드코딩된 `scan` 객체 제거 -> `useScanDetail(id)` 훅으로 교체
3. **상태 폴링 구현**:
   - scan.status가 `queued` 또는 `running`이면 `refetchInterval: 2000` (2초)
   - `completed` 또는 `failed`이면 폴링 중지 (`refetchInterval: false`)
4. 완료 상태에서 취약점 목록 표시:
   - `useVulnerabilityList({ repoId: scan.repoId, page: 1, perPage: 50 })` 또는
   - 스캔 ID 기반 필터가 필요하면 `scan_job_id` 필터 추가 검토 (현재 스키마에 없으므로 repo_id 기반으로 최근 스캔 결과 표시)
5. 스캔 소요 시간 표시: `duration_seconds`를 "X분 Y초" 형식으로 포매팅
6. 로딩 상태: 스켈레톤 UI
7. 에러 상태: 에러 메시지 표시 + 재시도 버튼

### 5-5. 수동 스캔 트리거 후 스캔 상세 페이지 연결

**파일**: `frontend/src/components/repos/scan-trigger-button.tsx` (기 구현, 수정)

**변경 내용**:

- `onSuccess` 콜백에서 `alert()` 대신 `router.push(/scans/${job.id})` 로 스캔 상세 페이지로 이동
- 사용자가 스캔 진행 상태를 실시간으로 확인할 수 있도록 함
- `useRouter()` import 추가

---

## 6. 시퀀스 흐름

### 6-1. 수동 스캔 트리거 -> 결과 확인 흐름

```
사용자
  -> [클릭] 수동 스캔 버튼 (scan-trigger-button.tsx)
  -> POST /api/v1/scans { repo_id }
  -> FastAPI -> ScanOrchestrator.enqueue_scan() -> Redis 큐 등록
  -> 응답: { success: true, data: { id: "scan-123", status: "queued" } }
  -> router.push("/scans/scan-123")
  -> scans/[id]/page.tsx 렌더링 (상태: queued)
  -> 2초 간격 폴링: GET /api/v1/scans/scan-123
  -> (백그라운드) 워커가 스캔 실행 -> status: running
  -> (백그라운드) 스캔 완료 -> status: completed, findings_count: N
  -> 폴링으로 completed 상태 수신 -> 폴링 중지
  -> 취약점 목록 렌더링
  -> [클릭] 취약점 항목
  -> GET /api/v1/vulnerabilities/{vuln_id}
  -> vulnerabilities/[id]/page.tsx 렌더링
```

### 6-2. 취약점 상태 변경 흐름

```
사용자
  -> vulnerabilities/[id]/page.tsx
  -> [클릭] "오탐으로 표시" 버튼
  -> 확인 다이얼로그 ("정말 오탐으로 표시하시겠습니까?")
  -> PATCH /api/v1/vulnerabilities/{vuln_id} { status: "false_positive", reason: "..." }
  -> FastAPI:
     1. Vulnerability.status = "false_positive"
     2. Vulnerability.resolved_at = now()
     3. Repository.security_score 재계산
     4. Redis 대시보드 캐시 무효화
  -> 응답: { success: true, data: { ...updated vuln } }
  -> React Query: 취약점 상세 + 목록 + 대시보드 쿼리 무효화
  -> UI 즉시 반영
```

### 6-3. 대시보드 로딩 흐름

```
사용자
  -> /dashboard 접속
  -> dashboard/page.tsx 렌더링
  -> useDashboardSummary() 호출
  -> GET /api/v1/dashboard/summary
  -> FastAPI:
     1. Redis 캐시 키 확인
     2-a. 캐시 히트 -> 즉시 반환
     2-b. 캐시 미스 -> DB 집계 쿼리 실행 -> Redis 저장 (TTL 5분) -> 반환
  -> 응답 수신 -> SummaryCard 컴포넌트 업데이트
  -> useVulnerabilityList({ status: 'open', perPage: 5 }) 호출
  -> GET /api/v1/vulnerabilities?status=open&per_page=5
  -> "최근 탐지된 취약점" 섹션 렌더링
```

---

## 7. 영향 범위

### 수정 필요 파일

| 파일 | 변경 내용 |
|------|-----------|
| `backend/src/api/v1/scans.py` | `get_scan` TODO 구현 |
| `backend/src/api/v1/vulns.py` | `list_vulnerabilities`, `get_vulnerability`, `update_vulnerability_status` TODO 구현 |
| `backend/src/api/v1/dashboard.py` | `get_dashboard_summary` TODO 구현, 응답 타입 dict -> DashboardSummary |
| `backend/src/api/v1/repos.py` | `list_repo_scans`, `list_repo_vulnerabilities` TODO 구현 |
| `backend/src/schemas/vulnerability.py` | `VulnerabilityResponse`에 `patch_pr`, `repo_full_name` 필드 추가 |
| `frontend/src/app/dashboard/page.tsx` | 'use client' 추가, React Query 연동, 더미 데이터 제거 |
| `frontend/src/app/vulnerabilities/[id]/page.tsx` | 'use client' 추가, React Query 연동, 상태 변경 기능, diff 뷰어 |
| `frontend/src/app/scans/[id]/page.tsx` | 'use client' 추가, React Query 연동, 상태 폴링 |
| `frontend/src/components/repos/scan-trigger-button.tsx` | alert -> router.push 변경 |

### 신규 생성 파일

| 파일 | 설명 |
|------|------|
| `backend/src/schemas/dashboard.py` | DashboardSummary, RecentScanItem 스키마 |
| `backend/src/schemas/patch_pr.py` | PatchPRSummary 스키마 |
| `backend/src/services/security_score.py` | 보안 점수 계산 서비스 |
| `frontend/src/lib/hooks/use-scans.ts` | 스캔 관련 React Query 훅 |
| `frontend/src/lib/hooks/use-vulnerabilities.ts` | 취약점 관련 React Query 훅 |
| `frontend/src/lib/hooks/use-dashboard.ts` | 대시보드 React Query 훅 |
| `frontend/src/components/dashboard/recent-vulnerabilities.tsx` | 최근 취약점 목록 컴포넌트 |
| `frontend/src/components/dashboard/recent-scans.tsx` | 최근 스캔 목록 컴포넌트 |
| `frontend/src/components/vulnerability/code-viewer.tsx` | 코드 스니펫 뷰어 컴포넌트 |
| `frontend/src/components/vulnerability/patch-diff-viewer.tsx` | 패치 diff 뷰어 컴포넌트 |
| `frontend/src/components/vulnerability/status-actions.tsx` | 상태 변경 액션 컴포넌트 |

---

## 8. 성능 설계

### 8-1. 인덱스 활용

기존 인덱스 (system-design.md 4-3절)로 충분:

| 인덱스 | 활용 쿼리 |
|--------|-----------|
| `idx_vulnerability_repo_status` | 취약점 목록 필터 (repo_id + status) |
| `idx_vulnerability_severity` | 심각도별 필터 |
| `idx_scan_job_repo_status` | 저장소별 스캔 히스토리 |
| `idx_scan_job_created` | 최근 스캔 정렬 |

### 8-2. Redis 캐싱 전략

| 캐시 키 | TTL | 무효화 시점 |
|---------|-----|-------------|
| `dashboard:summary:{team_hash}` | 5분 | 스캔 완료 시, 취약점 상태 변경 시 |

### 8-3. 프론트엔드 쿼리 전략

| 훅 | staleTime | refetchInterval | keepPreviousData |
|----|-----------|-----------------|------------------|
| useDashboardSummary | 60s | false | false |
| useVulnerabilityList | 30s | false | true |
| useVulnerabilityDetail | 30s | false | false |
| useScanDetail | 0s | 2000ms (진행중) / false (완료) | false |

---

## 9. DB 설계

### 9-1. 기존 테이블 변경

F-04에서는 기존 DB 테이블 스키마 변경이 **없다**. 모든 필요한 컬럼은 system-design.md 4-2절에 이미 정의되어 있고, 모델 파일도 구현 완료 상태이다.

### 9-2. 권한 확인 공통 헬퍼

여러 엔드포인트에서 반복되는 "사용자 -> 팀 멤버 -> 저장소 접근 권한" 확인 로직을 공통 헬퍼로 추출:

```python
# backend/src/api/deps.py 에 추가
async def verify_repo_access(
    db: AsyncSession,
    user_id: uuid.UUID,
    repo_id: uuid.UUID,
) -> Repository:
    """저장소 접근 권한을 확인하고 Repository 객체를 반환한다.

    Raises:
        HTTPException 404: 저장소가 존재하지 않음
        HTTPException 403: 접근 권한 없음
    """
```

이 헬퍼는 `repos.py`에 이미 존재하는 `get_repo_by_id`와 `get_user_team_role` 패턴을 재사용하되, 공통 의존성 모듈(`deps.py`)로 이동하여 `scans.py`, `vulns.py`, `dashboard.py`에서도 활용할 수 있게 한다.

---

## 변경 이력

| 날짜 | 변경 내용 | 이유 |
|------|-----------|------|
| 2026-02-25 | 초안 작성 | F-04 기능 설계 |
