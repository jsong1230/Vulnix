# F-03 자동 패치 PR 생성 -- 기술 설계서

## 1. 참조

- 인수조건: `docs/project/features.md` #F-03
- 시스템 설계: `docs/system/system-design.md` 3-4절, 3-5절, 4-2절
- 선행 기능: F-02 취약점 탐지 엔진 (완료)

---

## 2. 아키텍처 결정

### ADR-F03-001: diff 적용 방식 -- Git Data API vs Contents API

- **선택지**:
  - A) Git Data API (tree/blob/commit 저수준 API로 diff 적용)
  - B) Contents API (`PUT /repos/{owner}/{repo}/contents/{path}` 파일 단위 생성/수정)
- **결정**: B) Contents API
- **근거**:
  - PoC 단계에서 패치는 단일 파일 수정이 대부분 (SQL 파라미터화, Markup 이스케이프 등)
  - Contents API는 파일 1개 수정에 브랜치 생성 + 커밋이 1회 호출로 완료되므로 구현 복잡도가 낮음
  - Git Data API는 multi-file 패치에 유리하지만, M1 범위에서는 과잉 설계
  - 향후 multi-file 패치 필요 시 Git Data API로 전환 가능 (GitHubAppService 내부 구현만 교체)

### ADR-F03-002: 패치 불가 시 처리 방식

- **선택지**:
  - A) PatchPR 레코드를 생성하지 않고 Vulnerability에 manual_guide 필드 추가
  - B) PatchPR 레코드를 `status=manual_guide`로 생성하여 통합 관리
- **결정**: A) Vulnerability 모델에 manual_guide 필드 추가
- **근거**:
  - PatchPR은 실제 GitHub PR이 생성된 경우만 기록하는 것이 의미적으로 명확
  - 패치 불가 정보는 취약점 자체의 속성 (수동 가이드, 우선순위)이므로 Vulnerability에 저장이 자연스러움
  - API 조회 시 패치 가능/불가를 Vulnerability 레벨에서 바로 판단 가능

### ADR-F03-003: 패치 PR 본문에 테스트 코드 제안 포함 방식

- **선택지**:
  - A) LLM 패치 프롬프트에서 테스트 코드까지 함께 생성
  - B) 별도 LLM 호출로 테스트 코드 생성 (선택적)
- **결정**: A) 패치 프롬프트에서 테스트 코드 제안까지 한 번에 생성
- **근거**:
  - 인수조건에서 "선택적"으로 명시되어 있어, 별도 호출은 비용 대비 효과가 낮음
  - 패치 diff와 테스트 코드를 동시에 생성하면 일관성이 높음
  - PR 본문의 "테스트 제안" 섹션에 코드 블록으로 포함 (커밋에는 포함하지 않음)

---

## 3. 구현 범위

### 3-1. 수정 파일

| 파일 경로 | 변경 내용 |
|-----------|-----------|
| `backend/src/services/patch_generator.py` | `generate_patch_prs()` 핵심 로직 구현, PR 본문 구성, 패치 불가 처리 |
| `backend/src/services/github_app.py` | `create_branch()`, `create_file_commit()`, `create_pull_request()`, `get_file_content()` 메서드 추가 |
| `backend/src/services/llm_agent.py` | `_build_patch_prompt()` 개선 (테스트 코드 제안 + 패치 불가 판단 응답 추가) |
| `backend/src/workers/scan_worker.py` | 9단계와 10단계 사이에 패치 PR 생성 단계 추가 (단계 9.5) |
| `backend/src/api/v1/patches.py` | `list_patches()`, `get_patch()` 엔드포인트 구현 |
| `backend/src/models/vulnerability.py` | `manual_guide`, `manual_priority` 필드 추가 |

### 3-2. 신규 생성 파일

| 파일 경로 | 설명 |
|-----------|------|
| `backend/src/schemas/patch.py` | PatchPR 요청/응답 Pydantic 스키마 |
| `backend/alembic/versions/xxxx_add_manual_guide_fields.py` | Vulnerability 테이블 마이그레이션 |
| `backend/tests/services/test_patch_generator.py` | PatchGenerator 단위 테스트 |
| `backend/tests/api/test_patches.py` | 패치 PR API 통합 테스트 |

