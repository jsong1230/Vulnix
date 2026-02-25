# F-01: 저장소 연동 및 스캔 트리거 -- 기술 설계서

## 1. 참조

- 인수조건: `docs/project/features.md` #F-01
- 시스템 설계: `docs/system/system-design.md`

---

## 2. 구현 범위

### 2-1. 백엔드 수정 파일

| 파일 | 변경 내용 |
|------|-----------|
| `backend/src/api/v1/webhooks.py` | push / pull_request / installation 이벤트 핸들러 구현 |
| `backend/src/api/v1/repos.py` | 저장소 목록 조회, 연동 등록, 연동 해제 엔드포인트 구현 |
| `backend/src/api/v1/scans.py` | 수동 스캔 트리거 엔드포인트 구현 |
| `backend/src/services/github_app.py` | JWT 생성, Installation Token 발급, 저장소 목록 조회 |
| `backend/src/services/scan_orchestrator.py` | enqueue_scan 실제 큐 등록, 재시도 로직 |
| `backend/src/schemas/repository.py` | 연동 해제 스키마, GitHub Installation 콜백 스키마 추가 |
| `backend/src/models/repository.py` | `retry_count`, `is_initial_scan_done` 컬럼 추가 검토 |

### 2-2. 백엔드 신규 파일

| 파일 | 역할 |
|------|------|
| `backend/src/services/webhook_handler.py` | Webhook 이벤트별 비즈니스 로직 (webhooks.py에서 분리) |
| `backend/src/schemas/webhook.py` | Webhook 페이로드 Pydantic 스키마 |

### 2-3. 프론트엔드 수정 파일

| 파일 | 변경 내용 |
|------|-----------|
| `frontend/src/app/repos/page.tsx` | 저장소 목록 API 연동, 수동 스캔 버튼, 연동 해제 버튼 |
| `frontend/src/app/repos/[id]/page.tsx` | 수동 스캔 트리거 버튼 추가 |
| `frontend/src/lib/api-client.ts` | 저장소/스캔 관련 API 호출 헬퍼 함수 추가 |

### 2-4. 프론트엔드 신규 파일

| 파일 | 역할 |
|------|------|
| `frontend/src/app/repos/connect/page.tsx` | GitHub App 설치 완료 후 콜백 페이지 |
| `frontend/src/components/repos/scan-trigger-button.tsx` | 수동 스캔 트리거 버튼 컴포넌트 |
| `frontend/src/components/repos/disconnect-dialog.tsx` | 연동 해제 확인 다이얼로그 |

---

## 3. 아키텍처 결정

### 결정 1: Webhook 이벤트 핸들링 구조

- **선택지**: A) webhooks.py에 모든 로직 인라인 / B) webhook_handler.py 서비스 분리
- **결정**: B) 서비스 분리
- **근거**: webhooks.py는 HTTP 관심사(서명 검증, 헤더 파싱)만 담당하고, 비즈니스 로직(DB 조회, 스캔 큐 등록)은 webhook_handler.py로 분리하여 단위 테스트 용이성 확보. 기존 스캐폴딩의 TODO 분기 구조를 유지하되 핸들러를 호출하는 형태로 변경.

### 결정 2: GitHub App JWT 생성 라이브러리

- **선택지**: A) python-jose / B) PyJWT (pyjwt) / C) 직접 구현
- **결정**: B) PyJWT
- **근거**: GitHub App JWT는 RS256 서명이 필요하며, PyJWT는 cryptography 백엔드로 RS256을 지원한다. python-jose도 가능하지만 PyJWT가 더 가볍고 GitHub 공식 문서 예제에서도 사용한다. 기존 config.py에 이미 `GITHUB_APP_PRIVATE_KEY` PEM이 준비되어 있어 바로 적용 가능.

### 결정 3: Installation Token 캐싱 전략

- **선택지**: A) Redis에 캐싱 / B) 인메모리(TTL dict) / C) 매번 발급
- **결정**: B) 인메모리 TTL dict
- **근거**: PoC 단계에서는 단일 프로세스이므로 인메모리로 충분. Installation Token은 1시간 유효하므로 만료 5분 전에 갱신하는 TTL 캐시를 사용한다. 향후 멀티 프로세스 환경에서는 Redis로 전환.

### 결정 4: 초기 스캔 트리거 방식

- **선택지**: A) installation.created Webhook에서 즉시 스캔 큐 등록 / B) 저장소 등록 API에서 명시적 트리거
- **결정**: A) installation.created에서 자동 트리거
- **근거**: 인수조건 "연동 후 첫 실행 시 전체 코드베이스 초기 스캔 수행"을 자연스럽게 구현. GitHub App 설치 시 자동으로 초기 스캔이 시작되어 사용자 경험이 좋다. Repository 모델에 `is_initial_scan_done` 플래그를 추가하여 초기 스캔 완료 여부를 추적한다.

### 결정 5: Webhook 재시도 범위

