# F-06 오탐 관리 -- 기술 설계서

**버전**: v1.0
**작성일**: 2026-02-25
**상태**: 설계 완료

---

## 1. 참조

- 인수조건: docs/project/features.md #F-06
- 시스템 설계: docs/system/system-design.md
- 의존 기능: F-04 (스캔 결과 API 및 기본 UI)

---

## 2. 아키텍처 결정

### ADR-F06-001: 오탐 패턴 저장 방식

- **선택지**:
  A) Vulnerability 테이블에 is_false_positive 플래그만 추가하고 패턴 학습 없음
  B) 별도 FalsePositivePattern 테이블로 패턴을 추출하여 저장하고 스캔 시 자동 필터링
  C) LLM에 오탐 피드백을 fine-tuning 데이터로 활용

- **결정**: B) 별도 FalsePositivePattern 테이블
- **근거**:
  - 기존 Vulnerability.status = "false_positive" 마킹은 이미 구현되어 있으므로 이를 활용
  - 패턴 테이블을 별도로 두면 팀 단위 규칙 공유가 자연스러움 (team_id FK)
  - 스캔 파이프라인에서 패턴 매칭 후 자동 제외가 가능 (scan_worker.py에 필터 단계 삽입)
  - C) fine-tuning은 비용이 높고 PoC 단계에 부적합. 향후 데이터 축적 후 검토

### ADR-F06-002: 패턴 매칭 전략

- **선택지**:
  A) semgrep_rule_id 정확 일치만
  B) semgrep_rule_id + file_pattern (glob) 복합 매칭
  C) semgrep_rule_id + file_pattern + code_snippet 해시 매칭

- **결정**: B) semgrep_rule_id + file_pattern 복합 매칭
- **근거**:
  - rule_id만으로는 너무 광범위하여 실제 취약점까지 제외할 위험
  - file_pattern (glob, 예: `tests/**`, `**/migrations/*`)으로 테스트 코드/마이그레이션 등 특정 경로에 한정하여 오탐 룰을 적용할 수 있음
  - code_snippet 해시는 코드 변경에 너무 민감하여 실용성이 낮음
  - file_pattern이 null이면 모든 파일에 대해 해당 rule_id 매칭 (광범위 규칙)

### ADR-F06-003: 오탐 패턴 생성 시점

- **선택지**:
  A) 취약점 상태를 false_positive로 변경할 때 자동 생성 (옵트아웃)
  B) 취약점 상태를 false_positive로 변경한 후 별도 API로 패턴 등록 (옵트인)
  C) 상태 변경 시 "패턴으로 등록" 옵션을 함께 전달 (옵트인, 단일 요청)

- **결정**: C) 상태 변경 시 옵트인 옵션
- **근거**:
  - 모든 오탐이 패턴으로 등록될 필요는 없음 (일회성 오탐 vs 반복적 오탐)
  - 상태 변경 API(PATCH /vulnerabilities/{id})에 `create_pattern: bool` 필드를 추가하여 단일 요청으로 처리
  - 별도 API(POST /false-positives)도 함께 제공하여 수동 패턴 등록도 지원

### ADR-F06-004: 스캔 파이프라인 내 필터링 위치

- **선택지**:
  A) Semgrep 1차 결과 직후, LLM 호출 전에 필터링
  B) LLM 2차 분석 결과 이후, DB 저장 전에 필터링
  C) LLM 프롬프트에 오탐 패턴 정보를 컨텍스트로 주입

- **결정**: A) Semgrep 결과 직후 필터링
- **근거**:
  - LLM 호출 자체를 줄여 비용 절감 (ADR-001의 비용 절감 전략과 일치)
  - Semgrep finding의 rule_id와 file_path를 패턴과 대조하여 빠르게 필터링 가능
  - 필터링된 항목도 로그로 기록하여 추적 가능

### ADR-F06-005: 오탐율 계산 방식