---

## 4. PatchGenerator 상세 로직

### 4-1. `generate_patch_prs()` 전체 흐름

```
입력: repo_full_name, installation_id, base_branch, scan_job_id,
      repo_id, analysis_results, findings

  [1] analysis_results에서 패치 가능 항목 필터링
      조건: is_true_positive=True AND patch_diff IS NOT NULL
      ▼
  [2] 패치 불가 항목 처리
      조건: is_true_positive=True AND patch_diff IS NULL
      -> Vulnerability.manual_guide에 수동 수정 가이드 저장
      -> Vulnerability.manual_priority에 심각도 기반 우선순위 저장
      ▼
  [3] 패치 가능 항목 순회 (for each patchable_result):
      ▼
    [3-1] 브랜치명 생성
          형식: vulnix/fix-{vuln_type}-{short_hash}
          예시: vulnix/fix-sql-injection-a1b2c3
          ▼
    [3-2] base_branch의 최신 SHA 조회
          GitHubAppService.get_default_branch_sha()
          ▼
    [3-3] 패치 브랜치 생성
          GitHubAppService.create_branch()
          ▼
    [3-4] patch_diff를 파싱하여 수정 파일 내용 추출
          _apply_patch_diff() -> 원본 파일 내용 + diff -> 수정된 파일 내용
          ▼
    [3-5] 파일 커밋
          GitHubAppService.create_file_commit()
          ▼
    [3-6] PR 본문 생성
          _build_pr_body() -> 취약점 설명, 패치 설명, 참고 링크, 테스트 제안
          ▼
    [3-7] PR 생성
          GitHubAppService.create_pull_request()
          ▼
    [3-8] PatchPR 레코드 DB 저장
          ▼
    [3-9] Vulnerability.status -> "patched" 업데이트

  [4] 결과 반환: 생성된 PatchPR 레코드 목록
```

### 4-2. 메서드 시그니처 (변경)

```python
async def generate_patch_prs(
    self,
    repo_full_name: str,
    installation_id: int,
    base_branch: str,
    scan_job_id: uuid.UUID,
    repo_id: uuid.UUID,
    analysis_results: list[LLMAnalysisResult],
    findings: list[SemgrepFinding],
    db: AsyncSession,
) -> list[PatchPR]:
```

기존 시그니처 대비 변경점:
- `repo_id: uuid.UUID` 추가 -- PatchPR 레코드 생성에 필요
- `findings: list[SemgrepFinding]` 추가 -- finding_id로 Vulnerability 조회에 필요
- `db: AsyncSession` 추가 -- DB 저장을 위해 세션 전달
- 반환 타입: `list[dict]` -> `list[PatchPR]` -- ORM 모델 직접 반환

### 4-3. 브랜치명 규칙

```
vulnix/fix-{vulnerability_type}-{short_hash}
```

- `vulnerability_type`: LLM이 분류한 유형 (예: `sql-injection`, `xss`, `hardcoded-credentials`)
- `short_hash`: `finding_id`(Semgrep rule_id)의 SHA-256 해시 앞 7자
  - rule_id가 길고 특수문자를 포함할 수 있으므로 해시 사용
  - 동일 rule_id에 대해 동일 해시가 생성되므로 멱등성 확보
- `_` -> `-` 치환 (Git 브랜치명 컨벤션)
- 예시: `vulnix/fix-sql-injection-a1b2c3d`

**충돌 방지**: 동일 취약점 유형이 여러 파일에서 발견될 경우, `short_hash`에 `file_path + start_line`을 추가하여 유니크하게 만듦.

```python
import hashlib

@staticmethod
def _make_branch_name(vulnerability_type: str, file_path: str, start_line: int) -> str:
    raw = f"{vulnerability_type}:{file_path}:{start_line}"
    short_hash = hashlib.sha256(raw.encode()).hexdigest()[:7]
    safe_type = vulnerability_type.lower().replace("_", "-")
    return f"vulnix/fix-{safe_type}-{short_hash}"
```

