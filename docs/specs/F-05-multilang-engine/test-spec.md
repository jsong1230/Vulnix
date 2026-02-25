# F-05 다국어 탐지 엔진 확장 -- 테스트 명세

**버전**: v1.0
**작성일**: 2026-02-25
**상태**: 초안

---

## 참조

- 설계서: `docs/specs/F-05-multilang-engine/design.md`
- 인수조건: `docs/project/features.md` #F-05
- 기존 테스트: `backend/tests/services/test_semgrep_engine.py`, `backend/tests/services/test_llm_agent.py`

---

## 테스트 전략

### 테스트 범주

| 범주 | 대상 | 파일 |
|------|------|------|
| Semgrep 룰 단위 테스트 | 각 언어별 룰이 취약 코드를 올바르게 탐지하는지 검증 | `backend/tests/rules/` |
| VulnerabilityMapper 단위 테스트 | 신규 rule_id 매핑 및 헬퍼 함수 검증 | `backend/tests/services/test_vulnerability_mapper.py` |
| LLMAgent 단위 테스트 | 다국어 프롬프트 생성 및 언어 감지 검증 | `backend/tests/services/test_llm_agent_multilang.py` |
| 통합 테스트 | 다국어 코드베이스 전체 파이프라인 검증 | `backend/tests/integration/test_multilang_scan.py` |
| 회귀 테스트 | 기존 Python 스캔 기능이 그대로 동작하는지 검증 | 기존 테스트 파일 재실행 |

### 테스트용 fixture 파일 구조

```
backend/tests/fixtures/sample_vulnerable_code/
  python/          # 기존 유지
    vuln_sql.py
    vuln_xss.py
    vuln_creds.py
  javascript/      # 신규
    vuln_injection.js
    vuln_xss.js
    vuln_auth.js
    vuln_crypto.js
    vuln_misconfig.js
    vuln_injection.ts    # TypeScript 변형
  java/            # 신규
    VulnInjection.java
    VulnXss.java
    VulnAuth.java
    VulnCrypto.java
    VulnMisconfig.java
  go/              # 신규
    vuln_injection.go
    vuln_xss.go
    vuln_auth.go
    vuln_crypto.go
    vuln_misconfig.go
  python_extended/ # 신규 (OWASP 확장)
    vuln_command_injection.py
    vuln_auth.py
    vuln_crypto.py
    vuln_misconfig.py
```

---

## 단위 테스트

### 1. Semgrep 룰 테스트 (언어별)

각 룰이 의도한 취약 패턴을 탐지하고, 안전한 패턴에서는 탐지하지 않는 것을 검증한다.

#### 1-1. JavaScript/TypeScript 룰 테스트

파일: `backend/tests/rules/test_javascript_rules.py`

| 대상 룰 | 시나리오 | 입력 (fixture) | 예상 결과 |
|---------|----------|----------------|-----------|
| `vulnix.javascript.injection.sql_string_concat` | 문자열 연결 SQL 탐지 | `db.query("SELECT * FROM users WHERE id=" + userId)` | 탐지됨 (severity=ERROR, CWE-89) |
| `vulnix.javascript.injection.sql_string_concat` | 파라미터 바인딩 (안전) | `db.query("SELECT * FROM users WHERE id=$1", [userId])` | 탐지 안 됨 |
| `vulnix.javascript.injection.sql_sequelize_raw` | Sequelize 템플릿 리터럴 SQL | `` sequelize.query(`SELECT * FROM users WHERE id=${userId}`) `` | 탐지됨 (severity=ERROR) |
| `vulnix.javascript.injection.command_exec` | child_process.exec 직접 호출 | `` exec(`ls ${userInput}`) `` | 탐지됨 (CWE-78) |
| `vulnix.javascript.injection.nosql_mongo` | MongoDB 미검증 쿼리 | `collection.find({email: req.body.email})` | 탐지됨 (CWE-943) |
| `vulnix.javascript.xss.innerhtml_assignment` | innerHTML 직접 할당 | `el.innerHTML = userInput` | 탐지됨 (CWE-79) |
| `vulnix.javascript.xss.innerhtml_assignment` | textContent 사용 (안전) | `el.textContent = userInput` | 탐지 안 됨 |
| `vulnix.javascript.xss.react_dangerously_set` | dangerouslySetInnerHTML | `<div dangerouslySetInnerHTML={{__html: data}} />` | 탐지됨 |
| `vulnix.javascript.xss.express_send_unsanitized` | Express res.send 미이스케이프 | `res.send(req.query.name)` | 탐지됨 |
| `vulnix.javascript.auth.jwt_no_verify` | jwt.decode 서명 미검증 | `jwt.decode(token, {complete: true})` | 탐지됨 (CWE-347) |
| `vulnix.javascript.crypto.weak_hash` | MD5 사용 | `crypto.createHash("md5")` | 탐지됨 (CWE-328) |
| `vulnix.javascript.crypto.weak_hash` | SHA-256 사용 (안전) | `crypto.createHash("sha256")` | 탐지 안 됨 |
| `vulnix.javascript.crypto.hardcoded_secret` | 하드코딩 시크릿 | `const SECRET_KEY = "abc123"` | 탐지됨 (CWE-798) |
| `vulnix.javascript.crypto.hardcoded_secret` | 환경변수 사용 (안전) | `const SECRET_KEY = process.env.SECRET` | 탐지 안 됨 |
| `vulnix.javascript.crypto.insecure_random` | Math.random() 사용 | `const token = Math.random().toString(36)` | 탐지됨 (CWE-330) |
| `vulnix.javascript.misconfig.cors_wildcard` | CORS origin * | `cors({origin: "*"})` | 탐지됨 (CWE-942) |
| `vulnix.javascript.misconfig.sensitive_logging` | 패스워드 로깅 | `console.log("password:", password)` | 탐지됨 (CWE-532) |

