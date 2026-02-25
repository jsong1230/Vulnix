# F-05 다국어 탐지 엔진 확장 — DB 스키마 확정본

**버전**: v1.0
**작성일**: 2026-02-25
**상태**: 확정

---

## 개요

F-05는 DB 스키마를 변경하지 않는다. 기존 `Vulnerability` 테이블 구조를 그대로 사용하며,
신규 언어(JavaScript, Java, Go)의 탐지 결과도 동일한 스키마에 저장된다.

---

## DB 변경사항

**없음.** 마이그레이션 파일 없음.

---

## 기존 스키마와의 호환성

### `vulnerability` 테이블

```sql
-- 기존 컬럼에 저장되는 신규 값 목록 (F-05 추가분)
-- vulnerability_type: "sql_injection" | "xss" | "hardcoded_credentials" |
--                     "insecure_jwt" | "command_injection" | "weak_crypto" |
--                     "insecure_random" | "security_misconfiguration" | "unknown"
-- cwe_id: "CWE-89" | "CWE-79" | "CWE-78" | "CWE-798" | "CWE-347" |
--         "CWE-327" | "CWE-328" | "CWE-330" | "CWE-942" | NULL
-- owasp_category: "A02:2021 - Cryptographic Failures" |
--                 "A03:2021 - Injection" |
--                 "A05:2021 - Security Misconfiguration" |
--                 "A07:2021 - Identification and Authentication Failures" | NULL
```

기존에 저장되던 Python 탐지 결과와 동일한 컬럼(`vulnerability_type`, `cwe_id`, `owasp_category`, `severity`)에
JavaScript, Java, Go 탐지 결과도 저장된다.

---

## Semgrep 룰 파일 구조 (코드 자산)

DB가 아닌 파일시스템에 저장되는 룰 파일 목록 (F-05 신규 추가):

```
backend/src/rules/
  javascript/
    sql_injection.yml    -- vulnix.javascript.injection.sql_string_concat
    xss.yml              -- vulnix.javascript.xss.innerhtml_assignment
                         -- vulnix.javascript.xss.document_write
    hardcoded_creds.yml  -- vulnix.javascript.crypto.hardcoded_key
    insecure_jwt.yml     -- vulnix.javascript.auth.jwt_no_verify
    misconfig.yml        -- vulnix.javascript.misconfig.cors_wildcard
  java/
    sql_injection.yml    -- vulnix.java.injection.sql_string_concat
    xss.yml              -- vulnix.java.xss.servlet_print_unsanitized
    hardcoded_creds.yml  -- vulnix.java.crypto.hardcoded_key
    weak_crypto.yml      -- vulnix.java.crypto.weak_hash
                         -- vulnix.java.crypto.insecure_random
  go/
    sql_injection.yml    -- vulnix.go.injection.sql_string_format
    command_injection.yml -- vulnix.go.injection.command_exec
    hardcoded_creds.yml  -- vulnix.go.crypto.hardcoded_key
    weak_crypto.yml      -- vulnix.go.crypto.weak_hash_md5
  python/                -- (기존 유지, 변경 없음)
    ...
```

---

## 변경 이력

| 날짜 | 변경 내용 |
|------|-----------|
| 2026-02-25 | F-05 구현 완료 — DB 스키마 변경 없음, 룰 파일 13개 신규 추가 |
