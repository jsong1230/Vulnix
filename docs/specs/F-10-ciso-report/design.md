# F-10: CISO 리포트 및 인증 증적 -- 기술 설계서

## 1. 참조
- 인수조건: docs/project/features.md #F-10
- 시스템 설계: docs/system/system-design.md
- 의존 기능: F-07(대시보드 -- 보안 점수, 취약점 통계 데이터 소스)

## 2. 아키텍처 결정

### 결정 1: PDF 생성 라이브러리
- **선택지**: A) reportlab (순수 Python) / B) WeasyPrint (HTML->PDF) / C) wkhtmltopdf (외부 바이너리)
- **결정**: A) reportlab
- **근거**: 순수 Python 라이브러리로 외부 시스템 의존성 없음. Railway 컨테이너에서 추가 패키지 설치 불필요. PDF 내 차트(그래프)도 reportlab.graphics로 구현 가능. 한글 폰트(NanumGothic 등) 임베딩 지원.

### 결정 2: 증적 자료 출력 포맷
- **선택지**: A) PDF만 / B) JSON + PDF / C) JSON + PDF + Excel
- **결정**: B) JSON + PDF 두 포맷
- **근거**: JSON은 기계 판독 가능한 형식으로 인증 심사 도구에 자동 임포트 가능. PDF는 심사원이 직접 확인하는 문서로 양쪽 모두 필요. Excel은 PoC 단계에서 과도한 범위.

### 결정 3: 리포트 생성 스케줄링 방식
- **선택지**: A) cron + 별도 스크립트 / B) APScheduler (인프로세스) / C) Celery Beat / D) RQ Scheduler
- **결정**: D) RQ Scheduler (기존 RQ 워커 활용)
- **근거**: 이미 스캔 작업에 RQ 워커를 사용 중이므로 RQ Scheduler로 주기적 작업을 등록하면 추가 인프라 없이 스케줄링 가능. APScheduler는 프로세스 재시작 시 스케줄이 사라지고, Celery는 PoC 단계에서 과도한 설정.

### 결정 4: 이메일 발송 방식
- **선택지**: A) smtplib (직접) / B) SendGrid API / C) Amazon SES
- **결정**: A) smtplib (환경변수 기반 SMTP)
- **근거**: PoC 단계에서 외부 서비스 의존을 최소화. Gmail SMTP, Naver SMTP 등 범용 SMTP 서버와 호환. 발송량이 적으므로 (주간/월간 리포트) 전용 이메일 서비스 불필요.

### 결정 5: 리포트 파일 저장 방식
- **선택지**: A) S3 업로드 / B) 로컬 파일시스템 / C) DB BLOB
- **결정**: B) 로컬 파일시스템 (PoC) -> A) S3 (프로덕션)
- **근거**: PoC에서는 `/data/reports/` 디렉토리에 저장. 프로덕션에서는 S3 업로드로 전환. `report_history.file_path`에 로컬 경로 또는 S3 URL 저장.

## 3. DB 설계

### 3-1. 새 테이블: report_config

리포트 생성 주기 및 수신자 설정을 저장한다.

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|----------|------|
| `id` | UUID | PK | 기본 키 |
| `team_id` | UUID | FK -> team, NOT NULL, INDEX | 소속 팀 ID |
| `report_type` | VARCHAR(30) | NOT NULL | 리포트 유형: "ciso" / "csap" / "iso27001" / "isms" |
| `schedule` | VARCHAR(20) | NOT NULL | 생성 주기: "weekly" / "monthly" / "quarterly" |
| `email_recipients` | JSONB | NOT NULL, DEFAULT '[]' | 수신자 이메일 목록 (JSON 배열) |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | 스케줄 활성화 여부 |
| `last_generated_at` | TIMESTAMPTZ | NULL | 마지막 생성 시각 |
| `next_generation_at` | TIMESTAMPTZ | NULL | 다음 생성 예정 시각 |
| `created_by` | UUID | FK -> user, NOT NULL | 설정 생성 사용자 |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 생성 시각 |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 수정 시각 |

