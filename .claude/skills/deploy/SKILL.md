---
name: deploy
description: >
  배포. devops-engineer를 호출하여 Docker/CI/CD/클라우드 배포.
  인자로 환경 지정 (staging/production). 인자 없으면 기본 환경 배포.
disable-model-invocation: true
---

배포를 수행합니다.

## devops-engineer 에이전트 호출

### 배포 전 확인
1. 테스트 통과 여부 확인 (CLAUDE.md 테스트 명령어 실행)
2. 빌드 성공 여부 확인
3. 환경변수 설정 확인

### 배포 실행
1. CLAUDE.md의 기술 스택 및 실행 방법 참조
2. 환경에 맞는 배포 수행:
   - `staging`: 스테이징 환경 배포
   - `production`: 프로덕션 배포 (수동 확인 후)
   - 기본값: docker-compose 로컬 빌드 + 실행

### 배포 후 확인
1. 헬스체크 엔드포인트 확인 (/health)
2. 기본 기능 동작 확인
3. 문제 발생 시 롤백 절차 안내

## 배포 환경: $ARGUMENTS
