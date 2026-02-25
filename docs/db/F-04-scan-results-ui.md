# F-04: 스캔 결과 API — DB 스키마 확정본

**버전**: v1.0
**작성일**: 2026-02-25
**상태**: 확정 (GREEN 달성)

---

## 개요

F-04는 기존 DB 테이블 스키마 변경이 없다. `scan_job`, `vulnerability`, `repository`, `team_member` 테이블을 읽기 위주로 활용하며, 취약점 상태 변경(PATCH) 시 `vulnerability.status`, `vulnerability.resolved_at`, `repository.security_score` 컬럼만 업데이트한다.

---

## 조회 대상 테이블

### 테이블: `scan_job`

F-04에서 조회하는 스캔 작업 테이블.

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `repo_id` | UUID | NOT NULL | - | FK -> repository.id |
| `status` | VARCHAR(20) | NOT NULL | 'queued' | queued/running/completed/failed |
| `trigger_type` | VARCHAR(20) | NOT NULL | - | webhook/manual/schedule |
| `commit_sha` | VARCHAR(40) | NULL | - | 대상 커밋 SHA |
| `branch` | VARCHAR(255) | NULL | - | 대상 브랜치 |
| `pr_number` | INTEGER | NULL | - | PR 번호 |
| `scan_type` | VARCHAR(20) | NOT NULL | 'incremental' | full/incremental/pr/initial |
| `retry_count` | INTEGER | NOT NULL | 0 | 재시도 횟수 |
| `changed_files` | JSONB | NULL | - | 변경 파일 목록 |
| `findings_count` | INTEGER | NOT NULL | 0 | Semgrep 탐지 건수 |
| `true_positives_count` | INTEGER | NOT NULL | 0 | LLM 확정 취약점 건수 |
| `false_positives_count` | INTEGER | NOT NULL | 0 | 오탐 건수 |
| `duration_seconds` | INTEGER | NULL | - | 스캔 소요 시간 (초) |
| `error_message` | TEXT | NULL | - | 실패 메시지 |
| `started_at` | TIMESTAMPTZ | NULL | - | 스캔 시작 시각 |
| `completed_at` | TIMESTAMPTZ | NULL | - | 스캔 완료 시각 |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 생성 시각 |
| `updated_at` | TIMESTAMPTZ | NOT NULL | now() | 수정 시각 |

#### F-04에서 활용되는 인덱스

```sql
-- 저장소별 스캔 목록 조회 (created_at DESC)
CREATE INDEX idx_scan_job_repo_status ON scan_job(repo_id, status);
CREATE INDEX idx_scan_job_created ON scan_job(created_at DESC);
```

---

### 테이블: `vulnerability`

F-04에서 조회 및 상태 업데이트를 수행하는 취약점 테이블.

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `scan_job_id` | UUID | NOT NULL | - | FK -> scan_job.id (CASCADE DELETE) |
| `repo_id` | UUID | NOT NULL | - | FK -> repository.id (CASCADE DELETE) |
| `status` | VARCHAR(20) | NOT NULL | 'open' | open/patched/ignored/false_positive |
| `severity` | VARCHAR(20) | NOT NULL | - | critical/high/medium/low |
| `vulnerability_type` | VARCHAR(100) | NOT NULL | - | sql_injection/xss/... |
| `cwe_id` | VARCHAR(20) | NULL | - | CWE-89 등 |
| `owasp_category` | VARCHAR(50) | NULL | - | A03:2021 - Injection 등 |
| `file_path` | VARCHAR(500) | NOT NULL | - | 취약 파일 경로 |
| `start_line` | INTEGER | NOT NULL | - | 취약 코드 시작 라인 |
| `end_line` | INTEGER | NOT NULL | - | 취약 코드 끝 라인 |
| `code_snippet` | TEXT | NULL | - | 취약 코드 조각 |
| `description` | TEXT | NULL | - | 취약점 설명 |
| `llm_reasoning` | TEXT | NULL | - | LLM 분석 근거 |
| `llm_confidence` | NUMERIC(3,2) | NULL | - | LLM 확신도 (0.00~1.00) |
| `semgrep_rule_id` | VARCHAR(255) | NULL | - | Semgrep 룰 ID |
| `references` | JSONB | NULL | - | 참고 링크 목록 |
| `detected_at` | TIMESTAMPTZ | NULL | - | 최초 탐지 시각 |
| `resolved_at` | TIMESTAMPTZ | NULL | - | **해결 시각 (F-04 PATCH에서 자동 설정)** |
| `manual_guide` | TEXT | NULL | - | 수동 수정 가이드 |
| `manual_priority` | VARCHAR(10) | NULL | - | P0/P1/P2/P3 |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 생성 시각 |
| `updated_at` | TIMESTAMPTZ | NOT NULL | now() | 수정 시각 |

#### F-04에서 활용되는 인덱스

```sql
-- 저장소별 상태 조회 (목록 필터링, 대시보드)
CREATE INDEX idx_vulnerability_repo_status ON vulnerability(repo_id, status);

-- 심각도별 필터링
CREATE INDEX idx_vulnerability_severity ON vulnerability(severity);

-- 스캔 작업 ID 조회
CREATE INDEX idx_vulnerability_scan_job_id ON vulnerability(scan_job_id);
```

---

