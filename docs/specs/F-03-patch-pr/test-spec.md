# F-03 자동 패치 PR 생성 -- 테스트 명세

## 참조

- 설계서: `docs/specs/F-03-patch-pr/design.md`
- 인수조건: `docs/project/features.md` #F-03

---

## 단위 테스트

### PatchGenerator

| # | 대상 메서드 | 시나리오 | 입력 | 예상 결과 |
|---|-------------|----------|------|-----------|
| U-01 | `_make_branch_name()` | 정상 브랜치명 생성 | vulnerability_type="sql_injection", file_path="app/db.py", start_line=42 | "vulnix/fix-sql-injection-{7자 해시}" 형식, `_` -> `-` 치환 확인 |
| U-02 | `_make_branch_name()` | 특수문자 포함 유형 | vulnerability_type="hardcoded_credentials", file_path="config/settings.py", start_line=10 | "vulnix/fix-hardcoded-credentials-{7자 해시}" |
| U-03 | `_make_branch_name()` | 동일 유형/다른 파일 | 같은 type, 다른 file_path | 서로 다른 해시 생성 (유니크 보장) |
| U-04 | `generate_patch_prs()` | 패치 가능 항목 1건 | is_true_positive=True, patch_diff="---...", 나머지 mock | PatchPR 1건 생성, status="created", GitHub API 호출 4회 (sha조회+branch생성+file commit+PR생성) |
| U-05 | `generate_patch_prs()` | 패치 불가 항목 1건 | is_true_positive=True, patch_diff=None | PatchPR 0건, Vulnerability.manual_guide 저장됨, Vulnerability.manual_priority != None |
| U-06 | `generate_patch_prs()` | 오탐 항목 (스킵) | is_true_positive=False | PatchPR 0건, GitHub API 호출 0회 |
| U-07 | `generate_patch_prs()` | 혼합 (패치가능 2 + 불가 1 + 오탐 2) | 5개 analysis_results | PatchPR 2건 생성, manual_guide 1건, 오탐 2건 무시 |
| U-08 | `generate_patch_prs()` | 빈 analysis_results | [] | PatchPR 0건, GitHub API 호출 0회 |
| U-09 | `_build_pr_body()` | PR 본문 구조 확인 | vulnerability dict (모든 필드 채움) | "취약점 설명", "패치 내용", "참고 자료" 섹션 모두 포함, Vulnix 서명 포함 |
| U-10 | `_build_pr_body()` | 테스트 제안 포함 | test_suggestion="def test_..." | PR 본문에 "테스트 제안" 섹션 + 코드 블록 포함 |
| U-11 | `_build_pr_body()` | 테스트 제안 없음 | test_suggestion=None | PR 본문에 "테스트 제안" 섹션 없음 |
| U-12 | `_apply_patch_diff()` | 정상 diff 적용 | 원본 파일 + 유효한 unified diff | 수정된 파일 내용 반환, diff의 +/- 라인 정확히 적용 |
| U-13 | `_apply_patch_diff()` | 잘못된 diff (context mismatch) | 원본과 불일치하는 diff | None 반환 (패치 불가 전환) |

### GitHubAppService (추가 메서드)

| # | 대상 메서드 | 시나리오 | 입력 | 예상 결과 |
|---|-------------|----------|------|-----------|
| U-14 | `create_branch()` | 정상 브랜치 생성 | full_name, branch_name, base_sha | POST /git/refs 호출, 201 응답 |
| U-15 | `create_branch()` | 이미 존재하는 브랜치 | 동일 branch_name | 422 에러 처리 후 기존 브랜치 삭제 + 재생성, 또는 경고 로그 |
| U-16 | `get_file_content()` | 정상 파일 조회 | file_path, ref | (파일 내용 문자열, blob SHA) 튜플 반환 |
| U-17 | `get_file_content()` | 존재하지 않는 파일 | 잘못된 file_path | 404 에러 -> 적절한 예외 발생 |
| U-18 | `create_file_commit()` | 정상 커밋 | branch, file_path, content, file_sha | PUT /contents/{path} 호출, content base64 인코딩 확인 |
| U-19 | `create_pull_request()` | 정상 PR 생성 | head, base, title, body | POST /pulls 호출, {"number": int, "html_url": str} 반환 |
| U-20 | `create_pull_request()` | PR 생성 실패 (base와 head 동일) | 변경사항 없는 브랜치 | 422 에러 -> 적절한 예외 발생 |

### LLMAgent (프롬프트 개선)

