# 시스템 설계서 — Vulnix

**버전**: v1.0
**작성일**: 2026-02-25
**상태**: 확정 (PoC 기준)

---

## 1. 시스템 개요

### 1-1. 핵심 가치 흐름

```
코드 푸시/PR 생성
  -> GitHub Webhook 수신
  -> Semgrep 룰 기반 1차 탐지
  -> Claude LLM 2차 분석 (오탐 필터 + 패치 코드 생성)
  -> GitHub 패치 PR 자동 생성
  -> 대시보드에 결과 반영
```

### 1-2. 아키텍처 패턴

- **모듈형 모노리스** (Modular Monolith)
  - PoC 단계에서는 단일 FastAPI 애플리케이션 내에 모듈을 분리하여 구성
  - 스캔 작업은 Redis 큐를 통해 비동기 처리 (백그라운드 워커)
  - 향후 스캔 오케스트레이터를 별도 서비스로 분리 가능한 구조 유지

### 1-3. 배포 전략

- **Backend**: Railway (단일 서비스 + 워커 프로세스)
- **Frontend**: Vercel (Next.js 자동 배포)
- **DB**: Supabase (관리형 PostgreSQL)
- **캐시/큐**: Upstash Redis (서버리스 Redis)

### 1-4. 주요 컴포넌트 목록

| # | 컴포넌트 | 역할 |
|---|----------|------|
| 1 | API Gateway | FastAPI 기반 라우팅, 인증, 요청 검증 |
| 2 | 스캔 오케스트레이터 | 스캔 작업 큐 관리, 워커 배분, 상태 추적 |
| 3 | 1차 탐지 엔진 | Semgrep 룰 기반 AST 정적 분석 |
| 4 | 2차 LLM 에이전트 | Claude API 기반 오탐 필터 + 패치 코드 생성 |
| 5 | GitHub App 연동 | Webhook 수신, 코드 클론, PR 생성 |
| 6 | 대시보드 API | 취약점 히스토리, 통계, 리포트 |
| 7 | 프론트엔드 | Next.js 대시보드 UI |

---

## 2. 아키텍처 다이어그램

### 2-1. 전체 시스템 흐름

```
                          [Vercel]
                       +--------------+
                       |   Next.js    |
                       |  Dashboard   |
                       +------+-------+
                              |
                              | REST API
                              v
[GitHub]              +-------+--------+        [Supabase]
+----------+  Webhook |                |        +----------+
| Customer +--------->+  FastAPI       +------->+PostgreSQL|
|   Repo   |          |  (Railway)     |        +----------+
+----+-----+          |                |
     ^                | +------------+ |        [Upstash]
     |                | | API        | |        +----------+
     | PR Create      | | Gateway    | +------->+  Redis   |
     |                | +-----+------+ |        |  (Queue) |
     |                |       |        |        +----------+
     |                | +-----v------+ |
     |                | | Scan       | |
     |                | | Orchestr.  | |
     |                | +--+------+--+ |
     |                |    |      |    |
     |                | +--v--+ +-v--+ |
     |                | |Semgr| |LLM | |
     |                | |ep   | |Agent|
     |                | +-----+ +--+-+ |
     |                |            |   |
     |                +------------+---+
     |                             |
     +-----------------------------+
           Patch PR via GitHub API
```

### 2-2. 스캔 처리 흐름 (Sequence)

```
GitHub           API Gateway      Orchestrator     Semgrep        LLM Agent       GitHub API
  |                  |                |               |               |               |
  |-- webhook ------>|                |               |               |               |
  |                  |-- enqueue ---->|               |               |               |
  |                  |<-- job_id -----|               |               |               |
  |                  |                |               |               |               |
  |                  |                |-- clone repo->|               |               |
  |                  |                |               |               |               |
  |                  |                |-- run scan -->|               |               |
  |                  |                |<- findings ---|               |               |
  |                  |                |               |               |               |
  |                  |                |-- analyze ----|-------------->|               |
  |                  |                |              (filter + patch) |               |
  |                  |                |<------------- results -------|               |
  |                  |                |               |               |               |
  |                  |                |-- create PR --|---------------|-------------->|
  |                  |                |               |               |               |
  |                  |                |-- save to DB  |               |               |
  |                  |                |               |               |               |
```

