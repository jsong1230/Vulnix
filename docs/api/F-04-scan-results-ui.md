# F-04: 스캔 결과 API 스펙 확정본

**버전**: v1.0
**작성일**: 2026-02-25
**상태**: 확정 (GREEN 달성)
**테스트**: 39/39 통과

---

## 개요

F-04에서 구현된 스캔 결과 조회 및 대시보드 통계 API를 정의한다.
모든 엔드포인트는 Bearer JWT 인증을 필수로 요구하며, `{ success, data?, error? }` 형식의 응답을 반환한다.

---

## 공통 사항

### 인증

```
Authorization: Bearer <JWT 토큰>
```

### 공통 응답 형식

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

### 공통 에러 응답

```json
{
  "success": false,
  "data": null,
  "error": "에러 메시지"
}
```

### 페이지네이션 응답 형식

```json
{
  "success": true,
  "data": [ ... ],
  "error": null,
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 45,
    "total_pages": 3
  }
}
```

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 | 파일 |
|--------|------|------|------|
| GET | /api/v1/scans/{scan_id} | 스캔 작업 상태 및 결과 조회 | `api/v1/scans.py` |
| GET | /api/v1/vulnerabilities | 취약점 목록 조회 (필터/페이지네이션) | `api/v1/vulns.py` |
| GET | /api/v1/vulnerabilities/{vuln_id} | 취약점 상세 조회 | `api/v1/vulns.py` |
| PATCH | /api/v1/vulnerabilities/{vuln_id} | 취약점 상태 변경 | `api/v1/vulns.py` |
| GET | /api/v1/dashboard/summary | 대시보드 요약 통계 | `api/v1/dashboard.py` |
| GET | /api/v1/dashboard/trend | 취약점 발견/해결 추이 | `api/v1/dashboard.py` |

---

## GET /api/v1/scans/{scan_id}

**목적**: 스캔 작업의 상태 및 결과 상세 조회

**인증**: Bearer JWT 필수

### Path Parameter

| 이름 | 타입 | 설명 |
|------|------|------|
| scan_id | UUID | 조회할 스캔 작업 ID |

### Response 200

```json
{
  "success": true,
  "data": {
    "id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
    "repo_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    "status": "completed",
    "trigger_type": "manual",
    "commit_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
    "branch": "main",
    "pr_number": null,
    "findings_count": 15,
    "true_positives_count": 8,
    "false_positives_count": 7,
    "duration_seconds": 120,
    "error_message": null,
    "started_at": "2026-02-25T10:00:00",
    "completed_at": "2026-02-25T10:02:00",
    "created_at": "2026-02-25T09:59:50"
  },
  "error": null
}
```

### 에러 케이스

| HTTP | 상황 | 메시지 |
|------|------|--------|
| 401 | 인증 토큰 없음/만료 | "유효하지 않은 인증 정보입니다." |
| 403 | 해당 저장소 팀 멤버가 아님 | "이 스캔에 접근할 권한이 없습니다." |
| 404 | scan_id 존재하지 않음 | "스캔을 찾을 수 없습니다: {scan_id}" |

### 구현 로직

1. `scan_id`로 ScanJob 테이블 조회
2. `repo_id` → Repository → `team_id` → TeamMember에서 현재 사용자 접근 권한 확인
3. `ScanJobResponse` 스키마로 직렬화하여 반환

---

## GET /api/v1/vulnerabilities

**목적**: 팀 전체 취약점 목록 조회 (필터링/페이지네이션 포함)

**인증**: Bearer JWT 필수

### Query Parameters

| 이름 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| page | int | N | 1 | 페이지 번호 (1-based) |
| per_page | int | N | 20 | 페이지당 항목 수 (최대 100) |
| status | string | N | null | open / patched / ignored / false_positive |
| severity | string | N | null | critical / high / medium / low |
| repo_id | UUID | N | null | 특정 저장소 필터 |

### Response 200

```json
{
  "success": true,
  "data": [
    {
      "id": "eeeeeeee-eeee-eeee-eeee-000000000000",
      "status": "open",
      "severity": "critical",
      "vulnerability_type": "sql_injection",
      "file_path": "src/module_0/code.py",
      "start_line": 10,
      "detected_at": "2026-02-25T10:00:00",
      "created_at": "2026-02-25T10:00:00"
    }
  ],
  "error": null,
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 10,
    "total_pages": 1
  }
}
```

