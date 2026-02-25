# F-02 취약점 탐지 엔진 (Python) -- 테스트 명세

**버전**: v1.0
**작성일**: 2026-02-25

---

## 참조

- 설계서: `docs/specs/F-02-detection-engine/design.md`
- 인수조건: `docs/project/features.md` #F-02

---

## 1. 단위 테스트

### 1-1. SemgrepEngine

**파일**: `backend/tests/services/test_semgrep_engine.py`

| # | 대상 메서드 | 시나리오 | 입력 | 예상 결과 |
|---|-------------|----------|------|-----------|
| 1 | `_parse_results` | 정상 Semgrep JSON 출력 파싱 | SQL Injection 1건 포함된 Semgrep JSON | `SemgrepFinding` 1건, `rule_id="vulnix.python.sql_injection.string_format"`, `severity="ERROR"`, `cwe=["CWE-89"]` |
| 2 | `_parse_results` | 복수 결과 파싱 | SQL Injection 2건 + XSS 1건 포함된 JSON | `SemgrepFinding` 3건 반환, 각각 올바른 rule_id/severity/cwe 매핑 |
| 3 | `_parse_results` | 결과 0건 | `{"results": [], "errors": []}` | 빈 리스트 반환 |
| 4 | `_parse_results` | file_path 상대 경로 변환 | `path="/tmp/vulnix-scan-xxx/app/db.py"`, base_dir=`/tmp/vulnix-scan-xxx` | `file_path="app/db.py"` |
| 5 | `_parse_results` | CWE 메타데이터 없는 결과 | metadata에 cwe 필드 없는 JSON | `cwe=[]` (빈 리스트) |
| 6 | `_run_semgrep_cli` | 정상 실행 (returncode=0) | 취약점 없는 코드 대상 | 빈 results 딕셔너리 반환 |
| 7 | `_run_semgrep_cli` | 취약점 발견 (returncode=1) | 취약 코드 대상 | results가 포함된 딕셔너리 반환 |
| 8 | `_run_semgrep_cli` | Semgrep 에러 (returncode=2) | 잘못된 룰 파일 경로 | `RuntimeError` 발생 |
| 9 | `_run_semgrep_cli` | Semgrep 미설치 | semgrep 바이너리 없는 환경 | `RuntimeError("Semgrep CLI가 설치되지 않았습니다")` |
| 10 | `_run_semgrep_cli` | 실행 타임아웃 | 600초 초과 실행 (mock) | `RuntimeError` 발생 (타임아웃 메시지 포함) |
| 11 | `scan` | 전체 통합 흐름 (mock subprocess) | SQL Injection 포함된 Python 파일이 있는 디렉토리 | `SemgrepFinding` 리스트 반환 |
| 12 | `prepare_temp_dir` | 임시 디렉토리 생성 | `job_id="test-123"` | `/tmp/vulnix-scan-test-123/` 경로의 디렉토리 존재 |
| 13 | `cleanup_temp_dir` | 임시 디렉토리 삭제 | 존재하는 임시 디렉토리 | 디렉토리가 삭제됨 |
| 14 | `cleanup_temp_dir` | 존재하지 않는 디렉토리 삭제 시도 | 존재하지 않는 경로 | 에러 없이 정상 종료 |

### 1-2. LLMAgent

**파일**: `backend/tests/services/test_llm_agent.py`

