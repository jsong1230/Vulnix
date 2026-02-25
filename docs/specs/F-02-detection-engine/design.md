# F-02 취약점 탐지 엔진 (Python) -- 기술 설계서

**버전**: v1.0
**작성일**: 2026-02-25
**상태**: 초안

---

## 1. 참조

- 인수조건: `docs/project/features.md` #F-02
- 시스템 설계: `docs/system/system-design.md` 3-3절 (Semgrep), 3-4절 (LLM Agent)
- 아키텍처 결정: `docs/system/system-design.md` ADR-001 (하이브리드 탐지), ADR-003 (코드 보안)

---

## 2. 구현 범위

### 수정 대상 파일

| 파일 경로 | 변경 유형 | 설명 |
|-----------|-----------|------|
| `backend/src/services/semgrep_engine.py` | 구현 | `scan()`, `_run_semgrep_cli()`, `_parse_results()` TODO 구현 |
| `backend/src/services/llm_agent.py` | 구현 | `analyze_findings()`, `_generate_patch()` TODO 구현 |
| `backend/src/workers/scan_worker.py` | 구현 | `_run_scan_async()` 전체 파이프라인 TODO 구현 |
| `backend/src/rules/python/sql_injection.yml` | 개선 | Django ORM raw(), extra() 패턴 추가 |
| `backend/src/rules/python/xss.yml` | 개선 | FastAPI HTMLResponse 패턴 추가 |
| `backend/src/rules/python/hardcoded_creds.yml` | 개선 | JWT secret, private key 패턴 추가 |

### 신규 생성 파일

| 파일 경로 | 설명 |
|-----------|------|
| `backend/src/services/vulnerability_mapper.py` | Semgrep rule_id -> vulnerability_type / CWE / OWASP 매핑 유틸리티 |
| `backend/tests/services/test_semgrep_engine.py` | SemgrepEngine 단위 테스트 |
| `backend/tests/services/test_llm_agent.py` | LLMAgent 단위 테스트 |
| `backend/tests/workers/test_scan_worker.py` | ScanWorker 통합 테스트 |
| `backend/tests/fixtures/sample_vulnerable_code/` | 테스트용 취약 코드 샘플 디렉토리 |

---

## 3. 핵심 로직 상세

### 3-1. SemgrepEngine

#### 3-1-1. `scan(target_dir, job_id) -> list[SemgrepFinding]`

기존 스켈레톤의 TODO를 구현한다. 핵심 흐름:

```
scan()
  |-> _run_semgrep_cli(cmd)         # subprocess로 Semgrep CLI 실행
  |-> _parse_results(output, base)  # JSON 결과를 SemgrepFinding 목록으로 변환
  |-> return findings
```

**Semgrep CLI 실행 명령**:

```python
cmd = [
    "semgrep", "scan",
    "--config", str(self._rules_dir),   # 커스텀 룰만 사용 (--config=auto 제외)
    "--json",                            # JSON 출력
    "--quiet",                           # 진행 메시지 숨김
    "--timeout", "300",                  # 파일당 타임아웃 5분
    "--max-target-bytes", "1000000",     # 1MB 이상 파일 스킵
    "--jobs", "4",                       # 4개 코어 병렬 실행
    str(target_dir),
]
```

**설계 결정: `--config=auto` 제외**

- 선택지: A) `--config=auto` (Semgrep 공식 레지스트리) + 커스텀 룰 / B) 커스텀 룰만
- 결정: B) 커스텀 룰만
- 근거: PoC 단계에서 공식 레지스트리는 수천 개 룰을 포함하여 (1) 스캔 시간이 크게 증가하고 (2) 과도한 오탐이 발생하며 (3) CWE/OWASP 매핑을 직접 제어할 수 없다. 3가지 취약점 유형에 최적화된 커스텀 룰만 사용하여 정확도와 성능을 확보한다.

#### 3-1-2. `_run_semgrep_cli(cmd) -> dict`

```python
def _run_semgrep_cli(self, cmd: list[str]) -> dict:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 전체 실행 타임아웃 10분
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Semgrep 실행 타임아웃 (600초 초과): {e}") from e
    except FileNotFoundError as e:
        raise RuntimeError("Semgrep CLI가 설치되지 않았습니다") from e

    # returncode 해석:
    # 0 = 클린 (취약점 없음)
    # 1 = 취약점 발견 (정상)
    # 2+ = Semgrep 내부 에러
    if result.returncode >= 2:
        raise RuntimeError(
            f"Semgrep 실행 에러 (returncode={result.returncode}): {result.stderr}"
        )

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Semgrep 출력 JSON 파싱 실패: {e}") from e
```

#### 3-1-3. `_parse_results(semgrep_output, base_dir) -> list[SemgrepFinding]`

Semgrep JSON 출력의 `results` 배열을 순회하며 `SemgrepFinding`으로 변환한다.

**Semgrep JSON 출력 구조** (핵심 필드):