### 4-4. PR 본문 템플릿

`system-design.md` 3-5절 PR 본문 템플릿을 확장하여 인수조건의 모든 항목을 충족.

```markdown
## Vulnix Security Patch

### 탐지된 취약점
- **유형**: {vulnerability_type} ({cwe_id})
- **심각도**: {severity_badge} {severity}
- **파일**: `{file_path}` (Line {start_line}-{end_line})
- **OWASP**: {owasp_category}

### 왜 위험한가 (취약점 설명)
{llm_reasoning}

{vulnerability_description}

### 무엇을 어떻게 고쳤는가 (패치 설명)
{patch_description}

### 변경 코드
```diff
{patch_diff}
```

### 참고 자료
- {cwe_link}
- {owasp_link}
- {additional_references}

### 테스트 제안 (선택적)
{test_suggestion_code_block}

---
> 이 PR은 [Vulnix](https://vulnix.dev) 보안 에이전트가 자동 생성했습니다.
> 반드시 코드 리뷰 후 머지하세요.
```

**severity_badge 매핑**:
- critical: `:red_circle:`
- high: `:orange_circle:`
- medium: `:yellow_circle:`
- low: `:white_circle:`

### 4-5. 패치 불가 시 처리

LLM이 `patch_diff=None`을 반환한 경우 (is_true_positive=True이지만 패치 생성 불가):

1. Vulnerability 모델의 `manual_guide` 필드에 LLM의 `reasoning` + 수동 수정 가이드 저장
2. `manual_priority` 필드에 심각도 기반 우선순위 저장:
   - critical -> P0 (즉시 수정)
   - high -> P1 (1주 내 수정)
   - medium -> P2 (스프린트 내 수정)
   - low -> P3 (백로그)
3. PatchPR 레코드는 생성하지 않음 (ADR-F03-002)

**manual_guide 형식**:

```
## 수동 수정 가이드

### 취약점
- 유형: {vulnerability_type}
- 파일: {file_path} (Line {start_line}-{end_line})
- 심각도: {severity}
- 우선순위: {priority}

### 왜 자동 패치가 불가능한가
{reason_for_no_patch}

### 권장 수정 방법
{manual_fix_suggestion}

### 참고 자료
{references}
```

### 4-6. diff 적용 로직 (`_apply_patch_diff`)

LLM이 생성한 unified diff를 원본 파일에 적용하여 수정된 파일 내용을 생성한다.

```python
async def _apply_patch_diff(
    self,
    full_name: str,
    installation_id: int,
    file_path: str,
    patch_diff: str,
    ref: str,
) -> tuple[str, str]:
    """
    Returns:
        (수정된 파일 내용, 원본 파일의 SHA -- Contents API 업데이트에 필요)
    """
```

처리 흐름:
1. `GitHubAppService.get_file_content()`로 원본 파일 내용 + SHA 조회
2. unified diff를 라인 단위로 파싱
3. `+` 라인 추가, `-` 라인 제거, ` ` 라인 유지
4. 적용 실패 시 (context mismatch) -> 패치 불가로 전환하여 manual_guide 처리

**주의**: LLM이 생성한 diff가 원본과 맞지 않을 수 있으므로, fuzzy matching (전후 3줄 컨텍스트 비교)을 적용한다.

### 4-7. 성능 요구사항

인수조건: "취약점 1건당 패치 PR 생성 30초 이내"

**병목 분석**:
| 단계 | 예상 소요 시간 |
|------|----------------|
| 브랜치 SHA 조회 | ~0.5초 |
| 브랜치 생성 | ~0.5초 |
| 파일 내용 조회 | ~0.5초 |
| diff 적용 (로컬) | ~0.01초 |
| 파일 커밋 | ~1초 |
| PR 생성 | ~1초 |
| DB 저장 | ~0.1초 |
| **합계** | **~3.6초** |

