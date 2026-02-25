# F-05 다국어 탐지 엔진 확장 -- 기술 설계서

**버전**: v1.0
**작성일**: 2026-02-25
**상태**: 초안

---

## 1. 참조

- 인수조건: `docs/project/features.md` #F-05
- 시스템 설계: `docs/system/system-design.md` 3-3절 (Semgrep), 3-4절 (LLM Agent)
- 선행 설계: `docs/specs/F-02-detection-engine/design.md`
- 아키텍처 결정: `docs/system/system-design.md` ADR-001 (하이브리드 탐지), ADR-003 (코드 보안)

---

## 2. 아키텍처 결정

### 결정 1: 언어별 룰 디렉토리 분리 방식

- **선택지**: A) 단일 디렉토리에 모든 언어 룰 혼합 / B) `rules/{language}/` 디렉토리로 분리
- **결정**: B) `rules/{language}/` 디렉토리로 분리
- **근거**: Semgrep은 `--config` 경로 내 모든 YAML 파일을 자동으로 로드한다. 언어별 디렉토리 분리 시 (1) 특정 언어만 선택적 스캔이 가능해지고 (2) 룰 관리/테스트가 독립적이며 (3) 기존 `rules/python/` 구조와 일관성을 유지한다. Semgrep의 `languages` 필드가 실행 시 자동 필터링하므로 전체 `rules/` 디렉토리를 config로 전달해도 성능 문제 없다.

### 결정 2: Semgrep 스캔 시 언어 자동 감지 vs 명시적 지정

- **선택지**: A) 파일 확장자로 언어 감지 후 해당 언어 룰만 실행 / B) 전체 룰 디렉토리 전달 (Semgrep이 자체 감지)
- **결정**: B) 전체 룰 디렉토리 전달 (Semgrep 자체 감지)
- **근거**: Semgrep은 각 룰의 `languages` 필드를 참조하여 대상 파일을 자동 필터링한다. 즉 `python` 룰은 `.py` 파일에만, `javascript` 룰은 `.js/.jsx/.ts/.tsx` 파일에만 적용된다. 추가적인 언어 감지 로직을 구현할 필요가 없으며, 기존 `SemgrepEngine.scan()`의 `--config self._rules_dir` 방식을 그대로 유지할 수 있다. `scan()` 시그니처와 동작은 변경 없다.

### 결정 3: OWASP Top 10 확장 범위

- **선택지**: A) 기존 3개 카테고리만 유지 / B) OWASP Top 10 전체(10개 카테고리) 지원
- **결정**: B) OWASP Top 10 전체 지원
- **근거**: 인수조건에 "OWASP Top 10 전체 카테고리 탐지 지원"이 명시되어 있다. 기존 Python 룰에서 지원하던 A03(Injection), A07(Authentication Failures) 외에 A01(Broken Access Control), A02(Cryptographic Failures), A04(Insecure Design), A05(Security Misconfiguration), A06(Vulnerable Components), A08(Software Integrity Failures), A09(Logging Failures), A10(SSRF)을 추가한다.

### 결정 4: LLM 분석 프롬프트의 다국어 대응

- **선택지**: A) 언어별 전용 프롬프트 / B) 범용 프롬프트 (언어명을 변수로 주입)
- **결정**: B) 범용 프롬프트 (언어명을 변수로 주입)
- **근거**: LLM(Claude)은 Python/JavaScript/Java/Go 모두에 대해 높은 코드 이해력을 보유한다. 프롬프트에 `다음 {language} 코드에서` 형태로 언어명만 주입하면 충분하다. 언어별 전용 프롬프트는 유지보수 비용이 높고 실질적 정확도 향상이 미미하다.

### 결정 5: rule_id 네이밍 컨벤션

- **선택지**: A) 기존 방식 유지 (`vulnix.python.{category}.{rule}`) / B) 언어 접두사 통일 (`vulnix.{language}.{category}.{rule}`)
- **결정**: B) 언어 접두사 통일
- **근거**: 기존 Python 룰이 이미 `vulnix.python.*` 패턴을 사용하고 있다. JavaScript는 `vulnix.javascript.*`, Java는 `vulnix.java.*`, Go는 `vulnix.go.*`로 확장하면 `vulnerability_mapper.py`에서 rule_id 파싱 시 언어를 추출할 수 있다.

---

## 3. 구현 범위

### 3-1. 수정 대상 파일

| 파일 경로 | 변경 유형 | 설명 |
|-----------|-----------|------|
| `backend/src/services/vulnerability_mapper.py` | 수정 | 새 언어/취약점 유형 rule_id 매핑 추가, 헬퍼 함수 `detect_language_from_rule_id()` 추가 |
| `backend/src/services/llm_agent.py` | 수정 | `_build_analysis_prompt()` 내 "Python" 하드코딩을 언어 변수로 교체 |
| `backend/src/rules/README.md` | 수정 | 새 룰 디렉토리 및 취약점 유형 문서화 |

### 3-2. 신규 생성 파일

| 파일 경로 | 설명 |
|-----------|------|
| `backend/src/rules/javascript/injection.yml` | JS/TS SQL Injection, Command Injection, NoSQL Injection |
| `backend/src/rules/javascript/xss.yml` | JS/TS XSS (Reflected, Stored, DOM-based) |
| `backend/src/rules/javascript/auth.yml` | JS/TS 인증/인가 취약점 (JWT, Access Control) |
| `backend/src/rules/javascript/crypto.yml` | JS/TS 암호화 취약점 (약한 해시, 하드코딩 키, 안전하지 않은 랜덤) |
| `backend/src/rules/javascript/misconfig.yml` | JS/TS 설정 오류 (Debug mode, CORS, 민감 정보 로깅) |
| `backend/src/rules/java/injection.yml` | Java SQL Injection, Command Injection, LDAP Injection |
| `backend/src/rules/java/xss.yml` | Java XSS (Reflected, Stored) |
| `backend/src/rules/java/auth.yml` | Java 인증/인가 취약점 |
| `backend/src/rules/java/crypto.yml` | Java 암호화 취약점 |
| `backend/src/rules/java/misconfig.yml` | Java 설정 오류 |
| `backend/src/rules/go/injection.yml` | Go SQL Injection, Command Injection |
| `backend/src/rules/go/xss.yml` | Go XSS (template 미이스케이프) |
| `backend/src/rules/go/auth.yml` | Go 인증/인가 취약점 |
| `backend/src/rules/go/crypto.yml` | Go 암호화 취약점 |
| `backend/src/rules/go/misconfig.yml` | Go 설정 오류 |
| `backend/src/rules/python/injection.yml` | Python Command Injection, LDAP Injection (기존 sql_injection.yml에서 분리 불필요, 추가 룰 파일) |
| `backend/src/rules/python/auth.yml` | Python 인증/인가 취약점 (JWT 검증 미흡, Broken Access Control) |
| `backend/src/rules/python/crypto.yml` | Python 암호화 취약점 (약한 해시, 안전하지 않은 랜덤) |
| `backend/src/rules/python/misconfig.yml` | Python 설정 오류 (Debug mode, CORS, 민감 정보 로깅) |