#### 1-2. TypeScript 전용 테스트

| 대상 룰 | 시나리오 | 입력 | 예상 결과 |
|---------|----------|------|-----------|
| `vulnix.javascript.injection.sql_string_concat` | TS 파일에서 SQL Injection | `.ts` 파일 내 동일 패턴 | 탐지됨 (Semgrep languages: [javascript, typescript]) |
| `vulnix.javascript.xss.react_dangerously_set` | TSX 파일에서 XSS | `.tsx` 파일 내 dangerouslySetInnerHTML | 탐지됨 |

#### 1-3. Java 룰 테스트

파일: `backend/tests/rules/test_java_rules.py`

| 대상 룰 | 시나리오 | 입력 | 예상 결과 |
|---------|----------|------|-----------|
| `vulnix.java.injection.sql_string_concat` | JDBC 문자열 연결 SQL | `stmt.executeQuery("SELECT * FROM users WHERE id=" + userId)` | 탐지됨 (CWE-89) |
| `vulnix.java.injection.sql_string_concat` | PreparedStatement (안전) | `stmt.setString(1, userId)` | 탐지 안 됨 |
| `vulnix.java.injection.command_runtime_exec` | Runtime.exec 직접 호출 | `Runtime.getRuntime().exec("cmd " + userInput)` | 탐지됨 (CWE-78) |
| `vulnix.java.injection.ldap_search` | LDAP 필터 미검증 | `ctx.search(base, "(uid=" + username + ")", ...)` | 탐지됨 (CWE-90) |
| `vulnix.java.xss.servlet_print_unsanitized` | Servlet 미이스케이프 출력 | `response.getWriter().print(request.getParameter("name"))` | 탐지됨 (CWE-79) |
| `vulnix.java.auth.jwt_no_signature_verify` | JWT 서명 미검증 파싱 | `Jwts.parser().parseClaimsJwt(token)` | 탐지됨 (CWE-347) |
| `vulnix.java.crypto.weak_hash` | MD5 사용 | `MessageDigest.getInstance("MD5")` | 탐지됨 (CWE-328) |
| `vulnix.java.crypto.insecure_random` | java.util.Random | `new Random()` | 탐지됨 (CWE-330) |
| `vulnix.java.crypto.insecure_random` | SecureRandom (안전) | `new SecureRandom()` | 탐지 안 됨 |
| `vulnix.java.crypto.hardcoded_key` | 하드코딩 키 | `new SecretKeySpec("mysecret".getBytes(), "AES")` | 탐지됨 (CWE-798) |
| `vulnix.java.misconfig.cors_allow_all` | CORS 전체 허용 | `@CrossOrigin(origins = "*")` | 탐지됨 (CWE-942) |

#### 1-4. Go 룰 테스트