**인덱스**:
```sql
CREATE INDEX idx_report_config_team ON report_config(team_id);
CREATE INDEX idx_report_config_next_gen ON report_config(next_generation_at)
    WHERE is_active = TRUE;
CREATE UNIQUE INDEX uq_report_config_team_type
    ON report_config(team_id, report_type);
```

### 3-2. 새 테이블: report_history

생성된 리포트의 이력과 파일 위치를 저장한다.

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|----------|------|
| `id` | UUID | PK | 기본 키 |
| `config_id` | UUID | FK -> report_config, NOT NULL, INDEX | 설정 ID |
| `team_id` | UUID | FK -> team, NOT NULL, INDEX | 소속 팀 ID |
| `report_type` | VARCHAR(30) | NOT NULL | 리포트 유형 |
| `format` | VARCHAR(10) | NOT NULL | "pdf" / "json" |
| `file_path` | TEXT | NOT NULL | 파일 경로 (로컬) 또는 S3 URL |
| `file_size_bytes` | BIGINT | NULL | 파일 크기 |
| `period_start` | DATE | NOT NULL | 리포트 대상 기간 시작일 |
| `period_end` | DATE | NOT NULL | 리포트 대상 기간 종료일 |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'generating' | "generating" / "completed" / "failed" / "sent" |
| `email_sent_at` | TIMESTAMPTZ | NULL | 이메일 발송 시각 |
| `email_recipients` | JSONB | NULL | 실제 발송된 수신자 목록 |
| `error_message` | TEXT | NULL | 생성 실패 시 에러 메시지 |
| `metadata` | JSONB | NULL | 리포트 요약 메타데이터 (보안 점수, 취약점 수 등) |
| `generated_by` | UUID | FK -> user, NULL | 수동 생성 시 사용자 ID (스케줄 생성은 NULL) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 생성 시각 |

**인덱스**:
```sql
CREATE INDEX idx_report_history_team ON report_history(team_id);
CREATE INDEX idx_report_history_config ON report_history(config_id);
CREATE INDEX idx_report_history_created ON report_history(created_at DESC);
CREATE INDEX idx_report_history_type_period ON report_history(report_type, period_start, period_end);
```

## 4. API 설계

### 4-1. 리포트 수동 생성

#### `POST /api/v1/reports/generate`
- **목적**: 리포트를 수동으로 생성 (즉시 또는 큐 등록)
- **인증**: JWT 필요 (owner/admin만)
- **Request Body**:
```json
{
    "report_type": "ciso",
    "period_start": "2026-01-01",
    "period_end": "2026-02-25",
    "format": "pdf",
    "send_email": true,
    "email_recipients": ["ciso@company.com", "security@company.com"]
}
```
- **처리 로직**:
  1. 사용자 권한 확인 (owner/admin)
  2. 입력값 검증 (report_type, period 범위, 이메일 형식)
  3. `report_history` 레코드 생성 (status="generating")
  4. Redis 큐에 리포트 생성 작업 등록
  5. 즉시 report_history ID 반환 (비동기 생성)
- **Response** (202):
```json
{
    "success": true,
    "data": {
        "report_id": "uuid",
        "status": "generating",
        "report_type": "ciso",
        "estimated_completion_seconds": 30
    }
}
```
- **에러 케이스**:

| 코드 | 상황 |
|------|------|
| 401 | JWT 인증 실패 |
| 403 | 권한 부족 (member는 생성 불가) |
| 422 | 잘못된 report_type 또는 기간 범위 |

### 4-2. 리포트 이력 조회

#### `GET /api/v1/reports/history`
- **목적**: 생성된 리포트 이력 조회
- **인증**: JWT 필요
- **Query Params**:
  - `report_type: str | None` -- 리포트 유형 필터
  - `status: str | None` -- 상태 필터
  - `page: int = 1`
  - `per_page: int = 20`
