# F-08 Slack/Teams 알림 API 스펙

## 개요

팀 단위 Slack/Teams webhook 알림을 관리하는 API입니다. 취약점 발견 시 실시간 알림 발송 및 주간 보안 리포트 발송을 지원합니다.

## Base URL

```
/api/v1/notifications
```

## 인증

모든 엔드포인트는 JWT Bearer 토큰 인증이 필요합니다.

```
Authorization: Bearer <jwt_token>
```

## 공통 응답 형식

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

---

## 엔드포인트

### 1. 알림 설정 생성

**POST** `/api/v1/notifications/config`

팀의 Slack/Teams webhook 알림 설정을 등록합니다. owner/admin 권한이 필요합니다.

#### 권한

- `owner` 또는 `admin` 역할 필요

#### 요청 본문

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| platform | string | Y | 알림 플랫폼 (`slack` / `teams`) |
| webhook_url | string | Y | Webhook URL (HTTPS 필수, slack.com 또는 office.com 도메인) |
| severity_threshold | string | N | 알림 기준 심각도 (`critical` / `high` / `medium` / `all`, 기본: `all`) |
| weekly_report_enabled | boolean | N | 주간 리포트 발송 여부 (기본: false) |
| weekly_report_day | integer | N | 주간 리포트 발송 요일 1=월 ~ 7=일 (기본: 1) |

```json
{
  "platform": "slack",
  "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXX",
  "severity_threshold": "high",
  "weekly_report_enabled": true,
  "weekly_report_day": 1
}
```

#### 응답 201 Created

```json
{
  "success": true,
  "data": {
    "id": "11111111-1111-1111-1111-111111111111",
    "team_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
    "platform": "slack",
    "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXX",
    "severity_threshold": "high",
    "weekly_report_enabled": true,
    "weekly_report_day": 1,
    "is_active": true,
    "created_by": "00000000-0000-0000-0000-000000000001",
    "created_at": "2026-02-25T10:00:00Z",
    "updated_at": "2026-02-25T10:00:00Z"
  },
  "error": null
}
```

#### 오류 응답

| 코드 | 사유 |
|------|------|
| 400 | 유효하지 않은 webhook URL (HTTPS 아님, 허용 외 도메인, 내부 IP) |
| 403 | 팀 미소속 또는 owner/admin 권한 없음 |
| 422 | 요청 본문 유효성 검증 실패 (잘못된 platform, severity_threshold) |

---

### 2. 알림 설정 목록 조회

**GET** `/api/v1/notifications/config`

현재 사용자 팀의 알림 설정 목록을 조회합니다.

#### 권한

- 팀 멤버 모두 가능

#### 응답 200 OK

```json
{
  "success": true,
  "data": [
    {
      "id": "11111111-1111-1111-1111-111111111111",
      "team_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
      "platform": "slack",
      "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXX",
      "severity_threshold": "high",
      "weekly_report_enabled": true,
      "weekly_report_day": 1,
      "is_active": true,
      "created_by": "00000000-0000-0000-0000-000000000001",
      "created_at": "2026-02-25T10:00:00Z",
      "updated_at": "2026-02-25T10:00:00Z"
    }
  ],
  "error": null
}
```

팀에 소속되지 않은 경우 빈 배열을 반환합니다.

---

### 3. 알림 설정 수정

**PATCH** `/api/v1/notifications/config/{config_id}`

지정된 알림 설정을 부분 업데이트합니다.

#### 파라미터

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| config_id | UUID | 알림 설정 ID |

#### 권한

- `owner` 또는 `admin` 역할 필요

#### 요청 본문 (모든 필드 선택)

```json
{
  "webhook_url": "https://hooks.slack.com/services/NEW_URL",
  "severity_threshold": "critical",
  "weekly_report_enabled": false,
  "weekly_report_day": 5,
  "is_active": true
}
```

#### 응답 200 OK

```json
{
  "success": true,
  "data": {
    "id": "11111111-1111-1111-1111-111111111111",
    "severity_threshold": "critical",
    ...
  },
  "error": null
}
```

#### 오류 응답

| 코드 | 사유 |
|------|------|
| 400 | 유효하지 않은 webhook URL |
| 403 | 권한 없음 |
| 404 | 설정을 찾을 수 없음 |