LLM 패치 생성은 scan_worker의 LLM 분석 단계(단계 6)에서 이미 완료되므로, PR 생성 단계에서의 LLM 호출은 없다. 30초 제한을 충분히 충족한다.

**추가 최적화**: 여러 취약점의 PR을 `asyncio.gather()`로 병렬 생성 가능 (단, GitHub API rate limit 고려하여 동시성 3으로 제한).

---

## 5. GitHub App 추가 메서드

### 5-1. `create_branch()`

```python
async def create_branch(
    self,
    full_name: str,
    installation_id: int,
    branch_name: str,
    base_sha: str,
) -> None:
    """GitHub ref를 생성하여 새 브랜치를 만든다.

    GitHub API: POST /repos/{owner}/{repo}/git/refs
    Body: {"ref": "refs/heads/{branch_name}", "sha": "{base_sha}"}
    """
```

- **에러 처리**: 422 (이미 존재하는 브랜치) -> 기존 브랜치 삭제 후 재생성, 또는 경고 후 스킵

### 5-2. `get_file_content()`

```python
async def get_file_content(
    self,
    full_name: str,
    installation_id: int,
    file_path: str,
    ref: str,
) -> tuple[str, str]:
    """파일 내용과 blob SHA를 조회한다.

    GitHub API: GET /repos/{owner}/{repo}/contents/{path}?ref={ref}

    Returns:
        (파일 내용 문자열, blob SHA)
    """
```

- base64 디코딩하여 파일 내용 반환
- blob SHA는 Contents API의 PUT 요청에 필요

### 5-3. `create_file_commit()`

```python
async def create_file_commit(
    self,
    full_name: str,
    installation_id: int,
    branch_name: str,
    file_path: str,
    content: str,
    message: str,
    file_sha: str,
) -> dict:
    """브랜치에 파일 수정 커밋을 생성한다.

    GitHub API: PUT /repos/{owner}/{repo}/contents/{path}
    Body: {
        "message": "{message}",
        "content": "{base64_encoded_content}",
        "branch": "{branch_name}",
        "sha": "{file_sha}"
    }
    """
```

- `content`를 base64 인코딩하여 전송
- `file_sha`: 수정 대상 파일의 현재 blob SHA (get_file_content에서 조회)

### 5-4. `create_pull_request()`

```python
async def create_pull_request(
    self,
    full_name: str,
    installation_id: int,
    head: str,
    base: str,
    title: str,
    body: str,
    labels: list[str] | None = None,
) -> dict:
    """Pull Request를 생성한다.

    GitHub API: POST /repos/{owner}/{repo}/pulls
    Body: {"title", "body", "head", "base"}

    Returns:
        {"number": int, "html_url": str}
    """
```

- PR 생성 후 라벨 추가: `["security", "vulnix-auto-patch", severity]`
- 반환값에서 `number`와 `html_url`을 추출하여 PatchPR 레코드에 저장

### 5-5. 공통 사항

- 모든 메서드는 `get_installation_token()`으로 토큰을 얻어 인증
- httpx.AsyncClient 사용, 기존 패턴과 동일
- API 버전 헤더: `X-GitHub-Api-Version: 2022-11-28`

---

## 6. LLM 프롬프트 개선

### 6-1. `_build_patch_prompt()` 변경

기존 프롬프트에 다음을 추가:

1. **테스트 코드 제안 요청**: 응답 JSON에 `test_suggestion` 필드 추가
2. **패치 불가 판단 요청**: 응답 JSON에 `patchable` 필드 추가
3. **수동 수정 가이드**: `patchable=false`일 때 `manual_guide` 필드 포함

**변경된 응답 JSON 형식**:

```json
{
  "patchable": true,
  "patch_diff": "--- a/file.py\n+++ b/file.py\n@@ ... @@\n...",
  "patch_description": "패치 설명",
  "references": ["https://cwe.mitre.org/..."],
  "test_suggestion": "def test_sql_injection_prevention():\n    ...",
  "manual_guide": null
}
```

패치 불가 시:

```json
{
  "patchable": false,
  "patch_diff": null,
  "patch_description": null,
  "references": ["https://cwe.mitre.org/..."],
  "test_suggestion": null,
  "manual_guide": "이 취약점은 아키텍처 수준의 변경이 필요하여 자동 패치가 불가능합니다. ..."
}
```

### 6-2. LLMAnalysisResult 데이터 클래스 확장

```python
@dataclass
class LLMAnalysisResult:
    # ... 기존 필드 ...
    patchable: bool = True                    # 패치 가능 여부
    test_suggestion: str | None = None        # 테스트 코드 제안
    manual_guide: str | None = None           # 수동 수정 가이드 (패치 불가 시)
```

---

## 7. scan_worker 통합

### 7-1. 파이프라인 변경

현재 `_run_scan_async()` 파이프라인의 8단계(통계 업데이트)와 9단계(completed) 사이에 패치 PR 생성 단계를 추가한다.

```
기존:
  ... -> 7. Vulnerability DB 저장 -> 8. 통계 업데이트 -> 9. completed

변경 후:
  ... -> 7. Vulnerability DB 저장 -> 8. 패치 PR 생성 -> 9. 통계 업데이트 -> 10. completed
```

### 7-2. 추가 코드 위치

`_run_scan_async()` 함수 내 `_save_vulnerabilities()` 호출 직후:

```python
# 8. 패치 PR 생성 (F-03)
patch_gen = PatchGenerator()
patch_prs = await patch_gen.generate_patch_prs(
    repo_full_name=repo.full_name,
    installation_id=repo.installation_id,
    base_branch=repo.default_branch,
    scan_job_id=uuid.UUID(message.job_id),
    repo_id=repo.id,
    analysis_results=all_results,
    findings=findings,
    db=db,
)
logger.info(
    f"[WorkerID={message.job_id}] 패치 PR 생성 완료: {len(patch_prs)}건"
)
```

### 7-3. 에러 처리

패치 PR 생성 실패는 전체 스캔 파이프라인을 실패시키지 않는다:
- 개별 PR 생성 실패 시 경고 로그 기록 후 다음 취약점 처리 계속
- 전체 PR 생성 단계 실패 시 경고 로그 기록 후 스캔은 `completed` 처리
- 이유: 스캔 결과(Vulnerability 레코드)는 이미 저장되었으므로, PR 생성 실패가 스캔 성공을 무효화하면 안 됨

```python
try:
    patch_prs = await patch_gen.generate_patch_prs(...)
except Exception as e:
    logger.warning(f"[WorkerID={message.job_id}] 패치 PR 생성 실패 (스캔 자체는 성공): {e}")
    patch_prs = []
```

---

## 8. API 엔드포인트

### 8-1. Pydantic 스키마 (`schemas/patch.py`)

```python
class PatchPRResponse(BaseModel):
    """패치 PR 응답"""
    id: uuid.UUID
    vulnerability_id: uuid.UUID
    repo_id: uuid.UUID
    github_pr_number: int | None
    github_pr_url: str | None
    branch_name: str | None
    status: Literal["created", "merged", "closed", "rejected"]
    patch_diff: str | None
    patch_description: str | None
    created_at: datetime
    merged_at: datetime | None

    model_config = {"from_attributes": True}


class PatchPRDetailResponse(PatchPRResponse):
    """패치 PR 상세 응답 (취약점 정보 포함)"""
    vulnerability: VulnerabilitySummary | None = None
```

### 8-2. `GET /api/v1/patches`

**목적**: 현재 사용자 팀의 패치 PR 목록 조회

**인증**: 필요 (Bearer JWT)

**Query Parameters**:
| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| page | int | 1 | 페이지 번호 |
| per_page | int | 20 | 페이지당 항목 수 (max 100) |
| status | str | null | 필터: created / merged / closed / rejected |
| repo_id | uuid | null | 특정 저장소로 필터 |

**Response**: `PaginatedResponse[PatchPRResponse]`

