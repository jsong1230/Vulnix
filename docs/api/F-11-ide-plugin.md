# F-11 IDE 플러그인 — API 스펙 확정본

작성일: 2026-02-25
구현 파일: `backend/src/api/v1/ide.py`

---

## 인증 방식

| 엔드포인트 | 인증 방식 |
|-----------|-----------|
| `POST /api/v1/ide/analyze` | `X-Api-Key` 헤더 (API Key 인증) |
| `GET /api/v1/ide/false-positive-patterns` | `X-Api-Key` 헤더 (API Key 인증) |
| `POST /api/v1/ide/patch-suggestion` | `X-Api-Key` 헤더 (API Key 인증) |
| `POST /api/v1/ide/api-keys` | `Authorization: Bearer <JWT>` (owner/admin만) |
| `GET /api/v1/ide/api-keys` | `Authorization: Bearer <JWT>` |
| `DELETE /api/v1/ide/api-keys/{id}` | `Authorization: Bearer <JWT>` (owner/admin만) |

---

## POST /api/v1/ide/analyze

코드 스니펫을 Semgrep으로 실시간 분석하여 취약점 목록을 반환한다.

### Request Headers

| 헤더 | 필수 | 설명 |
|------|------|------|
| `X-Api-Key` | Y | API Key (`vx_live_...` 형식) |

### Request Body

```json
{
  "file_path": "src/api/routes/users.py",
  "language": "python",
  "content": "... 파일 전체 소스코드 ...",
  "context": {
    "workspace_name": "my-project",
    "git_branch": "feature/login"
  }
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `file_path` | string | N | 파일 경로 (FP 패턴 glob 매칭에 활용) |
| `language` | string | Y | 지원 언어: python, javascript, typescript, java, go |
| `content` | string | Y | 분석할 소스코드 (최대 1MB) |
| `context` | object | N | 부가 컨텍스트 (workspace_name, git_branch) |

### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "findings": [
      {
        "rule_id": "python.sqlalchemy.security.sql-injection",
        "severity": "high",
        "message": "사용자 입력이 SQL 쿼리에 직접 삽입됩니다.",
        "file_path": "src/api/routes/users.py",
        "start_line": 42,
        "end_line": 45,
        "start_col": 8,
        "end_col": 55,
        "code_snippet": "db.execute(f\"SELECT * FROM users WHERE id = {user_id}\")",
        "cwe_id": "CWE-89",
        "owasp_category": "A03:2021 - Injection",
        "vulnerability_type": "sql_injection",
        "is_false_positive_filtered": false
      }
    ],
    "analysis_duration_ms": 187,
    "semgrep_version": "1.56.0"
  },
  "error": null
}
```

### 에러 케이스

| HTTP 코드 | 에러 코드 | 상황 |
|-----------|-----------|------|
| 400 | CONTENT_TOO_LARGE | content가 1MB 초과 |
| 401 | INVALID_API_KEY | API Key 누락 또는 유효하지 않음 |
| 403 | API_KEY_DISABLED | 비활성화된 API Key |
| 422 | - | 지원하지 않는 언어 또는 필수 필드 누락 |

---

## GET /api/v1/ide/false-positive-patterns

팀의 활성 오탐 패턴 목록을 반환한다. ETag 캐싱 지원.

### Request Headers

| 헤더 | 필수 | 설명 |
|------|------|------|
| `X-Api-Key` | Y | API Key |
| `If-None-Match` | N | 이전 응답의 ETag 값 (조건부 요청) |

### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "patterns": [
      {
        "id": "bbbb1111-bbbb-bbbb-bbbb-bbbb11111111",
        "semgrep_rule_id": "python.flask.security.xss",
        "file_pattern": "tests/**",
        "reason": "테스트 코드에서 XSS 탐지 무시",
        "is_active": true,
        "updated_at": "2026-02-25T10:00:00Z"
      }
    ],
    "last_updated": "2026-02-25T10:00:00Z",
    "etag": "\"abc123def456789a\""
  },
  "error": null
}
```

### Response Headers

| 헤더 | 설명 |
|------|------|
| `ETag` | 응답 본문의 해시 (변경 감지용) |

### Response (304 Not Modified)

`If-None-Match` 헤더의 ETag가 현재 값과 일치하면 본문 없이 304 반환.

---

## POST /api/v1/ide/patch-suggestion

특정 취약점에 대해 LLM 기반 패치 diff를 생성한다.

### Request Headers

| 헤더 | 필수 | 설명 |
|------|------|------|
| `X-Api-Key` | Y | API Key |

### Request Body

```json
{
  "file_path": "src/api/routes/users.py",
  "language": "python",
  "content": "... 파일 전체 소스코드 ...",
  "finding": {
    "rule_id": "python.sqlalchemy.security.sql-injection",
    "start_line": 42,
    "end_line": 45,
    "code_snippet": "db.execute(f\"SELECT * FROM users WHERE id = {user_id}\")",
    "message": "사용자 입력이 SQL 쿼리에 직접 삽입됩니다."
  }
}
```

### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "patch_diff": "--- a/src/api/routes/users.py\n+++ b/src/api/routes/users.py\n@@ -42,4 +42,4 @@\n-    db.execute(f\"SELECT * FROM users WHERE id = {user_id}\")\n+    db.execute(text(\"SELECT * FROM users WHERE id = :user_id\"), {\"user_id\": user_id})",
    "patch_description": "f-string SQL 쿼리를 파라미터 바인딩 방식으로 변경하여 SQL Injection을 방지합니다.",
    "vulnerability_detail": {
      "type": "sql_injection",
      "severity": "high",
      "cwe_id": "CWE-89",
      "owasp_category": "A03:2021 - Injection",
      "description": "사용자 입력값이 SQL 쿼리에 직접 삽입되면 공격자가 임의의 SQL을 실행할 수 있습니다.",
      "references": [
        "https://cwe.mitre.org/data/definitions/89.html",
        "https://owasp.org/Top10/"
      ]
    }
  },
  "error": null
}
```

---

## POST /api/v1/ide/api-keys

팀용 IDE API Key를 생성한다. `owner` 또는 `admin` 역할만 호출 가능.

### Request Headers

| 헤더 | 필수 | 설명 |
|------|------|------|
| `Authorization` | Y | `Bearer <JWT>` |

### Request Body

```json
{
  "name": "Team IDE Key",
  "expires_in_days": 365
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | Y | 키 이름 (1~255자) |
| `expires_in_days` | integer | N | 만료 기간 (일, 미입력 시 무기한) |

### Response (201 Created)

```json
{
  "success": true,
  "data": {
    "id": "aaaa1111-aaaa-aaaa-aaaa-aaaa11111111",
    "name": "Team IDE Key",
    "key": "vx_live_a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
    "key_prefix": "vx_live_a1b2",
    "expires_at": "2027-02-25T00:00:00Z",
    "created_at": "2026-02-25T00:00:00Z"
  },
  "error": null
}
```

> 주의: `key` 값은 생성 시 한 번만 반환됩니다. 이후 조회에서는 `key_prefix`만 표시됩니다.

### 에러 케이스

| HTTP 코드 | 에러 코드 | 상황 |
|-----------|-----------|------|
| 401 | - | JWT 미제공 또는 유효하지 않음 |
| 403 | FORBIDDEN | owner/admin 이외의 역할 |
| 422 | - | name 필드 누락 |

---

## GET /api/v1/ide/api-keys

팀의 발급된 API Key 목록을 반환한다. `key` 원본 값은 포함되지 않는다.

### Response (200 OK)

```json
{
  "success": true,
  "data": [
    {
      "id": "aaaa1111-aaaa-aaaa-aaaa-aaaa11111111",
      "name": "Team IDE Key",
      "key_prefix": "vx_live_a1b2",
      "is_active": true,
      "created_at": "2026-02-25T00:00:00Z",
      "expires_at": "2027-02-25T00:00:00Z",
      "last_used_at": null
    }
  ],
  "error": null
}
```

---

## DELETE /api/v1/ide/api-keys/{key_id}

API Key를 논리 삭제(비활성화)한다. `owner` 또는 `admin` 역할만 호출 가능.

### Path Parameters

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `key_id` | UUID | 비활성화할 API Key ID |

### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "id": "aaaa1111-aaaa-aaaa-aaaa-aaaa11111111",
    "name": "Team IDE Key",
    "is_active": false,
    "revoked_at": "2026-02-25T12:00:00Z"
  },
  "error": null
}
```

### 에러 케이스

| HTTP 코드 | 에러 코드 | 상황 |
|-----------|-----------|------|
| 401 | - | JWT 미제공 |
| 403 | FORBIDDEN | owner/admin 이외의 역할 |
| 404 | NOT_FOUND | 해당 ID의 API Key 없음 |
| 422 | - | UUID 형식 오류 |