---

### 4. 알림 설정 삭제

**DELETE** `/api/v1/notifications/config/{config_id}`

지정된 알림 설정을 영구 삭제합니다.

#### 파라미터

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| config_id | UUID | 알림 설정 ID |

#### 권한

- `owner` 또는 `admin` 역할 필요

#### 응답 200 OK

```json
{
  "success": true,
  "data": {
    "id": "11111111-1111-1111-1111-111111111111",
    ...
  },
  "error": null
}
```

#### 오류 응답

| 코드 | 사유 |
|------|------|
| 403 | 권한 없음 |
| 404 | 설정을 찾을 수 없음 |

---

### 5. 테스트 알림 발송

**POST** `/api/v1/notifications/config/{config_id}/test`

지정된 설정으로 테스트 메시지를 발송합니다. webhook 연결 상태를 즉시 확인할 수 있습니다.

#### 파라미터

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| config_id | UUID | 알림 설정 ID |

#### 권한

- 팀 멤버 모두 가능

#### 응답 200 OK

```json
{
  "success": true,
  "data": {
    "sent": true,
    "http_status": 200,
    "error": null,
    "platform": "slack"
  },
  "error": null
}
```

webhook 발송 실패 시:

```json
{
  "success": true,
  "data": {
    "sent": false,
    "http_status": 400,
    "error": "channel_not_found",
    "platform": "slack"
  },
  "error": null
}
```

#### 오류 응답

| 코드 | 사유 |
|------|------|
| 403 | 팀 미소속 |
| 404 | 설정을 찾을 수 없음 |

---

### 6. 알림 발송 이력 조회

**GET** `/api/v1/notifications/logs`

현재 사용자 팀의 알림 발송 이력을 최신순으로 조회합니다.

#### 권한

- 팀 멤버 모두 가능

#### 쿼리 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| page | integer | 1 | 페이지 번호 |
| per_page | integer | 20 | 페이지당 항목 수 (최대 100) |
| status | string | null | 상태 필터 (`sent` / `failed`) |

#### 응답 200 OK

```json
{
  "success": true,
  "data": [
    {
      "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      "team_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
      "config_id": "11111111-1111-1111-1111-111111111111",
      "notification_type": "vulnerability",
      "status": "sent",
      "http_status": 200,
      "error_message": null,
      "payload": { "blocks": [...] },
      "sent_at": "2026-02-25T10:00:00Z"
    }
  ],
  "error": null
}
```

---

## 내부 서비스 API (직접 호출 전용)

### NotificationService.send_vulnerability_alert

취약점 발견 시 스캔 파이프라인에서 자동 호출됩니다.

```python
await notification_service.send_vulnerability_alert(
    db=db,
    vuln=vulnerability,
    repo_name="test-org/test-repo",
    patch_pr_url="https://github.com/test-org/test-repo/pull/42",
)
```

처리 흐름:
1. 취약점 → 저장소 → 팀 ID 조회
2. 팀의 활성 알림 설정 조회
3. `severity_threshold` 필터링
4. 플랫폼별 payload 포맷
5. HTTP POST 발송 (httpx, timeout=10s)
6. `notification_log` 기록

발송 실패 시 스캔 파이프라인을 블로킹하지 않습니다 (예외 내부 처리).

---

## SSRF 방어 규칙

`validate_webhook_url()` 함수는 다음 순서로 검증합니다:

1. HTTPS 프로토콜 필수
2. 허용 도메인 목록 검증:
   - `hooks.slack.com`
   - `slack.com`
   - `outlook.office.com`
   - `office.com`
   - `webhook.office.com`
3. DNS 해석 후 내부 IP 차단:
   - `127.x.x.x` (localhost)
   - `10.x.x.x` (Class A private)
   - `192.168.x.x` (Class C private)
   - `172.16.x.x ~ 172.31.x.x` (Class B private)
   - `::1` (IPv6 loopback)

---

## 심각도 임계값 필터링

| threshold | 발송 대상 심각도 |
|-----------|----------------|
| `all` | critical, high, medium, low |
| `medium` | critical, high, medium |
| `high` | critical, high |
| `critical` | critical |