- **Response** (200):
```json
{
    "success": true,
    "data": [
        {
            "id": "uuid",
            "report_type": "ciso",
            "format": "pdf",
            "status": "completed",
            "period_start": "2026-01-01",
            "period_end": "2026-02-25",
            "file_size_bytes": 245760,
            "email_sent_at": "2026-02-25T10:30:00Z",
            "metadata": {
                "security_score": 75.5,
                "total_vulnerabilities": 42,
                "critical_count": 3
            },
            "created_at": "2026-02-25T10:00:00Z"
        }
    ],
    "meta": {
        "page": 1,
        "per_page": 20,
        "total": 15,
        "total_pages": 1
    }
}
```

### 4-3. 리포트 다운로드

#### `GET /api/v1/reports/{report_id}/download`
- **목적**: 생성된 리포트 파일 다운로드
- **인증**: JWT 필요
- **Response**: 파일 스트림 (Content-Type: application/pdf 또는 application/json)
- **에러 케이스**:

| 코드 | 상황 |
|------|------|
| 404 | 리포트가 없거나 다른 팀의 리포트 |
| 409 | 아직 생성 중 (status="generating") |
| 410 | 파일이 삭제됨 (만료) |

### 4-4. 리포트 스케줄 설정

#### `POST /api/v1/reports/config`
- **목적**: 리포트 자동 생성 스케줄 설정
- **인증**: JWT 필요 (owner/admin만)
- **Request Body**:
```json
{
    "report_type": "ciso",
    "schedule": "monthly",
    "email_recipients": ["ciso@company.com"],
    "is_active": true
}
```
- **Response** (201):
```json
{
    "success": true,
    "data": {
        "id": "uuid",
        "report_type": "ciso",
        "schedule": "monthly",
        "email_recipients": ["ciso@company.com"],
        "is_active": true,
        "next_generation_at": "2026-03-01T00:00:00Z"
    }
}
```

#### `GET /api/v1/reports/config`
- **목적**: 팀의 리포트 스케줄 설정 목록 조회
- **인증**: JWT 필요

#### `PATCH /api/v1/reports/config/{config_id}`
- **목적**: 리포트 스케줄 설정 변경
- **인증**: JWT 필요 (owner/admin만)
- **Request Body** (부분 업데이트):
```json
{
    "schedule": "weekly",
    "email_recipients": ["ciso@company.com", "cto@company.com"],
    "is_active": true
}
```

#### `DELETE /api/v1/reports/config/{config_id}`
- **목적**: 리포트 스케줄 삭제
- **인증**: JWT 필요 (owner/admin만)

## 5. 리포트 콘텐츠 설계

### 5-1. CISO 경영진 리포트 (PDF)

대상: 경영진, CISO
목적: 보안 현황 요약 + 의사결정을 위한 핵심 지표

**PDF 구조**:
1. **표지**: Vulnix 로고, 팀명, 리포트 기간, 생성일
2. **경영진 요약 (Executive Summary)**: 1페이지
   - 전체 보안 점수 (게이지 차트)
   - 핵심 지표 카드: 총 취약점 수, 신규 발견, 해결 건수, 해결률
   - 위험 등급 요약: "개선됨" / "유지" / "악화됨" (전 기간 대비)
3. **보안 점수 추이**: 기간 내 일별/주별 보안 점수 라인 차트
4. **취약점 통계**:
   - 심각도별 분포 (파이 차트)
   - 상태별 분포 (open/patched/ignored/false_positive)
   - 취약점 유형별 Top 10 (바 차트)
5. **대응 현황**:
   - 평균 대응 시간 (탐지 -> 패치 완료)
   - 자동 패치 적용률
   - 저장소별 보안 점수 랭킹
6. **권고 사항**: 우선 대응이 필요한 Critical/High 취약점 목록 (최대 10건)

### 5-2. CSAP 인증 증적 (PDF + JSON)

대상: CSAP(클라우드 보안 인증) 심사
참조 항목: CSAP 2.0 보안 요구사항 중 "취약점 관리" 영역

