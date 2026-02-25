# F-11 IDE 플러그인 (VS Code) -- 기술 설계서

## 1. 참조

- 인수조건: docs/project/features.md #F-11
- 시스템 설계: docs/system/system-design.md
- 의존 기능: F-02 (취약점 탐지 엔진), F-06 (오탐 관리)

## 2. 아키텍처 결정

### ADR-F11-001: 분석 방식 -- 직접 API 호출 vs Language Server Protocol

- **선택지**: A) `vscode-languageclient`를 사용한 LSP 서버 구축 / B) 직접 Vulnix 백엔드 REST API 호출
- **결정**: B) 직접 REST API 호출
- **근거**:
  - LSP 서버 방식은 로컬에 별도 프로세스를 실행해야 하므로 설치 복잡도가 높아진다
  - 기존 백엔드에 Semgrep 엔진과 LLM 에이전트가 이미 구현되어 있어, 서버 측 분석을 재사용하는 것이 효율적이다
  - IDE 플러그인은 경량 클라이언트로 유지하고, 분석 로직은 서버에 집중시켜 일관성을 확보한다
  - 서버가 다운되었을 때는 오프라인 모드(캐시된 결과 표시)로 graceful degradation 가능

### ADR-F11-002: 실시간 분석 트리거 전략 -- 문서 저장 시 vs 타이핑 디바운스

- **선택지**: A) 키 입력마다 디바운스(1~2초) 후 분석 / B) 문서 저장(`onDidSaveTextDocument`) 시 분석
- **결정**: B) 문서 저장 시 분석 (+ 수동 명령 트리거 보조)
- **근거**:
  - 키 입력마다 서버 API를 호출하면 과도한 네트워크 트래픽 및 서버 부하 발생
  - 저장 시 분석은 사용자가 "의미 있는 코드 상태"를 확정한 시점에서 분석하므로 결과 품질이 높다
  - 추가로 `Vulnix: Analyze Current File` 명령으로 수동 트리거 가능
  - 향후 필요시 디바운스 방식 추가 가능 (설정으로 전환)

### ADR-F11-003: IDE 분석용 백엔드 API -- Semgrep 전용 경량 엔드포인트

- **선택지**: A) 기존 전체 스캔 파이프라인(Semgrep + LLM) 재사용 / B) Semgrep 1차 분석만 수행하는 경량 엔드포인트 신설
- **결정**: B) Semgrep 1차 분석만 수행하는 경량 IDE 전용 엔드포인트 (`POST /api/v1/ide/analyze`)
- **근거**:
  - IDE 실시간 분석에서 LLM 호출(1~5초)은 UX에 치명적이다. Semgrep만으로 500ms 이내 응답 가능
  - LLM 분석이 필요한 경우 별도 패치 제안 엔드포인트(`POST /api/v1/ide/patch-suggestion`)를 사용자가 명시적으로 호출
  - API 비용 절감: 파일 저장마다 LLM이 호출되면 비용 폭발

### ADR-F11-004: 인증 방식 -- JWT vs API Key

- **선택지**: A) 기존 JWT Bearer 토큰 / B) 장기 유효 API Key
- **결정**: B) API Key 방식 (팀 단위 발급, `X-API-Key` 헤더)
- **근거**:
  - JWT는 30분 만료이므로 IDE에서 반복적인 토큰 갱신이 필요하여 UX 저하
  - API Key는 팀 설정에서 발급하고 VS Code 설정에 한 번만 입력하면 됨
  - API Key는 팀 ID와 연결되어 오탐 규칙 동기화 시 팀 식별에도 활용
  - 보안: API Key는 해시 저장, rate limit 적용, 언제든 재발급/비활성화 가능

### ADR-F11-005: 오프라인 / 서버 미연결 시 동작

- **선택지**: A) 오류 표시 후 기능 중단 / B) 마지막 동기화된 캐시 데이터로 제한 동작
- **결정**: B) 캐시 기반 제한 동작
- **근거**:
  - 오탐 패턴은 마지막 동기화 시점 데이터를 로컬 캐시(ExtensionContext.globalState)에 저장
  - 서버 미연결 시 새 분석은 불가하지만, 이전 분석 결과(진단 하이라이트)는 유지
  - 상태 표시줄에 연결 상태 아이콘 표시