- **선택지**: A) GitHub 자체 Webhook 재시도에 의존 / B) 앱 내부에서 스캔 큐 등록 실패 시 재시도 / C) 둘 다
- **결정**: C) 둘 다 활용
- **근거**: 인수조건 "Webhook 수신 실패 시 재시도 로직 동작 (최대 3회)"를 충족하려면, (1) GitHub의 Webhook 재전송 메커니즘(응답 코드 500일 때 재시도)을 활용하고, (2) 앱 내부적으로 스캔 큐 등록 실패 시 RQ의 `Retry(max=3)` 메커니즘을 통해 재시도한다. 이중 안전망.

---

## 4. API 설계

### 4-1. POST /api/v1/webhooks/github

**목적**: GitHub Webhook 이벤트 수신 (서명 검증 후 이벤트별 처리)
**인증**: HMAC-SHA256 서명 검증 (Bearer JWT 아님)

**Request Headers**:
```
X-GitHub-Event: push | pull_request | installation | ping
X-Hub-Signature-256: sha256=<hex_digest>
X-GitHub-Delivery: <uuid>
Content-Type: application/json
```

**Response (202 Accepted)**:
```json
{
  "message": "이벤트가 수신되었습니다.",
  "event": "push",
  "delivery": "<delivery_id>",
  "scan_job_id": "uuid (스캔 트리거된 경우)"
}
```

**에러 케이스**:

| 코드 | 상황 |
|------|------|
| 403 | HMAC-SHA256 서명 검증 실패 |
| 400 | X-GitHub-Event 헤더 누락 |
| 404 | 등록되지 않은 저장소의 이벤트 |
| 500 | 내부 처리 오류 (GitHub가 자동 재시도) |

---

### 4-2. GET /api/v1/repos

**목적**: 현재 사용자 팀의 연동 저장소 목록 조회
**인증**: Bearer JWT 필요

**Query Parameters**:

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| page | int | 1 | 페이지 번호 |
| per_page | int | 20 | 페이지당 항목 수 (max: 100) |
| is_active | bool | None | 활성화 여부 필터 |

**Response (200)**:
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

---

### 4-3. POST /api/v1/repos

**목적**: 저장소 연동 등록
**인증**: Bearer JWT 필요

**Request Body** (기존 `RepositoryRegisterRequest` 사용):
```json
{
  "github_repo_id": 123456,
  "full_name": "org/repo-name",
  "default_branch": "main",
  "language": "Python",
  "installation_id": 789
}
```

**Response (201 Created)**:
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

**에러 케이스**:

| 코드 | 상황 |
|------|------|
| 400 | 유효하지 않은 요청 (필수 필드 누락) |
| 401 | 인증 실패 |
| 409 | 이미 등록된 저장소 (github_repo_id 중복) |
| 403 | GitHub API로 저장소 접근 권한 확인 실패 |

---

### 4-4. DELETE /api/v1/repos/{repo_id} (신규)

**목적**: 저장소 연동 해제 및 관련 데이터 정리
**인증**: Bearer JWT 필요 (팀 owner/admin 권한)

**Response (200)**:
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

**에러 케이스**:

| 코드 | 상황 |
|------|------|
| 401 | 인증 실패 |
| 403 | 권한 부족 (member 역할) |
| 404 | 저장소 없음 |

---

### 4-5. GET /api/v1/repos/github/installations (신규)

**목적**: GitHub App 설치 후 접근 가능한 저장소 목록 조회 (연동 전 목록)
**인증**: Bearer JWT 필요

**Response (200)**:
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

### 4-6. POST /api/v1/scans (기존 스캐폴딩)

**목적**: 수동 스캔 트리거
**인증**: Bearer JWT 필요

**Request Body** (기존 `ScanTriggerRequest` 사용):
```json
{
  "repo_id": "uuid",
  "branch": "main",
  "commit_sha": null
}
```

**Response (202 Accepted)**:
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "repo_id": "uuid",
    "status": "queued",
    "trigger_type": "manual",
    "commit_sha": "a1b2c3d...",
    "branch": "main",
    "pr_number": null,
    "findings_count": 0,
    "true_positives_count": 0,
    "false_positives_count": 0,
    "duration_seconds": null,
    "error_message": null,
    "started_at": null,
    "completed_at": null,
    "created_at": "2026-02-25T10:00:00Z"
  },
  "error": null
}
```

**에러 케이스**:

| 코드 | 상황 |
|------|------|
| 401 | 인증 실패 |
| 403 | 해당 저장소에 접근 권한 없음 |
| 404 | 저장소 없음 |
| 422 | 유효하지 않은 commit_sha 형식 |
| 429 | 동일 저장소 스캔이 이미 진행 중 |

---

## 5. DB 설계

### 5-1. Repository 테이블 변경

기존 `repository` 테이블에 다음 컬럼 추가:

| 컬럼 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `is_initial_scan_done` | BOOLEAN | false | 초기 전체 스캔 완료 여부 |

**Alembic 마이그레이션**:
```sql
ALTER TABLE repository ADD COLUMN is_initial_scan_done BOOLEAN NOT NULL DEFAULT false;
```

### 5-2. ScanJob 테이블 변경

기존 `scan_job` 테이블에 다음 컬럼 추가:

| 컬럼 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `retry_count` | INTEGER | 0 | 현재 재시도 횟수 |
| `scan_type` | VARCHAR(20) | 'incremental' | 스캔 유형 (initial / incremental / pr) |
| `changed_files` | JSONB | null | PR/push 시 변경된 파일 목록 |

**Alembic 마이그레이션**:
```sql
ALTER TABLE scan_job ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE scan_job ADD COLUMN scan_type VARCHAR(20) NOT NULL DEFAULT 'incremental';
ALTER TABLE scan_job ADD COLUMN changed_files JSONB;
```

### 5-3. 인덱스 추가

```sql
-- 기존 설계에 이미 포함된 인덱스
CREATE INDEX idx_scan_job_repo_status ON scan_job(repo_id, status);