```json
{
  "results": [
    {
      "check_id": "vulnix.python.sql_injection.string_format",
      "path": "/tmp/vulnix-scan-xxx/app/db.py",
      "start": {"line": 42, "col": 5},
      "end": {"line": 42, "col": 55},
      "extra": {
        "message": "SQL Injection 취약점 탐지: ...",
        "severity": "ERROR",
        "lines": "cursor.execute(f\"SELECT * FROM users WHERE id={user_id}\")",
        "metadata": {
          "cwe": ["CWE-89"],
          "owasp": ["A03:2021 - Injection"],
          "confidence": "HIGH"
        }
      }
    }
  ],
  "errors": []
}
```

**파싱 로직**:

```python
def _parse_results(self, semgrep_output: dict, base_dir: Path) -> list[SemgrepFinding]:
    findings = []
    for result in semgrep_output.get("results", []):
        # 파일 경로를 base_dir 기준 상대 경로로 변환
        abs_path = Path(result["path"])
        try:
            rel_path = str(abs_path.relative_to(base_dir))
        except ValueError:
            rel_path = str(abs_path)

        metadata = result.get("extra", {}).get("metadata", {})

        finding = SemgrepFinding(
            rule_id=result["check_id"],
            severity=result.get("extra", {}).get("severity", "WARNING"),
            file_path=rel_path,
            start_line=result["start"]["line"],
            end_line=result["end"]["line"],
            code_snippet=result.get("extra", {}).get("lines", ""),
            message=result.get("extra", {}).get("message", ""),
            cwe=metadata.get("cwe", []),
        )
        findings.append(finding)

    return findings
```

**에러 처리**: `semgrep_output["errors"]` 배열이 비어있지 않으면 경고 로그를 남기되, 스캔을 중단하지는 않는다 (부분 결과라도 LLM에 전달).

### 3-2. LLMAgent

#### 3-2-1. `analyze_findings(file_content, file_path, findings) -> list[LLMAnalysisResult]`

기존 스켈레톤의 TODO를 구현한다. 2단계 프롬프트 전략을 사용한다.

**전체 흐름**:

```
analyze_findings()
  |-> _build_analysis_prompt()        # 1차 프롬프트 생성
  |-> Claude API 호출 (1차: 오탐 필터 + 심각도 평가)
  |-> _parse_analysis_response()      # 1차 응답 JSON 파싱
  |-> for each true_positive:
  |     |-> _generate_patch()          # 2차 프롬프트로 패치 생성
  |-> _enrich_with_references()       # CWE/OWASP 참조 링크 추가
  |-> return results
```

**설계 결정: Claude API 호출 방식**

- 선택지: A) `anthropic.Anthropic` (동기 클라이언트) / B) `anthropic.AsyncAnthropic` (비동기 클라이언트)
- 결정: B) `anthropic.AsyncAnthropic`
- 근거: `analyze_findings()`가 `async` 함수이고, 파일별 배치 처리 시 `asyncio.gather()`로 병렬 호출해야 하므로 비동기 클라이언트가 필수다. 기존 코드의 `self._client = anthropic.Anthropic()`을 `anthropic.AsyncAnthropic()`으로 변경한다.

**1차 프롬프트 (오탐 필터 + 심각도 평가)**:

기존 `_build_analysis_prompt()`에 아래 내용을 보강한다:

```
[시스템 프롬프트]
당신은 10년 이상 경력의 시니어 보안 엔지니어입니다.
정적 분석 도구의 결과를 검증하여 실제 취약점과 오탐을 구분합니다.
반드시 JSON 형식으로만 응답하세요.

[사용자 프롬프트]
다음 Python 코드에서 정적 분석 도구가 탐지한 취약점 목록입니다.
각 항목에 대해:
1. 코드의 전체 컨텍스트를 고려하여 실제 취약점인지 오탐인지 판단하세요
2. 실제 취약점이면 심각도를 평가하세요
3. 판단 근거를 설명하세요
4. OWASP Top 10 카테고리를 매핑하세요

판단 기준:
- 사용자 입력이 실제로 제어 가능한 경로로 전달되는지 확인
- 입력 검증/이스케이프 로직이 코드 내에 이미 존재하는지 확인
- 테스트 코드, 주석, 상수 할당 등은 오탐으로 분류
- 환경변수에서 읽는 값은 하드코딩으로 분류하지 않음

--- 파일: {file_path} ---
{file_content}

--- 탐지 결과 ---
{각 finding의 rule_id, 라인, 코드, 메시지}

JSON 응답 형식:
{
  "results": [
    {
      "rule_id": "해당 Semgrep 룰 ID",
      "is_true_positive": true/false,
      "confidence": 0.0~1.0,
      "severity": "Critical/High/Medium/Low/Informational",
      "reasoning": "판단 근거 2-3문장",
      "owasp_category": "A03:2021 - Injection",
      "vulnerability_type": "sql_injection"
    }
  ]
}
```

**Claude API 호출 파라미터**:

```python
response = await self._client.messages.create(
    model=CLAUDE_MODEL,
    max_tokens=4096,
    temperature=0.0,          # 결정론적 응답 (일관성 확보)
    system="당신은 10년 이상 경력의 시니어 보안 엔지니어입니다...",
    messages=[
        {"role": "user", "content": user_prompt}
    ],
)
```

- `temperature=0.0`: 동일 입력에 대해 일관된 판단을 보장
- `max_tokens=4096`: 20개 findings 기준 충분한 응답 공간

**1차 응답 파싱 (`_parse_analysis_response`)**:

```python
def _parse_analysis_response(self, response_text: str) -> list[dict]:
    # JSON 블록 추출 (```json ... ``` 래퍼 처리)
    text = response_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    parsed = json.loads(text.strip())
    return parsed.get("results", [])
```

**2차 프롬프트 (패치 생성)**: 1차에서 `is_true_positive=True`로 판정된 항목에만 호출한다.

기존 `_build_patch_prompt()`를 보강:

```
[시스템 프롬프트]
당신은 시니어 보안 엔지니어입니다. 보안 취약점에 대한 최소 패치 코드를 생성합니다.

[사용자 프롬프트]
다음 취약점에 대한 패치 코드를 생성하세요.
규칙:
- 기존 코드 스타일(들여쓰기, 네이밍 컨벤션)을 유지하세요
- 최소한의 변경으로 취약점만 수정하세요
- 기능 동작을 변경하지 마세요
- unified diff 형식으로 출력하세요
- 패치 설명을 간단히 추가하세요

--- 취약점 정보 ---
유형: {vulnerability_type} ({cwe_id})
심각도: {severity}
파일: {file_path} (Line {start_line}-{end_line})
설명: {reasoning}

--- 원본 코드 ---
{file_content}

JSON 응답 형식:
{
  "patch_diff": "--- a/file.py\n+++ b/file.py\n@@ ... @@\n...",
  "patch_description": "패치 설명",
  "references": ["https://cwe.mitre.org/data/definitions/89.html"]
}
```

#### 3-2-2. 토큰 사용량 최적화

**파일 내용 전송 전략**:

1. 파일이 500줄 이하: 전체 전송
2. 파일이 500줄 초과: 취약점 주변 +/-50줄 범위만 잘라서 전송 (컨텍스트 윈도우)
3. 하나의 파일에 findings가 5개 이상이면 파일 전체 전송

```python
def _prepare_file_content(
    self,
    file_content: str,
    findings: list[SemgrepFinding],
    max_lines: int = 500,
) -> str:
    lines = file_content.split("\n")
    if len(lines) <= max_lines or len(findings) >= 5:
        return file_content

    # 취약점 주변 +/-50줄 범위만 추출
    relevant_ranges = set()
    for f in findings:
        start = max(0, f.start_line - 50)
        end = min(len(lines), f.end_line + 50)
        for i in range(start, end):
            relevant_ranges.add(i)

    sorted_lines = sorted(relevant_ranges)
    result_parts = []
    prev_line = -2
    for line_num in sorted_lines:
        if line_num - prev_line > 1:
            result_parts.append(f"\n... (생략: 라인 {prev_line+2}~{line_num}) ...\n")
        result_parts.append(f"{line_num+1}: {lines[line_num]}")
        prev_line = line_num

    return "\n".join(result_parts)
```

### 3-3. VulnerabilityMapper (신규)

Semgrep rule_id를 DB Vulnerability 모델의 필드로 매핑하는 유틸리티.