**증적 내용**:
1. 취약점 관리 프로세스 증적
   - 스캔 실행 이력 (날짜, 대상, 결과)
   - 취약점 탐지 및 조치 이력 (탐지일, 조치일, 조치 내용)
   - 미조치 취약점 현황 및 사유
2. 자동화 보안 점검 증적
   - CI/CD 파이프라인 내 보안 점검 자동화 현황
   - 스캔 주기 및 실행 결과
3. 패치 관리 증적
   - 패치 적용 이력 (PR 번호, 적용일, 승인자)
   - 미패치 취약점 위험 수용 근거

### 5-3. ISO 27001 인증 증적 (PDF + JSON)

대상: ISO 27001 심사
참조 항목: Annex A.12.6 (기술 취약점 관리), A.14.2 (개발 및 지원 프로세스의 보안)

**증적 내용**:
1. A.12.6.1 기술 취약점 관리
   - 취약점 식별 이력 (CWE, OWASP 매핑 포함)
   - 취약점 평가 및 우선순위 결정 근거 (심각도, LLM 신뢰도)
   - 취약점 대응 조치 내역 (패치 PR, 수동 수정 가이드)
   - 취약점 대응 SLA 준수율
2. A.14.2.1 보안 개발 정책
   - 코드 보안 점검 자동화 현황
   - 개발 단계별 보안 점검 결과

### 5-4. ISMS 인증 증적 (PDF + JSON)

대상: ISMS-P 심사
참조 항목: 2.10.4 (취약점 점검 및 조치), 2.11.5 (소스코드 보안)

**증적 내용**:
1. 2.10.4 취약점 점검 및 조치
   - 정기 취약점 점검 수행 현황 (주기, 도구, 대상)
   - 취약점 조치 현황 (심각도별 조치율, 평균 조치 소요일)
   - 미조치 취약점 위험 관리 현황
2. 2.11.5 소스코드 보안
   - 소스코드 보안 약점 점검 현황
   - 보안 약점 조치 이력
   - 시큐어 코딩 적용 현황

## 6. 서비스 계층 설계

### 6-1. ReportService

```python
# backend/src/services/report_service.py

class ReportService:
    """리포트 생성 및 관리 서비스.

    역할:
    1. 리포트 데이터 수집 (대시보드 API 데이터 재사용)
    2. PDF 렌더링 (reportlab)
    3. JSON 증적 데이터 생성
    4. 파일 저장 (로컬/S3)
    5. 이메일 발송 (SMTP)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_report(
        self,
        report_id: uuid.UUID,
        report_type: str,
        team_id: uuid.UUID,
        period_start: date,
        period_end: date,
        format: str = "pdf",
    ) -> str:
        """리포트를 생성하고 파일 경로를 반환한다.

        1. 팀의 저장소/취약점/스캔 데이터 수집
        2. report_type에 따라 렌더러 선택
        3. PDF 또는 JSON 생성
        4. 파일 저장
        5. report_history 상태 업데이트

        Returns:
            생성된 파일 경로
        """
        ...

    async def collect_report_data(
        self,
        team_id: uuid.UUID,
        period_start: date,
        period_end: date,
    ) -> ReportData:
        """리포트에 필요한 데이터를 수집한다.

        기존 dashboard.py의 헬퍼 함수를 재사용한다.

        Returns:
            ReportData(
                repositories, vulnerabilities, scan_jobs,
                security_scores, severity_distribution,
                trend_data, patch_prs
            )
        """
        ...

    async def send_email(
        self,
        report_id: uuid.UUID,
        recipients: list[str],
        file_path: str,
        report_type: str,
    ) -> None:
        """생성된 리포트를 이메일로 발송한다.

        SMTP 설정은 환경변수에서 로드.
        첨부 파일: PDF/JSON 리포트.
        """
        ...
```

### 6-2. ReportRenderer (전략 패턴)

