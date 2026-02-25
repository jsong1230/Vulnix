# F-09 GitLab/Bitbucket 연동 API 스펙 (확정본)

작성일: 2026-02-25

## 개요

GitHub 외 GitLab, Bitbucket 저장소를 Vulnix에 연동하는 API 엔드포인트이다.
PAT(GitLab) 또는 App Password(Bitbucket) 기반 인증을 사용한다.

---

## 공통 응답 형식

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

---

## 1. GitLab 저장소 목록 조회

**GET** `/api/v1/repos/gitlab/projects`

GitLab PAT로 접근 가능한 프로젝트 목록을 조회한다. 이미 연동된 저장소에는 `already_connected=true` 플래그가 설정된다.

### 인증

JWT 필수

### Query Parameters

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `access_token` | string | Y | GitLab Personal Access Token |
| `gitlab_url` | string | N | GitLab 인스턴스 URL (기본: `https://gitlab.com`) |

### 응답 (200)

```json
{
  "success": true,
  "data": {
    "repositories": [
      {
        "platform_repo_id": "12345",
        "full_name": "group/project-name",
        "private": true,
        "default_branch": "main",
        "language": "Python",
        "platform_url": "https://gitlab.com/group/project-name",
        "already_connected": false
      }
    ]
  }
}
```

### 에러

| 코드 | 상황 |
|------|------|
| 401 | JWT 인증 실패 |

---

## 2. GitLab 저장소 연동

**POST** `/api/v1/repos/gitlab`

### 인증

JWT 필수

### Request Body

```json
{
  "gitlab_project_id": 12345,
  "full_name": "group/project-name",
  "default_branch": "main",
  "language": "python",
  "gitlab_url": "https://gitlab.com",
  "access_token": "glpat-xxxxxxxxxxxxxxxxxxxx"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `gitlab_project_id` | int | Y | GitLab 프로젝트 ID |
| `full_name` | string | Y | 저장소 전체 이름 (예: group/project-name) |
| `default_branch` | string | N | 기본 브랜치 (기본: "main") |
| `language` | string | N | 주 프로그래밍 언어 |
| `gitlab_url` | string | N | GitLab 인스턴스 URL (기본: "https://gitlab.com") |
| `access_token` | string | Y | GitLab Personal Access Token |

### 처리 순서

1. PAT 유효성 검증 (`GET /api/v4/user`)
2. 중복 확인 (`platform="gitlab"`, `platform_repo_id=gitlab_project_id`)
3. Repository 레코드 생성
4. GitLab Webhook 자동 등록 (`push_events`, `merge_requests_events`)
5. 초기 스캔 큐 등록

### 응답 (201)

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "team_id": "uuid",
    "platform": "gitlab",
    "platform_repo_id": "12345",
    "github_repo_id": 0,
    "full_name": "group/project-name",
    "default_branch": "main",
    "language": "python",
    "is_active": true,
    "installation_id": null,
    "last_scanned_at": null,
    "security_score": null,
    "is_initial_scan_done": false,
    "created_at": "2026-02-25T10:00:00Z"
  }
}
```

### 에러

| 코드 | 상황 |
|------|------|
| 401 | JWT 인증 실패 |
| 409 | 이미 등록된 저장소 (동일 platform + platform_repo_id) |
| 422 | GitLab PAT 유효성 검증 실패 |

---

## 3. Bitbucket 저장소 목록 조회

**GET** `/api/v1/repos/bitbucket/repositories`

### 인증

JWT 필수

### Query Parameters

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `username` | string | Y | Bitbucket 사용자명 |
| `app_password` | string | Y | Bitbucket App Password |
| `workspace` | string | Y | Bitbucket workspace 이름 |

### 응답 (200)

```json
{
  "success": true,
  "data": {
    "repositories": [
      {
        "platform_repo_id": "{aaaa-bbbb-cccc}",
        "full_name": "my-workspace/my-repo",
        "private": true,
        "default_branch": "main",
        "language": "Python",
        "platform_url": "https://bitbucket.org/my-workspace/my-repo",
        "already_connected": false
      }
    ]
  }
}
```

### 에러

| 코드 | 상황 |
|------|------|
| 401 | JWT 인증 실패 |

---

## 4. Bitbucket 저장소 연동

**POST** `/api/v1/repos/bitbucket`

### 인증

JWT 필수

### Request Body