-- 추가 인덱스: 동일 저장소 진행 중 스캔 중복 방지 조회용
CREATE INDEX idx_scan_job_repo_active ON scan_job(repo_id) WHERE status IN ('queued', 'running');
```

---

## 6. 핵심 로직 상세

### 6-1. webhook_handler.py -- WebhookHandler 서비스

```python
class WebhookHandler:
    """Webhook 이벤트별 비즈니스 로직 처리"""

    def __init__(self, db: AsyncSession, orchestrator: ScanOrchestrator):
        self.db = db
        self.orchestrator = orchestrator

    async def handle_push(self, payload: dict) -> str | None:
        """push 이벤트 처리

        pseudocode:
        1. payload에서 repo_id, branch, commit_sha, changed_files 추출
        2. payload["ref"]에서 브랜치명 파싱 ("refs/heads/main" -> "main")
        3. DB에서 Repository 조회 (github_repo_id + is_active=True)
           - 없으면 None 반환 (등록되지 않은 저장소)
        4. 브랜치가 default_branch인지 확인
           - default_branch가 아니면 None 반환 (기본 브랜치만 스캔)
        5. payload["commits"]에서 변경된 파일 목록 추출
           - added + modified 파일 목록 합산 (removed 제외)
           - Python 파일만 필터링 (.py 확장자)
        6. Python 파일이 없으면 None 반환 (PoC: Python만 지원)
        7. 동일 저장소에 이미 queued/running 상태의 ScanJob이 있으면 None 반환 (중복 방지)
        8. orchestrator.enqueue_scan() 호출
           - trigger="webhook", scan_type="incremental"
           - changed_files에 변경 파일 목록 저장
        9. scan_job_id 반환
        """

    async def handle_pull_request(self, payload: dict, action: str) -> str | None:
        """pull_request 이벤트 처리 (opened / synchronize)

        pseudocode:
        1. payload에서 repo info, pr_number, head.sha, head.ref 추출
        2. DB에서 Repository 조회 (github_repo_id + is_active=True)
           - 없으면 None 반환
        3. GitHub API로 PR의 changed files 목록 조회
           - GET /repos/{owner}/{repo}/pulls/{pr_number}/files
           - Python 파일만 필터링
        4. Python 파일이 없으면 None 반환
        5. 동일 PR에 대해 이미 queued/running 스캔이 있으면
           - 기존 스캔 취소 (status -> cancelled) 후 새로 등록
           - 이유: synchronize(추가 커밋)는 최신 커밋만 스캔하면 됨
        6. orchestrator.enqueue_scan() 호출
           - trigger="webhook", scan_type="pr"
           - pr_number, commit_sha, changed_files 저장
        7. scan_job_id 반환
        """

    async def handle_installation_created(self, payload: dict) -> list[str]:
        """installation.created 이벤트 처리 (GitHub App 설치)

        pseudocode:
        1. payload에서 installation.id, repositories[] 추출
        2. payload["sender"]로 GitHub 사용자 정보 조회
           - DB에서 User 조회 (github_id)
           - 없으면 새 User 생성 (GitHub OAuth와 별도 경로)
        3. 사용자의 팀 조회 (없으면 기본 팀 자동 생성)
        4. repositories[]를 순회하며:
           a. 이미 등록된 저장소인지 확인 (github_repo_id)
              - 이미 있으면 installation_id 업데이트 + is_active=True
              - 없으면 새 Repository 레코드 생성
           b. is_initial_scan_done=False로 설정
        5. 각 저장소에 대해 초기 스캔 큐 등록
           - orchestrator.enqueue_scan(trigger="webhook", scan_type="initial")
           - 초기 스캔: changed_files=None -> 전체 코드베이스 스캔
        6. 생성/업데이트된 repo_id 목록 반환
        """

    async def handle_installation_deleted(self, payload: dict) -> list[str]:
        """installation.deleted 이벤트 처리 (GitHub App 삭제)

        pseudocode:
        1. payload에서 installation.id 추출
        2. DB에서 해당 installation_id를 가진 모든 Repository 조회
        3. 각 Repository에 대해:
           a. is_active = False 설정
           b. 진행 중인 ScanJob(queued/running)이 있으면 cancelled로 변경
           c. installation_id = None 설정
        4. 비활성화된 repo_id 목록 반환
        Note: 실제 데이터 삭제는 하지 않음 (히스토리 보존).
              DELETE /api/v1/repos/{repo_id}에서 명시적 삭제.
        """
