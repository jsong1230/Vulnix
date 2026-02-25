# F-04: 스캔 결과 API 및 기본 UI -- 테스트 명세

**버전**: v1.0
**작성일**: 2026-02-25

---

## 참조

- 설계서: `docs/specs/F-04-scan-results-ui/design.md`
- 인수조건: `docs/project/features.md` #F-04

---

## 1. 단위 테스트 (Backend)

### 1-1. 보안 점수 계산 서비스

**대상**: `backend/src/services/security_score.py`

| # | 시나리오 | 입력 | 예상 결과 |
|---|----------|------|-----------|
| U-01 | 취약점 없는 저장소 점수 | 빈 취약점 목록 | score = 100.00 |
| U-02 | 모든 취약점이 open인 경우 | open: critical 1, high 2 | score = 0.00 |
| U-03 | 전부 해결된 경우 | patched: critical 1, high 2 | score = 100.00 |
| U-04 | 혼합 상태 점수 계산 | open: high 1(w=5), patched: critical 1(w=10), medium 1(w=2) | open_weighted=5, total_weighted=17, score=(1-5/17)*100=70.59 |
| U-05 | false_positive는 해결로 간주 | false_positive: critical 1, open: low 1 | open_weighted=1, total_weighted=11, score=(1-1/11)*100=90.91 |
| U-06 | ignored는 해결로 간주 | ignored: high 1, open: medium 1 | open_weighted=2, total_weighted=7, score=(1-2/7)*100=71.43 |
| U-07 | 심각도별 가중치 정확성 | critical=10, high=5, medium=2, low=1 각 1건 open | total_weighted=18, score=0.00 |

### 1-2. 대시보드 요약 집계 로직

**대상**: `backend/src/api/v1/dashboard.py` (집계 로직 부분)

| # | 시나리오 | 입력 | 예상 결과 |
|---|----------|------|-----------|
| U-08 | resolution_rate 계산 (정상) | total=10, patched=3, false_positive=2 | rate = 50.0 |
| U-09 | resolution_rate 취약점 0건 | total=0 | rate = 0.0 (ZeroDivisionError 방지) |
| U-10 | severity_distribution 집계 | critical 2, high 3, medium 5, low 0 | {"critical": 2, "high": 3, "medium": 5, "low": 0} |
| U-11 | status_distribution 집계 | open 5, patched 3, ignored 1, false_positive 1 | {"open": 5, "patched": 3, "ignored": 1, "false_positive": 1} |
| U-12 | recent_scans 최대 5건 제한 | 스캔 10건 존재 | 최근 5건만 반환, created_at DESC 정렬 |

### 1-3. 취약점 상태 변경 로직

**대상**: `backend/src/api/v1/vulns.py` (update_vulnerability_status)

| # | 시나리오 | 입력 | 예상 결과 |
|---|----------|------|-----------|
| U-13 | open -> false_positive | status="false_positive", reason="테스트 코드" | resolved_at 자동 설정 (not None) |
| U-14 | open -> ignored | status="ignored" | resolved_at 자동 설정 |
| U-15 | open -> patched | status="patched" | resolved_at 자동 설정 |
| U-16 | false_positive -> open (복원) | status="open" | resolved_at = None으로 리셋 |
| U-17 | ignored -> open (복원) | status="open" | resolved_at = None으로 리셋 |
| U-18 | reason 필드 저장 확인 | reason="사유 텍스트" | 사유가 DB에 저장됨 |

### 1-4. 권한 확인 헬퍼

**대상**: `backend/src/api/deps.py` (verify_repo_access)

| # | 시나리오 | 입력 | 예상 결과 |
|---|----------|------|-----------|
| U-19 | 존재하지 않는 repo_id | 잘못된 UUID | HTTPException 404 |
| U-20 | 팀 멤버가 아닌 사용자 | 다른 팀의 저장소 ID | HTTPException 403 |
| U-21 | 팀 멤버인 사용자 | 자기 팀 저장소 ID | Repository 객체 반환 |

### 1-5. 패치 diff 파싱 (프론트엔드)

**대상**: `frontend/src/components/vulnerability/patch-diff-viewer.tsx`

