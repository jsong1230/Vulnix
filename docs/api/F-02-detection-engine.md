# F-02 취약점 탐지 엔진 — API 스펙 확정본

**버전**: v1.0
**작성일**: 2026-02-25
**상태**: 확정

---

## 개요

F-02는 내부 파이프라인(스캔 워커)으로 구성됩니다. 외부에 노출되는 새로운 HTTP API는 없으며, F-01에서 트리거한 스캔 작업이 Redis 큐를 통해 실행됩니다.

---

## 내부 파이프라인 인터페이스

### SemgrepEngine

| 메서드 | 시그니처 | 설명 |
|--------|----------|------|
| `scan` | `scan(target_dir: Path, job_id: str) -> list[SemgrepFinding]` | Semgrep CLI 실행 및 결과 반환 |
| `_run_semgrep_cli` | `_run_semgrep_cli(cmd: list[str]) -> dict` | CLI 실행 및 JSON 파싱 |
| `_parse_results` | `_parse_results(semgrep_output: dict, base_dir: Path) -> list[SemgrepFinding]` | JSON -> SemgrepFinding 변환 |
| `prepare_temp_dir` | `@staticmethod prepare_temp_dir(job_id: str) -> Path` | 임시 디렉토리 생성 |
| `cleanup_temp_dir` | `@staticmethod cleanup_temp_dir(job_id: str) -> None` | 임시 디렉토리 삭제 |

#### SemgrepFinding 데이터 구조

```python
@dataclass
class SemgrepFinding:
    rule_id: str        # 예: "vulnix.python.sql_injection.string_format"
    severity: str       # ERROR / WARNING / INFO
    file_path: str      # 상대 경로
    start_line: int
    end_line: int
    code_snippet: str
    message: str
    cwe: list[str]      # 예: ["CWE-89"]
```

#### Semgrep CLI 명령

```bash
semgrep scan \
  --config /path/to/rules \
  --json \
  --quiet \
  --timeout 300 \
  --max-target-bytes 1000000 \
  --jobs 4 \
  /path/to/target
```

#### returncode 해석

| returncode | 의미 | 처리 |
|------------|------|------|
| 0 | 취약점 없음 (클린) | 정상 |
| 1 | 취약점 발견 | 정상 |
| >= 2 | Semgrep 내부 에러 | `RuntimeError` 발생 |

---

### LLMAgent

| 메서드 | 시그니처 | 설명 |
|--------|----------|------|
| `analyze_findings` | `async analyze_findings(file_content, file_path, findings) -> list[LLMAnalysisResult]` | 파일 단위 배치 분석 |
| `_generate_patch` | `async _generate_patch(finding, file_content) -> str or None` | 패치 diff 생성 |
| `_call_claude_with_retry` | `async _call_claude_with_retry(messages, system, max_retries) -> str` | 지수 백오프 재시도 |
| `_prepare_file_content` | `_prepare_file_content(content, findings, max_lines) -> str` | 토큰 최적화 |
| `_parse_analysis_response` | `_parse_analysis_response(response) -> list[dict]` | JSON 파싱 |

#### LLMAnalysisResult 데이터 구조

```python
@dataclass
class LLMAnalysisResult:
    finding_id: str          # Semgrep rule_id
    is_true_positive: bool
    confidence: float        # 0.0 ~ 1.0
    severity: str            # Critical / High / Medium / Low / Informational
    reasoning: str
    patch_diff: str | None   # unified diff 형식
    patch_description: str
    owasp_category: str | None
    vulnerability_type: str | None
    references: list[str]
```

#### Claude API 파라미터

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| model | claude-sonnet-4-6 | 분석/패치 생성 모델 |
| max_tokens | 4096 | 최대 응답 토큰 |
| temperature | 0.0 | 결정론적 응답 |

#### 재시도 정책