---

## 3. API 설계

### 3-1. 신규 API: IDE 전용 엔드포인트

#### POST /api/v1/ide/analyze

- **목적**: 단일 파일의 코드 스니펫을 Semgrep으로 실시간 분석하여 취약점 후보를 반환한다
- **인증**: API Key (`X-API-Key` 헤더)
- **성능 목표**: p95 < 500ms

**Request Body**:

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

**Response (200)**:

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

**에러 케이스**:

| HTTP 코드 | 에러 코드 | 상황 |
|-----------|-----------|------|
| 400 | INVALID_LANGUAGE | 지원하지 않는 언어 |
| 400 | CONTENT_TOO_LARGE | content가 1MB 초과 |
| 401 | INVALID_API_KEY | API Key 누락 또는 유효하지 않음 |
| 403 | API_KEY_DISABLED | 비활성화된 API Key |
| 429 | RATE_LIMIT_EXCEEDED | 분당 60회 초과 |
| 500 | ANALYSIS_FAILED | Semgrep 실행 실패 |

---

#### GET /api/v1/ide/false-positive-patterns

- **목적**: 팀의 활성 오탐 패턴 목록을 반환한다 (IDE 로컬 캐시용)
- **인증**: API Key (`X-API-Key` 헤더)
- **캐싱**: `ETag` 헤더 지원. 클라이언트가 `If-None-Match`로 변경 여부를 확인하면 304 응답

**Response (200)**:

```json
{
  "success": true,
  "data": {
    "patterns": [
      {
        "id": "uuid",
        "semgrep_rule_id": "python.flask.security.xss",
        "file_pattern": "tests/**",
        "reason": "테스트 코드에서 XSS 탐지 무시",
        "is_active": true,
        "updated_at": "2026-02-25T10:00:00Z"
      }
    ],
    "last_updated": "2026-02-25T10:00:00Z",
    "etag": "\"abc123def\""
  },
  "error": null
}
```

**에러 케이스**:

| HTTP 코드 | 에러 코드 | 상황 |
|-----------|-----------|------|
| 304 | - | `If-None-Match` ETag 일치 (변경 없음) |
| 401 | INVALID_API_KEY | API Key 유효하지 않음 |

---

#### POST /api/v1/ide/patch-suggestion

- **목적**: 특정 취약점에 대해 LLM 기반 패치 diff를 생성한다
- **인증**: API Key (`X-API-Key` 헤더)
- **성능**: LLM 호출 포함이므로 2~10초 소요. 클라이언트는 로딩 표시 필요

**Request Body**:

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

**Response (200)**:

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

**에러 케이스**:

| HTTP 코드 | 에러 코드 | 상황 |
|-----------|-----------|------|
| 400 | INVALID_FINDING | finding 정보 불완전 |
| 401 | INVALID_API_KEY | API Key 유효하지 않음 |
| 429 | RATE_LIMIT_EXCEEDED | 분당 10회 초과 (LLM 비용 보호) |
| 502 | LLM_SERVICE_UNAVAILABLE | Claude API 호출 실패 |
| 504 | LLM_TIMEOUT | Claude API 응답 타임아웃 (30초) |

---

#### POST /api/v1/ide/api-keys

- **목적**: 팀용 IDE API Key를 발급한다
- **인증**: JWT Bearer (owner/admin만)

**Request Body**:

```json
{
  "name": "Team IDE Key",
  "expires_in_days": 365
}
```

**Response (201)**:

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "Team IDE Key",
    "key": "vx_live_a1b2c3d4e5f6...",
    "key_prefix": "vx_live_a1b2",
    "expires_at": "2027-02-25T00:00:00Z",
    "created_at": "2026-02-25T00:00:00Z"
  },
  "error": null
}
```

> 주의: `key`는 발급 시 한 번만 표시. 이후 조회 시 `key_prefix`만 노출.

---

#### DELETE /api/v1/ide/api-keys/{key_id}

- **목적**: API Key를 비활성화(논리 삭제)한다
- **인증**: JWT Bearer (owner/admin만)

**Response (200)**:

```json
{
  "success": true,
  "data": { "id": "uuid", "name": "Team IDE Key", "revoked_at": "2026-02-25T12:00:00Z" },
  "error": null
}
```

---

### 3-2. API Key 인증 미들웨어

API Key 검증 흐름:

```
요청 수신 (X-API-Key: vx_live_xxx)
  -> SHA-256 해시 계산
  -> DB에서 해시값 조회 (api_key 테이블)
  -> 만료일/활성 상태 확인
  -> team_id 추출하여 요청 컨텍스트에 주입