```python
# backend/src/services/report_renderer.py

from abc import ABC, abstractmethod

class ReportRenderer(ABC):
    """리포트 렌더러 공통 인터페이스."""

    @abstractmethod
    def render_pdf(self, data: ReportData, output_path: str) -> None:
        """PDF 파일을 생성한다."""

    @abstractmethod
    def render_json(self, data: ReportData, output_path: str) -> None:
        """JSON 파일을 생성한다."""


class CISOReportRenderer(ReportRenderer):
    """CISO 경영진 리포트 렌더러.

    reportlab 사용:
    - SimpleDocTemplate으로 PDF 생성
    - Drawing 객체로 차트 렌더링
    - NanumGothic 폰트 임베딩 (한글 지원)
    """
    ...

class CSAPReportRenderer(ReportRenderer):
    """CSAP 인증 증적 렌더러."""
    ...

class ISO27001ReportRenderer(ReportRenderer):
    """ISO 27001 인증 증적 렌더러."""
    ...

class ISMSReportRenderer(ReportRenderer):
    """ISMS-P 인증 증적 렌더러."""
    ...


def get_report_renderer(report_type: str) -> ReportRenderer:
    """report_type에 맞는 렌더러를 반환한다."""
    renderers = {
        "ciso": CISOReportRenderer,
        "csap": CSAPReportRenderer,
        "iso27001": ISO27001ReportRenderer,
        "isms": ISMSReportRenderer,
    }
    cls = renderers.get(report_type)
    if cls is None:
        raise ValueError(f"지원하지 않는 리포트 유형: {report_type}")
    return cls()
```

### 6-3. ReportData 모델

```python
# backend/src/schemas/report.py

from dataclasses import dataclass
from datetime import date, datetime

@dataclass
class ReportData:
    """리포트 생성에 필요한 집계 데이터."""

    team_name: str
    period_start: date
    period_end: date

    # 저장소 정보
    repositories: list[dict]  # [{id, full_name, platform, security_score}]
    total_repo_count: int

    # 취약점 통계
    total_vulnerabilities: int
    new_vulnerabilities: int  # 기간 내 신규
    resolved_vulnerabilities: int  # 기간 내 해결
    severity_distribution: dict[str, int]  # {critical: N, high: N, ...}
    status_distribution: dict[str, int]  # {open: N, patched: N, ...}
    resolution_rate: float  # 해결률 (%)
    vulnerability_type_top10: list[dict]  # [{type, count}]

    # 보안 점수
    current_security_score: float
    previous_security_score: float  # 이전 동일 기간
    score_trend: list[dict]  # [{date, score}]

    # 대응 현황
    avg_response_time_hours: float  # 탐지->패치 평균 시간
    auto_patch_rate: float  # 자동 패치 적용률 (%)
    repo_score_ranking: list[dict]  # [{full_name, score, open_vulns}]

    # 스캔 이력
    scan_jobs: list[dict]  # [{id, repo_name, status, created_at, findings_count}]
    total_scans: int

    # 패치 이력
    patch_prs: list[dict]  # [{id, repo_name, pr_url, status, vulnerability_type}]

    # 미조치 취약점 (인증 증적용)
    unresolved_critical: list[dict]  # [{id, file_path, type, severity, detected_at}]
```

### 6-4. 스케줄러 설계

