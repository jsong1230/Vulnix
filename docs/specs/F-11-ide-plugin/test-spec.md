# F-11 IDE 플러그인 (VS Code) -- 테스트 명세

## 참조

- 설계서: docs/specs/F-11-ide-plugin/design.md
- 인수조건: docs/project/features.md #F-11

## 인수조건 매핑

| 인수조건 | 테스트 ID | 설명 |
|----------|-----------|------|
| VS Code 익스텐션으로 설치 가능 | U-01, U-02 | activate/deactivate 정상 동작 |
| 코드 작성 중 실시간 취약점 하이라이팅 | I-01, I-02, U-03, U-04, U-05 | 분석 API + 진단 표시 |
| 취약점 위치에 인라인 패치 제안 표시 | I-05, U-06, U-07 | CodeAction 전구 표시 |
| 패치 제안 수락 시 코드 자동 수정 | I-05, I-06, U-08, U-09 | patch-suggestion API + WorkspaceEdit |
| 취약점 상세 설명 패널 제공 | U-10, U-11 | WebviewPanel 상세 패널 |
| Vulnix 서버 연동하여 팀 오탐 규칙 동기화 | I-03, I-04, U-12, U-13, U-14 | FP 패턴 동기화 API + 로컬 캐시 |

---

## 단위 테스트 -- 백엔드 서비스

| ID | 대상 | 시나리오 | 입력 | 예상 결과 |
|----|------|----------|------|-----------|
| U-BS-01 | `IdeAnalyzerService.analyze` | Python 파일 Semgrep 분석 성공 | 취약한 Python 코드 (SQL Injection) | SemgrepFinding 1건 이상 반환 |
| U-BS-02 | `IdeAnalyzerService.analyze` | 안전한 코드 분석 | 취약점 없는 Python 코드 | 빈 findings 반환 |
| U-BS-03 | `IdeAnalyzerService.analyze` | 지원하지 않는 언어 | language="ruby" | INVALID_LANGUAGE 에러 |
| U-BS-04 | `IdeAnalyzerService.analyze` | 빈 content | content="" | 빈 findings 반환 |
| U-BS-05 | `IdeAnalyzerService.analyze` | 1MB 초과 content | 1MB 초과 문자열 | CONTENT_TOO_LARGE 에러 |
| U-BS-06 | `IdeAnalyzerService.analyze` | FP 패턴 필터링 적용 | findings 중 팀 FP 패턴에 매칭되는 항목 | 매칭된 finding에 `is_false_positive_filtered: true` |
| U-BS-07 | `IdeAnalyzerService` | 임시 파일 생성 후 삭제 확인 | 정상 분석 요청 | 분석 완료 후 /tmp/vulnix-ide-* 디렉토리 미존재 |
| U-BS-08 | `ApiKeyService.create_key` | API Key 발급 | name="Test Key", expires_in_days=365 | 키 원본(vx_live_...) + DB에 해시 저장 |
| U-BS-09 | `ApiKeyService.verify_key` | 유효한 API Key 검증 | 발급받은 키 원본 | (team_id, api_key_record) 반환 |
| U-BS-10 | `ApiKeyService.verify_key` | 만료된 API Key | 만료 일시 지난 키 | None 반환 |
| U-BS-11 | `ApiKeyService.verify_key` | 비활성화된 API Key | is_active=False인 키 | None 반환 |
| U-BS-12 | `ApiKeyService.verify_key` | 존재하지 않는 API Key | 임의 문자열 | None 반환 |
| U-BS-13 | `ApiKeyService.revoke_key` | API Key 비활성화 | 유효한 key_id | is_active=False, revoked_at 설정 |

---

## 단위 테스트 -- VS Code 익스텐션