- **선택지**:
  A) ScanJob 단위: false_positives_count / (true_positives_count + false_positives_count)
  B) 누적: 전체 기간 Vulnerability 테이블에서 status="false_positive" 비율 계산
  C) ScanJob 단위(A) + 누적(B) 둘 다 제공

- **결정**: C) 둘 다 제공
- **근거**:
  - ScanJob 단위 오탐율은 이미 ScanJob 테이블에 true_positives_count, false_positives_count가 존재
  - 누적 오탐율은 대시보드에서 전체 시스템 정확도 추이를 보여주는 데 필수
  - F-07 대시보드와 연계하여 오탐율 트렌드 그래프 제공 가능

---

## 3. API 설계

### 3-1. PATCH /api/v1/vulnerabilities/{vuln_id} (기존 API 확장)

- **목적**: 취약점 상태 변경 시 오탐 패턴 자동 생성 옵션 추가
- **인증**: Bearer JWT 필요
- **변경 사항**: VulnerabilityStatusUpdateRequest에 `create_pattern`, `file_pattern`, `pattern_reason` 필드 추가

**Request Body** (확장):
```json
{
  "status": "false_positive",
  "reason": "테스트 코드에서의 오탐",
  "create_pattern": true,
  "file_pattern": "tests/**",
  "pattern_reason": "테스트 코드의 하드코딩 값은 실제 크리덴셜이 아님"
}
```

**Response**: 기존 VulnerabilityResponse와 동일

**동작**:
- `create_pattern=true`이고 `status="false_positive"`인 경우:
  - 해당 취약점의 `semgrep_rule_id`와 `file_pattern`으로 FalsePositivePattern 레코드 생성
  - `file_pattern`이 생략되면 해당 취약점의 `file_path`에서 자동 추론 (디렉토리 패턴)
- `create_pattern=false`이거나 생략된 경우: 기존 동작 유지

### 3-2. POST /api/v1/false-positives

- **목적**: 오탐 패턴 수동 등록
- **인증**: Bearer JWT 필요 (팀 admin/owner만)

**Request Body**:
```json
{
  "team_id": "uuid",
  "semgrep_rule_id": "python.flask.security.xss",
  "file_pattern": "tests/**",
  "vulnerability_type": "xss",
  "reason": "테스트 코드에서 XSS 룰은 오탐으로 처리"
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "team_id": "uuid",
    "semgrep_rule_id": "python.flask.security.xss",
    "file_pattern": "tests/**",
    "vulnerability_type": "xss",
    "reason": "테스트 코드에서 XSS 룰은 오탐으로 처리",
    "is_active": true,
    "created_by": "uuid",
    "created_at": "2026-02-25T10:00:00Z",
    "matched_count": 0,
    "last_matched_at": null
  },
  "error": null
}
```

**에러 케이스**:

| 코드 | 상황 |
|------|------|
| 400 | semgrep_rule_id 누락 |
| 403 | 팀 admin/owner 권한 없음 |
| 404 | team_id에 해당하는 팀 없음 |
| 409 | 동일 team_id + semgrep_rule_id + file_pattern 조합이 이미 존재 |

### 3-3. GET /api/v1/false-positives

- **목적**: 팀별 오탐 패턴 목록 조회
- **인증**: Bearer JWT 필요

