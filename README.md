# Vulnix

> AI 기반 보안 취약점 탐지 & 자동 패치 SaaS

코드 저장소를 연동하면 Semgrep + Claude AI가 취약점을 찾아 **패치 PR까지 자동으로 생성**해주는 개발자용 보안 에이전트입니다.

기존 SAST 도구(Veracode, Checkmarx)가 취약점 **발견**에 그치는 반면, Vulnix는 **수분 내에 패치 PR까지** 제출합니다.

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| **자동 스캔 트리거** | PR 생성 / 브랜치 푸시 시 GitHub/GitLab/Bitbucket Webhook으로 자동 실행 |
| **2단계 탐지 엔진** | Semgrep 룰 기반 1차 AST 분석 → Claude API 2차 컨텍스트 분석으로 오탐 최소화 |
| **자동 패치 PR** | 탐지된 취약점별로 LLM이 패치 코드 생성, 코드 스타일 유지, PR 자동 제출 |
| **다국어 지원** | Python, JavaScript/TypeScript, Java, Go |
| **OWASP Top 10** | SQL Injection, XSS, Hardcoded Credentials, 인증/인가 취약점, 암호화 취약점 등 |
| **오탐 관리** | 개발자 오탐 마킹 → 패턴 학습 → 팀 단위 규칙 공유 |
| **보안 대시보드** | 저장소/팀별 보안 점수, 취약점 추이 그래프, 심각도별 분포 |
| **알림 연동** | Slack Block Kit / Microsoft Teams Adaptive Cards, 주간 리포트 자동 발송 |
| **CISO 리포트** | PDF 자동 생성, CSAP / ISO 27001 / ISMS 인증 증적 자료 출력 |
| **IDE 플러그인** | VS Code 파일 저장 시 자동 분석, 인라인 취약점 하이라이팅, 전구 클릭으로 패치 즉시 적용 |

---

## 아키텍처

```
GitHub / GitLab / Bitbucket
        │ Webhook
        ▼
┌─────────────────────────────────────┐
│            FastAPI Backend           │
│                                     │
│  Webhook Handler → Scan Orchestrator│
│       ↓                             │
│  Semgrep Engine (1차 AST 분석)       │
│       ↓                             │
│  Claude API (2차 컨텍스트 분석)       │
│       ↓                             │
│  Patch Generator → GitHub PR 생성   │
│       ↓                             │
│  Notification Service (Slack/Teams) │
└─────────────────────────────────────┘
        │
        ▼
  PostgreSQL + Redis
        │
        ▼
┌─────────────────┐
│  Next.js Frontend│
│  (대시보드 UI)    │
└─────────────────┘
```

---

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| Backend | Python 3.11, FastAPI, SQLAlchemy (async), Alembic |
| 탐지 엔진 | Semgrep (오픈소스 룰) + Claude API (claude-sonnet) |
| 저장소 연동 | GitHub App API, GitLab REST API v4, Bitbucket REST API |
| DB | PostgreSQL 16, Redis 7 |
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| 인증 | JWT (Access/Refresh Token), API Key (SHA-256 해시) |
| 보안 | Fernet 암호화 (PAT/App Password), SSRF 방어 |
| VS Code 익스텐션 | TypeScript, VS Code Extension API, Jest |

---

## 빠른 시작

### 사전 요구사항