| # | 대상 메서드 | 시나리오 | 입력 | 예상 결과 |
|---|-------------|----------|------|-----------|
| 1 | `_build_analysis_prompt` | 정상 프롬프트 생성 | 파일 내용 + SemgrepFinding 2건 | 프롬프트 문자열에 소스 코드, 탐지 결과 2건, JSON 응답 형식 지시 포함 |
| 2 | `_build_analysis_prompt` | 빈 findings | 파일 내용 + 빈 리스트 | 탐지 결과 섹션이 비어있는 프롬프트 |
| 3 | `_build_patch_prompt` | 패치 프롬프트 생성 | 취약점 상세 + 원본 코드 | unified diff 형식 출력 지시 포함 |
| 4 | `_parse_analysis_response` | 정상 JSON 응답 파싱 | `{"results": [{"rule_id": "...", "is_true_positive": true, ...}]}` | 1건의 분석 결과 dict 반환 |
| 5 | `_parse_analysis_response` | 코드 블록 감싼 JSON | `` ```json {"results": [...]} ``` `` | 정상 파싱 (```json 래퍼 제거) |
| 6 | `_parse_analysis_response` | 잘못된 JSON 응답 | `"이 코드에는 취약점이..."` (자연어) | `json.JSONDecodeError` 발생 |
| 7 | `analyze_findings` | 빈 findings 입력 | `findings=[]` | 빈 리스트 반환, Claude API 미호출 |
| 8 | `analyze_findings` | 모두 오탐으로 판정 (mock) | 3건의 findings, LLM 응답에서 모두 `is_true_positive=false` | 3건의 `LLMAnalysisResult` 반환, 모두 `is_true_positive=False`, `_generate_patch` 미호출 |
| 9 | `analyze_findings` | 1건 진양성 + 2건 오탐 (mock) | 3건의 findings | 3건의 결과 중 1건만 `patch_diff` 값 존재 |
| 10 | `analyze_findings` | 전체 흐름 (mock Claude API) | SQL Injection SemgrepFinding 1건 + 해당 파일 내용 | `LLMAnalysisResult` 1건, `is_true_positive=True`, `severity="High"`, `patch_diff` 포함 |
| 11 | `_generate_patch` | 패치 생성 성공 (mock) | 취약 코드 + finding 정보 | unified diff 형식 문자열 반환 |
| 12 | `_generate_patch` | 패치 생성 불가 | 복잡한 구조의 취약점 (LLM이 패치 불가로 응답) | `None` 반환 |
| 13 | `_prepare_file_content` | 500줄 이하 파일 | 200줄 파일 + findings 2건 | 파일 전체 내용 반환 |
| 14 | `_prepare_file_content` | 500줄 초과 파일 | 1000줄 파일 + findings 1건 (라인 400) | 라인 350~450 주변 내용만 포함, 나머지는 생략 표시 |
| 15 | `_prepare_file_content` | 500줄 초과 + findings 5건 이상 | 800줄 파일 + findings 6건 | 파일 전체 내용 반환 |
| 16 | `_call_claude_with_retry` | Rate limit 후 재시도 성공 | 1회 RateLimitError, 2회 정상 응답 (mock) | 2초 대기 후 정상 응답 반환 |
| 17 | `_call_claude_with_retry` | 최대 재시도 초과 | 4회 연속 RateLimitError (mock) | `anthropic.RateLimitError` 발생 |
| 18 | `_call_claude_with_retry` | 서버 에러 후 재시도 | 1회 500 에러, 2회 정상 응답 (mock) | 정상 응답 반환 |
| 19 | `_call_claude_with_retry` | 4xx 에러는 재시도 안 함 | 1회 401 에러 (mock) | 즉시 `APIStatusError` 발생 (재시도 없음) |

### 1-3. VulnerabilityMapper

**파일**: `backend/tests/services/test_vulnerability_mapper.py`

| # | 대상 함수 | 시나리오 | 입력 | 예상 결과 |
|---|-----------|----------|------|-----------|
| 1 | `map_finding_to_vulnerability` | SQL Injection 매핑 | `rule_id="vulnix.python.sql_injection.string_format"`, `severity="ERROR"` | `{"vulnerability_type": "sql_injection", "cwe_id": "CWE-89", "owasp_category": "A03:2021 - Injection", "severity": "high"}` |
| 2 | `map_finding_to_vulnerability` | XSS 매핑 | `rule_id="vulnix.python.xss.flask_render_html"`, `severity="ERROR"` | `{"vulnerability_type": "xss", "cwe_id": "CWE-79", ...}` |
| 3 | `map_finding_to_vulnerability` | Hardcoded Credentials 매핑 | `rule_id="vulnix.python.hardcoded_creds.password_assignment"`, `severity="ERROR"` | `{"vulnerability_type": "hardcoded_credentials", "cwe_id": "CWE-798", ...}` |
| 4 | `map_finding_to_vulnerability` | 알 수 없는 rule_id | `rule_id="unknown.rule"`, `severity="WARNING"` | `{"vulnerability_type": "unknown", "cwe_id": None, "owasp_category": None, "severity": "medium"}` |
| 5 | `map_finding_to_vulnerability` | WARNING severity 매핑 | `rule_id=...`, `severity="WARNING"` | `severity="medium"` |
| 6 | `map_finding_to_vulnerability` | INFO severity 매핑 | `rule_id=...`, `severity="INFO"` | `severity="low"` |

---

## 2. 통합 테스트

### 2-1. ScanWorker 파이프라인

**파일**: `backend/tests/workers/test_scan_worker.py`

| # | 시나리오 | 사전 조건 | 입력 | 예상 결과 |
|---|----------|-----------|------|-----------|
| 1 | 전체 파이프라인 성공 (E2E mock) | Repository 레코드 존재, GitHub clone mock, Semgrep mock (2건), LLM mock (1 TP + 1 FP) | `ScanJobMessage` | ScanJob status="completed", findings_count=2, true_positives_count=1, false_positives_count=1, Vulnerability 1건 저장 |
| 2 | Semgrep 결과 0건 | Repository 존재, GitHub clone mock, Semgrep mock (0건) | `ScanJobMessage` | ScanJob status="completed", findings_count=0, LLM 미호출 |
| 3 | Semgrep 실행 실패 | Semgrep RuntimeError mock | `ScanJobMessage` | ScanJob status="failed", error_message에 에러 내용 기록 |
| 4 | LLM API 실패 (일부 파일) | 파일 3개 중 1개에서 LLM 에러 | `ScanJobMessage` | 나머지 2개 파일의 결과는 정상 저장, ScanJob status="completed" |
| 5 | LLM API 전체 실패 | 모든 LLM 호출 실패 | `ScanJobMessage` | ScanJob status="failed" |
| 6 | 임시 디렉토리 삭제 확인 | 정상 완료 후 | `ScanJobMessage` | `/tmp/vulnix-scan-{job_id}/` 존재하지 않음 |
| 7 | 실패 시에도 임시 디렉토리 삭제 | Semgrep 실패 후 | `ScanJobMessage` | `/tmp/vulnix-scan-{job_id}/` 존재하지 않음 (finally 블록) |
| 8 | Repository 조회 실패 | DB에 repo_id 미존재 | `ScanJobMessage` | ScanJob status="failed", error_message="Repository를 찾을 수 없습니다" |

### 2-2. Semgrep 룰 검증 (실제 Semgrep 실행)

**파일**: `backend/tests/rules/test_semgrep_rules.py`

**사전 조건**: Semgrep CLI 설치 필요. CI 환경에서는 Docker 이미지 사용.

| # | 취약점 유형 | 테스트 코드 | 탐지 여부 |
|---|-------------|-------------|-----------|
| 1 | SQL Injection (f-string) | `cursor.execute(f"SELECT * FROM users WHERE id={user_id}")` | 탐지됨 |
| 2 | SQL Injection (% format) | `cursor.execute("SELECT * FROM users WHERE id=%s" % user_id)` | 탐지됨 |
| 3 | SQL Injection (.format) | `cursor.execute("SELECT * FROM users WHERE id={}".format(user_id))` | 탐지됨 |
| 4 | SQL Injection (string concat) | `cursor.execute("SELECT * FROM users WHERE id=" + user_id)` | 탐지됨 |
| 5 | SQL Injection (SQLAlchemy text) | `sqlalchemy.text(f"SELECT * FROM users WHERE id={uid}")` | 탐지됨 |
| 6 | SQL Injection (Django raw) | `User.objects.raw(f"SELECT * FROM auth_user WHERE id={uid}")` | 탐지됨 |
| 7 | SQL Injection (안전한 코드) | `cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))` | 탐지 안 됨 |
| 8 | XSS (Flask make_response) | `flask.make_response(user_input)` | 탐지됨 |
| 9 | XSS (Markup) | `markupsafe.Markup(user_input)` | 탐지됨 |
| 10 | XSS (Jinja2 autoescape=False) | `jinja2.Environment(autoescape=False)` | 탐지됨 |
| 11 | XSS (Django mark_safe) | `django.utils.safestring.mark_safe(user_input)` | 탐지됨 |
| 12 | XSS (FastAPI HTMLResponse) | `HTMLResponse(content=f"<h1>{user_input}</h1>")` | 탐지됨 |
| 13 | XSS (안전한 코드) | `flask.escape(user_input)` 후 렌더링 | 탐지 안 됨 |
| 14 | Hardcoded Credentials (password) | `password = "my_secret_123"` | 탐지됨 |
| 15 | Hardcoded Credentials (api_key) | `API_KEY = "sk-1234567890abcdef"` | 탐지됨 |
| 16 | Hardcoded Credentials (AWS key) | `aws_key = "AKIAIOSFODNN7EXAMPLE"` | 탐지됨 |
| 17 | Hardcoded Credentials (DB URL) | `db_url = "postgresql://admin:p4ss@host:5432/db"` | 탐지됨 |
| 18 | Hardcoded Credentials (JWT secret) | `jwt.encode(payload, "my-secret-key", algorithm="HS256")` | 탐지됨 |
| 19 | Hardcoded Credentials (빈 문자열) | `password = ""` | 탐지 안 됨 |
| 20 | Hardcoded Credentials (환경변수) | `password = os.environ["DB_PASSWORD"]` | 탐지 안 됨 |
| 21 | Hardcoded Credentials (private key) | `key = "-----BEGIN RSA PRIVATE KEY-----\nMIIE..."` | 탐지됨 |

---

## 3. 경계 조건 / 에러 케이스

### 3-1. Semgrep 관련

| # | 경계 조건 | 입력 | 예상 동작 |
|---|-----------|------|-----------|
| 1 | 빈 디렉토리 스캔 | Python 파일 없는 디렉토리 | findings 0건 반환 (에러 아님) |
| 2 | 바이너리 파일만 있는 디렉토리 | .pyc, .so 파일만 존재 | findings 0건 반환 |
| 3 | 1MB 초과 Python 파일 | 50,000줄짜리 단일 파일 | Semgrep이 `--max-target-bytes` 설정에 의해 스킵, 경고만 기록 |
| 4 | 인코딩 오류 파일 | UTF-8이 아닌 인코딩 Python 파일 | Semgrep이 자체 처리 (에러 아님), errors 배열에 기록될 수 있음 |
| 5 | 심볼릭 링크 포함 디렉토리 | symlink 포함된 코드베이스 | Semgrep이 따라가서 스캔 (기본 동작) |
| 6 | 동시 스캔 시 임시 디렉토리 충돌 | 같은 repo에 대해 2개 스캔 동시 실행 | job_id가 다르므로 임시 디렉토리 경로 상이, 충돌 없음 |

### 3-2. LLM 관련

| # | 경계 조건 | 입력 | 예상 동작 |
|---|-----------|------|-----------|
| 1 | 1개 파일에 findings 20건 | 단일 파일에 20건의 Semgrep findings | 1번의 LLM 호출로 배치 처리 (파일 단위) |
| 2 | 30개 파일 각 1건 | 30개 파일에서 각 1건 발견 | asyncio.Semaphore(5)로 5건씩 순차 병렬 처리, 총 6 라운드 |
| 3 | LLM 응답에 추가 필드 포함 | JSON에 예상 외 필드 있음 | 무시하고 필요한 필드만 추출 |
| 4 | LLM confidence가 0.0 | 매우 불확실한 판단 | 결과에 포함되되, confidence 값 그대로 저장 |
| 5 | LLM이 severity를 Informational로 평가 | 낮은 위험 탐지 | severity="informational"로 저장 |
| 6 | 파일 읽기 실패 (스캔 중 삭제됨) | temp_dir 내 파일이 사라진 경우 | 해당 파일 스킵, 경고 로그, 나머지 파일 계속 처리 |

### 3-3. DB 저장 관련

| # | 경계 조건 | 입력 | 예상 동작 |
|---|-----------|------|-----------|
| 1 | 동일 위치 중복 취약점 | 같은 파일/라인에서 다른 rule_id로 2건 탐지 | 2건 모두 별도 Vulnerability 레코드로 저장 |
| 2 | code_snippet이 매우 긴 경우 | 10,000자 이상의 코드 조각 | DB Text 컬럼이므로 제한 없이 저장 (단, 전후 5줄로 잘라서 저장 권장) |
| 3 | references 배열이 빈 경우 | LLM이 참조 링크 미제공 | `references=[]` (JSONB 빈 배열)로 저장 |

---

## 4. 테스트 픽스처 (Sample Vulnerable Code)

**디렉토리**: `backend/tests/fixtures/sample_vulnerable_code/`

### 4-1. `sql_injection_samples.py`

```python
"""SQL Injection 테스트용 취약 코드 샘플"""
import sqlite3