```

### 6-2. github_app.py -- GitHubAppService 확장

```python
class GitHubAppService:

    # 기존 메서드는 유지하고, 아래 메서드 구현/추가

    def _generate_jwt(self) -> str:
        """GitHub App JWT 생성

        pseudocode:
        1. 현재 시각(iat) 계산 - 60초 (클럭 드리프트 여유)
        2. 만료 시각(exp) = iat + 10분
        3. payload = { "iat": iat, "exp": exp, "iss": self._app_id }
        4. jwt.encode(payload, self._private_key, algorithm="RS256")
        5. 생성된 JWT 문자열 반환
        """

    async def get_installation_token(self, installation_id: int) -> str:
        """Installation Access Token 발급 (캐싱 포함)

        pseudocode:
        1. _token_cache에서 installation_id로 캐시 조회
           - 캐시 히트 + 만료 5분 이전 -> 캐시된 토큰 반환
        2. JWT 생성 (_generate_jwt)
        3. POST https://api.github.com/app/installations/{installation_id}/access_tokens
           - Authorization: Bearer {jwt}
           - Accept: application/vnd.github+json
        4. 응답에서 token, expires_at 추출
        5. _token_cache에 저장 { token, expires_at }
        6. token 반환
        """

    async def get_installation_repos(self, installation_id: int) -> list[dict]:
        """GitHub App 설치에서 접근 가능한 저장소 목록 조회 (신규)

        pseudocode:
        1. Installation Access Token 발급
        2. GET https://api.github.com/installation/repositories
           - Authorization: token {installation_token}
           - per_page=100 (페이지네이션 처리)
        3. 응답에서 repositories[] 추출
        4. 각 저장소의 id, full_name, private, default_branch, language 반환
        """

    async def get_pr_changed_files(
        self, full_name: str, installation_id: int, pr_number: int
    ) -> list[str]:
        """PR의 변경 파일 목록 조회 (신규)

        pseudocode:
        1. Installation Access Token 발급
        2. GET https://api.github.com/repos/{full_name}/pulls/{pr_number}/files
           - per_page=100 (페이지네이션 처리)
        3. 응답에서 각 파일의 filename 추출
        4. 파일 경로 목록 반환
        """

    async def get_default_branch_sha(
        self, full_name: str, installation_id: int, branch: str
    ) -> str:
        """특정 브랜치의 최신 커밋 SHA 조회 (신규)

        pseudocode:
        1. Installation Access Token 발급
        2. GET https://api.github.com/repos/{full_name}/branches/{branch}
        3. 응답에서 commit.sha 추출 및 반환
        """
```

### 6-3. scan_orchestrator.py -- ScanOrchestrator 구현

```python
class ScanOrchestrator:

    async def enqueue_scan(
        self,
        repo_id: uuid.UUID,
        trigger: str,
        commit_sha: str | None = None,
        branch: str | None = None,
        pr_number: int | None = None,
        scan_type: str = "incremental",
        changed_files: list[str] | None = None,
    ) -> str:
        """스캔 작업을 큐에 등록

        pseudocode:
        1. job_id = uuid4() 생성
        2. DB에 ScanJob 레코드 생성:
           - id=job_id, repo_id, status="queued", trigger_type=trigger
           - commit_sha, branch, pr_number
           - scan_type, changed_files (JSONB)
           - retry_count=0
        3. ScanJobMessage 생성
        4. RQ Queue에 작업 등록:
           self._queue.enqueue(
               "src.workers.scan_worker.run_scan",
               args=(message,),
               job_id=job_id,
               retry=Retry(max=MAX_RETRY_COUNT),
               job_timeout="10m",
           )
        5. job_id 반환
        """

    async def cancel_active_scans_for_pr(
        self, repo_id: uuid.UUID, pr_number: int
    ) -> int:
        """동일 PR에 대한 진행 중 스캔 취소 (신규)

        pseudocode:
        1. DB에서 repo_id + pr_number + status IN (queued, running) 조회
        2. 각 ScanJob의 status를 "cancelled"로 변경
        3. RQ에서 해당 job 취소 시도 (best effort)
        4. 취소한 스캔 수 반환
        """

    async def has_active_scan(self, repo_id: uuid.UUID) -> bool:
        """동일 저장소에 진행 중인 스캔이 있는지 확인 (신규)

        pseudocode:
        1. DB에서 repo_id + status IN (queued, running) 조회
        2. 1건 이상이면 True, 아니면 False 반환
        """

    async def update_job_status(
        self, job_id: str, status: str, error_message: str | None = None
    ) -> None:
        """스캔 작업 상태 업데이트 (구현)

        pseudocode:
        1. DB에서 ScanJob 조회 (job_id)
        2. scan_job.status = status
        3. if status == "running":
              scan_job.started_at = now()
        4. if status == "completed":
              scan_job.completed_at = now()
              scan_job.duration_seconds = (completed_at - started_at).seconds
        5. if status == "failed":
              scan_job.error_message = error_message
              scan_job.retry_count += 1
              if scan_job.retry_count < MAX_RETRY_COUNT:
                  # RQ의 Retry 메커니즘이 자동으로 재큐잉
                  pass
        6. DB commit
        """