**Query Parameters**:

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| team_id | UUID | 선택 | 특정 팀 필터 (생략 시 사용자 소속 전체 팀) |
| is_active | bool | 선택 | 활성 상태 필터 (기본: true) |
| page | int | 선택 | 페이지 번호 (기본: 1) |
| per_page | int | 선택 | 페이지당 항목 수 (기본: 20, 최대: 100) |

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "team_id": "uuid",
      "semgrep_rule_id": "python.flask.security.xss",
      "file_pattern": "tests/**",
      "vulnerability_type": "xss",
      "reason": "테스트 코드 오탐",
      "is_active": true,
      "created_by": "uuid",
      "created_by_name": "user-login",
      "created_at": "2026-02-25T10:00:00Z",
      "matched_count": 15,
      "last_matched_at": "2026-02-25T12:00:00Z"
    }
  ],
  "error": null,
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 5,
    "total_pages": 1
  }
}
```

### 3-4. DELETE /api/v1/false-positives/{pattern_id}

- **목적**: 오탐 패턴 삭제 (비활성화)
- **인증**: Bearer JWT 필요 (팀 admin/owner만)
- **동작**: 물리 삭제가 아닌 `is_active=false`로 소프트 삭제
- **Response**: `{ "success": true, "data": null, "error": null }`

**에러 케이스**:

| 코드 | 상황 |
|------|------|
| 403 | 팀 admin/owner 권한 없음 |
| 404 | 패턴을 찾을 수 없음 |

### 3-5. PUT /api/v1/false-positives/{pattern_id}/restore

- **목적**: 비활성화된 오탐 패턴 복원 (is_active=true)
- **인증**: Bearer JWT 필요 (팀 admin/owner만)
- **Response**: 복원된 패턴 데이터

### 3-6. GET /api/v1/dashboard/false-positive-rate

- **목적**: 오탐율 트래킹 통계 조회
- **인증**: Bearer JWT 필요

**Query Parameters**:

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| days | int | 선택 | 조회 기간 (기본: 30, 최대: 90) |
| repo_id | UUID | 선택 | 특정 저장소 필터 |

**Response**:
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
    "top_fp_rules": [
      {
        "semgrep_rule_id": "generic.secrets.hardcoded-credentials",
        "fp_count": 20,
        "pattern_exists": true
      }
    ]
  },
  "error": null
}
```

---

## 4. DB 설계

### 4-1. 새 테이블: false_positive_pattern

| 컬럼 | 타입 | 제약조건 | 설명 |
|-------|------|----------|------|
| id | UUID | PK, default uuid4 | 기본 키 |
| team_id | UUID | FK -> team.id, NOT NULL, INDEX | 소속 팀 (팀 단위 공유) |
| semgrep_rule_id | VARCHAR(255) | NOT NULL, INDEX | 대상 Semgrep 룰 ID |
| file_pattern | VARCHAR(500) | NULL | glob 패턴 (null이면 모든 파일 대상) |
| vulnerability_type | VARCHAR(100) | NULL | 취약점 유형 (보조 필터) |
| reason | TEXT | NOT NULL | 오탐으로 판단한 사유 |
| is_active | BOOLEAN | NOT NULL, default true | 활성 여부 (소프트 삭제용) |
| created_by | UUID | FK -> user.id, NOT NULL | 패턴 등록자 |
| source_vulnerability_id | UUID | FK -> vulnerability.id, NULL | 원본 취약점 ID (상태 변경으로 생성된 경우) |
| matched_count | INTEGER | NOT NULL, default 0 | 이 패턴으로 자동 필터링된 횟수 |
| last_matched_at | TIMESTAMPTZ | NULL | 마지막 매칭 시각 |
| created_at | TIMESTAMPTZ | NOT NULL, server_default now() | 생성 시각 |
| updated_at | TIMESTAMPTZ | NOT NULL, server_default now(), onupdate now() | 수정 시각 |

**제약조건**:
- UNIQUE(team_id, semgrep_rule_id, file_pattern) -- 동일 팀에서 동일 룰+패턴 중복 방지
  - file_pattern이 NULL인 경우를 위해 COALESCE 또는 partial unique index 사용

### 4-2. 새 테이블: false_positive_log

