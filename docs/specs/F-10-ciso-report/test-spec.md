# F-10: CISO 리포트 및 인증 증적 -- 테스트 명세

## 참조
- 설계서: docs/specs/F-10-ciso-report/design.md
- 인수조건: docs/project/features.md #F-10

## 인수조건 매핑

| 인수조건 | 테스트 케이스 |
|----------|---------------|
| CISO용 경영진 리포트 PDF 자동 생성 | I-1001, I-1002, I-1003, I-1004 |
| 리포트에 보안 점수 추이, 취약점 통계, 대응 현황 포함 | I-1005, I-1006, I-1007 |
| CSAP 인증 대응용 증적 자료 포맷 출력 | I-1008, I-1009 |
| ISO 27001 인증 대응용 증적 자료 포맷 출력 | I-1010, I-1011 |
| ISMS 인증 대응용 증적 자료 포맷 출력 | I-1012, I-1013 |
| 리포트 생성 주기 설정 가능 (주간/월간/분기) | I-1014, I-1015, I-1016 |
| 리포트 자동 이메일 발송 가능 | I-1017, I-1018, I-1019 |

---

## 단위 테스트

### ReportService -- 데이터 수집

| ID | 대상 | 시나리오 | Arrange | Act | Assert |
|----|------|----------|---------|-----|--------|
| U-1001 | `collect_report_data()` | 정상 데이터 수집 | DB에 저장소 3개, 취약점 20개, 스캔 10건, 패치 PR 5건 | `collect_report_data(team_id, start, end)` | ReportData 객체 반환. total_vulnerabilities=20, total_repo_count=3, total_scans=10 |
| U-1002 | `collect_report_data()` | 빈 팀 (저장소 없음) | DB에 해당 팀의 저장소 0개 | `collect_report_data(team_id, start, end)` | ReportData 반환. total_vulnerabilities=0, total_repo_count=0, security_score=0 |
| U-1003 | `collect_report_data()` | 기간 필터링 정확성 | 기간 내 취약점 10건, 기간 외 취약점 5건 | `collect_report_data(team_id, "2026-02-01", "2026-02-28")` | new_vulnerabilities=10 (기간 외 제외) |
| U-1004 | `collect_report_data()` | 보안 점수 추이 계산 | 기간 내 일별 취약점 변동 데이터 | `collect_report_data(...)` | score_trend 배열에 일별 점수 포함, 최신 점수가 current_security_score |
| U-1005 | `collect_report_data()` | 평균 대응 시간 계산 | 취약점 5건: detected_at -> resolved_at 간격 각각 24h, 48h, 72h, 12h, 36h | `collect_report_data(...)` | avg_response_time_hours = 38.4 |
| U-1006 | `collect_report_data()` | 자동 패치 적용률 | 전체 취약점 20건, 자동 패치 적용 8건 | `collect_report_data(...)` | auto_patch_rate = 40.0 |

### ReportRenderer -- CISO PDF

| ID | 대상 | 시나리오 | Arrange | Act | Assert |
|----|------|----------|---------|-----|--------|
| U-1007 | `CISOReportRenderer.render_pdf()` | PDF 생성 성공 | ReportData 완성, 출력 경로 지정 | `render_pdf(data, "/tmp/test.pdf")` | 파일 존재, PDF 바이트 시작이 `%PDF`, 파일 크기 > 0 |
| U-1008 | `CISOReportRenderer.render_pdf()` | 한글 텍스트 포함 | ReportData에 한글 팀명, 한글 취약점 설명 포함 | `render_pdf(data, "/tmp/test_kr.pdf")` | PDF 생성 성공 (폰트 임베딩 오류 없음) |
| U-1009 | `CISOReportRenderer.render_pdf()` | 차트 포함 확인 | ReportData에 severity_distribution, score_trend 데이터 존재 | `render_pdf(data, "/tmp/test_chart.pdf")` | PDF 페이지 수 >= 3 (표지 + 요약 + 통계) |
| U-1010 | `CISOReportRenderer.render_pdf()` | 빈 데이터 처리 | ReportData: 취약점 0건, 스캔 0건 | `render_pdf(data, "/tmp/test_empty.pdf")` | PDF 생성 성공 (빈 차트/테이블 처리), 에러 없음 |
| U-1011 | `CISOReportRenderer.render_json()` | JSON 생성 성공 | ReportData 완성 | `render_json(data, "/tmp/test.json")` | 유효한 JSON 파일, 필수 키 (security_score, vulnerabilities, scans) 포함 |