| # | 대상 메서드 | 시나리오 | 입력 | 예상 결과 |
|---|-------------|----------|------|-----------|
| U-21 | `_generate_patch()` | 패치 가능 응답 파싱 | LLM이 patchable=true 응답 | patch_diff 문자열 반환, test_suggestion 포함 |
| U-22 | `_generate_patch()` | 패치 불가 응답 파싱 | LLM이 patchable=false 응답 | patch_diff=None, manual_guide 문자열 반환 |
| U-23 | `_build_patch_prompt()` | 프롬프트에 테스트 제안 요청 포함 확인 | finding, file_content | 프롬프트에 "test_suggestion" 키워드 포함 |
| U-24 | `_build_patch_prompt()` | 프롬프트에 패치 불가 판단 요청 포함 확인 | finding, file_content | 프롬프트에 "patchable" 키워드 포함 |

---

## 통합 테스트

### scan_worker 파이프라인 통합

| # | 시나리오 | 입력 | 예상 결과 |
|---|----------|------|-----------|
| I-01 | 전체 파이프라인 (패치 PR 생성 포함) | ScanJobMessage + Semgrep findings 2건 (TP) | Vulnerability 2건 + PatchPR 2건 DB 저장, ScanJob status=completed |
| I-02 | LLM 분석 -> 패치 불가 -> manual_guide 저장 | Semgrep finding 1건 (TP, diff=None) | Vulnerability 1건 (manual_guide 필드 채워짐), PatchPR 0건 |
| I-03 | 패치 PR 생성 실패 시 스캔 completed 유지 | GitHub API PR 생성 500 에러 mock | ScanJob status=completed (패치 실패해도 스캔은 성공), 경고 로그 기록 |
| I-04 | findings 0건 -> 패치 생성 스킵 | Semgrep 결과 없음 | LLM 호출 0회, PatchPR 0건, ScanJob status=completed |

### API 통합 테스트

| # | API | 시나리오 | 입력 | 예상 결과 |
|---|-----|----------|------|-----------|
| I-05 | `GET /api/v1/patches` | 인증된 사용자 목록 조회 | Bearer JWT + page=1 | 200, PaginatedResponse, 본인 팀 패치만 반환 |
| I-06 | `GET /api/v1/patches` | status 필터 | status=merged | 200, status="merged"인 항목만 반환 |
| I-07 | `GET /api/v1/patches` | repo_id 필터 | repo_id=uuid | 200, 해당 저장소 패치만 반환 |
| I-08 | `GET /api/v1/patches` | 미인증 요청 | Authorization 헤더 없음 | 401 Unauthorized |
| I-09 | `GET /api/v1/patches` | 다른 팀 저장소 조회 | 다른 팀의 repo_id | 200, 빈 목록 (필터링으로 자동 제외) |
| I-10 | `GET /api/v1/patches/{id}` | 정상 상세 조회 | 유효한 patch_id | 200, PatchPRDetailResponse + vulnerability 포함 |
| I-11 | `GET /api/v1/patches/{id}` | 존재하지 않는 ID | 잘못된 patch_id | 404 Not Found |
| I-12 | `GET /api/v1/patches/{id}` | 미인증 요청 | Authorization 헤더 없음 | 401 Unauthorized |
| I-13 | `GET /api/v1/patches/{id}` | 다른 팀 패치 조회 | 다른 팀의 patch_id | 403 Forbidden |

---

## 경계 조건 / 에러 케이스

### PatchGenerator 경계 조건

| # | 시나리오 | 예상 동작 |
|---|----------|-----------|
| E-01 | 동일 취약점에 대해 PatchPR이 이미 존재 | 중복 생성 방지 (vulnerability_id UNIQUE 제약 위반 시 스킵 + 경고 로그) |
| E-02 | GitHub API rate limit 도달 | 지수 백오프 재시도 (2초, 4초, 8초), 3회 실패 시 해당 PR 스킵 |
| E-03 | 매우 긴 patch_diff (10,000줄 이상) | Contents API body size 제한 확인, 초과 시 패치 불가 처리 |
| E-04 | 바이너리 파일에 대한 패치 시도 | get_file_content에서 base64 디코딩 실패 -> 패치 불가 처리 |
| E-05 | 브랜치명이 Git 제한(255자) 초과 | vulnerability_type 길이 제한 (최대 50자로 truncate) |
| E-06 | 동시에 같은 저장소에 10개 이상 PR 생성 | Semaphore(3)으로 동시성 제한, 순차적으로 처리 |
| E-07 | Installation token 만료 중 PR 생성 | get_installation_token 캐시 갱신 로직으로 자동 처리 |

