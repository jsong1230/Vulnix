# F-09: GitLab/Bitbucket 연동 -- 변경 설계서

## 1. 참조
- 인수조건: docs/project/features.md #F-09
- 시스템 분석: docs/system/system-design.md
- 의존 기능: F-01(저장소 연동 및 스캔 트리거), F-03(자동 패치 PR 생성)

## 2. 변경 범위
- 변경 유형: 기존 확장 + 신규 추가
- 영향 받는 모듈: Repository 모델, PatchPR 모델, Webhook 핸들러, PatchGenerator, ScanWorker, Config, API Router, Dashboard API, 스키마

## 3. 영향 분석

### 기존 API 변경

| API | 현재 | 변경 후 | 하위 호환성 |
|-----|------|---------|-------------|
| `POST /api/v1/repos` | `github_repo_id` 필수 필드 | `platform` 필드 추가 (기본값 "github"), `github_repo_id` 유지 | 유지 -- platform 미지정 시 기존 동작과 동일 |
| `GET /api/v1/repos` | GitHub 저장소만 반환 | 모든 플랫폼 저장소 반환, `platform` 필드 추가, `?platform=` 필터 지원 | 유지 -- 기존 응답에 필드만 추가 |
| `DELETE /api/v1/repos/{repo_id}` | GitHub 저장소 삭제 | 모든 플랫폼 저장소 삭제 지원 | 유지 -- UUID 기반이므로 플랫폼 무관 |
| `GET /api/v1/dashboard/summary` | GitHub 저장소만 집계 | 전 플랫폼 통합 집계 | 유지 -- 집계 로직은 repository 테이블 기준이므로 투명 확장 |

### 기존 DB 변경

| 테이블 | 변경 내용 | 마이그레이션 전략 |
|--------|----------|------------------|
| `repository` | `platform` 컬럼 추가, `platform_repo_id` 추가, `platform_url` 추가, `platform_access_token_enc` 추가, `external_username` 추가 | Alembic: `ALTER TABLE ADD COLUMN ... DEFAULT 'github'`. 기존 `github_repo_id` 유지 (호환성). 기존 행의 `platform_repo_id`에 `github_repo_id` 값 복사 |
| `patch_pr` | `platform_pr_number` 추가, `platform_pr_url` 추가 | Alembic: `ALTER TABLE ADD COLUMN`. 기존 `github_pr_*` 유지 (호환성) |

### 사이드 이펙트
- **F-01 GitHub 연동**: 기존 로직은 `platform="github"` 조건으로 격리. `_get_active_repo_by_github_id()` 내부에서 `github_repo_id` 조회는 변경 없음. 신규 플랫폼은 `platform_repo_id` 사용
- **F-03 PatchGenerator**: `GitHubAppService` 직접 참조를 `GitPlatformService` 팩토리로 분기 필요. 기존 GitHub PR 생성 경로는 `GitHubPlatformService`로 래핑하여 동작 동일
- **F-07 대시보드**: 통합 대시보드에서 `platform` 필터 추가 필요 (프론트엔드). 백엔드는 repository 테이블 기준 집계이므로 영향 최소
- **F-08 알림**: 알림 메시지에 플랫폼 정보 포함 필요 (영향 미미)

## 4. 아키텍처 결정

### 결정 1: 플랫폼별 Git 서비스 분리 (Strategy Pattern)
- **선택지**: A) 기존 GitHubAppService에 if/else 분기 추가 / B) 공통 인터페이스(ABC) + 플랫폼별 구현 클래스
- **결정**: B) Strategy Pattern (ABC 기반)
- **근거**: 각 플랫폼의 API 구조, 인증 방식, Webhook 페이로드가 완전히 다름. if/else로 하나의 클래스에 넣으면 SRP 위반 + 유지보수 불가. ABC로 계약을 강제하면 새 플랫폼 추가 시 구현 누락을 방지할 수 있다.