### ReportRenderer -- 인증 증적

| ID | 대상 | 시나리오 | Arrange | Act | Assert |
|----|------|----------|---------|-----|--------|
| U-1012 | `CSAPReportRenderer.render_pdf()` | CSAP 증적 PDF 생성 | ReportData 완성 | `render_pdf(data, "/tmp/csap.pdf")` | PDF 생성 성공, "취약점 관리 프로세스" 섹션 포함 |
| U-1013 | `CSAPReportRenderer.render_json()` | CSAP 증적 JSON 생성 | ReportData 완성 | `render_json(data, "/tmp/csap.json")` | 유효한 JSON, `vulnerability_management`, `scan_history`, `patch_history` 키 포함 |
| U-1014 | `ISO27001ReportRenderer.render_pdf()` | ISO 27001 증적 PDF | ReportData 완성 | `render_pdf(data, "/tmp/iso.pdf")` | PDF 생성 성공, "A.12.6.1", "A.14.2.1" 항목 번호 포함 |
| U-1015 | `ISO27001ReportRenderer.render_json()` | ISO 27001 증적 JSON | ReportData 완성 | `render_json(data, "/tmp/iso.json")` | 유효한 JSON, CWE/OWASP 매핑 데이터 포함 |
| U-1016 | `ISMSReportRenderer.render_pdf()` | ISMS 증적 PDF | ReportData 완성 | `render_pdf(data, "/tmp/isms.pdf")` | PDF 생성 성공, "2.10.4", "2.11.5" 항목 번호 포함 |
| U-1017 | `ISMSReportRenderer.render_json()` | ISMS 증적 JSON | ReportData 완성 | `render_json(data, "/tmp/isms.json")` | 유효한 JSON, 취약점 조치율/평균 조치일 포함 |

### ReportRenderer 팩토리

| ID | 대상 | 시나리오 | 입력 | 예상 결과 |
|----|------|----------|------|-----------|
| U-1018 | `get_report_renderer()` | "ciso" 유형 | `"ciso"` | `CISOReportRenderer` 인스턴스 |
| U-1019 | `get_report_renderer()` | "csap" 유형 | `"csap"` | `CSAPReportRenderer` 인스턴스 |
| U-1020 | `get_report_renderer()` | "iso27001" 유형 | `"iso27001"` | `ISO27001ReportRenderer` 인스턴스 |
| U-1021 | `get_report_renderer()` | "isms" 유형 | `"isms"` | `ISMSReportRenderer` 인스턴스 |
| U-1022 | `get_report_renderer()` | 미지원 유형 | `"soc2"` | `ValueError` 발생 |

### EmailService

| ID | 대상 | 시나리오 | Arrange | Act | Assert |
|----|------|----------|---------|-----|--------|
| U-1023 | `send_report_email()` | 이메일 발송 성공 | smtplib mock: 정상 | `send_report_email(recipients, subject, body, attachment)` | `True` 반환, smtplib.sendmail 1회 호출, 수신자 목록 정확 |
| U-1024 | `send_report_email()` | SMTP 연결 실패 | smtplib mock: ConnectionRefusedError | `send_report_email(...)` | `False` 반환, 에러 로깅 |
| U-1025 | `send_report_email()` | 첨부 파일 확인 | smtplib mock 정상, PDF 파일 경로 | `send_report_email(...)` | MIMEMultipart에 PDF 첨부 포함 |
| U-1026 | `send_report_email()` | 다수 수신자 | 수신자 3명 | `send_report_email(["a@co.com", "b@co.com", "c@co.com"], ...)` | sendmail 호출 시 수신자 3명 포함 |