```

Rate Limit 정책:

| 엔드포인트 | 제한 | 단위 |
|-----------|------|------|
| `POST /ide/analyze` | 60회 | 분 |
| `GET /ide/false-positive-patterns` | 30회 | 분 |
| `POST /ide/patch-suggestion` | 10회 | 분 |

Rate Limit 구현: Redis 기반 sliding window counter (기존 Upstash Redis 활용)

---

## 4. DB 설계

### 신규 테이블: api_key

IDE API Key를 저장한다. 팀 단위로 발급되며, 해시값만 저장 (원본 키는 발급 시 한 번만 노출).

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|----------|------|
| id | UUID | PK, DEFAULT uuid_generate_v4() | 기본 키 |
| team_id | UUID | FK -> team.id, NOT NULL, INDEX | 소속 팀 |
| name | VARCHAR(255) | NOT NULL | 키 이름 (사용자 지정) |
| key_hash | VARCHAR(64) | NOT NULL, UNIQUE, INDEX | SHA-256 해시 (원본 키 미저장) |
| key_prefix | VARCHAR(20) | NOT NULL | 키 앞 12자리 (조회 시 표시용) |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE | 활성 여부 |
| last_used_at | TIMESTAMPTZ | NULL | 마지막 사용 시각 |
| expires_at | TIMESTAMPTZ | NULL | 만료 일시 (NULL이면 무기한) |
| created_by | UUID | FK -> user.id, NULL | 발급자 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 생성 시각 |
| revoked_at | TIMESTAMPTZ | NULL | 비활성화 시각 |

**인덱스**:

```sql
CREATE UNIQUE INDEX idx_api_key_hash ON api_key(key_hash);
CREATE INDEX idx_api_key_team ON api_key(team_id);
CREATE INDEX idx_api_key_active ON api_key(team_id, is_active) WHERE is_active = TRUE;
```

---

## 5. VS Code 익스텐션 설계

### 5-1. 디렉토리 구조

```
vscode-extension/
  package.json            -- VS Code 메타데이터, contributes, activationEvents
  tsconfig.json           -- TypeScript 컴파일 설정
  .vscodeignore           -- 패키징 제외 파일
  src/
    extension.ts          -- activate/deactivate 진입점, 전체 초기화
    config.ts             -- 설정 관리 (서버 URL, API Key 읽기)
    api/
      client.ts           -- HTTP 클라이언트 (fetch 래퍼, 인증 헤더, 에러 핸들링)
      types.ts            -- API 요청/응답 TypeScript 타입 정의
    analyzer/
      analyzer.ts         -- 분석 오케스트레이터 (파일 저장 이벤트 -> API 호출 -> 결과 전달)
      fp-cache.ts         -- 오탐 패턴 로컬 캐시 (ExtensionContext.globalState 기반)
    diagnostics/
      diagnostics.ts      -- DiagnosticCollection 관리 (빨간/노란 밑줄 표시)
      diagnostic-mapper.ts-- API 응답 -> vscode.Diagnostic 변환
    code-actions/
      code-actions.ts     -- CodeActionProvider (전구 아이콘 -> 패치 적용/상세 보기)
      patch-applier.ts    -- 패치 diff를 WorkspaceEdit로 변환하여 코드 수정
    webview/
      webview.ts          -- WebviewPanel 생성 및 관리
      panel-content.ts    -- 취약점 상세 HTML 생성
    status/
      status-bar.ts       -- 상태 표시줄 아이콘 (연결 상태, 취약점 수)
  test/
    suite/
      extension.test.ts   -- activate/deactivate 테스트
      analyzer.test.ts    -- 분석 로직 단위 테스트
      diagnostics.test.ts -- 진단 매핑 테스트
      code-actions.test.ts-- 코드 액션 테스트
      fp-cache.test.ts    -- 오탐 캐시 테스트
    fixtures/
      sample-python.py    -- 취약점이 포함된 테스트용 Python 파일
      api-responses.json  -- 모킹용 API 응답 데이터