### 결정 2: Webhook 엔드포인트 분리
- **선택지**: A) 단일 엔드포인트에서 헤더 기반 자동 감지 / B) 플랫폼별 별도 엔드포인트
- **결정**: B) 플랫폼별 별도 엔드포인트 (`/webhooks/github`, `/webhooks/gitlab`, `/webhooks/bitbucket`)
- **근거**: GitHub은 `X-Hub-Signature-256` HMAC-SHA256, GitLab은 `X-Gitlab-Token` 직접 비교, Bitbucket은 `X-Hub-Signature` HMAC-SHA256. 서명 검증 방식이 완전히 달라 단일 엔드포인트 통합 시 보안 결함 가능성 증가. 플랫폼별 Webhook URL 설정이 명확.

### 결정 3: GitLab 인증 방식
- **선택지**: A) GitLab OAuth Application / B) Personal Access Token (PAT) / C) Project Access Token
- **결정**: B) Personal Access Token (PAT) 기반
- **근거**: PoC 단계에서 가장 설정이 간단하며, GitLab CE/EE/SaaS 모두에서 동작. PAT의 `api` 스코프 하나로 저장소 조회, 코드 클론, MR 생성, Webhook 등록 모두 가능. OAuth Application은 Self-managed GitLab에서 추가 앱 등록 절차가 필요하여 PoC 단계에서 복잡도 과다.

### 결정 4: Bitbucket 인증 방식
- **선택지**: A) Bitbucket OAuth 2.0 Consumer / B) App Password / C) Repository Access Token
- **결정**: B) App Password 기반
- **근거**: Bitbucket Cloud에서 App Password는 사용자 단위로 간편하게 발급 가능. repository, pullrequest, webhook 권한을 선택적으로 부여할 수 있다. OAuth Consumer는 앱 등록 + 콜백 URL 설정이 필요하여 PoC 단계에서 복잡도 과다.

### 결정 5: Repository 모델 확장 방식
- **선택지**: A) 플랫폼별 별도 테이블 / B) 단일 테이블 + platform 컬럼 / C) 별도 credential 테이블
- **결정**: B) 단일 테이블 + platform 컬럼 (credential은 repository 테이블에 암호화 저장)
- **근거**: 저장소 메타데이터는 플랫폼 간 구조가 동일(이름, 브랜치, 스캔 이력 등)하므로 단일 테이블 유지. PoC 단계에서 별도 credential 테이블은 과도한 설계. `platform_access_token_enc` 컬럼에 AES-256 암호화하여 저장 (기존 `access_token_enc` 패턴 답습).

## 5. DB 설계

### 5-1. 변경 테이블: repository

| 컬럼 | 타입 | 변경 | 설명 |
|------|------|------|------|
| `platform` | VARCHAR(20) | **추가** (DEFAULT 'github') | "github" / "gitlab" / "bitbucket" |
| `platform_repo_id` | VARCHAR(255) | **추가** | 플랫폼별 저장소 고유 ID (GitLab: project_id, Bitbucket: repo_uuid) |
| `platform_url` | TEXT | **추가** | 저장소 웹 URL (GitLab/Bitbucket) |
| `platform_access_token_enc` | TEXT | **추가** | AES-256 암호화된 PAT 또는 App Password |
| `external_username` | VARCHAR(255) | **추가** | Bitbucket username (App Password 인증에 필요) |
| `platform_base_url` | VARCHAR(500) | **추가** | Self-managed 인스턴스 URL (GitLab 전용, 기본 NULL) |

기존 `github_repo_id`, `installation_id` 컬럼은 하위 호환성을 위해 유지. 새 연동은 `platform_repo_id` 사용.

**인덱스 변경**:
```sql
-- 플랫폼별 저장소 조회 최적화
CREATE INDEX idx_repository_platform ON repository(platform);

-- 플랫폼 + 저장소 ID 복합 유니크 (동일 플랫폼 내 중복 방지)
CREATE UNIQUE INDEX uq_repository_platform_repo_id
    ON repository(platform, platform_repo_id)
    WHERE platform_repo_id IS NOT NULL;
```

### 5-2. 변경 테이블: patch_pr

| 컬럼 | 타입 | 변경 | 설명 |
|------|------|------|------|
| `platform_pr_number` | INTEGER | **추가** | 플랫폼 MR/PR 번호 (GitLab: iid, Bitbucket: id) |
| `platform_pr_url` | TEXT | **추가** | 플랫폼 MR/PR URL |