| # | 시나리오 | 입력 | 예상 결과 |
|---|----------|------|-----------|
| U-22 | 추가 줄 스타일링 | "+added line" | bg-green 클래스 적용 |
| U-23 | 삭제 줄 스타일링 | "-deleted line" | bg-red 클래스 적용 |
| U-24 | 헤더 줄 스타일링 | "@@ -1,3 +1,4 @@" | text-blue 클래스 적용 |
| U-25 | 일반 줄 스타일링 | " unchanged line" | text-gray 클래스 적용 |
| U-26 | 빈 diff 처리 | null 또는 "" | "패치 diff가 없습니다" 메시지 표시 |

### 1-6. 코드 뷰어 줄 번호

**대상**: `frontend/src/components/vulnerability/code-viewer.tsx`

| # | 시나리오 | 입력 | 예상 결과 |
|---|----------|------|-----------|
| U-27 | 줄 번호 시작값 | startLine=42, 코드 3줄 | 줄 번호 42, 43, 44 표시 |
| U-28 | 취약 라인 하이라이트 | highlightStart=42, highlightEnd=44 | 해당 줄에 bg-red 배경 적용 |
| U-29 | 빈 코드 스니펫 | codeSnippet=null | "코드 스니펫이 없습니다" 표시 |

---

## 2. 통합 테스트 (Backend API)

### 2-1. GET /api/v1/scans/{scan_id}

**파일**: `backend/tests/api/v1/test_scans.py`

| # | 시나리오 | 입력 | 예상 결과 |
|---|----------|------|-----------|
| I-01 | 정상 조회 (completed) | 유효한 scan_id, 인증된 팀 멤버 | 200, ScanJobResponse 반환 |
| I-02 | 정상 조회 (queued) | queued 상태 스캔 | 200, status="queued" |
| I-03 | 정상 조회 (failed) | failed 상태 스캔 | 200, status="failed", error_message 포함 |
| I-04 | 존재하지 않는 scan_id | 잘못된 UUID | 404, "스캔을 찾을 수 없습니다" |
| I-05 | 인증 없이 요청 | Authorization 헤더 없음 | 401 |
| I-06 | 다른 팀의 스캔 조회 | 접근 권한 없는 scan_id | 403, "이 스캔에 접근할 권한이 없습니다" |

### 2-2. GET /api/v1/vulnerabilities

**파일**: `backend/tests/api/v1/test_vulns.py`

| # | 시나리오 | 입력 | 예상 결과 |
|---|----------|------|-----------|
| I-07 | 필터 없이 전체 조회 | page=1, per_page=20 | 200, 팀 소속 저장소 취약점 목록, meta.total 정확 |
| I-08 | status 필터 | status=open | 200, open 상태 취약점만 반환 |
| I-09 | severity 필터 | severity=critical | 200, critical 취약점만 반환 |
| I-10 | repo_id 필터 | repo_id=유효한 UUID | 200, 해당 저장소 취약점만 반환 |
| I-11 | 복합 필터 | status=open, severity=high | 200, 두 조건 모두 충족하는 취약점만 반환 |
| I-12 | 페이지네이션 2페이지 | page=2, per_page=5, 총 12건 | 200, data 5건, meta.total=12, meta.total_pages=3 |
| I-13 | 빈 결과 | 취약점 0건인 팀 | 200, data=[], meta.total=0 |
| I-14 | 정렬 확인 | 여러 취약점 | detected_at DESC 순서로 정렬됨 |
| I-15 | 잘못된 status 값 | status=invalid | 422 Validation Error |
| I-16 | per_page 최대값 초과 | per_page=200 | 422 (per_page le=100 제약) |
| I-17 | 인증 없이 요청 | Authorization 헤더 없음 | 401 |

### 2-3. GET /api/v1/vulnerabilities/{vuln_id}

**파일**: `backend/tests/api/v1/test_vulns.py`

