# F-10 CISO 리포트 및 인증 증적 — DB 스키마 확정본

> 작성일: 2026-02-25
> 마이그레이션 파일: `alembic/versions/006_add_f10_tables.py`

---

## 신규 테이블 목록

| 테이블명 | 설명 |
|---------|------|
| `report_config` | 리포트 자동 생성 스케줄 설정 |
| `report_history` | 리포트 생성 이력 |

---

## report_config

리포트 자동 생성 스케줄 설정 (팀 단위). 동일 팀에서 report_type은 유일하다.

### 컬럼

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|--------|------|----------|--------|------|
| `id` | UUID | NOT NULL | uuid4 | PK |
| `team_id` | UUID | NOT NULL | - | FK → team.id (CASCADE) |
| `report_type` | VARCHAR(30) | NOT NULL | - | ciso / csap / iso27001 / isms |
| `schedule` | VARCHAR(20) | NOT NULL | - | weekly / monthly / quarterly |
| `email_recipients` | JSONB | NOT NULL | `'[]'` | 수신 이메일 목록 |
| `is_active` | BOOLEAN | NOT NULL | `true` | 활성 여부 |
| `last_generated_at` | TIMESTAMPTZ | NULL | - | 마지막 생성 시각 (UTC) |
| `next_generation_at` | TIMESTAMPTZ | NULL | - | 다음 생성 예정 시각 (UTC) |
| `created_by` | UUID | NULL | - | FK → user.id (SET NULL) |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | 생성 시각 (UTC) |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `now()` | 수정 시각 (UTC) |

### 제약 조건

| 이름 | 유형 | 대상 컬럼 |
|------|------|----------|
| `report_config_pkey` | PRIMARY KEY | `id` |
| `uq_report_config_team_type` | UNIQUE | `(team_id, report_type)` |
| `fk_report_config_team` | FK | `team_id → team.id` ON DELETE CASCADE |
| `fk_report_config_created_by` | FK | `created_by → user.id` ON DELETE SET NULL |

### 인덱스

| 인덱스명 | 컬럼 | 설명 |
|---------|------|------|
| `idx_report_config_team` | `team_id` | 팀별 설정 조회 |
| `idx_report_config_team_active` | `(team_id, is_active)` | 활성 설정 필터 |

### ORM 모델

파일: `src/models/report_config.py`
클래스: `ReportConfig`

- `metadata` 컬럼명이 SQLAlchemy Declarative API 예약어와 충돌하여 해당 속성명은 사용하지 않음.
- Python-level 기본값을 `__init__` 오버라이드로 설정 (`is_active=True`, `email_recipients=[]`).

---

## report_history

리포트 생성 이력. 수동 또는 스케줄에 의해 생성된 각 리포트 파일의 기록.

### 컬럼

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|--------|------|----------|--------|------|
| `id` | UUID | NOT NULL | uuid4 | PK |
| `team_id` | UUID | NOT NULL | - | FK → team.id (CASCADE) |
| `config_id` | UUID | NULL | - | FK → report_config.id (SET NULL), 수동 생성 시 NULL |
| `report_type` | VARCHAR(30) | NOT NULL | - | ciso / csap / iso27001 / isms |
| `format` | VARCHAR(10) | NOT NULL | `'pdf'` | pdf / json |
| `status` | VARCHAR(20) | NOT NULL | `'generating'` | generating / completed / failed |
| `file_path` | TEXT | NULL | - | 서버 로컬 파일 경로 |
| `file_size_bytes` | BIGINT | NULL | - | 파일 크기 (bytes) |
| `period_start` | DATE | NOT NULL | - | 리포트 기간 시작일 |
| `period_end` | DATE | NOT NULL | - | 리포트 기간 종료일 |
| `email_sent_at` | TIMESTAMPTZ | NULL | - | 이메일 발송 시각 (UTC) |
| `email_recipients` | JSONB | NULL | - | 이메일 수신자 목록 |
| `error_message` | TEXT | NULL | - | 오류 메시지 (failed 상태) |
| `metadata` | JSONB | NULL | - | 리포트 메타데이터 (보안 점수, 취약점 수 등) |
| `generated_by` | UUID | NULL | - | FK → user.id (SET NULL), 스케줄 자동 생성 시 NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | 생성 시각 (UTC) |

### 제약 조건

| 이름 | 유형 | 대상 컬럼 |
|------|------|----------|
| `report_history_pkey` | PRIMARY KEY | `id` |
| `fk_report_history_team` | FK | `team_id → team.id` ON DELETE CASCADE |
| `fk_report_history_config` | FK | `config_id → report_config.id` ON DELETE SET NULL |
| `fk_report_history_generated_by` | FK | `generated_by → user.id` ON DELETE SET NULL |

### 인덱스

| 인덱스명 | 컬럼 | 설명 |
|---------|------|------|
| `idx_report_history_team` | `team_id` | 팀별 이력 조회 |
| `idx_report_history_team_created_at` | `(team_id, created_at DESC)` | 팀별 최신 이력 조회 (페이지네이션 최적화) |
| `idx_report_history_status` | `status` | 상태별 필터 (scheduler가 generating 목록 주기 조회) |

### ORM 모델

파일: `src/models/report_history.py`
클래스: `ReportHistory`

- DB 컬럼명 `metadata`는 SQLAlchemy 예약어이므로 ORM 속성명은 `report_meta`로 선언.
  ```python
  report_meta: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
  ```
- Python-level 기본값을 `__init__` 오버라이드로 설정 (`status="generating"`).

---

## metadata JSONB 구조 예시

```json
{
  "security_score": 75.5,
  "total_vulnerabilities": 42,
  "critical_count": 3,
  "high_count": 12,
  "medium_count": 18,
  "low_count": 9,
  "total_repositories": 5,
  "active_repositories": 4,
  "avg_response_time_hours": 48.5,
  "auto_patch_rate": 0.35
}
```

---

## ER 다이어그램 (텍스트)

```
team (기존)
 └── report_config  (team_id FK, uq: team_id + report_type)
      └── report_history  (config_id FK, SET NULL)

user (기존)
 ├── report_config.created_by (FK, SET NULL)
 └── report_history.generated_by (FK, SET NULL)
```

---

## 마이그레이션 이력

| 버전 | 파일 | 설명 |
|------|------|------|
| 006 | `006_add_f10_tables.py` | report_config, report_history 테이블 신규 생성 |