- Python 3.11+
- Docker & Docker Compose
- Node.js 18+
- [Semgrep CLI](https://semgrep.dev/docs/getting-started/) (`pip install semgrep`)
- Anthropic API 키

### 1. 저장소 클론

```bash
git clone https://github.com/jsong1230/Vulnix.git
cd Vulnix
```

### 2. 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 필수 값 입력
```

주요 환경변수:

```dotenv
DATABASE_URL=postgresql+asyncpg://vulnix:vulnix_dev@localhost:5432/vulnix
REDIS_URL=redis://localhost:6379

GITHUB_APP_ID=
GITHUB_APP_PRIVATE_KEY=
GITHUB_WEBHOOK_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=

ANTHROPIC_API_KEY=sk-ant-...

JWT_SECRET_KEY=your-super-secret-key
```

### 3. DB & Redis 실행

```bash
docker compose up -d
```

### 4. 백엔드 실행

```bash
cd backend
pip install -e ".[dev]"

# DB 마이그레이션
alembic upgrade head

# 개발 서버 실행
uvicorn src.main:app --reload --port 8000
```

### 5. 프론트엔드 실행

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
# http://localhost:3000
```

API 문서: http://localhost:8000/docs

### 6. VS Code 익스텐션 설치 (개발 모드)

```bash
cd vscode-extension
npm install
npm run compile

# VS Code에서 F5 → "Run Extension" 선택
```

VS Code 설정 (`settings.json`):

```json
{
  "vulnix.serverUrl": "http://localhost:8000",
  "vulnix.apiKey": "vx_live_...",
  "vulnix.analyzeOnSave": true,
  "vulnix.severityFilter": "all"
}
```

API Key는 대시보드 또는 API로 발급:

```bash
curl -X POST http://localhost:8000/api/v1/ide/api-keys \
  -H "Authorization: Bearer {JWT}" \
  -d '{"name": "My IDE Key", "expires_in_days": 365}'
```

---

## 프로젝트 구조

```
Vulnix/
├── backend/
│   ├── src/
│   │   ├── api/v1/          # REST API 엔드포인트
│   │   │   ├── repos.py         # 저장소 연동 (GitHub)
│   │   │   ├── repos_gitlab.py  # GitLab 연동
│   │   │   ├── repos_bitbucket.py # Bitbucket 연동
│   │   │   ├── scans.py         # 스캔 관리
│   │   │   ├── vulns.py         # 취약점 목록/상세
│   │   │   ├── patches.py       # 패치 PR 관리
│   │   │   ├── dashboard.py     # 대시보드
│   │   │   ├── notifications.py # Slack/Teams 알림
│   │   │   ├── reports.py       # CISO 리포트
│   │   │   └── ide.py           # IDE 플러그인 API
│   │   ├── services/        # 비즈니스 로직
│   │   │   ├── semgrep_engine.py    # Semgrep 1차 분석
│   │   │   ├── llm_agent.py         # Claude API 2차 분석
│   │   │   ├── patch_generator.py   # 패치 코드 생성
│   │   │   ├── notification_service.py # Slack/Teams 발송
│   │   │   ├── report_renderer.py   # PDF 리포트 생성
│   │   │   ├── token_crypto.py      # PAT 암호화 (Fernet)
│   │   │   └── ide_analyzer.py      # IDE 실시간 분석
│   │   ├── models/          # SQLAlchemy ORM 모델
│   │   ├── schemas/         # Pydantic 스키마
│   │   ├── rules/           # 언어별 Semgrep 룰셋
│   │   │   ├── python/
│   │   │   ├── javascript/
│   │   │   ├── java/
│   │   │   └── go/
│   │   └── workers/         # RQ 백그라운드 워커
│   ├── alembic/             # DB 마이그레이션
│   └── tests/               # pytest 테스트 (518 케이스)
├── frontend/
│   └── src/
│       ├── app/             # Next.js App Router 페이지
│       └── components/      # UI 컴포넌트
├── vscode-extension/
│   ├── src/
│   │   ├── extension.ts         # 진입점 (activate/deactivate)
│   │   ├── config.ts            # 설정 관리 (serverUrl, apiKey)
│   │   ├── api/
│   │   │   ├── client.ts        # HTTP 클라이언트 (X-API-Key 인증)
│   │   │   └── types.ts         # Finding, AnalyzeRequest 등 타입
│   │   ├── analyzer/
│   │   │   ├── analyzer.ts      # 분석 오케스트레이터 (500ms 디바운스)
│   │   │   └── fp-cache.ts      # 오탐 패턴 캐시 (5분 주기 동기화)
│   │   ├── diagnostics/
│   │   │   ├── diagnostics.ts       # DiagnosticCollection 관리
│   │   │   └── diagnostic-mapper.ts # Finding → vscode.Diagnostic 변환
│   │   ├── code-actions/
│   │   │   ├── code-actions.ts  # CodeActionProvider (전구 아이콘)
│   │   │   └── patch-applier.ts # unified diff → WorkspaceEdit 적용
│   │   ├── webview/
│   │   │   ├── webview.ts       # 취약점 상세 WebviewPanel
│   │   │   └── panel-content.ts # HTML 생성 (XSS 이스케이프)
│   │   └── status/
│   │       └── status-bar.ts    # 상태 표시줄 (연결/오프라인/분석중)
│   ├── test/
│   │   ├── suite/               # Jest 단위 테스트 (62 케이스)
│   │   └── fixtures/            # 테스트 픽스처 (취약 코드, API 응답)
│   └── package.json
├── docs/
│   ├── project/             # PRD, 기능 백로그, 로드맵
│   ├── specs/               # 기능별 설계 문서
│   └── api/                 # API 명세
└── docker-compose.yml
```

---

## API 개요

전체 엔드포인트 목록은 서버 실행 후 `/docs`에서 확인할 수 있습니다.

| 그룹 | 엔드포인트 | 설명 |
|------|-----------|------|
| 저장소 | `POST /api/v1/repos` | GitHub 저장소 연동 |
| 저장소 | `POST /api/v1/repos/gitlab` | GitLab 저장소 연동 |
| 저장소 | `POST /api/v1/repos/bitbucket` | Bitbucket 저장소 연동 |
| 스캔 | `POST /api/v1/scans` | 수동 스캔 트리거 |
| 스캔 | `GET /api/v1/scans/{id}` | 스캔 상태 조회 |
| 취약점 | `GET /api/v1/vulnerabilities` | 취약점 목록 (필터/페이지네이션) |
| 취약점 | `PATCH /api/v1/vulnerabilities/{id}` | 상태 변경 (오탐 마킹 등) |
| 패치 | `GET /api/v1/patches` | 패치 PR 목록 |
| 대시보드 | `GET /api/v1/dashboard/summary` | 팀 보안 현황 요약 |
| 알림 | `POST /api/v1/notifications` | Slack/Teams Webhook 등록 |
| 리포트 | `POST /api/v1/reports/generate` | CISO 리포트 PDF 생성 |
| IDE | `POST /api/v1/ide/analyze` | 코드 스니펫 실시간 분석 |
| IDE | `POST /api/v1/ide/api-keys` | IDE API Key 발급 |

---

## 테스트 실행

```bash
# 백엔드
cd backend
pytest tests/ -v
# 518 tests, 0 failures

# VS Code 익스텐션
cd vscode-extension
npm test
# 62 tests, 0 failures
```

---

## 배포

권장 스택: **Railway** (백엔드) + **Vercel** (프론트엔드) + **Supabase** (PostgreSQL) + **Upstash** (Redis)

### 백엔드 — Railway

**1. Docker 이미지 빌드**

```bash
cd backend
docker build -t vulnix-backend .
```

**2. Railway 프로젝트 생성 및 배포**

```bash
# Railway CLI 설치
npm install -g @railway/cli

railway login
railway init
railway up
```

**3. Railway 환경변수 설정**

```dotenv
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/vulnix
REDIS_URL=redis://default:pass@host:port

GITHUB_APP_ID=
GITHUB_APP_PRIVATE_KEY=
GITHUB_WEBHOOK_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=

ANTHROPIC_API_KEY=

JWT_SECRET_KEY=        # openssl rand -hex 32
TOKEN_ENCRYPTION_KEY=  # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

CORS_ORIGINS=https://your-app.vercel.app
APP_ENV=production
DEBUG=false
```

**4. DB 마이그레이션**

```bash
railway run alembic upgrade head
```

**5. 워커 프로세스 추가** (Railway 서비스 하나 더 생성)

```bash
# Start Command:
python -m src.workers.scan_worker
```

---

### 프론트엔드 — Vercel

```bash
cd frontend
npm install -g vercel

vercel
# 또는 GitHub 저장소 연결 후 자동 배포
```

Vercel 환경변수:

```dotenv
NEXT_PUBLIC_API_URL=https://your-backend.railway.app
```

---

### DB — Supabase

1. [supabase.com](https://supabase.com) 에서 프로젝트 생성
2. `Settings → Database` 에서 Connection String 복사
3. `DATABASE_URL`에 `postgresql+asyncpg://...` 형식으로 설정

---

### Redis — Upstash

1. [upstash.com](https://upstash.com) 에서 Redis 데이터베이스 생성
2. `REDIS_URL`에 `redis://default:...@...upstash.io:port` 설정

---

### GitHub App 설정

1. GitHub → Settings → Developer settings → GitHub Apps → New GitHub App
2. 아래 권한 설정:
   - **Repository permissions**: Contents (Read & Write), Pull requests (Read & Write), Webhooks (Read & Write)
   - **Subscribe to events**: Push, Pull request
3. Webhook URL: `https://your-backend.railway.app/api/v1/webhooks/github`
4. Private key 생성 후 `GITHUB_APP_PRIVATE_KEY`에 PEM 내용 설정

---

### 프로덕션 체크리스트

- [ ] `JWT_SECRET_KEY` — `openssl rand -hex 32` 로 생성
- [ ] `TOKEN_ENCRYPTION_KEY` — Fernet 키 생성 (위 명령 참고)
- [ ] `DEBUG=false`, `APP_ENV=production`
- [ ] `CORS_ORIGINS` — 실제 프론트엔드 도메인만 허용
- [ ] HTTPS 적용 (Railway/Vercel 자동 제공)
- [ ] GitHub App Webhook Secret 설정

---

## VS Code 익스텐션

### 동작 방식

```
파일 저장
  └─ 500ms 디바운스
       └─ POST /api/v1/ide/analyze (Semgrep, <500ms)
            └─ 오탐 패턴 로컬 필터링
                 └─ 빨간/노란 밑줄 표시

전구 아이콘 클릭 → "Vulnix: Apply Patch Fix"
  └─ POST /api/v1/ide/patch-suggestion (Claude API)
       └─ unified diff 파싱 → WorkspaceEdit 적용
```

### 지원 기능

| 기능 | 설명 |
|------|------|
| 자동 분석 | 파일 저장 시 Semgrep 기반 취약점 즉시 탐지 |
| 인라인 하이라이팅 | critical/high → 빨간 밑줄, medium → 노란 밑줄, low → 파란 밑줄 |
| 패치 적용 | 전구 아이콘 클릭 → LLM 패치 생성 → 코드 한 번에 수정 |
| 상세 패널 | 취약점 유형, CWE/OWASP 분류, 코드 스니펫, 패치 diff 표시 |
| 오탐 동기화 | 팀 오탐 패턴 5분 주기 자동 동기화 (ETag 캐싱) |
| 상태 표시줄 | `$(shield) Vulnix: 3 issue(s)` — 연결/분석중/오프라인 상태 |

### 지원 언어

Python, JavaScript, TypeScript, Java, Go

### VS Code 명령 팔레트

| 명령 | 설명 |
|------|------|
| `Vulnix: Analyze Current File` | 현재 파일 수동 분석 |
| `Vulnix: Apply Patch Fix` | 커서 위치 취약점 패치 적용 |
| `Vulnix: Show Vulnerability Detail` | 상세 패널 열기 |
| `Vulnix: Sync False Positive Patterns` | 오탐 패턴 수동 동기화 |
| `Vulnix: Clear All Diagnostics` | 진단 전체 초기화 |

---

## 로드맵

| 마일스톤 | 내용 | 상태 |
|----------|------|------|
| M1 | GitHub 연동, Python 탐지 엔진, 패치 PR, 기본 UI | ✅ 완료 |
| M2 | 다국어 확장, 오탐 관리, 대시보드, Slack/Teams 알림 | ✅ 완료 |
| M3 | GitLab/Bitbucket 연동, CISO 리포트, IDE 플러그인 | ✅ 완료 |

---

## 라이선스

MIT