```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "vulnerability_id": "uuid",
      "repo_id": "uuid",
      "github_pr_number": 42,
      "github_pr_url": "https://github.com/org/repo/pull/42",
      "branch_name": "vulnix/fix-sql-injection-a1b2c3d",
      "status": "created",
      "patch_diff": "--- a/app.py\n+++ b/app.py\n...",
      "patch_description": "SQL 쿼리를 파라미터화하여 인젝션 방지",
      "created_at": "2026-02-25T10:30:00Z",
      "merged_at": null
    }
  ],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 5,
    "total_pages": 1
  }
}
```

**에러 케이스**:
| 코드 | 상황 |
|------|------|
| 401 | 미인증 요청 |
| 403 | 팀 소속이 아닌 저장소의 패치 조회 시도 |

**DB 쿼리 로직**:
1. 현재 사용자의 팀 ID 조회 (TeamMember -> team_id)
2. 팀에 속한 Repository ID 목록 조회
3. PatchPR 테이블에서 repo_id IN (팀 리포 목록) AND status 필터 적용
4. created_at DESC 정렬, 페이지네이션

### 8-3. `GET /api/v1/patches/{patch_id}`

**목적**: 패치 PR 상세 조회 (취약점 정보 포함)

**인증**: 필요 (Bearer JWT)

**Response**: `ApiResponse[PatchPRDetailResponse]`

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "vulnerability_id": "uuid",
    "repo_id": "uuid",
    "github_pr_number": 42,
    "github_pr_url": "https://github.com/org/repo/pull/42",
    "branch_name": "vulnix/fix-sql-injection-a1b2c3d",
    "status": "created",
    "patch_diff": "--- a/app.py\n+++ b/app.py\n...",
    "patch_description": "SQL 쿼리를 파라미터화하여 인젝션 방지",
    "created_at": "2026-02-25T10:30:00Z",
    "merged_at": null,
    "vulnerability": {
      "id": "uuid",
      "status": "patched",
      "severity": "high",
      "vulnerability_type": "sql_injection",
      "file_path": "app/models/user.py",
      "start_line": 42,
      "detected_at": "2026-02-25T10:00:00Z",
      "created_at": "2026-02-25T10:00:00Z"
    }
  }
}
```

**에러 케이스**:
| 코드 | 상황 |
|------|------|
| 401 | 미인증 요청 |
| 403 | 팀 소속이 아닌 저장소의 패치 조회 시도 |
| 404 | 존재하지 않는 patch_id |

---

## 9. DB 설계 변경

### 9-1. Vulnerability 테이블 필드 추가

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|----------|------|
| manual_guide | TEXT | nullable=True | 패치 불가 시 수동 수정 가이드 |
| manual_priority | VARCHAR(10) | nullable=True | 수동 수정 우선순위 (P0/P1/P2/P3) |

### 9-2. PatchPR 테이블 필드 추가

기존 PatchPR 모델에 테스트 제안 필드 추가:

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|----------|------|
| test_suggestion | TEXT | nullable=True | LLM이 제안한 테스트 코드 |

### 9-3. 인덱스

기존 인덱스 (`idx_patch_pr_repo`)에 추가로:

```sql
CREATE INDEX idx_patch_pr_status ON patch_pr(status);
CREATE INDEX idx_patch_pr_created ON patch_pr(created_at DESC);
CREATE INDEX idx_vulnerability_manual_priority ON vulnerability(manual_priority)
  WHERE manual_priority IS NOT NULL;