| 컬럼 | 타입 | 제약조건 | 설명 |
|-------|------|----------|------|
| id | UUID | PK, default uuid4 | 기본 키 |
| pattern_id | UUID | FK -> false_positive_pattern.id, NOT NULL, INDEX | 매칭된 패턴 |
| scan_job_id | UUID | FK -> scan_job.id, NOT NULL, INDEX | 스캔 작업 |
| semgrep_rule_id | VARCHAR(255) | NOT NULL | 필터링된 Semgrep 룰 ID |
| file_path | VARCHAR(500) | NOT NULL | 필터링된 파일 경로 |
| start_line | INTEGER | NOT NULL | 필터링된 코드 시작 라인 |
| filtered_at | TIMESTAMPTZ | NOT NULL, server_default now() | 필터링 시각 |

**목적**: 자동 필터링 이력 추적. "오탐 피드백이 탐지 엔진 정확도 향상에 반영됨을 확인" 인수조건 충족.

### 4-3. 기존 테이블 변경: scan_job

| 변경 컬럼 | 변경 내용 | 설명 |
|-----------|-----------|------|
| auto_filtered_count | INTEGER, NOT NULL, default 0 신규 추가 | 오탐 패턴으로 자동 필터링된 건수 |

### 4-4. 인덱스 계획

```sql
-- false_positive_pattern 조회 최적화
CREATE INDEX idx_fp_pattern_team_active ON false_positive_pattern(team_id, is_active);
CREATE INDEX idx_fp_pattern_rule_id ON false_positive_pattern(semgrep_rule_id);
CREATE UNIQUE INDEX idx_fp_pattern_unique ON false_positive_pattern(team_id, semgrep_rule_id, COALESCE(file_pattern, ''))
  WHERE is_active = true;

-- false_positive_log 조회 최적화
CREATE INDEX idx_fp_log_pattern ON false_positive_log(pattern_id);
CREATE INDEX idx_fp_log_scan ON false_positive_log(scan_job_id);
CREATE INDEX idx_fp_log_filtered_at ON false_positive_log(filtered_at DESC);
```

---

## 5. 시퀀스 흐름

### 5-1. 오탐 마킹 + 패턴 등록 흐름

```
사용자          Frontend           API (vulns.py)       DB
  |                |                    |                |
  |-- "오탐" 클릭 -->|                    |                |
  |  (create_pattern |                    |                |
  |   = true 선택)   |                    |                |
  |                |-- PATCH /vulns/{id} -->|                |
  |                |   {status: "false_positive",          |
  |                |    create_pattern: true,              |
  |                |    file_pattern: "tests/**"}          |
  |                |                    |                |
  |                |                    |-- UPDATE vulnerability SET status='false_positive'
  |                |                    |                |
  |                |                    |-- INSERT false_positive_pattern
  |                |                    |   (team_id, semgrep_rule_id,
  |                |                    |    file_pattern, reason,
  |                |                    |    source_vulnerability_id)
  |                |                    |                |
  |                |                    |-- 보안 점수 재계산
  |                |                    |                |
  |                |<-- 200 OK ---------|                |
  |<-- 상태 반영 ---|                    |                |
```

### 5-2. 스캔 시 오탐 패턴 자동 필터링 흐름

```
ScanWorker       SemgrepEngine      FPFilterService      LLMAgent         DB
  |                  |                    |                  |              |
  |-- scan() ------->|                    |                  |              |
  |<-- findings[] ---|                    |                  |              |
  |                  |                    |                  |              |
  |-- filter_findings(findings, repo) --->|                  |              |
  |                  |                    |-- SELECT patterns WHERE team_id
  |                  |                    |   AND is_active = true        |
  |                  |                    |<-- patterns[] ---|--------------|
  |                  |                    |                  |              |
  |                  |                    |-- match(findings, patterns)   |
  |                  |                    |   (rule_id + file_pattern glob)|
  |                  |                    |                  |              |
  |                  |                    |-- INSERT false_positive_log   |
  |                  |                    |   (필터링 이력)                 |
  |                  |                    |                  |              |
  |                  |                    |-- UPDATE pattern SET           |
  |                  |                    |   matched_count += N,          |
  |                  |                    |   last_matched_at = now()      |
  |                  |                    |                  |              |
  |<-- filtered_findings[], auto_filtered_count ------------|              |
  |                  |                    |                  |              |
  |-- analyze(filtered_findings) --------|----------------->|              |
  |                  |                    |                  |              |
```