### 스케줄러

| ID | 대상 | 시나리오 | Arrange | Act | Assert |
|----|------|----------|---------|-----|--------|
| U-1027 | `calculate_next_generation()` | weekly | current=2026-02-25 | `calculate_next_generation("weekly", dt)` | 2026-03-04 (+ 7일) |
| U-1028 | `calculate_next_generation()` | monthly | current=2026-02-25 | `calculate_next_generation("monthly", dt)` | 2026-03-01 00:00:00 UTC |
| U-1029 | `calculate_next_generation()` | quarterly | current=2026-02-25 | `calculate_next_generation("quarterly", dt)` | 2026-04-01 00:00:00 UTC |
| U-1030 | `calculate_next_generation()` | quarterly (12월) | current=2026-12-15 | `calculate_next_generation("quarterly", dt)` | 2027-01-01 00:00:00 UTC |
| U-1031 | `calculate_next_generation()` | 미지원 주기 | `"daily"` | `calculate_next_generation("daily", dt)` | `ValueError` 발생 |
| U-1032 | `check_and_enqueue_reports()` | 생성 필요한 설정 2건 | report_config: 2건 (next_generation_at <= now, is_active=True) | `check_and_enqueue_reports()` | RQ 큐에 2건 등록, next_generation_at 업데이트 |
| U-1033 | `check_and_enqueue_reports()` | 비활성 설정 무시 | report_config: 1건 (is_active=False, next_generation_at <= now) | `check_and_enqueue_reports()` | RQ 큐에 0건 등록 |

### ReportConfig / ReportHistory 모델

| ID | 대상 | 시나리오 | Arrange | Act | Assert |
|----|------|----------|---------|-----|--------|
| U-1034 | `ReportConfig` | 기본 생성 | 필수 필드만 | `ReportConfig(team_id=..., report_type="ciso", schedule="monthly", email_recipients=[], created_by=...)` | is_active=True, DB 저장 성공 |
| U-1035 | `ReportConfig` | 팀+유형 유니크 제약 | 동일 team_id + report_type으로 2건 생성 시도 | 2번째 insert | IntegrityError 발생 |
| U-1036 | `ReportHistory` | 생성 시 기본 상태 | 필수 필드만 | `ReportHistory(...)` | status="generating" |

---

## 통합 테스트

### 리포트 수동 생성

| ID | API | 시나리오 | Arrange | Act | Assert |
|----|-----|----------|---------|-----|--------|
| I-1001 | `POST /reports/generate` | CISO PDF 리포트 수동 생성 | 인증된 사용자 (admin), 저장소 2개 + 취약점 15건 | `POST /api/v1/reports/generate` + body (type=ciso, format=pdf) | 202, report_id 반환, DB에 ReportHistory status="generating" |
| I-1002 | `POST /reports/generate` | 권한 부족 (member) | 인증된 사용자 (member 역할) | `POST /api/v1/reports/generate` | 403, "권한 부족" |
| I-1003 | `POST /reports/generate` | 잘못된 report_type | 인증된 사용자 (admin) | `POST /api/v1/reports/generate` + body (type="invalid") | 422, "잘못된 report_type" |
| I-1004 | `POST /reports/generate` | 잘못된 기간 범위 | period_start > period_end | `POST /api/v1/reports/generate` | 422, "시작일이 종료일보다 이후" |

### 리포트 콘텐츠 검증

| ID | API | 시나리오 | Arrange | Act | Assert |
|----|-----|----------|---------|-----|--------|
| I-1005 | 워커 | CISO 리포트에 보안 점수 추이 포함 | 저장소 2개 (보안 점수 75, 85), 30일간 취약점 추이 데이터 | 리포트 생성 워커 실행 | 생성된 PDF 파일 존재, ReportHistory.metadata에 security_score 포함 |
| I-1006 | 워커 | CISO 리포트에 취약점 통계 포함 | 취약점 20건 (critical 3, high 7, medium 5, low 5) | 리포트 생성 워커 실행 | ReportHistory.metadata.severity_distribution 정확 |
| I-1007 | 워커 | CISO 리포트에 대응 현황 포함 | 패치 PR 5건 (merged 3, created 2) | 리포트 생성 워커 실행 | ReportHistory.metadata에 auto_patch_rate 포함 |