### 테이블: `repository`

F-04에서 저장소 정보 조회 및 보안 점수 업데이트에 사용.

#### F-04에서 읽는 컬럼

| 컬럼 | 설명 |
|------|------|
| `id` | 저장소 ID (취약점/스캔 접근 권한 확인) |
| `team_id` | 팀 ID (권한 확인 조인 대상) |
| `full_name` | 저장소 전체 이름 (응답에 포함: repo_full_name) |
| `security_score` | 보안 점수 (취약점 상태 변경 후 재계산) |

#### F-04에서 업데이트하는 컬럼

| 컬럼 | 업데이트 시점 | 로직 |
|------|-------------|------|
| `security_score` | PATCH /vulnerabilities/{vuln_id} 완료 후 | 동기 재계산 (ADR-F04-003) |

#### 보안 점수 계산 공식

```
weights = { critical: 10, high: 5, medium: 2, low: 1 }

total_weighted = sum(weights[v.severity] for v in all_vulns)
open_weighted  = sum(weights[v.severity] for v in all_vulns if v.status == "open")

score = (1 - open_weighted / total_weighted) * 100
score = max(0.0, min(100.0, score))  # 0~100 클램핑

# 취약점 0건 시
if total_weighted == 0: score = 100.0
```

---

### 테이블: `team_member`

접근 권한 확인에만 사용 (읽기 전용).

#### F-04에서 읽는 컬럼

| 컬럼 | 설명 |
|------|------|
| `user_id` | 현재 사용자 ID |
| `team_id` | 팀 ID |
| `role` | 역할 (owner/member/viewer) |

---

## F-04 쿼리 패턴

### 1. 스캔 작업 조회 (GET /scans/{scan_id})

```sql
SELECT * FROM scan_job WHERE id = :scan_id;
SELECT team_id FROM repository WHERE id = :repo_id;
SELECT 1 FROM team_member WHERE user_id = :user_id AND team_id = :team_id;
```

### 2. 취약점 목록 조회 (GET /vulnerabilities)

```sql
-- 팀 소속 저장소 ID 목록
SELECT team_id FROM team_member WHERE user_id = :user_id;
SELECT id FROM repository WHERE team_id IN (:team_ids);

-- 취약점 목록 (인덱스: idx_vulnerability_repo_status)
SELECT id, status, severity, vulnerability_type, file_path, start_line, detected_at, created_at
FROM vulnerability
WHERE repo_id IN (:repo_ids)
  [AND status = :status]
  [AND severity = :severity]
ORDER BY detected_at DESC
LIMIT :per_page OFFSET :offset;
```

### 3. 취약점 상세 조회 (GET /vulnerabilities/{vuln_id})

```sql
SELECT * FROM vulnerability WHERE id = :vuln_id;
SELECT full_name, team_id FROM repository WHERE id = :repo_id;
SELECT 1 FROM team_member WHERE user_id = :user_id AND team_id = :team_id;
-- patch_pr은 SQLAlchemy relationship으로 lazy load (또는 필요 시 selectinload)
```

### 4. 취약점 상태 변경 (PATCH /vulnerabilities/{vuln_id})

```sql
-- 상태 변경
UPDATE vulnerability
SET status = :new_status, resolved_at = :resolved_at
WHERE id = :vuln_id;

-- 보안 점수 재계산용 전체 조회
SELECT severity, status FROM vulnerability WHERE repo_id = :repo_id;

-- 점수 업데이트
UPDATE repository SET security_score = :new_score WHERE id = :repo_id;
```

### 5. 대시보드 요약 (GET /dashboard/summary)

```sql
-- 저장소 목록
SELECT * FROM repository WHERE team_id IN (:team_ids);

-- 취약점 전체 (집계를 Python 레벨에서 수행)
SELECT severity, status FROM vulnerability WHERE repo_id IN (:repo_ids);

-- 최근 스캔 5건
SELECT * FROM scan_job
WHERE repo_id IN (:repo_ids)
ORDER BY created_at DESC
LIMIT 5;
```

### 6. 취약점 추이 (GET /dashboard/trend)

```sql
SELECT detected_at, resolved_at, repo_id
FROM vulnerability
WHERE repo_id IN (:repo_ids)
  AND detected_at >= :start_dt;
```

---

## 상태 전이 다이어그램

```
취약점 상태 (vulnerability.status):

      ┌──────────────────────────────────────┐
      ▼                                      │
   open ──────────► patched                  │
      │                                      │
      ├──────────► ignored           (모두 open으로 복원 가능)
      │
      └──────────► false_positive
```

### resolved_at 자동 설정 규칙

| 상태 변경 | resolved_at |
|----------|------------|
| open → patched | `datetime.now(UTC)` |
| open → ignored | `datetime.now(UTC)` |
| open → false_positive | `datetime.now(UTC)` |
| any → open (복원) | `None` |

---

## 마이그레이션

F-04는 신규 마이그레이션 파일이 없다. 기존 테이블 스키마를 그대로 활용하며, `vulnerability.resolved_at` 컬럼은 F-02에서 이미 생성되어 있다.

---

## 변경 이력

| 날짜 | 변경 내용 |
|------|-----------|
| 2026-02-25 | 초안 작성 (F-04 GREEN 달성, 기존 스키마 활용 확인) |
