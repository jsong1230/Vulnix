# Vulnix

## 프로젝트
코드 저장소를 연동하면 AI가 보안 취약점을 찾아 패치 PR까지 자동 생성해주는 개발자용 보안 에이전트 SaaS

## 기술 스택
- Backend: Python (FastAPI), Semgrep (룰 기반 SAST), Claude API (claude-sonnet)
- Frontend: Next.js 14 (App Router), Tailwind CSS, TanStack Query, axios
- DB: PostgreSQL (Supabase) + Redis (Upstash)
- 인프라: Railway (Backend) + Vercel (Frontend) + Supabase (PostgreSQL)

## 디렉토리
- `backend/` — Python FastAPI 서버 (스캔 오케스트레이터, 에이전트)
- `frontend/` — Next.js 14 대시보드
  - `frontend/src/app/` — App Router 페이지
  - `frontend/src/components/` — 재사용 컴포넌트 (layout/, dashboard/, vulnerability/)
  - `frontend/src/lib/` — API 클라이언트, 인증 유틸, 공통 유틸
- `docs/` — 프로젝트 문서

## 실행
- 인프라: `docker-compose up -d`
- Backend 의존성 설치: `cd backend && pip install -e ".[dev]"`
- Backend 환경변수: `cd backend && cp .env.example .env` (실제 값 입력 필요)
- Backend 개발: `cd backend && uvicorn src.main:app --reload --port 8000`
- Backend 워커: `cd backend && python -m src.workers.scan_worker`
- DB 마이그레이션: `cd backend && alembic upgrade head`
- Frontend 개발: `cd frontend && npm install && npm run dev` (http://localhost:3000)
- Frontend 빌드: `cd frontend && npm run build`
- 테스트: `cd backend && pytest`
- 빌드: `cd backend && docker build -t vulnix-backend .`

## Backend 환경변수
- `backend/.env.example` 참고
- `DATABASE_URL` — PostgreSQL 연결 URL (postgresql+asyncpg://user:pass@localhost:5432/vulnix)
- `REDIS_URL` — Redis 연결 URL (redis://localhost:6379)
- `GITHUB_APP_ID` / `GITHUB_APP_PRIVATE_KEY` / `GITHUB_WEBHOOK_SECRET` — GitHub App 설정
- `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` — GitHub OAuth App 설정
- `ANTHROPIC_API_KEY` — Claude API 키
- `JWT_SECRET_KEY` — JWT 서명 키 (openssl rand -hex 32 생성 권장)

## Frontend 환경변수
- `frontend/.env.example` 참고
- `NEXT_PUBLIC_API_URL` — 백엔드 API URL (기본: http://localhost:8000)

## 프로젝트 관리
- 방식: file