### CSAP 증적

| ID | API | 시나리오 | Arrange | Act | Assert |
|----|-----|----------|---------|-----|--------|
| I-1008 | `POST /reports/generate` | CSAP PDF 증적 생성 | admin, 스캔 10건, 패치 5건, 미조치 2건 | `POST /api/v1/reports/generate` (type=csap, format=pdf) | 202, 생성 완료 후 PDF에 스캔 이력/패치 이력/미조치 현황 포함 |
| I-1009 | `POST /reports/generate` | CSAP JSON 증적 생성 | admin, 동일 데이터 | `POST /api/v1/reports/generate` (type=csap, format=json) | 202, 생성 완료 후 JSON에 `vulnerability_management`, `scan_history` 키 존재 |

### ISO 27001 증적

| ID | API | 시나리오 | Arrange | Act | Assert |
|----|-----|----------|---------|-----|--------|
| I-1010 | `POST /reports/generate` | ISO 27001 PDF 증적 생성 | admin, CWE/OWASP 매핑된 취약점 존재 | `POST /api/v1/reports/generate` (type=iso27001, format=pdf) | 202, 생성 완료 후 PDF에 A.12.6.1 항목 데이터 포함 |
| I-1011 | `POST /reports/generate` | ISO 27001 JSON 증적 생성 | admin, 동일 데이터 | `POST /api/v1/reports/generate` (type=iso27001, format=json) | 202, 생성 완료 후 JSON에 CWE/OWASP 매핑 포함 |

### ISMS 증적

| ID | API | 시나리오 | Arrange | Act | Assert |
|----|-----|----------|---------|-----|--------|
| I-1012 | `POST /reports/generate` | ISMS PDF 증적 생성 | admin, 취약점 점검 및 조치 이력 존재 | `POST /api/v1/reports/generate` (type=isms, format=pdf) | 202, 생성 완료 후 PDF에 2.10.4 항목 데이터 포함 |
| I-1013 | `POST /reports/generate` | ISMS JSON 증적 생성 | admin, 동일 데이터 | `POST /api/v1/reports/generate` (type=isms, format=json) | 202, 생성 완료 후 JSON에 취약점 조치율 데이터 포함 |

### 스케줄 설정 및 자동 생성

| ID | API | 시나리오 | Arrange | Act | Assert |
|----|-----|----------|---------|-----|--------|
| I-1014 | `POST /reports/config` | 주간 스케줄 설정 | admin | `POST /api/v1/reports/config` (schedule=weekly, type=ciso) | 201, next_generation_at = 현재 + 7일 |
| I-1015 | `POST /reports/config` | 월간 스케줄 설정 | admin | `POST /api/v1/reports/config` (schedule=monthly, type=csap) | 201, next_generation_at = 다음 달 1일 |
| I-1016 | `POST /reports/config` | 분기 스케줄 설정 | admin | `POST /api/v1/reports/config` (schedule=quarterly, type=iso27001) | 201, next_generation_at = 다음 분기 시작일 |
| I-1016a | `GET /reports/config` | 스케줄 목록 조회 | admin, 설정 3건 존재 | `GET /api/v1/reports/config` | 200, 3건 반환 |
| I-1016b | `PATCH /reports/config/{id}` | 스케줄 변경 | admin, 기존 weekly -> monthly | `PATCH /api/v1/reports/config/{id}` (schedule=monthly) | 200, schedule="monthly", next_generation_at 업데이트 |
| I-1016c | `DELETE /reports/config/{id}` | 스케줄 삭제 | admin | `DELETE /api/v1/reports/config/{id}` | 200, DB에서 삭제됨 |

### 이메일 발송