```

### 5-2. package.json 주요 설정

```jsonc
{
  "name": "vulnix-security",
  "displayName": "Vulnix Security Scanner",
  "description": "Real-time security vulnerability detection and auto-fix for your code",
  "version": "0.1.0",
  "publisher": "vulnix",
  "engines": { "vscode": "^1.85.0" },
  "categories": ["Linters", "Other"],
  "activationEvents": [
    "onLanguage:python",
    "onLanguage:javascript",
    "onLanguage:typescript",
    "onLanguage:java",
    "onLanguage:go"
  ],
  "main": "./out/extension.js",
  "contributes": {
    "configuration": {
      "title": "Vulnix Security",
      "properties": {
        "vulnix.serverUrl": {
          "type": "string",
          "default": "https://api.vulnix.dev",
          "description": "Vulnix 서버 URL"
        },
        "vulnix.apiKey": {
          "type": "string",
          "default": "",
          "description": "팀 API Key (vx_live_... 형식)"
        },
        "vulnix.analyzeOnSave": {
          "type": "boolean",
          "default": true,
          "description": "파일 저장 시 자동 분석"
        },
        "vulnix.severityFilter": {
          "type": "string",
          "enum": ["all", "high", "critical"],
          "default": "all",
          "description": "표시할 최소 심각도"
        }
      }
    },
    "commands": [
      {
        "command": "vulnix.analyzeFile",
        "title": "Vulnix: Analyze Current File"
      },
      {
        "command": "vulnix.showDetail",
        "title": "Vulnix: Show Vulnerability Detail"
      },
      {
        "command": "vulnix.syncFPPatterns",
        "title": "Vulnix: Sync False Positive Patterns"
      },
      {
        "command": "vulnix.clearDiagnostics",
        "title": "Vulnix: Clear All Diagnostics"
      }
    ]
  }
}
```

### 5-3. 핵심 모듈 상세

#### extension.ts (진입점)

```
activate(context: ExtensionContext):
  1. config에서 serverUrl, apiKey 로드
  2. ApiClient 인스턴스 생성
  3. DiagnosticCollection 생성 ('vulnix')
  4. StatusBarItem 생성 및 표시
  5. Analyzer 인스턴스 생성
  6. FPCache 인스턴스 생성 -> 초기 동기화 시작 (백그라운드)
  7. 이벤트 리스너 등록:
     - onDidSaveTextDocument -> analyzer.analyzeFile()
     - onDidCloseTextDocument -> diagnostics.clearFor(uri)
     - onDidChangeConfiguration -> config.reload()
  8. CodeActionProvider 등록 (python, javascript, typescript, java, go)
  9. 명령 핸들러 등록 (analyzeFile, showDetail, syncFPPatterns, clearDiagnostics)

deactivate():
  1. DiagnosticCollection.dispose()
  2. StatusBarItem.dispose()
```

#### analyzer/analyzer.ts (분석 오케스트레이터)

```
analyzeFile(document: TextDocument):
  1. 지원 언어 확인 (python/javascript/typescript/java/go)
  2. 파일 내용 추출 (document.getText())
  3. 파일 크기 확인 (1MB 초과 시 스킵)
  4. API 호출: POST /api/v1/ide/analyze
  5. 응답에서 findings 추출
  6. FPCache의 로컬 패턴과 클라이언트 측 추가 필터링
  7. diagnostics.update(document.uri, findings)
  8. statusBar.update(findings.length)
  9. findings를 내부 맵에 캐시 (코드 액션에서 참조)
```

#### diagnostics/diagnostics.ts (진단 표시)

```
Finding -> vscode.Diagnostic 변환 규칙:
  - severity 매핑:
    - critical -> DiagnosticSeverity.Error (빨간 밑줄)
    - high     -> DiagnosticSeverity.Error (빨간 밑줄)
    - medium   -> DiagnosticSeverity.Warning (노란 밑줄)
    - low      -> DiagnosticSeverity.Information (파란 밑줄)
  - range: new Range(start_line - 1, start_col, end_line - 1, end_col)
  - message: "[Vulnix] {severity}: {message} ({cwe_id})"
  - source: "Vulnix"
  - code: { value: rule_id, target: Uri.parse(cwe_url) }
  - tags: DiagnosticTag.Unnecessary (for Informational)