### LLM 응답 경계 조건

| # | 시나리오 | 예상 동작 |
|---|----------|-----------|
| E-08 | LLM이 유효하지 않은 diff 형식 반환 | _apply_patch_diff에서 파싱 실패 -> 패치 불가 처리 (manual_guide 저장) |
| E-09 | LLM이 JSON 아닌 응답 반환 | _strip_json_wrapper + json.loads 실패 -> patch_diff=None, 경고 로그 |
| E-10 | LLM 응답에 patchable 필드 누락 | 기본값 True로 처리, patch_diff가 None이면 패치 불가로 판단 |
| E-11 | LLM API 타임아웃 | 기존 _call_claude_with_retry 재시도 로직 활용 (3회), 실패 시 패치 불가 |

### DB 경계 조건

| # | 시나리오 | 예상 동작 |
|---|----------|-----------|
| E-12 | PatchPR INSERT 시 DB 연결 끊김 | 트랜잭션 롤백, 스캔은 completed 처리 (패치만 실패) |
| E-13 | patch_diff 컬럼에 매우 큰 텍스트 (1MB 이상) | TEXT 타입이므로 저장 가능하나, API 응답 시 페이로드 크기 확인 필요 |

---

## 성능 테스트

| # | 시나리오 | 측정 기준 | 목표 |
|---|----------|-----------|------|
| P-01 | 취약점 1건 패치 PR 생성 소요 시간 | GitHub API 모의 호출 포함 end-to-end | 30초 이내 (인수조건) |
| P-02 | 취약점 10건 병렬 PR 생성 소요 시간 | Semaphore(3) 동시성 제한 하에서 | 120초 이내 (4배치 x 30초) |
| P-03 | PatchPR 목록 API 응답 시간 | 1,000건 데이터에서 페이지네이션 조회 | 200ms 이내 |

---

## 인수조건 매핑

각 인수조건이 어떤 테스트 케이스로 검증되는지 매핑.

| 인수조건 | 테스트 케이스 |
|----------|--------------|
| 탐지된 취약점별 LLM이 패치 코드 자동 생성 | U-04, U-21, I-01 |
| 기존 코드 스타일/네이밍 컨벤션 유지 | U-23 (프롬프트에 스타일 유지 지시 포함 확인) |
| 패치 PR에 변경 코드 diff 포함 | U-09, I-10 |
| 패치 PR에 취약점 설명 (왜 위험한가) 포함 | U-09 |
| 패치 PR에 패치 설명 (무엇을 어떻게 고쳤는가) 포함 | U-09 |
| 패치 PR에 참고 링크 (CVE, OWASP) 포함 | U-09 |
| 패치 PR에 테스트 코드 제안 포함 (선택적) | U-10, U-11, U-21 |
| 패치 불가능한 경우 수동 수정 가이드 + 우선순위 제공 | U-05, U-22, I-02 |
| 취약점 1건당 패치 PR 생성 30초 이내 | P-01 |
| 패치 PR 승인율 40% 이상 (PoC 기준) | 수동 검증 (파일럿 고객 피드백 기반 측정) |

---

## 테스트 인프라 요구사항

### Mock 대상

| 대상 | Mock 방식 | 이유 |
|------|-----------|------|
| GitHub API | `httpx.AsyncClient` 응답 Mock (`respx` 라이브러리) | 실제 GitHub API 호출 방지 |
| Claude API | `anthropic.AsyncAnthropic._client` Mock | 실제 LLM 호출 방지, 비용 절약 |
| DB | `pytest-asyncio` + 테스트 DB (SQLite in-memory 또는 테스트용 PostgreSQL) | 격리된 테스트 환경 |

### 테스트 픽스처

| 픽스처 | 내용 |
|--------|------|
| `sample_analysis_results` | LLMAnalysisResult 5건 (TP 패치가능 2, TP 패치불가 1, FP 2) |
| `sample_findings` | SemgrepFinding 5건 (위 결과와 매칭) |
| `mock_github_service` | GitHubAppService 전체 Mock (모든 API 호출 성공 응답) |
| `sample_vulnerability` | Vulnerability ORM 객체 (테스트용) |
| `sample_patch_pr` | PatchPR ORM 객체 (테스트용) |
| `authenticated_client` | JWT 토큰이 포함된 httpx.AsyncClient (API 테스트용) |
