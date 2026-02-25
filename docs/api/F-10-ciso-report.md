# F-10 CISO 리포트 및 인증 증적 — API 스펙 확정본

> 작성일: 2026-02-25
> 버전: 1.0.0
> Base URL: `/api/v1/reports`

---

## 개요

CISO 보고서(PDF) 자동 생성, CSAP/ISO 27001/ISMS 인증 증적 자료 출력, 스케줄 설정 및 이메일 발송 기능을 제공한다.

- 모든 요청은 `Authorization: Bearer <jwt>` 헤더가 필요하다.
- 응답 형식: `{ "success": bool, "data": T | null, "error": string | null }`

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| POST | `/generate` | 리포트 수동 생성 (비동기) | owner / admin |
| GET | `/history` | 리포트 생성 이력 조회 | 팀 멤버 전체 |
| GET | `/{report_id}/download` | 생성된 파일 다운로드 | 팀 멤버 전체 |
| POST | `/config` | 스케줄 설정 생성 | owner / admin |
| GET | `/config` | 스케줄 설정 목록 조회 | 팀 멤버 전체 |
| PATCH | `/config/{config_id}` | 스케줄 설정 수정 | owner / admin |
| DELETE | `/config/{config_id}` | 스케줄 설정 삭제 | owner / admin |

---

## POST `/generate`

리포트를 비동기로 생성한다. 즉시 202를 반환하고 RQ 큐에 생성 작업을 등록한다.

### 권한

owner, admin

### 요청 Body