### 3-3. 변경 없는 파일 (하위호환 유지)

| 파일 경로 | 이유 |
|-----------|------|
| `backend/src/services/semgrep_engine.py` | `--config self._rules_dir`이 전체 `rules/` 하위를 재귀 탐색하므로 코드 변경 불필요 |
| `backend/src/services/scan_orchestrator.py` | 언어 무관 워크플로우 |
| `backend/src/services/patch_generator.py` | 언어 무관 diff 적용 |
| `backend/src/workers/scan_worker.py` | 파이프라인 변경 없음 |
| `backend/src/rules/python/sql_injection.yml` | 기존 룰 유지 |
| `backend/src/rules/python/xss.yml` | 기존 룰 유지 |
| `backend/src/rules/python/hardcoded_creds.yml` | 기존 룰 유지 |

---

## 4. Semgrep 룰 상세 설계

### 4-1. OWASP Top 10 전체 매핑 계획

| OWASP 카테고리 | 취약점 유형 | CWE | Python | JS/TS | Java | Go |
|----------------|-------------|-----|--------|-------|------|-----|
| A01:2021 - Broken Access Control | Broken Access Control | CWE-284, CWE-862 | auth.yml | auth.yml | auth.yml | auth.yml |
| A02:2021 - Cryptographic Failures | 약한 해시 | CWE-328 | crypto.yml | crypto.yml | crypto.yml | crypto.yml |
| A02:2021 - Cryptographic Failures | 하드코딩 키 | CWE-798 | hardcoded_creds.yml | crypto.yml | crypto.yml | crypto.yml |
| A02:2021 - Cryptographic Failures | 안전하지 않은 랜덤 | CWE-330 | crypto.yml | crypto.yml | crypto.yml | crypto.yml |
| A03:2021 - Injection | SQL Injection | CWE-89 | sql_injection.yml | injection.yml | injection.yml | injection.yml |
| A03:2021 - Injection | Command Injection | CWE-78 | injection.yml | injection.yml | injection.yml | injection.yml |
| A03:2021 - Injection | LDAP Injection | CWE-90 | injection.yml | injection.yml | injection.yml | - |
| A03:2021 - Injection | XSS (Reflected) | CWE-79 | xss.yml | xss.yml | xss.yml | xss.yml |
| A03:2021 - Injection | XSS (Stored) | CWE-79 | xss.yml | xss.yml | xss.yml | xss.yml |
| A03:2021 - Injection | XSS (DOM-based) | CWE-79 | - | xss.yml | - | - |
| A03:2021 - Injection | NoSQL Injection | CWE-943 | - | injection.yml | - | - |
| A05:2021 - Security Misconfiguration | Debug mode | CWE-489 | misconfig.yml | misconfig.yml | misconfig.yml | misconfig.yml |
| A05:2021 - Security Misconfiguration | CORS 과도 허용 | CWE-942 | misconfig.yml | misconfig.yml | misconfig.yml | misconfig.yml |
| A05:2021 - Security Misconfiguration | 민감 정보 로깅 | CWE-532 | misconfig.yml | misconfig.yml | misconfig.yml | misconfig.yml |
| A07:2021 - Auth Failures | Insecure JWT | CWE-347 | auth.yml | auth.yml | auth.yml | auth.yml |
| A07:2021 - Auth Failures | 하드코딩 Credentials | CWE-798 | hardcoded_creds.yml | crypto.yml | crypto.yml | crypto.yml |

### 4-2. JavaScript/TypeScript 룰 상세

#### 4-2-1. `rules/javascript/injection.yml`

```yaml
rules:
  # SQL Injection (Node.js)
  - id: vulnix.javascript.injection.sql_string_concat
    languages: [javascript, typescript]
    severity: ERROR
    message: |
      SQL Injection: 사용자 입력을 문자열 연결로 SQL 쿼리에 삽입하고 있습니다.
      파라미터화된 쿼리 또는 ORM을 사용하세요.
    metadata:
      cwe: ["CWE-89"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: $DB.query("..." + $INPUT + "...")
      - pattern: $DB.query(`...${$INPUT}...`)

  - id: vulnix.javascript.injection.sql_sequelize_raw
    languages: [javascript, typescript]
    severity: ERROR
    message: |
      SQL Injection: Sequelize raw query에 사용자 입력을 직접 삽입하고 있습니다.
      bind 파라미터를 사용하세요.
    metadata:
      cwe: ["CWE-89"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: $DB.query(`...${$INPUT}...`)
      - pattern: sequelize.query("..." + $INPUT)

  # Command Injection
  - id: vulnix.javascript.injection.command_exec
    languages: [javascript, typescript]
    severity: ERROR
    message: |
      Command Injection: child_process.exec()에 사용자 입력을 직접 전달하고 있습니다.
      execFile() 또는 입력 검증을 사용하세요.
    metadata:
      cwe: ["CWE-78"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: exec($CMD + $INPUT)
      - pattern: exec(`...${$INPUT}...`)
      - pattern: child_process.exec($CMD + $INPUT)

  # NoSQL Injection
  - id: vulnix.javascript.injection.nosql_mongo
    languages: [javascript, typescript]
    severity: ERROR
    message: |
      NoSQL Injection: MongoDB 쿼리에 사용자 입력을 직접 전달하고 있습니다.
      입력값 타입 검증 및 sanitize를 수행하세요.
    metadata:
      cwe: ["CWE-943"]
      owasp: ["A03:2021 - Injection"]
      confidence: MEDIUM
      category: security
    patterns:
      - pattern: $COLLECTION.find({$FIELD: $REQ.$PARAM})
      - pattern: $COLLECTION.findOne({$FIELD: req.body.$PARAM})
```

#### 4-2-2. `rules/javascript/xss.yml`

```yaml
rules:
  # DOM-based XSS
  - id: vulnix.javascript.xss.innerhtml_assignment
    languages: [javascript, typescript]
    severity: ERROR
    message: |
      DOM-based XSS: innerHTML에 사용자 입력을 직접 할당하고 있습니다.
      textContent를 사용하거나 DOMPurify로 sanitize하세요.
    metadata:
      cwe: ["CWE-79"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: $EL.innerHTML = $INPUT
      - pattern: document.write($INPUT)

  # React dangerouslySetInnerHTML
  - id: vulnix.javascript.xss.react_dangerously_set
    languages: [javascript, typescript]
    severity: ERROR
    message: |
      XSS 위험: dangerouslySetInnerHTML에 사용자 입력을 전달하고 있습니다.
      DOMPurify.sanitize()로 처리하세요.
    metadata:
      cwe: ["CWE-79"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
    pattern: |
      <$TAG dangerouslySetInnerHTML={{__html: $INPUT}} />

  # Express response XSS
  - id: vulnix.javascript.xss.express_send_unsanitized
    languages: [javascript, typescript]
    severity: ERROR
    message: |
      Reflected XSS: Express 응답에 사용자 입력을 이스케이프 없이 포함하고 있습니다.
    metadata:
      cwe: ["CWE-79"]
      owasp: ["A03:2021 - Injection"]
      confidence: MEDIUM
      category: security
    patterns:
      - pattern: res.send($REQ.$PARAM)
      - pattern: res.send(`...${req.$PARAM}...`)
```

