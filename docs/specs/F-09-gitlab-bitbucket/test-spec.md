# F-09: GitLab/Bitbucket 연동 -- 테스트 명세

## 참조
- 설계서: docs/specs/F-09-gitlab-bitbucket/design.md
- 인수조건: docs/project/features.md #F-09

## 인수조건 매핑

| 인수조건 | 테스트 케이스 |
|----------|---------------|
| GitLab Integration으로 저장소 연동 가능 | I-0901, I-0902, I-0903 |
| Bitbucket App으로 저장소 연동 가능 | I-0904, I-0905, I-0906 |
| GitLab Merge Request 이벤트 기반 자동 스캔 | I-0907, I-0908, I-0909 |
| Bitbucket Pull Request 이벤트 기반 자동 스캔 | I-0910, I-0911, I-0912 |
| GitLab/Bitbucket 대상 자동 패치 MR/PR 생성 | I-0913, I-0914, I-0915 |
| 플랫폼 간 통합 대시보드에서 관리 | I-0916, I-0917, I-0918 |

---

## 단위 테스트

### GitPlatformService 팩토리

| ID | 대상 | 시나리오 | 입력 | 예상 결과 |
|----|------|----------|------|-----------|
| U-0901 | `get_platform_service()` | platform="github" Repository 전달 | `repo.platform="github"` | `GitHubPlatformService` 인스턴스 반환 |
| U-0902 | `get_platform_service()` | platform="gitlab" Repository 전달 | `repo.platform="gitlab"` | `GitLabPlatformService` 인스턴스 반환 |
| U-0903 | `get_platform_service()` | platform="bitbucket" Repository 전달 | `repo.platform="bitbucket"` | `BitbucketPlatformService` 인스턴스 반환 |
| U-0904 | `get_platform_service()` | 미지원 플랫폼 전달 | `repo.platform="svn"` | `ValueError` 발생 |

### GitLabPlatformService

| ID | 대상 | 시나리오 | Arrange | Act | Assert |
|----|------|----------|---------|-----|--------|
| U-0905 | `validate_credentials()` | PAT 유효 | httpx mock: `GET /api/v4/user` -> 200 | `validate_credentials()` | `True` 반환 |
| U-0906 | `validate_credentials()` | PAT 무효 | httpx mock: `GET /api/v4/user` -> 401 | `validate_credentials()` | `False` 반환 |
| U-0907 | `list_repositories()` | 정상 응답 | httpx mock: 200 + 프로젝트 JSON 배열 | `list_repositories()` | `[{"platform_repo_id": "123", "full_name": "group/repo", ...}]` 반환 |
| U-0908 | `list_repositories()` | 페이지네이션 처리 | httpx mock: page1(20건, `x-next-page: 2`) + page2(5건) | `list_repositories()` | 25건 반환 |
| U-0909 | `get_changed_files()` | MR 변경 파일 조회 | httpx mock: MR changes 응답 (`changes[].new_path`) | `get_changed_files(full_name, mr_iid)` | 변경 파일 경로 목록 반환 |
| U-0910 | `create_merge_request()` | MR 생성 성공 | httpx mock: 201 + MR JSON | `create_merge_request(full_name, ...)` | `{"number": iid, "html_url": web_url}` 반환 |
| U-0911 | `create_merge_request()` | GitLab API 오류 | httpx mock: 422 | `create_merge_request(full_name, ...)` | `httpx.HTTPStatusError` 발생 |
| U-0912 | `register_webhook()` | Webhook 등록 성공 | httpx mock: 201 | `register_webhook(full_name, url, secret, events)` | 정상 완료, 에러 없음 |
| U-0913 | `get_file_content()` | 파일 내용 조회 | httpx mock: 200 + base64 content JSON | `get_file_content(full_name, path, ref)` | `(decoded_content, blob_sha)` 튜플 반환 |
| U-0914 | `create_branch()` | 브랜치 생성 성공 | httpx mock: 201 | `create_branch(full_name, name, sha)` | 정상 완료 |
| U-0915 | `create_file_commit()` | 파일 수정 커밋 | httpx mock: 200 | `create_file_commit(full_name, ...)` | 커밋 결과 dict 반환 |
| U-0916 | `clone_repository()` | 클론 성공 | subprocess mock: `git clone` 성공 | `clone_repository(full_name, sha, dir)` | target_dir에 파일 존재 |

