# F-06 오탐 관리 API 스펙 확정본

**버전**: v1.0
**작성일**: 2026-02-25
**상태**: 구현 완료 (GREEN)

---

## 1. 개요

오탐 패턴 CRUD 및 오탐율 대시보드 API.
팀 단위로 Semgrep 룰 ID + 파일 glob 패턴을 등록하여 스캔 파이프라인에서 자동 필터링에 활용한다.

---

## 2. 엔드포인트 목록

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/v1/false-positives` | 오탐 패턴 등록 |
| GET | `/api/v1/false-positives` | 오탐 패턴 목록 조회 |
| DELETE | `/api/v1/false-positives/{pattern_id}` | 오탐 패턴 비활성화 (소프트 삭제) |
| PUT | `/api/v1/false-positives/{pattern_id}/restore` | 오탐 패턴 복원 |
| GET | `/api/v1/dashboard/false-positive-rate` | 오탐율 통계 조회 |
| PATCH | `/api/v1/vulnerabilities/{vuln_id}` | 취약점 상태 변경 + 패턴 옵션 (확장) |

---

## 3. 상세 스펙

### 3-1. POST /api/v1/false-positives

오탐 패턴을 등록한다. 현재 사용자의 팀에 패턴이 생성된다.

**인증**: Bearer JWT 필요

**Request Body**:
```json
{
  "semgrep_rule_id": "python.flask.security.xss",
  "file_pattern": "tests/**",
  "reason": "테스트 코드에서의 오탐"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| semgrep_rule_id | string (1~200자) | 필수 | Semgrep 룰 ID |
| file_pattern | string (max 500자) | 선택 | glob 패턴 (null이면 모든 파일) |
| reason | string | 선택 | 오탐 판단 사유 |

**Response** (201 Created):
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "team_id": "uuid",
    "semgrep_rule_id": "python.flask.security.xss",
    "file_pattern": "tests/**",
    "reason": "테스트 코드에서의 오탐",
    "is_active": true,
    "matched_count": 0,
    "last_matched_at": null,
    "created_by": "uuid",
    "source_vulnerability_id": null,
    "created_at": "2026-02-25T10:00:00Z"
  },
  "error": null
}
```

**에러 케이스**:

| 코드 | 상황 |
|------|------|
| 422 | semgrep_rule_id 누락 또는 빈 문자열 |
| 403 | 팀에 소속되지 않은 사용자 |

---

### 3-2. GET /api/v1/false-positives

팀의 오탐 패턴 목록을 조회한다.

**인증**: Bearer JWT 필요

**Response** (200 OK):
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "team_id": "uuid",
      "semgrep_rule_id": "python.flask.security.xss",
      "file_pattern": "tests/**",
      "reason": "테스트 코드 오탐",
      "is_active": true,
      "matched_count": 5,
      "last_matched_at": "2026-02-25T12:00:00Z",
      "created_by": "uuid",
      "source_vulnerability_id": null,
      "created_at": "2026-02-25T10:00:00Z"
    }
  ],
  "error": null
}
```

팀에 소속되지 않은 사용자는 빈 목록을 반환한다.

---

### 3-3. DELETE /api/v1/false-positives/{pattern_id}

오탐 패턴을 비활성화한다 (소프트 삭제). is_active=False로 변경.