```python
# backend/src/services/vulnerability_mapper.py

RULE_MAPPING = {
    # SQL Injection
    "vulnix.python.sql_injection.string_format": {
        "vulnerability_type": "sql_injection",
        "cwe_id": "CWE-89",
        "owasp_category": "A03:2021 - Injection",
    },
    "vulnix.python.sql_injection.string_concat": {
        "vulnerability_type": "sql_injection",
        "cwe_id": "CWE-89",
        "owasp_category": "A03:2021 - Injection",
    },
    "vulnix.python.sql_injection.sqlalchemy_text": {
        "vulnerability_type": "sql_injection",
        "cwe_id": "CWE-89",
        "owasp_category": "A03:2021 - Injection",
    },
    # Django 추가 룰
    "vulnix.python.sql_injection.django_raw": {
        "vulnerability_type": "sql_injection",
        "cwe_id": "CWE-89",
        "owasp_category": "A03:2021 - Injection",
    },
    "vulnix.python.sql_injection.django_extra": {
        "vulnerability_type": "sql_injection",
        "cwe_id": "CWE-89",
        "owasp_category": "A03:2021 - Injection",
    },

    # XSS
    "vulnix.python.xss.flask_render_html": {
        "vulnerability_type": "xss",
        "cwe_id": "CWE-79",
        "owasp_category": "A03:2021 - Injection",
    },
    "vulnix.python.xss.flask_markup_unsafe": {
        "vulnerability_type": "xss",
        "cwe_id": "CWE-79",
        "owasp_category": "A03:2021 - Injection",
    },
    "vulnix.python.xss.jinja2_autoescape_disabled": {
        "vulnerability_type": "xss",
        "cwe_id": "CWE-79",
        "owasp_category": "A03:2021 - Injection",
    },
    "vulnix.python.xss.django_mark_safe": {
        "vulnerability_type": "xss",
        "cwe_id": "CWE-79",
        "owasp_category": "A03:2021 - Injection",
    },
    # FastAPI 추가 룰
    "vulnix.python.xss.fastapi_html_response": {
        "vulnerability_type": "xss",
        "cwe_id": "CWE-79",
        "owasp_category": "A03:2021 - Injection",
    },

    # Hardcoded Credentials
    "vulnix.python.hardcoded_creds.password_assignment": {
        "vulnerability_type": "hardcoded_credentials",
        "cwe_id": "CWE-798",
        "owasp_category": "A07:2021 - Identification and Authentication Failures",
    },
    "vulnix.python.hardcoded_creds.api_key": {
        "vulnerability_type": "hardcoded_credentials",
        "cwe_id": "CWE-798",
        "owasp_category": "A07:2021 - Identification and Authentication Failures",
    },
    "vulnix.python.hardcoded_creds.aws_access_key": {
        "vulnerability_type": "hardcoded_credentials",
        "cwe_id": "CWE-798",
        "owasp_category": "A07:2021 - Identification and Authentication Failures",
    },
    "vulnix.python.hardcoded_creds.db_connection_string": {
        "vulnerability_type": "hardcoded_credentials",
        "cwe_id": "CWE-798",
        "owasp_category": "A07:2021 - Identification and Authentication Failures",
    },
    # 추가 룰
    "vulnix.python.hardcoded_creds.jwt_secret": {
        "vulnerability_type": "hardcoded_credentials",
        "cwe_id": "CWE-798",
        "owasp_category": "A07:2021 - Identification and Authentication Failures",
    },
    "vulnix.python.hardcoded_creds.private_key": {
        "vulnerability_type": "hardcoded_credentials",
        "cwe_id": "CWE-798",
        "owasp_category": "A07:2021 - Identification and Authentication Failures",
    },
}


# Semgrep severity -> Vulnix severity 초기 매핑
# (LLM이 재평가하므로 이 값은 fallback용)
SEVERITY_MAP = {
    "ERROR": "high",
    "WARNING": "medium",
    "INFO": "low",
}


def map_finding_to_vulnerability(rule_id: str, semgrep_severity: str) -> dict:
    """Semgrep rule_id를 Vulnerability 모델 필드로 매핑한다.

    Returns:
        {"vulnerability_type", "cwe_id", "owasp_category", "severity"}
    """
    mapping = RULE_MAPPING.get(rule_id, {})
    return {
        "vulnerability_type": mapping.get("vulnerability_type", "unknown"),
        "cwe_id": mapping.get("cwe_id"),
        "owasp_category": mapping.get("owasp_category"),
        "severity": SEVERITY_MAP.get(semgrep_severity, "medium"),
    }
```

### 3-4. ScanWorker (`_run_scan_async` 파이프라인)

기존 `scan_worker.py`의 `_run_scan_async()` TODO를 구현한다.

```python
async def _run_scan_async(message: ScanJobMessage) -> dict:
    semgrep = SemgrepEngine()
    github = GitHubAppService()
    llm = LLMAgent()
    patch_gen = PatchGenerator()

    temp_dir = SemgrepEngine.prepare_temp_dir(message.job_id)

    # DB 세션 획득 (워커 전용)
    async with get_async_session() as db:
        orchestrator = ScanOrchestrator(db)

        try:
            # 1. ScanJob 상태 -> running
            await orchestrator.update_job_status(message.job_id, "running")

            # 2. Repository 정보 DB 조회
            repo = await db.execute(
                select(Repository).where(Repository.id == uuid.UUID(message.repo_id))
            )
            repo = repo.scalar_one()

            # 3. git clone (임시 디렉토리)
            commit_sha = message.commit_sha
            if not commit_sha:
                commit_sha = await github.get_default_branch_sha(
                    repo.full_name, repo.installation_id, repo.default_branch,
                )
            await github.clone_repository(
                repo.full_name, repo.installation_id, commit_sha, temp_dir,
            )

            # 4. Semgrep 1차 스캔
            findings = semgrep.scan(temp_dir, message.job_id)
            logger.info(
                f"[WorkerID={message.job_id}] Semgrep 1차 스캔 완료: {len(findings)}건 탐지"
            )

            # 5. 결과 없으면 LLM 호출 스킵
            if not findings:
                await _update_scan_stats(db, message.job_id, 0, 0, 0)
                await orchestrator.update_job_status(message.job_id, "completed")
                return {"job_id": message.job_id, "status": "completed", "findings": 0}

            # 6. LLM 2차 분석 (파일별 배치)
            all_results = await _run_llm_analysis_batch(
                llm, findings, temp_dir, message.job_id,
            )
            logger.info(
                f"[WorkerID={message.job_id}] LLM 2차 분석 완료: "
                f"TP={sum(1 for r in all_results if r.is_true_positive)}, "
                f"FP={sum(1 for r in all_results if not r.is_true_positive)}"
            )

            # 7. Vulnerability 레코드 DB 저장
            vuln_records = await _save_vulnerabilities(
                db, message.job_id, repo.id, findings, all_results,
            )

            # 8. ScanJob 통계 업데이트
            tp_count = sum(1 for r in all_results if r.is_true_positive)
            fp_count = sum(1 for r in all_results if not r.is_true_positive)
            await _update_scan_stats(db, message.job_id, len(findings), tp_count, fp_count)

            # 9. ScanJob 상태 -> completed
            await orchestrator.update_job_status(message.job_id, "completed")

            return {
                "job_id": message.job_id,
                "status": "completed",
                "findings": len(findings),
                "true_positives": tp_count,
                "false_positives": fp_count,
            }

        except Exception as e:
            logger.error(f"[WorkerID={message.job_id}] 파이프라인 실패: {e}")
            await orchestrator.update_job_status(
                message.job_id, "failed", error_message=str(e),
            )
            raise

        finally:
            # 임시 디렉토리는 성공/실패 관계없이 항상 삭제 (ADR-003)
            SemgrepEngine.cleanup_temp_dir(message.job_id)
```