| ID | 대상 | 시나리오 | 입력 | 예상 결과 |
|----|------|----------|------|-----------|
| U-01 | `extension.activate` | 정상 활성화 | 지원 언어 파일 열기 | DiagnosticCollection 생성, StatusBar 표시, 이벤트 리스너 등록 |
| U-02 | `extension.deactivate` | 정상 비활성화 | 익스텐션 비활성화 | DiagnosticCollection.dispose(), StatusBar.dispose() 호출 |
| U-03 | `DiagnosticMapper.map` | critical 취약점 매핑 | severity="critical" finding | DiagnosticSeverity.Error, 빨간 밑줄 |
| U-04 | `DiagnosticMapper.map` | medium 취약점 매핑 | severity="medium" finding | DiagnosticSeverity.Warning, 노란 밑줄 |
| U-05 | `DiagnosticMapper.map` | low 취약점 매핑 | severity="low" finding | DiagnosticSeverity.Information, 파란 밑줄 |
| U-06 | `CodeActionProvider` | Vulnix 진단에 대해 전구 표시 | Vulnix source의 Diagnostic | "Apply Patch Fix" + "Show Detail" 두 가지 CodeAction 반환 |
| U-07 | `CodeActionProvider` | 비-Vulnix 진단 무시 | 다른 source의 Diagnostic | 빈 CodeAction 목록 |
| U-08 | `PatchApplier.apply` | 패치 diff 적용 성공 | 유효한 unified diff | WorkspaceEdit 생성, 해당 라인 텍스트 교체 |
| U-09 | `PatchApplier.apply` | 잘못된 diff 형식 | 파싱 불가능한 문자열 | 에러 메시지 표시, 코드 변경 없음 |
| U-10 | `WebviewPanel` | 상세 패널 생성 | finding 데이터 | WebviewPanel 생성, HTML에 취약점 정보 포함 |
| U-11 | `WebviewPanel` | "Apply Patch" 메시지 수신 | webview에서 메시지 전송 | PatchApplier.apply() 호출 |
| U-12 | `FPCache.sync` | 초기 동기화 | 서버에 3개 패턴 존재 | globalState에 3개 패턴 저장 |
| U-13 | `FPCache.sync` | ETag 일치 시 304 | 변경 없음 | 캐시 유지, API 응답 본문 파싱 없음 |
| U-14 | `FPCache.matchesAny` | 오탐 패턴 매칭 | rule_id + file_path가 패턴과 일치 | true 반환 |
| U-15 | `FPCache.matchesAny` | 매칭 안되는 finding | rule_id 불일치 | false 반환 |
| U-16 | `Analyzer.analyzeFile` | 지원하지 않는 언어 | Ruby 파일 | 분석 스킵, API 호출 없음 |
| U-17 | `Analyzer.analyzeFile` | 1MB 초과 파일 | 대용량 파일 | 분석 스킵, 경고 메시지 |
| U-18 | `Analyzer.analyzeFile` | 연속 저장 디바운스 | 500ms 내 3회 저장 | API 호출 1회만 발생 |
| U-19 | `StatusBar` | 분석 중 상태 표시 | 분석 시작 | "$(loading~spin) Vulnix: analyzing..." 표시 |
| U-20 | `StatusBar` | 결과 표시 | findings 3건 | "$(shield) Vulnix: 3 issues" 표시 |
| U-21 | `StatusBar` | 오프라인 상태 | API 호출 실패 | "$(shield) Vulnix: offline" 표시 |
| U-22 | `ApiClient` | 서버 URL 미설정 | serverUrl="" | 설정 안내 메시지 표시 |
| U-23 | `ApiClient` | API Key 미설정 | apiKey="" | 설정 안내 메시지 표시 |
| U-24 | `Config` | 설정 변경 감지 | serverUrl 변경 | ApiClient 재초기화 |

---

## 통합 테스트 -- 백엔드 API

