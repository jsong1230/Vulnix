---
name: doc-rules
description: >
  문서 체계 + 문서화 규칙 참조 스킬. 문서 작업 시 자동 참조.
user-invocable: false
---

# 문서 체계 + 문서화 규칙

## 4단계 문서 라이프사이클

### 1단계: 프로젝트 기획 문서 (프로젝트 시작 시)
- `docs/project/prd.md` — PRD (project-planner)
- `docs/project/features.md` — 기능 백로그 + 인수조건 (project-planner)
- `docs/project/roadmap.md` — 마일스톤 로드맵 (project-planner)

### 2단계: 시스템 레벨 문서 (init-project 시 1회)
**Greenfield:**
- `docs/system/system-design.md` — 시스템 아키텍처 설계 (system-architect)

**Brownfield:**
- `docs/system/system-analysis.md` — 시스템 분석 (system-architect)

### 3단계: 기능 레벨 사전 문서 (구현 전, /spec 시)
**Greenfield:**
- `docs/specs/{기능명}/design.md` — 기능 상세 설계 (architect)
- `docs/specs/{기능명}/test-spec.md` — 테스트 명세 (architect)
- `docs/specs/{기능명}/ui-spec.md` — UI 설계서 (ui-designer, 프론트엔드 변경 시)
- `docs/specs/{기능명}/wireframes/*.html` — HTML 프로토타입 (ui-designer, 프론트엔드 변경 시)
- `docs/specs/{기능명}/plan.md` — 구현 태스크 목록 (product-manager)

**Brownfield:**
- `docs/specs/{기능명}/change-design.md` — 변경 설계 + 영향 분석 (architect)
- `docs/specs/{기능명}/test-spec.md` — 테스트 명세 (architect)
- `docs/specs/{기능명}/ui-spec.md` — UI 설계서 (ui-designer, 프론트엔드 변경 시)
- `docs/specs/{기능명}/wireframes/*.html` — HTML 프로토타입 (ui-designer, 프론트엔드 변경 시)
- `docs/specs/{기능명}/plan.md` — 구현 태스크 목록 (product-manager)

### 4단계: 사후 기술 문서 (구현 직후, 코드와 100% 일치)
- `docs/api/{기능명}.md` — API 스펙 확정본 (backend-dev)
- `docs/db/{기능명}.md` — DB 스키마 확정본 (backend-dev)
- `docs/components/{컴포넌트명}.md` — 컴포넌트 문서 (frontend-dev, 선택)
- `docs/tests/{기능명}/{timestamp}.md` — 테스트 + QG 검증 결과 (test-runner + quality-gate)
- `docs/tests/full-report-{date}.md` — 전체 프로젝트 테스트 결과 (/test 시)

## 에이전트별 문서 책임
| 에이전트 | 작성 문서 |
|----------|-----------|
| project-planner | prd.md, features.md, roadmap.md |
| system-architect | system-design.md 또는 system-analysis.md |
| architect | design.md, change-design.md, test-spec.md |
| ui-designer | ui-spec.md, wireframes/*.html |
| product-manager | plan.md |
| backend-dev | docs/api/, docs/db/ |
| frontend-dev | docs/components/ (선택) |
| test-runner | docs/tests/{기능명}/, full-report-*.md |
| quality-gate | docs/tests/{기능명}/ (QG 결과 append) |

## Greenfield vs Brownfield 비교
| 항목 | Greenfield | Brownfield |
|------|-----------|-----------|
| 시스템 레벨 | system-design.md | system-analysis.md |
| 기능 레벨 | design.md | change-design.md |
| 영향 분석 | 불필요 | 필수 |
| 회귀 테스트 | 불필요 | 필수 |