```

#### code-actions/code-actions.ts (패치 제안)

```
CodeActionProvider.provideCodeActions(document, range, context):
  1. context.diagnostics에서 Vulnix 진단만 필터
  2. 각 진단에 대해 두 가지 CodeAction 생성:
     a) "Vulnix: Apply Patch Fix" (CodeActionKind.QuickFix)
        - 전구 아이콘으로 표시
        - 선택 시: patch-suggestion API 호출 -> diff 적용
     b) "Vulnix: Show Vulnerability Detail" (CodeActionKind.Empty)
        - 선택 시: Webview 패널 오픈

applyPatch(document, finding):
  1. POST /api/v1/ide/patch-suggestion 호출
  2. 응답의 patch_diff를 파싱
  3. WorkspaceEdit 생성:
     - 영향 라인 범위의 텍스트를 패치된 텍스트로 교체
  4. workspace.applyEdit(edit) 실행
  5. 성공 시 해당 진단 제거
```

#### webview/webview.ts (상세 패널)

```
showDetail(finding):
  1. WebviewPanel 생성 (viewType: 'vulnix.detail', title: '[Vulnix] 취약점 상세')
  2. HTML 콘텐츠 생성:
     - 취약점 유형, 심각도 배지
     - CWE/OWASP 분류
     - 취약 코드 스니펫 (syntax highlight)
     - "왜 위험한가?" 설명
     - 패치 제안 diff (있는 경우)
     - 참고 링크 목록
     - "Apply Patch" 버튼 (webview -> extension 메시지)
  3. 메시지 핸들러: 'applyPatch' -> code-actions.applyPatch() 호출
```

#### analyzer/fp-cache.ts (오탐 패턴 캐시)

```
FPCache:
  - storage: ExtensionContext.globalState
  - storageKey: 'vulnix.fpPatterns'
  - etagKey: 'vulnix.fpPatternsEtag'

  sync():
    1. 저장된 ETag 조회
    2. GET /api/v1/ide/false-positive-patterns (If-None-Match: etag)
    3. 304 응답 -> 캐시 유지
    4. 200 응답 -> 캐시 갱신, 새 ETag 저장

  syncPeriodically():
    - setInterval로 5분마다 sync() 호출

  matchesAny(finding): boolean
    - 로컬 캐시된 패턴과 finding을 비교
    - rule_id + file_pattern(glob) 매칭 (minimatch 라이브러리 사용)
```

#### status/status-bar.ts (상태 표시줄)

```
StatusBarManager:
  - 위치: StatusBarAlignment.Left
  - 표시 형식:
    - 연결됨:  "$(shield) Vulnix: 3 issues"
    - 미연결:  "$(shield) Vulnix: offline"
    - 분석중:  "$(loading~spin) Vulnix: analyzing..."
  - 클릭 시: Problems 패널 열기 (command: workbench.actions.view.problems)
```

---

## 6. 시퀀스 흐름

### 6-1. 파일 저장 시 실시간 분석 흐름

```
사용자        VS Code         Analyzer       ApiClient      Backend API      Semgrep
  |              |               |              |               |               |
  |-- 파일 저장 ->|               |              |               |               |
  |              |-- onSave --->|              |               |               |
  |              |              |-- analyze -->|               |               |
  |              |              |              |-- POST ------->|               |
  |              |              |              |  /ide/analyze  |-- run scan -->|
  |              |              |              |               |<-- findings ---|
  |              |              |              |               |-- FP filter -->|
  |              |              |              |<-- 200 --------|               |
  |              |              |<-- findings -|               |               |
  |              |              |-- FP local -->|               |               |
  |              |              |   filter     |               |               |
  |              |<-- diag -----|               |               |               |
  |<-- 밑줄표시 --|              |               |               |               |