| # | 시나리오 | 입력 | 예상 결과 |
|---|----------|------|-----------|
| I-18 | 정상 조회 (패치 PR 있음) | 패치 PR이 연결된 취약점 | 200, patch_pr 필드에 PR 정보 포함 |
| I-19 | 정상 조회 (패치 PR 없음) | 패치 PR 없는 취약점 | 200, patch_pr = null |
| I-20 | repo_full_name 포함 확인 | 정상 요청 | 200, repo_full_name 필드에 "org/repo" 형식 포함 |
| I-21 | 모든 필드 반환 확인 | 정상 요청 | code_snippet, description, llm_reasoning, llm_confidence, references 포함 |
| I-22 | 존재하지 않는 vuln_id | 잘못된 UUID | 404 |
| I-23 | 다른 팀의 취약점 조회 | 접근 권한 없는 vuln_id | 403 |
| I-24 | 인증 없이 요청 | Authorization 헤더 없음 | 401 |

### 2-4. PATCH /api/v1/vulnerabilities/{vuln_id}

**파일**: `backend/tests/api/v1/test_vulns.py`

| # | 시나리오 | 입력 | 예상 결과 |
|---|----------|------|-----------|
| I-25 | open -> false_positive | status="false_positive", reason="테스트" | 200, status 변경, resolved_at 설정 |
| I-26 | open -> ignored | status="ignored" | 200, status 변경, resolved_at 설정 |
| I-27 | open -> patched | status="patched" | 200, status 변경, resolved_at 설정 |
| I-28 | false_positive -> open | status="open" | 200, resolved_at = null |
| I-29 | reason 없이 변경 | status="ignored", reason 생략 | 200, 정상 처리 (reason은 optional) |
| I-30 | 보안 점수 재계산 확인 | open -> patched 변경 후 | Repository.security_score 값 업데이트됨 |
| I-31 | 존재하지 않는 vuln_id | 잘못된 UUID | 404 |
| I-32 | 다른 팀의 취약점 변경 | 접근 권한 없는 vuln_id | 403 |
| I-33 | 잘못된 status 값 | status="unknown" | 422 |
| I-34 | reason 최대 길이 초과 | reason=501자 문자열 | 422 |

### 2-5. GET /api/v1/dashboard/summary

**파일**: `backend/tests/api/v1/test_dashboard.py`

| # | 시나리오 | 입력 | 예상 결과 |
|---|----------|------|-----------|
| I-35 | 정상 조회 (데이터 있음) | 취약점 + 스캔 데이터 존재 | 200, severity/status distribution, resolution_rate, recent_scans 포함 |
| I-36 | 데이터 없는 팀 | 취약점 0건, 스캔 0건 | 200, total_vulnerabilities=0, resolution_rate=0, recent_scans=[], repo_count=0 |
| I-37 | Redis 캐시 히트 | 5분 이내 재요청 | 200, DB 쿼리 없이 캐시에서 반환 (응답 시간 단축) |
| I-38 | severity_distribution 정확성 | critical 2, high 3, medium 5, low 1 | 각 수치 정확히 반환 |
| I-39 | resolution_rate 정확성 | total=10, patched=3, false_positive=2 | rate=50.0 |
| I-40 | recent_scans 최대 5건 | 스캔 10건 | 5건만 반환, 최신순 |
| I-41 | recent_scans에 repo_full_name 포함 | 스캔 데이터 존재 | 각 항목에 repo_full_name 포함 |
| I-42 | 인증 없이 요청 | Authorization 헤더 없음 | 401 |

### 2-6. GET /api/v1/repos/{repo_id}/scans

**파일**: `backend/tests/api/v1/test_repos.py`

| # | 시나리오 | 입력 | 예상 결과 |
|---|----------|------|-----------|
| I-43 | 정상 조회 | 스캔 히스토리 있는 저장소 | 200, ScanJobResponse 목록, 최신순 정렬 |
| I-44 | 페이지네이션 | page=2, per_page=5 | 200, 올바른 페이지 데이터 |
| I-45 | 스캔 없는 저장소 | 스캔 0건 | 200, data=[], meta.total=0 |
| I-46 | 존재하지 않는 repo_id | 잘못된 UUID | 404 |
| I-47 | 다른 팀의 저장소 | 접근 권한 없는 repo_id | 403 |

### 2-7. GET /api/v1/repos/{repo_id}/vulnerabilities

**파일**: `backend/tests/api/v1/test_repos.py`

