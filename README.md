# Vulnix

> **AI 기반 보안 취약점 탐지 & 자동 패치 에이전트**

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=nextdotjs)](https://nextjs.org)
[![Tests](https://img.shields.io/badge/Tests-518%20passed-brightgreen)](#테스트-실행)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

코드 저장소를 연동하면 **Semgrep + Claude AI** 2단계 엔진이 취약점을 찾고, **패치 PR까지 자동으로 생성**해주는 개발자용 보안 에이전트 SaaS입니다.

---

## 왜 Vulnix인가?

기존 SAST 도구(Veracode, Checkmarx, Fortify)의 두 가지 결정적 한계:

| 문제 | 기존 도구 | Vulnix |
|------|-----------|--------|
| 취약점 발견만 하고 수정 방법 없음 | 보안팀 → 개발팀 → 컨설턴트 3단계 비효율 | **탐지부터 패치 PR까지 수분 내 자동 완료** |
| 오탐율 30~60% | 개발자가 경고를 무시하게 됨 | **2단계 LLM 검증으로 오탐 최소화** |
| 연 수천만~수억 원 라이선스 | 중소기업은 엄두도 못 냄 | **기존 대비 1/5 수준의 비용** |

취약점 발견 → 패치 완료까지 기존 60~90일 → **Vulnix로 당일 처리**.

---

## 주요 기능

### 탐지 엔진
- **2단계 하이브리드 분석**: Semgrep 룰 기반 1차 AST 탐지 → Claude API 2차 컨텍스트 검증
- **다국어 지원**: Python / JavaScript / TypeScript / Java / Go
- **OWASP Top 10 전체 커버**: SQL Injection, XSS, Hardcoded Credentials, 인증/인가 취약점, 암호화 취약점, 보안 설정 오류 등
- **CWE / OWASP 자동 매핑**: 탐지된 취약점마다 CWE ID와 OWASP 카테고리 자동 부여

### 자동화
- **Webhook 기반 자동 스캔**: PR 생성 / 브랜치 푸시 시 자동 실행 (GitHub / GitLab / Bitbucket)
- **패치 PR 자동 생성**: LLM이 기존 코드 스타일 유지하며 패치 코드 작성, PR 자동 제출
- **주간 보안 리포트 자동 발송**: Slack / Teams으로 팀별 보안 현황 자동 공유

### 관리 & 리포팅
- **보안 점수**: `100 - (critical×25 + high×10 + medium×5 + low×1)` 공식으로 저장소/팀별 점수화
- **CISO 리포트 PDF**: CSAP / ISO 27001 / ISMS 인증 증적 자료 자동 생성
- **오탐 관리**: 오탐 마킹 → 패턴 학습 → 팀 단위 규칙 공유로 오탐율 지속 개선

### IDE 통합
- **VS Code 익스텐션**: 파일 저장 시 실시간 분석, 빨간/노란 밑줄 하이라이팅
- **인라인 패치 적용**: 전구 아이콘 클릭 → LLM 패치 생성 → 코드 자동 수정

---

## 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│                        클라이언트 레이어                        │
│                                                              │
│   GitHub / GitLab / Bitbucket      VS Code 익스텐션            │
│         (Webhook 이벤트)              (X-API-Key)              │
└────────────────┬─────────────────────────┬───────────────────┘
                 │ HTTPS                   │ HTTPS
                 ▼                         ▼
┌──────────────────────────────────────────────────────────────┐
│                      FastAPI Backend (Railway)                │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  Webhook    │  │  REST API    │  │  IDE API           │  │
│  │  Handler    │  │  (JWT 인증)  │  │  (API Key 인증)    │  │
│  └──────┬──────┘  └──────┬───────┘  └─────────┬──────────┘  │
│         │                │                    │             │
│         └────────────────┼────────────────────┘             │
│                          │                                  │
│                 ┌─────────▼────────┐                        │
│                 │ Scan Orchestrator│                        │
│                 │  (Redis Queue)   │                        │
│                 └─────────┬────────┘                        │
│                           │                                 │
│          ┌────────────────┼──────────────────┐              │
│          ▼                ▼                  ▼              │
│  ┌──────────────┐ ┌──────────────┐  ┌──────────────────┐   │
│  │  Semgrep     │ │  Claude API  │  │  Patch Generator │   │
│  │  Engine      │ │  LLM Agent   │  │  (PR 자동 생성)  │   │
│  │  (1차 탐지)  │ │  (2차 검증)  │  └────────┬─────────┘   │
│  └──────────────┘ └──────────────┘           │             │
│                                              │             │
│  ┌──────────────────────────────────────┐    │             │
│  │  Notification Service                │    │             │
│  │  (Slack Block Kit / Teams Adaptive)  │    │             │
│  └──────────────────────────────────────┘    │             │
└──────────────────────┬───────────────────────┼─────────────┘
                       │                       │ GitHub/GitLab/Bitbucket API
              ┌────────▼────────┐              ▼
              │  PostgreSQL     │      ┌───────────────┐
              │  (Supabase)     │      │  Patch PR     │
              ├─────────────────┤      │  생성 완료    │
              │  Redis          │      └───────────────┘
              │  (Upstash)      │
              └─────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Next.js        │
              │  Dashboard      │
              │  (Vercel)       │
              └─────────────────┘
```

### 스캔 처리 흐름

```
1. Webhook 수신 (PR 생성 / 브랜치 푸시)
        ↓
2. Redis 큐에 스캔 작업 등록 (비동기)
        ↓
3. 스캔 워커가 작업 수신
        ↓
4. Semgrep 1차 분석
   - 언어별 커스텀 룰셋 적용
   - AST 기반 패턴 매칭
   - 후보 취약점 목록 추출
        ↓
5. Claude API 2차 분석
   - 각 후보의 코드 컨텍스트 분석
   - 오탐 여부 판단
   - 취약점 심각도 최종 결정
   - 패치 코드 생성
        ↓
6. 패치 PR 자동 생성
   - 취약점별 브랜치 생성
   - 패치 코드 커밋
   - PR 생성 (취약점 설명 + diff 포함)
        ↓
7. Slack/Teams 알림 발송
8. 대시보드에 결과 반영
```

---

## 기술 스택

| 레이어 | 기술 | 용도 |
|--------|------|------|
| **Backend** | Python 3.11, FastAPI | API 서버, 스캔 오케스트레이션 |
| **ORM / DB** | SQLAlchemy 2.0 (async), Alembic | 비동기 DB 접근, 마이그레이션 |
| **탐지 엔진** | Semgrep (오픈소스 룰) | 1차 AST 기반 정적 분석 |
| **AI 에이전트** | Claude API (claude-sonnet) | 2차 오탐 검증 + 패치 코드 생성 |
| **저장소 연동** | GitHub App API, GitLab REST API v4, Bitbucket REST API | Webhook 수신, PR 생성 |
| **DB** | PostgreSQL 16 (Supabase) | 취약점/스캔 이력 저장 |
| **큐 / 캐시** | Redis 7 (Upstash), RQ | 스캔 작업 큐, 세션 캐시 |
| **Frontend** | Next.js 14 (App Router), Tailwind CSS, TanStack Query | 대시보드 UI |
| **인증** | JWT (Access/Refresh Token), API Key (SHA-256 해시) | 사용자/IDE 인증 |
| **보안** | Fernet 암호화, SSRF 방어, HMAC-SHA256 Webhook 검증 | PAT 암호화, 내부 IP 차단 |
| **VS Code 익스텐션** | TypeScript, VS Code Extension API | 실시간 IDE 분석 |
| **테스트** | pytest (백엔드), Jest (익스텐션) | 518 + 62 케이스 |
| **인프라** | Railway, Vercel, Docker | 백엔드/프론트엔드 배포 |

---

## 빠른 시작

### 사전 요구사항

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Semgrep CLI (`pip install semgrep`)
- Anthropic API 키 ([console.anthropic.com](https://console.anthropic.com))
- GitHub App (또는 GitLab/Bitbucket 토큰)

### 1. 저장소 클론

```bash
git clone https://github.com/jsong1230/Vulnix.git
cd Vulnix
```

### 2. 인프라 실행 (PostgreSQL + Redis)

```bash
docker compose up -d
# PostgreSQL: localhost:5432, Redis: localhost:6379
```

### 3. 백엔드 설정

```bash
cd backend

# 의존성 설치
pip install -e ".[dev]"

# 환경변수 설정
cp .env.example .env
# .env 파일에 ANTHROPIC_API_KEY, GITHUB_APP_ID 등 입력

# DB 마이그레이션
alembic upgrade head

# API 서버 실행
uvicorn src.main:app --reload --port 8000
```

백엔드 API 문서: **http://localhost:8000/docs**

별도 터미널에서 스캔 워커 실행:

```bash
cd backend
python -m src.workers.scan_worker
```

### 4. 프론트엔드 설정

```bash
cd frontend

npm install

cp .env.example .env.local
# NEXT_PUBLIC_API_URL=http://localhost:8000

npm run dev
# http://localhost:3000
```

### 5. VS Code 익스텐션 설치 (선택)

```bash
cd vscode-extension
npm install
npm run compile

# VS Code에서 F5 → "Run Extension" 선택
```

`settings.json` 설정:

```json
{
  "vulnix.serverUrl": "http://localhost:8000",
  "vulnix.apiKey": "vx_live_...",
  "vulnix.analyzeOnSave": true,
  "vulnix.severityFilter": "all"
}
```

API Key 발급:

```bash
# 먼저 로그인하여 JWT 획득
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "..."}'

# API Key 발급
curl -X POST http://localhost:8000/api/v1/ide/api-keys \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"name": "My IDE Key", "expires_in_days": 365}'
```

---

## 환경변수 상세

### 백엔드 (`backend/.env`)

```dotenv
# ── 데이터베이스 ──────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://vulnix:vulnix_dev@localhost:5432/vulnix

# ── Redis (스캔 큐) ───────────────────────────────────────────
REDIS_URL=redis://localhost:6379

# ── GitHub App ───────────────────────────────────────────────
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET=your-webhook-secret
GITHUB_CLIENT_ID=Iv1.xxxxxxxxxxxx
GITHUB_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ── Claude API ───────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ── 인증 ─────────────────────────────────────────────────────
JWT_SECRET_KEY=                  # openssl rand -hex 32
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ── 보안 암호화 ───────────────────────────────────────────────
TOKEN_ENCRYPTION_KEY=            # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# ── CORS / 앱 설정 ────────────────────────────────────────────
CORS_ORIGINS=http://localhost:3000
APP_ENV=development
DEBUG=true
```

### 프론트엔드 (`frontend/.env.local`)

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## API 레퍼런스

전체 Swagger 문서: `http://localhost:8000/docs`

### 인증

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| `POST` | `/api/v1/auth/register` | 회원가입 |
| `POST` | `/api/v1/auth/login` | 로그인 (JWT 발급) |
| `POST` | `/api/v1/auth/refresh` | Access Token 갱신 |
| `GET`  | `/api/v1/auth/github` | GitHub OAuth 로그인 |

### 저장소 연동

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| `GET`  | `/api/v1/repos` | 연동된 저장소 목록 |
| `POST` | `/api/v1/repos` | GitHub 저장소 연동 |
| `DELETE` | `/api/v1/repos/{id}` | 저장소 연동 해제 |
| `POST` | `/api/v1/repos/gitlab` | GitLab 저장소 연동 |
| `POST` | `/api/v1/repos/bitbucket` | Bitbucket 저장소 연동 |

### 스캔

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| `POST` | `/api/v1/scans` | 수동 스캔 트리거 |
| `GET`  | `/api/v1/scans` | 스캔 목록 |
| `GET`  | `/api/v1/scans/{id}` | 스캔 상태/결과 조회 |

### 취약점

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| `GET`  | `/api/v1/vulnerabilities` | 취약점 목록 (심각도/상태/언어 필터, 페이지네이션) |
| `GET`  | `/api/v1/vulnerabilities/{id}` | 취약점 상세 |
| `PATCH` | `/api/v1/vulnerabilities/{id}` | 상태 변경 (`open` / `fixed` / `false_positive` / `accepted_risk`) |

### 패치 PR

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| `GET`  | `/api/v1/patches` | 패치 PR 목록 |
| `GET`  | `/api/v1/patches/{id}` | 패치 PR 상세 (diff 포함) |
| `POST` | `/api/v1/patches/{id}/retry` | 패치 재생성 |

### 대시보드

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| `GET`  | `/api/v1/dashboard/summary` | 팀 보안 현황 요약 (보안 점수, 취약점 수) |
| `GET`  | `/api/v1/dashboard/trend` | 기간별 취약점 추이 |
| `GET`  | `/api/v1/dashboard/repo-scores` | 저장소별 보안 점수 |
| `GET`  | `/api/v1/dashboard/severity-distribution` | 심각도별 분포 |

### 오탐 관리

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| `GET`  | `/api/v1/false-positives` | 팀 오탐 패턴 목록 |
| `POST` | `/api/v1/false-positives` | 오탐 패턴 등록 |
| `PATCH` | `/api/v1/false-positives/{id}` | 패턴 수정 |
| `DELETE` | `/api/v1/false-positives/{id}` | 패턴 삭제 |

### 알림

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| `GET`  | `/api/v1/notifications` | 알림 설정 목록 |
| `POST` | `/api/v1/notifications` | Slack/Teams Webhook 등록 |
| `PATCH` | `/api/v1/notifications/{id}` | 알림 설정 수정 |
| `DELETE` | `/api/v1/notifications/{id}` | 알림 설정 삭제 |
| `POST` | `/api/v1/notifications/{id}/test` | 테스트 메시지 발송 |

### 리포트

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| `POST` | `/api/v1/reports/generate` | CISO 리포트 PDF 생성 (`csap` / `iso27001` / `isms`) |
| `GET`  | `/api/v1/reports` | 리포트 생성 이력 |
| `GET`  | `/api/v1/reports/{id}/download` | PDF 다운로드 |

### IDE (API Key 인증)

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| `POST` | `/api/v1/ide/analyze` | 코드 스니펫 실시간 분석 (Semgrep, p95 < 500ms) |
| `GET`  | `/api/v1/ide/false-positive-patterns` | 팀 오탐 패턴 조회 (ETag 캐싱) |
| `POST` | `/api/v1/ide/patch-suggestion` | LLM 패치 제안 생성 |
| `GET`  | `/api/v1/ide/api-keys` | API Key 목록 |
| `POST` | `/api/v1/ide/api-keys` | API Key 발급 |
| `DELETE` | `/api/v1/ide/api-keys/{id}` | API Key 비활성화 |

---

## 취약점 탐지 상세

### 지원 언어 및 룰셋

| 언어 | 탐지 유형 |
|------|-----------|
| **Python** | SQL Injection, XSS, Hardcoded Credentials |
| **JavaScript / TypeScript** | SQL Injection, XSS, Hardcoded Credentials, Insecure JWT, 보안 설정 오류 |
| **Java** | SQL Injection, XSS, Hardcoded Credentials, 취약한 암호화 |
| **Go** | SQL Injection, Command Injection, Hardcoded Credentials, 취약한 암호화 |

### 심각도 분류

| 심각도 | 보안 점수 감점 | 예시 |
|--------|--------------|------|
| **Critical** | -25점 | OS Command Injection, Auth Bypass |
| **High** | -10점 | SQL Injection, XXE, SSRF |
| **Medium** | -5점 | XSS, IDOR, Insecure Deserialization |
| **Low** | -1점 | Hardcoded Credentials, 취약한 Hash 알고리즘 |
| **Informational** | -0점 | 코드 품질 이슈 |

### 보안 점수 계산

```
보안 점수 = max(0, 100 - (Critical×25 + High×10 + Medium×5 + Low×1))
```

---

## VS Code 익스텐션

### 동작 흐름

```
파일 저장 (Cmd+S / Ctrl+S)
  └─ 500ms 디바운스 (연속 저장 최적화)
       └─ POST /api/v1/ide/analyze (Semgrep 분석, p95 < 500ms)
            └─ 팀 오탐 패턴으로 로컬 필터링
                 └─ vscode.DiagnosticCollection 업데이트
                      └─ 인라인 밑줄 표시
                           ├─ critical / high → 빨간 밑줄 (Error)
                           ├─ medium → 노란 밑줄 (Warning)
                           └─ low → 파란 밑줄 (Information)

전구 아이콘 클릭 → "Vulnix: Apply Patch Fix"
  └─ POST /api/v1/ide/patch-suggestion (Claude API, 2~10초)
       └─ unified diff 파싱
            └─ WorkspaceEdit 생성
                 └─ workspace.applyEdit() → 코드 자동 수정
                      └─ 해당 진단 자동 제거
```

### 설정 옵션

| 설정 키 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| `vulnix.serverUrl` | string | `https://api.vulnix.dev` | Vulnix 서버 URL |
| `vulnix.apiKey` | string | `""` | 팀 API Key (`vx_live_...`) |
| `vulnix.analyzeOnSave` | boolean | `true` | 파일 저장 시 자동 분석 |
| `vulnix.severityFilter` | enum | `"all"` | 표시 최소 심각도 (`all` / `high` / `critical`) |

### 명령 팔레트 (`Cmd+Shift+P` / `Ctrl+Shift+P`)

| 명령 | 설명 |
|------|------|
| `Vulnix: Analyze Current File` | 현재 파일 수동 분석 |
| `Vulnix: Apply Patch Fix` | 커서 위치 취약점 패치 적용 |
| `Vulnix: Show Vulnerability Detail` | 취약점 상세 패널 열기 (CWE, OWASP, 패치 diff) |
| `Vulnix: Sync False Positive Patterns` | 팀 오탐 패턴 수동 동기화 |
| `Vulnix: Clear All Diagnostics` | 진단 전체 초기화 |

### 지원 언어

Python, JavaScript, TypeScript, Java, Go

---

## 프로젝트 구조

```
Vulnix/
├── backend/
│   ├── src/
│   │   ├── api/v1/
│   │   │   ├── auth.py              # 회원가입/로그인/OAuth
│   │   │   ├── repos.py             # GitHub 저장소 연동
│   │   │   ├── repos_gitlab.py      # GitLab 저장소 연동
│   │   │   ├── repos_bitbucket.py   # Bitbucket 저장소 연동
│   │   │   ├── webhooks.py          # GitHub Webhook (HMAC-SHA256)
│   │   │   ├── webhooks_gitlab.py   # GitLab Webhook (X-Gitlab-Token)
│   │   │   ├── webhooks_bitbucket.py # Bitbucket Webhook (HMAC-SHA256)
│   │   │   ├── scans.py             # 스캔 관리
│   │   │   ├── vulns.py             # 취약점 목록/상세/상태변경
│   │   │   ├── patches.py           # 패치 PR 관리
│   │   │   ├── dashboard.py         # 보안 점수/추이/분포
│   │   │   ├── false_positives.py   # 오탐 패턴 CRUD
│   │   │   ├── notifications.py     # Slack/Teams Webhook
│   │   │   ├── reports.py           # CISO 리포트 PDF
│   │   │   └── ide.py               # IDE 전용 API
│   │   ├── services/
│   │   │   ├── semgrep_engine.py    # Semgrep 실행/결과 파싱
│   │   │   ├── llm_agent.py         # Claude API 오탐검증/패치생성
│   │   │   ├── scan_orchestrator.py # 스캔 작업 흐름 조율
│   │   │   ├── patch_generator.py   # GitHub PR 자동 생성
│   │   │   ├── github_app.py        # GitHub App API 클라이언트
│   │   │   ├── gitlab_service.py    # GitLab API 클라이언트
│   │   │   ├── bitbucket_service.py # Bitbucket API 클라이언트
│   │   │   ├── notification_service.py  # Slack/Teams 발송
│   │   │   ├── notification_formatter.py # Block Kit/Adaptive Cards
│   │   │   ├── report_renderer.py   # PDF 렌더링 (CSAP/ISO/ISMS)
│   │   │   ├── report_service.py    # 리포트 생성 서비스
│   │   │   ├── fp_filter_service.py # 오탐 패턴 필터링
│   │   │   ├── ide_analyzer.py      # IDE 실시간 분석
│   │   │   ├── api_key_service.py   # API Key 발급/검증
│   │   │   ├── security_score.py    # 보안 점수 계산 유틸
│   │   │   ├── token_crypto.py      # Fernet 암호화/SSRF 방어
│   │   │   ├── auth_service.py      # JWT 발급/검증
│   │   │   └── webhook_handler.py   # Webhook 이벤트 처리
│   │   ├── models/                  # SQLAlchemy ORM 모델
│   │   │   ├── user.py / team.py
│   │   │   ├── repository.py / scan_job.py
│   │   │   ├── vulnerability.py / patch_pr.py
│   │   │   ├── false_positive.py
│   │   │   ├── notification.py
│   │   │   ├── report_config.py / report_history.py
│   │   │   └── api_key.py
│   │   ├── schemas/                 # Pydantic 요청/응답 스키마
│   │   ├── rules/                   # 언어별 Semgrep 커스텀 룰셋
│   │   │   ├── python/              # sql_injection.yml, xss.yml, hardcoded_creds.yml
│   │   │   ├── javascript/          # + insecure_jwt.yml, misconfig.yml
│   │   │   ├── java/                # + weak_crypto.yml
│   │   │   └── go/                  # + command_injection.yml, weak_crypto.yml
│   │   ├── workers/
│   │   │   ├── scan_worker.py       # RQ 스캔 워커
│   │   │   ├── weekly_report_job.py # 주간 리포트 발송 작업
│   │   │   └── report_scheduler.py  # 리포트 스케줄러
│   │   ├── api/deps.py              # 인증 의존성 (JWT, API Key)
│   │   ├── config.py                # 환경변수/설정
│   │   └── main.py                  # FastAPI 앱 진입점
│   ├── alembic/versions/            # DB 마이그레이션 (001~007)
│   ├── tests/                       # pytest 테스트 (518 케이스)
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   └── src/
│       ├── app/                     # Next.js App Router
│       │   ├── dashboard/           # 대시보드 페이지
│       │   ├── repos/               # 저장소 목록/상세
│       │   ├── scans/               # 스캔 상세
│       │   ├── vulnerabilities/     # 취약점 상세
│       │   └── login/               # GitHub OAuth 로그인
│       ├── components/
│       │   ├── dashboard/           # 요약 카드, 최근 스캔/취약점
│       │   ├── layout/              # 헤더, 사이드바
│       │   ├── repos/               # 저장소 카드, 스캔 트리거 버튼
│       │   └── vulnerability/       # 코드 뷰어, 패치 diff, 상태 액션
│       └── lib/
│           ├── api-client.ts        # axios 기반 API 클라이언트
│           ├── auth.ts              # 인증 유틸
│           └── hooks/               # TanStack Query 훅
├── vscode-extension/
│   ├── src/
│   │   ├── extension.ts             # 진입점 (activate/deactivate)
│   │   ├── config.ts                # 설정 관리
│   │   ├── api/client.ts            # HTTP 클라이언트 (X-API-Key)
│   │   ├── api/types.ts             # Finding 등 타입 정의
│   │   ├── analyzer/analyzer.ts     # 분석 오케스트레이터 (500ms 디바운스)
│   │   ├── analyzer/fp-cache.ts     # 오탐 패턴 캐시 (5분 주기 ETag 동기화)
│   │   ├── diagnostics/             # DiagnosticCollection 관리 및 매핑
│   │   ├── code-actions/            # CodeActionProvider + 패치 적용
│   │   ├── webview/                 # 취약점 상세 WebviewPanel
│   │   └── status/status-bar.ts    # 상태 표시줄
│   ├── test/suite/                  # Jest 단위 테스트 (62 케이스)
│   └── package.json
├── docs/
│   ├── project/prd.md              # 제품 요구사항 문서
│   ├── project/features.md         # 기능 백로그 + 인수조건
│   ├── specs/                      # 기능별 기술 설계서
│   ├── api/                        # API 명세 문서
│   ├── db/                         # DB 스키마 문서
│   └── system/system-design.md     # 시스템 전체 설계
└── docker-compose.yml
```

---

## 배포

권장 스택: **Railway** (백엔드) + **Vercel** (프론트엔드) + **Supabase** (PostgreSQL) + **Upstash** (Redis)

### 백엔드 — Railway

```bash
# 1. Docker 이미지 빌드 확인
cd backend
docker build -t vulnix-backend .

# 2. Railway CLI 배포
npm install -g @railway/cli
railway login
railway init
railway up
```

Railway 환경변수 (`railway variables set KEY=VALUE`):

```dotenv
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/vulnix
REDIS_URL=redis://default:pass@host:port

GITHUB_APP_ID=
GITHUB_APP_PRIVATE_KEY=
GITHUB_WEBHOOK_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=

ANTHROPIC_API_KEY=

JWT_SECRET_KEY=          # openssl rand -hex 32
TOKEN_ENCRYPTION_KEY=    # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

CORS_ORIGINS=https://your-app.vercel.app
APP_ENV=production
DEBUG=false
```

DB 마이그레이션 및 워커 설정:

```bash
# 마이그레이션 실행
railway run alembic upgrade head

# 워커 프로세스: Railway에서 서비스 하나 추가 생성 후 Start Command 설정
# Start Command: python -m src.workers.scan_worker
```

### 프론트엔드 — Vercel

```bash
cd frontend
npx vercel
# 또는 GitHub 저장소를 Vercel에 연결하여 자동 배포
```

Vercel 환경변수:

```dotenv
NEXT_PUBLIC_API_URL=https://your-backend.railway.app
```

### DB — Supabase

1. [supabase.com](https://supabase.com) → 프로젝트 생성
2. `Settings → Database → Connection String` 복사
3. `DATABASE_URL`을 `postgresql+asyncpg://...` 형식으로 설정

### Redis — Upstash

1. [upstash.com](https://upstash.com) → Redis 데이터베이스 생성
2. `REDIS_URL`에 `redis://default:...@...upstash.io:port` 설정

### GitHub App 설정

1. GitHub → `Settings → Developer settings → GitHub Apps → New GitHub App`
2. 권한 설정:
   - **Repository permissions**: `Contents` (Read & Write), `Pull requests` (Read & Write)
   - **Subscribe to events**: `Push`, `Pull request`
3. Webhook URL: `https://your-backend.railway.app/api/v1/webhooks/github`
4. Private key 생성 → `GITHUB_APP_PRIVATE_KEY`에 PEM 전체 내용 설정

### 프로덕션 체크리스트

- [ ] `JWT_SECRET_KEY` 생성 (`openssl rand -hex 32`)
- [ ] `TOKEN_ENCRYPTION_KEY` 생성 (Fernet 키)
- [ ] `DEBUG=false`, `APP_ENV=production` 설정
- [ ] `CORS_ORIGINS`에 실제 프론트엔드 도메인만 허용
- [ ] HTTPS 적용 확인 (Railway/Vercel 자동 제공)
- [ ] GitHub App Webhook Secret 설정
- [ ] DB 백업 정책 설정 (Supabase 자동 백업 활성화)

---

## 테스트 실행

```bash
# 백엔드 (전체)
cd backend
pytest tests/ -v
# 518 passed

# 백엔드 (커버리지 포함)
pytest tests/ --cov=src --cov-report=html

# VS Code 익스텐션
cd vscode-extension
npm test
# 62 passed
```

---

## 보안 설계

- **코드 보관 최소화**: 고객 코드는 `/tmp/vulnix-scan-{job_id}/` 임시 디렉토리에만 저장, 스캔 완료 즉시 삭제
- **PAT/App Password 암호화**: GitLab/Bitbucket 연동 토큰은 Fernet 암호화 후 DB 저장
- **SSRF 방어**: Webhook URL 등록 시 내부 IP(10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, IPv6 fc00::/7, fe80::/10, IPv4-mapped) 차단
- **Webhook 서명 검증**: GitHub (HMAC-SHA256), GitLab (X-Gitlab-Token), Bitbucket (HMAC-SHA256)
- **API Key 해시 저장**: 원본 키는 발급 시 한 번만 노출, DB에는 SHA-256 해시만 저장
- **Rate Limit**: IDE analyze 60회/분, patch-suggestion 10회/분 (LLM 비용 보호)

---

## 로드맵

| 마일스톤 | 구현 내용 | 상태 |
|----------|-----------|------|
| **M1** | GitHub 연동, Python 탐지 엔진, 자동 패치 PR, 기본 대시보드 UI | ✅ 완료 |
| **M2** | JS/TS/Java/Go 다국어 확장, 오탐 관리, 보안 점수 대시보드, Slack/Teams 알림 | ✅ 완료 |
| **M3** | GitLab/Bitbucket 연동, CISO 리포트 PDF, VS Code 익스텐션 | ✅ 완료 |
| **M4** | SCA (패키지 취약점 분석), DAST 연동, 엔터프라이즈 VPC 배포 | 예정 |

---

## 라이선스

MIT