# 취약: f-string SQL Injection
def get_user_by_id_vulnerable(user_id):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    return cursor.fetchone()

# 취약: % format SQL Injection
def search_users_vulnerable(name):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE name = '%s'" % name)
    return cursor.fetchall()

# 안전: parameterized query
def get_user_by_id_safe(user_id):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cursor.fetchone()
```

### 4-2. `xss_samples.py`

```python
"""XSS 테스트용 취약 코드 샘플"""
import flask
import markupsafe

# 취약: 사용자 입력 직접 응답
def render_user_input_vulnerable():
    user_input = flask.request.args.get("name")
    return flask.make_response(user_input)

# 취약: Markup으로 안전하지 않은 마킹
def markup_user_input_vulnerable():
    user_input = flask.request.args.get("comment")
    return markupsafe.Markup(user_input)

# 안전: escape 후 사용
def render_user_input_safe():
    user_input = flask.request.args.get("name")
    escaped = markupsafe.escape(user_input)
    return flask.make_response(f"Hello, {escaped}")
```

### 4-3. `hardcoded_creds_samples.py`

```python
"""Hardcoded Credentials 테스트용 취약 코드 샘플"""
import os

# 취약: 하드코딩된 패스워드
password = "super_secret_password_123"

# 취약: 하드코딩된 API 키
API_KEY = "sk-1234567890abcdef1234567890abcdef"