```python
# backend/src/workers/report_scheduler.py

"""RQ Scheduler 기반 리포트 자동 생성.

report_config 테이블의 next_generation_at을 주기적으로 확인하여
리포트 생성 작업을 큐에 등록한다.

실행 방법:
    rq scheduler --interval 60 --url $REDIS_URL
"""

def check_and_enqueue_reports():
    """현재 시각 기준으로 생성이 필요한 리포트를 큐에 등록한다.

    1. report_config에서 is_active=True AND next_generation_at <= now 조회
    2. 각 설정에 대해 리포트 생성 작업 큐 등록
    3. next_generation_at을 다음 주기로 업데이트

    주기 계산:
    - weekly: + 7일
    - monthly: + 1개월 (dateutil.relativedelta)
    - quarterly: + 3개월
    """
    ...


def calculate_next_generation(schedule: str, current: datetime) -> datetime:
    """다음 생성 시각을 계산한다."""
    if schedule == "weekly":
        return current + timedelta(days=7)
    elif schedule == "monthly":
        # 매월 1일 00:00 UTC
        next_month = current.replace(day=1) + timedelta(days=32)
        return next_month.replace(day=1, hour=0, minute=0, second=0)
    elif schedule == "quarterly":
        # 분기 시작월 (1, 4, 7, 10월) 1일 00:00 UTC
        quarter_month = ((current.month - 1) // 3 + 1) * 3 + 1
        year = current.year + (1 if quarter_month > 12 else 0)
        quarter_month = quarter_month if quarter_month <= 12 else quarter_month - 12
        return datetime(year, quarter_month, 1, 0, 0, 0, tzinfo=timezone.utc)
    else:
        raise ValueError(f"지원하지 않는 주기: {schedule}")
```

### 6-5. 이메일 발송 서비스

```python
# backend/src/services/email_service.py

class EmailService:
    """SMTP 기반 이메일 발송 서비스.

    환경변수:
    - SMTP_HOST: SMTP 서버 호스트
    - SMTP_PORT: SMTP 포트 (기본 587, STARTTLS)
    - SMTP_USERNAME: SMTP 인증 사용자명
    - SMTP_PASSWORD: SMTP 인증 비밀번호
    - SMTP_FROM_EMAIL: 발신자 이메일
    - SMTP_FROM_NAME: 발신자 이름 (기본 "Vulnix Security")
    """

    async def send_report_email(
        self,
        recipients: list[str],
        subject: str,
        body_html: str,
        attachment_path: str,
        attachment_name: str,
    ) -> bool:
        """리포트를 첨부하여 이메일을 발송한다.

        Returns:
            발송 성공 여부
        """
        ...
```

## 7. 시퀀스 흐름

### 7-1. 수동 리포트 생성 흐름

```
사용자      Frontend       API            ReportService     RQ Worker        SMTP
  |            |            |                  |                |              |
  |-- 생성 --->|            |                  |                |              |
  |            |-- POST --->|                  |                |              |
  |            | /reports/  |                  |                |              |
  |            | generate   |                  |                |              |
  |            |            |-- create         |                |              |
  |            |            |   history ------>|                |              |
  |            |            |-- enqueue ------>|                |              |
  |            |<-- 202 ----|                  |                |              |
  |<-- 생성중 -|            |                  |                |              |
  |            |            |                  |-- job -------->|              |
  |            |            |                  |                |              |
  |            |            |                  |  [collect_data]|              |
  |            |            |                  |  [render_pdf]  |              |
  |            |            |                  |  [save_file]   |              |
  |            |            |                  |                |              |
  |            |            |                  |  [send_email]--|------------->|
  |            |            |                  |                |              |
  |            |            |                  |  [update       |              |
  |            |            |                  |   status ->    |              |
  |            |            |                  |   "sent"]      |              |
```

### 7-2. 자동 스케줄 리포트 생성 흐름

```
RQ Scheduler    ReportConfig DB    RQ Worker    ReportService    SMTP
     |                |                |              |            |
     |-- check ------>|                |              |            |
     |  (매 1분)      |                |              |            |
     |<-- configs ----|                |              |            |
     |  (next_gen     |                |              |            |
     |   <= now)      |                |              |            |
     |                |                |              |            |
     |-- enqueue ---->|--------------->|              |            |
     |                |                |-- generate ->|            |
     |                |                |              |-- PDF      |
     |                |                |              |-- email -->|
     |                |                |              |            |
     |-- update ----->|                |              |            |
     |  next_gen_at   |                |              |            |
```

## 8. 환경변수 추가

