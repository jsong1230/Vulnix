# F-05 다국어 탐지 엔진 확장 — API 스펙 확정본

**버전**: v1.0
**작성일**: 2026-02-25
**상태**: 확정

---

## 개요

F-05는 기존 Python 전용 Semgrep 탐지 엔진을 JavaScript/TypeScript, Java, Go 언어로 확장한다.
API 엔드포인트의 변경은 없으며, 내부 서비스 레이어 및 룰 파일이 추가된다.

---

## 변경된 서비스 API (내부 함수)

### 1. `vulnerability_mapper.detect_language_from_rule_id()`

**모듈**: `src/services/vulnerability_mapper.py`

**시그니처**:
```python
def detect_language_from_rule_id(rule_id: str) -> str
```

**설명**: Semgrep rule_id의 두 번째 세그먼트에서 언어를 추출한다.

**입력/출력 예시**:

| 입력 `rule_id` | 반환값 |
|---------------|--------|
| `"vulnix.javascript.injection.sql_string_concat"` | `"javascript"` |
| `"vulnix.java.xss.servlet_print_unsanitized"` | `"java"` |
| `"vulnix.go.crypto.weak_hash_md5"` | `"go"` |
| `"vulnix.python.xss.flask_render_html"` | `"python"` |
| `"unknown.rule.xyz"` | `"unknown"` |
| `"p/default"` | `"unknown"` |
| `""` | `"unknown"` |
| `"vulnix.python"` (세그먼트 2개) | `"unknown"` |

**규칙**:
- 형식: `vulnix.{language}.{category}.{rule}`
- 최소 3개 세그먼트(`vulnix.{lang}.{rest}`)이고 첫 번째 세그먼트가 `vulnix`여야 한다
- 조건 미충족 시 `"unknown"` 반환

---

### 2. `vulnerability_mapper.map_finding_to_vulnerability()` (확장)

**모듈**: `src/services/vulnerability_mapper.py`

**시그니처** (기존 유지):
```python
def map_finding_to_vulnerability(rule_id: str, semgrep_severity: str) -> dict[str, str | None]
```

**F-05에서 추가된 rule_id 매핑**:

| rule_id | vulnerability_type | cwe_id | owasp_category |
|---------|--------------------|--------|----------------|
| `vulnix.javascript.injection.sql_string_concat` | `sql_injection` | `CWE-89` | `A03:2021 - Injection` |
| `vulnix.javascript.xss.innerhtml_assignment` | `xss` | `CWE-79` | `A03:2021 - Injection` |
| `vulnix.javascript.xss.document_write` | `xss` | `CWE-79` | `A03:2021 - Injection` |
| `vulnix.javascript.crypto.hardcoded_key` | `hardcoded_credentials` | `CWE-798` | `A02:2021 - Cryptographic Failures` |
| `vulnix.javascript.auth.jwt_no_verify` | `insecure_jwt` | `CWE-347` | `A07:2021 - Identification and Authentication Failures` |
| `vulnix.javascript.misconfig.cors_wildcard` | `security_misconfiguration` | `CWE-942` | `A05:2021 - Security Misconfiguration` |
| `vulnix.javascript.injection.command_exec` | `command_injection` | `CWE-78` | `A03:2021 - Injection` |
| `vulnix.java.injection.sql_string_concat` | `sql_injection` | `CWE-89` | `A03:2021 - Injection` |
| `vulnix.java.xss.servlet_print_unsanitized` | `xss` | `CWE-79` | `A03:2021 - Injection` |
| `vulnix.java.crypto.hardcoded_key` | `hardcoded_credentials` | `CWE-798` | `A02:2021 - Cryptographic Failures` |
| `vulnix.java.crypto.weak_hash` | `weak_crypto` | `CWE-328` | `A02:2021 - Cryptographic Failures` |
| `vulnix.java.crypto.insecure_random` | `insecure_random` | `CWE-330` | `A02:2021 - Cryptographic Failures` |
| `vulnix.go.injection.sql_string_format` | `sql_injection` | `CWE-89` | `A03:2021 - Injection` |
| `vulnix.go.injection.command_exec` | `command_injection` | `CWE-78` | `A03:2021 - Injection` |
| `vulnix.go.crypto.hardcoded_key` | `hardcoded_credentials` | `CWE-798` | `A02:2021 - Cryptographic Failures` |
| `vulnix.go.crypto.weak_hash_md5` | `weak_crypto` | `CWE-328` | `A02:2021 - Cryptographic Failures` |

---

### 3. `LLMAgent._detect_language_from_path()` (신규)

**모듈**: `src/services/llm_agent.py`

**시그니처**:
```python
def _detect_language_from_path(self, file_path: str) -> str
```

**설명**: 파일 확장자에서 언어 이름(한국어 프롬프트에 삽입할 표시명)을 반환한다.

**확장자 매핑**:

| 확장자 | 반환값 |
|--------|--------|
| `.py` | `"Python"` |
| `.js` | `"JavaScript"` |
| `.jsx` | `"JavaScript (React)"` |
| `.ts` | `"TypeScript"` |
| `.tsx` | `"TypeScript (React)"` |
| `.java` | `"Java"` |
| `.go` | `"Go"` |
| 미인식 / 확장자 없음 | `"소스"` |

---

### 4. `LLMAgent._build_analysis_prompt()` (수정)

**모듈**: `src/services/llm_agent.py`

**변경 내용**: 프롬프트 첫 줄에서 `"Python"` 하드코딩 제거 → `_detect_language_from_path(file_path)` 동적 주입.

**프롬프트 첫 줄 형식**:
```
다음 {language} 코드에서 정적 분석 도구가 탐지한 취약점 목록입니다.
```

**예시**:
- `.js` 파일: `"다음 JavaScript 코드에서 정적 분석 도구가 탐지한 취약점 목록입니다."`
- `.java` 파일: `"다음 Java 코드에서 정적 분석 도구가 탐지한 취약점 목록입니다."`
- `.go` 파일: `"다음 Go 코드에서 정적 분석 도구가 탐지한 취약점 목록입니다."`
- `.py` 파일: `"다음 Python 코드에서 정적 분석 도구가 탐지한 취약점 목록입니다."` (하위 호환)

---

## HTTP API 변경사항

**없음.** 기존 스캔 API(`POST /api/scans`)의 요청/응답 형식은 변경되지 않는다.
탐지 결과의 `vulnerability_type`, `cwe_id`, `owasp_category` 필드에 새로운 언어의 값이 추가로 반환된다.

---

## 변경 이력

| 날짜 | 변경 내용 |
|------|-----------|
| 2026-02-25 | F-05 구현 완료 — 다국어 룰 매핑, 헬퍼 함수 2개 신규 추가 |