기존 `github_pr_number`, `github_pr_url` 유지 (하위 호환성).

## 6. API 설계

### 6-1. GitLab 저장소 연동

#### `POST /api/v1/repos/gitlab`
- **목적**: GitLab PAT로 저장소 연동 등록 및 초기 스캔 큐 등록
- **인증**: JWT 필요
- **Request Body**:
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
- **처리 로직**:
  1. `access_token`으로 GitLab API 접근 검증 (`GET /api/v4/projects/{id}`)
  2. 중복 확인 (platform="gitlab", platform_repo_id=gitlab_project_id)
  3. Repository 레코드 생성 (access_token AES-256 암호화 저장)
  4. GitLab Webhook 자동 등록 (`POST /api/v4/projects/{id}/hooks`)
  5. 초기 스캔 큐 등록
- **Response** (201):
```json
{
    "success": true,
    "data": {
        "id": "uuid",
        "team_id": "uuid",
        "platform": "gitlab",
        "platform_repo_id": "12345",
        "full_name": "group/project-name",
        "default_branch": "main",
        "language": "python",
        "is_active": true,
        "is_initial_scan_done": false,
        "created_at": "2026-02-25T10:00:00Z"
    }
}
```
- **에러 케이스**:

| 코드 | 상황 |
|------|------|
| 401 | JWT 인증 실패 |
| 409 | 이미 등록된 저장소 (동일 platform + platform_repo_id) |
| 422 | GitLab PAT 유효성 검증 실패 (API 접근 불가) |

### 6-2. Bitbucket 저장소 연동

#### `POST /api/v1/repos/bitbucket`
- **목적**: Bitbucket App Password로 저장소 연동 등록 및 초기 스캔 큐 등록
- **인증**: JWT 필요
- **Request Body**:
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
- **처리 로직**:
  1. `username`+`app_password`로 Bitbucket API 접근 검증 (`GET /2.0/repositories/{workspace}/{repo_slug}`)
  2. 중복 확인 (platform="bitbucket", platform_repo_id="{workspace}/{repo_slug}")
  3. Repository 레코드 생성 (app_password AES-256 암호화 저장)
  4. Bitbucket Webhook 자동 등록 (`POST /2.0/repositories/{workspace}/{repo_slug}/hooks`)
  5. 초기 스캔 큐 등록
- **Response** (201): 동일 형식 (platform: "bitbucket")
- **에러 케이스**:

| 코드 | 상황 |
|------|------|
| 401 | JWT 인증 실패 |
| 409 | 이미 등록된 저장소 |
| 422 | Bitbucket 자격증명 검증 실패 |

### 6-3. GitLab 저장소 목록 조회

#### `GET /api/v1/repos/gitlab/projects`
- **목적**: GitLab PAT로 접근 가능한 프로젝트 목록 조회
- **인증**: JWT 필요
- **Query Params**: `access_token: str`, `gitlab_url: str = "https://gitlab.com"`
- **Response** (200):
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

### 6-4. Bitbucket 저장소 목록 조회

#### `GET /api/v1/repos/bitbucket/repositories`
- **목적**: Bitbucket App Password로 접근 가능한 저장소 목록 조회
- **인증**: JWT 필요
- **Query Params**: `username: str`, `app_password: str`, `workspace: str`
- **Response** (200): 6-3과 동일 형식

### 6-5. GitLab Webhook 수신

#### `POST /api/v1/webhooks/gitlab`
- **목적**: GitLab Webhook 이벤트 수신 및 자동 스캔 트리거
- **인증**: `X-Gitlab-Token` 헤더 검증 (저장소별 `webhook_secret`과 상수 시간 비교)
- **지원 이벤트**:

| 이벤트 (X-Gitlab-Event) | 액션 | 처리 |
|--------------------------|------|------|
| `Push Hook` | - | 기본 브랜치 push + Python 파일 변경 시 스캔 트리거 |
| `Merge Request Hook` | open, update | MR 대상 변경 파일 중 Python 파일 있으면 스캔 트리거 |

