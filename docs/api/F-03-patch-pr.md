# F-03 자동 패치 PR 생성 — API 스펙 확정본

> 작성일: 2026-02-25
> 구현 버전: backend commit (F-03 GREEN)

---

## 개요

LLM이 취약점별 패치 코드를 자동 생성하여 GitHub PR로 제출하는 기능.
스캔 워커 파이프라인에 통합되어, 스캔 완료 후 patchable 취약점에 대해 자동 실행된다.

---

## 공통 규격

### 인증
모든 엔드포인트는 `Authorization: Bearer <JWT>` 헤더 필수.

### 응답 형식

**단건 조회**
```json
{
  "success": true,
  "data": { ... }
}
```

**목록 조회 (페이지네이션)**
```json
{
  "success": true,
  "data": [ ... ],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

**에러 응답**
```json
{
  "success": false,
  "error": "에러 메시지"
}
```

---

## 엔드포인트

### GET /api/v1/patches

현재 사용자 팀의 패치 PR 목록 조회.

#### Query Parameters

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| page | integer | N | 1 | 페이지 번호 (최소 1) |
| per_page | integer | N | 20 | 페이지당 항목 수 (1~100) |
| status | string | N | - | 상태 필터: `created` / `merged` / `closed` / `rejected` |
| repo_id | UUID | N | - | 저장소 ID 필터 |

#### 응답 스키마 `PatchPRResponse`

| 필드 | 타입 | 설명 |
|------|------|------|
| id | UUID | 패치 PR UUID |
| vulnerability_id | UUID | 대상 취약점 UUID |
| repo_id | UUID | 저장소 UUID |
| github_pr_number | integer \| null | GitHub PR 번호 |
| github_pr_url | string \| null | GitHub PR URL |
| branch_name | string \| null | 패치 브랜치명 (예: `vulnix/fix-sql-injection-a1b2c3d`) |
| status | string | PR 상태: `created` / `merged` / `closed` / `rejected` |
| patch_diff | string \| null | unified diff 형식 패치 내용 |
| patch_description | string \| null | 패치 설명 |
| created_at | datetime | PR 생성 시각 (ISO 8601, UTC) |
| merged_at | datetime \| null | PR 머지 시각 (ISO 8601, UTC) |

#### 응답 예시

```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "vulnerability_id": "660f9500-f30c-52e5-b827-557766551111",
      "repo_id": "770a0600-g41d-63f6-c938-668877662222",
      "github_pr_number": 42,
      "github_pr_url": "https://github.com/owner/repo/pull/42",
      "branch_name": "vulnix/fix-sql-injection-a1b2c3d",
      "status": "created",
      "patch_diff": "--- a/app/db.py\n+++ b/app/db.py\n@@ -10,7 +10,7 @@\n-    cursor.execute(f\"SELECT...\")\n+    cursor.execute(\"SELECT...\", params)",
      "patch_description": "파라미터화된 쿼리를 사용하여 SQL Injection 취약점을 수정합니다.",
      "created_at": "2026-02-25T10:00:00Z",
      "merged_at": null
    }
  ],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 1,
    "total_pages": 1
  }
}
```

#### HTTP 상태 코드

| 코드 | 설명 |
|------|------|
| 200 | 성공 |
| 401 | 미인증 |

---

### GET /api/v1/patches/{patch_id}

패치 PR 상세 조회 (취약점 정보 포함).

#### Path Parameters

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| patch_id | UUID | 패치 PR UUID |

#### 응답 스키마 `PatchPRDetailResponse`

`PatchPRResponse`를 상속하며 아래 필드 추가:

| 필드 | 타입 | 설명 |
|------|------|------|
| vulnerability | VulnerabilitySummary \| null | 연관 취약점 요약 정보 |

**VulnerabilitySummary 필드:**

| 필드 | 타입 | 설명 |
|------|------|------|
| id | UUID | 취약점 UUID |
| severity | string | 심각도: `critical` / `high` / `medium` / `low` |
| vulnerability_type | string | 취약점 유형 (예: `sql_injection`) |
| file_path | string | 취약 파일 경로 |
| start_line | integer | 취약 코드 시작 라인 |
| status | string | 취약점 상태: `open` / `patched` / `ignored` / `false_positive` |

#### 응답 예시

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "vulnerability_id": "660f9500-f30c-52e5-b827-557766551111",
    "repo_id": "770a0600-g41d-63f6-c938-668877662222",
    "github_pr_number": 42,
    "github_pr_url": "https://github.com/owner/repo/pull/42",
    "branch_name": "vulnix/fix-sql-injection-a1b2c3d",
    "status": "created",
    "patch_diff": "--- a/app/db.py\n+++ b/app/db.py\n...",
    "patch_description": "파라미터화된 쿼리를 사용하여 SQL Injection 취약점을 수정합니다.",
    "created_at": "2026-02-25T10:00:00Z",
    "merged_at": null,
    "vulnerability": {
      "id": "660f9500-f30c-52e5-b827-557766551111",
      "severity": "high",
      "vulnerability_type": "sql_injection",
      "file_path": "app/db.py",
      "start_line": 42,
      "status": "open"
    }
  }
}
```