#### 3-4-1. 파일별 LLM 배치 처리 (`_run_llm_analysis_batch`)

Semgrep findings를 파일별로 그룹화한 뒤, `asyncio.gather()`로 병렬 호출한다.

```python
async def _run_llm_analysis_batch(
    llm: LLMAgent,
    findings: list[SemgrepFinding],
    temp_dir: Path,
    job_id: str,
    max_concurrent: int = 5,
) -> list[LLMAnalysisResult]:
    """파일별로 findings를 그룹화하여 LLM 배치 분석을 실행한다.

    Args:
        max_concurrent: 동시 LLM 호출 최대 수 (rate limit 대응)
    """
    # 파일별 그룹화
    file_groups: dict[str, list[SemgrepFinding]] = {}
    for f in findings:
        file_groups.setdefault(f.file_path, []).append(f)

    # asyncio.Semaphore로 동시 호출 수 제한
    semaphore = asyncio.Semaphore(max_concurrent)

    async def analyze_file(file_path: str, file_findings: list[SemgrepFinding]):
        async with semaphore:
            abs_path = temp_dir / file_path
            try:
                file_content = abs_path.read_text(encoding="utf-8")
            except (FileNotFoundError, UnicodeDecodeError) as e:
                logger.warning(f"파일 읽기 실패 ({file_path}): {e}")
                return []

            return await llm.analyze_findings(file_content, file_path, file_findings)

    tasks = [
        analyze_file(file_path, file_findings)
        for file_path, file_findings in file_groups.items()
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 예외 필터링 및 결과 병합
    all_results = []
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"LLM 분석 실패: {r}")
            continue
        all_results.extend(r)

    return all_results
```

**동시성 제한 근거**: Anthropic API rate limit는 일반적으로 분당 50~60 요청. `max_concurrent=5`로 설정하면 초당 최대 5건으로 충분히 안전하며, 파일 10개를 약 2초 내에 처리 가능.

#### 3-4-2. Vulnerability 레코드 저장 (`_save_vulnerabilities`)

```python
async def _save_vulnerabilities(
    db: AsyncSession,
    scan_job_id: str,
    repo_id: uuid.UUID,
    findings: list[SemgrepFinding],
    analysis_results: list[LLMAnalysisResult],
) -> list[Vulnerability]:
    """LLM 분석 결과를 Vulnerability 레코드로 DB에 저장한다.

    is_true_positive=True인 항목만 Vulnerability로 저장한다.
    is_true_positive=False인 항목은 ScanJob.false_positives_count에만 반영.
    """
    # rule_id 기준으로 findings를 인덱싱
    finding_map = {f.rule_id: f for f in findings}

    records = []
    for result in analysis_results:
        if not result.is_true_positive:
            continue

        finding = finding_map.get(result.finding_id)
        if not finding:
            continue

        mapping = map_finding_to_vulnerability(finding.rule_id, finding.severity)

        vuln = Vulnerability(
            scan_job_id=uuid.UUID(scan_job_id),
            repo_id=repo_id,
            status="open",
            severity=result.severity.lower(),  # LLM이 평가한 심각도 사용
            vulnerability_type=mapping["vulnerability_type"],
            cwe_id=mapping["cwe_id"],
            owasp_category=result.owasp_category if hasattr(result, 'owasp_category') else mapping["owasp_category"],
            file_path=finding.file_path,
            start_line=finding.start_line,
            end_line=finding.end_line,
            code_snippet=finding.code_snippet,
            description=finding.message,
            llm_reasoning=result.reasoning,
            llm_confidence=result.confidence,
            semgrep_rule_id=finding.rule_id,
            references=result.references,
            detected_at=datetime.now(timezone.utc),
        )
        db.add(vuln)
        records.append(vuln)

    await db.flush()
    return records
```

