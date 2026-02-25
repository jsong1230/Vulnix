# F-06 오탐 관리 -- 테스트 명세

**버전**: v1.0
**작성일**: 2026-02-25

---

## 참조

- 설계서: docs/specs/F-06-false-positive-mgmt/design.md
- 인수조건: docs/project/features.md #F-06

---

## 단위 테스트

### UT-01: FPFilterService 패턴 매칭 로직

| 대상 | 시나리오 | 입력 | 예상 결과 |
|------|----------|------|-----------|
| `_matches_pattern` | rule_id 일치 + file_pattern null (모든 파일 대상) | finding(rule_id="python.flask.xss", file_path="src/app.py"), pattern(rule_id="python.flask.xss", file_pattern=None) | True |
| `_matches_pattern` | rule_id 일치 + file_pattern glob 일치 | finding(rule_id="generic.secrets", file_path="tests/test_auth.py"), pattern(rule_id="generic.secrets", file_pattern="tests/**") | True |
| `_matches_pattern` | rule_id 일치 + file_pattern glob 불일치 | finding(rule_id="generic.secrets", file_path="src/auth.py"), pattern(rule_id="generic.secrets", file_pattern="tests/**") | False |
| `_matches_pattern` | rule_id 불일치 | finding(rule_id="python.flask.xss", file_path="tests/test.py"), pattern(rule_id="generic.secrets", file_pattern="tests/**") | False |
| `_matches_pattern` | file_pattern에 `**/` 접두사가 있는 경우 | finding(rule_id="python.sql", file_path="src/db/migrations/001.py"), pattern(rule_id="python.sql", file_pattern="**/migrations/*") | True |

### UT-02: FPFilterService 필터링 실행

| 대상 | 시나리오 | 입력 | 예상 결과 |
|------|----------|------|-----------|
| `filter_findings` | 패턴 0개 (필터링 없음) | findings 5개, 팀에 패턴 없음 | (findings 5개 그대로, auto_filtered=0) |
| `filter_findings` | 패턴 1개, 매칭 2건 | findings 5개 중 2개가 패턴에 일치 | (findings 3개, auto_filtered=2) |
| `filter_findings` | 패턴 여러 개, 전부 매칭 | findings 3개 모두 패턴에 일치 | (findings 0개, auto_filtered=3) |
| `filter_findings` | 비활성 패턴은 무시 | findings 3개, 패턴 1개(is_active=false) | (findings 3개, auto_filtered=0) |
| `filter_findings` | 매칭 시 matched_count 업데이트 확인 | 패턴 matched_count=5, 이번 스캔에서 3건 매칭 | pattern.matched_count == 8, last_matched_at 갱신 |
| `filter_findings` | 매칭 시 false_positive_log 레코드 생성 확인 | 2건 필터링 | false_positive_log에 2건 INSERT |

### UT-03: 오탐율 계산 로직

| 대상 | 시나리오 | 입력 | 예상 결과 |
|------|----------|------|-----------|
| 오탐율 계산 | 정상 케이스 | tp=70, fp=30 | fp_rate = 30.0% |
| 오탐율 계산 | 오탐 0건 | tp=100, fp=0 | fp_rate = 0.0% |
| 오탐율 계산 | 전부 오탐 | tp=0, fp=50 | fp_rate = 100.0% |
| 오탐율 계산 | 스캔 없음 (ZeroDivisionError 방지) | tp=0, fp=0 | fp_rate = 0.0% |
| 오탐율 개선 | 이전 기간 대비 개선율 | 이전 32%, 현재 25.5% | improvement = 6.5% |

### UT-04: 패턴 자동 생성 (취약점 상태 변경 시)