#### 4-2-3. `rules/javascript/auth.yml`

```yaml
rules:
  # JWT 검증 미흡
  - id: vulnix.javascript.auth.jwt_no_verify
    languages: [javascript, typescript]
    severity: ERROR
    message: |
      인증 취약점: JWT를 검증 없이 디코딩하고 있습니다.
      jwt.verify()를 사용하세요.
    metadata:
      cwe: ["CWE-347"]
      owasp: ["A07:2021 - Identification and Authentication Failures"]
      confidence: HIGH
      category: security
    pattern: jwt.decode($TOKEN, ...)

  # JWT 알고리즘 none 허용
  - id: vulnix.javascript.auth.jwt_algorithm_none
    languages: [javascript, typescript]
    severity: ERROR
    message: |
      인증 취약점: JWT 알고리즘으로 'none'을 허용하고 있습니다.
      algorithms 옵션으로 허용 알고리즘을 명시하세요.
    metadata:
      cwe: ["CWE-347"]
      owasp: ["A07:2021 - Identification and Authentication Failures"]
      confidence: HIGH
      category: security
    pattern: jwt.verify($TOKEN, $SECRET, {algorithms: ["none", ...]})
```

#### 4-2-4. `rules/javascript/crypto.yml`

```yaml
rules:
  # 약한 해시 알고리즘
  - id: vulnix.javascript.crypto.weak_hash
    languages: [javascript, typescript]
    severity: WARNING
    message: |
      암호화 취약점: MD5/SHA1은 보안용으로 안전하지 않습니다.
      SHA-256 이상을 사용하세요.
    metadata:
      cwe: ["CWE-328"]
      owasp: ["A02:2021 - Cryptographic Failures"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: crypto.createHash("md5")
      - pattern: crypto.createHash("sha1")

  # 하드코딩 시크릿
  - id: vulnix.javascript.crypto.hardcoded_secret
    languages: [javascript, typescript]
    severity: ERROR
    message: |
      하드코딩 시크릿: 시크릿 키가 소스 코드에 하드코딩되어 있습니다.
      환경변수(process.env)를 사용하세요.
    metadata:
      cwe: ["CWE-798"]
      owasp: ["A02:2021 - Cryptographic Failures"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: |
          const $SECRET = "..."
      - pattern: |
          let $SECRET = "..."
    metavariable-regex:
      metavariable: $SECRET
      regex: '(?i)(secret|password|api_key|apikey|token|private_key)'

  # 안전하지 않은 랜덤
  - id: vulnix.javascript.crypto.insecure_random
    languages: [javascript, typescript]
    severity: WARNING
    message: |
      암호화 취약점: Math.random()은 암호학적으로 안전하지 않습니다.
      crypto.randomBytes() 또는 crypto.randomUUID()를 사용하세요.
    metadata:
      cwe: ["CWE-330"]
      owasp: ["A02:2021 - Cryptographic Failures"]
      confidence: MEDIUM
      category: security
    pattern: Math.random()
```

#### 4-2-5. `rules/javascript/misconfig.yml`

```yaml
rules:
  # CORS 과도 허용
  - id: vulnix.javascript.misconfig.cors_wildcard
    languages: [javascript, typescript]
    severity: WARNING
    message: |
      설정 오류: CORS origin이 '*'로 설정되어 모든 도메인에서 접근 가능합니다.
      허용 도메인을 명시적으로 지정하세요.
    metadata:
      cwe: ["CWE-942"]
      owasp: ["A05:2021 - Security Misconfiguration"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: cors({origin: "*"})
      - pattern: "Access-Control-Allow-Origin", "*"

  # 민감 정보 로깅
  - id: vulnix.javascript.misconfig.sensitive_logging
    languages: [javascript, typescript]
    severity: WARNING
    message: |
      민감 정보 로깅: password, token, secret 등의 민감 정보를 로그에 출력하고 있습니다.
    metadata:
      cwe: ["CWE-532"]
      owasp: ["A09:2021 - Security Logging and Monitoring Failures"]
      confidence: MEDIUM
      category: security
    patterns:
      - pattern: console.log(..., $PASSWORD, ...)
      - pattern: console.log(`...${$PASSWORD}...`)
    metavariable-regex:
      metavariable: $PASSWORD
      regex: '(?i)(password|secret|token|api_key|apikey|credential)'
```

### 4-3. Java 룰 상세

#### 4-3-1. `rules/java/injection.yml`

```yaml
rules:
  # SQL Injection (JDBC)
  - id: vulnix.java.injection.sql_string_concat
    languages: [java]
    severity: ERROR
    message: |
      SQL Injection: 문자열 연결로 SQL 쿼리를 동적 생성하고 있습니다.
      PreparedStatement를 사용하세요.
    metadata:
      cwe: ["CWE-89"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: |
          $STMT.executeQuery("..." + $INPUT + "...")
      - pattern: |
          $STMT.execute("..." + $INPUT + "...")
      - pattern: |
          $CONN.createStatement().executeQuery("..." + $INPUT + "...")

  # SQL Injection (Spring JPA)
  - id: vulnix.java.injection.sql_spring_query
    languages: [java]
    severity: ERROR
    message: |
      SQL Injection: Spring @Query에 문자열 연결을 사용하고 있습니다.
      :param 바인딩 또는 SpEL을 사용하세요.
    metadata:
      cwe: ["CWE-89"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
    pattern: |
      @Query("..." + $INPUT + "...")

  # Command Injection
  - id: vulnix.java.injection.command_runtime_exec
    languages: [java]
    severity: ERROR
    message: |
      Command Injection: Runtime.exec()에 사용자 입력을 전달하고 있습니다.
      ProcessBuilder를 사용하고 입력을 검증하세요.
    metadata:
      cwe: ["CWE-78"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: Runtime.getRuntime().exec($CMD + $INPUT)
      - pattern: Runtime.getRuntime().exec("..." + $INPUT + "...")

  # LDAP Injection
  - id: vulnix.java.injection.ldap_search
    languages: [java]
    severity: ERROR
    message: |
      LDAP Injection: LDAP 검색 필터에 사용자 입력을 직접 삽입하고 있습니다.
      LDAP 인코딩을 수행하세요.
    metadata:
      cwe: ["CWE-90"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: |
          $CTX.search($BASE, "..." + $INPUT + "...", ...)
      - pattern: |
          new SearchControls(..., "(..." + $INPUT + "...)", ...)
```