- **Response** (202):
```json
{
    "message": "이벤트가 수신되었습니다.",
    "event": "merge_request",
    "scan_job_id": "uuid"
}
```
- **에러 케이스**:

| 코드 | 상황 |
|------|------|
| 403 | X-Gitlab-Token 검증 실패 |
| 400 | X-Gitlab-Event 헤더 누락 |

### 6-6. Bitbucket Webhook 수신

#### `POST /api/v1/webhooks/bitbucket`
- **목적**: Bitbucket Webhook 이벤트 수신 및 자동 스캔 트리거
- **인증**: `X-Hub-Signature` HMAC-SHA256 서명 검증 (저장소별 `webhook_secret` 사용)
- **지원 이벤트**:

| 이벤트 (X-Event-Key) | 처리 |
|-----------------------|------|
| `repo:push` | 기본 브랜치 push + Python 파일 변경 시 스캔 트리거 |
| `pullrequest:created` | PR 대상 변경 파일 중 Python 파일 있으면 스캔 트리거 |
| `pullrequest:updated` | 기존 PR 스캔 취소 후 새 스캔 등록 |

- **Response** (202): GitLab Webhook과 동일 형식
- **에러 케이스**:

| 코드 | 상황 |
|------|------|
| 403 | X-Hub-Signature 검증 실패 |
| 400 | X-Event-Key 헤더 누락 |

### 6-7. 기존 API 변경: GET /api/v1/repos

- **추가 Query Param**: `platform: str | None = None` ("github" | "gitlab" | "bitbucket")
- platform=None이면 모든 플랫폼 반환 (하위 호환)
- RepositoryResponse에 `platform` 필드 추가

## 7. 서비스 계층 설계

### 7-1. 공통 인터페이스: GitPlatformService (ABC)

```python
# backend/src/services/git_platform_service.py

from abc import ABC, abstractmethod
from pathlib import Path

class GitPlatformService(ABC):
    """Git 플랫폼 공통 인터페이스.

    GitHub/GitLab/Bitbucket 구현체가 이 계약을 따른다.
    """

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """자격증명 유효성 검증 (API 호출 테스트)"""

    @abstractmethod
    async def list_repositories(self) -> list[dict]:
        """접근 가능한 저장소 목록 조회"""

    @abstractmethod
    async def clone_repository(
        self, full_name: str, commit_sha: str, target_dir: Path
    ) -> None:
        """저장소 클론"""

    @abstractmethod
    async def get_changed_files(
        self, full_name: str, mr_or_pr_number: int
    ) -> list[str]:
        """MR/PR 변경 파일 목록 조회"""

    @abstractmethod
    async def get_default_branch_sha(
        self, full_name: str, branch: str
    ) -> str:
        """브랜치 최신 커밋 SHA 조회"""

    @abstractmethod
    async def create_branch(
        self, full_name: str, branch_name: str, base_sha: str
    ) -> None:
        """새 브랜치 생성"""

    @abstractmethod
    async def get_file_content(
        self, full_name: str, file_path: str, ref: str
    ) -> tuple[str, str]:
        """파일 내용 + blob SHA 조회. Returns: (content, sha)"""

    @abstractmethod
    async def create_file_commit(
        self, full_name: str, branch_name: str, file_path: str,
        content: str, message: str, file_sha: str
    ) -> dict:
        """파일 수정 커밋 생성"""

    @abstractmethod
    async def create_merge_request(
        self, full_name: str, head: str, base: str,
        title: str, body: str, labels: list[str] | None = None
    ) -> dict:
        """MR/PR 생성. Returns: {"number": int, "html_url": str}"""

    @abstractmethod
    async def register_webhook(
        self, full_name: str, webhook_url: str, secret: str, events: list[str]
    ) -> None:
        """Webhook 등록"""
```

### 7-2. 팩토리 함수