파일: `backend/tests/rules/test_go_rules.py`

| 대상 룰 | 시나리오 | 입력 | 예상 결과 |
|---------|----------|------|-----------|
| `vulnix.go.injection.sql_string_format` | fmt.Sprintf SQL | `db.Query(fmt.Sprintf("SELECT * FROM users WHERE id=%s", id))` | 탐지됨 (CWE-89) |
| `vulnix.go.injection.sql_string_format` | 파라미터 바인딩 (안전) | `db.Query("SELECT * FROM users WHERE id=$1", id)` | 탐지 안 됨 |
| `vulnix.go.injection.command_exec` | exec.Command 쉘 실행 | `exec.Command("bash", "-c", userInput)` | 탐지됨 (CWE-78) |
| `vulnix.go.xss.template_html_unescaped` | text/template 사용 | `import "text/template"` | 탐지됨 (CWE-79) |
| `vulnix.go.xss.template_html_unescaped` | html/template 사용 (안전) | `import "html/template"` | 탐지 안 됨 |
| `vulnix.go.auth.jwt_parse_unvalidated` | JWT 미검증 파싱 | `jwt.Parse(tokenString, ...)` | 탐지됨 (CWE-347) |
| `vulnix.go.crypto.weak_hash_md5` | MD5 사용 | `md5.New()` | 탐지됨 (CWE-328) |
| `vulnix.go.crypto.insecure_random` | math/rand 사용 | `import "math/rand"` | 탐지됨 (CWE-330) |
| `vulnix.go.crypto.insecure_random` | crypto/rand 사용 (안전) | `import "crypto/rand"` | 탐지 안 됨 |
| `vulnix.go.crypto.hardcoded_key` | 하드코딩 시크릿 | `secretKey := "mysupersecret"` | 탐지됨 (CWE-798) |
| `vulnix.go.misconfig.cors_allow_all` | CORS 전체 허용 | `AllowAllOrigins: true` | 탐지됨 (CWE-942) |

#### 1-5. Python 신규 룰 테스트 (OWASP 확장)

파일: `backend/tests/rules/test_python_extended_rules.py`

| 대상 룰 | 시나리오 | 입력 | 예상 결과 |
|---------|----------|------|-----------|
| `vulnix.python.injection.os_system` | os.system 직접 호출 | `os.system("rm " + user_input)` | 탐지됨 (CWE-78) |
| `vulnix.python.injection.subprocess_shell` | subprocess shell=True | `subprocess.run(cmd, shell=True)` | 탐지됨 (CWE-78) |
| `vulnix.python.injection.subprocess_shell` | subprocess shell=False (안전) | `subprocess.run(cmd_list, shell=False)` | 탐지 안 됨 |
| `vulnix.python.injection.ldap_search` | LDAP 필터 미검증 | `conn.search(base, f"(uid={username})")` | 탐지됨 (CWE-90) |
| `vulnix.python.auth.jwt_decode_no_verify` | JWT 서명 미검증 디코딩 | `jwt.decode(token, options={"verify_signature": False})` | 탐지됨 (CWE-347) |
| `vulnix.python.auth.flask_no_login_required` | admin 라우트에 인증 없음 | `@app.route("/admin/delete") def ...` | 탐지됨 (CWE-862) |
| `vulnix.python.crypto.weak_hash` | MD5 사용 | `hashlib.md5(data)` | 탐지됨 (CWE-328) |
| `vulnix.python.crypto.weak_hash` | SHA-256 사용 (안전) | `hashlib.sha256(data)` | 탐지 안 됨 |
| `vulnix.python.crypto.insecure_random` | random.random() | `token = random.random()` | 탐지됨 (CWE-330) |
| `vulnix.python.crypto.insecure_random` | secrets 사용 (안전) | `token = secrets.token_hex(32)` | 탐지 안 됨 |
| `vulnix.python.misconfig.django_debug_true` | Django DEBUG=True | `DEBUG = True` | 탐지됨 (CWE-489) |
| `vulnix.python.misconfig.flask_debug_true` | Flask debug=True | `app.run(debug=True)` | 탐지됨 (CWE-489) |
| `vulnix.python.misconfig.cors_allow_all` | CORS origin * | `CORS(app, origins="*")` | 탐지됨 (CWE-942) |
| `vulnix.python.misconfig.sensitive_logging` | 패스워드 로깅 | `logger.info(f"password: {password}")` | 탐지됨 (CWE-532) |

