# F-06 오탐 관리 DB 스키마 확정본

**버전**: v1.0
**작성일**: 2026-02-25
**상태**: 구현 완료 (GREEN)

---

## 1. 신규 테이블: false_positive_pattern

오탐 패턴을 팀 단위로 저장하는 테이블.

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|----------|------|
| id | UUID | PK, default uuid4 | 기본 키 |
| team_id | UUID | NOT NULL, INDEX | 소속 팀 ID |
| semgrep_rule_id | VARCHAR(200) | NOT NULL | 대상 Semgrep 룰 ID |
| file_pattern | VARCHAR(500) | NULL | glob 패턴 (null이면 모든 파일) |
| reason | TEXT | NULL | 오탐 판단 사유 |
| is_active | BOOLEAN | NOT NULL, default true | 활성 여부 (소프트 삭제용) |
| matched_count | INTEGER | NOT NULL, default 0 | 자동 필터링된 횟수 |
| last_matched_at | TIMESTAMPTZ | NULL | 마지막 매칭 시각 |
| created_by | UUID | NULL | 패턴 등록자 ID |
| source_vulnerability_id | UUID | FK -> vulnerability.id ON DELETE SET NULL, NULL | 원본 취약점 ID |
| created_at | TIMESTAMPTZ | NOT NULL, server_default now() | 생성 시각 |
| updated_at | TIMESTAMPTZ | NOT NULL, server_default now() | 수정 시각 |

**인덱스**:
```sql
CREATE INDEX idx_fp_pattern_team_active ON false_positive_pattern(team_id, is_active);
CREATE INDEX idx_fp_pattern_rule_id ON false_positive_pattern(semgrep_rule_id);
```

---

## 2. 신규 테이블: false_positive_log

오탐 자동 필터링 이력을 기록하는 테이블.
"오탐 피드백이 탐지 엔진 정확도 향상에 반영됨을 확인" 인수조건 충족 목적.

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|----------|------|
| id | UUID | PK, default uuid4 | 기본 키 |
| pattern_id | UUID | FK -> false_positive_pattern.id ON DELETE CASCADE, NOT NULL, INDEX | 매칭된 패턴 |
| scan_job_id | UUID | FK -> scan_job.id ON DELETE CASCADE, NOT NULL, INDEX | 스캔 작업 |
| semgrep_rule_id | VARCHAR(255) | NOT NULL | 필터링된 Semgrep 룰 ID |
| file_path | VARCHAR(500) | NOT NULL | 필터링된 파일 경로 |
| start_line | INTEGER | NOT NULL | 필터링된 코드 시작 라인 |
| filtered_at | TIMESTAMPTZ | NOT NULL, server_default now() | 필터링 시각 |

**인덱스**:
```sql
CREATE INDEX idx_fp_log_pattern ON false_positive_log(pattern_id);
CREATE INDEX idx_fp_log_scan ON false_positive_log(scan_job_id);
CREATE INDEX idx_fp_log_filtered_at ON false_positive_log(filtered_at DESC);
```

---

## 3. 기존 테이블 변경: scan_job

| 신규 컬럼 | 타입 | 기본값 | 설명 |
|-----------|------|--------|------|
| auto_filtered_count | INTEGER | 0 | 오탐 패턴으로 자동 필터링된 건수 |

---

## 4. 기존 테이블 변경: vulnerability (스키마 변경 없음)

VulnerabilityStatusUpdateRequest에 create_pattern, file_pattern, pattern_reason 필드가 추가되었으나
DB 컬럼 변경은 없다. 기존 `semgrep_rule_id` 및 `file_path` 컬럼을 패턴 생성 시 활용한다.

---

## 5. 마이그레이션

**파일**: `alembic/versions/003_add_f06_tables.py`

- Revision: `003_add_f06_tables`
- down_revision: `002_add_f03_columns`

**upgrade 내용**:
1. `false_positive_pattern` 테이블 생성
2. `false_positive_log` 테이블 생성
3. `scan_job.auto_filtered_count` 컬럼 추가
4. 인덱스 생성 (5개)

**downgrade 내용**:
1. `scan_job.auto_filtered_count` 컬럼 삭제
2. `false_positive_log` 테이블 삭제
3. `false_positive_pattern` 테이블 삭제

---

## 6. ERD (관계)

```
team
 └──< false_positive_pattern >──── vulnerability (source_vulnerability_id, optional)
                └──< false_positive_log >──── scan_job

scan_job
 └──< false_positive_log
```

- team : false_positive_pattern = 1 : N (team_id 기반, FK 없이 애플리케이션 레벨 관리)
- false_positive_pattern : false_positive_log = 1 : N (CASCADE DELETE)
- scan_job : false_positive_log = 1 : N (CASCADE DELETE)
- vulnerability : false_positive_pattern = 1 : N (SET NULL on DELETE, optional)