```

### 6-4. repos.py -- 엔드포인트 구현

```python
@router.get("")
async def list_repos(current_user, db, page, per_page):
    """저장소 목록 조회

    pseudocode:
    1. current_user로부터 team_id 목록 조회 (TeamMember 테이블)
    2. SELECT * FROM repository WHERE team_id IN (team_ids)
       - is_active 필터 적용 (선택)
       - ORDER BY created_at DESC
       - LIMIT per_page OFFSET (page-1) * per_page
    3. COUNT(*) 쿼리로 전체 수 조회
    4. PaginatedResponse 구성 후 반환
    """

@router.post("")
async def register_repo(request, current_user, db):
    """저장소 연동 등록

    pseudocode:
    1. github_repo_id로 중복 확인 -> 409 Conflict
    2. current_user의 팀 확인 (소속 팀이 없으면 기본 팀 생성)
    3. installation_id가 있으면 GitHub API로 접근 권한 확인
    4. webhook_secret = secrets.token_hex(32) 생성
    5. Repository 레코드 생성 (is_initial_scan_done=False)
    6. 초기 스캔 큐 등록 (scan_type="initial")
    7. 201 Created 응답
    """

@router.delete("/{repo_id}")  # 신규 엔드포인트
async def disconnect_repo(repo_id, current_user, db):
    """저장소 연동 해제

    pseudocode:
    1. repo_id로 Repository 조회 -> 404
    2. current_user의 team role 확인 (owner/admin만 허용) -> 403
    3. 진행 중인 ScanJob(queued/running) 취소
    4. CASCADE 설정에 따라 관련 데이터 자동 삭제:
       - ScanJob (cascade: all, delete-orphan)
       - Vulnerability (cascade: all, delete-orphan)
       - PatchPR (vulnerability 통해 cascade)
    5. Repository 레코드 삭제
    6. 삭제된 통계 반환
    """

@router.get("/github/installations")  # 신규 엔드포인트
async def list_github_installations(current_user, db):
    """GitHub App 설치의 접근 가능 저장소 목록

    pseudocode:
    1. current_user의 GitHub Access Token으로 사용자의 installations 조회
       - GET /user/installations
    2. 각 installation에 대해 get_installation_repos() 호출
    3. 이미 연동된 저장소 표시 (already_connected)
    4. 목록 반환
    """
```

### 6-5. webhooks.py -- 이벤트 라우팅 (리팩토링)

```python
@router.post("/github", status_code=202)
async def receive_github_webhook(request, headers, db):
    """
    기존 스캐폴딩 구조를 유지하되, 각 이벤트 분기에서
    WebhookHandler의 메서드를 호출하는 형태로 변경.

    pseudocode:
    1. raw body 읽기
    2. HMAC-SHA256 서명 검증 -> 403
    3. X-GitHub-Event 헤더 확인 -> 400
    4. payload JSON 파싱
    5. WebhookHandler 인스턴스 생성 (db, orchestrator 주입)
    6. 이벤트 분기:
       - "push": handler.handle_push(payload)
       - "pull_request" (opened/synchronize): handler.handle_pull_request(payload, action)
       - "installation" (created): handler.handle_installation_created(payload)
       - "installation" (deleted): handler.handle_installation_deleted(payload)
       - "ping": return {"message": "pong"}
    7. 응답 반환 (scan_job_id 포함, 트리거된 경우)
    """
```

### 6-6. scans.py -- 수동 스캔 트리거 구현

```python
@router.post("", status_code=202)
async def trigger_scan(request, current_user, db):
    """수동 스캔 트리거

    pseudocode:
    1. repo_id로 Repository 조회 -> 404
    2. current_user가 해당 repo의 팀에 속하는지 확인 -> 403
    3. repository.is_active 확인 -> 400 ("비활성 저장소")
    4. 동일 저장소에 이미 진행 중인 스캔 확인 -> 429 ("이미 스캔 진행 중")
    5. branch가 없으면 repository.default_branch 사용
    6. commit_sha가 없으면:
       - GitHub API로 해당 브랜치의 최신 commit SHA 조회
    7. scan_type 결정:
       - is_initial_scan_done == False -> "initial" (전체 스캔)
       - 그 외 -> "incremental"
    8. orchestrator.enqueue_scan() 호출 (trigger="manual")
    9. DB에서 생성된 ScanJob 조회
    10. 202 Accepted + ScanJobResponse 반환
    """
```

---

## 7. Webhook 페이로드 스키마

### 7-1. schemas/webhook.py (신규)

```python
from pydantic import BaseModel, Field