```

### 6-2. 패치 제안 수락 흐름

```
사용자        VS Code          CodeAction     ApiClient      Backend API       LLM Agent
  |              |                |              |               |                |
  |-- 전구 클릭 ->|                |              |               |                |
  |              |-- quickfix --->|              |               |                |
  |              |  "Apply Patch" |              |               |                |
  |              |               |-- request -->|               |                |
  |              |               |              |-- POST ------->|                |
  |              |               |              | /ide/patch-    |-- generate --->|
  |              |               |              |  suggestion    |<-- diff -------|
  |              |               |              |<-- 200 --------|                |
  |              |               |<-- diff -----|               |                |
  |              |               |              |               |                |
  |              |<-- applyEdit -|              |               |                |
  |<-- 코드 수정 -|               |              |               |                |
  |              |-- re-analyze->|              |               |                |
  |              |   (자동 저장)  |              |               |                |
```

### 6-3. 오탐 패턴 동기화 흐름

```
FPCache          ApiClient      Backend API
  |                |               |
  |-- 5분 주기 --->|               |
  |                |-- GET ------->|
  |                | /ide/false-   |
  |                |  positive-    |
  |                |  patterns     |
  |                | If-None-Match |
  |                |<-- 304 -------|  (변경 없음)
  |<-- 캐시 유지 ---|               |
  |                |               |
  | ... 5분 후 ... |               |
  |                |-- GET ------->|
  |                |<-- 200 -------|  (변경 있음)
  |<-- 캐시 갱신 ---|               |
```

---

## 7. 영향 범위

### 수정 필요 파일 (백엔드)

| 파일 | 변경 내용 |
|------|-----------|
| `backend/src/api/v1/router.py` | IDE 전용 라우터 등록 (`/ide` prefix) |
| `backend/src/config.py` | IDE rate limit 설정 추가 (선택) |
| `backend/src/api/deps.py` | API Key 인증 의존성 함수 추가 (`get_api_key_team`) |
| `backend/src/models/__init__.py` | ApiKey 모델 import 추가 |

### 신규 생성 파일 (백엔드)

| 파일 | 설명 |
|------|------|
| `backend/src/api/v1/ide.py` | IDE 전용 엔드포인트 (analyze, patch-suggestion, FP 패턴, API Key CRUD) |
| `backend/src/models/api_key.py` | ApiKey SQLAlchemy 모델 |
| `backend/src/schemas/ide.py` | IDE 전용 Pydantic 스키마 (요청/응답) |
| `backend/src/services/ide_analyzer.py` | IDE 분석 서비스 (Semgrep 실행 + FP 필터 + 응답 구성) |
| `backend/src/services/api_key_service.py` | API Key 생성/검증/해시/rate limit 서비스 |
| `backend/alembic/versions/xxxx_add_api_key_table.py` | api_key 테이블 마이그레이션 |
| `backend/tests/api/test_ide.py` | IDE 엔드포인트 통합 테스트 |
| `backend/tests/services/test_ide_analyzer.py` | IDE 분석 서비스 단위 테스트 |
| `backend/tests/services/test_api_key_service.py` | API Key 서비스 단위 테스트 |

### 신규 생성 파일 (VS Code 익스텐션)

| 파일 | 설명 |
|------|------|
| `vscode-extension/package.json` | VS Code 메타데이터 및 contributes 설정 |
| `vscode-extension/tsconfig.json` | TypeScript 컴파일 설정 |
| `vscode-extension/.vscodeignore` | 패키징 제외 파일 |
| `vscode-extension/src/extension.ts` | 진입점 |
| `vscode-extension/src/config.ts` | 설정 관리 |
| `vscode-extension/src/api/client.ts` | HTTP 클라이언트 |
| `vscode-extension/src/api/types.ts` | API 타입 정의 |
| `vscode-extension/src/analyzer/analyzer.ts` | 분석 오케스트레이터 |
| `vscode-extension/src/analyzer/fp-cache.ts` | 오탐 패턴 캐시 |
| `vscode-extension/src/diagnostics/diagnostics.ts` | DiagnosticCollection 관리 |
| `vscode-extension/src/diagnostics/diagnostic-mapper.ts` | API 응답 -> Diagnostic 변환 |
| `vscode-extension/src/code-actions/code-actions.ts` | CodeActionProvider |
| `vscode-extension/src/code-actions/patch-applier.ts` | 패치 적용 (WorkspaceEdit) |
| `vscode-extension/src/webview/webview.ts` | WebviewPanel 관리 |
| `vscode-extension/src/webview/panel-content.ts` | 상세 패널 HTML 생성 |
| `vscode-extension/src/status/status-bar.ts` | 상태 표시줄 |
| `vscode-extension/test/suite/extension.test.ts` | activate/deactivate 테스트 |
| `vscode-extension/test/suite/analyzer.test.ts` | 분석 로직 테스트 |
| `vscode-extension/test/suite/diagnostics.test.ts` | 진단 매핑 테스트 |
| `vscode-extension/test/suite/code-actions.test.ts` | 코드 액션 테스트 |
| `vscode-extension/test/suite/fp-cache.test.ts` | 오탐 캐시 테스트 |
| `vscode-extension/test/fixtures/sample-python.py` | 테스트용 취약 코드 |
| `vscode-extension/test/fixtures/api-responses.json` | 모킹용 API 응답 |

---

## 8. 성능 설계

### 8-1. 백엔드 성능

#### IDE 분석 엔드포인트 성능 최적화

1. **임시 파일 기반 Semgrep 실행**: 전송받은 코드를 `/tmp/vulnix-ide-{request_id}/` 에 단일 파일로 저장한 후 Semgrep 실행. 완료 즉시 삭제.
2. **Semgrep 프로세스 풀**: IDE 요청 특성상 빈번하므로, Semgrep CLI를 매번 프로세스로 실행하는 대신 `semgrep scan --json` 결과를 캐시하거나, 룰 사전 로드를 통해 cold start 최소화.
3. **응답 목표**: p95 < 500ms (단일 파일 1,000줄 기준)

#### Rate Limit 구현

- Redis의 `INCR` + `EXPIRE`를 사용한 sliding window counter
- 키 형식: `vulnix:ratelimit:{team_id}:{endpoint}:{minute_bucket}`

### 8-2. 익스텐션 성능

1. **분석 디바운스**: 짧은 시간 내 연속 저장 시 마지막 저장만 분석 (500ms 디바운스)
2. **대용량 파일 스킵**: 1MB 초과 파일은 자동 분석 생략 (수동 분석은 가능)
3. **비동기 분석**: API 호출은 모두 비동기. UI 스레드를 차단하지 않음
4. **패치 제안 지연 로딩**: 전구 아이콘 클릭 시에만 LLM API 호출 (사전 호출 없음)
5. **오탐 캐시**: ETag 기반 조건부 요청으로 불필요한 데이터 전송 최소화

### 8-3. 인덱스 계획

```sql
-- api_key 해시 조회 (O(1) lookup)
CREATE UNIQUE INDEX idx_api_key_hash ON api_key(key_hash);