#### 4-3-2. `rules/java/xss.yml`

```yaml
rules:
  # Servlet XSS
  - id: vulnix.java.xss.servlet_print_unsanitized
    languages: [java]
    severity: ERROR
    message: |
      XSS: HttpServletResponse에 사용자 입력을 이스케이프 없이 출력하고 있습니다.
      OWASP Encoder 또는 StringEscapeUtils를 사용하세요.
    metadata:
      cwe: ["CWE-79"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: |
          $RESPONSE.getWriter().print($REQ.getParameter(...))
      - pattern: |
          $RESPONSE.getWriter().println($REQ.getParameter(...))

  # Spring MVC XSS
  - id: vulnix.java.xss.spring_model_unsanitized
    languages: [java]
    severity: WARNING
    message: |
      XSS 위험: Spring MVC 모델에 사용자 입력을 이스케이프 없이 전달하고 있습니다.
      뷰에서 자동 이스케이프가 활성화되어 있는지 확인하세요.
    metadata:
      cwe: ["CWE-79"]
      owasp: ["A03:2021 - Injection"]
      confidence: MEDIUM
      category: security
    pattern: |
      $MODEL.addAttribute($KEY, $REQ.getParameter(...))
```

#### 4-3-3. `rules/java/auth.yml`

```yaml
rules:
  # JWT 검증 미흡
  - id: vulnix.java.auth.jwt_no_signature_verify
    languages: [java]
    severity: ERROR
    message: |
      인증 취약점: JWT 서명을 검증하지 않고 파싱하고 있습니다.
      parseClaimsJws()를 사용하세요.
    metadata:
      cwe: ["CWE-347"]
      owasp: ["A07:2021 - Identification and Authentication Failures"]
      confidence: HIGH
      category: security
    pattern: Jwts.parser().parseClaimsJwt($TOKEN)

  # Broken Access Control (Spring)
  - id: vulnix.java.auth.spring_permit_all_sensitive
    languages: [java]
    severity: WARNING
    message: |
      접근 제어 취약점: 민감한 엔드포인트에 permitAll()이 설정되어 있습니다.
    metadata:
      cwe: ["CWE-862"]
      owasp: ["A01:2021 - Broken Access Control"]
      confidence: MEDIUM
      category: security
    patterns:
      - pattern: |
          .antMatchers("/api/admin/**").permitAll()
      - pattern: |
          .requestMatchers("/api/admin/**").permitAll()
```

#### 4-3-4. `rules/java/crypto.yml`

```yaml
rules:
  # 약한 해시
  - id: vulnix.java.crypto.weak_hash
    languages: [java]
    severity: WARNING
    message: |
      암호화 취약점: MD5/SHA-1은 보안용으로 안전하지 않습니다.
      SHA-256 이상을 사용하세요.
    metadata:
      cwe: ["CWE-328"]
      owasp: ["A02:2021 - Cryptographic Failures"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: MessageDigest.getInstance("MD5")
      - pattern: MessageDigest.getInstance("SHA-1")
      - pattern: MessageDigest.getInstance("SHA1")

  # 안전하지 않은 랜덤
  - id: vulnix.java.crypto.insecure_random
    languages: [java]
    severity: WARNING
    message: |
      암호화 취약점: java.util.Random은 암호학적으로 안전하지 않습니다.
      java.security.SecureRandom을 사용하세요.
    metadata:
      cwe: ["CWE-330"]
      owasp: ["A02:2021 - Cryptographic Failures"]
      confidence: MEDIUM
      category: security
    pattern: new Random()

  # 하드코딩 키
  - id: vulnix.java.crypto.hardcoded_key
    languages: [java]
    severity: ERROR
    message: |
      하드코딩 키: 암호화 키가 소스 코드에 하드코딩되어 있습니다.
      환경변수 또는 키 관리 서비스를 사용하세요.
    metadata:
      cwe: ["CWE-798"]
      owasp: ["A02:2021 - Cryptographic Failures"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: new SecretKeySpec("...".getBytes(), ...)
      - pattern: |
          String $KEY = "..."
    metavariable-regex:
      metavariable: $KEY
      regex: '(?i)(secret|password|api_key|apikey|private_key)'
```

#### 4-3-5. `rules/java/misconfig.yml`

```yaml
rules:
  # Debug mode (Spring)
  - id: vulnix.java.misconfig.spring_debug_enabled
    languages: [java]
    severity: WARNING
    message: |
      설정 오류: Spring 디버그 모드가 활성화되어 있습니다.
      프로덕션 환경에서는 비활성화하세요.
    metadata:
      cwe: ["CWE-489"]
      owasp: ["A05:2021 - Security Misconfiguration"]
      confidence: MEDIUM
      category: security
    pattern: |
      @EnableWebMvcSecurity

  # CORS 과도 허용
  - id: vulnix.java.misconfig.cors_allow_all
    languages: [java]
    severity: WARNING
    message: |
      설정 오류: CORS가 모든 origin을 허용하고 있습니다.
    metadata:
      cwe: ["CWE-942"]
      owasp: ["A05:2021 - Security Misconfiguration"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: |
          @CrossOrigin(origins = "*")
      - pattern: |
          .allowedOrigins("*")

  # 민감 정보 로깅
  - id: vulnix.java.misconfig.sensitive_logging
    languages: [java]
    severity: WARNING
    message: |
      민감 정보 로깅: 패스워드/토큰 등 민감 정보를 로그에 출력하고 있습니다.
    metadata:
      cwe: ["CWE-532"]
      owasp: ["A09:2021 - Security Logging and Monitoring Failures"]
      confidence: MEDIUM
      category: security
    patterns:
      - pattern: $LOG.info("..." + $PASSWORD)
      - pattern: $LOG.debug("..." + $PASSWORD)
    metavariable-regex:
      metavariable: $PASSWORD
      regex: '(?i)(password|secret|token|api_key|credential)'
```

### 4-4. Go 룰 상세

#### 4-4-1. `rules/go/injection.yml`