class GitHubPushPayload(BaseModel):
    """push 이벤트 페이로드 (필요 필드만)"""
    ref: str = Field(description="refs/heads/{branch}")
    after: str = Field(description="push 후 커밋 SHA")
    repository: GitHubRepoInfo
    commits: list[GitHubCommit] = []
    installation: GitHubInstallation | None = None


class GitHubPullRequestPayload(BaseModel):
    """pull_request 이벤트 페이로드 (필요 필드만)"""
    action: str
    number: int
    pull_request: GitHubPR
    repository: GitHubRepoInfo
    installation: GitHubInstallation | None = None


class GitHubInstallationPayload(BaseModel):
    """installation 이벤트 페이로드 (필요 필드만)"""
    action: str  # created / deleted
    installation: GitHubInstallationDetail
    repositories: list[GitHubRepoSummary] = []
    sender: GitHubUser


class GitHubRepoInfo(BaseModel):
    id: int
    full_name: str
    default_branch: str
    language: str | None = None


class GitHubCommit(BaseModel):
    id: str
    added: list[str] = []
    modified: list[str] = []
    removed: list[str] = []


class GitHubPR(BaseModel):
    number: int
    head: GitHubPRHead
    base: GitHubPRBase


class GitHubPRHead(BaseModel):
    ref: str
    sha: str


class GitHubPRBase(BaseModel):
    ref: str


class GitHubInstallation(BaseModel):
    id: int


class GitHubInstallationDetail(BaseModel):
    id: int
    account: GitHubUser


class GitHubRepoSummary(BaseModel):
    id: int
    full_name: str
    private: bool


class GitHubUser(BaseModel):
    id: int
    login: str
```

---

## 8. 데이터 흐름

### 8-1. Webhook -> 스캔 큐 등록 흐름

```
GitHub            webhooks.py        WebhookHandler     ScanOrchestrator    Redis Queue     DB
  |                   |                    |                  |                 |            |
  |-- POST /webhook ->|                   |                  |                 |            |
  |                   |-- 서명 검증 ------->|                  |                 |            |
  |                   |-- parse event ---->|                  |                 |            |
  |                   |                    |                  |                 |            |
  |                   |                    |-- DB: repo 조회 --|---------------->|            |-- SELECT repo
  |                   |                    |<----- repo ------|-----------------|            |<- repo
  |                   |                    |                  |                 |            |
  |                   |                    |-- enqueue_scan ->|                 |            |
  |                   |                    |                  |-- DB: ScanJob ->|            |-- INSERT scan_job
  |                   |                    |                  |                 |            |
  |                   |                    |                  |-- enqueue ----->|            |
  |                   |                    |                  |<-- job_id ------|            |
  |                   |                    |<-- job_id -------|                 |            |
  |                   |<-- job_id ---------|                  |                 |            |
  |<- 202 Accepted ---|                   |                  |                 |            |
```

### 8-2. 수동 스캔 트리거 흐름

```
Frontend          scans.py           ScanOrchestrator    GitHubAppService    Redis Queue    DB
  |                  |                    |                   |                  |           |
  |-- POST /scans -->|                   |                   |                  |           |
  |                  |-- JWT 인증 ------->|                   |                  |           |
  |                  |-- DB: repo 조회 -->|                   |                  |           |
  |                  |                    |                   |                  |           |
  |                  |-- get latest SHA--|------------------>|                  |           |
  |                  |                    |<-- commit_sha ---|                  |           |
  |                  |                    |                   |                  |           |
  |                  |-- enqueue_scan -->|                   |                  |           |
  |                  |                    |-- INSERT scan --->|----------------->|           |-- INSERT
  |                  |                    |-- enqueue ------->|----------------->|           |
  |                  |                    |<-- job_id --------|                  |           |
  |                  |<-- job_id ---------|                   |                  |           |
  |<- 202 + scan ----|                   |                   |                  |           |
```

### 8-3. GitHub App 설치 -> 초기 스캔 흐름

```
GitHub            webhooks.py        WebhookHandler      GitHubAppService    ScanOrchestrator    DB
  |                   |                   |                    |                   |              |
  |-- installation -->|                  |                    |                   |              |
  |   (created)       |-- 서명 검증 ------>|                    |                   |              |
  |                   |                   |                    |                   |              |
  |                   |                   |-- repos 조회 ----->|                    |              |
  |                   |                   |                    |-- GitHub API ----->|              |
  |                   |                   |<-- repos[] --------|                    |              |
  |                   |                   |                    |                   |              |
  |                   |                   |-- for each repo:  |                   |              |
  |                   |                   |   INSERT repo -----|------------------>|              |-- INSERT repo
  |                   |                   |   enqueue_scan ----|------------------>|              |-- INSERT scan
  |                   |                   |                    |                   |-- Redis Q -->|
  |                   |                   |<-- repo_ids -------|                   |              |
  |                   |<-- repo_ids ------|                    |                   |              |
  |<- 202 Accepted ---|                   |                    |                   |              |