**인증**: Bearer JWT 필요

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "is_active": false,
    ...
  },
  "error": null
}
```

**에러 케이스**:

| 코드 | 상황 |
|------|------|
| 403 | 팀에 소속되지 않은 사용자 |
| 404 | 패턴을 찾을 수 없음 |

---

### 3-4. PUT /api/v1/false-positives/{pattern_id}/restore

비활성화된 오탐 패턴을 복원한다. is_active=True로 변경.
이미 활성인 패턴은 상태 변경 없이 그대로 반환 (멱등).

**인증**: Bearer JWT 필요

**Response** (200 OK): DELETE와 동일한 구조, is_active=true

**에러 케이스**:

| 코드 | 상황 |
|------|------|
| 403 | 팀에 소속되지 않은 사용자 |
| 404 | 패턴을 찾을 수 없음 |

---

### 3-5. GET /api/v1/dashboard/false-positive-rate

오탐율 통계를 조회한다.

**인증**: Bearer JWT 필요

**Query Parameters**:

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| days | int | 30 | 조회 기간 (최대 90일로 클램핑) |

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "current_fp_rate": 25.5,
    "previous_fp_rate": 32.0,
    "improvement": 6.5,
    "total_scanned": 200,
    "total_true_positives": 149,
    "total_false_positives": 51,
    "total_auto_filtered": 30,
    "trend": [
      {
        "date": "2026-02-20",
        "fp_rate": 30.0,
        "auto_filtered_count": 3
      }
    ],
    "top_fp_rules": []
  },
  "error": null
}
```

스캔 기록이 없으면 current_fp_rate=0.0, trend=[] 반환.

**에러 케이스**:

| 코드 | 상황 |
|------|------|
| 401 | 인증 없음 |

---

### 3-6. PATCH /api/v1/vulnerabilities/{vuln_id} (F-06 확장)

취약점 상태 변경 시 오탐 패턴 자동 생성 옵션을 추가한다.

**Request Body** (확장):
```json
{
  "status": "false_positive",
  "reason": "테스트 코드 오탐",
  "create_pattern": true,
  "file_pattern": "tests/**",
  "pattern_reason": "테스트 코드의 하드코딩 값은 실제 크리덴셜이 아님"
}
```

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| create_pattern | bool | false | 오탐 패턴 등록 여부 |
| file_pattern | string | null | 패턴 glob (null이면 파일 경로에서 자동 추론) |
| pattern_reason | string | null | 패턴 등록 사유 |

**동작**:
- `create_pattern=true` + `status="false_positive"` 조건에서만 패턴 생성
- `file_pattern` 미지정 시 취약점 파일 경로의 부모 디렉토리로 자동 추론 (예: `tests/unit/**`)
- 동일 패턴 이미 존재 시 기존 패턴 재활용 (중복 INSERT 없음)
- `create_pattern=false` 또는 status가 false_positive가 아니면 기존 동작 유지

---

## 4. 서비스 레이어

### FPFilterService (`src/services/fp_filter_service.py`)

| 메서드 | 설명 |
|--------|------|
| `filter(findings, team_id)` | 오탐 패턴과 일치하는 findings를 제거하고 나머지 반환 |
| `filter_findings(findings, team_id, scan_job_id)` | 필터링 + FalsePositiveLog 기록 + matched_count 갱신 |
| `_matches(finding, pattern)` | finding이 패턴과 일치하는지 판단 (rule_id + fnmatch) |

### calculate_fp_rate (`src/services/fp_filter_service.py`)

```python
def calculate_fp_rate(true_positives: int, false_positives: int) -> float
```

오탐율 계산. total=0이면 0.0 반환.

---

## 5. 구현 파일 목록

| 파일 | 역할 |
|------|------|
| `src/models/false_positive.py` | FalsePositivePattern, FalsePositiveLog 모델 |
| `src/schemas/false_positive.py` | 요청/응답 스키마 |
| `src/api/v1/false_positives.py` | CRUD 엔드포인트 |
| `src/services/fp_filter_service.py` | 패턴 매칭/필터링 서비스 |
| `src/api/v1/router.py` | false-positives 라우터 등록 |
| `src/api/v1/dashboard.py` | false-positive-rate 엔드포인트 추가 |
| `src/api/v1/vulns.py` | create_pattern 옵션 추가 |
| `src/schemas/vulnerability.py` | VulnerabilityStatusUpdateRequest 확장 |
| `alembic/versions/003_add_f06_tables.py` | DB 마이그레이션 |
| `tests/services/test_fp_filter_service.py` | 서비스 단위 테스트 (17개) |
| `tests/api/test_fp_api.py` | API 통합 테스트 (21개) |