### BitbucketPlatformService

| ID | 대상 | 시나리오 | Arrange | Act | Assert |
|----|------|----------|---------|-----|--------|
| U-0917 | `validate_credentials()` | App Password 유효 | httpx mock: `GET /2.0/user` -> 200 (Basic Auth) | `validate_credentials()` | `True` 반환 |
| U-0918 | `validate_credentials()` | App Password 무효 | httpx mock: `GET /2.0/user` -> 401 | `validate_credentials()` | `False` 반환 |
| U-0919 | `list_repositories()` | 정상 응답 | httpx mock: 200 + repos JSON (`values[]`) | `list_repositories()` | 저장소 목록 반환 |
| U-0920 | `list_repositories()` | 페이지네이션 (`next` URL) | httpx mock: page1 with `next` + page2 | `list_repositories()` | 전체 저장소 병합 반환 |
| U-0921 | `get_changed_files()` | PR diffstat 조회 | httpx mock: diffstat 응답 (`values[].new.path`) | `get_changed_files(full_name, pr_id)` | 변경 파일 경로 목록 반환 |
| U-0922 | `create_merge_request()` | PR 생성 성공 | httpx mock: 201 + PR JSON | `create_merge_request(full_name, ...)` | `{"number": id, "html_url": links.html.href}` 반환 |
| U-0923 | `register_webhook()` | Webhook 등록 성공 | httpx mock: 201 | `register_webhook(full_name, url, secret, events)` | 정상 완료 |
| U-0924 | `create_branch()` | 브랜치 생성 성공 | httpx mock: 201 | `create_branch(full_name, name, sha)` | 정상 완료 |
| U-0925 | `create_file_commit()` | form-data 커밋 | httpx mock: 201 | `create_file_commit(full_name, ...)` | 커밋 결과 dict 반환 |

### Webhook 서명 검증

| ID | 대상 | 시나리오 | Arrange | Act | Assert |
|----|------|----------|---------|-----|--------|
| U-0926 | `_verify_gitlab_token()` | 유효한 토큰 | secret="abc123", header="abc123" | `_verify_gitlab_token(header, secret)` | `True` |
| U-0927 | `_verify_gitlab_token()` | 토큰 불일치 | secret="abc123", header="wrong" | `_verify_gitlab_token(header, secret)` | `False` |
| U-0928 | `_verify_gitlab_token()` | 헤더 없음 (None) | secret="abc123", header=None | `_verify_gitlab_token(None, secret)` | `False` |
| U-0929 | `_verify_gitlab_token()` | 타이밍 공격 방지 | secret="abc123", header="abc124" | `hmac.compare_digest` 사용 확인 | 상수 시간 비교 |
| U-0930 | `_verify_bitbucket_signature()` | 유효한 HMAC-SHA256 | payload bytes, secret, 올바른 `sha256=...` 서명 | `_verify_bitbucket_signature(payload, sig, secret)` | `True` |
| U-0931 | `_verify_bitbucket_signature()` | 서명 불일치 | payload bytes, secret, 잘못된 서명 | `_verify_bitbucket_signature(payload, sig, secret)` | `False` |
| U-0932 | `_verify_bitbucket_signature()` | 서명 헤더 없음 | payload bytes, secret, header=None | `_verify_bitbucket_signature(payload, None, secret)` | `False` |

### WebhookHandler (GitLab/Bitbucket)