# 안전: 환경변수에서 로드
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

# 안전: 빈 기본값
default_password = ""
```

---

## 5. Mock 전략

### 5-1. Semgrep CLI Mock

```python
# subprocess.run을 mock하여 Semgrep CLI 실행을 시뮬레이션
@pytest.fixture
def mock_semgrep_output():
    return {
        "results": [
            {
                "check_id": "vulnix.python.sql_injection.string_format",
                "path": "/tmp/vulnix-scan-test/app/db.py",
                "start": {"line": 5, "col": 5},
                "end": {"line": 5, "col": 65},
                "extra": {
                    "message": "SQL Injection 취약점 탐지...",
                    "severity": "ERROR",
                    "lines": 'cursor.execute(f"SELECT * FROM users WHERE id={user_id}")',
                    "metadata": {
                        "cwe": ["CWE-89"],
                        "owasp": ["A03:2021 - Injection"],
                        "confidence": "HIGH",
                    },
                },
            }
        ],
        "errors": [],
    }

@pytest.fixture
def mock_subprocess_run(mock_semgrep_output):
    with unittest.mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["semgrep"],
            returncode=1,  # 1 = 취약점 발견
            stdout=json.dumps(mock_semgrep_output),
            stderr="",
        )
        yield mock_run
```

### 5-2. Claude API Mock

```python
# anthropic.AsyncAnthropic.messages.create를 mock
@pytest.fixture
def mock_claude_analysis_response():
    return {
        "results": [
            {
                "rule_id": "vulnix.python.sql_injection.string_format",
                "is_true_positive": True,
                "confidence": 0.95,
                "severity": "High",
                "reasoning": "사용자 입력(user_id)이 f-string을 통해 SQL 쿼리에 직접 삽입되어 있어 SQL Injection 공격에 취약합니다.",
                "owasp_category": "A03:2021 - Injection",
                "vulnerability_type": "sql_injection",
            }
        ]
    }