```yaml
rules:
  # SQL Injection
  - id: vulnix.go.injection.sql_string_format
    languages: [go]
    severity: ERROR
    message: |
      SQL Injection: fmt.Sprintf로 SQL 쿼리를 동적 생성하고 있습니다.
      db.Query(query, args...) 형태의 파라미터 바인딩을 사용하세요.
    metadata:
      cwe: ["CWE-89"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: |
          $DB.Query(fmt.Sprintf("...", $INPUT))
      - pattern: |
          $DB.Exec(fmt.Sprintf("...", $INPUT))
      - pattern: |
          $DB.QueryRow(fmt.Sprintf("...", $INPUT))

  - id: vulnix.go.injection.sql_string_concat
    languages: [go]
    severity: ERROR
    message: |
      SQL Injection: 문자열 연결로 SQL 쿼리를 동적 생성하고 있습니다.
    metadata:
      cwe: ["CWE-89"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: |
          $DB.Query("..." + $INPUT + "...")
      - pattern: |
          $DB.Exec("..." + $INPUT + "...")

  # Command Injection
  - id: vulnix.go.injection.command_exec
    languages: [go]
    severity: ERROR
    message: |
      Command Injection: exec.Command에 사용자 입력을 직접 전달하고 있습니다.
      입력을 검증하고 허용 목록(allowlist)을 사용하세요.
    metadata:
      cwe: ["CWE-78"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: exec.Command($INPUT, ...)
      - pattern: exec.Command("bash", "-c", $INPUT)
      - pattern: exec.Command("sh", "-c", $INPUT)
```

#### 4-4-2. `rules/go/xss.yml`

```yaml
rules:
  # Go template 미이스케이프
  - id: vulnix.go.xss.template_html_unescaped
    languages: [go]
    severity: ERROR
    message: |
      XSS: text/template을 HTML 출력에 사용하고 있습니다.
      html/template을 사용하세요 (자동 이스케이프).
    metadata:
      cwe: ["CWE-79"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
    pattern: |
      import "text/template"

  # Gin HTML 미이스케이프
  - id: vulnix.go.xss.gin_html_unsanitized
    languages: [go]
    severity: WARNING
    message: |
      XSS 위험: Gin 응답에 사용자 입력을 직접 포함하고 있습니다.
    metadata:
      cwe: ["CWE-79"]
      owasp: ["A03:2021 - Injection"]
      confidence: MEDIUM
      category: security
    patterns:
      - pattern: |
          $CTX.Writer.WriteString($INPUT)
```

#### 4-4-3. `rules/go/auth.yml`

```yaml
rules:
  # JWT 검증 미흡
  - id: vulnix.go.auth.jwt_parse_unvalidated
    languages: [go]
    severity: ERROR
    message: |
      인증 취약점: JWT를 검증 없이 파싱하고 있습니다.
      jwt.ParseWithClaims()에 검증 함수를 전달하세요.
    metadata:
      cwe: ["CWE-347"]
      owasp: ["A07:2021 - Identification and Authentication Failures"]
      confidence: HIGH
      category: security
    pattern: jwt.Parse($TOKEN, ...)
```

#### 4-4-4. `rules/go/crypto.yml`

```yaml
rules:
  # 약한 해시
  - id: vulnix.go.crypto.weak_hash_md5
    languages: [go]
    severity: WARNING
    message: |
      암호화 취약점: MD5는 보안용으로 안전하지 않습니다. SHA-256을 사용하세요.
    metadata:
      cwe: ["CWE-328"]
      owasp: ["A02:2021 - Cryptographic Failures"]
      confidence: HIGH
      category: security
    pattern: md5.New()

  - id: vulnix.go.crypto.weak_hash_sha1
    languages: [go]
    severity: WARNING
    message: |
      암호화 취약점: SHA-1은 보안용으로 안전하지 않습니다. SHA-256을 사용하세요.
    metadata:
      cwe: ["CWE-328"]
      owasp: ["A02:2021 - Cryptographic Failures"]
      confidence: HIGH
      category: security
    pattern: sha1.New()

  # 안전하지 않은 랜덤
  - id: vulnix.go.crypto.insecure_random
    languages: [go]
    severity: WARNING
    message: |
      암호화 취약점: math/rand는 암호학적으로 안전하지 않습니다.
      crypto/rand를 사용하세요.
    metadata:
      cwe: ["CWE-330"]
      owasp: ["A02:2021 - Cryptographic Failures"]
      confidence: MEDIUM
      category: security
    pattern: |
      import "math/rand"

  # 하드코딩 키
  - id: vulnix.go.crypto.hardcoded_key
    languages: [go]
    severity: ERROR
    message: |
      하드코딩 키: 시크릿 키가 소스 코드에 하드코딩되어 있습니다.
      환경변수(os.Getenv)를 사용하세요.
    metadata:
      cwe: ["CWE-798"]
      owasp: ["A02:2021 - Cryptographic Failures"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: |
          $KEY := "..."
    metavariable-regex:
      metavariable: $KEY
      regex: '(?i)(secret|password|apiKey|token|privateKey)'
```

#### 4-4-5. `rules/go/misconfig.yml`

```yaml
rules:
  # CORS 과도 허용
  - id: vulnix.go.misconfig.cors_allow_all
    languages: [go]
    severity: WARNING
    message: |
      설정 오류: CORS가 모든 origin을 허용하고 있습니다.
    metadata:
      cwe: ["CWE-942"]
      owasp: ["A05:2021 - Security Misconfiguration"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: |
          AllowAllOrigins: true
      - pattern: cors.Default()

  # 민감 정보 로깅
  - id: vulnix.go.misconfig.sensitive_logging
    languages: [go]
    severity: WARNING
    message: |
      민감 정보 로깅: 패스워드/토큰 등 민감 정보를 로그에 출력하고 있습니다.
    metadata:
      cwe: ["CWE-532"]
      owasp: ["A09:2021 - Security Logging and Monitoring Failures"]
      confidence: MEDIUM
      category: security
    patterns:
      - pattern: log.Printf("..." + $PASSWORD)
      - pattern: fmt.Printf("..." + $PASSWORD)
    metavariable-regex:
      metavariable: $PASSWORD
      regex: '(?i)(password|secret|token|apiKey|credential)'
```

### 4-5. Python 신규 룰 (OWASP 확장)

#### 4-5-1. `rules/python/injection.yml`

```yaml
rules:
  # Command Injection
  - id: vulnix.python.injection.os_system
    languages: [python]
    severity: ERROR
    message: |
      Command Injection: os.system()에 사용자 입력을 전달하고 있습니다.
      subprocess.run()을 쉘 없이 사용하세요.
    metadata:
      cwe: ["CWE-78"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: os.system($CMD + $INPUT)
      - pattern: os.system(f"...{$INPUT}...")

  - id: vulnix.python.injection.subprocess_shell
    languages: [python]
    severity: ERROR
    message: |
      Command Injection: subprocess를 shell=True로 실행하고 있습니다.
      shell=False로 변경하고 인자를 리스트로 전달하세요.
    metadata:
      cwe: ["CWE-78"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: subprocess.run($CMD, shell=True, ...)
      - pattern: subprocess.call($CMD, shell=True, ...)
      - pattern: subprocess.Popen($CMD, shell=True, ...)

  # LDAP Injection
  - id: vulnix.python.injection.ldap_search
    languages: [python]
    severity: ERROR
    message: |
      LDAP Injection: LDAP 검색 필터에 사용자 입력을 직접 삽입하고 있습니다.
      ldap3의 escape_filter_chars()를 사용하세요.
    metadata:
      cwe: ["CWE-90"]
      owasp: ["A03:2021 - Injection"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: |
          $CONN.search($BASE, f"...{$INPUT}...")
      - pattern: |
          $CONN.search($BASE, "..." % $INPUT)
```