### 에러 케이스

| HTTP | 상황 | 메시지 |
|------|------|--------|
| 401 | 인증 토큰 없음/만료 | "유효하지 않은 인증 정보입니다." |
| 422 | 잘못된 파라미터 | Pydantic validation error |

### 구현 로직

1. `current_user.id` → TeamMember → team_ids 목록 조회
2. Vulnerability 테이블에서 `repo_id IN (repo_ids)` 조건으로 필터
3. 추가 필터 (status, severity, repo_id) 적용
4. `detected_at DESC` 정렬
5. 페이지네이션 적용 (OFFSET/LIMIT)
6. `idx_vulnerability_repo_status` 복합 인덱스 활용

---

## GET /api/v1/vulnerabilities/{vuln_id}

**목적**: 취약점 상세 정보 조회 (코드 스니펫, LLM 분석, 패치 PR 포함)

**인증**: Bearer JWT 필수

### Path Parameter

| 이름 | 타입 | 설명 |
|------|------|------|
| vuln_id | UUID | 조회할 취약점 ID |

### Response 200

```json
{
  "success": true,
  "data": {
    "id": "eeeeeeee-eeee-eeee-eeee-000000000000",
    "scan_job_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
    "repo_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    "status": "open",
    "severity": "critical",
    "vulnerability_type": "sql_injection",
    "cwe_id": "CWE-89",
    "owasp_category": "A03:2021 - Injection",
    "file_path": "src/module_0/code.py",
    "start_line": 10,
    "end_line": 12,
    "code_snippet": "# 취약한 코드 예시 0",
    "description": "취약점 설명 0",
    "llm_reasoning": "LLM 분석 근거 0",
    "llm_confidence": 0.9,
    "semgrep_rule_id": "python.security.rule-0",
    "references": ["https://cwe.mitre.org/data/definitions/89.html"],
    "detected_at": "2026-02-25T10:00:00",
    "resolved_at": null,
    "created_at": "2026-02-25T10:00:00",
    "patch_pr": null,
    "repo_full_name": "test-org/test-repo"
  },
  "error": null
}
```

#### patch_pr 필드 (패치 PR이 있는 경우)

```json
"patch_pr": {
  "id": "ffffffff-ffff-ffff-ffff-000000000000",
  "github_pr_number": 42,
  "github_pr_url": "https://github.com/org/repo/pull/42",
  "status": "created",
  "patch_diff": "--- a/src/...\n+++ b/src/...",
  "patch_description": "파라미터 바인딩을 사용하도록 수정"
}
```

### 에러 케이스

| HTTP | 상황 | 메시지 |
|------|------|--------|
| 401 | 인증 토큰 없음/만료 | "유효하지 않은 인증 정보입니다." |
| 403 | 해당 저장소 팀 멤버가 아님 | "이 취약점에 접근할 권한이 없습니다." |
| 404 | vuln_id 존재하지 않음 | "취약점을 찾을 수 없습니다: {vuln_id}" |

### 구현 로직

1. `vuln_id`로 Vulnerability 테이블 조회
2. `repo_id` → Repository → `team_id` → TeamMember에서 접근 권한 확인
3. Repository의 `full_name`을 `repo_full_name` 필드로 응답에 추가
4. `VulnerabilityResponse` 스키마로 직렬화

---

## PATCH /api/v1/vulnerabilities/{vuln_id}

**목적**: 취약점 상태 변경 (오탐 마킹, 무시, 패치 완료 등)

**인증**: Bearer JWT 필수

### Path Parameter

| 이름 | 타입 | 설명 |
|------|------|------|
| vuln_id | UUID | 상태를 변경할 취약점 ID |

### Request Body