```

---

## 10. 시퀀스 흐름

### 10-1. 정상 패치 PR 생성 (Happy Path)

```
ScanWorker       PatchGenerator    GitHubAppService     GitHub API      DB
    |                  |                  |                  |           |
    |-- generate_prs ->|                  |                  |           |
    |                  |                  |                  |           |
    |              [필터링: TP + diff 있음]|                  |           |
    |                  |                  |                  |           |
    |                  |-- get_branch_sha>|                  |           |
    |                  |                  |-- GET branch --->|           |
    |                  |                  |<---- sha --------|           |
    |                  |                  |                  |           |
    |                  |-- create_branch->|                  |           |
    |                  |                  |-- POST refs ---->|           |
    |                  |                  |<---- 201 --------|           |
    |                  |                  |                  |           |
    |                  |-- get_file ----->|                  |           |
    |                  |                  |-- GET contents ->|           |
    |                  |                  |<- content+sha ---|           |
    |                  |                  |                  |           |
    |                  |  [diff 적용]     |                  |           |
    |                  |                  |                  |           |
    |                  |-- commit_file -->|                  |           |
    |                  |                  |-- PUT contents ->|           |
    |                  |                  |<---- 201 --------|           |
    |                  |                  |                  |           |
    |                  |-- create_pr ---->|                  |           |
    |                  |                  |-- POST pulls --->|           |
    |                  |                  |<- number+url ----|           |
    |                  |                  |                  |           |
    |                  |-- save PatchPR --|------------------|---------->|
    |                  |-- update Vuln --|------------------|---------->|
    |                  |                  |                  |           |
    |<- patch_prs -----|                  |                  |           |
```

### 10-2. 패치 불가 시 (Manual Guide)

```
ScanWorker       PatchGenerator         DB
    |                  |                  |
    |-- generate_prs ->|                  |
    |                  |                  |
    |              [필터링: TP + diff 없음]|
    |                  |                  |
    |                  |-- update Vuln ---|
    |                  |   manual_guide   |
    |                  |   manual_priority|
    |                  |                  |
    |<- [] (빈 목록) --|                  |
```

---

## 11. 영향 범위

### 11-1. 수정 필요 파일 (6개)

1. `/backend/src/services/patch_generator.py` -- 핵심 로직 구현
2. `/backend/src/services/github_app.py` -- GitHub API 메서드 4개 추가
3. `/backend/src/services/llm_agent.py` -- 프롬프트 개선 + 데이터 클래스 확장
4. `/backend/src/workers/scan_worker.py` -- 파이프라인에 PR 생성 단계 추가
5. `/backend/src/api/v1/patches.py` -- 엔드포인트 구현
6. `/backend/src/models/vulnerability.py` -- manual_guide, manual_priority 필드 추가

### 11-2. 신규 생성 파일 (4개)

1. `/backend/src/schemas/patch.py` -- PatchPR Pydantic 스키마
2. `/backend/alembic/versions/xxxx_add_manual_guide_and_test_suggestion.py` -- 마이그레이션
3. `/backend/tests/services/test_patch_generator.py` -- 단위 테스트
4. `/backend/tests/api/test_patches.py` -- 통합 테스트

### 11-3. 기존 기능 영향 없음

- F-01 (저장소 연동): 영향 없음 -- Webhook 수신/클론은 그대로 동작
- F-02 (탐지 엔진): LLMAnalysisResult 확장으로 필드 추가 (하위 호환)
  - 기존 필드는 모두 유지, 신규 필드는 default 값이 있으므로 기존 코드에 영향 없음

---

## 12. 성능 설계

### 12-1. 인덱스 계획

```sql
-- 패치 PR 조회 최적화
CREATE INDEX idx_patch_pr_status ON patch_pr(status);
CREATE INDEX idx_patch_pr_created ON patch_pr(created_at DESC);

-- 패치 불가 취약점 조회
CREATE INDEX idx_vulnerability_manual_priority ON vulnerability(manual_priority)
  WHERE manual_priority IS NOT NULL;
```

### 12-2. 동시성 제어

- 패치 PR 생성: `asyncio.Semaphore(3)` -- GitHub API rate limit 대응
- GitHub App Installation Token: 기존 캐시 메커니즘 재사용 (5분 전 갱신)

### 12-3. 캐싱 전략

- 현 단계에서 패치 PR API에 캐싱은 불필요 (PoC 트래픽 낮음)
- 향후 Redis 캐싱 고려 가능: `patch_pr:{id}` (TTL 5분)

---

## 변경 이력

| 날짜 | 변경 내용 | 이유 |
|------|-----------|------|
| 2026-02-25 | 초안 작성 | F-03 설계 시작 |
