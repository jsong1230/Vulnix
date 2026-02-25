# F-01: 저장소 연동 및 스캔 트리거 — API 스펙 확정본

작성일: 2026-02-25

---

## 1. POST /api/v1/webhooks/github

**목적**: GitHub Webhook 이벤트 수신 (서명 검증 후 이벤트별 처리)
**인증**: HMAC-SHA256 서명 검증 (Bearer JWT 아님)

### 요청 헤더

| 헤더 | 필수 | 설명 |
|------|------|------|
| X-GitHub-Event | 필수 | push / pull_request / installation / ping |
| X-Hub-Signature-256 | 필수 | sha256=<hex_digest> |
| X-GitHub-Delivery | 선택 | 배달 ID (UUID) |
| Content-Type | 필수 | application/json |

### 응답 (202 Accepted)

**push 이벤트**:
```json
{
  "message": "이벤트가 수신되었습니다.",
  "event": "push",
  "delivery": "uuid",
  "scan_job_id": "uuid | null"
}
```

**pull_request 이벤트 (opened / synchronize)**:
```json
{
  "message": "이벤트가 수신되었습니다.",
  "event": "pull_request",
  "delivery": "uuid",
  "scan_job_id": "uuid | null"
}
```

**installation 이벤트 (created / deleted)**:
```json
{
  "message": "이벤트가 수신되었습니다.",
  "event": "installation",
  "delivery": "uuid",
  "repo_ids": ["uuid", ...]
}
```

**ping 이벤트**:
```json
{
  "message": "pong",
  "delivery": "uuid"
}
```

### 에러 케이스

| 코드 | 상황 |
|------|------|
| 403 | HMAC-SHA256 서명 검증 실패 또는 서명 헤더 누락 |
| 400 | X-GitHub-Event 헤더 누락 |

---

## 2. GET /api/v1/repos

**목적**: 현재 사용자 팀의 연동 저장소 목록 조회
**인증**: Bearer JWT 필요

### 쿼리 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| page | int | 1 | 페이지 번호 |
| per_page | int | 20 | 페이지당 항목 수 |

### 응답 (200 OK)

```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "team_id": "uuid",
      "github_repo_id": 123456,
      "full_name": "org/repo-name",
      "default_branch": "main",
      "language": "Python",
      "is_active": true,
      "installation_id": 789,
      "last_scanned_at": "2026-02-25T10:00:00Z",
      "security_score": 85.50,
      "is_initial_scan_done": true,
      "created_at": "2026-02-24T09:00:00Z"
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

### 에러 케이스

| 코드 | 상황 |
|------|------|
| 401 | 인증 실패 |

---

## 3. POST /api/v1/repos

**목적**: 저장소 연동 등록 (초기 스캔 자동 트리거)
**인증**: Bearer JWT 필요

### 요청 Body

```json
{
  "github_repo_id": 123456,
  "full_name": "org/repo-name",
  "default_branch": "main",
  "language": "Python",
  "installation_id": 789
}
```

### 응답 (201 Created)

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "team_id": "uuid",
    "github_repo_id": 123456,
    "full_name": "org/repo-name",
    "default_branch": "main",
    "language": "Python",
    "is_active": true,
    "installation_id": 789,
    "last_scanned_at": null,
    "security_score": null,
    "is_initial_scan_done": false,
    "created_at": "2026-02-25T10:00:00Z"
  },
  "error": null
}
```

### 에러 케이스

| 코드 | 상황 |
|------|------|
| 401 | 인증 실패 |
| 409 | 이미 등록된 github_repo_id |
| 422 | 필수 필드 누락 (full_name 등) |

---

## 4. DELETE /api/v1/repos/{repo_id}

**목적**: 저장소 연동 해제 및 관련 데이터 정리
**인증**: Bearer JWT 필요 (owner/admin 권한)

### 응답 (200 OK)

```json
{
  "success": true,
  "data": {
    "repo_id": "uuid",
    "full_name": "org/repo-name",
    "deleted_scans_count": 12,
    "deleted_vulnerabilities_count": 45
  },
  "error": null
}
```

### 에러 케이스

| 코드 | 상황 |
|------|------|
| 401 | 인증 실패 |
| 403 | member 역할 (owner/admin이 아님) |
| 404 | 저장소 없음 |

---

## 5. GET /api/v1/repos/github/installations

**목적**: GitHub App 설치 후 접근 가능한 저장소 목록 조회
**인증**: Bearer JWT 필요

### 응답 (200 OK)

```json
{
  "success": true,
  "data": {
    "installation_id": 789,
    "repositories": [
      {
        "github_repo_id": 123456,
        "full_name": "org/repo-name",
        "private": true,
        "default_branch": "main",
        "language": "Python",
        "already_connected": false
      }
    ]
  },
  "error": null
}
```

---

## 비고

- `scan_job_id`는 스캔이 트리거된 경우에만 값이 있으며, 미등록 저장소나 조건 미충족 시 `null`
- Webhook 서명 검증은 `GITHUB_WEBHOOK_SECRET` 환경변수 기반 HMAC-SHA256 사용
- `already_connected` 플래그는 현재 팀에 연동된 저장소 여부를 표시