```json
{
  "status": "false_positive",
  "reason": "테스트 코드에서만 사용되는 값으로 실제 위험 없음"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| status | string | Y | open / patched / ignored / false_positive |
| reason | string | N | 상태 변경 사유 (최대 500자) |

### Response 200

`VulnerabilityResponse` 전체 필드를 포함한 업데이트된 취약점 정보 반환 (GET /api/v1/vulnerabilities/{vuln_id}와 동일한 형식)

### 에러 케이스

| HTTP | 상황 | 메시지 |
|------|------|--------|
| 401 | 인증 토큰 없음/만료 | "유효하지 않은 인증 정보입니다." |
| 403 | 해당 저장소 팀 멤버가 아님 | "이 취약점을 변경할 권한이 없습니다." |
| 404 | vuln_id 존재하지 않음 | "취약점을 찾을 수 없습니다: {vuln_id}" |
| 422 | 잘못된 status 값 | Pydantic validation error |

### 구현 로직

1. `vuln_id`로 Vulnerability 테이블 조회
2. 접근 권한 확인 (팀 멤버 여부)
3. `status` 값 업데이트
4. `resolved_at` 자동 설정:
   - `patched` / `false_positive` / `ignored` → `resolved_at = datetime.now(UTC)`
   - `open` → `resolved_at = None`
5. DB commit
6. 보안 점수 동기 재계산 (ADR-F04-003):
   - `score = (1 - open_weighted / total_weighted) * 100`
   - 가중치: `critical=10, high=5, medium=2, low=1`
   - 범위 클램핑: `max(0.0, min(100.0, score))`
   - 취약점 0건 시 100점

---

## GET /api/v1/dashboard/summary

**목적**: 대시보드 전체 요약 통계

**인증**: Bearer JWT 필수

### Response 200

```json
{
  "success": true,
  "data": {
    "total_vulnerabilities": 10,
    "severity_distribution": {
      "critical": 1,
      "high": 2,
      "medium": 3,
      "low": 4
    },
    "status_distribution": {
      "open": 6,
      "patched": 2,
      "ignored": 1,
      "false_positive": 1
    },
    "resolution_rate": 30.0,
    "recent_scans": [
      {
        "id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
        "repo_full_name": "test-org/test-repo",
        "status": "completed",
        "findings_count": 15,
        "true_positives_count": 8,
        "created_at": "2026-02-25T09:59:50"
      }
    ],
    "repo_count": 1,
    "last_scan_at": "2026-02-25T10:02:00"
  },
  "error": null
}
```

### 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| total_vulnerabilities | int | 전체 취약점 수 |
| severity_distribution | dict | 심각도별 분포 (critical/high/medium/low) |
| status_distribution | dict | 상태별 분포 (open/patched/ignored/false_positive) |
| resolution_rate | float | 해결률 = (patched + false_positive) / total * 100 |
| recent_scans | list | 최근 스캔 목록 (최대 5건, created_at DESC) |
| repo_count | int | 접근 가능한 저장소 수 |
| last_scan_at | datetime/null | 마지막 스캔 완료 시각 |

### 에러 케이스

| HTTP | 상황 | 메시지 |
|------|------|--------|
| 401 | 인증 토큰 없음/만료 | "유효하지 않은 인증 정보입니다." |

### 구현 로직

1. `current_user` → team_ids → repo_ids 조회
2. Vulnerability 테이블에서 `repo_id IN (repo_ids)` 전체 조회
3. Python 레벨에서 심각도/상태별 집계 및 해결률 계산
4. ScanJob에서 최근 5건 조회 (created_at DESC)
5. ADR-F04-002: PoC 단계에서는 DB 직접 조회 (운영에서 Redis TTL 5분 캐시 적용 예정)

---

## GET /api/v1/dashboard/trend

**목적**: 기간별 취약점 발견/해결 추이

**인증**: Bearer JWT 필수

### Query Parameters

| 이름 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| days | int | N | 30 | 조회할 일수 (최대 90일) |

### Response 200

```json
{
  "success": true,
  "data": {
    "days": 30,
    "data": [
      {
        "date": "2026-01-26",
        "new_count": 0,
        "resolved_count": 0
      },
      {
        "date": "2026-02-25",
        "new_count": 10,
        "resolved_count": 4
      }
    ]
  },
  "error": null
}
```

### 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| days | int | 요청된 조회 일수 |
| data | list | 날짜별 데이터 포인트 목록 (date ASC) |
| data[].date | string | 날짜 (YYYY-MM-DD) |
| data[].new_count | int | 해당 날짜에 탐지된 신규 취약점 수 |
| data[].resolved_count | int | 해당 날짜에 해결된 취약점 수 |

### 에러 케이스

| HTTP | 상황 | 메시지 |
|------|------|--------|
| 401 | 인증 토큰 없음/만료 | "유효하지 않은 인증 정보입니다." |

### 구현 로직

1. `days = min(days, 90)` 최대 90일 제한
2. `current_user` → team_ids → repo_ids 조회
3. `detected_at >= now - days` 조건으로 기간 내 취약점 조회
4. 날짜별 `new_count` (detected_at 기준), `resolved_count` (resolved_at 기준) 집계
5. 데이터 없는 날짜도 `new_count=0, resolved_count=0`으로 채워서 반환 (date ASC)

---

## 스키마 정의

### ScanJobResponse

```python
class ScanJobResponse(BaseModel):
    id: uuid.UUID
    repo_id: uuid.UUID
    status: Literal["queued", "running", "completed", "failed"]
    trigger_type: Literal["webhook", "manual", "schedule"]
    commit_sha: str | None
    branch: str | None
    pr_number: int | None
    findings_count: int
    true_positives_count: int
    false_positives_count: int
    duration_seconds: int | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}