| 대상 | 시나리오 | 입력 | 예상 결과 |
|------|----------|------|-----------|
| 패턴 자동 생성 | create_pattern=true, file_pattern 지정 | status="false_positive", create_pattern=true, file_pattern="tests/**" | FalsePositivePattern 레코드 생성, source_vulnerability_id 설정 |
| 패턴 자동 생성 | create_pattern=true, file_pattern 미지정 (자동 추론) | status="false_positive", create_pattern=true, 취약점 file_path="tests/unit/test_auth.py" | file_pattern = "tests/unit/**" (디렉토리 기반 자동 추론) |
| 패턴 미생성 | create_pattern=false | status="false_positive", create_pattern=false | FalsePositivePattern 생성 안 됨, 취약점 상태만 변경 |
| 패턴 미생성 | create_pattern 생략 (기본값) | status="false_positive" | FalsePositivePattern 생성 안 됨 |
| 패턴 미생성 | status가 false_positive가 아닌 경우 | status="ignored", create_pattern=true | create_pattern 무시, 패턴 생성 안 됨 |
| 중복 방지 | 동일 패턴이 이미 존재 | 이미 동일 team_id + rule_id + file_pattern 존재 | 409 에러 없이 기존 패턴 재활용 (중복 INSERT 시도 안 함) |

---

## 통합 테스트

### IT-01: 오탐 패턴 CRUD API

| API | 시나리오 | 입력 | 예상 결과 |
|-----|----------|------|-----------|
| POST /api/v1/false-positives | 정상 패턴 등록 | team_id, semgrep_rule_id, reason (admin 사용자) | 201 Created, 패턴 데이터 반환 |
| POST /api/v1/false-positives | semgrep_rule_id 누락 | team_id만 전달 | 422 Validation Error |
| POST /api/v1/false-positives | 팀 멤버 권한 (admin 아님) | member 역할 사용자 | 403 Forbidden |
| POST /api/v1/false-positives | 존재하지 않는 team_id | 잘못된 UUID | 404 Not Found |
| POST /api/v1/false-positives | 중복 패턴 등록 | 동일 team_id + rule_id + file_pattern | 409 Conflict |
| GET /api/v1/false-positives | 팀별 패턴 목록 조회 | team_id 파라미터 (team member) | 200 OK, 해당 팀의 활성 패턴 목록 |
| GET /api/v1/false-positives | 비활성 포함 조회 | is_active=false | 200 OK, 비활성 패턴도 포함 |
| GET /api/v1/false-positives | 소속되지 않은 팀 조회 | 다른 팀의 team_id | 403 Forbidden |
| DELETE /api/v1/false-positives/{id} | 정상 삭제 (소프트) | admin 사용자 | 200 OK, is_active=false |
| DELETE /api/v1/false-positives/{id} | 존재하지 않는 ID | 잘못된 UUID | 404 Not Found |
| DELETE /api/v1/false-positives/{id} | 권한 없음 | member 역할 사용자 | 403 Forbidden |
| PUT /api/v1/false-positives/{id}/restore | 정상 복원 | admin 사용자, 비활성 패턴 | 200 OK, is_active=true |
| PUT /api/v1/false-positives/{id}/restore | 이미 활성인 패턴 복원 | is_active=true인 패턴 | 200 OK (멱등, 상태 변경 없음) |

### IT-02: 취약점 상태 변경 + 패턴 생성 연동

| API | 시나리오 | 입력 | 예상 결과 |
|-----|----------|------|-----------|
| PATCH /api/v1/vulnerabilities/{id} | 오탐 마킹 + 패턴 생성 | status="false_positive", create_pattern=true, file_pattern="tests/**" | 200 OK, vulnerability.status="false_positive", FalsePositivePattern 1건 생성 |
| PATCH /api/v1/vulnerabilities/{id} | 오탐 마킹만 (패턴 미생성) | status="false_positive", create_pattern=false | 200 OK, vulnerability.status="false_positive", FalsePositivePattern 생성 안 됨 |
| PATCH /api/v1/vulnerabilities/{id} | 오탐 해제 (복원) | status="open" (기존 false_positive 상태) | 200 OK, vulnerability.status="open", resolved_at=None |
| PATCH /api/v1/vulnerabilities/{id} | 오탐 해제 시 연관 패턴에 영향 없음 | status="open"으로 복원 | 연관 FalsePositivePattern은 그대로 유지 (독립적) |
| PATCH /api/v1/vulnerabilities/{id} | 권한 없는 팀의 취약점 | 다른 팀 저장소의 취약점 | 403 Forbidden |