### 2. VulnerabilityMapper 단위 테스트

파일: `backend/tests/services/test_vulnerability_mapper.py`

| 대상 | 시나리오 | 입력 | 예상 결과 |
|------|----------|------|-----------|
| `map_finding_to_vulnerability()` | 기존 Python rule_id 매핑 | `("vulnix.python.sql_injection.string_format", "ERROR")` | `{"vulnerability_type": "sql_injection", "cwe_id": "CWE-89", "owasp_category": "A03:2021 - Injection", "severity": "high"}` |
| `map_finding_to_vulnerability()` | JavaScript rule_id 매핑 | `("vulnix.javascript.injection.sql_string_concat", "ERROR")` | `{"vulnerability_type": "sql_injection", "cwe_id": "CWE-89", ...}` |
| `map_finding_to_vulnerability()` | Java rule_id 매핑 | `("vulnix.java.crypto.weak_hash", "WARNING")` | `{"vulnerability_type": "weak_hash", "cwe_id": "CWE-328", "owasp_category": "A02:2021 - Cryptographic Failures", "severity": "medium"}` |
| `map_finding_to_vulnerability()` | Go rule_id 매핑 | `("vulnix.go.injection.command_exec", "ERROR")` | `{"vulnerability_type": "command_injection", "cwe_id": "CWE-78", ...}` |
| `map_finding_to_vulnerability()` | 미등록 rule_id fallback | `("unknown.rule.xyz", "WARNING")` | `{"vulnerability_type": "unknown", "cwe_id": None, "owasp_category": None, "severity": "medium"}` |
| `detect_language_from_rule_id()` | Python rule_id | `"vulnix.python.xss.flask_render_html"` | `"python"` |
| `detect_language_from_rule_id()` | JavaScript rule_id | `"vulnix.javascript.xss.innerhtml_assignment"` | `"javascript"` |
| `detect_language_from_rule_id()` | Java rule_id | `"vulnix.java.injection.sql_string_concat"` | `"java"` |
| `detect_language_from_rule_id()` | Go rule_id | `"vulnix.go.crypto.weak_hash_md5"` | `"go"` |
| `detect_language_from_rule_id()` | 미인식 rule_id | `"unknown.rule.xyz"` | `"unknown"` |
| `detect_language_from_rule_id()` | vulnix 접두사 없음 | `"p/default"` | `"unknown"` |

### 3. LLMAgent 다국어 프롬프트 테스트

파일: `backend/tests/services/test_llm_agent_multilang.py`

| 대상 | 시나리오 | 입력 | 예상 결과 |
|------|----------|------|-----------|
| `_detect_language_from_path()` | Python 파일 | `"app/main.py"` | `"Python"` |
| `_detect_language_from_path()` | JavaScript 파일 | `"src/index.js"` | `"JavaScript"` |
| `_detect_language_from_path()` | TypeScript 파일 | `"src/app.ts"` | `"TypeScript"` |
| `_detect_language_from_path()` | TSX React 파일 | `"src/Component.tsx"` | `"TypeScript (React)"` |
| `_detect_language_from_path()` | Java 파일 | `"src/Main.java"` | `"Java"` |
| `_detect_language_from_path()` | Go 파일 | `"main.go"` | `"Go"` |
| `_detect_language_from_path()` | 미인식 확장자 | `"config.toml"` | `"소스"` |
| `_build_analysis_prompt()` | JS 파일 프롬프트 생성 | file_path=`"app.js"`, findings 포함 | 프롬프트에 "다음 JavaScript 코드에서" 포함 |
| `_build_analysis_prompt()` | Java 파일 프롬프트 생성 | file_path=`"Main.java"`, findings 포함 | 프롬프트에 "다음 Java 코드에서" 포함 |
| `_build_analysis_prompt()` | Go 파일 프롬프트 생성 | file_path=`"main.go"`, findings 포함 | 프롬프트에 "다음 Go 코드에서" 포함 |
| `_build_analysis_prompt()` | Python 파일 (하위호환) | file_path=`"app.py"`, findings 포함 | 프롬프트에 "다음 Python 코드에서" 포함 |
| `analyze_findings()` | JS 코드 LLM 분석 (Mock) | JS 파일 + JS findings | LLMAnalysisResult 반환, is_true_positive 필드 존재 |
| `analyze_findings()` | Java 코드 LLM 분석 (Mock) | Java 파일 + Java findings | LLMAnalysisResult 반환 |
| `analyze_findings()` | Go 코드 LLM 분석 (Mock) | Go 파일 + Go findings | LLMAnalysisResult 반환 |