### 5-3. 오탐율 대시보드 조회 흐름

```
사용자          Frontend           API (dashboard.py)     DB
  |                |                    |                   |
  |-- 대시보드 열기 -->|                    |                   |
  |                |-- GET /dashboard/false-positive-rate -->|
  |                |                    |                   |
  |                |                    |-- SELECT scan_jobs (기간 내)
  |                |                    |   SUM(true_positives_count),
  |                |                    |   SUM(false_positives_count),
  |                |                    |   SUM(auto_filtered_count)
  |                |                    |                   |
  |                |                    |-- 일별 그룹핑 + 오탐율 계산
  |                |                    |                   |
  |                |                    |-- 오탐 빈도 상위 룰 집계
  |                |                    |                   |
  |                |<-- 오탐율 데이터 ---|                   |
  |<-- 차트 렌더링 --|                    |                   |
```

---

## 6. 영향 범위

### 수정 필요 파일

**Backend**:

| 파일 | 변경 내용 |
|------|-----------|
| `backend/src/models/vulnerability.py` | 변경 없음 (기존 status="false_positive" 활용) |
| `backend/src/models/scan_job.py` | `auto_filtered_count` 컬럼 추가 |
| `backend/src/schemas/vulnerability.py` | `VulnerabilityStatusUpdateRequest`에 `create_pattern`, `file_pattern`, `pattern_reason` 필드 추가 |
| `backend/src/api/v1/vulns.py` | `update_vulnerability_status` 엔드포인트에 패턴 자동 생성 로직 추가 |
| `backend/src/api/v1/router.py` | `false_positives` 라우터 등록 |
| `backend/src/api/v1/dashboard.py` | `get_false_positive_rate` 엔드포인트 추가 |
| `backend/src/workers/scan_worker.py` | Semgrep 결과 후 FPFilterService 호출 단계 추가, `auto_filtered_count` 업데이트 |

**Frontend**:

| 파일 | 변경 내용 |
|------|-----------|
| `frontend/src/components/vulnerability/status-actions.tsx` | "오탐으로 표시" 버튼 클릭 시 패턴 등록 옵션 모달/체크박스 추가 |
| `frontend/src/lib/scan-api.ts` | `patchVulnerabilityStatus` 함수에 `create_pattern` 등 파라미터 추가, 오탐 패턴 CRUD API 함수 추가, 오탐율 API 함수 추가 |

### 신규 생성 파일

**Backend**:

| 파일 | 설명 |
|------|------|
| `backend/src/models/false_positive.py` | FalsePositivePattern, FalsePositiveLog 모델 |
| `backend/src/schemas/false_positive.py` | 오탐 패턴 요청/응답 스키마 |
| `backend/src/api/v1/false_positives.py` | 오탐 패턴 CRUD 엔드포인트 |
| `backend/src/services/fp_filter_service.py` | 스캔 시 오탐 패턴 매칭/필터링 서비스 |
| `backend/src/schemas/fp_rate.py` | 오탐율 관련 응답 스키마 |
| `alembic/versions/xxxx_add_false_positive_tables.py` | DB 마이그레이션 |

**Frontend**:

| 파일 | 설명 |
|------|------|
| `frontend/src/components/vulnerability/fp-pattern-dialog.tsx` | 오탐 패턴 등록 다이얼로그 |
| `frontend/src/app/settings/false-positives/page.tsx` | 오탐 규칙 관리 페이지 |
| `frontend/src/components/dashboard/fp-rate-card.tsx` | 오탐율 트래킹 카드 컴포넌트 |

---

## 7. 서비스 상세 설계

### 7-1. FPFilterService (신규)