### IT-03: 오탐율 대시보드 API

| API | 시나리오 | 입력 | 예상 결과 |
|-----|----------|------|-----------|
| GET /api/v1/dashboard/false-positive-rate | 기본 조회 (30일) | 인증된 사용자 | 200 OK, current_fp_rate, trend 배열 반환 |
| GET /api/v1/dashboard/false-positive-rate | 기간 지정 | days=7 | 200 OK, 7일간 데이터 |
| GET /api/v1/dashboard/false-positive-rate | 최대 기간 초과 | days=120 | 200 OK, 90일로 클램핑 |
| GET /api/v1/dashboard/false-positive-rate | 저장소 필터 | repo_id=uuid | 200 OK, 해당 저장소만 집계 |
| GET /api/v1/dashboard/false-positive-rate | 스캔 기록 없음 | 신규 팀, 스캔 0건 | 200 OK, current_fp_rate=0.0, trend=[] |
| GET /api/v1/dashboard/false-positive-rate | 인증 없음 | Authorization 헤더 없음 | 401 Unauthorized |

### IT-04: 스캔 파이프라인 오탐 자동 필터링

| API | 시나리오 | 입력 | 예상 결과 |
|-----|----------|------|-----------|
| 스캔 파이프라인 | 패턴에 매칭되는 finding이 있는 경우 | Semgrep findings 10건, 패턴 매칭 3건 | LLM에 7건만 전달, auto_filtered_count=3, false_positive_log 3건 생성 |
| 스캔 파이프라인 | 패턴이 없는 경우 | 팀에 패턴 0건 | 기존과 동일하게 모든 findings가 LLM으로 전달 |
| 스캔 파이프라인 | 모든 findings가 필터링된 경우 | Semgrep findings 5건, 전부 패턴 매칭 | LLM 호출 안 함, completed 처리, auto_filtered_count=5 |

---

## 경계 조건 / 에러 케이스

### 패턴 관련

- file_pattern에 잘못된 glob 패턴 입력 시 (예: `[invalid`): 422 Validation Error 반환
- file_pattern에 보안 위험한 패턴 입력 시 (예: `../../../../etc/passwd`): 패턴 길이 500자 제한으로 방어, 추가 검증 불필요 (glob 패턴은 파일 접근에 사용되지 않음)
- semgrep_rule_id에 255자 초과 입력: 422 Validation Error
- reason이 빈 문자열인 경우: 422 Validation Error (최소 1자 이상 필수)
- team_id가 UUID 형식이 아닌 경우: 422 Validation Error

### 동시성 관련

- 동일 패턴에 대해 두 사용자가 동시에 DELETE + RESTORE 요청: DB unique constraint로 일관성 보장
- 스캔 실행 중 패턴이 삭제/비활성화되는 경우: 스캔 시작 시점의 패턴 스냅샷을 사용하므로 영향 없음
- 동일 취약점에 대해 두 사용자가 동시에 false_positive 마킹 + 패턴 생성: 첫 번째 요청 성공, 두 번째 요청은 중복 패턴 감지하여 기존 패턴 재활용

### 데이터 정합성

- 취약점을 open으로 복원해도 연관 FalsePositivePattern은 삭제되지 않음 (의도적 설계)
- FalsePositivePattern의 source_vulnerability_id가 가리키는 취약점이 삭제된 경우: NULL로 처리 (FK ON DELETE SET NULL)
- 팀이 삭제된 경우 관련 패턴도 CASCADE 삭제
- matched_count 누적 시 integer overflow 가능성: 실무상 불가능 (42억 이상), 무시

### 스캔 파이프라인 관련

