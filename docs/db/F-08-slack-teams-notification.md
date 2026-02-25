# F-08 Slack/Teams 알림 DB 스키마 확정본

## 개요

F-08 알림 기능을 위해 추가된 테이블입니다. 알림 마이그레이션 파일: `004_add_f08_tables.py`

---

## 테이블: `notification_config`

팀 단위 Slack/Teams webhook 알림 설정을 저장합니다.

### 컬럼

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id | UUID | NOT NULL | uuid4() | 기본 키 |
| team_id | UUID | NOT NULL | - | 소속 팀 ID (FK → team.id CASCADE) |
| platform | VARCHAR(20) | NOT NULL | - | 알림 플랫폼 (slack / teams) |
| webhook_url | TEXT | NOT NULL | - | Webhook URL |
| severity_threshold | VARCHAR(20) | NOT NULL | 'all' | 알림 기준 심각도 |
| weekly_report_enabled | BOOLEAN | NOT NULL | false | 주간 리포트 발송 여부 |
| weekly_report_day | INTEGER | NOT NULL | 1 | 주간 리포트 발송 요일 (1=월~7=일) |
| is_active | BOOLEAN | NOT NULL | true | 활성 여부 |
| created_by | UUID | NULL | NULL | 등록자 ID (FK → user.id SET NULL) |
| created_at | TIMESTAMPTZ | NOT NULL | now() | 생성 시각 (UTC) |
| updated_at | TIMESTAMPTZ | NOT NULL | now() | 수정 시각 (UTC) |

### 제약 조건

| 이름 | 타입 | 컬럼 | 참조 | ON DELETE |
|------|------|------|------|-----------|
| PK | PRIMARY KEY | id | - | - |
| FK | FOREIGN KEY | team_id | team.id | CASCADE |
| FK | FOREIGN KEY | created_by | user.id | SET NULL |

### 인덱스

| 인덱스명 | 컬럼 | 설명 |
|----------|------|------|
| idx_notification_config_team | team_id | 팀별 설정 조회 |
| idx_notification_config_team_active | (team_id, is_active) | 팀 활성 설정 조회 |

### 유효값

| 컬럼 | 허용값 |
|------|--------|
| platform | `slack`, `teams` |
| severity_threshold | `critical`, `high`, `medium`, `all` |
| weekly_report_day | 1(월) ~ 7(일) |

---

## 테이블: `notification_log`

webhook 발송 이력을 저장합니다. 발송 성공/실패 추적 및 감사에 활용됩니다.

### 컬럼

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id | UUID | NOT NULL | uuid4() | 기본 키 |
| team_id | UUID | NOT NULL | - | 소속 팀 ID (FK → team.id CASCADE) |
| config_id | UUID | NULL | NULL | 알림 설정 ID (FK → notification_config.id CASCADE) |
| notification_type | VARCHAR(30) | NOT NULL | - | 알림 유형 (vulnerability / weekly_report) |
| status | VARCHAR(20) | NOT NULL | - | 발송 상태 (sent / failed) |
| http_status | INTEGER | NULL | NULL | HTTP 응답 코드 |
| error_message | TEXT | NULL | NULL | 오류 메시지 |
| payload | JSONB | NULL | NULL | 발송된 JSON payload |
| sent_at | TIMESTAMPTZ | NOT NULL | now() | 발송 시각 (UTC) |

### 제약 조건

| 이름 | 타입 | 컬럼 | 참조 | ON DELETE |
|------|------|------|------|-----------|
| PK | PRIMARY KEY | id | - | - |
| FK | FOREIGN KEY | team_id | team.id | CASCADE |
| FK | FOREIGN KEY | config_id | notification_config.id | CASCADE |

### 인덱스

| 인덱스명 | 컬럼 | 설명 |
|----------|------|------|
| idx_notification_log_team | team_id | 팀별 로그 조회 |
| idx_notification_log_config | config_id | 설정별 로그 조회 |
| idx_notification_log_sent_at | sent_at DESC | 최신순 정렬 |

### 유효값

| 컬럼 | 허용값 |
|------|--------|
| notification_type | `vulnerability`, `weekly_report` |
| status | `sent`, `failed` |

---

## ERD 관계

```
team (1) ─────────────── (N) notification_config
                                    │
                                    │ (1)
                                    │
                               (N) notification_log
user (1) ─── (N, created_by) notification_config
```

---

## 마이그레이션

### 004_add_f08_tables.py

```
Revision ID: 004_add_f08_tables
Revises: 003_add_f06_tables
Create Date: 2026-02-25
```

upgrade:
- `notification_config` 테이블 생성
- `notification_log` 테이블 생성
- 인덱스 5개 생성

downgrade:
- 인덱스 5개 삭제
- `notification_log` 테이블 삭제
- `notification_config` 테이블 삭제

---

## 성능 고려사항

1. N+1 방지: 알림 설정 조회 시 `team_id` 인덱스로 한 번에 로드
2. 로그 조회: `sent_at DESC` 인덱스로 최신순 정렬 최적화
3. 활성 설정 필터: `(team_id, is_active)` 복합 인덱스 활용
4. payload 컬럼: JSONB 타입으로 유연한 구조 지원 (GIN 인덱스 필요 시 추가 검토)