| ID | 대상 | 시나리오 | Arrange | Act | Assert |
|----|------|----------|---------|-----|--------|
| U-0933 | `handle_gitlab_push()` | 기본 브랜치 Push + Python 파일 | GitLab push payload (ref="refs/heads/main"), repo DB 존재 | `handle_gitlab_push(payload)` | ScanJob ID 반환, orchestrator.enqueue_scan 호출됨 |
| U-0934 | `handle_gitlab_push()` | 비기본 브랜치 Push | GitLab push payload (ref="refs/heads/feature") | `handle_gitlab_push(payload)` | `None` 반환 |
| U-0935 | `handle_gitlab_push()` | Python 파일 없는 Push | GitLab push payload (commits에 .js만) | `handle_gitlab_push(payload)` | `None` 반환 |
| U-0936 | `handle_gitlab_push()` | 미등록 저장소 Push | GitLab push payload, repo DB 없음 | `handle_gitlab_push(payload)` | `None` 반환 |
| U-0937 | `handle_gitlab_mr()` | MR open + Python 파일 | GitLab MR payload (object_attributes.action="open"), GitLab API mock (변경파일) | `handle_gitlab_mr(payload, "open")` | ScanJob ID 반환 |
| U-0938 | `handle_gitlab_mr()` | MR update + 기존 스캔 취소 | GitLab MR payload (action="update"), 기존 스캔 queued 상태 | `handle_gitlab_mr(payload, "update")` | 기존 ScanJob cancelled, 새 ScanJob ID 반환 |
| U-0939 | `handle_gitlab_mr()` | MR close -> 무시 | GitLab MR payload (action="close") | `handle_gitlab_mr(payload, "close")` | `None` 반환 |
| U-0940 | `handle_bitbucket_push()` | 기본 브랜치 Push + Python 파일 | Bitbucket push payload, repo DB 존재 | `handle_bitbucket_push(payload)` | ScanJob ID 반환 |
| U-0941 | `handle_bitbucket_push()` | 비기본 브랜치 Push | Bitbucket push payload (feature branch) | `handle_bitbucket_push(payload)` | `None` 반환 |
| U-0942 | `handle_bitbucket_pr()` | PR created + Python 파일 | Bitbucket PR created payload | `handle_bitbucket_pr(payload, "created")` | ScanJob ID 반환 |
| U-0943 | `handle_bitbucket_pr()` | PR updated + 기존 스캔 취소 | Bitbucket PR updated payload, 기존 스캔 존재 | `handle_bitbucket_pr(payload, "updated")` | 기존 스캔 cancelled, 새 ScanJob ID 반환 |

### PatchGenerator 플랫폼 분기

| ID | 대상 | 시나리오 | Arrange | Act | Assert |
|----|------|----------|---------|-----|--------|
| U-0944 | `PatchGenerator` | GitLab 저장소 대상 패치 MR 생성 | repo.platform="gitlab", GitLabPlatformService mock | `generate_patch_prs(...)` | `GitLabPlatformService.create_merge_request` 호출됨, PatchPR.platform_pr_url에 gitlab.com 포함 |
| U-0945 | `PatchGenerator` | Bitbucket 저장소 대상 패치 PR 생성 | repo.platform="bitbucket", BitbucketPlatformService mock | `generate_patch_prs(...)` | `BitbucketPlatformService.create_merge_request` 호출됨, PatchPR.platform_pr_url에 bitbucket.org 포함 |
| U-0946 | `PatchGenerator` | GitHub 저장소 대상 기존 동작 유지 | repo.platform="github", GitHubPlatformService mock | `generate_patch_prs(...)` | `GitHubPlatformService.create_merge_request` 호출됨, PatchPR.github_pr_url 설정됨 |

### Repository 모델

| ID | 대상 | 시나리오 | Arrange | Act | Assert |
|----|------|----------|---------|-----|--------|
| U-0947 | `Repository` | platform 기본값 | 새 Repository 생성 (platform 미지정) | `Repository(full_name="org/repo", ...)` | `platform == "github"` |
| U-0948 | `Repository` | GitLab 저장소 생성 | platform="gitlab" 지정 | `Repository(platform="gitlab", platform_repo_id="123", ...)` | DB 저장 후 조회 시 platform="gitlab", platform_repo_id="123" |
| U-0949 | `Repository` | Bitbucket 저장소 생성 | platform="bitbucket" 지정 | `Repository(platform="bitbucket", external_username="user", ...)` | DB 저장 후 조회 시 external_username="user" |

---

## 통합 테스트

### GitLab 저장소 연동