```python
# backend/src/services/platform_factory.py

from src.models.repository import Repository
from src.services.git_platform_service import GitPlatformService

def get_platform_service(repo: Repository) -> GitPlatformService:
    """Repository의 platform에 맞는 서비스 인스턴스를 반환한다.

    GitHub: 기존 GitHubAppService를 래핑한 GitHubPlatformService
    GitLab: PAT 기반 GitLabPlatformService
    Bitbucket: App Password 기반 BitbucketPlatformService
    """
    match repo.platform:
        case "github":
            from src.services.github_platform_service import GitHubPlatformService
            return GitHubPlatformService(installation_id=repo.installation_id)
        case "gitlab":
            from src.services.gitlab_service import GitLabPlatformService
            # platform_access_token_enc 복호화 필요
            return GitLabPlatformService(
                access_token=decrypt_token(repo.platform_access_token_enc),
                base_url=repo.platform_base_url or "https://gitlab.com",
            )
        case "bitbucket":
            from src.services.bitbucket_service import BitbucketPlatformService
            return BitbucketPlatformService(
                username=repo.external_username,
                app_password=decrypt_token(repo.platform_access_token_enc),
            )
        case _:
            raise ValueError(f"지원하지 않는 플랫폼: {repo.platform}")
```

### 7-3. GitLabPlatformService

- **인증**: Personal Access Token (`PRIVATE-TOKEN` 헤더)
- **API Base**: `{base_url}/api/v4`
- **주요 API 매핑**:

| ABC 메서드 | GitLab REST API v4 |
|-----------|-----------|
| `validate_credentials` | `GET /api/v4/user` |
| `list_repositories` | `GET /api/v4/projects?membership=true&per_page=100` |
| `clone_repository` | `git clone https://oauth2:{token}@gitlab.com/{full_name}.git` |
| `get_changed_files` | `GET /api/v4/projects/{id}/merge_requests/{mr_iid}/changes` |
| `get_default_branch_sha` | `GET /api/v4/projects/{id}/repository/branches/{branch}` |
| `create_branch` | `POST /api/v4/projects/{id}/repository/branches` |
| `get_file_content` | `GET /api/v4/projects/{id}/repository/files/{path}?ref={ref}` |
| `create_file_commit` | `PUT /api/v4/projects/{id}/repository/files/{path}` |
| `create_merge_request` | `POST /api/v4/projects/{id}/merge_requests` |
| `register_webhook` | `POST /api/v4/projects/{id}/hooks` |

### 7-4. BitbucketPlatformService

- **인증**: App Password (HTTP Basic Auth: `username:app_password`)
- **API Base**: `https://api.bitbucket.org/2.0`
- **주요 API 매핑**:

| ABC 메서드 | Bitbucket REST API 2.0 |
|-----------|-------------|
| `validate_credentials` | `GET /2.0/user` |
| `list_repositories` | `GET /2.0/repositories/{workspace}` |
| `clone_repository` | `git clone https://{username}:{app_password}@bitbucket.org/{full_name}.git` |
| `get_changed_files` | `GET /2.0/repositories/{workspace}/{slug}/pullrequests/{id}/diffstat` |
| `get_default_branch_sha` | `GET /2.0/repositories/{workspace}/{slug}/refs/branches/{branch}` |
| `create_branch` | `POST /2.0/repositories/{workspace}/{slug}/refs/branches` |
| `get_file_content` | `GET /2.0/repositories/{workspace}/{slug}/src/{commit}/{path}` |
| `create_file_commit` | `POST /2.0/repositories/{workspace}/{slug}/src` (form-data) |
| `create_merge_request` | `POST /2.0/repositories/{workspace}/{slug}/pullrequests` |
| `register_webhook` | `POST /2.0/repositories/{workspace}/{slug}/hooks` |

### 7-5. GitHubPlatformService (기존 래핑)

기존 `GitHubAppService`를 `GitPlatformService` ABC 구현체로 래핑한다. 내부적으로 `GitHubAppService` 인스턴스를 위임(delegation) 패턴으로 호출한다. 기존 코드는 변경하지 않고, 새 클래스가 기존 서비스를 래핑한다.

