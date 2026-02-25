# Vulnix 커스텀 Semgrep 룰

PoC 범위: Python 코드 대상 3가지 취약점 유형

## 룰 목록

| 파일 | 취약점 유형 | CWE |
|------|------------|-----|
| `python/sql_injection.yml` | SQL Injection | CWE-89 |
| `python/xss.yml` | Cross-Site Scripting (XSS) | CWE-79 |
| `python/hardcoded_creds.yml` | Hardcoded Credentials | CWE-798 |

## 실행 방법

```bash
# 단일 룰셋으로 스캔
semgrep scan --config=./rules/python/ --json <target_dir>

# auto 룰셋과 함께 스캔
semgrep scan --config=auto --config=./rules/ --json <target_dir>
```

## 룰 작성 가이드

- `id`: `vulnix.python.{category}.{rule_name}` 형식
- `severity`: ERROR (Critical/High), WARNING (Medium), INFO (Low)
- `metadata.cwe`: CWE 번호 배열
- `metadata.confidence`: HIGH / MEDIUM / LOW
- `fix`: 자동 수정 패턴 (가능한 경우)