| # | 시나리오 | 입력 | 예상 결과 |
|---|----------|------|-----------|
| I-48 | 정상 조회 | 취약점 있는 저장소 | 200, VulnerabilitySummary 목록 |
| I-49 | status 필터 | status=open | 200, open 취약점만 |
| I-50 | severity 필터 | severity=critical | 200, critical만 |
| I-51 | 취약점 없는 저장소 | 취약점 0건 | 200, data=[] |
| I-52 | 존재하지 않는 repo_id | 잘못된 UUID | 404 |
| I-53 | 다른 팀의 저장소 | 접근 권한 없는 repo_id | 403 |

---

## 3. E2E 테스트 (Playwright)

**파일**: `frontend/tests/e2e/f04-scan-results.spec.ts`

### 3-1. 대시보드 페이지

| # | 시나리오 | 사전 조건 | 검증 |
|---|----------|-----------|------|
| E-01 | 대시보드 로딩 | 인증된 사용자, 취약점 데이터 존재 | 요약 카드 4개 표시 (전체 취약점, 미해결, 해결률, 연동 저장소) |
| E-02 | 최근 취약점 목록 클릭 | 대시보드에 취약점 목록 표시 | 항목 클릭 시 /vulnerabilities/{id}로 이동 |
| E-03 | 최근 스캔 기록 표시 | 스캔 데이터 존재 | 최대 5건 표시, 상태 배지 포함 |
| E-04 | 빈 대시보드 | 데이터 없는 새 사용자 | "탐지된 취약점이 없습니다", "스캔 기록이 없습니다" 메시지 표시 |

### 3-2. 취약점 상세 페이지

| # | 시나리오 | 사전 조건 | 검증 |
|---|----------|-----------|------|
| E-05 | 취약점 상세 표시 | /vulnerabilities/{id} 접속 | SeverityBadge, CWE ID, OWASP 분류, 파일 경로, 코드 스니펫 표시 |
| E-06 | AI 분석 결과 표시 | 취약점 데이터 존재 | 탐지 확신도 프로그레스 바, 판단 근거, 참고 자료 표시 |
| E-07 | 패치 diff 표시 | patch_pr이 있는 취약점 | diff 뷰어에 +/- 줄 색상 구분, PR 링크 표시 |
| E-08 | 패치 없는 경우 | patch_pr이 없는 취약점 | "패치 코드 생성 대기 중" 메시지 표시 |
| E-09 | 오탐 마킹 | "오탐으로 표시" 버튼 클릭 | 확인 다이얼로그 -> 상태 변경 -> UI 반영 |
| E-10 | 무시 마킹 | "무시" 버튼 클릭 | 상태 "ignored"로 변경 |
| E-11 | 브레드크럼 네비게이션 | 브레드크럼 "저장소" 클릭 | /repos 페이지로 이동 |

### 3-3. 스캔 상세 페이지

| # | 시나리오 | 사전 조건 | 검증 |
|---|----------|-----------|------|
| E-12 | 대기 중 상태 표시 | queued 상태 스캔 | "스캔 대기 중..." 메시지, 로딩 스피너 |
| E-13 | 스캔 중 상태 폴링 | running 상태 스캔 | "Semgrep + Claude AI 분석 중..." 표시, 상태 자동 업데이트 |
| E-14 | 완료 후 통계 표시 | completed 상태 스캔 | 전체 탐지, 실제 취약점, 오탐 수 표시 |
| E-15 | 실패 시 에러 표시 | failed 상태 스캔 | 에러 메시지 표시 (pre 태그) |
| E-16 | 취약점 목록에서 상세 이동 | 완료 스캔의 취약점 항목 클릭 | /vulnerabilities/{id}로 이동 |

### 3-4. 수동 스캔 트리거

| # | 시나리오 | 사전 조건 | 검증 |
|---|----------|-----------|------|
| E-17 | 수동 스캔 성공 | 저장소 상세 페이지에서 "수동 스캔" 클릭 | 스캔 상세 페이지로 이동, queued 상태 표시 |
| E-18 | 이미 스캔 진행 중 | 동일 저장소에 running 스캔 존재 | "이미 스캔이 진행 중입니다" 에러 |

---

## 4. 경계 조건 / 에러 케이스

### 4-1. 데이터 경계

