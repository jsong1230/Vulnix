# F-02 취약점 탐지 엔진 — DB 스키마 확정본

**버전**: v1.0
**작성일**: 2026-02-25
**상태**: 확정

---

## 개요

F-02는 기존 `vulnerability` 테이블과 `scan_job` 테이블에 데이터를 저장합니다. 새로운 테이블은 추가되지 않습니다.

---

## 테이블: `vulnerability`

탐지된 취약점을 저장합니다. Semgrep + LLM 하이브리드 분석 결과.

### 스키마

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `scan_job_id` | UUID | NOT NULL | - | FK -> scan_job.id |
| `repo_id` | UUID | NOT NULL | - | FK -> repository.id |
| `status` | VARCHAR(20) | NOT NULL | 'open' | open/patched/ignored/false_positive |
| `severity` | VARCHAR(20) | NOT NULL | - | critical/high/medium/low/informational |
| `vulnerability_type` | VARCHAR(100) | NOT NULL | - | sql_injection/xss/hardcoded_credentials/unknown |
| `cwe_id` | VARCHAR(20) | NULL | - | CWE-89 / CWE-79 / CWE-798 |
| `owasp_category` | VARCHAR(50) | NULL | - | A03:2021 - Injection 등 |
| `file_path` | VARCHAR(500) | NOT NULL | - | 취약 파일 경로 (상대 경로) |
| `start_line` | INTEGER | NOT NULL | - | 취약 코드 시작 라인 |
| `end_line` | INTEGER | NOT NULL | - | 취약 코드 끝 라인 |
| `code_snippet` | TEXT | NULL | - | 취약 코드 조각 |
| `description` | TEXT | NULL | - | Semgrep 룰 설명 |
| `llm_reasoning` | TEXT | NULL | - | LLM 판단 근거 |
| `llm_confidence` | NUMERIC(3,2) | NULL | - | LLM 확신도 (0.00~1.00) |
| `semgrep_rule_id` | VARCHAR(255) | NULL | - | 탐지에 사용된 Semgrep 룰 ID |
| `references` | JSONB | NULL | - | 참고 링크 목록 |
| `detected_at` | TIMESTAMPTZ | NULL | - | 최초 탐지 시각 |
| `resolved_at` | TIMESTAMPTZ | NULL | - | 해결 시각 |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 생성 시각 |
| `updated_at` | TIMESTAMPTZ | NOT NULL | now() | 수정 시각 |

### 인덱스

```sql
-- 저장소별 상태 조회 (대시보드)
CREATE INDEX idx_vulnerability_repo_status ON vulnerability(repo_id, status);

-- 심각도별 조회 (필터링)
CREATE INDEX idx_vulnerability_severity ON vulnerability(severity);

-- 스캔 작업 ID 조회
CREATE INDEX idx_vulnerability_scan_job_id ON vulnerability(scan_job_id);
```

### 취약점 상태 전이

```
open -> patched     (F-03: PR 머지 시)
open -> ignored     (사용자가 수동으로 무시)
open -> false_positive  (사용자가 오탐으로 표시)
```

---

## 테이블: `scan_job` (업데이트)

F-01에서 생성된 테이블. F-02 파이프라인이 다음 컬럼을 업데이트합니다.

### F-02에서 업데이트하는 컬럼

| 컬럼 | 업데이트 시점 | 설명 |
|------|-------------|------|
| `status` | running -> completed / failed | 파이프라인 상태 |
| `findings_count` | 완료 시 | Semgrep 탐지 총 건수 |
| `true_positives_count` | 완료 시 | LLM이 진양성으로 확정한 건수 |
| `false_positives_count` | 완료 시 | LLM이 오탐으로 분류한 건수 |
| `duration_seconds` | completed 시 | 스캔 소요 시간 (ScanOrchestrator 계산) |
| `error_message` | failed 시 | 실패 에러 메시지 |
| `started_at` | running 전환 시 | ScanOrchestrator.update_job_status |
| `completed_at` | completed 전환 시 | ScanOrchestrator.update_job_status |

---

## 데이터 흐름

```
Semgrep JSON output
  -> SemgrepFinding (메모리)
  -> LLMAnalysisResult (메모리)
  -> Vulnerability (DB 저장, true_positive만)
  -> scan_job (통계 업데이트)
```

### 중복 방지 로직

`_save_vulnerabilities`에서 `finding_map`을 `rule_id` 기준으로 구성합니다:

```python
finding_map: dict[str, SemgrepFinding] = {}
for f in findings:
    if f.rule_id not in finding_map:
        finding_map[f.rule_id] = f  # 최초 등장한 finding만 사용
```

동일 `rule_id`를 가진 중복 finding이 있어도 1건만 저장됩니다.

---

## 심각도 체계

| 값 (DB) | LLM 분류 기준 |
|---------|--------------|
| `critical` | 인증 없이 원격 코드 실행 / 전체 데이터 유출 가능 |
| `high` | 사용자 데이터 유출 / 권한 상승 가능 |
| `medium` | 제한된 조건에서만 악용 가능 |
| `low` | 직접 공격은 어렵지만 보안 위생 미달 |
| `informational` | 보안 모범사례 미준수 |

Semgrep severity(ERROR/WARNING/INFO)를 LLM이 5단계로 세분화합니다.

---

## 변경 이력

| 날짜 | 변경 내용 |
|------|-----------|
| 2026-02-25 | 초안 작성 (F-02 구현 완료) |