| 에러 유형 | 처리 방법 |
|-----------|-----------|
| RateLimitError (429) | 지수 백오프 재시도 (2s / 4s / 8s), 최대 3회 |
| APITimeoutError | 2초 후 재시도, 최대 3회 |
| APIStatusError 5xx | 지수 백오프 재시도, 최대 3회 |
| APIStatusError 4xx (429 제외) | 즉시 raise, 재시도 없음 |

---

### ScanWorker 파이프라인 (`_run_scan_async`)

```
1. ScanJob status -> "running"
2. Repository DB 조회
3. GitHubAppService.clone_repository() -> /tmp/vulnix-scan-{job_id}/
4. SemgrepEngine.scan() -> list[SemgrepFinding]
5. findings == 0 -> status="completed", return
6. _run_llm_analysis_batch() (asyncio.Semaphore(5))
   -> 파일별 LLMAgent.analyze_findings()
7. _save_vulnerabilities() -> DB에 Vulnerability 저장
8. _update_scan_stats() -> ScanJob 통계 업데이트
9. ScanJob status -> "completed"
[finally] SemgrepEngine.cleanup_temp_dir()
```

#### 오류 처리 흐름

```
Exception 발생 시:
  -> ScanJob status -> "failed" (error_message 기록)
  -> raise (RQ 재시도 처리)
  [finally] SemgrepEngine.cleanup_temp_dir() (반드시 실행)
```

---

### VulnerabilityMapper

| 함수 | 시그니처 | 설명 |
|------|----------|------|
| `map_finding_to_vulnerability` | `map_finding_to_vulnerability(rule_id, semgrep_severity) -> dict` | rule_id -> 취약점 메타데이터 매핑 |

#### 반환 형식

```python
{
    "vulnerability_type": "sql_injection",  # or "xss", "hardcoded_credentials", "unknown"
    "cwe_id": "CWE-89",                    # or None
    "owasp_category": "A03:2021 - Injection",  # or None
    "severity": "high",                    # "high" / "medium" / "low"
}
```

#### 지원 rule_id 매핑

| rule_id | vulnerability_type | CWE | OWASP |
|---------|--------------------|-----|-------|
| `vulnix.python.sql_injection.string_format` | sql_injection | CWE-89 | A03:2021 |
| `vulnix.python.sql_injection.string_concat` | sql_injection | CWE-89 | A03:2021 |
| `vulnix.python.sql_injection.sqlalchemy_text` | sql_injection | CWE-89 | A03:2021 |
| `vulnix.python.sql_injection.django_raw` | sql_injection | CWE-89 | A03:2021 |
| `vulnix.python.sql_injection.django_extra` | sql_injection | CWE-89 | A03:2021 |
| `vulnix.python.xss.flask_render_html` | xss | CWE-79 | A03:2021 |
| `vulnix.python.xss.flask_markup_unsafe` | xss | CWE-79 | A03:2021 |
| `vulnix.python.xss.jinja2_autoescape_disabled` | xss | CWE-79 | A03:2021 |
| `vulnix.python.xss.django_mark_safe` | xss | CWE-79 | A03:2021 |
| `vulnix.python.xss.fastapi_html_response` | xss | CWE-79 | A03:2021 |
| `vulnix.python.hardcoded_creds.password_assignment` | hardcoded_credentials | CWE-798 | A07:2021 |
| `vulnix.python.hardcoded_creds.api_key` | hardcoded_credentials | CWE-798 | A07:2021 |
| `vulnix.python.hardcoded_creds.aws_access_key` | hardcoded_credentials | CWE-798 | A07:2021 |
| `vulnix.python.hardcoded_creds.db_connection_string` | hardcoded_credentials | CWE-798 | A07:2021 |
| `vulnix.python.hardcoded_creds.jwt_secret` | hardcoded_credentials | CWE-798 | A07:2021 |
| `vulnix.python.hardcoded_creds.private_key` | hardcoded_credentials | CWE-798 | A07:2021 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|------|-----------|
| 2026-02-25 | 초안 작성 (F-02 구현 완료) |