| # | 케이스 | 검증 내용 |
|---|--------|-----------|
| B-01 | 매우 긴 코드 스니펫 | code_snippet이 1000줄인 경우에도 렌더링 정상 동작 (overflow-x-auto) |
| B-02 | 특수 문자 포함 코드 | HTML 태그(`<script>`)가 포함된 코드 스니펫이 이스케이프되어 표시 |
| B-03 | 유니코드 파일 경로 | 한글/일본어 포함 파일 경로 정상 표시 |
| B-04 | references가 null | references 필드가 null인 취약점 상세 조회 시 참고 자료 섹션 미표시 |
| B-05 | llm_confidence가 null | LLM 분석 전 취약점 (Semgrep만 탐지) 상세 조회 시 확신도 바 미표시 또는 0% |
| B-06 | 동시 상태 변경 | 두 사용자가 동시에 같은 취약점 상태 변경 시 마지막 변경이 적용 (last-write-wins) |

### 4-2. 네트워크/인프라 경계

| # | 케이스 | 검증 내용 |
|---|--------|-----------|
| B-07 | Redis 연결 실패 | 대시보드 캐시 Redis 불가 시 DB 직접 조회로 fallback |
| B-08 | API 타임아웃 | 30초 이상 응답 지연 시 프론트엔드에서 에러 메시지 표시 |
| B-09 | 폴링 중 네트워크 단절 | 스캔 폴링 중 네트워크 끊김 시 React Query 자동 재시도 (3회) |

### 4-3. 인증/인가 경계

| # | 케이스 | 검증 내용 |
|---|--------|-----------|
| B-10 | JWT 만료 중 폴링 | 스캔 폴링 중 JWT 만료 시 401 -> 로그인 페이지 리다이렉트 |
| B-11 | 팀에서 제거된 사용자 | 조회 중 팀 멤버십이 삭제된 경우 403 응답 |
| B-12 | 삭제된 저장소의 스캔 조회 | 저장소 삭제 후 해당 스캔 조회 시 404 (CASCADE 삭제) |

---

## 5. 테스트 인프라 요구사항

### 5-1. Backend 테스트 픽스처

```python
# conftest.py에 추가 필요한 픽스처

@pytest.fixture
async def sample_scan_completed(db, sample_repo):
    """완료된 스캔 작업 (취약점 포함)"""

@pytest.fixture
async def sample_scan_queued(db, sample_repo):
    """대기 중인 스캔 작업"""

@pytest.fixture
async def sample_vulnerabilities(db, sample_scan_completed, sample_repo):
    """다양한 상태/심각도의 취약점 세트 (10건)"""

@pytest.fixture
async def sample_vulnerability_with_patch(db, sample_vulnerabilities):
    """패치 PR이 연결된 취약점"""

@pytest.fixture
async def other_team_repo(db):
    """다른 팀의 저장소 (권한 테스트용)"""
```

### 5-2. Frontend 테스트 Mock

```typescript
// MSW (Mock Service Worker) 핸들러

// GET /api/v1/dashboard/summary -> DashboardSummary mock
// GET /api/v1/vulnerabilities -> PaginatedResponse<VulnerabilitySummary> mock
// GET /api/v1/vulnerabilities/:id -> ApiResponse<VulnerabilityResponse> mock
// PATCH /api/v1/vulnerabilities/:id -> ApiResponse<VulnerabilityResponse> mock
// GET /api/v1/scans/:id -> ApiResponse<ScanJobResponse> mock (상태별 분기)
// POST /api/v1/scans -> ApiResponse<ScanJobResponse> mock
```

### 5-3. E2E 테스트 시드 데이터

Playwright E2E 테스트를 위해 다음 시드 데이터가 DB에 존재해야 한다:

- 테스트 사용자 1명 (GitHub OAuth mock)
- 팀 1개 + 팀 멤버 (테스트 사용자)
- 저장소 2개 (활성 1, 비활성 1)
- 완료된 스캔 3건 (취약점 포함)
- 대기 중 스캔 1건
- 취약점 10건 (severity, status 혼합)
- 패치 PR 2건

---

## 변경 이력

| 날짜 | 변경 내용 | 이유 |
|------|-----------|------|
| 2026-02-25 | 초안 작성 | F-04 테스트 명세 |