-- 팀별 활성 API Key 조회
CREATE INDEX idx_api_key_team_active ON api_key(team_id, is_active) WHERE is_active = TRUE;
```

### 8-4. 캐싱 전략

| 대상 | 캐시 방식 | TTL | 무효화 |
|------|-----------|-----|--------|
| 오탐 패턴 (IDE 클라이언트) | ExtensionContext.globalState | 5분 | ETag 기반 조건부 갱신 |
| API Key -> team_id 매핑 | Redis | 5분 | API Key 삭제 시 Redis DEL |
| Semgrep 룰셋 로드 | 메모리 (프로세스 내) | 앱 재시작 시 | 룰 변경 시 reload |

---

## 9. 보안 고려사항

### 9-1. API Key 보안

- 원본 키는 발급 시 한 번만 전달. DB에는 SHA-256 해시만 저장
- 키 형식: `vx_live_{32자 랜덤 hex}` (프로덕션) / `vx_test_{32자 랜덤 hex}` (테스트)
- VS Code settings에 저장 시 `"scope": "machine"` 으로 기기별 격리
- 키 재발급/비활성화 기능으로 유출 시 즉시 대응 가능

### 9-2. 코드 전송 보안

- 분석용 코드는 HTTPS로만 전송
- 서버에서는 임시 파일로 저장 후 분석 완료 즉시 삭제 (ADR-003 준수)
- API 로그에 코드 내용을 기록하지 않음 (file_path와 findings만 기록)

### 9-3. Rate Limit

- 팀 단위 rate limit으로 남용 방지
- LLM 호출이 포함된 patch-suggestion은 엄격한 제한 (분당 10회)

---

## 변경 이력

| 날짜 | 변경 내용 | 이유 |
|------|-----------|------|
| 2026-02-25 | 초안 작성 | F-11 기능 설계 시작 |