```json
{
  "workspace": "my-workspace",
  "repo_slug": "my-repo",
  "full_name": "my-workspace/my-repo",
  "default_branch": "main",
  "language": "python",
  "username": "bitbucket-username",
  "app_password": "xxxxxxxxxxxxxxxxxxxx"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `workspace` | string | Y | Bitbucket workspace 이름 |
| `repo_slug` | string | Y | 저장소 slug |
| `full_name` | string | Y | 저장소 전체 이름 (예: workspace/repo-slug) |
| `default_branch` | string | N | 기본 브랜치 (기본: "main") |
| `language` | string | N | 주 프로그래밍 언어 |
| `username` | string | Y | Bitbucket 사용자명 |
| `app_password` | string | Y | Bitbucket App Password |

### 처리 순서

1. App Password 유효성 검증 (`GET /2.0/user`)
2. 중복 확인 (`platform="bitbucket"`, `platform_repo_id="{workspace}/{repo_slug}"`)
3. Repository 레코드 생성
4. Bitbucket Webhook 자동 등록 (`repo:push`, `pullrequest:created`, `pullrequest:updated`)
5. 초기 스캔 큐 등록

### 응답 (201)

`data.platform = "bitbucket"` 외 GitLab과 동일 형식

### 에러

| 코드 | 상황 |
|------|------|
| 401 | JWT 인증 실패 |
| 409 | 이미 등록된 저장소 |
| 422 | Bitbucket 자격증명 검증 실패 |

---

## 5. GitLab Webhook 수신

**POST** `/api/v1/webhooks/gitlab`

### 인증

X-Gitlab-Token 헤더 검증 (상수 시간 비교, `hmac.compare_digest`)

### 지원 이벤트

| X-Gitlab-Event | 응답 event 필드 | 처리 |
|----------------|-----------------|------|
| Push Hook | "push" | 기본 브랜치 push + Python 파일 변경 시 스캔 트리거 |
| Merge Request Hook | "merge_request" | MR open/update 시 스캔 트리거 |
| 그 외 | (이벤트명) | 200으로 무시 |

### Request Headers

| 헤더 | 설명 |
|------|------|
| `X-Gitlab-Event` | 이벤트 타입 (없으면 400) |
| `X-Gitlab-Token` | Webhook 시크릿 토큰 (없거나 불일치 시 403) |

### 응답 (202)

```json
{
  "message": "이벤트가 수신되었습니다.",
  "event": "push",
  "scan_job_id": "uuid-or-null"
}
```

### 에러

| 코드 | 상황 |
|------|------|
| 400 | X-Gitlab-Event 헤더 누락 |
| 403 | X-Gitlab-Token 검증 실패 (누락 포함) |

---

## 6. Bitbucket Webhook 수신

**POST** `/api/v1/webhooks/bitbucket`

### 인증

X-Hub-Signature HMAC-SHA256 검증 (`hmac.compare_digest`)

### 지원 이벤트

| X-Event-Key | 처리 |
|-------------|------|
| repo:push | 기본 브랜치 push 시 스캔 트리거 |
| pullrequest:created | PR 생성 시 스캔 트리거 |
| pullrequest:updated | PR 업데이트 시 기존 스캔 취소 후 재등록 |
| 그 외 | 200으로 무시 |

### Request Headers

| 헤더 | 설명 |
|------|------|
| `X-Event-Key` | 이벤트 타입 (없으면 400) |
| `X-Hub-Signature` | "sha256=..." 형식 HMAC-SHA256 서명 (없거나 불일치 시 403) |

### 응답 (202)

Gitab Webhook과 동일 형식

### 에러

| 코드 | 상황 |
|------|------|
| 400 | X-Event-Key 헤더 누락 |
| 403 | X-Hub-Signature 검증 실패 (누락 포함) |

---

## 7. 저장소 목록 조회 (platform 필터 추가, 기존 API 변경)

**GET** `/api/v1/repos`

### 변경사항 (F-09 기존 API 확장)

- `platform` 쿼리 파라미터 추가 (선택)
- `RepositoryResponse`에 `platform`, `platform_repo_id` 필드 추가

### Query Parameters (추가)

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `platform` | string | N | "github" / "gitlab" / "bitbucket" (없으면 모든 플랫폼) |

### 응답 (200)

`data[]` 배열 각 항목에 `platform` 필드 추가됨. 하위 호환성 유지.

---

## 환경변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `GITLAB_WEBHOOK_SECRET` | GitLab Webhook 서명 시크릿 | (없으면 빈 문자열) |
| `BITBUCKET_WEBHOOK_SECRET` | Bitbucket Webhook 서명 시크릿 | (없으면 빈 문자열) |
| `APP_BASE_URL` | Webhook 등록 시 사용할 서버 URL | "https://vulnix.example.com" |