| ID | API | 시나리오 | Arrange | Act | Assert |
|----|-----|----------|---------|-----|--------|
| I-0901 | `GET /repos/gitlab/projects` | GitLab 프로젝트 목록 조회 | 인증된 사용자, GitLab API mock | `GET /api/v1/repos/gitlab/projects?access_token=glpat-xxx&gitlab_url=https://gitlab.com` | 200, 프로젝트 목록 반환, `already_connected` 플래그 정확 |
| I-0902 | `POST /repos/gitlab` | GitLab 저장소 연동 성공 | 인증된 사용자, GitLab PAT 유효, 미등록 저장소 | `POST /api/v1/repos/gitlab` + body | 201, Repository 생성 (platform="gitlab"), ScanJob queued |
| I-0903 | `POST /repos/gitlab` | 중복 연동 시도 | 이미 등록된 GitLab 저장소 | `POST /api/v1/repos/gitlab` + 동일 project_id | 409, "이미 등록된 저장소" |

### Bitbucket 저장소 연동

| ID | API | 시나리오 | Arrange | Act | Assert |
|----|-----|----------|---------|-----|--------|
| I-0904 | `GET /repos/bitbucket/repositories` | Bitbucket 저장소 목록 조회 | 인증된 사용자, Bitbucket API mock | `GET /api/v1/repos/bitbucket/repositories?username=user&app_password=xxx&workspace=ws` | 200, 저장소 목록 반환 |
| I-0905 | `POST /repos/bitbucket` | Bitbucket 저장소 연동 성공 | 인증된 사용자, App Password 유효, 미등록 저장소 | `POST /api/v1/repos/bitbucket` + body | 201, Repository 생성 (platform="bitbucket"), ScanJob queued |
| I-0906 | `POST /repos/bitbucket` | 잘못된 자격증명 | 인증된 사용자, Bitbucket API mock 401 반환 | `POST /api/v1/repos/bitbucket` + 잘못된 credentials | 422, "자격증명 검증 실패" |

### GitLab Webhook 기반 자동 스캔

| ID | API | 시나리오 | Arrange | Act | Assert |
|----|-----|----------|---------|-----|--------|
| I-0907 | `POST /webhooks/gitlab` | Push Hook -> 스캔 트리거 | GitLab repo DB 등록, 유효한 X-Gitlab-Token | Push Hook payload 전송 | 202, `scan_job_id` 반환, DB에 ScanJob status="queued" |
| I-0908 | `POST /webhooks/gitlab` | MR Hook (open) -> 스캔 트리거 | GitLab repo 등록, GitLab API mock (MR 변경 파일 Python 포함) | MR Hook payload (action=open) | 202, `scan_job_id` 반환, ScanJob trigger_type="webhook" |
| I-0909 | `POST /webhooks/gitlab` | 잘못된 X-Gitlab-Token | 잘못된 토큰 | Push Hook payload | 403, "Webhook 서명 검증 실패" |

### Bitbucket Webhook 기반 자동 스캔

| ID | API | 시나리오 | Arrange | Act | Assert |
|----|-----|----------|---------|-----|--------|
| I-0910 | `POST /webhooks/bitbucket` | repo:push -> 스캔 트리거 | Bitbucket repo DB 등록, 유효한 X-Hub-Signature | Push payload (X-Event-Key: repo:push) | 202, `scan_job_id` 반환 |
| I-0911 | `POST /webhooks/bitbucket` | pullrequest:created -> 스캔 트리거 | Bitbucket repo 등록, Bitbucket API mock (PR 변경 파일 Python 포함) | PR payload (X-Event-Key: pullrequest:created) | 202, `scan_job_id` 반환 |
| I-0912 | `POST /webhooks/bitbucket` | 잘못된 HMAC 서명 | 잘못된 X-Hub-Signature | payload | 403 |

### 패치 MR/PR 생성