#### 4-5-2. `rules/python/auth.yml`

```yaml
rules:
  # JWT 검증 미흡
  - id: vulnix.python.auth.jwt_decode_no_verify
    languages: [python]
    severity: ERROR
    message: |
      인증 취약점: JWT를 서명 검증 없이 디코딩하고 있습니다.
      options={"verify_signature": True}로 설정하세요.
    metadata:
      cwe: ["CWE-347"]
      owasp: ["A07:2021 - Identification and Authentication Failures"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: jwt.decode($TOKEN, options={"verify_signature": False})
      - pattern: jwt.decode($TOKEN, ..., algorithms=["none"])

  # Broken Access Control
  - id: vulnix.python.auth.flask_no_login_required
    languages: [python]
    severity: WARNING
    message: |
      접근 제어 취약점: 관리자 엔드포인트에 인증 데코레이터가 없습니다.
      @login_required 또는 @admin_required를 추가하세요.
    metadata:
      cwe: ["CWE-862"]
      owasp: ["A01:2021 - Broken Access Control"]
      confidence: LOW
      category: security
    patterns:
      - pattern: |
          @app.route("/admin/...")
          def $FUNC(...):
              ...
      - pattern-not: |
          @login_required
          @app.route("/admin/...")
          def $FUNC(...):
              ...
```

#### 4-5-3. `rules/python/crypto.yml`

```yaml
rules:
  # 약한 해시
  - id: vulnix.python.crypto.weak_hash
    languages: [python]
    severity: WARNING
    message: |
      암호화 취약점: MD5/SHA-1은 보안용으로 안전하지 않습니다.
      hashlib.sha256()을 사용하세요.
    metadata:
      cwe: ["CWE-328"]
      owasp: ["A02:2021 - Cryptographic Failures"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: hashlib.md5(...)
      - pattern: hashlib.sha1(...)

  # 안전하지 않은 랜덤
  - id: vulnix.python.crypto.insecure_random
    languages: [python]
    severity: WARNING
    message: |
      암호화 취약점: random 모듈은 암호학적으로 안전하지 않습니다.
      secrets 모듈을 사용하세요.
    metadata:
      cwe: ["CWE-330"]
      owasp: ["A02:2021 - Cryptographic Failures"]
      confidence: MEDIUM
      category: security
    patterns:
      - pattern: random.random()
      - pattern: random.randint(...)
      - pattern: random.choice(...)
```

#### 4-5-4. `rules/python/misconfig.yml`

```yaml
rules:
  # Django DEBUG
  - id: vulnix.python.misconfig.django_debug_true
    languages: [python]
    severity: WARNING
    message: |
      설정 오류: Django DEBUG가 True로 설정되어 있습니다.
      프로덕션에서는 반드시 False로 설정하세요.
    metadata:
      cwe: ["CWE-489"]
      owasp: ["A05:2021 - Security Misconfiguration"]
      confidence: HIGH
      category: security
    pattern: DEBUG = True

  # Flask DEBUG
  - id: vulnix.python.misconfig.flask_debug_true
    languages: [python]
    severity: WARNING
    message: |
      설정 오류: Flask 앱이 debug=True로 실행되고 있습니다.
    metadata:
      cwe: ["CWE-489"]
      owasp: ["A05:2021 - Security Misconfiguration"]
      confidence: HIGH
      category: security
    pattern: app.run(debug=True, ...)

  # CORS 과도 허용 (Flask)
  - id: vulnix.python.misconfig.cors_allow_all
    languages: [python]
    severity: WARNING
    message: |
      설정 오류: CORS가 모든 origin을 허용하고 있습니다.
    metadata:
      cwe: ["CWE-942"]
      owasp: ["A05:2021 - Security Misconfiguration"]
      confidence: HIGH
      category: security
    patterns:
      - pattern: CORS($APP, resources={...: {"origins": "*"}})
      - pattern: CORS($APP, origins="*")

  # 민감 정보 로깅
  - id: vulnix.python.misconfig.sensitive_logging
    languages: [python]
    severity: WARNING
    message: |
      민감 정보 로깅: 패스워드/토큰 등 민감 정보를 로그에 출력하고 있습니다.
    metadata:
      cwe: ["CWE-532"]
      owasp: ["A09:2021 - Security Logging and Monitoring Failures"]
      confidence: MEDIUM
      category: security
    patterns:
      - pattern: logger.info(f"...{$PASSWORD}...")
      - pattern: logging.info(f"...{$PASSWORD}...")
      - pattern: print(f"...{$PASSWORD}...")
    metavariable-regex:
      metavariable: $PASSWORD
      regex: '(?i)(password|secret|token|api_key|apikey|credential)'
```

---

## 5. vulnerability_mapper.py 확장 설계

### 5-1. 새 rule_id 매핑 추가

기존 `RULE_MAPPING` 딕셔너리에 모든 신규 rule_id를 추가한다. 구조는 기존과 동일:

```python
RULE_MAPPING: dict[str, dict[str, str]] = {
    # ========== 기존 Python 룰 (변경 없음) ==========
    "vulnix.python.sql_injection.string_format": { ... },
    # ... (기존 16개 룰 유지)

    # ========== Python 신규 룰 ==========
    # Injection (Command, LDAP)
    "vulnix.python.injection.os_system": {
        "vulnerability_type": "command_injection",
        "cwe_id": "CWE-78",
        "owasp_category": "A03:2021 - Injection",
    },
    "vulnix.python.injection.subprocess_shell": {
        "vulnerability_type": "command_injection",
        "cwe_id": "CWE-78",
        "owasp_category": "A03:2021 - Injection",
    },
    "vulnix.python.injection.ldap_search": {
        "vulnerability_type": "ldap_injection",
        "cwe_id": "CWE-90",
        "owasp_category": "A03:2021 - Injection",
    },
    # Auth
    "vulnix.python.auth.jwt_decode_no_verify": {
        "vulnerability_type": "insecure_jwt",
        "cwe_id": "CWE-347",
        "owasp_category": "A07:2021 - Identification and Authentication Failures",
    },
    "vulnix.python.auth.flask_no_login_required": {
        "vulnerability_type": "broken_access_control",
        "cwe_id": "CWE-862",
        "owasp_category": "A01:2021 - Broken Access Control",
    },
    # Crypto
    "vulnix.python.crypto.weak_hash": {
        "vulnerability_type": "weak_hash",
        "cwe_id": "CWE-328",
        "owasp_category": "A02:2021 - Cryptographic Failures",
    },
    "vulnix.python.crypto.insecure_random": {
        "vulnerability_type": "insecure_random",
        "cwe_id": "CWE-330",
        "owasp_category": "A02:2021 - Cryptographic Failures",
    },
    # Misconfig
    "vulnix.python.misconfig.django_debug_true": {
        "vulnerability_type": "debug_mode_enabled",
        "cwe_id": "CWE-489",
        "owasp_category": "A05:2021 - Security Misconfiguration",
    },
    "vulnix.python.misconfig.flask_debug_true": {
        "vulnerability_type": "debug_mode_enabled",
        "cwe_id": "CWE-489",
        "owasp_category": "A05:2021 - Security Misconfiguration",
    },
    "vulnix.python.misconfig.cors_allow_all": {
        "vulnerability_type": "cors_misconfiguration",
        "cwe_id": "CWE-942",
        "owasp_category": "A05:2021 - Security Misconfiguration",
    },
    "vulnix.python.misconfig.sensitive_logging": {
        "vulnerability_type": "sensitive_data_logging",
        "cwe_id": "CWE-532",
        "owasp_category": "A09:2021 - Security Logging and Monitoring Failures",
    },

    # ========== JavaScript/TypeScript 룰 ==========
    # Injection
    "vulnix.javascript.injection.sql_string_concat": {
        "vulnerability_type": "sql_injection",
        "cwe_id": "CWE-89",
        "owasp_category": "A03:2021 - Injection",
    },
    "vulnix.javascript.injection.sql_sequelize_raw": {
        "vulnerability_type": "sql_injection",
        "cwe_id": "CWE-89",
        "owasp_category": "A03:2021 - Injection",
    },
    "vulnix.javascript.injection.command_exec": {
        "vulnerability_type": "command_injection",
        "cwe_id": "CWE-78",
        "owasp_category": "A03:2021 - Injection",
    },
    "vulnix.javascript.injection.nosql_mongo": {
        "vulnerability_type": "nosql_injection",
        "cwe_id": "CWE-943",
        "owasp_category": "A03:2021 - Injection",
    },
    # XSS
    "vulnix.javascript.xss.innerhtml_assignment": {
        "vulnerability_type": "xss",
        "cwe_id": "CWE-79",
        "owasp_category": "A03:2021 - Injection",
    },
    "vulnix.javascript.xss.react_dangerously_set": {
        "vulnerability_type": "xss",
        "cwe_id": "CWE-79",
        "owasp_category": "A03:2021 - Injection",
    },
    "vulnix.javascript.xss.express_send_unsanitized": {
        "vulnerability_type": "xss",
        "cwe_id": "CWE-79",
        "owasp_category": "A03:2021 - Injection",
    },
    # Auth
    "vulnix.javascript.auth.jwt_no_verify": {
        "vulnerability_type": "insecure_jwt",
        "cwe_id": "CWE-347",
        "owasp_category": "A07:2021 - Identification and Authentication Failures",
    },
    "vulnix.javascript.auth.jwt_algorithm_none": {
        "vulnerability_type": "insecure_jwt",
        "cwe_id": "CWE-347",
        "owasp_category": "A07:2021 - Identification and Authentication Failures",
    },
    # Crypto
    "vulnix.javascript.crypto.weak_hash": {
        "vulnerability_type": "weak_hash",
        "cwe_id": "CWE-328",
        "owasp_category": "A02:2021 - Cryptographic Failures",
    },
    "vulnix.javascript.crypto.hardcoded_secret": {
        "vulnerability_type": "hardcoded_credentials",
        "cwe_id": "CWE-798",
        "owasp_category": "A02:2021 - Cryptographic Failures",
    },
    "vulnix.javascript.crypto.insecure_random": {
        "vulnerability_type": "insecure_random",
        "cwe_id": "CWE-330",
        "owasp_category": "A02:2021 - Cryptographic Failures",
    },
    # Misconfig
    "vulnix.javascript.misconfig.cors_wildcard": {
        "vulnerability_type": "cors_misconfiguration",
        "cwe_id": "CWE-942",
        "owasp_category": "A05:2021 - Security Misconfiguration",
    },
    "vulnix.javascript.misconfig.sensitive_logging": {
        "vulnerability_type": "sensitive_data_logging",
        "cwe_id": "CWE-532",
        "owasp_category": "A09:2021 - Security Logging and Monitoring Failures",
    },

    # ========== Java 룰 ==========
    # (동일 구조, 생략 -- 총 12개 rule_id)
    "vulnix.java.injection.sql_string_concat": { ... },
    "vulnix.java.injection.sql_spring_query": { ... },
    "vulnix.java.injection.command_runtime_exec": { ... },
    "vulnix.java.injection.ldap_search": { ... },
    "vulnix.java.xss.servlet_print_unsanitized": { ... },
    "vulnix.java.xss.spring_model_unsanitized": { ... },
    "vulnix.java.auth.jwt_no_signature_verify": { ... },
    "vulnix.java.auth.spring_permit_all_sensitive": { ... },
    "vulnix.java.crypto.weak_hash": { ... },
    "vulnix.java.crypto.insecure_random": { ... },
    "vulnix.java.crypto.hardcoded_key": { ... },
    "vulnix.java.misconfig.cors_allow_all": { ... },
    "vulnix.java.misconfig.sensitive_logging": { ... },

    # ========== Go 룰 ==========
    # (동일 구조, 생략 -- 총 10개 rule_id)
    "vulnix.go.injection.sql_string_format": { ... },
    "vulnix.go.injection.sql_string_concat": { ... },
    "vulnix.go.injection.command_exec": { ... },
    "vulnix.go.xss.template_html_unescaped": { ... },
    "vulnix.go.xss.gin_html_unsanitized": { ... },
    "vulnix.go.auth.jwt_parse_unvalidated": { ... },
    "vulnix.go.crypto.weak_hash_md5": { ... },
    "vulnix.go.crypto.weak_hash_sha1": { ... },
    "vulnix.go.crypto.insecure_random": { ... },
    "vulnix.go.crypto.hardcoded_key": { ... },
    "vulnix.go.misconfig.cors_allow_all": { ... },
    "vulnix.go.misconfig.sensitive_logging": { ... },
}
```

### 5-2. 헬퍼 함수 추가

```python
def detect_language_from_rule_id(rule_id: str) -> str:
    """rule_id에서 프로그래밍 언어를 추출한다.

    Args:
        rule_id: Semgrep 룰 ID (예: "vulnix.javascript.injection.sql_string_concat")

    Returns:
        언어 문자열 ("python" / "javascript" / "java" / "go" / "unknown")
    """
    parts = rule_id.split(".")
    if len(parts) >= 2 and parts[0] == "vulnix":
        lang = parts[1]
        if lang in ("python", "javascript", "java", "go"):
            return lang
    return "unknown"
```

---

## 6. LLM 프롬프트 변경 설계

### 6-1. `_build_analysis_prompt()` 변경

기존 프롬프트의 하드코딩된 "Python" 문자열을 동적으로 교체한다.