```python
# backend/src/services/github_platform_service.py

class GitHubPlatformService(GitPlatformService):
    """기존 GitHubAppService를 GitPlatformService ABC로 래핑."""

    def __init__(self, installation_id: int | None = None):
        self._github = GitHubAppService()
        self._installation_id = installation_id

    async def create_merge_request(self, full_name, head, base, title, body, labels=None):
        return await self._github.create_pull_request(
            full_name=full_name,
            installation_id=self._installation_id,
            head=head, base=base, title=title, body=body, labels=labels
        )
    # ... 나머지 메서드도 동일한 위임 패턴
```

## 8. 시퀀스 흐름

### 8-1. GitLab 저장소 연동 흐름

```
사용자 -> Frontend -> GET /repos/gitlab/projects?access_token=...
                         -> GitLab API: GET /projects?membership=true
                         -> Response: 프로젝트 목록
사용자 -> Frontend -> POST /repos/gitlab (project_id, access_token, ...)
                         -> GitLab API: GET /projects/{id} (PAT 검증)
                         -> DB: Repository 생성 (platform="gitlab", token 암호화)
                         -> GitLab API: POST /projects/{id}/hooks (Webhook 등록)
                         -> ScanOrchestrator: 초기 스캔 큐 등록
                         -> Response: 201 Created
```

### 8-2. GitLab MR 이벤트 기반 스캔 흐름

```
GitLab           Webhook Endpoint        WebhookHandler      Orchestrator     ScanWorker
  |                    |                       |                   |               |
  |-- MR Hook -------->|                       |                   |               |
  | (X-Gitlab-Token)   |                       |                   |               |
  |                    |-- verify token ------>|                   |               |
  |                    |<-- OK ---------------|                   |               |
  |                    |-- handle_gitlab_mr -->|                   |               |
  |                    |                       |-- get repo (DB) ->|               |
  |                    |                       |<-- repo ----------|               |
  |                    |                       |-- get_changed     |               |
  |                    |                       |   _files (GitLab) |               |
  |                    |                       |-- enqueue ------->|               |
  |                    |                       |                   |-- scan job -->|
  |                    |                       |                   |               |
  |                    |                       |                   |     [Semgrep + LLM]
  |                    |                       |                   |               |
  |<-- MR created (패치) ----------------------------------------------- GitLab API|
```

### 8-3. 패치 MR/PR 생성 (플랫폼 분기)

```
ScanWorker      PatchGenerator      PlatformFactory     GitLab/Bitbucket Service
  |                   |                   |                       |
  |-- generate ------>|                   |                       |
  |                   |-- get_platform    |                       |
  |                   |   _service(repo)->|                       |
  |                   |<-- client --------|                       |
  |                   |                                           |
  |                   |-- create_branch ------ (ABC method) ----->|
  |                   |-- get_file_content --- (ABC method) ----->|
  |                   |-- create_file_commit - (ABC method) ----->|
  |                   |-- create_merge_request (ABC method) ----->|
  |                   |                                           |
  |                   |-- DB: PatchPR 저장 (platform_pr_*)        |
```

## 9. 환경변수 추가

```bash
# GitLab Webhook 서명 (글로벌 기본값; 저장소별 webhook_secret 우선)
GITLAB_WEBHOOK_SECRET=your-gitlab-webhook-secret

# Bitbucket Webhook 서명 (글로벌 기본값; 저장소별 webhook_secret 우선)
BITBUCKET_WEBHOOK_SECRET=your-bitbucket-webhook-secret

# AES-256 암호화 키 (PAT/App Password 암호화용; 기존 키 재사용 가능)
# ENCRYPTION_KEY=your-32-byte-encryption-key (이미 존재하면 재사용)
```

GitLab PAT와 Bitbucket App Password는 연동 시 사용자가 입력하며, `repository.platform_access_token_enc`에 AES-256 암호화하여 DB에 저장한다.

## 10. 영향 범위

### 수정 필요 파일

