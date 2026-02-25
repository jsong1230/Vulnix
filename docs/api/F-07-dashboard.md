# F-07 대시보드 API 스펙 확정본

## 개요

저장소별/팀별 보안 점수, 심각도별 분포, 취약점 추이(미해결 누적 포함)를 제공하는 대시보드 확장 API.

---

## 1. GET /api/v1/dashboard/repo-scores

저장소별 보안 점수를 반환한다.

### 인증

Bearer 토큰 필수 (`Authorization: Bearer {token}`)

### 응답

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "repo_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "repo_full_name": "org/repo-name",
        "security_score": 65.0,
        "open_vulns_count": 5,
        "total_vulns_count": 10
      }
    ],
    "total": 1
  },
  "error": null
}
```

### 보안 점수 계산 공식

```
score = max(0, 100 - (critical*25 + high*10 + medium*5 + low*1))
```

open 상태 취약점만 감점 대상. 취약점이 없으면 100점.

### 오류

| 상태 코드 | 설명 |
|---------|------|
| 401 | 인증 없음 |

---

## 2. GET /api/v1/dashboard/team-scores

팀 내 저장소들의 평균 보안 점수를 집계하여 반환한다.

### 인증

Bearer 토큰 필수

### 응답

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "team_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
        "avg_score": 72.5,
        "repo_count": 3,
        "total_open_vulns": 12
      }
    ],
    "total": 1
  },
  "error": null
}
```

### 오류

| 상태 코드 | 설명 |
|---------|------|
| 401 | 인증 없음 |

---

## 3. GET /api/v1/dashboard/severity-distribution

심각도별 취약점 분포를 반환한다.

### 인증

Bearer 토큰 필수

### 쿼리 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| repository_id | UUID | 아니오 | 특정 저장소 필터 (없으면 팀 전체) |

### 응답

```json
{
  "success": true,
  "data": {
    "critical": 2,
    "high": 5,
    "medium": 10,
    "low": 15,
    "total": 32
  },
  "error": null
}
```

### 비고

- `total = critical + high + medium + low`
- `repository_id`가 팀에 속하지 않으면 모든 값이 0인 응답 반환

### 오류

| 상태 코드 | 설명 |
|---------|------|
| 401 | 인증 없음 |

---

## 4. GET /api/v1/dashboard/summary (수정)

기존 응답에 `avg_security_score` 필드가 추가됨.

### 추가된 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| avg_security_score | float | 팀 저장소들의 평균 보안 점수 (0.0 ~ 100.0) |

### 응답 예시 (추가 필드 포함)

```json
{
  "success": true,
  "data": {
    "total_vulnerabilities": 10,
    "severity_distribution": {"critical": 1, "high": 2, "medium": 3, "low": 4},
    "status_distribution": {"open": 7, "patched": 2, "ignored": 1, "false_positive": 0},
    "resolution_rate": 20.0,
    "recent_scans": [],
    "repo_count": 1,
    "last_scan_at": "2026-02-25T10:02:00Z",
    "avg_security_score": 65.0
  },
  "error": null
}
```

---

## 5. GET /api/v1/dashboard/trend (수정)

각 데이터 포인트에 `open_count` (미해결 누적 수) 필드가 추가됨.

### 추가된 필드 (TrendDataPoint)

| 필드 | 타입 | 설명 |
|------|------|------|
| open_count | int | 해당 날짜까지의 미해결 취약점 누적 수 (>= 0) |

### 응답 예시 (추가 필드 포함)

```json
{
  "success": true,
  "data": {
    "days": 7,
    "data": [
      {
        "date": "2026-02-19",
        "new_count": 3,
        "resolved_count": 1,
        "open_count": 2
      },
      {
        "date": "2026-02-20",
        "new_count": 0,
        "resolved_count": 0,
        "open_count": 2
      }
    ]
  },
  "error": null
}
```

### open_count 계산 방식

날짜순 누적 계산: `open_count(day) = open_count(day-1) + new_count - resolved_count`, 최솟값 0.

---

## 6. GET /api/v1/vulnerabilities (수정)

`vulnerability_type` 쿼리 파라미터 필터가 추가됨.

### 추가된 쿼리 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| vulnerability_type | string | 아니오 | 취약점 유형 필터 (예: sql_injection, xss, hardcoded_credentials) |

### 응답 형식

기존과 동일 (`PaginatedResponse[VulnerabilitySummary]`)

### 필터 조합 예시

```
GET /api/v1/vulnerabilities?vulnerability_type=sql_injection&severity=high
GET /api/v1/vulnerabilities?vulnerability_type=xss&status=open&page=2
```
