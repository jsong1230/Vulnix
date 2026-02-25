# Vulnix 사용자 매뉴얼

**버전**: 1.0
**최종 업데이트**: 2026년 2월

---

## 목차

1. [시작하기](#1-시작하기)
2. [저장소 연동](#2-저장소-연동)
3. [보안 스캔](#3-보안-스캔)
4. [취약점 관리](#4-취약점-관리)
5. [자동 패치 PR](#5-자동-패치-pr)
6. [보안 대시보드](#6-보안-대시보드)
7. [오탐 관리](#7-오탐-관리)
8. [알림 설정](#8-알림-설정)
9. [CISO 리포트](#9-ciso-리포트)
10. [VS Code 익스텐션](#10-vs-code-익스텐션)
11. [API Key 관리](#11-api-key-관리)
12. [문제 해결](#12-문제-해결)

---

## 1. 시작하기

### 1.1 Vulnix란?

Vulnix는 코드 저장소를 연동하면 AI가 보안 취약점을 자동으로 탐지하고, 패치 PR까지 생성해주는 개발자용 보안 에이전트 SaaS입니다.

**핵심 기능:**
- Semgrep(룰 기반) + Claude AI(LLM 기반) 2단계 탐지 엔진으로 오탐률 최소화
- PR 생성 또는 브랜치 푸시 시 자동 스캔 실행 (수분 내 결과 제공)
- 취약점별 패치 코드 자동 생성 및 PR 제출
- OWASP Top 10 기준 취약점 분류 및 CWE 매핑
- 팀/저장소별 보안 점수 실시간 추적
- Slack, Microsoft Teams 알림 연동
- CSAP / ISO 27001 / ISMS 인증용 CISO 리포트 PDF 자동 생성
- VS Code 익스텐션으로 코드 작성 중 실시간 취약점 하이라이팅

**지원 언어:** Python, JavaScript, TypeScript, Java, Go

---

### 1.2 회원가입 및 로그인 (GitHub OAuth)

Vulnix는 별도의 계정 생성 없이 GitHub 계정으로 바로 로그인합니다.

**로그인 절차:**

1. `https://app.vulnix.dev` 에 접속합니다.
2. 메인 화면에서 **"GitHub으로 로그인"** 버튼을 클릭합니다.
3. GitHub OAuth 인증 페이지로 리다이렉트됩니다.
4. GitHub에서 Vulnix 앱의 권한 요청을 검토하고 **"Authorize vulnix"** 를 클릭합니다.
5. 인증 완료 후 Vulnix 대시보드로 자동 이동합니다.

> **참고:** 처음 로그인하면 자동으로 개인 팀(Personal Team)이 생성됩니다. 팀원을 초대하려면 설정 > 팀 관리에서 이메일로 초대하세요.

**API 직접 호출 (참고용):**
```bash
# GitHub OAuth 코드를 받아 JWT 토큰 교환
curl -X POST https://api.vulnix.dev/api/v1/auth/github \
  -H "Content-Type: application/json" \
  -d '{"code": "github_oauth_code_here"}'
```

---

### 1.3 첫 번째 저장소 연동 방법 (GitHub)

로그인 후 대시보드에 처음 진입하면 저장소 연동 안내 화면이 표시됩니다.

**GitHub 저장소 연동 절차:**

1. 대시보드 상단의 **"저장소 추가"** 버튼을 클릭합니다.
2. **"GitHub"** 탭을 선택합니다.
3. **"GitHub App 설치"** 버튼을 클릭하면 GitHub 앱 설치 페이지로 이동합니다.
4. 분석할 저장소(또는 모든 저장소)를 선택하고 **"Install"** 을 클릭합니다.
5. Vulnix로 돌아오면 접근 가능한 저장소 목록이 표시됩니다.
6. 연동할 저장소 옆의 **"연동"** 버튼을 클릭합니다.
7. 저장소가 등록되면 초기 전체 스캔이 자동으로 시작됩니다.

> **팁:** 초기 스캔은 저장소 크기에 따라 5~15분 소요될 수 있습니다. 스캔 진행 상태는 대시보드 > 스캔 이력에서 확인할 수 있습니다.

---

## 2. 저장소 연동

### 2.1 GitHub 저장소 연동

GitHub App 방식으로 연동하며, OAuth 토큰이 아닌 Installation Token을 사용하므로 토큰 만료 걱정 없이 안정적으로 운영됩니다.

**연동 절차:**
1. 대시보드 좌측 메뉴에서 **저장소** 를 클릭합니다.
2. 우측 상단의 **"저장소 추가"** 버튼을 클릭합니다.
3. GitHub 탭에서 **"GitHub App 설치"** 를 클릭합니다.
4. GitHub 앱 설치 후 저장소 목록에서 원하는 저장소를 선택하여 **"연동"** 을 클릭합니다.

**API 예시:**
```bash
# 연동된 저장소 목록 조회
curl -X GET "https://api.vulnix.dev/api/v1/repos?platform=github" \
  -H "Authorization: Bearer {JWT_TOKEN}"

# 저장소 연동 등록
curl -X POST "https://api.vulnix.dev/api/v1/repos" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "github_repo_id": 123456789,
    "full_name": "my-org/my-repo",
    "default_branch": "main",
    "language": "Python",
    "installation_id": 987654
  }'
```

---

### 2.2 GitLab 저장소 연동 (PAT 입력)

GitLab은 Personal Access Token(PAT)을 사용하여 연동합니다. PAT는 암호화되어 저장됩니다.

**PAT 발급 방법:**
1. GitLab 계정 설정 > Access Tokens로 이동합니다.
2. Token name을 입력하고 `read_repository`, `write_repository`, `api` 스코프를 선택합니다.
3. 만료일을 설정하고 **"Create personal access token"** 을 클릭합니다.
4. 발급된 토큰을 복사합니다 (이후 다시 확인 불가).

**Vulnix에서 연동 절차:**
1. 저장소 추가 > **GitLab** 탭을 선택합니다.
2. **GitLab 인스턴스 URL** (예: `https://gitlab.com` 또는 자체 호스팅 URL)을 입력합니다.
3. 발급한 **Personal Access Token** 을 입력합니다.
4. **"프로젝트 목록 불러오기"** 를 클릭하면 접근 가능한 프로젝트 목록이 표시됩니다.
5. 연동할 프로젝트를 선택하고 **"연동"** 을 클릭합니다.

**API 예시:**
```bash
# GitLab 프로젝트 목록 조회
curl -X GET "https://api.vulnix.dev/api/v1/repos/gitlab/projects?access_token=glpat-xxxx&gitlab_url=https://gitlab.com" \
  -H "Authorization: Bearer {JWT_TOKEN}"

# GitLab 저장소 연동 등록
curl -X POST "https://api.vulnix.dev/api/v1/repos/gitlab" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "gitlab_project_id": 12345678,
    "full_name": "my-group/my-project",
    "default_branch": "main",
    "language": "Python",
    "gitlab_url": "https://gitlab.com",
    "access_token": "glpat-xxxxxxxxxxxx"
  }'
```

> **보안 안내:** PAT는 AES-256 암호화 후 DB에 저장됩니다. 화면에서는 절대 평문으로 표시되지 않습니다.

---

### 2.3 Bitbucket 저장소 연동 (App Password 입력)

Bitbucket은 App Password를 사용하여 연동합니다. 계정 비밀번호 대신 앱 전용 비밀번호를 사용하므로 보안에 안전합니다.

**App Password 발급 방법:**
1. Bitbucket 계정 설정 > App passwords로 이동합니다.
2. **"Create app password"** 를 클릭합니다.
3. Label을 입력하고 `Repositories: Read`, `Webhooks: Read and write` 권한을 체크합니다.
4. **"Create"** 를 클릭하고 발급된 App Password를 복사합니다.

**Vulnix에서 연동 절차:**
1. 저장소 추가 > **Bitbucket** 탭을 선택합니다.
2. **Bitbucket 사용자명** 과 **App Password** 를 입력합니다.
3. **Workspace 이름** 을 입력하고 **"저장소 목록 불러오기"** 를 클릭합니다.
4. 연동할 저장소를 선택하고 **"연동"** 을 클릭합니다.

**API 예시:**
```bash
# Bitbucket 저장소 목록 조회
curl -X GET "https://api.vulnix.dev/api/v1/repos/bitbucket/repositories?username=myuser&app_password=ATBB-xxxx&workspace=my-workspace" \
  -H "Authorization: Bearer {JWT_TOKEN}"

# Bitbucket 저장소 연동 등록
curl -X POST "https://api.vulnix.dev/api/v1/repos/bitbucket" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "workspace": "my-workspace",
    "repo_slug": "my-repo",
    "full_name": "my-workspace/my-repo",
    "default_branch": "main",
    "language": "JavaScript",
    "username": "myuser",
    "app_password": "ATBB-xxxxxxxxxxxx"
  }'
```

---

### 2.4 연동 해제

저장소 연동을 해제하면 해당 저장소의 모든 스캔 데이터와 취약점 정보가 함께 삭제됩니다. 이 작업은 되돌릴 수 없으니 신중하게 진행하세요.

**연동 해제 절차:**
1. 대시보드 > 저장소 목록에서 연동 해제할 저장소를 클릭합니다.
2. 저장소 상세 페이지 우측 상단의 **"더보기 (...)"** 메뉴를 클릭합니다.
3. **"연동 해제"** 를 선택합니다.
4. 확인 다이얼로그에서 저장소 이름을 입력하고 **"연동 해제"** 를 클릭합니다.

> **권한:** 연동 해제는 팀의 `owner` 또는 `admin` 역할을 가진 사용자만 가능합니다.

**API 예시:**
```bash
curl -X DELETE "https://api.vulnix.dev/api/v1/repos/{repo_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

## 3. 보안 스캔

### 3.1 자동 스캔 트리거 (PR 생성 / 브랜치 푸시)

저장소를 연동하면 GitHub/GitLab/Bitbucket Webhook이 자동으로 등록됩니다. 이후 다음 이벤트 발생 시 스캔이 자동으로 시작됩니다.

**자동 트리거 이벤트:**

| 플랫폼 | 트리거 이벤트 |
|---|---|
| GitHub | PR 생성, 브랜치 푸시, PR 업데이트 |
| GitLab | Push, Merge Request 생성/업데이트 |
| Bitbucket | Push, Pull Request 생성/업데이트 |

**스캔 흐름:**
1. 코드 변경 감지 (Webhook 수신)
2. 변경된 파일 추출
3. Semgrep 정적 분석 실행 (룰 기반 1차 탐지)
4. Claude AI 분석 실행 (LLM 기반 2차 검증 및 오탐 필터링)
5. 취약점 저장 및 심각도 분류
6. 패치 코드 생성 및 PR 제출
7. Slack/Teams 알림 발송 (설정된 경우)

---

### 3.2 수동 스캔 실행

언제든지 저장소를 수동으로 스캔할 수 있습니다.

**UI에서 수동 스캔:**
1. 대시보드 > 저장소 목록에서 스캔할 저장소를 선택합니다.
2. 저장소 상세 페이지에서 **"지금 스캔"** 버튼을 클릭합니다.
3. 스캔할 브랜치를 선택하고 **"스캔 시작"** 을 클릭합니다.

**API 예시:**
```bash
# 수동 스캔 트리거
curl -X POST "https://api.vulnix.dev/api/v1/scans" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "branch": "main",
    "commit_sha": "abc123def456"
  }'

# 응답 예시
{
  "success": true,
  "data": {
    "id": "scan-job-uuid",
    "status": "queued",
    "repo_id": "repo-uuid",
    "trigger": "manual",
    "branch": "main",
    "created_at": "2026-02-26T10:00:00Z"
  }
}
```

> **참고:** 이미 진행 중인 스캔이 있으면 새 스캔은 시작되지 않습니다 (409 Conflict 응답).

---

### 3.3 스캔 진행 상태 확인

**UI에서 확인:**
1. 대시보드 좌측 메뉴에서 **스캔** 을 클릭합니다.
2. 스캔 목록에서 각 스캔의 상태를 확인합니다.

**스캔 상태 종류:**

| 상태 | 설명 |
|---|---|
| `queued` | 스캔 대기 중 |
| `running` | 스캔 진행 중 |
| `completed` | 스캔 완료 |
| `failed` | 스캔 실패 |
| `cancelled` | 스캔 취소됨 |

**API 예시:**
```bash
# 특정 스캔 상태 조회
curl -X GET "https://api.vulnix.dev/api/v1/scans/{scan_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

### 3.4 지원 언어 및 취약점 유형

**지원 언어:**
- Python (3.6+)
- JavaScript (ES6+)
- TypeScript
- Java (8+)
- Go (1.16+)

**탐지 취약점 유형 (OWASP Top 10 기준):**

| 취약점 유형 | 예시 |
|---|---|
| SQL Injection | 비매개변수화 쿼리, ORM 우회 |
| Cross-Site Scripting (XSS) | 미검증 사용자 입력 HTML 출력 |
| Broken Authentication | 약한 비밀번호 정책, JWT 미검증 |
| Sensitive Data Exposure | 하드코딩된 비밀번호, API 키 노출 |
| Security Misconfiguration | 디버그 모드 활성화, CORS 설정 오류 |
| Insecure Deserialization | pickle, yaml.load() 무분별 사용 |
| Path Traversal | 파일 경로 미검증 |
| Command Injection | os.system(), subprocess 미검증 입력 |
| SSRF | URL 파라미터 미검증 외부 요청 |
| Cryptographic Issues | MD5/SHA1 사용, 약한 암호화 키 |

---

## 4. 취약점 관리

### 4.1 취약점 목록 보기 (심각도/상태 필터)

**UI에서 확인:**
1. 대시보드 좌측 메뉴에서 **취약점** 을 클릭합니다.
2. 상단 필터 영역에서 원하는 조건을 선택합니다.

**필터 옵션:**

| 필터 | 옵션 |
|---|---|
| 심각도 | `critical`, `high`, `medium`, `low` |
| 상태 | `open`, `fixed`, `false_positive`, `accepted_risk` |
| 저장소 | 특정 저장소 선택 |
| 취약점 유형 | `sql_injection`, `xss`, `path_traversal` 등 |

**API 예시:**
```bash
# 취약점 목록 조회 (심각도 critical 필터)
curl -X GET "https://api.vulnix.dev/api/v1/vulnerabilities?severity=critical&status=open&page=1&per_page=20" \
  -H "Authorization: Bearer {JWT_TOKEN}"

# 특정 저장소의 취약점만 조회
curl -X GET "https://api.vulnix.dev/api/v1/vulnerabilities?repo_id={repo_id}&severity=high" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

### 4.2 취약점 상세 확인 (코드 위치, CWE/OWASP 분류)

취약점 목록에서 항목을 클릭하면 상세 페이지로 이동합니다.

**상세 페이지 포함 정보:**
- **취약점 설명:** 어떤 취약점인지 자연어로 설명
- **코드 위치:** 파일명, 라인 번호, 코드 스니펫
- **심각도:** Critical / High / Medium / Low
- **CWE 분류:** CWE-89 (SQL Injection) 등 CWE ID
- **OWASP 분류:** A01:2021 등 OWASP Top 10 카테고리
- **AI 분석 결과:** Claude AI의 취약점 분석 및 수정 방향 제시
- **연결된 패치 PR:** 자동 생성된 패치 PR 링크 (있는 경우)

**API 예시:**
```bash
# 취약점 상세 조회
curl -X GET "https://api.vulnix.dev/api/v1/vulnerabilities/{vuln_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

### 4.3 상태 변경: open / fixed / false_positive / accepted_risk

취약점의 처리 상태를 수동으로 변경할 수 있습니다.

**상태 의미:**

| 상태 | 의미 |
|---|---|
| `open` | 미처리 상태 (기본값) |
| `fixed` | 수정 완료 |
| `false_positive` | 오탐으로 판정 |
| `accepted_risk` | 위험 수용 (의도적으로 방치) |

**UI에서 상태 변경:**
1. 취약점 목록 또는 상세 페이지에서 취약점을 선택합니다.
2. 상태 드롭다운에서 원하는 상태를 선택합니다.
3. 변경 이유를 입력하고 **"저장"** 을 클릭합니다.
4. 상태 변경 후 해당 저장소의 보안 점수가 즉시 재계산됩니다.

**API 예시:**
```bash
# 취약점 상태 변경
curl -X PATCH "https://api.vulnix.dev/api/v1/vulnerabilities/{vuln_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "fixed"
  }'

# 오탐 처리 + 패턴 자동 등록
curl -X PATCH "https://api.vulnix.dev/api/v1/vulnerabilities/{vuln_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "false_positive",
    "create_pattern": true,
    "file_pattern": "tests/**",
    "pattern_reason": "테스트 코드는 스캔 대상 제외"
  }'
```

---

### 4.4 오탐(False Positive) 마킹 방법

Vulnix는 취약점을 오탐으로 마킹하면 동일한 패턴의 취약점을 향후 스캔에서 자동으로 필터링합니다.

**오탐 마킹 절차:**
1. 취약점 상세 페이지에서 **"오탐으로 표시"** 버튼을 클릭합니다.
2. 오탐 사유를 입력합니다 (예: "테스트 코드의 의도적인 패턴").
3. **"오탐 패턴 자동 등록"** 체크박스를 활성화하면 해당 Semgrep 룰 ID + 파일 패턴이 팀 오탐 패턴에 자동으로 등록됩니다.
4. 파일 패턴을 직접 지정하지 않으면 취약점 파일의 디렉토리 경로를 기반으로 자동 추론됩니다.

---

## 5. 자동 패치 PR

### 5.1 패치 PR 확인 방법

취약점 탐지 후 Claude AI가 자동으로 패치 코드를 생성하고 저장소에 PR을 제출합니다.

**UI에서 확인:**
1. 대시보드 좌측 메뉴에서 **패치 PR** 을 클릭합니다.
2. 생성된 패치 PR 목록을 확인합니다.
3. 상태 필터로 `created`, `merged`, `closed`, `rejected` 중 원하는 상태를 선택합니다.

**패치 PR 목록 정보:**
- PR 번호 및 제목
- 연결된 취약점
- PR 상태 (생성됨 / 병합됨 / 닫힘 / 거부됨)
- 생성일시

**API 예시:**
```bash
# 패치 PR 목록 조회
curl -X GET "https://api.vulnix.dev/api/v1/patches?status=created&page=1&per_page=20" \
  -H "Authorization: Bearer {JWT_TOKEN}"

# 특정 저장소의 패치 PR만 조회
curl -X GET "https://api.vulnix.dev/api/v1/patches?repo_id={repo_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

### 5.2 패치 코드 리뷰 및 승인

1. 패치 PR 상세 페이지에서 **"GitHub에서 보기"** 링크를 클릭합니다.
2. GitHub PR 페이지에서 변경된 코드를 확인합니다.
3. 코드가 적절하다면 **"Merge pull request"** 를 클릭하여 병합합니다.
4. 패치가 병합되면 Vulnix에서 해당 취약점 상태가 자동으로 `fixed`로 업데이트됩니다.

> **중요:** 자동 생성된 패치 코드는 반드시 리뷰 후 병합하세요. AI가 생성한 코드가 비즈니스 로직에 맞지 않을 수 있습니다.

---

### 5.3 패치 재생성 요청

자동 생성된 패치가 적절하지 않다고 판단되면 재생성을 요청할 수 있습니다.

**UI에서 재생성:**
1. 패치 PR 상세 페이지에서 **"패치 재생성"** 버튼을 클릭합니다.
2. 재생성 이유나 추가 컨텍스트를 입력합니다 (선택사항).
3. **"재생성"** 을 클릭하면 새로운 패치 PR이 생성됩니다.

**API 예시:**
```bash
# 패치 PR 상세 조회 (vulnerability 정보 포함)
curl -X GET "https://api.vulnix.dev/api/v1/patches/{patch_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

## 6. 보안 대시보드

### 6.1 보안 점수 계산 방식

Vulnix의 보안 점수는 `open` 상태의 취약점 수를 기반으로 계산됩니다.

**계산 공식:**
```
보안 점수 = max(0, 100 - (critical × 25 + high × 10 + medium × 5 + low × 1))
```

**예시:**
- Critical 취약점 1개, High 2개, Medium 3개 → `100 - (25 + 20 + 15)` = **40점**
- 취약점 0개 → **100점 (만점)**

**점수 등급:**

| 점수 범위 | 등급 | 의미 |
|---|---|---|
| 90 ~ 100 | A (양호) | 보안 상태 우수 |
| 70 ~ 89 | B (보통) | 일부 개선 필요 |
| 50 ~ 69 | C (주의) | 적극적 조치 필요 |
| 0 ~ 49 | D (위험) | 즉각적인 조치 필요 |

---

### 6.2 저장소별 보안 점수 확인

**UI에서 확인:**
1. 대시보드 메인 화면에서 연동된 저장소 목록과 각 저장소의 보안 점수를 확인합니다.
2. 저장소를 클릭하면 해당 저장소의 상세 점수와 취약점 현황을 볼 수 있습니다.

**API 예시:**
```bash
# 저장소 보안 점수 조회
curl -X GET "https://api.vulnix.dev/api/v1/repos/{repo_id}/score" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

### 6.3 취약점 추이 그래프

대시보드 > **보안 트렌드** 섹션에서 시간 경과에 따른 취약점 수 변화를 확인할 수 있습니다.

- **전체 취약점 추이:** 신규 발견 vs 해결 완료 추이
- **심각도별 추이:** Critical/High/Medium/Low 각각의 변화
- **저장소별 비교:** 팀 내 저장소들의 보안 점수 비교

**API 예시:**
```bash
# 대시보드 통계 조회
curl -X GET "https://api.vulnix.dev/api/v1/dashboard/stats" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

### 6.4 심각도별 분포

대시보드 메인에서 현재 `open` 상태의 취약점을 심각도별로 분류한 도넛 차트를 확인할 수 있습니다.

- **Critical:** 즉각적인 악용 가능, 전체 서비스 영향
- **High:** 높은 심각도, 빠른 조치 권장
- **Medium:** 특정 조건에서 악용 가능
- **Low:** 낮은 위험, 장기적 개선 권장

---

## 7. 오탐 관리

### 7.1 팀 오탐 패턴 등록

Vulnix는 팀 단위로 오탐 패턴을 관리합니다. 등록된 패턴에 매칭되는 취약점은 이후 스캔에서 자동으로 필터링됩니다.

**오탐 패턴 구성 요소:**
- **Semgrep 룰 ID:** 어떤 Semgrep 룰을 오탐으로 처리할지 지정 (예: `python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text`)
- **파일 패턴:** 어떤 파일에서만 오탐으로 처리할지 glob 패턴으로 지정 (예: `tests/**`)
- **사유:** 오탐으로 판단한 이유 기록

**UI에서 직접 등록:**
1. 설정 > **오탐 패턴** 메뉴로 이동합니다.
2. **"패턴 추가"** 버튼을 클릭합니다.
3. Semgrep 룰 ID, 파일 패턴, 사유를 입력합니다.
4. **"저장"** 을 클릭합니다.

**API 예시:**
```bash
# 오탐 패턴 등록
curl -X POST "https://api.vulnix.dev/api/v1/false-positives" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "semgrep_rule_id": "python.lang.security.audit.avoid-eval.avoid-eval",
    "file_pattern": "tests/fixtures/**",
    "reason": "테스트 픽스처 파일의 의도적인 eval 사용"
  }'
```

> **권한:** 오탐 패턴 등록/삭제는 팀의 `owner` 또는 `admin` 역할만 가능합니다.

---

### 7.2 패턴 적용 범위 (파일 패턴 glob 사용법)

파일 패턴은 glob 형식을 사용합니다. 패턴 작성 시 다음 규칙을 참고하세요.

**glob 패턴 예시:**

| 패턴 | 적용 범위 |
|---|---|
| `tests/**` | `tests/` 디렉토리 하위 모든 파일 |
| `**/*.test.ts` | 프로젝트 전체에서 `.test.ts`로 끝나는 파일 |
| `src/utils/legacy/**` | `src/utils/legacy/` 하위 모든 파일 |
| `**/fixtures/**` | 어느 위치든 `fixtures` 디렉토리 하위 파일 |
| `**` | 모든 파일 (전체 프로젝트에 적용) |

> **주의:** `**` (전체 프로젝트)를 파일 패턴으로 사용하면 해당 Semgrep 룰이 프로젝트 전체에서 무시됩니다. 최대한 좁은 범위로 지정하는 것을 권장합니다.

---

### 7.3 팀 단위 규칙 공유

등록된 오탐 패턴은 팀 내 모든 멤버에게 자동으로 공유됩니다. 새로운 팀원이 합류해도 기존 오탐 패턴이 그대로 적용됩니다.

**패턴 비활성화/복원:**
```bash
# 오탐 패턴 비활성화 (소프트 삭제)
curl -X DELETE "https://api.vulnix.dev/api/v1/false-positives/{pattern_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}"

# 비활성화된 패턴 복원
curl -X PUT "https://api.vulnix.dev/api/v1/false-positives/{pattern_id}/restore" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

## 8. 알림 설정

### 8.1 Slack Webhook 연동

취약점 발견 시 지정한 Slack 채널로 알림을 받을 수 있습니다.

**Slack Incoming Webhook URL 발급 방법:**
1. Slack 앱 디렉토리에서 **Incoming WebHooks** 앱을 설치합니다.
2. 알림을 받을 채널을 선택합니다.
3. Webhook URL이 발급됩니다 (`https://hooks.slack.com/services/...`).

**Vulnix에서 설정:**
1. 설정 > **알림** 메뉴로 이동합니다.
2. **"알림 채널 추가"** 를 클릭합니다.
3. 플랫폼에서 **Slack** 을 선택합니다.
4. 발급받은 Webhook URL을 입력합니다.
5. 알림을 받을 최소 심각도를 설정합니다.
6. **"저장"** 을 클릭합니다.

**API 예시:**
```bash
# Slack 알림 설정 등록
curl -X POST "https://api.vulnix.dev/api/v1/notifications/config" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "slack",
    "webhook_url": "https://hooks.slack.com/services/YOUR_WORKSPACE/YOUR_CHANNEL/YOUR_TOKEN",
    "severity_threshold": "high",
    "weekly_report_enabled": true,
    "weekly_report_day": 1
  }'

# 테스트 알림 발송
curl -X POST "https://api.vulnix.dev/api/v1/notifications/config/{config_id}/test" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

### 8.2 Microsoft Teams Webhook 연동

**Teams Incoming Webhook URL 발급 방법:**
1. Teams에서 알림을 받을 채널로 이동합니다.
2. 채널 이름 우측의 **"..."** 메뉴 > **"커넥터"** 를 클릭합니다.
3. **"Incoming Webhook"** 을 찾아 **"구성"** 을 클릭합니다.
4. Webhook 이름을 입력하고 **"만들기"** 를 클릭합니다.
5. 생성된 Webhook URL을 복사합니다.

**Vulnix에서 설정:**
1. 알림 설정에서 플랫폼을 **Microsoft Teams** 로 선택합니다.
2. Webhook URL을 입력하고 저장합니다.

**API 예시:**
```bash
curl -X POST "https://api.vulnix.dev/api/v1/notifications/config" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "teams",
    "webhook_url": "https://outlook.office.com/webhook/xxxx",
    "severity_threshold": "critical",
    "weekly_report_enabled": false
  }'
```

---

### 8.3 주간 보안 리포트 자동 발송 설정

매주 지정한 요일에 팀 전체의 보안 현황 요약을 알림 채널로 자동 발송합니다.

**설정 방법:**
1. 알림 설정에서 원하는 채널을 선택합니다.
2. **"주간 리포트 사용"** 토글을 활성화합니다.
3. 발송 요일을 선택합니다 (0=월요일 ~ 6=일요일).
4. **"저장"** 을 클릭합니다.

**API 예시:**
```bash
# 알림 설정 수정 (주간 리포트 활성화)
curl -X PATCH "https://api.vulnix.dev/api/v1/notifications/config/{config_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "weekly_report_enabled": true,
    "weekly_report_day": 1
  }'
```

---

### 8.4 알림 심각도 임계값 설정

지정한 심각도 이상의 취약점이 발견될 때만 알림을 발송하도록 설정할 수 있습니다.

**심각도 임계값 옵션:**

| 설정값 | 알림 발송 조건 |
|---|---|
| `low` | 모든 취약점 발견 시 |
| `medium` | Medium 이상 발견 시 |
| `high` | High 이상 발견 시 |
| `critical` | Critical 발견 시만 |

---

## 9. CISO 리포트

### 9.1 리포트 유형: CSAP / ISO 27001 / ISMS

Vulnix는 주요 보안 인증 체계에 맞는 리포트를 자동으로 생성합니다.

**지원 리포트 유형:**

| 유형 | 설명 |
|---|---|
| `csap` | 클라우드 보안 인증제(CSAP) 증적용 취약점 현황 리포트 |
| `iso27001` | ISO 27001 정보보안 관리체계 인증 증적 리포트 |
| `isms` | 국내 정보보호관리체계(ISMS) 인증 증적 리포트 |

---

### 9.2 PDF 리포트 생성 방법

**UI에서 생성:**
1. 대시보드 좌측 메뉴에서 **리포트** 를 클릭합니다.
2. **"리포트 생성"** 버튼을 클릭합니다.
3. 리포트 유형 (CSAP / ISO 27001 / ISMS)을 선택합니다.
4. 기간을 설정합니다 (시작일 ~ 종료일).
5. 출력 형식 (PDF 또는 JSON)을 선택합니다.
6. **"생성"** 을 클릭합니다.
7. 리포트 생성은 비동기로 처리되며, 완료되면 알림이 표시됩니다.
8. 생성 완료 후 **"다운로드"** 버튼으로 파일을 받을 수 있습니다.

**API 예시:**
```bash
# 리포트 생성 요청 (비동기)
curl -X POST "https://api.vulnix.dev/api/v1/reports/generate" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "csap",
    "format": "pdf",
    "period_start": "2026-01-01",
    "period_end": "2026-02-28"
  }'

# 응답 예시
{
  "success": true,
  "data": {
    "report_id": "report-uuid",
    "status": "generating",
    "report_type": "csap",
    "estimated_completion_seconds": 30
  }
}

# 리포트 생성 이력 조회
curl -X GET "https://api.vulnix.dev/api/v1/reports/history?report_type=csap&status=completed" \
  -H "Authorization: Bearer {JWT_TOKEN}"

# 리포트 다운로드
curl -X GET "https://api.vulnix.dev/api/v1/reports/{report_id}/download" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -o "report.pdf"
```

---

### 9.3 자동 발송 스케줄 설정

정기적으로 리포트를 자동 생성하여 지정한 이메일 주소로 발송하도록 설정할 수 있습니다.

**스케줄 설정 방법:**
1. 리포트 > **"스케줄 설정"** 탭으로 이동합니다.
2. **"스케줄 추가"** 버튼을 클릭합니다.
3. 리포트 유형과 발송 주기 (cron 형식)를 입력합니다.
4. 수신자 이메일 주소를 입력합니다.
5. **"저장"** 을 클릭합니다.

**스케줄 형식 예시:**
- `@monthly` — 매월 1일 자동 생성
- `@weekly` — 매주 월요일 자동 생성
- `0 9 1 * *` — 매월 1일 오전 9시 생성

**API 예시:**
```bash
# 리포트 자동 발송 스케줄 설정
curl -X POST "https://api.vulnix.dev/api/v1/reports/config" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "isms",
    "schedule": "@monthly",
    "email_recipients": ["ciso@company.com", "security@company.com"],
    "is_active": true
  }'
```

---

## 10. VS Code 익스텐션

### 10.1 설치 방법

**VS Code Marketplace에서 설치:**
1. VS Code를 실행합니다.
2. 좌측 사이드바에서 **Extensions** 아이콘을 클릭합니다.
3. 검색창에 `Vulnix Security Scanner`를 입력합니다.
4. 검색 결과에서 **"Vulnix Security Scanner"** 를 클릭하고 **"Install"** 버튼을 클릭합니다.

**VSIX 파일로 설치 (오프라인):**
1. Vulnix 대시보드 > 설정에서 VSIX 파일을 다운로드합니다.
2. VS Code에서 `Ctrl+Shift+P` (Mac: `Cmd+Shift+P`)를 눌러 명령 팔레트를 엽니다.
3. `Extensions: Install from VSIX...` 를 선택합니다.
4. 다운로드한 VSIX 파일을 선택합니다.

---

### 10.2 API Key 발급

VS Code 익스텐션은 Vulnix 서버와 통신하기 위해 API Key가 필요합니다.

**API Key 발급 방법:**
1. Vulnix 대시보드에서 설정 > **API Keys** 로 이동합니다.
2. **"새 API Key 발급"** 버튼을 클릭합니다.
3. Key 이름을 입력합니다 (예: "VS Code - 개인 노트북").
4. 만료 기간을 설정합니다 (선택사항).
5. **"발급"** 을 클릭합니다.
6. 발급된 API Key (`vx_live_...` 형식)를 복사합니다. **이 값은 다시 확인할 수 없습니다.**

> **권한:** API Key 발급은 팀의 `owner` 또는 `admin` 역할만 가능합니다.

---

### 10.3 설정 방법 (serverUrl, apiKey)

**VS Code 설정 방법:**
1. VS Code에서 `Ctrl+,` (Mac: `Cmd+,`)를 눌러 설정을 엽니다.
2. 검색창에 `vulnix`를 입력합니다.
3. 다음 설정을 입력합니다.

| 설정 항목 | 키 | 기본값 | 설명 |
|---|---|---|---|
| 서버 URL | `vulnix.serverUrl` | `https://api.vulnix.dev` | Vulnix API 서버 주소 |
| API Key | `vulnix.apiKey` | (비어있음) | 발급받은 API Key |
| 저장 시 분석 | `vulnix.analyzeOnSave` | `true` | 파일 저장 시 자동 분석 여부 |
| 심각도 필터 | `vulnix.severityFilter` | `all` | 표시할 최소 심각도 (`all` / `high` / `critical`) |

**settings.json에서 직접 설정:**
```json
{
  "vulnix.serverUrl": "https://api.vulnix.dev",
  "vulnix.apiKey": "vx_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "vulnix.analyzeOnSave": true,
  "vulnix.severityFilter": "all"
}
```

---

### 10.4 실시간 취약점 하이라이팅 사용법

설정이 완료되면 Python, JavaScript, TypeScript, Java, Go 파일을 편집하거나 저장할 때 자동으로 취약점 분석이 실행됩니다.

**하이라이팅 방식:**
- 취약점이 발견된 코드 라인 아래에 빨간색 물결 밑줄이 표시됩니다.
- 물결 밑줄에 마우스를 올리면 취약점 설명이 팝업으로 표시됩니다.
- 좌측 에디터 여백(gutter)에 경고 아이콘이 표시됩니다.
- VS Code **Problems** 패널 (`Ctrl+Shift+M`)에서 현재 파일의 모든 취약점 목록을 확인할 수 있습니다.

**심각도별 표시 색상:**
- Critical / High: 빨간색 밑줄
- Medium: 주황색 밑줄
- Low: 노란색 밑줄

---

### 10.5 패치 자동 적용 방법

취약점이 표시된 코드 라인에서 자동 패치를 적용할 수 있습니다.

**패치 적용 절차:**
1. 취약점 코드 라인에서 빨간색 물결 밑줄을 클릭합니다.
2. 코드 라인 왼쪽에 나타나는 **전구 아이콘 (Quick Fix)** 을 클릭합니다.
3. **"Vulnix: Apply Patch Fix"** 를 선택합니다.
4. "패치 제안을 생성하는 중..." 로딩 표시가 나타납니다.
5. 패치가 완료되면 코드가 자동으로 수정되고 성공 메시지가 표시됩니다.

> **주의:** 패치 적용 전 현재 작업 내용을 저장하고 git commit을 권장합니다. 패치 후 반드시 코드를 검토하세요.

---

### 10.6 명령 팔레트 목록

`Ctrl+Shift+P` (Mac: `Cmd+Shift+P`)를 눌러 명령 팔레트에서 Vulnix 명령을 실행할 수 있습니다.

| 명령 | 설명 |
|---|---|
| `Vulnix: Analyze Current File` | 현재 열린 파일 즉시 분석 |
| `Vulnix: Apply Patch Fix` | 선택한 취약점에 패치 적용 |
| `Vulnix: Show Vulnerability Detail` | 취약점 상세 정보 웹뷰로 표시 |
| `Vulnix: Sync False Positive Patterns` | 서버에서 최신 오탐 패턴 동기화 |
| `Vulnix: Clear All Diagnostics` | 현재 표시된 모든 취약점 하이라이팅 제거 |

---

## 11. API Key 관리

### 11.1 IDE용 API Key 발급

API Key는 VS Code 익스텐션과 같은 IDE 도구가 Vulnix 서버에 접근할 때 사용합니다. JWT 토큰과는 별개로 관리됩니다.

**발급 절차:**
1. Vulnix 대시보드 설정 > **API Keys** 로 이동합니다.
2. **"새 API Key 발급"** 버튼을 클릭합니다.
3. Key 이름을 입력합니다 (사용 목적을 명확히 구분할 수 있는 이름 권장).
4. 만료 기간을 설정합니다 (30일, 90일, 1년 또는 만료 없음).
5. **"발급"** 을 클릭합니다.
6. 발급된 전체 API Key 값을 안전한 곳에 복사합니다. **화면을 벗어나면 다시 확인할 수 없습니다.**

**API 예시:**
```bash
# API Key 발급
curl -X POST "https://api.vulnix.dev/api/v1/ide/api-keys" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "VS Code - 개발 노트북",
    "expires_in_days": 365
  }'

# 응답 예시
{
  "success": true,
  "data": {
    "id": "key-uuid",
    "name": "VS Code - 개발 노트북",
    "key": "vx_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "key_prefix": "vx_live_xxxx",
    "expires_at": "2027-02-26T00:00:00Z",
    "created_at": "2026-02-26T00:00:00Z"
  }
}
```

---

### 11.2 Key 비활성화 방법

더 이상 사용하지 않는 API Key는 즉시 비활성화하세요. 비활성화된 Key로는 API 요청이 거부됩니다.

**UI에서 비활성화:**
1. 설정 > API Keys 목록에서 비활성화할 Key를 찾습니다.
2. 해당 Key 우측의 **"비활성화"** 버튼을 클릭합니다.
3. 확인 다이얼로그에서 **"비활성화"** 를 클릭합니다.

**API 예시:**
```bash
# API Key 비활성화
curl -X DELETE "https://api.vulnix.dev/api/v1/ide/api-keys/{key_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}"

# API Key 목록 조회
curl -X GET "https://api.vulnix.dev/api/v1/ide/api-keys" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

> **보안 권장사항:** API Key가 유출된 경우 즉시 비활성화하고 새로운 Key를 발급받으세요.

---

## 12. 문제 해결

### 12.1 스캔이 시작되지 않는 경우

**증상:** 저장소에 코드를 푸시했는데 자동 스캔이 시작되지 않음.

**확인 사항:**

1. **Webhook 등록 여부 확인**
   - GitHub: 저장소 설정 > Webhooks에서 Vulnix webhook이 등록되어 있는지 확인합니다.
   - Webhook URL: `https://api.vulnix.dev/api/v1/webhooks/github`
   - 최근 전송 이력에서 응답 코드가 200인지 확인합니다.

2. **저장소 활성화 상태 확인**
   - Vulnix 대시보드에서 해당 저장소가 `is_active: true` 상태인지 확인합니다.

3. **수동 스캔으로 대체 실행**
   ```bash
   curl -X POST "https://api.vulnix.dev/api/v1/scans" \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"repo_id": "{repo_id}", "branch": "main"}'
   ```

4. **진행 중인 스캔 확인**
   - 동일 저장소에 이미 진행 중인 스캔이 있으면 새 스캔이 시작되지 않습니다.
   - 대시보드 > 스캔 이력에서 `queued` 또는 `running` 상태의 스캔이 있는지 확인합니다.

---

### 12.2 Webhook이 수신되지 않는 경우

**증상:** GitHub/GitLab/Bitbucket에서 이벤트가 발생했으나 Vulnix에서 수신하지 못함.

**확인 사항:**

1. **Webhook Secret 일치 여부 확인**
   - GitHub: 저장소 설정 > Webhooks > 해당 Webhook 편집에서 Secret이 일치하는지 확인합니다.

2. **Webhook 이벤트 유형 확인**
   - GitHub Webhook은 `push`, `pull_request` 이벤트가 체크되어 있어야 합니다.
   - GitLab Webhook은 `Push events`, `Merge request events`가 활성화되어 있어야 합니다.

3. **네트워크 접근성 확인**
   - Vulnix 서버가 외부에서 접근 가능한지 확인합니다.
   - 로컬 개발 환경에서는 ngrok 등의 터널링 도구를 사용하세요.

4. **Webhook 전송 로그 확인**
   - GitHub: 저장소 설정 > Webhooks > 최근 전송 목록에서 응답 코드를 확인합니다.
   - 응답 코드가 4xx 또는 5xx라면 서버 로그를 확인하세요.

---

### 12.3 패치 PR이 생성되지 않는 경우

**증상:** 취약점이 탐지되었으나 패치 PR이 자동으로 생성되지 않음.

**확인 사항:**

1. **GitHub App 권한 확인**
   - GitHub App이 `pull_requests: write`, `contents: write` 권한을 가지고 있는지 확인합니다.

2. **취약점 심각도 확인**
   - 패치 PR은 기본적으로 `medium` 이상의 취약점에 대해서만 생성됩니다.

3. **브랜치 보호 규칙 확인**
   - default 브랜치에 직접 푸시를 막는 브랜치 보호 규칙이 있으면 PR 생성이 실패할 수 있습니다.
   - Vulnix가 패치 브랜치를 생성하고 PR을 제출하는 방식이므로 브랜치 생성 권한이 필요합니다.

4. **수동으로 패치 재요청**
   - 취약점 상세 페이지에서 **"패치 재생성"** 버튼을 클릭합니다.

---

### 12.4 VS Code 익스텐션 연결 오류

**증상:** VS Code에서 "API 키가 설정되지 않았습니다" 또는 "서버에 연결할 수 없습니다" 메시지가 표시됨.

**해결 방법:**

1. **API Key 설정 확인**
   - VS Code 설정에서 `vulnix.apiKey`가 올바르게 입력되어 있는지 확인합니다.
   - API Key 형식: `vx_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

2. **서버 URL 확인**
   - `vulnix.serverUrl`이 올바른지 확인합니다. 기본값: `https://api.vulnix.dev`
   - 자체 호스팅 환경이라면 내부 URL로 변경하세요.

3. **API Key 유효성 확인**
   ```bash
   # API Key로 취약점 분석 테스트
   curl -X POST "https://api.vulnix.dev/api/v1/ide/analyze" \
     -H "X-Api-Key: vx_live_xxxx" \
     -H "Content-Type: application/json" \
     -d '{
       "content": "import os\nos.system(input())",
       "language": "python",
       "file_path": "test.py"
     }'
   ```

4. **API Key 비활성화 여부 확인**
   - Vulnix 대시보드 > 설정 > API Keys에서 해당 Key가 활성화 상태인지 확인합니다.
   - 만료된 Key라면 새로운 Key를 발급받으세요.

5. **VS Code 재시작**
   - 설정 변경 후 VS Code를 완전히 종료하고 다시 시작합니다.
   - 명령 팔레트 (`Ctrl+Shift+P`)에서 `Vulnix: Sync False Positive Patterns`를 실행하여 연결 상태를 확인합니다.

---

## 추가 도움이 필요한 경우

- **공식 문서:** `https://docs.vulnix.dev`
- **기술 지원:** `support@vulnix.dev`
- **GitHub Issues:** `https://github.com/vulnix/vulnix/issues`

---

*Vulnix 사용자 매뉴얼 v1.0 | 2026년 2월*