---

## 3. 컴포넌트 상세 설계

### 3-1. API Gateway (FastAPI)

**역할**: 모든 외부 요청의 진입점. 인증, 라우팅, 요청 검증 담당.

**주요 기술**: FastAPI, Pydantic, python-jose (JWT)

**핵심 엔드포인트**:

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/webhooks/github` | GitHub Webhook 수신 |
| POST | `/api/v1/scans` | 수동 스캔 트리거 |
| GET | `/api/v1/scans/{scan_id}` | 스캔 상태 조회 |
| GET | `/api/v1/repos` | 연동 저장소 목록 |
| POST | `/api/v1/repos` | 저장소 연동 등록 |
| GET | `/api/v1/vulnerabilities` | 취약점 목록 조회 |
| GET | `/api/v1/vulnerabilities/{vuln_id}` | 취약점 상세 조회 |
| PATCH | `/api/v1/vulnerabilities/{vuln_id}` | 취약점 상태 변경 (오탐 마킹 등) |
| GET | `/api/v1/patches` | 패치 PR 목록 조회 |
| GET | `/api/v1/dashboard/summary` | 대시보드 요약 통계 |
| POST | `/api/v1/auth/github` | GitHub OAuth 로그인 |
| GET | `/api/v1/auth/me` | 현재 사용자 정보 |

**응답 형식**:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 150
  }
}
```

**인증 방식**:
- 사용자 인증: GitHub OAuth -> JWT 발급
- Webhook 인증: GitHub Webhook Secret 서명 검증
- API 인증: Bearer JWT (Access Token + Refresh Token)

### 3-2. 스캔 오케스트레이터

**역할**: 스캔 작업의 생명주기를 관리. 작업 큐잉, 상태 추적, 실패 재시도.

**주요 기술**: Redis Queue (arq 또는 rq), asyncio

**작업 흐름**:

1. Webhook 또는 수동 트리거 수신
2. ScanJob 레코드 생성 (상태: `queued`)
3. Redis 큐에 작업 등록
4. 워커가 작업을 가져와 처리 시작 (상태: `running`)
5. Semgrep 1차 스캔 실행
6. 1차 결과로 LLM 2차 분석 실행
7. 결과 DB 저장 + PR 생성 (상태: `completed` / `failed`)

**스캔 작업 상태 머신**:

```
queued -> running -> completed
                  -> failed -> queued (재시도, 최대 3회)
```

**Redis 큐 메시지 형식**:

```json
{
  "job_id": "scan_abc123",
  "repo_id": "repo_xyz",
  "trigger": "webhook",
  "commit_sha": "a1b2c3d",
  "branch": "feature/login",
  "pr_number": 42,
  "created_at": "2026-02-25T10:00:00Z"
}
```

### 3-3. 1차 탐지 엔진 (Semgrep)

**역할**: 룰 기반 AST 분석으로 빠르게 취약점 후보를 추출. LLM 호출을 최소화하기 위한 사전 필터.

**주요 기술**: Semgrep CLI, 커스텀 룰셋 (YAML)

**PoC 범위 탐지 대상** (Python만):

| 취약점 유형 | Semgrep 룰 카테고리 | CWE |
|-------------|---------------------|-----|
| SQL Injection | python.sqlalchemy.security, python.django.security | CWE-89 |
| XSS | python.flask.security, python.django.security | CWE-79 |
| Hardcoded Credentials | generic.secrets | CWE-798 |

**실행 방식**:

```bash
semgrep scan --config=auto --config=./rules/ --json --output=results.json <target_dir>
```

**Semgrep 출력 → 내부 모델 변환**:

```python
# Semgrep JSON 결과를 내부 Finding 모델로 변환
class SemgrepFinding:
    rule_id: str           # 예: "python.flask.security.xss"
    severity: str          # ERROR / WARNING / INFO
    file_path: str         # 취약 코드 위치
    start_line: int
    end_line: int
    code_snippet: str      # 해당 코드 조각
    message: str           # 룰 설명
    cwe: list[str]         # CWE 매핑
```