@pytest.fixture
def mock_claude_patch_response():
    return {
        "patch_diff": '--- a/app/db.py\n+++ b/app/db.py\n@@ -4,3 +4,3 @@\n-    cursor.execute(f"SELECT * FROM users WHERE id={user_id}")\n+    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))',
        "patch_description": "f-string SQL 쿼리를 파라미터화된 쿼리로 변경하여 SQL Injection 취약점을 수정합니다.",
        "references": ["https://cwe.mitre.org/data/definitions/89.html"],
    }
```

### 5-3. DB Session Mock

```python
# 테스트용 비동기 DB 세션 (SQLite 인메모리 사용)
@pytest.fixture
async def async_db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

---

## 6. 성능 테스트 시나리오

| # | 시나리오 | 조건 | 성공 기준 |
|---|----------|------|-----------|
| 1 | Semgrep 스캔 성능 | 1만 라인 Python 코드, 커스텀 룰 3카테고리 | 30초 이내 완료 |
| 2 | LLM 배치 처리 성능 | 10개 파일 x 2 findings, mock Claude API (0.5초 응답) | Semaphore(5) 기준 2초 이내 완료 |
| 3 | 전체 파이프라인 성능 | 10만 라인 (mock clone, 실제 Semgrep, mock LLM) | 5분 이내 완료 |