**현재 (변경 전)**:
```python
return f"""다음 Python 코드에서 정적 분석 도구가 탐지한 취약점 목록입니다.
```

**변경 후**:
```python
def _build_analysis_prompt(
    self,
    file_content: str,
    file_path: str,
    findings: list[SemgrepFinding],
) -> str:
    # 파일 확장자로 언어 감지
    language = self._detect_language_from_path(file_path)

    findings_text = "\n".join(
        f"- Rule: {f.rule_id}, Line {f.start_line}-{f.end_line}: {f.message}\n"
        f"  Code: {f.code_snippet}"
        for f in findings
    )

    return f"""다음 {language} 코드에서 정적 분석 도구가 탐지한 취약점 목록입니다.
...
```

### 6-2. 언어 감지 헬퍼 추가

```python
@staticmethod
def _detect_language_from_path(file_path: str) -> str:
    """파일 경로의 확장자로 프로그래밍 언어를 감지한다.

    Returns:
        사람이 읽을 수 있는 언어 문자열 (프롬프트 삽입용)
    """
    ext_map = {
        ".py": "Python",
        ".js": "JavaScript",
        ".jsx": "JavaScript (React)",
        ".ts": "TypeScript",
        ".tsx": "TypeScript (React)",
        ".java": "Java",
        ".go": "Go",
    }
    from pathlib import Path
    ext = Path(file_path).suffix.lower()
    return ext_map.get(ext, "소스")
```

---

## 7. 시퀀스 흐름

기존 F-02 파이프라인과 동일하다. 언어 확장은 Semgrep 룰 디렉토리 추가와 vulnerability_mapper 확장으로 달성되므로 워크플로우 변경은 없다.

```
GitHub Webhook / 수동 트리거
  |
  v
ScanOrchestrator.enqueue_scan()
  |
  v
ScanWorker._run_scan_async()
  |-> git clone (다국어 코드베이스)
  |-> SemgrepEngine.scan(temp_dir)
  |     -- rules/ 전체 디렉토리를 Semgrep에 전달
  |     -- Semgrep이 파일 확장자 기반으로 적절한 룰을 매칭
  |     -- Python .py -> rules/python/*.yml
  |     -- JS/TS .js/.ts/.jsx/.tsx -> rules/javascript/*.yml
  |     -- Java .java -> rules/java/*.yml
  |     -- Go .go -> rules/go/*.yml
  |-> LLMAgent.analyze_findings()
  |     -- file_path 확장자로 언어 감지
  |     -- 프롬프트에 언어명 동적 삽입
  |-> vulnerability_mapper.map_finding_to_vulnerability()
  |     -- 확장된 RULE_MAPPING으로 CWE/OWASP 매핑
  |-> _save_vulnerabilities() + PatchGenerator
```

---

## 8. 영향 범위

### 변경 필요 파일

| 파일 | 변경 내용 |
|------|-----------|
| `backend/src/services/vulnerability_mapper.py` | RULE_MAPPING에 약 50개 rule_id 추가, `detect_language_from_rule_id()` 헬퍼 추가 |
| `backend/src/services/llm_agent.py` | `_build_analysis_prompt()`에서 "Python" -> 동적 언어명, `_detect_language_from_path()` 메서드 추가 |
| `backend/src/rules/README.md` | 새 룰 디렉토리 및 취약점 유형 목록 업데이트 |

### 신규 생성 파일

- `backend/src/rules/javascript/` 5개 yml 파일
- `backend/src/rules/java/` 5개 yml 파일
- `backend/src/rules/go/` 5개 yml 파일
- `backend/src/rules/python/` 4개 yml 파일 (injection, auth, crypto, misconfig)

### 영향 없는 파일 (하위호환)

- `backend/src/services/semgrep_engine.py` -- 변경 없음
- `backend/src/services/scan_orchestrator.py` -- 변경 없음
- `backend/src/services/patch_generator.py` -- 변경 없음
- `backend/src/workers/scan_worker.py` -- 변경 없음
- 기존 Python 룰 3개 파일 -- 변경 없음
- 기존 모든 테스트 -- 통과 유지

---

## 9. 성능 설계

### 9-1. 다국어 스캔 성능 영향

| 항목 | Python만 (현재) | Python+JS+Java+Go | 차이 |
|------|----------------|---------------------|------|
| Semgrep 룰 파일 수 | 3개 | 22개 | +19개 |
| Semgrep 스캔 시간 (10만 라인) | ~45초 | ~60초 | +15초 (예상) |
| LLM 호출 횟수 | 파일 수 비례 | 파일 수 비례 | 변화 없음 |

**근거**: Semgrep은 AST 기반 패턴 매칭이므로 룰 수 증가에 의한 성능 영향이 선형적이지 않다. 언어별 필터링이 자동으로 수행되므로 Python-only 코드베이스를 스캔할 때 JS/Java/Go 룰은 무시된다.

### 9-2. 인수조건 "10만 라인 5분 이내" 유지 확인

기존 성능 분석(F-02 설계서 6-1절)에 따르면 전체 파이프라인이 약 100~270초 소요된다. 룰 추가로 인한 Semgrep 단계 15초 증가는 5분(300초) 이내 목표에 영향을 미치지 않는다.

---

## 10. 최종 파일 구조

```
backend/src/rules/
  README.md                    # 업데이트
  python/
    sql_injection.yml          # 기존 유지
    xss.yml                    # 기존 유지
    hardcoded_creds.yml        # 기존 유지
    injection.yml              # 신규: Command Injection, LDAP Injection
    auth.yml                   # 신규: JWT, Access Control
    crypto.yml                 # 신규: Weak Hash, Insecure Random
    misconfig.yml              # 신규: Debug, CORS, Logging
  javascript/
    injection.yml              # 신규: SQL, Command, NoSQL Injection
    xss.yml                    # 신규: DOM-based, Reflected, Stored XSS
    auth.yml                   # 신규: JWT, Access Control
    crypto.yml                 # 신규: Weak Hash, Hardcoded Key, Insecure Random
    misconfig.yml              # 신규: CORS, Logging
  java/
    injection.yml              # 신규: SQL, Command, LDAP Injection
    xss.yml                    # 신규: Servlet, Spring MVC XSS
    auth.yml                   # 신규: JWT, Spring Security
    crypto.yml                 # 신규: Weak Hash, Insecure Random, Hardcoded Key
    misconfig.yml              # 신규: CORS, Logging
  go/
    injection.yml              # 신규: SQL, Command Injection
    xss.yml                    # 신규: template, Gin XSS
    auth.yml                   # 신규: JWT
    crypto.yml                 # 신규: Weak Hash, Insecure Random, Hardcoded Key
    misconfig.yml              # 신규: CORS, Logging
```

---

## 변경 이력

| 날짜 | 변경 내용 | 이유 |
|------|-----------|------|
| 2026-02-25 | 초안 작성 | F-05 다국어 탐지 엔진 확장 기능 상세 설계 |