**코드 보안 원칙**:
- 고객 코드를 임시 디렉토리에 클론
- 스캔 완료 후 즉시 삭제 (`shutil.rmtree`)
- 임시 디렉토리는 `/tmp/vulnix-scan-{job_id}/` 형식

### 3-4. 2차 LLM 에이전트 (Claude API)

**역할**: Semgrep 1차 결과를 받아 (1) 오탐 필터링 (2) 심각도 재평가 (3) 패치 코드 생성.

**주요 기술**: Anthropic Python SDK, claude-sonnet 모델

**LLM 호출 전략**:

- 1차 Semgrep 결과가 없으면 LLM 호출 안 함 (비용 절약)
- Finding별로 개별 호출하지 않고, 파일 단위로 배치 처리
- 토큰 사용량 추적 → 사용자별 한도 관리

**프롬프트 구조** (2단계):

**(1) 오탐 필터 + 심각도 평가 프롬프트**:

```
[시스템] 당신은 시니어 보안 엔지니어입니다.
[사용자]
다음 코드에서 정적 분석 도구가 탐지한 취약점 목록입니다.
각 항목에 대해:
1. 실제 취약점인지 오탐인지 판단하세요
2. 실제 취약점이면 심각도를 평가하세요 (Critical/High/Medium/Low)
3. 판단 근거를 간단히 설명하세요

--- 소스 코드 ---
{file_content}

--- 탐지 결과 ---
{semgrep_findings}
```

**(2) 패치 코드 생성 프롬프트**:

```
[시스템] 당신은 시니어 보안 엔지니어입니다. 보안 취약점에 대한 패치 코드를 생성합니다.
[사용자]
다음 취약점에 대한 패치 코드를 생성하세요.
- 기존 코드 스타일을 유지하세요
- 최소한의 변경으로 취약점만 수정하세요
- unified diff 형식으로 출력하세요

--- 취약점 정보 ---
{vulnerability_detail}

--- 원본 코드 ---
{original_code}
```

**LLM 응답 파싱**:

```python
class LLMAnalysisResult:
    finding_id: str
    is_true_positive: bool    # 실제 취약점 여부
    confidence: float         # 0.0 ~ 1.0
    severity: str             # Critical / High / Medium / Low
    reasoning: str            # 판단 근거
    patch_diff: str | None    # unified diff 형식 패치
    patch_description: str    # 패치 설명
    references: list[str]     # CVE, OWASP 참조 링크
```

### 3-5. GitHub App 연동

**역할**: GitHub App으로 설치, Webhook 수신, 코드 클론(read), PR 생성(write).

**주요 기술**: PyGithub 또는 httpx (GitHub REST API v3), GitHub App JWT

**GitHub App 필요 권한**:

| 권한 | 수준 | 용도 |
|------|------|------|
| Repository contents | Read | 코드 클론 |
| Pull requests | Write | 패치 PR 생성 |
| Webhooks | Read | 이벤트 수신 |
| Metadata | Read | 저장소 메타정보 |
| Checks | Write | 스캔 상태 리포트 (선택) |

**Webhook 처리 대상 이벤트**:

| 이벤트 | 액션 | 처리 |
|--------|------|------|
| `push` | - | 지정 브랜치 푸시 시 스캔 트리거 |
| `pull_request` | `opened`, `synchronize` | PR 생성/업데이트 시 스캔 트리거 |
| `installation` | `created`, `deleted` | App 설치/삭제 시 저장소 등록/해제 |

**패치 PR 생성 흐름**:

1. 스캔 결과에서 패치 가능한 취약점 추출
2. 취약점별로 패치 브랜치 생성 (`vulnix/fix-{vuln_type}-{short_hash}`)
3. 패치 diff를 커밋으로 적용
4. PR 생성 (제목, 본문, 라벨 자동 작성)

**PR 본문 템플릿**:

```markdown
## Vulnix Security Patch

### 탐지된 취약점
- **유형**: {vulnerability_type} ({cwe_id})
- **심각도**: {severity}
- **파일**: `{file_path}` (Line {start_line}-{end_line})

### 취약점 설명
{vulnerability_description}

### 패치 내용
{patch_description}

### 참고 자료
- {reference_links}

---
> 이 PR은 [Vulnix](https://vulnix.dev) 보안 에이전트가 자동 생성했습니다.
> 반드시 코드 리뷰 후 머지하세요.
```

### 3-6. 대시보드 API

**역할**: 프론트엔드에 취약점 현황, 히스토리, 통계 데이터를 제공.

**주요 기술**: FastAPI (API Gateway와 동일 앱)

**핵심 엔드포인트**:

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/v1/dashboard/summary` | 전체 요약 (총 취약점, 해결률, 최근 스캔) |
| GET | `/api/v1/dashboard/trend` | 기간별 취약점 추이 |
| GET | `/api/v1/repos/{repo_id}/score` | 저장소별 보안 점수 |
| GET | `/api/v1/repos/{repo_id}/vulnerabilities` | 저장소별 취약점 목록 |
| GET | `/api/v1/repos/{repo_id}/scans` | 저장소별 스캔 히스토리 |

### 3-7. 프론트엔드 (Next.js)

**역할**: 사용자가 저장소를 연동하고, 스캔 결과를 확인하며, 취약점을 관리하는 웹 대시보드.

**주요 기술**: Next.js 14 (App Router), Tailwind CSS, shadcn/ui, React Query (TanStack Query)

**주요 페이지**:

| 페이지 | 경로 | 설명 |
|--------|------|------|
| 랜딩 | `/` | 제품 소개, CTA |
| 로그인 | `/login` | GitHub OAuth 로그인 |
| 대시보드 | `/dashboard` | 전체 요약 통계 |
| 저장소 목록 | `/repos` | 연동된 저장소 목록 |
| 저장소 상세 | `/repos/{id}` | 저장소별 취약점, 스캔 히스토리 |
| 취약점 상세 | `/vulnerabilities/{id}` | 취약점 코드 뷰, 패치 diff, 상태 관리 |
| 스캔 상세 | `/scans/{id}` | 스캔 진행 상태, 결과 요약 |
| 설정 | `/settings` | 팀 관리, 알림 설정, API 키 |

**인증 흐름**:
- GitHub OAuth 로그인 -> Backend에서 JWT 발급 -> httpOnly 쿠키 또는 Authorization 헤더로 API 호출

---

## 4. 데이터 모델

### 4-1. ER 다이어그램

```
User 1---* TeamMember *---1 Team
Team 1---* Repository
Repository 1---* ScanJob
ScanJob 1---* Vulnerability
Vulnerability 1---0..1 PatchPR
```

### 4-2. 엔티티 상세

#### User (사용자)

| 컬럼 | 타입 | 설명 |
|-------|------|------|
| id | UUID | PK |
| github_id | BIGINT | GitHub 사용자 ID |
| github_login | VARCHAR(255) | GitHub 로그인명 |
| email | VARCHAR(255) | 이메일 |
| avatar_url | TEXT | 프로필 이미지 |
| access_token_enc | TEXT | 암호화된 GitHub Access Token |
| created_at | TIMESTAMPTZ | 생성일 |
| updated_at | TIMESTAMPTZ | 수정일 |

#### Team (팀)

| 컬럼 | 타입 | 설명 |
|-------|------|------|
| id | UUID | PK |
| name | VARCHAR(255) | 팀명 |
| plan | VARCHAR(50) | 플랜 (starter/growth/scale/enterprise) |
| created_at | TIMESTAMPTZ | 생성일 |

#### TeamMember (팀 멤버)

| 컬럼 | 타입 | 설명 |
|-------|------|------|
| id | UUID | PK |
| team_id | UUID | FK -> Team |
| user_id | UUID | FK -> User |
| role | VARCHAR(50) | 역할 (owner/admin/member) |
| joined_at | TIMESTAMPTZ | 가입일 |

#### Repository (저장소)

| 컬럼 | 타입 | 설명 |
|-------|------|------|
| id | UUID | PK |
| team_id | UUID | FK -> Team |
| github_repo_id | BIGINT | GitHub 저장소 ID |
| full_name | VARCHAR(255) | 예: "org/repo-name" |
| default_branch | VARCHAR(255) | 기본 브랜치 |
| language | VARCHAR(50) | 주 언어 |
| is_active | BOOLEAN | 스캔 활성화 여부 |
| installation_id | BIGINT | GitHub App 설치 ID |
| webhook_secret | TEXT | Webhook 서명 검증용 시크릿 |
| last_scanned_at | TIMESTAMPTZ | 마지막 스캔 일시 |
| security_score | DECIMAL(5,2) | 보안 점수 (0~100) |
| created_at | TIMESTAMPTZ | 생성일 |

#### ScanJob (스캔 작업)

| 컬럼 | 타입 | 설명 |
|-------|------|------|
| id | UUID | PK |
| repo_id | UUID | FK -> Repository |
| status | VARCHAR(20) | queued / running / completed / failed |
| trigger_type | VARCHAR(20) | webhook / manual / schedule |
| commit_sha | VARCHAR(40) | 대상 커밋 SHA |
| branch | VARCHAR(255) | 대상 브랜치 |
| pr_number | INTEGER | PR 번호 (PR 트리거 시) |
| findings_count | INTEGER | 탐지 건수 |
| true_positives_count | INTEGER | 실제 취약점 건수 |
| false_positives_count | INTEGER | 오탐 건수 |
| duration_seconds | INTEGER | 스캔 소요 시간 (초) |
| error_message | TEXT | 실패 시 에러 메시지 |
| started_at | TIMESTAMPTZ | 시작 시각 |
| completed_at | TIMESTAMPTZ | 완료 시각 |
| created_at | TIMESTAMPTZ | 생성일 |

#### Vulnerability (취약점)

| 컬럼 | 타입 | 설명 |
|-------|------|------|
| id | UUID | PK |
| scan_job_id | UUID | FK -> ScanJob |
| repo_id | UUID | FK -> Repository |
| status | VARCHAR(20) | open / patched / ignored / false_positive |
| severity | VARCHAR(20) | critical / high / medium / low |
| vulnerability_type | VARCHAR(100) | 예: "sql_injection" |
| cwe_id | VARCHAR(20) | 예: "CWE-89" |
| owasp_category | VARCHAR(50) | OWASP Top 10 분류 |
| file_path | VARCHAR(500) | 취약 파일 경로 |
| start_line | INTEGER | 시작 라인 |
| end_line | INTEGER | 끝 라인 |
| code_snippet | TEXT | 취약 코드 조각 |
| description | TEXT | 취약점 설명 |
| llm_reasoning | TEXT | LLM 분석 근거 |
| llm_confidence | DECIMAL(3,2) | LLM 확신도 (0.00~1.00) |
| semgrep_rule_id | VARCHAR(255) | Semgrep 룰 ID |
| references | JSONB | 참고 링크 목록 |
| detected_at | TIMESTAMPTZ | 탐지 시각 |
| resolved_at | TIMESTAMPTZ | 해결 시각 |
| created_at | TIMESTAMPTZ | 생성일 |

#### PatchPR (패치 PR)

| 컬럼 | 타입 | 설명 |
|-------|------|------|
| id | UUID | PK |
| vulnerability_id | UUID | FK -> Vulnerability |
| repo_id | UUID | FK -> Repository |
| github_pr_number | INTEGER | GitHub PR 번호 |
| github_pr_url | TEXT | GitHub PR URL |
| branch_name | VARCHAR(255) | 패치 브랜치명 |
| status | VARCHAR(20) | created / merged / closed / rejected |
| patch_diff | TEXT | 패치 diff 내용 |
| patch_description | TEXT | 패치 설명 |
| created_at | TIMESTAMPTZ | 생성일 |
| merged_at | TIMESTAMPTZ | 머지 시각 |

### 4-3. 인덱스 전략

```sql
-- 자주 조회되는 필터 조건에 인덱스
CREATE INDEX idx_vulnerability_repo_status ON vulnerability(repo_id, status);
CREATE INDEX idx_vulnerability_severity ON vulnerability(severity);
CREATE INDEX idx_scan_job_repo_status ON scan_job(repo_id, status);
CREATE INDEX idx_scan_job_created ON scan_job(created_at DESC);
CREATE INDEX idx_patch_pr_repo ON patch_pr(repo_id);
CREATE INDEX idx_repository_team ON repository(team_id);
```

---

## 5. 핵심 기술 결정 (ADR)

### ADR-001: Semgrep + LLM 하이브리드 탐지 구조

**상태**: 확정

**맥락**: 취약점 탐지 방식으로 (A) 룰 기반만, (B) LLM만, (C) 하이브리드 중 선택 필요.

**결정**: (C) 하이브리드 — Semgrep 1차 → Claude LLM 2차

**근거**:
- *Semgrep만*: 빠르고 저렴하지만, 코드 컨텍스트를 이해하지 못해 오탐율 30~60%. 패치 생성 불가.
- *LLM만*: 컨텍스트 이해력 우수하지만, 전체 코드베이스를 LLM에 넣으면 비용 폭발 (10만 라인 기준 1회 스캔에 약 $50~100 추정). 속도도 느림.
- *하이브리드*: Semgrep이 빠르게 후보를 추려 LLM 호출을 최소화. LLM은 후보에 대해서만 정밀 분석 + 패치 생성. 비용과 정확도의 최적 균형점.

**비용 추정 (10만 라인, 취약점 20건 기준)**:
- Semgrep: 무료 (오픈소스)
- Claude API: 취약점 20건 x 약 4,000 토큰 = 약 $0.5~1.0

### ADR-002: Railway + Supabase + Vercel 인프라 선택

**상태**: 확정 (PoC 단계)

**맥락**: PoC 단계에서 인프라 비용과 운영 부담을 최소화해야 함.

**결정**: Railway (Backend) + Supabase (PostgreSQL) + Vercel (Frontend) + Upstash (Redis)

**근거**:
- *Railway*: Docker 기반 배포가 간단하고, PoC 월 $5~20 예상. Semgrep CLI 실행 가능한 컨테이너 환경 제공. 워커 프로세스 별도 배포 가능.
- *Supabase*: 관리형 PostgreSQL. 무료 플랜으로 시작 가능. Row Level Security 등 보안 기능 내장.
- *Vercel*: Next.js 최적 배포 플랫폼. 무료 플랜으로 시작 가능.
- *Upstash*: 서버리스 Redis. 요청당 과금으로 PoC 단계 비용 최소.

**향후 전환 계획**: 유료 고객 10사 이상 시 AWS ECS Fargate + RDS 전환 검토.

### ADR-003: 코드 보안 처리 원칙

**상태**: 확정

**결정**:
1. 고객 코드는 스캔 처리 목적으로만 임시 클론
2. 스캔 완료 후 즉시 삭제 (파일시스템에서 `shutil.rmtree`)
3. 데이터베이스에는 취약 코드 스니펫(해당 라인 전후 5줄)만 저장
4. LLM API 호출 시 고객 코드가 학습 데이터로 사용되지 않도록 Anthropic API 정책 확인 및 계약 명시
5. 모든 코드 전송은 TLS 암호화

**검증 방법**:
- 스캔 완료 후 임시 디렉토리 삭제 확인 로그 기록
- 주기적으로 `/tmp/vulnix-scan-*` 잔존 파일 정리 cron 설정

---

## 6. PoC 아키텍처 (M1 범위)

### 6-1. M1 (PoC) 범위

PRD 9-2절 기준, 의도적으로 좁은 범위:

| 항목 | M1 범위 |
|------|---------|
| 언어 | Python만 |
| 취약점 | SQL Injection, XSS, Hardcoded Credentials (3가지) |
| 저장소 | GitHub만 |
| 기능 | Webhook 수신 -> Semgrep 스캔 -> Claude 분석 -> 패치 PR 생성 |
| 프론트엔드 | 최소 대시보드 (저장소 목록, 스캔 결과, 취약점 목록) |

### 6-2. M1 구현 컴포넌트

```
[M1 아키텍처 — 최소 구조]

