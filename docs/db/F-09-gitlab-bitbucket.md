# F-09 GitLab/Bitbucket 연동 DB 스키마 확정본

작성일: 2026-02-25

## 개요

F-09 GitLab/Bitbucket 연동 기능을 위해 기존 `repository` 테이블에 플랫폼 관련 컬럼 6개를 추가한다.
신규 테이블은 없으며, 기존 GitHub 연동 컬럼은 하위 호환성을 위해 유지된다.

마이그레이션 파일: `005_add_f09_platform_columns.py`

---

## 테이블 변경: `repository`

GitHub / GitLab / Bitbucket 저장소 연동 정보를 통합 관리하는 테이블.
F-09에서 플랫폼 확장을 위한 컬럼 6개가 추가되었다.

### F-09 신규 추가 컬럼

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| platform | VARCHAR(20) | NOT NULL | 'github' | Git 플랫폼 구분 (github / gitlab / bitbucket) |
| platform_repo_id | VARCHAR(255) | NULL | NULL | 플랫폼별 저장소 고유 ID (GitLab: project_id 문자열, Bitbucket: workspace/slug) |
| platform_url | TEXT | NULL | NULL | 저장소 웹 URL (GitLab/Bitbucket) |
| platform_access_token_enc | TEXT | NULL | NULL | AES-256 암호화된 PAT 또는 App Password |
| external_username | VARCHAR(255) | NULL | NULL | Bitbucket username (App Password 인증에 필요) |
| platform_base_url | VARCHAR(500) | NULL | NULL | Self-managed 인스턴스 URL (GitLab 전용, 기본 NULL) |

### 기존 컬럼 (하위 호환 유지)

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id | UUID | NOT NULL | uuid4() | 기본 키 |
| team_id | UUID | NOT NULL | - | 소속 팀 ID (FK → team.id CASCADE) |
| github_repo_id | BIGINT | NOT NULL | 0 | GitHub 저장소 ID (GitHub 외 플랫폼은 0) |
| full_name | VARCHAR(255) | NOT NULL | - | 저장소 전체 이름 (예: org/repo-name) |
| default_branch | VARCHAR(255) | NOT NULL | 'main' | 기본 브랜치 이름 |
| language | VARCHAR(50) | NULL | NULL | 주 프로그래밍 언어 |
| is_active | BOOLEAN | NOT NULL | true | 스캔 활성화 여부 |
| installation_id | BIGINT | NULL | NULL | GitHub App 설치 ID |
| webhook_secret | TEXT | NULL | NULL | Webhook 서명 검증용 시크릿 |
| last_scanned_at | TIMESTAMPTZ | NULL | NULL | 마지막 스캔 완료 시각 (UTC) |
| security_score | NUMERIC(5,2) | NULL | NULL | 보안 점수 (0.00 ~ 100.00) |
| is_initial_scan_done | BOOLEAN | NOT NULL | false | 초기 전체 스캔 완료 여부 |
| created_at | TIMESTAMPTZ | NOT NULL | now() | 생성 시각 (UTC) |
| updated_at | TIMESTAMPTZ | NOT NULL | now() | 수정 시각 (UTC) |

### 제약 조건

| 이름 | 타입 | 컬럼 | 참조 | ON DELETE |
|------|------|------|------|-----------|
| PK | PRIMARY KEY | id | - | - |
| FK | FOREIGN KEY | team_id | team.id | CASCADE |
| UQ | UNIQUE | github_repo_id | - | - |

### 인덱스 전체 목록

| 인덱스명 | 컬럼 | 타입 | F-09 추가 | 설명 |
|----------|------|------|-----------|------|
| idx_repository_team_id | team_id | BTREE | N | 팀별 저장소 조회 |
| idx_repository_platform | platform | BTREE | Y | 플랫폼별 저장소 필터 |
| uq_repository_platform_repo_id | (platform, platform_repo_id) | UNIQUE (partial) | Y | 플랫폼 + 저장소 ID 중복 방지 (platform_repo_id IS NOT NULL) |

### partial unique 인덱스 DDL

