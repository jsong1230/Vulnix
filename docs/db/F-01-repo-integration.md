# F-01: 저장소 연동 및 스캔 트리거 — DB 스키마 확정본

작성일: 2026-02-25

---

## 1. repository 테이블 변경

### 추가 컬럼

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| is_initial_scan_done | BOOLEAN | NOT NULL | false | 초기 전체 스캔 완료 여부 |

### 마이그레이션

```sql
ALTER TABLE repository
  ADD COLUMN is_initial_scan_done BOOLEAN NOT NULL DEFAULT false;

CREATE INDEX idx_repository_installation
  ON repository(installation_id);
```

### 전체 스키마 (변경 후)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID | PK |
| team_id | UUID | FK (team.id, CASCADE) |
| github_repo_id | BIGINT | GitHub 저장소 ID (UNIQUE) |
| full_name | VARCHAR(255) | 저장소 전체 이름 |
| default_branch | VARCHAR(255) | 기본 브랜치 이름 |
| language | VARCHAR(50) | 주 프로그래밍 언어 |
| is_active | BOOLEAN | 스캔 활성화 여부 |
| installation_id | BIGINT | GitHub App 설치 ID |
| webhook_secret | TEXT | Webhook 서명 검증 시크릿 |
| last_scanned_at | TIMESTAMPTZ | 마지막 스캔 완료 시각 |
| security_score | NUMERIC(5,2) | 보안 점수 |
| **is_initial_scan_done** | **BOOLEAN** | **초기 전체 스캔 완료 여부 (신규)** |
| created_at | TIMESTAMPTZ | 생성 시각 |
| updated_at | TIMESTAMPTZ | 수정 시각 |

---

## 2. scan_job 테이블 변경

### 추가 컬럼

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| scan_type | VARCHAR(20) | NOT NULL | 'incremental' | 스캔 유형 |
| retry_count | INTEGER | NOT NULL | 0 | 현재 재시도 횟수 |
| changed_files | JSONB | NULL | null | 변경된 파일 목록 |

### 마이그레이션

```sql
ALTER TABLE scan_job
  ADD COLUMN scan_type VARCHAR(20) NOT NULL DEFAULT 'incremental';

ALTER TABLE scan_job
  ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE scan_job
  ADD COLUMN changed_files JSONB;

CREATE INDEX idx_scan_job_repo_active
  ON scan_job(repo_id)
  WHERE status IN ('queued', 'running');
```

### scan_type 열거값

| 값 | 설명 |
|----|------|
| initial | 첫 연동 후 전체 코드베이스 스캔 |
| incremental | push 이벤트 기반 변경 파일 스캔 |
| pr | PR 이벤트 기반 변경 파일 스캔 |
| full | 수동 전체 스캔 |

### 전체 스키마 (변경 후)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID | PK |
| repo_id | UUID | FK (repository.id, CASCADE) |
| status | VARCHAR(20) | queued / running / completed / failed / cancelled |
| trigger_type | VARCHAR(20) | webhook / manual / schedule |
| commit_sha | VARCHAR(40) | 대상 커밋 SHA |
| branch | VARCHAR(255) | 대상 브랜치 |
| pr_number | INTEGER | PR 번호 |
| **scan_type** | **VARCHAR(20)** | **스캔 유형 (신규)** |
| **retry_count** | **INTEGER** | **현재 재시도 횟수 (신규)** |
| **changed_files** | **JSONB** | **변경된 파일 목록 (신규)** |
| findings_count | INTEGER | Semgrep 탐지 건수 |
| true_positives_count | INTEGER | 실제 취약점 건수 |
| false_positives_count | INTEGER | 오탐 건수 |
| duration_seconds | INTEGER | 스캔 소요 시간 |
| error_message | TEXT | 실패 시 에러 메시지 |
| started_at | TIMESTAMPTZ | 스캔 시작 시각 |
| completed_at | TIMESTAMPTZ | 스캔 완료 시각 |
| created_at | TIMESTAMPTZ | 생성 시각 |
| updated_at | TIMESTAMPTZ | 수정 시각 |

---

## 3. 인덱스 요약

| 인덱스명 | 테이블 | 컬럼 | 유형 | 목적 |
|----------|--------|------|------|------|
| idx_repository_installation | repository | installation_id | B-tree | installation_id로 저장소 빠른 조회 |
| idx_scan_job_repo_active | scan_job | repo_id | 부분 인덱스 (status IN queued,running) | 진행 중 스캔 중복 방지 조회 최적화 |
