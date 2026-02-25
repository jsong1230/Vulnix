---
name: dev
description: >
  태스크 구현 전담. TDD(RED→GREEN→REFACTOR) + Agent Team 기본.
  /plan에서 생성된 태스크를 구현. 설계/분석/태스크 생성은 하지 않음.
  인자 없이 호출 시 plan.md에서 우선순위 높은 미완료 태스크 자동 선택.
disable-model-invocation: true
---

## 미완료 태스크 현황 (자동 주입)
!`grep -r '\[ \]\|\[→\]' docs/specs/*/plan.md 2>/dev/null | head -15 || echo "미완료 태스크 없음"`

태스크를 구현합니다. TDD 사이클: RED → GREEN → REFACTOR

## Step 1: 태스크 선택

**인자가 있는 경우**: 지정된 태스크로 진행

**인자가 없는 경우**: docs/specs/*/plan.md에서 자동 선택
1. [ ] 상태인 태스크 목록 조회
2. 의존성 충족 태스크만 필터
3. 우선순위 순서로 정렬, 최상위 태스크 선택
4. 사용자에게 확인

## Step 2: 태스크 → In Progress

plan.md에서 해당 태스크의 `[ ]`를 `[→]`로 변경

## Step 3: RED — 실패하는 테스트 작성 (test-runner 에이전트)

1. test-spec.md의 테스트 명세 읽기
2. 실패하는 테스트 코드 작성 (실제 assertion, test.todo 금지)
3. 테스트 실행 → FAIL 확인

## Step 4: GREEN — 구현 (Agent Team)

plan.md의 "병렬 실행 판단" 확인:

**Agent Team 권장 (기본):**
```
bash .claude/scripts/worktree-setup.sh {기능명} backend frontend
```

팀 생성:
| 팀원 | subagent_type | 작업 디렉토리 | 역할 |
|------|---------------|---------------|------|
| backend | backend-dev | .worktrees/{기능명}-backend/ | API + DB + TDD GREEN |
| frontend | frontend-dev | .worktrees/{기능명}-frontend/ | UI + API 연동 + TDD GREEN |

각 팀원은 테스트가 PASS하도록 구현 후 팀 리더에게 보고

**단일 에이전트 (프론트 또는 백 Only):**
해당 에이전트만 직접 호출

## Step 5: Merge

```
bash .claude/scripts/worktree-merge.sh {기능명} backend frontend
```

충돌 해결 불가 시 → 멈추고 사용자에게 보고

## Step 6: REFACTOR — quality-gate 검증

quality-gate 에이전트 호출:
- 보안 + 성능 + 코드/설계/문서 리뷰 + 시각 검증 (ui-spec.md 존재 시)

🔴 Critical 이슈 발견:
1. 해당 에이전트(backend-dev/frontend-dev)에게 수정 요청
2. quality-gate 재실행
3. 2회 시도 후에도 실패 → 멈추고 사용자에게 보고

🟡 Warning: 자동으로 해당 에이전트에게 수정 요청 후 진행

## Step 7: 태스크 → Done

plan.md에서 `[→]`를 `[x]`로 변경
features.md의 모든 태스크 완료 시 상태 → "✅ 완료"

## 완료 보고

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 구현 완료: {기능명}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

완료된 태스크:
- [x] {태스크 1}
- [x] {태스크 2}

생성된 문서:
- docs/api/{기능명}.md
- docs/db/{기능명}.md
- docs/tests/{기능명}/{YYYY-MM-DD-HHmm}.md

다음 단계: /dev (다음 태스크) 또는 /commit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

태스크 ID 또는 기능명: $ARGUMENTS