+------------------+     +--------------------+     +-----------+
|  Next.js (Vercel)|---->|  FastAPI (Railway)  |---->| Supabase  |
|  - 로그인         |     |  - Webhook 수신     |     | PostgreSQL|
|  - 저장소 목록    |     |  - Semgrep 스캔     |     +-----------+
|  - 취약점 목록    |     |  - Claude 분석      |
|  - 스캔 결과      |     |  - PR 생성          |     +-----------+
+------------------+     |  - Dashboard API    |---->| Upstash   |
                         +--------------------+     | Redis     |
                                |                   +-----------+
                                v
                         +--------------------+
                         |   GitHub API       |
                         |   - Code Clone     |
                         |   - PR Create      |
                         +--------------------+
```

### 6-3. M1 제외 항목 (v1.0에서 추가)

- GitLab / Bitbucket 연동
- Python 외 언어 지원
- 3가지 외 추가 취약점 유형
- 오탐 피드백 학습 루프
- CISO 리포트 / PDF 생성
- 팀 관리 / 멤버 초대
- Slack / Teams 알림 연동

### 6-4. M1 성공 기준

PRD 9-4절 기준:

| 기준 | 목표값 |
|------|--------|
| 탐지 정확도 | 80% 이상 |
| 패치 PR 승인율 | 40% 이상 |
| 파일럿 고객 NPS | 30 이상 |
| 유료 전환 의향 | 3사 중 2사 이상 |

---

## 7. 디렉토리 구조

```
Vulnix/
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml            # 의존성 관리 (Poetry 또는 uv)
│   ├── alembic.ini               # DB 마이그레이션 설정
│   ├── alembic/
│   │   └── versions/             # 마이그레이션 파일
│   └── src/
│       ├── main.py               # FastAPI 앱 진입점
│       ├── config.py             # 환경 설정 (pydantic-settings)
│       ├── api/
│       │   ├── v1/
│       │   │   ├── router.py     # v1 라우터 집합
│       │   │   ├── webhooks.py   # GitHub Webhook 핸들러
│       │   │   ├── scans.py      # 스캔 관련 엔드포인트
│       │   │   ├── repos.py      # 저장소 관련 엔드포인트
│       │   │   ├── vulns.py      # 취약점 관련 엔드포인트
│       │   │   ├── patches.py    # 패치 PR 관련 엔드포인트
│       │   │   ├── dashboard.py  # 대시보드 통계 엔드포인트
│       │   │   └── auth.py       # 인증 관련 엔드포인트
│       │   └── deps.py           # 공통 의존성 (DB 세션, 인증 등)
│       ├── models/
│       │   ├── user.py
│       │   ├── team.py
│       │   ├── repository.py
│       │   ├── scan_job.py
│       │   ├── vulnerability.py
│       │   └── patch_pr.py
│       ├── schemas/               # Pydantic 요청/응답 스키마
│       │   ├── scan.py
│       │   ├── vulnerability.py
│       │   └── ...
│       ├── services/
│       │   ├── scan_orchestrator.py  # 스캔 작업 관리
│       │   ├── semgrep_engine.py     # Semgrep 실행 및 결과 파싱
│       │   ├── llm_agent.py          # Claude API 연동
│       │   ├── github_app.py         # GitHub App API 연동
│       │   ├── patch_generator.py    # 패치 PR 생성
│       │   └── auth_service.py       # 인증 서비스
│       ├── workers/
│       │   └── scan_worker.py        # Redis 큐 워커
│       └── rules/
│           ├── python/               # Python 커스텀 Semgrep 룰
│           │   ├── sql_injection.yml
│           │   ├── xss.yml
│           │   └── hardcoded_creds.yml
│           └── README.md
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   └── src/
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── page.tsx              # 랜딩 페이지
│       │   ├── login/
│       │   ├── dashboard/
│       │   ├── repos/
│       │   │   ├── page.tsx          # 저장소 목록
│       │   │   └── [id]/
│       │   │       └── page.tsx      # 저장소 상세
│       │   ├── vulnerabilities/
│       │   │   └── [id]/
│       │   │       └── page.tsx      # 취약점 상세
│       │   ├── scans/
│       │   │   └── [id]/
│       │   │       └── page.tsx      # 스캔 상세
│       │   └── settings/
│       ├── components/
│       │   ├── ui/                   # shadcn/ui 컴포넌트
│       │   ├── dashboard/
│       │   ├── vulnerability/
│       │   └── layout/
│       └── lib/
│           ├── api-client.ts         # Backend API 클라이언트
│           ├── auth.ts               # 인증 유틸
│           └── utils.ts
├── docs/
│   ├── PRD_security_patch_agent.md
│   ├── system/
│   │   └── system-design.md          # 이 문서
│   ├── specs/                        # 기능별 상세 설계
│   ├── api/                          # API 스펙 확정본
│   └── db/                           # DB 스키마 확정본
├── .github/
│   └── workflows/
│       └── ci.yml                    # CI 파이프라인
├── docker-compose.yml                # 로컬 개발 환경
└── .env.example                      # 환경변수 템플릿
```

---

## 8. 개발 환경 구성

### 8-1. 로컬 실행 방법

```bash
# 1. 저장소 클론
git clone https://github.com/org/Vulnix.git
cd Vulnix

