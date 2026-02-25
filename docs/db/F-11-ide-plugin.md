# F-11 IDE 플러그인 — DB 스키마 확정본

작성일: 2026-02-25
마이그레이션: `backend/alembic/versions/007_add_f11_tables.py`

---

## 신규 테이블: api_key

IDE 플러그인 인증용 팀 단위 API Key를 저장한다.
원본 키는 발급 시 한 번만 반환되며, DB에는 SHA-256 해시만 저장된다. (ADR-F11-004)

### DDL

```sql
CREATE TABLE api_key (
    id          UUID          NOT NULL DEFAULT uuid_generate_v4(),
    team_id     UUID          NOT NULL,
    name        VARCHAR(255)  NOT NULL,
    key_hash    VARCHAR(64)   NOT NULL UNIQUE,
    key_prefix  VARCHAR(20)   NOT NULL,
    is_active   BOOLEAN       NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMPTZ  NULL,
    expires_at  TIMESTAMPTZ   NULL,
    created_by  UUID          NULL,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    revoked_at  TIMESTAMPTZ   NULL,

    PRIMARY KEY (id),
    CONSTRAINT uq_api_key_hash UNIQUE (key_hash),
    FOREIGN KEY (team_id) REFERENCES team(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES user(id) ON DELETE SET NULL
);
```

### 컬럼 정의

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|----------|------|
| `id` | UUID | PK, NOT NULL | 기본 키 (UUID v4) |
| `team_id` | UUID | FK → team.id CASCADE, NOT NULL | 소속 팀 ID |
| `name` | VARCHAR(255) | NOT NULL | 키 이름 (사용자 지정) |
| `key_hash` | VARCHAR(64) | NOT NULL, UNIQUE | SHA-256 해시 (원본 키 미저장) |
| `key_prefix` | VARCHAR(20) | NOT NULL | 앞 12자리 (조회 시 표시용) |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | 활성 여부 |
| `last_used_at` | TIMESTAMPTZ | NULL | 마지막 사용 시각 |
| `expires_at` | TIMESTAMPTZ | NULL | 만료 일시 (NULL이면 무기한) |
| `created_by` | UUID | FK → user.id SET NULL, NULL | 발급자 ID |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 생성 시각 |
| `revoked_at` | TIMESTAMPTZ | NULL | 비활성화 시각 (논리 삭제 표시) |

### 인덱스

```sql
-- key_hash UNIQUE 인덱스 (O(1) 조회 — 인증 시 핵심 경로)
CREATE UNIQUE INDEX idx_api_key_hash
    ON api_key(key_hash);

-- 팀별 API Key 목록 조회
CREATE INDEX idx_api_key_team
    ON api_key(team_id);

-- 팀별 활성 API Key 조회 (부분 인덱스)
CREATE INDEX idx_api_key_active
    ON api_key(team_id, is_active)
    WHERE is_active = TRUE;
```

### API Key 형식

| 환경 | 형식 | 예시 |
|------|------|------|
| 프로덕션 | `vx_live_{32자 URL-safe base64}` | `vx_live_a1b2c3d4e5f6...` |
| 테스트 | `vx_test_{32자 URL-safe base64}` | `vx_test_a1b2c3d4e5f6...` |

- `key_prefix`: key 앞 12자리 저장 (예: `vx_live_a1b2`)
- `key_hash`: SHA-256(`vx_live_...` 전체 문자열) → 64자 hex 문자열

### 논리 삭제 방식

API Key 삭제는 물리 삭제가 아닌 논리 삭제로 처리된다:
- `is_active = FALSE` 로 변경
- `revoked_at = NOW()` 타임스탬프 기록

비활성화된 키로 인증 시 HTTP 403 (API_KEY_DISABLED) 반환.

---

## 기존 테이블 변경사항

F-11에서 기존 테이블의 변경은 없다.

---

## 마이그레이션 이력

| 버전 | 파일 | 내용 |
|------|------|------|
| 007 | `007_add_f11_tables.py` | api_key 테이블 및 인덱스 신규 생성 |