### 3-5. Semgrep 룰 개선

기존 룰을 검토한 결과, 다음 패턴을 추가하여 탐지 범위를 넓힌다.

#### 3-5-1. SQL Injection 룰 추가 (`sql_injection.yml`)

```yaml
  # Django ORM raw() 패턴 추가
  - id: vulnix.python.sql_injection.django_raw
    languages: [python]
    severity: ERROR
    message: |
      SQL Injection 취약점 탐지: Django raw() 쿼리에 사용자 입력을 직접 삽입하고 있습니다.
      params 인자로 전달하세요. 예: Model.objects.raw("SELECT ... WHERE id=%s", [user_id])
    metadata:
      cwe: ["CWE-89"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
      technology: [python, django]
    patterns:
      - pattern: |
          $MODEL.objects.raw(f"...{$INPUT}...")
      - pattern: |
          $MODEL.objects.raw("..." % $INPUT)
      - pattern: |
          $MODEL.objects.raw("..." + $INPUT)

  # Django ORM extra() 패턴 추가
  - id: vulnix.python.sql_injection.django_extra
    languages: [python]
    severity: WARNING
    message: |
      SQL Injection 위험: Django QuerySet.extra()에 사용자 입력이 전달될 수 있습니다.
      extra()는 deprecated이므로 annotation/F() 표현식으로 대체하세요.
    metadata:
      cwe: ["CWE-89"]
      owasp: ["A03:2021 - Injection"]
      confidence: MEDIUM
      category: security
      technology: [python, django]
    patterns:
      - pattern: |
          $QS.extra(where=[f"...{$INPUT}..."])
      - pattern: |
          $QS.extra(where=["..." % $INPUT])
```

#### 3-5-2. XSS 룰 추가 (`xss.yml`)

```yaml
  # FastAPI HTMLResponse 패턴 추가
  - id: vulnix.python.xss.fastapi_html_response
    languages: [python]
    severity: ERROR
    message: |
      XSS 취약점 탐지: FastAPI HTMLResponse에 사용자 입력을 이스케이프 없이 포함하고 있습니다.
      html.escape()로 사용자 입력을 이스케이프하세요.
    metadata:
      cwe: ["CWE-79"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
      technology: [python, fastapi]
    patterns:
      - pattern: |
          fastapi.responses.HTMLResponse(content=f"...{$INPUT}...")
      - pattern: |
          HTMLResponse(content=f"...{$INPUT}...")
      - pattern: |
          HTMLResponse(f"...{$INPUT}...")
```

#### 3-5-3. Hardcoded Credentials 룰 추가 (`hardcoded_creds.yml`)

```yaml
  # JWT Secret 하드코딩 탐지
  - id: vulnix.python.hardcoded_creds.jwt_secret
    languages: [python]
    severity: ERROR
    message: |
      Hardcoded Credentials 탐지: JWT 시크릿 키가 소스 코드에 하드코딩되어 있습니다.
      환경변수를 사용하세요.
    metadata:
      cwe: ["CWE-798"]
      owasp: ["A07:2021 - Identification and Authentication Failures"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: |
          jwt.encode($PAYLOAD, "...", ...)
      - pattern: |
          jwt.decode($TOKEN, "...", ...)
      - pattern: |
          SECRET_KEY = "..."
    pattern-not-regex: 'os\.environ|os\.getenv|getenv|settings\.'

  # Private Key 문자열 하드코딩 탐지
  - id: vulnix.python.hardcoded_creds.private_key
    languages: [python]
    severity: ERROR
    message: |
      Hardcoded Credentials 탐지: Private Key가 소스 코드에 하드코딩되어 있습니다.
      파일 또는 시크릿 관리 서비스에서 로드하세요.
    metadata:
      cwe: ["CWE-798"]
      owasp: ["A07:2021 - Identification and Authentication Failures"]
      confidence: HIGH
      category: security
    pattern-regex: '-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----'
```

---

## 4. 데이터 흐름

### 전체 파이프라인 시퀀스

```
GitHub Webhook / 수동 트리거
  |
  v
ScanOrchestrator.enqueue_scan()
  |-> ScanJob 레코드 생성 (status=queued)
  |-> Redis 큐에 메시지 등록
  |
  v
Redis Queue ("scans")
  |
  v
ScanWorker.run_scan(message)
  |-> asyncio.run(_run_scan_async)
  |
  v
_run_scan_async(message)
  |-> [1] ScanJob status -> "running"
  |-> [2] Repository 정보 DB 조회 (full_name, installation_id)
  |-> [3] GitHubAppService.clone_repository() -> /tmp/vulnix-scan-{job_id}/
  |-> [4] SemgrepEngine.scan(temp_dir, job_id) -> list[SemgrepFinding]
  |-> [5] findings == 0 이면 -> completed 처리, return
  |-> [6] _run_llm_analysis_batch()
  |       |-> 파일별 그룹화
  |       |-> asyncio.gather (max_concurrent=5)
  |       |     |-> LLMAgent.analyze_findings(file_content, findings)
  |       |           |-> [1차] Claude API: 오탐 필터 + 심각도 평가
  |       |           |-> [2차] Claude API: 패치 코드 생성 (TP만)
  |       |-> list[LLMAnalysisResult] 반환
  |-> [7] _save_vulnerabilities() -> Vulnerability 레코드 DB 저장
  |-> [8] ScanJob 통계 업데이트 (findings_count, tp_count, fp_count)
  |-> [9] ScanJob status -> "completed"
  |-> [finally] SemgrepEngine.cleanup_temp_dir(job_id)
```