# 2. Backend
cd backend
cp .env.example .env  # 환경변수 설정
pip install -e ".[dev]"  # 또는 poetry install
uvicorn src.main:app --reload --port 8000

# 3. 워커 (별도 터미널)
cd backend
python -m src.workers.scan_worker

# 4. Frontend
cd frontend
npm install
npm run dev  # http://localhost:3000

# 5. 로컬 인프라 (PostgreSQL + Redis)
docker-compose up -d
```

### 8-2. 필수 환경변수

```bash
# Backend
DATABASE_URL=postgresql://user:pass@localhost:5432/vulnix
REDIS_URL=redis://localhost:6379

# GitHub App
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n..."
GITHUB_WEBHOOK_SECRET=your-webhook-secret
GITHUB_CLIENT_ID=Iv1.xxxxxxxx
GITHUB_CLIENT_SECRET=xxxxxxxx

# Claude API
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx

# JWT
JWT_SECRET_KEY=your-jwt-secret
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 8-3. 테스트 전략

| 레벨 | 도구 | 대상 |
|------|------|------|
| 단위 테스트 | pytest | 서비스 로직, Semgrep 결과 파싱, LLM 응답 파싱 |
| 통합 테스트 | pytest + httpx | API 엔드포인트, DB 연동 |
| E2E 테스트 | Playwright | 프론트엔드 핵심 흐름 |
| 보안 테스트 | Semgrep (자체 적용) | 자사 코드 보안 검증 |

