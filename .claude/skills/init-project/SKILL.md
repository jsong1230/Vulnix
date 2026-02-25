---
name: init-project
description: >
  프로젝트 초기화. 상태를 자동 감지하여 Greenfield/Brownfield/리뉴얼 모드 결정.
  기획 + 시스템 설계/분석만 수행. 환경 구성은 /setup에서.
disable-model-invocation: true
---

프로젝트 상태를 자동 감지하여 적절한 초기화를 수행합니다.

## Step 1: 프로젝트 상태 감지

다음을 확인하여 모드를 결정합니다:
1. 소스 코드 파일 존재 여부 (frontend/, backend/, src/ 등)
2. docs/system/system-design.md 존재 여부
3. docs/system/system-analysis.md 존재 여부
4. docs/project/features.md 존재 여부

**모드 결정:**
| 조건 | 모드 |
|------|------|
| 코드 없음 + system 문서 없음 | 신규 (Greenfield) |
| 코드 있음 + system 문서 없음 | Brownfield 첫 도입 |
| system-design.md 또는 system-analysis.md 존재 | 리뉴얼/업데이트 |

감지된 모드를 사용자에게 알리고 확인을 받습니다.

## Step 2-A: 신규 (Greenfield)

### project-planner 에이전트 호출
1. 사용자와 대화하며 프로젝트 목적, 대상 사용자, 핵심 기능 파악
2. docs/project/prd.md 작성
3. docs/project/features.md 작성 (인수조건 포함)
4. docs/project/roadmap.md 작성

### system-architect 에이전트 호출 (Greenfield 모드)
1. prd.md 기반으로 시스템 아키텍처 설계
2. docs/system/system-design.md 작성

## Step 2-B: Brownfield 첫 도입

### system-architect 에이전트 호출 (Brownfield 모드)
1. 기존 코드베이스 전체 분석
2. docs/system/system-analysis.md 작성

### project-planner 에이전트 호출 (Brownfield 모드)
1. system-analysis.md 기반으로 변경/추가 기능 정리
2. docs/project/features.md 작성 (신규 기능만)
3. docs/project/roadmap.md 작성

## Step 2-C: 리뉴얼/업데이트

### system-architect 에이전트 호출 (재분석)
1. 현재 코드베이스 재분석
2. system-design.md 또는 system-analysis.md 업데이트

### project-planner 에이전트 호출
1. 신규 features.md에 추가할 기능 정리
2. roadmap.md 업데이트

## Step 3: 사용자 검토 및 조정

### 3-1. 문서 요약 제시
- PRD 핵심 (프로젝트 개요, 핵심 기능, 기술 스택)
- 기능 백로그 전체 테이블 (features.md)
- 마일스톤 구조 (roadmap.md)
- 시스템 설계 개요 (system-design.md, Greenfield인 경우)

### 3-2. 피드백 루프
사용자가 "확정"이라 할 때까지 반복:

1. 사용자 피드백 수집 (자유 대화)
   - 기능 추가/삭제/수정, 우선순위 변경, 인수조건 수정, 마일스톤 재배치
2. project-planner 에이전트 호출 (수정 모드)
3. system-architect 에이전트 호출 (기술/아키텍처 변경 시에만)
4. 변경 결과 요약 제시 → "추가 조정 또는 확정?"

### 3-3. 확정 후 안내
- "다음 단계: /setup으로 개발 환경을 구성하세요"
- "나중에 기획 조정: /revise-project"

추가 지시사항: $ARGUMENTS