### 데이터 변환 흐름

```
Semgrep JSON output
  -> list[SemgrepFinding]       (semgrep_engine._parse_results)
  -> 파일별 그룹화               (_run_llm_analysis_batch)
  -> list[LLMAnalysisResult]    (llm_agent.analyze_findings)
  -> list[Vulnerability]         (_save_vulnerabilities + vulnerability_mapper)
```

---

## 5. 오류 처리

### 5-1. Semgrep 실행 실패

| 오류 상황 | 처리 방법 |
|-----------|-----------|
| Semgrep CLI 미설치 (`FileNotFoundError`) | `RuntimeError` 발생, ScanJob -> failed |
| 실행 타임아웃 (600초 초과) | `RuntimeError` 발생, ScanJob -> failed |
| returncode >= 2 (내부 에러) | `RuntimeError` 발생, ScanJob -> failed |
| JSON 파싱 실패 | `RuntimeError` 발생, ScanJob -> failed |
| 부분 에러 (errors 배열 비어있지 않음) | 경고 로그, 부분 결과로 계속 진행 |

### 5-2. LLM API 오류

| 오류 상황 | 처리 방법 |
|-----------|-----------|
| Rate Limit (429) | `asyncio.Semaphore(5)` + 지수 백오프 재시도 (최대 3회, 대기 2초/4초/8초) |
| 응답 타임아웃 | Claude API timeout=120초 설정, 실패 시 해당 파일 스킵 |
| JSON 파싱 실패 (응답 형식 오류) | 경고 로그, 해당 파일의 findings를 Semgrep 결과만으로 저장 (LLM 미검증 상태) |
| API 키 무효 (401) | 즉시 ScanJob -> failed, 에러 메시지 기록 |
| 서버 에러 (500/503) | 지수 백오프 재시도 (최대 3회) |

**LLM 호출 재시도 로직**:

```python
async def _call_claude_with_retry(
    self,
    messages: list[dict],
    max_retries: int = 3,
) -> str:
    for attempt in range(max_retries + 1):
        try:
            response = await self._client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                temperature=0.0,
                messages=messages,
            )
            return response.content[0].text
        except anthropic.RateLimitError:
            if attempt == max_retries:
                raise
            wait = 2 ** (attempt + 1)  # 2, 4, 8초
            logger.warning(f"Rate limit 도달, {wait}초 후 재시도 ({attempt+1}/{max_retries})")
            await asyncio.sleep(wait)
        except anthropic.APITimeoutError:
            if attempt == max_retries:
                raise
            logger.warning(f"API 타임아웃, 재시도 ({attempt+1}/{max_retries})")
            await asyncio.sleep(2)
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                if attempt == max_retries:
                    raise
                await asyncio.sleep(2 ** (attempt + 1))
            else:
                raise  # 4xx 에러는 재시도하지 않음
```

### 5-3. 임시 디렉토리 관련

| 오류 상황 | 처리 방법 |
|-----------|-----------|
| `shutil.rmtree` 실패 (권한 문제) | 경고 로그 기록, ScanJob 상태는 정상 유지 (데이터는 이미 저장됨) |
| 잔존 임시 파일 | cron 작업으로 `/tmp/vulnix-scan-*` 중 생성 후 1시간 경과 디렉토리 정리 |
| 디스크 용량 부족 | clone_repository 실패 -> RuntimeError -> ScanJob failed |

### 5-4. DB 오류

| 오류 상황 | 처리 방법 |
|-----------|-----------|
| Repository 조회 실패 | ScanJob -> failed, "Repository를 찾을 수 없습니다" |
| Vulnerability 저장 실패 (unique constraint 등) | 트랜잭션 롤백 후 ScanJob -> failed |
| DB 연결 실패 | RQ가 자동 재시도 (Retry max=3) |

---

## 6. 성능 설계

### 6-1. 10만 라인 5분 이내 달성 전략

**병목 분석**:

| 단계 | 예상 소요 시간 | 비고 |
|------|----------------|------|
| git clone | 10~30초 | shallow clone (`--depth 1`) 사용 |
| Semgrep 1차 스캔 | 30~60초 | 4코어 병렬 실행 (`--jobs 4`) |
| LLM 2차 분석 | 60~180초 | 파일 수에 비례 (10파일 x 3초/파일 x 5병렬) |
| DB 저장 | 1~5초 | bulk insert |
| 합계 | 약 100~270초 | 5분(300초) 이내 달성 가능 |