```python
# backend/src/services/fp_filter_service.py

class FPFilterService:
    """오탐 패턴 매칭 및 Semgrep findings 필터링 서비스."""

    async def filter_findings(
        self,
        db: AsyncSession,
        repo_id: uuid.UUID,
        scan_job_id: uuid.UUID,
        findings: list[SemgrepFinding],
    ) -> tuple[list[SemgrepFinding], int]:
        """
        Semgrep findings에서 오탐 패턴과 일치하는 항목을 제외한다.

        1. repo -> team_id 조회
        2. team_id로 활성 패턴 목록 로드
        3. 각 finding에 대해 패턴 매칭 (rule_id + file_pattern glob)
        4. 매칭된 finding은 제외 + 로그 기록
        5. 패턴의 matched_count, last_matched_at 업데이트

        Returns:
            (필터링된 findings, 자동 필터링 건수)
        """

    def _matches_pattern(
        self,
        finding: SemgrepFinding,
        pattern: FalsePositivePattern,
    ) -> bool:
        """단일 finding이 패턴과 일치하는지 판단한다.

        매칭 조건 (AND):
        1. finding.rule_id == pattern.semgrep_rule_id
        2. pattern.file_pattern이 null이면 무조건 매칭
           pattern.file_pattern이 있으면 fnmatch(finding.file_path, pattern.file_pattern)
        """
```

### 7-2. scan_worker.py 변경 포인트

`_run_scan_async` 함수의 스캔 파이프라인에 4.5단계를 삽입:

```
4. Semgrep 1차 스캔 -> findings
4.5. FPFilterService.filter_findings() -> filtered_findings, auto_filtered_count  # 신규
5. findings 없으면 completed (filtered_findings 기준으로 변경)
6. LLM 2차 분석 (filtered_findings 기준으로 변경)
...
9. ScanJob 통계 업데이트 (auto_filtered_count 추가)
```

### 7-3. 오탐율 계산 로직

```python
# 스캔 단위 오탐율 (LLM 기반)
scan_fp_rate = false_positives_count / (true_positives_count + false_positives_count) * 100

# 누적 오탐율 (사용자 마킹 기반)
total_vulns = COUNT(vulnerability WHERE repo_id IN user_repos)
total_fp = COUNT(vulnerability WHERE status='false_positive' AND repo_id IN user_repos)
cumulative_fp_rate = total_fp / total_vulns * 100

# 자동 필터링 효과
auto_filter_rate = SUM(auto_filtered_count) / SUM(findings_count) * 100
```

---

## 8. 성능 설계

### 8-1. 인덱스 계획

4-4절 참조. 핵심 인덱스:
- `idx_fp_pattern_team_active`: 스캔 시 팀별 활성 패턴 조회 (가장 빈번한 쿼리)
- `idx_fp_pattern_rule_id`: rule_id 기반 패턴 존재 여부 확인
- `idx_fp_pattern_unique`: 중복 패턴 방지

### 8-2. 캐싱 전략

- 팀별 활성 패턴 목록은 스캔 워커 실행 시 1회 DB 조회 후 메모리에 캐싱
- 패턴 수가 많지 않을 것으로 예상 (팀당 수십~수백 건)
- Redis 캐시는 PoC 단계에서 불필요 (DB 직접 조회로 충분)
- 향후 팀당 패턴 1,000건 이상 시 Redis 캐시 도입 검토 (TTL 5분)

### 8-3. 성능 영향 분석

- 패턴 필터링은 O(findings x patterns) 시간 복잡도
- 실제로는 findings 20~50건, patterns 10~100건 수준이므로 1ms 미만
- LLM 호출 감소 효과로 전체 스캔 시간은 오히려 단축될 가능성 높음

---

## 변경 이력

| 날짜 | 변경 내용 | 이유 |
|------|-----------|------|
| 2026-02-25 | 초안 작성 | F-06 기능 설계 |