- FPFilterService DB 조회 실패 시: 필터링 건너뛰고 모든 findings를 LLM으로 전달 (fail-open), 경고 로그 기록
- 패턴 매칭 중 예외 발생 시: 해당 패턴만 건너뛰고 나머지 매칭 계속 진행
- auto_filtered_count 업데이트 실패 시: 스캔 자체는 completed 유지

---

## 회귀 테스트

이 기능은 기존 F-04(스캔 결과 API 및 기본 UI)를 확장하므로 아래 회귀 테스트가 필요합니다.

| 기존 기능 | 영향 여부 | 검증 방법 |
|-----------|-----------|-----------|
| PATCH /vulnerabilities/{id} 기존 동작 | 영향 있음 (확장) | create_pattern 필드 없이 호출 시 기존과 동일하게 동작하는지 확인 |
| 취약점 목록 조회 (GET /vulnerabilities) | 영향 없음 | 기존 필터링 (status, severity) 정상 동작 확인 |
| 취약점 상세 조회 (GET /vulnerabilities/{id}) | 영향 없음 | 응답 형식 변경 없음 확인 |
| 대시보드 요약 통계 (GET /dashboard/summary) | 영향 없음 | false_positive 상태 카운트가 기존과 동일하게 집계되는지 확인 |
| 대시보드 추이 (GET /dashboard/trend) | 영향 없음 | resolved_count에 false_positive가 포함되는 기존 동작 유지 확인 |
| 보안 점수 계산 (_calc_security_score) | 영향 없음 | false_positive 상태 취약점이 open_weighted에 포함되지 않는 기존 동작 확인 |
| 스캔 파이프라인 (scan_worker) | 영향 있음 (확장) | 패턴 0개일 때 기존과 동일한 파이프라인 실행 확인 |
| LLM 분석 (llm_agent) | 영향 없음 | LLMAgent 자체에는 변경 없음, 입력 findings만 달라짐 |
| StatusActions UI 컴포넌트 | 영향 있음 (확장) | create_pattern 옵션 없이 "오탐으로 표시" 클릭 시 기존과 동일하게 동작하는지 확인 |
| patchVulnerabilityStatus API 클라이언트 | 영향 있음 (확장) | 추가 파라미터 없이 호출 시 기존과 동일하게 동작하는지 확인 |

---

## 테스트 환경 요구사항

### 테스트 데이터 시드

- Team 2개 (team_a, team_b)
- User 3명 (admin_a: team_a admin, member_a: team_a member, admin_b: team_b admin)
- Repository 2개 (repo_a -> team_a, repo_b -> team_b)
- Vulnerability 10개 (repo_a에 7개, repo_b에 3개, status 혼합)
- ScanJob 5개 (repo_a에 3개, repo_b에 2개, 다양한 tp/fp 카운트)
- FalsePositivePattern 3개 (team_a에 2개, team_b에 1개)

### Mock 대상

- DB 세션: AsyncSession mock (SQLite in-memory 또는 pytest-asyncio + testcontainers-postgres)
- LLMAgent: 전체 mock (오탐 필터링은 LLM 호출 전에 발생하므로 LLM mock 필요 없음, 파이프라인 테스트에서만 필요)
- GitHubAppService: 전체 mock (clone_repository)
- SemgrepEngine: 전체 mock (scan 결과를 fixture로 제공)

### 테스트 파일 구조

```
backend/tests/
  test_fp_filter_service.py       # UT-01, UT-02 (FPFilterService 단위 테스트)
  test_fp_rate_calculation.py     # UT-03 (오탐율 계산 로직)
  test_fp_pattern_creation.py     # UT-04 (패턴 자동 생성 로직)
  test_api_false_positives.py     # IT-01 (오탐 패턴 CRUD API)
  test_api_vuln_fp_integration.py # IT-02 (취약점 상태 변경 + 패턴 연동)
  test_api_fp_rate_dashboard.py   # IT-03 (오탐율 대시보드 API)
  test_scan_pipeline_fp_filter.py # IT-04 (스캔 파이프라인 필터링 통합)
```
