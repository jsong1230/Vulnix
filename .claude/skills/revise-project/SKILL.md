---
name: revise-project
description: >
  프로젝트 기획 문서(PRD/기능 백로그/로드맵) 조정.
  /init-project 완료 후 요구사항 변경이 필요할 때 사용.
disable-model-invocation: true
---

## 현재 기획 상태 (자동 주입)
!`head -20 docs/project/features.md 2>/dev/null || echo "features.md 없음 - /init-project 먼저 실행"`

## Step 0: 전제조건 확인
- docs/project/prd.md 존재 확인
- 없으면 → "/init-project를 먼저 실행하세요" 안내 후 종료

## Step 1: 현재 상태 파악 + 변경 의도 수집
1. docs/project/prd.md, features.md, roadmap.md 읽기
2. 현재 기획 요약 제시
3. $ARGUMENTS 또는 대화를 통해 변경 의도 파악

변경 유형:
| 유형 | 영향 문서 |
|------|-----------|
| 기능 추가/제거/수정 | prd + features + roadmap |
| 우선순위/마일스톤 변경 | features + roadmap |
| 기술/아키텍처 변경 | prd + system-design |

## Step 2: 변경 계획 제시 → 사용자 승인
- 변경 사항 목록 + 영향 문서 정리
- 이미 설계 완료된 기능(docs/specs/ 존재) 영향 시 경고
- 사용자 승인 후 진행

## Step 3: 문서 업데이트

### project-planner 에이전트 호출 (수정 모드)
- prd.md + features.md + roadmap.md 업데이트

### system-architect 에이전트 호출 (조건부)
- 기술/아키텍처 변경 시에만 system-design.md 업데이트

## Step 4: 결과 제시 + 추가 조정
- 변경 요약 제시
- "추가 조정이 있으면 계속, 완료되면 확정"
- 확정 시 → "다음 단계: /setup 또는 /spec" 안내

추가 지시사항: $ARGUMENTS
