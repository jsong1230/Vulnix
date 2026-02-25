---
name: auto-dev
description: >
  features.md의 기능을 자동으로 연속 개발. /spec → /dev 반복.
  마일스톤 경계, Critical 이슈, 사용자 판단 필요 시에만 멈춤.
disable-model-invocation: true
---

## 현재 기능 상태 (자동 주입)
!`head -50 docs/project/features.md 2>/dev/null || echo "features.md 없음 - /init-project 먼저 실행"`

features.md의 기능을 자동으로 연속 개발합니다.

## 동작 원칙

**자동 진행**: 기능 완료 → 다음 기능 자동 시작 (사용자 승인 없이)

**멈추는 조건:**
1. 마일스톤 경계 도달 (현재 마일스톤의 모든 기능 완료 시)
2. Critical 이슈를 2회 시도 후에도 해결 불가
3. 사용자 판단이 필요한 중대한 아키텍처 결정
4. 테스트 실패를 자동 수정으로 해결 불가 (2회 시도)
5. 모든 기능 완료
6. 의존성 미충족으로 진행 가능한 기능이 없을 때

**자동 판단 (멈추지 않고 진행):**
- 경미한 이슈(Warning): 자동 수정 후 진행
- 테스트 실패 → 수정 → 재테스트 (최대 2회)

## 실행 루프

### Loop Start: 다음 기능 선택 (product-manager)
1. **컨텍스트 정리** (첫 루프가 아닌 경우): `/compact 완료: {이전 기능명}. 다음 기능 선택 대기.`
2. **product-manager 에이전트 호출** (다음 기능 선택):
   - 백로그 소스 동기화 (Jira/Linear인 경우)
   - 대기 + 의존성 충족 기능 필터링
   - 병렬 배치 판단 (PG-* 힌트 + 런타임 분석)
   - 추천 결과 반환 (단일 또는 병렬 배치)
3. **마일스톤 경계 체크**: PM이 "마일스톤 완료"로 보고 시 → 멈춤
4. PM이 "진행 가능 기능 없음"으로 보고 시 → 멈춤
5. PM 추천에 따라 모드 분기:
   - 단일 기능 추천 → 단일 기능 모드
   - 복수 기능 추천 → 병렬 배치 모드

### 단일 기능 모드
1. 기능 상태 → "🔄 진행중"
2. /spec 흐름 실행 (architect → product-manager)
3. /dev 흐름 실행 (test-runner RED → Agent Team GREEN → quality-gate REFACTOR)
4. 기능 상태 → "✅ 완료"
5. → Loop Start

### 병렬 배치 모드 (PM 추천, 최대 3개)
1. 모든 배치 기능 상태 → "🔄 진행중"
2. 각 기능 /spec 순차 실행 (설계 일관성 유지)
3. 기능별 worktree 생성:
   ```
   bash .claude/scripts/worktree-setup.sh {기능명-1} dev
   bash .claude/scripts/worktree-setup.sh {기능명-2} dev
   ```
4. Agent Team으로 병렬 구현 (기능당 팀원 1명)
5. 순차 머지
6. 통합 테스트 + quality-gate
7. 모든 기능 상태 → "✅ 완료"
8. Git 커밋 (feat: 배치 내 기능 목록)
9. Git push
10. → Loop Start

## 멈췄을 때 출력 형식

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 자동 개발 일시 정지
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

사유: {마일스톤 완료 / Critical 이슈 / 테스트 실패 / 사용자 판단 필요 / 전체 완료}

진행 상황:
- 완료: {완료된 기능 목록}
- 남은 기능: {남은 기능 목록}

{사유별 상세 내용}

계속하려면: /auto-dev
💡 장시간 실행 후에는 /clear 후 /auto-dev로 재개하세요.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

추가 지시사항: $ARGUMENTS