```sql
CREATE UNIQUE INDEX uq_repository_platform_repo_id
ON repository(platform, platform_repo_id)
WHERE platform_repo_id IS NOT NULL;
```

`platform_repo_id IS NOT NULL` 조건을 포함한 부분 유니크 인덱스이다.
동일 플랫폼에서 동일한 저장소 ID를 중복 등록하는 것을 방지하되,
NULL 값(기존 GitHub 연동 행)은 중복 제약에서 제외된다.

---

## platform 별 데이터 형식

### GitHub

| 컬럼 | 값 |
|------|-----|
| platform | `"github"` |
| platform_repo_id | NULL (github_repo_id 컬럼 사용) |
| platform_url | NULL |
| platform_access_token_enc | NULL (installation_id + GitHub App 인증) |
| external_username | NULL |
| platform_base_url | NULL |

### GitLab

| 컬럼 | 값 |
|------|-----|
| platform | `"gitlab"` |
| platform_repo_id | GitLab 프로젝트 ID 문자열 (예: `"12345"`) |
| platform_url | GitLab 저장소 URL (예: `"https://gitlab.com/group/project-name"`) |
| platform_access_token_enc | GitLab Personal Access Token (PoC: 평문, 운영: AES-256 암호화) |
| external_username | NULL |
| platform_base_url | GitLab 인스턴스 URL (예: `"https://gitlab.com"`, self-managed 시 변경) |

### Bitbucket

| 컬럼 | 값 |
|------|-----|
| platform | `"bitbucket"` |
| platform_repo_id | `"workspace/repo-slug"` 형식 (예: `"my-workspace/my-repo"`) |
| platform_url | Bitbucket 저장소 URL (예: `"https://bitbucket.org/my-workspace/my-repo"`) |
| platform_access_token_enc | Bitbucket App Password (PoC: 평문, 운영: AES-256 암호화) |
| external_username | Bitbucket 사용자명 |
| platform_base_url | NULL |

---

## ERD 관계 (변경 없음)

```
team (1) ─────────────── (N) repository
                                  │
                  ┌───────────────┼───────────────┐
                  │               │               │
             (N) scan_job   (N) vulnerability  ...
```

`repository` 테이블은 F-09 변경 전후 동일한 관계를 유지하며,
플랫폼 종류에 관계없이 단일 테이블로 통합 관리된다.

---

## 마이그레이션

### 005_add_f09_platform_columns.py

```
Revision ID: 005_add_f09_platform_columns
Revises: 004_add_f08_tables
Create Date: 2026-02-25
```

upgrade:
- `platform` 컬럼 추가 (NOT NULL, DEFAULT 'github') — 기존 행은 자동으로 'github'로 설정
- `platform_repo_id` 컬럼 추가 (NULL)
- `platform_url` 컬럼 추가 (NULL)
- `platform_access_token_enc` 컬럼 추가 (NULL)
- `external_username` 컬럼 추가 (NULL)
- `platform_base_url` 컬럼 추가 (NULL)
- `github_repo_id` 컬럼에 `server_default='0'` 추가
- `idx_repository_platform` 인덱스 생성
- `uq_repository_platform_repo_id` partial unique 인덱스 생성

downgrade:
- `uq_repository_platform_repo_id` 인덱스 삭제
- `idx_repository_platform` 인덱스 삭제
- 추가된 컬럼 6개 삭제

---

## 성능 고려사항

1. 플랫폼 필터: `idx_repository_platform` 인덱스로 `GET /api/v1/repos?platform=gitlab` 쿼리 최적화
2. 중복 등록 방지: `uq_repository_platform_repo_id` partial unique 인덱스로 O(log n) 중복 체크
3. 기존 GitHub 행 영향 없음: partial 인덱스의 `WHERE platform_repo_id IS NOT NULL` 조건으로 기존 행(platform_repo_id=NULL) 제외
4. platform_access_token_enc: PoC 단계에서는 평문 저장, 운영 배포 시 AES-256 암호화 적용 필요
5. N+1 방지: 저장소 목록 조회 시 team_id 인덱스로 한 번에 로드, 플랫폼 필터는 인덱스 활용