---

## 통합 테스트

파일: `backend/tests/integration/test_multilang_scan.py`

### 전체 파이프라인 테스트 (Semgrep 실제 실행)

이 테스트는 Semgrep CLI가 설치된 환경에서만 실행된다. pytest marker `@pytest.mark.semgrep`으로 분리.

| API/서비스 | 시나리오 | 입력 | 예상 결과 |
|------------|----------|------|-----------|
| `SemgrepEngine.scan()` | 혼합 언어 코드베이스 스캔 | Python + JS + Java + Go 취약 코드 포함 디렉토리 | 4개 언어 모두에서 findings 탐지 |
| `SemgrepEngine.scan()` | Python 전용 코드베이스 | Python 파일만 포함 | Python 룰만 매칭, 기존 동작 동일 |
| `SemgrepEngine.scan()` | JavaScript 전용 코드베이스 | JS/TS 파일만 포함 | JavaScript 룰만 매칭 |
| `SemgrepEngine.scan()` | 취약점 없는 코드베이스 | 안전한 코드만 포함 | 빈 findings 목록 반환 |
| `SemgrepEngine.scan()` + `vulnerability_mapper` | 탐지 결과 매핑 | 혼합 언어 findings | 모든 finding에 올바른 CWE/OWASP 매핑 |

### OWASP Top 10 전체 카테고리 커버리지 테스트

| 시나리오 | 입력 | 예상 결과 |
|----------|------|-----------|
| A01 Broken Access Control 탐지 | Python auth fixture + Java auth fixture | owasp_category에 "A01:2021" 포함된 finding 존재 |
| A02 Cryptographic Failures 탐지 | 전 언어 crypto fixture | owasp_category에 "A02:2021" 포함 |
| A03 Injection 탐지 | 전 언어 injection + xss fixture | owasp_category에 "A03:2021" 포함 |
| A05 Security Misconfiguration 탐지 | 전 언어 misconfig fixture | owasp_category에 "A05:2021" 포함 |
| A07 Auth Failures 탐지 | 전 언어 auth fixture | owasp_category에 "A07:2021" 포함 |
| A09 Logging Failures 탐지 | 전 언어 misconfig fixture (sensitive logging) | owasp_category에 "A09:2021" 포함 |

---

## 경계 조건 / 에러 케이스

### Semgrep 룰 관련

| 경계 조건 | 예상 동작 |
|-----------|-----------|
| 빈 룰 디렉토리 (rules/에 yml 파일 없음) | Semgrep이 에러 없이 빈 결과 반환 |
| 문법 오류가 있는 yml 파일 | Semgrep이 해당 룰 스킵, errors 배열에 경고 포함, 나머지 룰로 정상 스캔 |
| 동일 패턴이 여러 언어에서 탐지 (예: 하드코딩 regex) | 각 언어별 별도 finding으로 반환 |
| 극대 파일 (1MB 초과) | `--max-target-bytes 1000000`에 의해 스킵, 경고 로그 |
| 바이너리 파일 포함 디렉토리 | Semgrep이 자동 스킵 |

### VulnerabilityMapper 관련

| 경계 조건 | 예상 동작 |
|-----------|-----------|
| RULE_MAPPING에 없는 rule_id | `vulnerability_type: "unknown"`, `cwe_id: None`, `owasp_category: None` |
| rule_id가 빈 문자열 | 동일하게 "unknown" 반환 |
| rule_id에 점(.)이 2개 미만 | `detect_language_from_rule_id()` -> "unknown" |

### LLMAgent 관련

| 경계 조건 | 예상 동작 |
|-----------|-----------|
| 미인식 파일 확장자 (.rb, .php 등) | `_detect_language_from_path()` -> "소스", 프롬프트에 "다음 소스 코드에서" |
| 확장자 없는 파일 (Makefile 등) | 동일하게 "소스" 반환 |
| 매우 큰 파일 (1000줄 초과) + 여러 언어 findings | `_prepare_file_content()` 기존 로직 그대로 동작 (취약점 주변 +/-50줄 추출) |
| LLM이 지원하지 않는 언어의 코드 | LLM은 최선의 분석 결과를 반환, is_true_positive 판단은 confidence 기반 |