```json
{
  "report_type": "ciso",
  "format": "pdf",
  "period_start": "2026-02-01",
  "period_end": "2026-02-28",
  "send_email": false,
  "email_recipients": []
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `report_type` | string | Y | `ciso` / `csap` / `iso27001` / `isms` |
| `format` | string | N | `pdf` (기본) / `json` |
| `period_start` | date | Y | 리포트 기간 시작일 |
| `period_end` | date | Y | 리포트 기간 종료일 |
| `send_email` | bool | N | 완료 시 이메일 발송 여부 (기본 false) |
| `email_recipients` | array\<email\> | N | 수신자 목록 (`send_email=true` 시 필수) |

#### 유효성 검사 규칙

- `period_start` < `period_end`
- 기간 최대 366일
- `send_email=true` 이면 `email_recipients` 비어있지 않아야 함

### 응답 202

```json
{
  "success": true,
  "data": {
    "report_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "status": "generating",
    "report_type": "ciso",
    "estimated_completion_seconds": 30
  },
  "error": null
}
```

### 오류

| 코드 | 조건 |
|------|------|
| 401 | 인증 없음 |
| 403 | member 역할 (owner/admin 아님) |
| 422 | 유효성 검사 실패 |

---

## GET `/history`

팀의 리포트 생성 이력을 조회한다. 페이지네이션 지원.

### 쿼리 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| `report_type` | string | - | 유형 필터 (ciso / csap / iso27001 / isms) |
| `status` | string | - | 상태 필터 (generating / completed / failed) |
| `page` | int | 1 | 페이지 번호 (1 이상) |
| `per_page` | int | 20 | 페이지당 항목 수 (1~100) |

### 응답 200

```json
{
  "success": true,
  "data": [
    {
      "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      "config_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      "team_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
      "report_type": "ciso",
      "format": "pdf",
      "file_path": "/data/reports/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.pdf",
      "file_size_bytes": 245760,
      "period_start": "2026-02-01",
      "period_end": "2026-02-28",
      "status": "completed",
      "email_sent_at": null,
      "email_recipients": null,
      "error_message": null,
      "metadata": {
        "security_score": 75.5,
        "total_vulnerabilities": 42,
        "critical_count": 3
      },
      "generated_by": "00000000-0000-0000-0000-000000000001",
      "created_at": "2026-02-25T10:00:00"
    }
  ],
  "error": null
}
```

### 오류

| 코드 | 조건 |
|------|------|
| 401 | 인증 없음 |

---

## GET `/{report_id}/download`

생성된 리포트 파일을 다운로드한다.

### 응답 200

- Content-Type: `application/pdf` 또는 `application/json`
- Content-Disposition: `attachment; filename="{report_type}_report_{period_start}.{format}"`

### 오류

| 코드 | 조건 |
|------|------|
| 401 | 인증 없음 |
| 404 | 존재하지 않거나 다른 팀의 리포트 |
| 409 | 아직 생성 중 (`status='generating'`) |
| 410 | 파일이 서버에서 삭제됨 |

---

## POST `/config`

리포트 자동 생성 스케줄 설정을 생성한다.
동일 팀에 동일 `report_type`은 하나만 허용된다.

### 권한

owner, admin

### 요청 Body

```json
{
  "report_type": "ciso",
  "schedule": "monthly",
  "email_recipients": ["ciso@company.com"],
  "is_active": true
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `report_type` | string | Y | `ciso` / `csap` / `iso27001` / `isms` |
| `schedule` | string | Y | `weekly` / `monthly` / `quarterly` |
| `email_recipients` | array\<email\> | N | 수신 이메일 목록 (기본 []) |
| `is_active` | bool | N | 활성 여부 (기본 true) |

### 응답 201

```json
{
  "success": true,
  "data": {
    "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    "team_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
    "report_type": "ciso",
    "schedule": "monthly",
    "email_recipients": ["ciso@company.com"],
    "is_active": true,
    "last_generated_at": null,
    "next_generation_at": "2026-03-01T00:00:00+00:00",
    "created_by": "00000000-0000-0000-0000-000000000001",
    "created_at": "2026-02-25T10:00:00",
    "updated_at": "2026-02-25T10:00:00"
  },
  "error": null
}
```

### 오류

| 코드 | 조건 |
|------|------|
| 401 | 인증 없음 |
| 403 | member 역할 |
| 409 | 동일 팀에 동일 report_type 설정 중복 |
| 422 | 유효성 검사 실패 |

---

## GET `/config`

팀의 스케줄 설정 목록을 조회한다.

### 응답 200

```json
{
  "success": true,
  "data": [
    {
      "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      "team_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
      "report_type": "ciso",
      "schedule": "monthly",
      "email_recipients": ["ciso@company.com"],
      "is_active": true,
      "last_generated_at": null,
      "next_generation_at": "2026-03-01T00:00:00+00:00",
      "created_by": "00000000-0000-0000-0000-000000000001",
      "created_at": "2026-02-25T10:00:00",
      "updated_at": "2026-02-25T10:00:00"
    }
  ],
  "error": null
}
```

### 오류

| 코드 | 조건 |
|------|------|
| 401 | 인증 없음 |

---

## PATCH `/config/{config_id}`

스케줄 설정을 부분 업데이트한다.
`schedule` 변경 시 `next_generation_at`이 자동 재계산된다.

### 권한

owner, admin

### 요청 Body (모든 필드 선택)

```json
{
  "schedule": "quarterly",
  "email_recipients": ["ciso@company.com", "cto@company.com"],
  "is_active": false
}
```

### 응답 200

`ReportConfigResponse` (POST /config와 동일 구조)

### 오류

| 코드 | 조건 |
|------|------|
| 401 | 인증 없음 |
| 403 | member 역할 |
| 404 | 설정 없음 또는 다른 팀 |
| 422 | 유효성 검사 실패 |

---

## DELETE `/config/{config_id}`

스케줄 설정을 삭제한다.

### 권한

owner, admin

### 응답 200

```json
{
  "success": true,
  "data": {
    "deleted_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
  },
  "error": null
}
```

### 오류

| 코드 | 조건 |
|------|------|
| 401 | 인증 없음 |
| 403 | member 역할 |
| 404 | 설정 없음 또는 다른 팀 |

---

## 스케줄 계산 규칙

| 주기 | next_generation_at 계산 |
|------|------------------------|
| `weekly` | 현재 시각 + 7일 |
| `monthly` | 다음 달 1일 00:00 UTC |
| `quarterly` | 다음 분기 첫날 1일 00:00 UTC (1, 4, 7, 10월) |

---

## 리포트 유형별 생성 내용

| 유형 | 설명 | 주요 섹션 |
|------|------|----------|
| `ciso` | 경영진 보안 현황 요약 | 보안 점수, 취약점 현황, 패치율, 리포지토리 현황 |
| `csap` | 클라우드 서비스 보안 인증 증적 | 2.10.4 취약점 관리, 2.11.5 패치 관리 |
| `iso27001` | ISO 27001 인증 증적 | A.12.6.1 기술적 취약점 관리, A.14.2.1 보안 개발 정책 |
| `isms` | 정보보호 관리체계 증적 | 취약점 관리, 패치 관리, 탐지 현황 |