```bash
# SMTP 이메일 발송
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=vulnix@company.com
SMTP_PASSWORD=your-smtp-password
SMTP_FROM_EMAIL=vulnix@company.com
SMTP_FROM_NAME=Vulnix Security

# 리포트 파일 저장 경로
REPORT_STORAGE_PATH=/data/reports
# S3 사용 시 (프로덕션)
# REPORT_S3_BUCKET=vulnix-reports
# REPORT_S3_REGION=ap-northeast-2
```

## 9. 영향 범위

### 수정 필요 파일

| 파일 | 변경 내용 |
|------|----------|
| `backend/src/config.py` | SMTP_*, REPORT_STORAGE_PATH 환경변수 추가 |
| `backend/src/api/v1/router.py` | reports 라우터 등록 |
| `backend/src/models/__init__.py` | ReportConfig, ReportHistory import 추가 |
| `backend/src/api/v1/dashboard.py` | `_get_vulns_by_repos`, `_get_recent_scans` 등 헬퍼 함수를 서비스 계층으로 추출하여 재사용 가능하게 리팩터링 |
| `backend/src/workers/scan_worker.py` | RQ Scheduler 설정에 리포트 스케줄 체크 작업 등록 |
| `backend/pyproject.toml` | `reportlab`, `python-dateutil` 의존성 추가 |

### 신규 생성 파일

| 파일 | 설명 |
|------|------|
| `backend/src/models/report_config.py` | ReportConfig ORM 모델 |
| `backend/src/models/report_history.py` | ReportHistory ORM 모델 |
| `backend/src/schemas/report.py` | 리포트 관련 Pydantic 스키마 + ReportData 데이터클래스 |
| `backend/src/services/report_service.py` | 리포트 생성 서비스 (데이터 수집, 생성, 이메일) |
| `backend/src/services/report_renderer.py` | ReportRenderer ABC + CISO/CSAP/ISO27001/ISMS 렌더러 |
| `backend/src/services/email_service.py` | SMTP 이메일 발송 서비스 |
| `backend/src/api/v1/reports.py` | 리포트 관련 엔드포인트 |
| `backend/src/workers/report_worker.py` | 리포트 생성 RQ 워커 작업 |
| `backend/src/workers/report_scheduler.py` | 리포트 스케줄 체크 및 큐 등록 |
| `backend/alembic/versions/xxxx_f10_report_tables.py` | DB 마이그레이션 (report_config, report_history) |
| `backend/src/assets/fonts/NanumGothic.ttf` | 한글 폰트 파일 (reportlab용) |

## 10. 성능 설계

### 인덱스 계획

```sql
CREATE INDEX idx_report_config_team ON report_config(team_id);
CREATE INDEX idx_report_config_next_gen ON report_config(next_generation_at)
    WHERE is_active = TRUE;
CREATE UNIQUE INDEX uq_report_config_team_type ON report_config(team_id, report_type);

CREATE INDEX idx_report_history_team ON report_history(team_id);
CREATE INDEX idx_report_history_config ON report_history(config_id);
CREATE INDEX idx_report_history_created ON report_history(created_at DESC);
```

### 캐싱 전략
- 리포트 데이터 수집: 대시보드 API와 동일한 쿼리이므로 Redis 캐시 TTL 5분 적용 가능 (PoC에서는 미적용)
- 생성된 PDF/JSON: 파일시스템에 저장하므로 별도 캐시 불필요

### 비동기 처리
- PDF 생성은 CPU 집약적이므로 RQ 워커에서 비동기 처리
- 이메일 발송은 네트워크 I/O이므로 PDF 생성 완료 후 별도 비동기 태스크로 처리
- 리포트 생성 큐: `reports` (기존 `scans` 큐와 분리)

### 파일 정리
- 90일 이상 된 리포트 파일 자동 삭제 (cron 또는 RQ Scheduler)
- `report_history` 레코드는 유지 (file_path만 NULL로 업데이트)

## 변경 이력

| 날짜 | 변경 내용 | 이유 |
|------|----------|------|
| 2026-02-25 | 초안 작성 | M3-A 병렬 배치 설계 |