| ID | API | 시나리오 | 입력 | 예상 결과 |
|----|-----|----------|------|-----------|
| I-01 | `POST /api/v1/ide/analyze` | SQL Injection 탐지 | Python 코드: `db.execute(f"SELECT * FROM users WHERE id = {user_id}")` | 200, findings에 sql_injection 항목, severity="high" |
| I-02 | `POST /api/v1/ide/analyze` | XSS 탐지 | Python Flask 코드: `return f"<p>{request.args.get('name')}</p>"` | 200, findings에 xss 항목 |
| I-03 | `POST /api/v1/ide/analyze` | 안전한 코드 | 파라미터 바인딩 사용한 안전 코드 | 200, findings 빈 배열 |
| I-04 | `POST /api/v1/ide/analyze` | FP 패턴 적용 | 팀에 FP 패턴 등록 후 해당 룰 매칭 코드 분석 | 200, 해당 finding의 `is_false_positive_filtered: true` |
| I-05 | `POST /api/v1/ide/analyze` | JavaScript 파일 분석 | JS 코드: `eval(userInput)` | 200, findings에 code_injection 항목 |
| I-06 | `POST /api/v1/ide/analyze` | 인증 실패 (API Key 없음) | `X-API-Key` 헤더 누락 | 401, INVALID_API_KEY |
| I-07 | `POST /api/v1/ide/analyze` | 인증 실패 (잘못된 API Key) | `X-API-Key: invalid_key` | 401, INVALID_API_KEY |
| I-08 | `POST /api/v1/ide/analyze` | 비활성 API Key | is_active=False인 키 | 403, API_KEY_DISABLED |
| I-09 | `POST /api/v1/ide/analyze` | 만료된 API Key | expires_at 지난 키 | 401, INVALID_API_KEY |
| I-10 | `POST /api/v1/ide/analyze` | 지원하지 않는 언어 | language="ruby" | 400, INVALID_LANGUAGE |
| I-11 | `POST /api/v1/ide/analyze` | content 1MB 초과 | 1.5MB 코드 | 400, CONTENT_TOO_LARGE |
| I-12 | `POST /api/v1/ide/analyze` | Rate limit 초과 | 61회 연속 호출 | 429, RATE_LIMIT_EXCEEDED |
| I-13 | `GET /api/v1/ide/false-positive-patterns` | 팀 FP 패턴 조회 | 유효한 API Key (팀에 FP 패턴 3개) | 200, patterns 3개, ETag 헤더 |
| I-14 | `GET /api/v1/ide/false-positive-patterns` | ETag 캐시 히트 | `If-None-Match` 일치 | 304, 본문 없음 |
| I-15 | `GET /api/v1/ide/false-positive-patterns` | FP 패턴 없는 팀 | 패턴 미등록 팀의 API Key | 200, 빈 patterns 배열 |
| I-16 | `POST /api/v1/ide/patch-suggestion` | 패치 제안 생성 성공 | SQL Injection finding + 코드 | 200, patch_diff (unified diff), patch_description, vulnerability_detail |
| I-17 | `POST /api/v1/ide/patch-suggestion` | 패치 제안 rate limit | 11회 연속 호출 | 429, RATE_LIMIT_EXCEEDED |
| I-18 | `POST /api/v1/ide/patch-suggestion` | 불완전한 finding 정보 | rule_id 누락 | 400, INVALID_FINDING |
| I-19 | `POST /api/v1/ide/api-keys` | API Key 발급 | JWT 인증 (owner), name="Test Key" | 201, key (vx_live_...), key_prefix, expires_at |
| I-20 | `POST /api/v1/ide/api-keys` | API Key 발급 (권한 부족) | JWT 인증 (member) | 403, "admin/owner 권한이 필요합니다" |
| I-21 | `POST /api/v1/ide/api-keys` | API Key 발급 (미인증) | JWT 없음 | 401 |
| I-22 | `DELETE /api/v1/ide/api-keys/{id}` | API Key 비활성화 | JWT 인증 (admin), 유효한 key_id | 200, revoked_at 설정 |
| I-23 | `DELETE /api/v1/ide/api-keys/{id}` | 존재하지 않는 Key | JWT 인증, 잘못된 key_id | 404 |
| I-24 | `POST /api/v1/ide/analyze` | 임시 파일 정리 확인 | 정상 요청 후 서버 /tmp 확인 | /tmp/vulnix-ide-* 디렉토리 미존재 |

---

## 경계 조건 / 에러 케이스

### 백엔드

- 빈 파일 (content="") 분석 시 findings 빈 배열 반환 (에러 아님)
- content에 바이너리 데이터 포함 시 400 에러 (UTF-8 디코딩 실패)
- Semgrep CLI가 서버에 미설치 시 500, ANALYSIS_FAILED 에러 + 구체적 메시지
- Semgrep 실행 타임아웃(10분) 시 500, ANALYSIS_FAILED
- Claude API 호출 실패 시 patch-suggestion은 502, LLM_SERVICE_UNAVAILABLE
- Claude API 응답 타임아웃(30초) 시 504, LLM_TIMEOUT
- API Key SHA-256 해시 충돌 확률은 무시 가능 (2^128 생일 역설 기준)
- 동일 팀에서 동시에 다수 IDE 분석 요청 시 rate limit 공유 (팀 단위)