```

### 8-4. 연동 해제 흐름

```
Frontend           repos.py          DB
  |                   |                |
  |-- DELETE /repos ->|               |
  |                   |-- 권한 확인 --->|
  |                   |               |
  |                   |-- 진행 중 스캔 취소
  |                   |-- DELETE repo -|-- CASCADE: scan_jobs, vulnerabilities, patch_prs 삭제
  |                   |<-- 삭제 통계 ---|
  |<- 200 + stats ----|               |
```

---

## 9. 성능 설계

### 9-1. 인덱스 계획

system-design.md에 정의된 기존 인덱스 외 추가분:

```sql
-- 동일 저장소 진행 중 스캔 중복 방지 (부분 인덱스)
CREATE INDEX idx_scan_job_repo_active
  ON scan_job(repo_id) WHERE status IN ('queued', 'running');

-- github_repo_id로 빠른 중복 확인 (기존 unique 제약에 의해 자동 생성)
-- 이미 repository.github_repo_id에 UNIQUE 제약이 있음

-- installation_id로 저장소 조회 (연동 해제 시)
CREATE INDEX idx_repository_installation ON repository(installation_id);
```

### 9-2. 동시성 제어

- **동일 저장소 중복 스캔 방지**: `has_active_scan()` 조회 후 큐 등록. 완벽한 동시성 제어는 아니지만 PoC 수준에서 충분. 필요시 Redis 분산 잠금(`SETNX`) 적용.
- **PR synchronize 이벤트**: 기존 PR 스캔을 취소하고 새 스캔 등록. 순서 보장을 위해 `cancel_active_scans_for_pr()` -> `enqueue_scan()` 순서로 단일 트랜잭션 내 실행.

### 9-3. Webhook 응답 시간

- Webhook 핸들러는 DB 조회 + 큐 등록만 수행하므로 100ms 이내 응답 목표.
- 실제 스캔은 워커에서 비동기 실행.
- GitHub는 Webhook 응답을 10초 이내에 받아야 하므로, 핸들러에서 장시간 작업 수행 금지.

---

## 10. 테스트 시나리오

### 10-1. 단위 테스트

| 대상 | 시나리오 | 입력 | 예상 결과 |
|------|----------|------|-----------|
| `_verify_github_signature()` | 유효한 서명 검증 | payload + 올바른 HMAC | True |
| `_verify_github_signature()` | 서명 불일치 | payload + 잘못된 HMAC | False |
| `_verify_github_signature()` | 서명 헤더 누락 | payload + None | False |
| `_verify_github_signature()` | sha256= 접두사 없음 | payload + "abc123" | False |
| `GitHubAppService._generate_jwt()` | JWT 생성 | app_id + private_key | RS256 JWT 문자열, iss=app_id |
| `WebhookHandler.handle_push()` | default_branch push | push payload (main) | scan_job_id 반환 |
| `WebhookHandler.handle_push()` | non-default branch | push payload (feature/x) | None 반환 |
| `WebhookHandler.handle_push()` | Python 파일 없음 | push payload (only .js files) | None 반환 |
| `WebhookHandler.handle_push()` | 미등록 저장소 | push payload (unknown repo) | None 반환 |
| `WebhookHandler.handle_pull_request()` | PR opened | PR payload (opened) | scan_job_id 반환 |
| `WebhookHandler.handle_pull_request()` | PR synchronize | PR payload (synchronize) | 기존 스캔 취소 + 새 scan_job_id |
| `WebhookHandler.handle_installation_created()` | App 설치 | installation payload (3 repos) | 3개 repo_id + 3개 초기 스캔 |
| `WebhookHandler.handle_installation_deleted()` | App 삭제 | installation payload | repos 비활성화 |
| `ScanOrchestrator.enqueue_scan()` | 정상 큐 등록 | repo_id + trigger | job_id, ScanJob(queued) |
| `ScanOrchestrator.has_active_scan()` | 진행 중 스캔 있음 | repo_id (with queued job) | True |
| `ScanOrchestrator.has_active_scan()` | 진행 중 스캔 없음 | repo_id (no active job) | False |
| `ScanOrchestrator.cancel_active_scans_for_pr()` | PR 스캔 취소 | repo_id + pr_number | 취소된 수 반환, status=cancelled |

### 10-2. 통합 테스트

| API | 시나리오 | 입력 | 예상 결과 |
|-----|----------|------|-----------|
| POST /webhooks/github | push 이벤트 정상 처리 | 유효한 서명 + push payload | 202, scan_job_id 포함 |
| POST /webhooks/github | 서명 검증 실패 | 잘못된 서명 | 403 |
| POST /webhooks/github | 이벤트 헤더 누락 | 서명 OK, 이벤트 헤더 없음 | 400 |
| POST /webhooks/github | ping 이벤트 | ping payload | 200, "pong" |
| POST /webhooks/github | PR opened 이벤트 | PR opened payload | 202, scan_job_id |
| POST /webhooks/github | installation created | installation payload | 202, repos 생성 |
| POST /webhooks/github | installation deleted | installation payload | 202, repos 비활성화 |
| GET /repos | 저장소 목록 조회 | JWT 인증 | 200, 저장소 목록 |
| GET /repos | 미인증 | 인증 헤더 없음 | 401 |
| POST /repos | 저장소 연동 등록 | 유효한 repo 정보 | 201, repo 생성 + 초기 스캔 큐 |
| POST /repos | 중복 저장소 등록 | 이미 등록된 github_repo_id | 409 |
| DELETE /repos/{id} | 연동 해제 | owner/admin JWT | 200, 데이터 삭제 통계 |
| DELETE /repos/{id} | 권한 부족 | member JWT | 403 |
| DELETE /repos/{id} | 존재하지 않는 저장소 | 잘못된 repo_id | 404 |
| POST /scans | 수동 스캔 트리거 | repo_id + branch | 202, ScanJob(queued) |
| POST /scans | 진행 중 스캔 있음 | 이미 스캔 중인 repo_id | 429 |
| POST /scans | 비활성 저장소 | is_active=False repo | 400 |
| GET /repos/github/installations | 설치 저장소 목록 | JWT 인증 | 200, 저장소 목록 |

### 10-3. 경계 조건 / 에러 케이스

- push 이벤트에 commits가 빈 배열인 경우 (force push 등) -> 안전하게 처리, 스캔 건너뜀
- installation.created에 repositories가 빈 배열 -> 정상 처리, 빈 목록 반환
- 동일 커밋 SHA로 중복 push 이벤트 수신 -> 이미 스캔 큐에 있으면 무시
- GitHub API 호출 실패 (rate limit, 네트워크) -> 에러 로깅 후 500 응답 (GitHub가 재시도)
- 매우 큰 PR (변경 파일 100개 이상) -> 페이지네이션으로 전체 파일 목록 확보
- webhook_secret이 None인 저장소 (레거시) -> 글로벌 GITHUB_WEBHOOK_SECRET으로 폴백
- Redis 연결 실패 시 -> 큐 등록 실패, 500 응답, GitHub Webhook 재시도에 의존
- 동시에 installation.created와 수동 등록이 발생하는 경우 -> github_repo_id UNIQUE 제약으로 중복 방지, 409 처리

---

## 11. 영향 범위

### 11-1. 수정 필요 파일 목록

**백엔드**:
- `/Users/jsong/dev/jsong1230-github/Vulnix/backend/src/api/v1/webhooks.py` -- 이벤트 핸들러 위임 로직
- `/Users/jsong/dev/jsong1230-github/Vulnix/backend/src/api/v1/repos.py` -- 목록 조회, 등록, 해제, GitHub installations
- `/Users/jsong/dev/jsong1230-github/Vulnix/backend/src/api/v1/scans.py` -- 수동 스캔 트리거
- `/Users/jsong/dev/jsong1230-github/Vulnix/backend/src/services/github_app.py` -- JWT, token, repos, PR files
- `/Users/jsong/dev/jsong1230-github/Vulnix/backend/src/services/scan_orchestrator.py` -- enqueue, cancel, has_active
- `/Users/jsong/dev/jsong1230-github/Vulnix/backend/src/schemas/repository.py` -- is_initial_scan_done 필드 추가
- `/Users/jsong/dev/jsong1230-github/Vulnix/backend/src/models/repository.py` -- is_initial_scan_done 컬럼 추가
- `/Users/jsong/dev/jsong1230-github/Vulnix/backend/src/models/scan_job.py` -- retry_count, scan_type, changed_files 컬럼 추가
- `/Users/jsong/dev/jsong1230-github/Vulnix/backend/src/schemas/scan.py` -- scan_type, changed_files 필드 추가

**프론트엔드**:
- `/Users/jsong/dev/jsong1230-github/Vulnix/frontend/src/app/repos/page.tsx` -- API 연동, 수동 스캔
- `/Users/jsong/dev/jsong1230-github/Vulnix/frontend/src/app/repos/[id]/page.tsx` -- 수동 스캔 버튼
- `/Users/jsong/dev/jsong1230-github/Vulnix/frontend/src/lib/api-client.ts` -- 헬퍼 함수

### 11-2. 신규 생성 파일 목록

**백엔드**:
- `/Users/jsong/dev/jsong1230-github/Vulnix/backend/src/services/webhook_handler.py`
- `/Users/jsong/dev/jsong1230-github/Vulnix/backend/src/schemas/webhook.py`
- `/Users/jsong/dev/jsong1230-github/Vulnix/backend/alembic/versions/xxxx_add_f01_columns.py` (Alembic 마이그레이션)

**프론트엔드**:
- `/Users/jsong/dev/jsong1230-github/Vulnix/frontend/src/app/repos/connect/page.tsx`
- `/Users/jsong/dev/jsong1230-github/Vulnix/frontend/src/components/repos/scan-trigger-button.tsx`
- `/Users/jsong/dev/jsong1230-github/Vulnix/frontend/src/components/repos/disconnect-dialog.tsx`

---

## 변경 이력

| 날짜 | 변경 내용 | 이유 |
|------|-----------|------|
| 2026-02-25 | 초안 작성 | F-01 기능 설계 |