**테스트 실행**:

```bash
# Backend 단위 + 통합 테스트
cd backend && pytest

# Frontend E2E 테스트
cd frontend && npx playwright test
```

### 8-4. DB 마이그레이션

- ORM: SQLAlchemy 2.0
- 마이그레이션: Alembic
- 전략: 모든 스키마 변경은 Alembic 마이그레이션으로 관리

```bash
# 마이그레이션 생성
cd backend && alembic revision --autogenerate -m "description"

# 마이그레이션 적용
cd backend && alembic upgrade head
```

---

## 9. 보안 원칙

### 9-1. 인증/인가

- 사용자 인증: GitHub OAuth 2.0
- API 인증: JWT (Access Token 30분 + Refresh Token 7일)
- Webhook 인증: HMAC-SHA256 서명 검증
- 팀 기반 권한: Owner / Admin / Member

### 9-2. 데이터 보안

- 고객 코드: 스캔 후 즉시 삭제
- GitHub Access Token: AES-256 암호화 후 DB 저장
- 모든 외부 통신: TLS 1.2+
- 환경변수: `.env` 파일 (Git 미포함), 배포 시 플랫폼 시크릿 관리

### 9-3. CORS 정책

```python
# PoC 단계
origins = [
    "http://localhost:3000",        # 로컬 개발
    "https://vulnix.vercel.app",    # 프로덕션
]
```