| ID | API | 시나리오 | Arrange | Act | Assert |
|----|-----|----------|---------|-----|--------|
| I-0913 | 스캔 파이프라인 | GitLab 대상 패치 MR 자동 생성 | GitLab repo, Semgrep 취약점 탐지, LLM 패치 생성, GitLab API mock | 스캔 완료 후 PatchGenerator 실행 | PatchPR 레코드 생성, `platform_pr_url`에 gitlab.com 포함, `platform_pr_number` 설정 |
| I-0914 | 스캔 파이프라인 | Bitbucket 대상 패치 PR 자동 생성 | Bitbucket repo, Semgrep 취약점 탐지, LLM 패치 생성, Bitbucket API mock | 스캔 완료 후 PatchGenerator 실행 | PatchPR 레코드 생성, `platform_pr_url`에 bitbucket.org 포함 |
| I-0915 | `POST /repos/gitlab` | GitLab 연동 등록 + 초기 스캔 + Webhook 등록 | GitLab PAT 유효, GitLab API mock | `POST /api/v1/repos/gitlab` | 201, Repository 생성, ScanJob queued, GitLab Webhook 등록 API 호출됨 |

### 통합 대시보드

| ID | API | 시나리오 | Arrange | Act | Assert |
|----|-----|----------|---------|-----|--------|
| I-0916 | `GET /dashboard/summary` | 모든 플랫폼 통합 집계 | GitHub 2개 + GitLab 2개 + Bitbucket 1개 저장소, 각각 취약점 보유 | `GET /api/v1/dashboard/summary` | `repo_count=5`, `total_vulnerabilities`에 모든 플랫폼 합산 |
| I-0917 | `GET /repos` | platform 필터 없이 전체 조회 | 다양한 플랫폼 저장소 | `GET /api/v1/repos` | 응답에 `platform` 필드 포함, 모든 플랫폼 저장소 반환 |
| I-0918 | `GET /repos?platform=gitlab` | platform 필터로 GitLab만 조회 | GitHub 2개 + GitLab 2개 저장소 | `GET /api/v1/repos?platform=gitlab` | GitLab 저장소 2개만 반환 |

---

## 경계 조건 / 에러 케이스

- GitLab Self-managed 인스턴스 URL에 트레일링 슬래시가 있는 경우 (`https://gitlab.example.com/`) 정규화 처리 (`rstrip('/')`)
- GitLab PAT 만료 시 API 호출 401 -> 사용자에게 PAT 갱신 안내 응답
- Bitbucket App Password 권한 부족 시 API 호출 403 -> 필요 권한 목록 안내
- GitLab/Bitbucket API rate limit 초과 시 429 -> httpx retry (exponential backoff, 최대 3회)
- 동일 저장소를 GitHub와 GitLab에서 이중 등록 시도 -> 허용 (platform별 별도 관리)
- `platform_repo_id`가 NULL인 기존 GitHub 저장소와의 유니크 제약조건 충돌 방지 (WHERE 조건부 유니크)
- Webhook payload에 알 수 없는 이벤트 타입 -> 200으로 무시 (에러 발생하지 않음)
- GitLab MR의 WIP/Draft 상태도 스캔 대상에 포함
- `platform_access_token_enc` 복호화 실패 시 (키 변경 등) -> 500 대신 사용자에게 재연동 안내
- Bitbucket workspace 이름에 특수문자 포함 시 URL 인코딩 처리

---

## 회귀 테스트

| 기존 기능 | 영향 여부 | 검증 방법 |
|-----------|-----------|-----------|
| F-01 GitHub 저장소 연동 | 영향 있음 (Repository 모델 변경) | 기존 GitHub 저장소 CRUD 테스트 재실행. `platform="github"` 기본값 + `github_repo_id` 기존 동작 확인 |
| F-01 GitHub Webhook | 영향 없음 (별도 엔드포인트 `/webhooks/github` 유지) | 기존 GitHub Webhook 수신 + 서명 검증 테스트 재실행 |
| F-03 패치 PR 생성 | 영향 있음 (PatchGenerator 팩토리 패턴으로 리팩터링) | GitHub repo 대상 패치 PR 생성 기존 테스트 재실행. `GitHubPlatformService`를 통한 기존 흐름 동일 동작 확인 |
| F-04 스캔 결과 API | 영향 없음 | 기존 스캔 결과 API 테스트 재실행 |
| F-07 대시보드 | 영향 있음 (다중 플랫폼 저장소 집계) | 기존 대시보드 통계 테스트 재실행 + `platform` 필드 포함 검증 |
| F-08 알림 | 영향 미미 | 기존 알림 테스트 재실행. 알림 메시지에 플랫폼 정보 포함 확인 |
