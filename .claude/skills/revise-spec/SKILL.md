---
name: revise-spec
description: >
  기능 설계 문서(design.md/plan.md/ui-spec.md) 조정.
  /spec 완료 후 설계 변경이 필요할 때 사용.
disable-model-invocation: true
---

## 현재 설계 상태 (자동 주입)
!`ls docs/specs/*/design.md 2>/dev/null || echo "설계 문서 없음 - /spec 먼저 실행"`

## Step 0: 전제조건 확인
- docs/specs/ 하위에 설계 문서 존재 확인
- 없으면 → "/plan을 먼저 실행하세요" 안내 후 종료

## Step 1: 대상 기능 + 변경 의도 수집
1. $ARGUMENTS로 기능명 지정 또는 설계 완료된 기능 목록 제시
2. 해당 기능의 design.md, plan.md, ui-spec.md, test-spec.md 읽기
3. 대화를 통해 변경 의도 파악

변경 유형:
| 유형 | 영향 문서 | cascade |
|------|-----------|---------|
| 설계 변경 (API/DB/구조) | design.md + plan.md + test-spec.md | - |
| 태스크 조정 | plan.md | - |
| UI 변경 | ui-spec.md + plan.md | - |
| 요구사항 자체 변경 | 위 전부 | → features.md, roadmap.md (project-planner 추가 호출) |

## Step 2: 변경 계획 제시 → 사용자 승인
- 변경 사항 + 영향 문서 정리
- cascade 여부 명시 (features.md까지 영향 시 경고)
- 사용자 승인 후 진행

## Step 3: 문서 업데이트

### architect 에이전트 호출 (설계 변경 시)
- design.md 수정 + test-spec.md 업데이트

### ui-designer 에이전트 호출 (UI 변경 시)
- ui-spec.md 수정

### product-manager 에이전트 호출 (태스크 재분해)
- plan.md 업데이트

### cascade: project-planner 에이전트 호출 (요구사항 변경 시)
- features.md 인수조건/우선순위 수정 → roadmap.md 반영

## Step 4: 결과 제시 + 추가 조정
- 변경 요약 제시
- "추가 조정이 있으면 계속, 완료되면 확정"
- 확정 시 → "다음 단계: /dev" 안내

추가 지시사항: $ARGUMENTS