| 파일 | 변경 내용 |
|------|----------|
| `backend/src/models/repository.py` | `platform`, `platform_repo_id`, `platform_url`, `platform_access_token_enc`, `external_username`, `platform_base_url` 컬럼 추가 |
| `backend/src/models/patch_pr.py` | `platform_pr_number`, `platform_pr_url` 컬럼 추가 |
| `backend/src/schemas/repository.py` | `RepositoryRegisterRequest`에 `platform` 필드 추가, `RepositoryResponse`에 `platform` 필드 추가 |
| `backend/src/api/v1/repos.py` | `register_repo`에 platform 분기, `list_repos`에 platform 필터, GitLab/Bitbucket 연동 엔드포인트 추가 |
| `backend/src/api/v1/webhooks.py` | 기존 파일은 GitHub 전용으로 유지 (변경 없음) |
| `backend/src/api/v1/router.py` | GitLab/Bitbucket webhook 라우터, repos/gitlab, repos/bitbucket 라우터 등록 |
| `backend/src/services/patch_generator.py` | `self._github_service` -> `get_platform_service(repo)` 팩토리 사용. `_create_patch_pr_for_result`에서 Repository 객체 수신하여 플랫폼 분기 |
| `backend/src/workers/scan_worker.py` | `GitHubAppService()` -> `get_platform_service(repo)` 팩토리 사용 (clone, PR 생성) |
| `backend/src/services/webhook_handler.py` | `handle_gitlab_push`, `handle_gitlab_mr`, `handle_bitbucket_push`, `handle_bitbucket_pr` 메서드 추가 |
| `backend/src/config.py` | `GITLAB_WEBHOOK_SECRET`, `BITBUCKET_WEBHOOK_SECRET` 환경변수 추가 |

### 신규 생성 파일

| 파일 | 설명 |
|------|------|
| `backend/src/services/git_platform_service.py` | GitPlatformService ABC 정의 |
| `backend/src/services/platform_factory.py` | `get_platform_service()` 팩토리 함수 |
| `backend/src/services/github_platform_service.py` | GitHubPlatformService (기존 GitHubAppService 래핑) |
| `backend/src/services/gitlab_service.py` | GitLabPlatformService 구현 (PAT + REST API v4) |
| `backend/src/services/bitbucket_service.py` | BitbucketPlatformService 구현 (App Password + REST API 2.0) |
| `backend/src/api/v1/webhooks_gitlab.py` | GitLab Webhook 엔드포인트 + `X-Gitlab-Token` 검증 |
| `backend/src/api/v1/webhooks_bitbucket.py` | Bitbucket Webhook 엔드포인트 + `X-Hub-Signature` 검증 |
| `backend/src/schemas/gitlab.py` | GitLab 연동 요청/응답 Pydantic 스키마 |
| `backend/src/schemas/bitbucket.py` | Bitbucket 연동 요청/응답 Pydantic 스키마 |
| `backend/alembic/versions/xxxx_f09_multi_platform.py` | DB 마이그레이션 |

## 11. 성능 설계

### 인덱스 계획

```sql
-- 플랫폼별 저장소 조회 최적화
CREATE INDEX idx_repository_platform ON repository(platform);

-- 플랫폼 + 저장소 ID 복합 유니크
CREATE UNIQUE INDEX uq_repository_platform_repo_id
    ON repository(platform, platform_repo_id)
    WHERE platform_repo_id IS NOT NULL;
```

### 캐싱 전략
- 저장소 목록 조회 (GitLab/Bitbucket): Redis 캐시 TTL 5분 (PoC에서는 미적용, DB 직접 조회)
- PAT/App Password: DB에서 요청 시 복호화. 인메모리 캐시 불필요 (보안상 메모리에 오래 유지하지 않음)

### Rate Limit 대응
- GitLab: 인증 사용자 분당 300 요청. httpx retry 3회 (exponential backoff)
- Bitbucket: 분당 1,000 요청. httpx retry 3회
- 패치 MR/PR 생성: `asyncio.Semaphore(3)` 유지 (기존 GitHub 패턴 동일)

## 변경 이력

| 날짜 | 변경 내용 | 이유 |
|------|----------|------|
| 2026-02-25 | 초안 작성 | M3-A 병렬 배치 설계 |
| 2026-02-25 | 인증 방식 변경: GitLab OAuth -> PAT, Bitbucket OAuth -> App Password | 사용자 설계 지침 반영. PoC 단계 단순화 |
| 2026-02-25 | credential 별도 테이블 -> repository 테이블 내 컬럼으로 통합 | PoC 단계 설계 단순화 |
