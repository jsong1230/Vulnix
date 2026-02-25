# F-03 자동 패치 PR 생성 — DB 스키마 확정본

> 작성일: 2026-02-25
> 마이그레이션 파일: `alembic/versions/002_add_f03_columns.py`

---

## 변경 개요

F-03 구현을 위해 기존 테이블에 컬럼을 추가하고 `patch_pr` 테이블을 확정한다.

---

## 테이블: `patch_pr` (기존 + 컬럼 추가)

LLM이 생성한 패치를 GitHub PR로 자동 제출한 기록.
취약점 1개당 최대 1개의 패치 PR (vulnerability_id UNIQUE 제약).

### 전체 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|--------|------|----------|--------|------|
| id | UUID | NOT NULL | gen_random_uuid() | PK |
| vulnerability_id | UUID | NOT NULL | - | FK → vulnerability.id (CASCADE, UNIQUE) |
| repo_id | UUID | NOT NULL | - | FK → repository.id (CASCADE) |
| github_pr_number | INTEGER | NULL | - | GitHub PR 번호 |
| github_pr_url | TEXT | NULL | - | GitHub PR URL |
| branch_name | VARCHAR(255) | NULL | - | 패치 브랜치명 (예: `vulnix/fix-sql-injection-a1b2c3d`) |
| status | VARCHAR(20) | NOT NULL | `'created'` | PR 상태: created / merged / closed / rejected |
| patch_diff | TEXT | NULL | - | unified diff 형식 패치 내용 |
| patch_description | TEXT | NULL | - | 패치 설명 (PR 본문에 포함) |
| **test_suggestion** | **TEXT** | **NULL** | **-** | **LLM이 제안한 테스트 코드 (F-03 신규 추가)** |
| created_at | TIMESTAMPTZ | NOT NULL | - | PR 생성 시각 |
| merged_at | TIMESTAMPTZ | NULL | - | PR 머지 시각 |

### 인덱스

| 인덱스명 | 컬럼 | 타입 | 설명 |
|---------|------|------|------|
| patch_pr_pkey | id | PRIMARY KEY | PK |
| uq_patch_pr_vulnerability_id | vulnerability_id | UNIQUE | 취약점당 1개 PR |
| idx_patch_pr_repo_id | repo_id | B-TREE | 저장소 기준 목록 조회 |
| **idx_patch_pr_status** | **status** | **B-TREE** | **상태 필터 조회 (F-03 신규)** |
| **idx_patch_pr_created** | **created_at** | **B-TREE** | **최신순 정렬 (F-03 신규)** |

### 외래키

| 컬럼 | 참조 테이블 | 참조 컬럼 | ON DELETE |
|------|------------|----------|-----------|
| vulnerability_id | vulnerability | id | CASCADE |
| repo_id | repository | id | CASCADE |

---

## 테이블: `vulnerability` (기존 + 컬럼 추가)

### F-03에서 추가된 컬럼

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|--------|------|----------|--------|------|
| **manual_guide** | **TEXT** | **NULL** | **-** | **패치 불가 시 LLM 생성 수동 수정 가이드** |
| **manual_priority** | **VARCHAR(10)** | **NULL** | **-** | **수동 수정 우선순위 (P0/P1/P2/P3)** |

### manual_priority 값 정의

| 값 | 해당 심각도 | 설명 |
|----|-----------|------|
| P0 | critical | 즉시 처리 필요 |
| P1 | high | 우선 처리 권장 |
| P2 | medium | 일반 처리 |
| P3 | low | 여유 있을 때 처리 |

### 추가 인덱스

| 인덱스명 | 컬럼 | 조건 | 타입 | 설명 |
|---------|------|------|------|------|
| **idx_vulnerability_manual_priority** | **manual_priority** | **WHERE manual_priority IS NOT NULL** | **부분 인덱스 (B-TREE)** | **수동 처리 대상 필터** |

---

## 마이그레이션

### 파일 위치

```
backend/alembic/versions/002_add_f03_columns.py
```

### 의존성 체인

```
(base) → 001_add_f01_columns → 002_add_f03_columns
```

### upgrade() 실행 내용

1. `vulnerability.manual_guide` TEXT 컬럼 추가
2. `vulnerability.manual_priority` VARCHAR(10) 컬럼 추가
3. `patch_pr.test_suggestion` TEXT 컬럼 추가
4. `idx_patch_pr_status` 인덱스 생성
5. `idx_patch_pr_created` 인덱스 생성
6. `idx_vulnerability_manual_priority` 부분 인덱스 생성 (PostgreSQL 전용 DDL)

### downgrade() 실행 내용

1. `idx_vulnerability_manual_priority` 인덱스 삭제
2. `idx_patch_pr_created` 인덱스 삭제
3. `idx_patch_pr_status` 인덱스 삭제
4. `patch_pr.test_suggestion` 컬럼 삭제
5. `vulnerability.manual_priority` 컬럼 삭제
6. `vulnerability.manual_guide` 컬럼 삭제

---

## ERD (F-03 관련 테이블)

```
repository (1) ──────────────────── (N) patch_pr
     │                                      │
     │                                      │ vulnerability_id (UNIQUE)
     │                                      │
     └──── (1) ── (N) vulnerability ──── (0..1)
                        │
                        ├── manual_guide    [NEW]
                        └── manual_priority [NEW]
```

---

## 성능 고려사항

1. `GET /api/v1/patches`: `repo_id IN (...)` + `status` 필터 → `idx_patch_pr_repo_id` + `idx_patch_pr_status` 활용
2. `created_at DESC` 정렬 → `idx_patch_pr_created` 활용
3. `manual_priority` 조회는 `IS NOT NULL` 조건이 많으므로 부분 인덱스로 인덱스 크기 최소화
4. `selectinload(PatchPR.vulnerability)` 사용으로 N+1 쿼리 방지 (상세 조회)