#### HTTP 상태 코드

| 코드 | 설명 |
|------|------|
| 200 | 성공 |
| 401 | 미인증 |
| 403 | 타 팀 저장소의 패치 접근 시도 |
| 404 | 해당 patch_id 없음 |

---

## 내부 파이프라인

스캔 워커(`scan_worker.py`) 내에서 `_save_vulnerabilities()` 이후 자동 실행됨.

```
ScanWorker._run_scan_async()
  └─> _save_vulnerabilities()    # Vulnerability 레코드 저장
  └─> PatchGenerator.generate_patch_prs()
        ├─ unpatchable 항목 → Vulnerability.manual_guide / manual_priority 업데이트
        └─ patchable 항목 → asyncio.Semaphore(3) 병렬 처리
              ├─ GitHubAppService.create_branch()
              ├─ GitHubAppService.get_file_content()
              ├─ _apply_unified_diff()
              ├─ GitHubAppService.create_file_commit()
              ├─ GitHubAppService.create_pull_request()
              └─ PatchPR 레코드 DB 저장
```

### 브랜치 명 규칙

```
vulnix/fix-{vulnerability_type}-{sha256(type:file:line)[:7]}
```

예시:
- `vulnix/fix-sql-injection-a1b2c3d`
- `vulnix/fix-xss-b2c3d4e`

밑줄(`_`)은 하이픈(`-`)으로 변환.

### 패치 불가(unpatchable) 처리

- `patchable=False`인 LLM 분석 결과 → PR 생성 없음
- `Vulnerability.manual_guide`: LLM 생성 수동 수정 가이드 저장
- `Vulnerability.manual_priority`: 심각도별 자동 매핑
  - `critical` → `P0`
  - `high` → `P1`
  - `medium` → `P2`
  - `low` → `P3`

### ADR-F03-002

PatchPR 레코드는 GitHub PR이 실제로 생성된 경우에만 저장한다.
패치 PR 생성 실패 시, 스캔 자체는 `completed` 상태를 유지한다.

---

## GitHubAppService 메서드 (신규)

| 메서드 | 설명 |
|--------|------|
| `create_branch(full_name, installation_id, branch_name, base_sha)` | 브랜치 생성. 422(이미 존재) 시 삭제 후 재생성 |
| `get_file_content(full_name, installation_id, file_path, ref)` | 파일 내용 + SHA 조회 (base64 디코딩) |
| `create_file_commit(full_name, installation_id, branch_name, file_path, content, message, file_sha)` | 파일 커밋 생성 (base64 인코딩) |
| `create_pull_request(full_name, installation_id, head, base, title, body, labels)` | PR 생성 + 라벨 추가 |