**참고**: 성능 테스트는 CI에서 매 빌드 실행하지 않고, `@pytest.mark.slow` 데코레이터로 분리하여 필요 시 수동 실행한다.

---

## 7. 인수조건 매핑

| 인수조건 | 검증 테스트 |
|----------|-------------|
| Semgrep 룰 기반 1차 AST 분석으로 후보 취약점 추출 | 단위 1-1 (#6~#11), 통합 2-2 (#1~#21) |
| Claude API 2차 분석으로 컨텍스트 기반 오탐 필터링 | 단위 1-2 (#7~#10), 통합 2-1 (#1, #2) |
| SQL Injection 취약점 탐지 가능 | 통합 2-2 (#1~#7) |
| XSS 취약점 탐지 가능 | 통합 2-2 (#8~#13) |
| Hardcoded Credentials 탐지 가능 | 통합 2-2 (#14~#21) |
| 심각도 분류: Critical / High / Medium / Low / Informational | 단위 1-2 (#9, #10), 단위 1-3 (#1~#6) |
| 각 취약점에 OWASP Top 10, CWE ID 매핑 | 단위 1-3 (#1~#3), 통합 2-1 (#1) |
| 10만 라인 Python 코드베이스 스캔 5분 이내 완료 | 성능 테스트 #3 |
| 탐지 정확도 80% 이상 | 통합 2-2 전체 (21건 중 17건 이상 정확) |

---

## 변경 이력

| 날짜 | 변경 내용 | 이유 |
|------|-----------|------|
| 2026-02-25 | 초안 작성 | F-02 테스트 명세 |