**핵심 최적화 포인트**:

1. **Semgrep 실행 최적화**:
   - `--jobs 4`: CPU 코어 수에 맞게 병렬 실행
   - `--max-target-bytes 1000000`: 1MB 초과 파일 스킵 (대형 바이너리/빌드 결과물)
   - `--timeout 300`: 파일당 최대 5분
   - 커스텀 룰만 사용 (auto registry 미사용)

2. **LLM 호출 최적화**:
   - 파일별 배치 호출 (개별 finding 호출 대비 API 호출 수 90% 감소)
   - `asyncio.Semaphore(5)`: 동시 5건 병렬 호출
   - 500줄 초과 파일은 관련 라인만 추출 전송 (토큰 절약)
   - Semgrep findings가 없으면 LLM 미호출 (비용 0)

3. **git clone 최적화**:
   - `--depth 1`: shallow clone으로 히스토리 미포함
   - `--single-branch`: 대상 브랜치만 클론
   - sparse-checkout: incremental/PR 스캔 시 변경 파일만 가져오기 (향후)

### 6-2. 비용 추정

10만 라인 Python 코드베이스, 취약점 후보 20건 기준:

| 항목 | 추정 비용 |
|------|-----------|
| Semgrep | 무료 (오픈소스) |
| Claude API (1차 분석) | 약 10파일 x 4,000 input tokens x $3/M = ~$0.12 |
| Claude API (2차 패치) | 약 5건 x 5,000 input tokens x $3/M = ~$0.075 |
| **합계** | **약 $0.20/스캔** |

### 6-3. 인덱스 활용

기존 `system-design.md` 4-3절 인덱스 전략을 그대로 활용:

```sql
CREATE INDEX idx_vulnerability_repo_status ON vulnerability(repo_id, status);
CREATE INDEX idx_vulnerability_severity ON vulnerability(severity);
CREATE INDEX idx_scan_job_repo_status ON scan_job(repo_id, status);
CREATE INDEX idx_scan_job_created ON scan_job(created_at DESC);
```

---

## 7. 심각도 분류 체계

### 7-1. 5단계 심각도

인수조건에서 요구하는 `Informational` 레벨을 포함한 5단계:

| 심각도 | 기준 | 예시 |
|--------|------|------|
| Critical | 인증 없이 원격 코드 실행 또는 전체 데이터 유출 가능 | 인증 우회된 SQL Injection (admin 권한) |
| High | 사용자 데이터 유출 또는 권한 상승 가능 | 일반 SQL Injection, Stored XSS |
| Medium | 제한된 조건에서만 악용 가능 | Reflected XSS, 하드코딩된 개발용 API 키 |
| Low | 직접적 공격은 어렵지만 보안 위생 미달 | autoescape 비활성화 (XSS 간접 위험) |
| Informational | 보안 모범사례 미준수 | DB 커넥션 문자열에 비밀번호 포함 (내부망) |

### 7-2. Semgrep -> LLM 심각도 흐름

```
Semgrep severity (ERROR/WARNING/INFO)
  -> 초기 매핑 (SEVERITY_MAP: ERROR->high, WARNING->medium, INFO->low)
  -> LLM이 코드 컨텍스트 기반으로 재평가
  -> LLM 평가 결과를 최종 severity로 사용
```

Semgrep의 3단계(ERROR/WARNING/INFO)를 LLM이 5단계(Critical/High/Medium/Low/Informational)로 세분화한다.

### 7-3. CWE / OWASP 매핑

| 취약점 유형 | CWE ID | OWASP Top 10 (2021) |
|-------------|--------|---------------------|
| SQL Injection | CWE-89 | A03:2021 - Injection |
| XSS | CWE-79 | A03:2021 - Injection |
| Hardcoded Credentials | CWE-798 | A07:2021 - Identification and Authentication Failures |

---

## 8. LLMAnalysisResult 확장

기존 데이터 클래스에 `owasp_category` 필드를 추가한다:

```python
@dataclass
class LLMAnalysisResult:
    finding_id: str
    is_true_positive: bool
    confidence: float
    severity: str                    # Critical / High / Medium / Low / Informational
    reasoning: str
    owasp_category: str | None       # 신규 필드
    vulnerability_type: str | None   # 신규 필드 (LLM이 분류한 유형)
    patch_diff: str | None
    patch_description: str
    references: list[str] = field(default_factory=list)
```

1차 분석 프롬프트에서 `owasp_category`와 `vulnerability_type`을 함께 응답하도록 요청하며, LLM 응답 파싱 시 해당 필드를 추출한다.

---

## 변경 이력

| 날짜 | 변경 내용 | 이유 |
|------|-----------|------|
| 2026-02-25 | 초안 작성 | F-02 기능 상세 설계 |