```

### VulnerabilitySummary (목록 조회용 경량 응답)

```python
class VulnerabilitySummary(BaseModel):
    id: uuid.UUID
    status: str
    severity: str
    vulnerability_type: str
    file_path: str
    start_line: int
    detected_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}
```

### PatchPRSummary

```python
class PatchPRSummary(BaseModel):
    id: uuid.UUID
    github_pr_number: int | None
    github_pr_url: str | None
    status: str
    patch_diff: str | None
    patch_description: str | None
    model_config = {"from_attributes": True}
```

### VulnerabilityResponse (상세 조회용)

```python
class VulnerabilityResponse(BaseModel):
    id: uuid.UUID
    scan_job_id: uuid.UUID
    repo_id: uuid.UUID
    status: Literal["open", "patched", "ignored", "false_positive"]
    severity: Literal["critical", "high", "medium", "low"]
    vulnerability_type: str
    cwe_id: str | None
    owasp_category: str | None
    file_path: str
    start_line: int
    end_line: int
    code_snippet: str | None
    description: str | None
    llm_reasoning: str | None
    llm_confidence: float | None
    semgrep_rule_id: str | None
    references: list[str] | None
    detected_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    patch_pr: PatchPRSummary | None = None      # 패치 PR 정보 (F-03 생성)
    repo_full_name: str | None = None            # 저장소 전체 이름 (표시용)
    model_config = {"from_attributes": True}
```

### VulnerabilityStatusUpdateRequest

```python
class VulnerabilityStatusUpdateRequest(BaseModel):
    status: Literal["open", "patched", "ignored", "false_positive"]
    reason: str | None = Field(default=None, max_length=500)
```

### DashboardSummary

```python
class DashboardSummary(BaseModel):
    total_vulnerabilities: int
    severity_distribution: dict[str, int]
    status_distribution: dict[str, int]
    resolution_rate: float
    recent_scans: list[RecentScanItem]
    repo_count: int
    last_scan_at: datetime | None
```

### RecentScanItem

```python
class RecentScanItem(BaseModel):
    id: uuid.UUID
    repo_full_name: str
    status: str
    findings_count: int
    true_positives_count: int
    created_at: datetime
```

### TrendResponse

```python
class TrendResponse(BaseModel):
    days: int
    data: list[TrendDataPoint]

class TrendDataPoint(BaseModel):
    date: str          # YYYY-MM-DD
    new_count: int
    resolved_count: int
```

---

## 구현 파일 목록

| 파일 | 역할 |
|------|------|
| `backend/src/api/v1/scans.py` | GET /api/v1/scans/{scan_id} |
| `backend/src/api/v1/vulns.py` | GET/PATCH /api/v1/vulnerabilities/* |
| `backend/src/api/v1/dashboard.py` | GET /api/v1/dashboard/* |
| `backend/src/schemas/scan.py` | ScanJobResponse, ScanTriggerRequest |
| `backend/src/schemas/vulnerability.py` | VulnerabilityResponse, VulnerabilitySummary, PatchPRSummary |
| `backend/src/schemas/dashboard.py` | DashboardSummary, RecentScanItem, TrendResponse, TrendDataPoint |

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-02-25 | 초안 작성 (GREEN 달성, 39/39 테스트 통과) |
