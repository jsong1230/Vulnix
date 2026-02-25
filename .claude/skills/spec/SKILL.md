---
name: spec
description: >
  기능 설계 + 태스크 생성. architect → ui-designer → product-manager 순서로 실행.
  인자 없이 호출 시 product-manager가 백로그에서 다음 기능을 추천.
disable-model-invocation: true
---

## 기능 백로그 현황 (자동 주입)
!`grep -E '(대기|진행)' docs/project/features.md 2>/dev/null | head -10 || echo "features.md 없음"`

기능을 설계하고 구현 태스크를 생성합니다.

## Step 1: 기능 선택

**인자가 있는 경우**: 지정된 기능명으로 진행

**인자가 없는 경우**: product-manager에게 다음 기능 추천 요청
1. **product-manager 에이전트 호출** (다음 기능 선택):
   - 백로그 소스 동기화 (Jira/Linear인 경우)
   - 대기 + 의존성 충족 기능 필터링
   - 추천 기능 반환
2. PM 추천 기능을 사용자에게 제시, 확인 후 진행

## Step 2: Greenfield/Brownfield 판단

- docs/system/system-design.md 존재 → Greenfield 모드
- docs/system/system-analysis.md 존재 → Brownfield 모드
- docs/specs/{기능명}/design.md 이미 존재 → Step 3로 건너뜀 (재설계 필요 시 사용자 확인)

## Step 3: 설계 (architect 에이전트)

**Greenfield:**
- docs/project/features.md에서 인수조건 확인
- docs/system/system-design.md로 전체 아키텍처 파악
- docs/specs/{기능명}/design.md 작성
- docs/specs/{기능명}/test-spec.md 작성

**Brownfield:**
- docs/project/features.md에서 인수조건 확인
- docs/system/system-analysis.md로 현재 시스템 파악
- docs/specs/{기능명}/change-design.md 작성 (영향 분석 포함)
- docs/specs/{기능명}/test-spec.md 작성 (회귀 테스트 포함)

사용자 판단이 필요한 중대한 아키텍처 결정 시 → 멈추고 사용자에게 질문

## Step 4: UI 설계 (ui-designer 에이전트)

- design.md + features.md 인수조건 기반
- docs/specs/{기능명}/ui-spec.md 작성
- docs/specs/{기능명}/wireframes/*.html 프로토타입 생성
- 사용자가 브라우저에서 확인 후 승인
- 프론트엔드 변경이 없는 기능 → 이 단계 건너뜀
- ui-spec.md 이미 존재 → 건너뜀 (재설계 필요 시 사용자 확인)

## Step 5: 태스크 생성 (product-manager 에이전트)

1. design.md (또는 change-design.md) 읽기
2. features.md의 인수조건 확인
3. docs/specs/{기능명}/ui-spec.md 읽기 (존재하는 경우)
4. docs/specs/{기능명}/plan.md 작성 ([backend]/[frontend]/[shared] 태그 포함)
5. features.md 상태 → "🔄 진행중"

## Step 6: 프로젝트 관리 도구 등록

CLAUDE.md의 프로젝트 관리 섹션 확인:
- `file` 모드: plan.md의 체크리스트 그대로 사용
- `jira` 모드: Jira MCP로 이슈 생성 (MCP 도구 미사용 시 plan.md 체크리스트로 fallback)
- `linear` 모드: Linear MCP로 이슈 생성 (MCP 도구 미사용 시 plan.md 체크리스트로 fallback)

## Step 7: 사용자 확인
- 설계서와 태스크 목록을 사용자에게 제시
- "다음 단계: /dev로 구현을 시작하세요" 안내

기능명: $ARGUMENTS