| ID | API | 시나리오 | Arrange | Act | Assert |
|----|-----|----------|---------|-----|--------|
| I-1017 | 워커 | 리포트 생성 후 이메일 자동 발송 | send_email=true, recipients=["ciso@co.com"], smtplib mock | 리포트 생성 워커 실행 | SMTP sendmail 호출됨, ReportHistory.email_sent_at 설정, status="sent" |
| I-1018 | 워커 | 이메일 발송 실패 시 리포트는 유지 | send_email=true, smtplib mock: ConnectionRefusedError | 리포트 생성 워커 실행 | PDF 파일 생성 성공, ReportHistory.status="completed" (sent 아님), 에러 로깅 |
| I-1019 | 워커 | send_email=false 시 발송 안 함 | send_email=false | 리포트 생성 워커 실행 | SMTP sendmail 호출 안 됨, ReportHistory.status="completed" |

### 리포트 이력 조회 및 다운로드

| ID | API | 시나리오 | Arrange | Act | Assert |
|----|-----|----------|---------|-----|--------|
| I-1020 | `GET /reports/history` | 이력 조회 (전체) | 리포트 10건 생성 완료 | `GET /api/v1/reports/history` | 200, 10건 반환, 최신순 정렬 |
| I-1021 | `GET /reports/history?report_type=ciso` | 유형별 필터 | CISO 5건 + CSAP 3건 | `GET /api/v1/reports/history?report_type=ciso` | 200, 5건만 반환 |
| I-1022 | `GET /reports/{id}/download` | PDF 다운로드 성공 | 생성 완료된 리포트, 파일 존재 | `GET /api/v1/reports/{id}/download` | 200, Content-Type: application/pdf, 파일 스트림 |
| I-1023 | `GET /reports/{id}/download` | 생성 중 다운로드 시도 | status="generating" | `GET /api/v1/reports/{id}/download` | 409, "리포트 생성 중" |
| I-1024 | `GET /reports/{id}/download` | 다른 팀의 리포트 | 다른 team_id의 리포트 | `GET /api/v1/reports/{id}/download` | 404 |
| I-1025 | `GET /reports/{id}/download` | JSON 다운로드 | format="json" 리포트 | `GET /api/v1/reports/{id}/download` | 200, Content-Type: application/json |

---

## 경계 조건 / 에러 케이스

- 취약점 0건인 팀의 리포트 생성 시 빈 차트/빈 테이블 처리 (에러 없이 "데이터 없음" 표시)
- period_start = period_end (1일 리포트) 정상 처리
- period 범위가 1년 초과 시 422 에러 (과도한 데이터 방지)
- email_recipients가 빈 배열이고 send_email=true 시 422 에러
- email_recipients에 잘못된 이메일 형식 포함 시 422 에러
- PDF 생성 중 메모리 부족 시 ReportHistory status="failed", error_message 저장
- SMTP 환경변수 미설정 시 이메일 발송 건너뜀 (리포트 생성 자체는 성공)
- 동일 report_type + team_id로 중복 config 생성 시 409 에러
- report_config 삭제 시 관련 report_history는 유지 (파일도 유지)
- 파일 경로에 특수문자 (공백, 한글 팀명) 포함 시 URL 인코딩 처리
- NanumGothic 폰트 파일 누락 시 fallback 폰트 사용 (영문만 표시)
- 대량 취약점 (1000건 이상) 시 PDF 테이블 페이지네이션 처리
- quarterly 스케줄의 period 계산: 이전 분기 전체 (1/1~3/31, 4/1~6/30, ...)

---

## 회귀 테스트

| 기존 기능 | 영향 여부 | 검증 방법 |
|-----------|-----------|-----------|
| F-07 대시보드 | 영향 있음 (헬퍼 함수 리팩터링 시) | 기존 대시보드 summary, trend, repo-scores, team-scores, severity-distribution API 테스트 재실행 |
| F-07 보안 점수 계산 | 영향 없음 (읽기 전용 사용) | calc_security_score 단위 테스트 재실행 |
| F-08 알림 | 영향 없음 | 기존 알림 테스트 재실행 |
| 스캔 워커 | 영향 있음 (RQ Scheduler 추가) | 기존 스캔 큐 등록/처리 테스트 재실행. reports 큐와 scans 큐 격리 확인 |