---

## 회귀 테스트

기존 F-02 기능이 F-05 변경에 의해 영향받지 않는지 검증한다.

| 기존 기능 | 영향 여부 | 검증 방법 |
|-----------|-----------|-----------|
| Python SQL Injection 탐지 | 영향 없음 (기존 yml 파일 미수정) | `backend/tests/services/test_semgrep_engine.py` 전체 통과 확인 |
| Python XSS 탐지 | 영향 없음 | 기존 테스트 통과 확인 |
| Python Hardcoded Credentials 탐지 | 영향 없음 | 기존 테스트 통과 확인 |
| LLM 분석 (Python 코드) | 영향 최소 (프롬프트 언어명만 변경) | `backend/tests/services/test_llm_agent.py` 전체 통과 확인 |
| ScanWorker 파이프라인 | 영향 없음 (코드 변경 없음) | `backend/tests/workers/test_scan_worker.py` 전체 통과 확인 |
| VulnerabilityMapper (기존 rule_id) | 영향 없음 (기존 매핑 유지, 추가만) | 기존 rule_id 매핑 테스트 통과 확인 |
| Patch Generator | 영향 없음 (코드 변경 없음) | `backend/tests/services/test_patch_generator.py` 전체 통과 확인 |
| Dashboard API | 영향 없음 | `backend/tests/api/test_dashboard_api.py` 전체 통과 확인 |
| Vulnerability API | 영향 없음 | `backend/tests/api/test_vulns_api.py` 전체 통과 확인 |

---

## 테스트 실행 명령

```bash
# 전체 테스트 실행 (기존 + 신규)
cd backend && pytest

# F-05 신규 테스트만 실행
cd backend && pytest tests/rules/ tests/services/test_vulnerability_mapper.py tests/services/test_llm_agent_multilang.py

# Semgrep 실제 실행 통합 테스트 (CI 환경)
cd backend && pytest -m semgrep tests/integration/test_multilang_scan.py

# 회귀 테스트 (기존 테스트 전체)
cd backend && pytest tests/services/test_semgrep_engine.py tests/services/test_llm_agent.py tests/workers/test_scan_worker.py tests/services/test_patch_generator.py tests/api/
```

---

## 인수조건 매핑

각 인수조건이 어떤 테스트로 검증되는지 추적한다.

| 인수조건 | 검증 테스트 |
|----------|-------------|
| JavaScript/TypeScript 코드 대상 취약점 탐지 가능 | `test_javascript_rules.py` 전체 + `test_multilang_scan.py` JS 시나리오 |
| Java 코드 대상 취약점 탐지 가능 | `test_java_rules.py` 전체 + `test_multilang_scan.py` Java 시나리오 |
| Go 코드 대상 취약점 탐지 가능 | `test_go_rules.py` 전체 + `test_multilang_scan.py` Go 시나리오 |
| OWASP Top 10 전체 카테고리 탐지 지원 | `test_multilang_scan.py` OWASP 커버리지 테스트 |
| Injection (SQL, Command, LDAP) 전체 유형 탐지 | 각 언어별 injection 룰 테스트 |
| XSS (Reflected, Stored, DOM-based) 전체 유형 탐지 | 각 언어별 xss 룰 테스트 |
| 인증/인가 취약점 (Insecure JWT, Broken Access Control) 탐지 | 각 언어별 auth 룰 테스트 |
| 암호화 취약점 (약한 해시, 하드코딩 키, 안전하지 않은 랜덤) 탐지 | 각 언어별 crypto 룰 테스트 |
| 설정 오류 (Debug mode, CORS 과도 허용, 민감 정보 로깅) 탐지 | 각 언어별 misconfig 룰 테스트 |
| 언어별 Semgrep 룰셋 커스터마이징 완료 | 전체 룰 테스트 통과 + 디렉토리 구조 검증 |

---

## 변경 이력

| 날짜 | 변경 내용 | 이유 |
|------|-----------|------|
| 2026-02-25 | 초안 작성 | F-05 다국어 탐지 엔진 확장 테스트 명세 |