### VS Code 익스텐션

- 서버 연결 불가 시 이전 진단 결과 유지, 상태바에 "offline" 표시
- 파일이 닫힌 후 진단 자동 제거 (onDidCloseTextDocument)
- 패치 적용 중 파일이 외부에서 변경된 경우 충돌 경고 표시
- API Key 형식 검증: `vx_live_` 또는 `vx_test_` 접두사 확인
- 다중 워크스페이스에서 각 워크스페이스별 독립 분석
- 매우 긴 파일(10,000줄 이상) 분석 시 타임아웃 처리 (30초)
- 네트워크 지연(느린 응답) 시 이전 분석 결과 취소 (AbortController)

---

## E2E 테스트 시나리오 (수동/자동)

| ID | 시나리오 | 수행 방법 | 예상 결과 |
|----|----------|-----------|-----------|
| E-01 | 익스텐션 설치 및 활성화 | VS Code에서 .vsix 파일 설치 | 상태바에 Vulnix 아이콘 표시 |
| E-02 | 서버 URL + API Key 설정 | Settings에서 입력 | 연결 성공 후 상태바 "0 issues" |
| E-03 | 취약한 Python 파일 저장 | SQL Injection 코드 포함 파일 저장 | 해당 라인에 빨간 밑줄 + Problems 패널에 항목 |
| E-04 | 전구 아이콘 클릭 -> 패치 적용 | 밑줄 위에서 전구 클릭 -> "Apply Patch Fix" | 코드가 안전한 코드로 자동 수정됨 |
| E-05 | 상세 패널 열기 | 전구 -> "Show Vulnerability Detail" | 웹뷰 패널에 취약점 설명, CWE, 참고 링크 표시 |
| E-06 | 오탐 패턴 동기화 후 필터링 | 서버에서 FP 패턴 등록 -> VS Code에서 Sync 명령 -> 파일 저장 | FP 패턴 매칭된 finding 미표시 |
| E-07 | 서버 연결 해제 상태 | 서버 URL을 잘못된 값으로 변경 -> 파일 저장 | 상태바 "offline", 이전 진단 유지 |

---

## 성능 테스트

| ID | 대상 | 시나리오 | 목표 |
|----|------|----------|------|
| P-01 | `POST /ide/analyze` | 100줄 Python 파일 | p95 < 300ms |
| P-02 | `POST /ide/analyze` | 1,000줄 Python 파일 | p95 < 500ms |
| P-03 | `POST /ide/analyze` | 5,000줄 Python 파일 (최대 지원) | p95 < 2s |
| P-04 | `POST /ide/patch-suggestion` | 단일 finding 패치 제안 | p95 < 10s (LLM 포함) |
| P-05 | `GET /ide/false-positive-patterns` | 패턴 50개 팀 | p95 < 100ms |
| P-06 | `GET /ide/false-positive-patterns` | ETag 캐시 히트 | p95 < 50ms |
| P-07 | Rate limit | 60회/분 초과 시 | 61번째 요청에서 429 응답 |

---

## 보안 테스트

| ID | 시나리오 | 예상 결과 |
|----|----------|-----------|
| S-01 | API Key 없이 /ide/analyze 호출 | 401 응답 |
| S-02 | 만료/비활성 API Key로 호출 | 401 또는 403 응답 |
| S-03 | JWT로 /ide/analyze 호출 (API Key 대신) | 401 응답 (X-API-Key 헤더 필수) |
| S-04 | 다른 팀의 API Key로 FP 패턴 조회 | 해당 팀의 패턴만 반환 (교차 접근 불가) |
| S-05 | content에 경로 탈출 시도 (../../etc/passwd) | file_path가 분석에 영향 없음 (Semgrep은 content만 분석) |
| S-06 | 분석 완료 후 임시 파일 잔존 여부 | /tmp/vulnix-ide-* 디렉토리 미존재 |
| S-07 | API Key 원본값 DB 조회 시도 | DB에 해시만 저장, 원본 복원 불가 |
| S-08 | Rate limit 우회 시도 (다수 API Key) | 팀 단위 rate limit이므로 같은 팀이면 합산 |
