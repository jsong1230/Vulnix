---
name: setup
description: >
  개발 환경 구성. devops-engineer를 호출하여 프로젝트 스캐폴딩 또는 기존 환경 구성.
  /init-project 완료 후 실행. 완료 후 localhost 접속 가능한 상태.
disable-model-invocation: true
---

개발 환경을 구성합니다.

## Step 1: 상태 확인

다음을 확인하여 동작을 결정합니다:
1. 소스 코드 파일 존재 여부
2. docs/system/system-design.md 존재 여부

**동작 결정:**
| 조건 | 동작 |
|------|------|
| 코드 없음 + system-design.md 있음 | 신규 스캐폴딩 |
| 코드 있음 | 기존 환경 구성 |
| system-design.md 없음 | "/init-project를 먼저 실행하세요" 안내 |

## Step 2-A: 신규 프로젝트 스캐폴딩

devops-engineer 에이전트 호출:
1. docs/system/system-design.md 읽기
2. 프로젝트 디렉토리 구조 생성
3. package.json / 의존성 파일 생성 및 설치
4. 로컬 DB docker-compose 구성
5. .env.example 생성
6. 로컬 서버 실행 확인
7. CLAUDE.md 실행 방법 섹션 업데이트

## Step 2-B: 기존 프로젝트 환경 구성

devops-engineer 에이전트 호출:
1. 기존 설정 파일 확인
2. 의존성 설치 (`npm install` 등)
3. .env.example 기반 환경변수 가이드 제공
4. 로컬 서버 실행 확인

## Step 3: 완료 확인

- localhost 접속 가능 여부 확인
- "다음 단계: /spec {기능명} 또는 /auto-dev로 개발을 시작하세요" 안내

추가 지시사항: $ARGUMENTS
