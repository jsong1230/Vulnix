# F-07 대시보드 기능 설계서

## 1. 개요

저장소별/팀별 보안 점수, 취약점 추이 그래프, 심각도별 분포, 취약점 유형 필터를 제공하는 대시보드 확장 기능.

## 2. 기능 요구사항

- 저장소별 보안 점수 조회 API
- 팀별 보안 점수 집계 API
- 취약점 추이에 미해결(open) 누적 수 포함
- 심각도별 취약점 분포 API (저장소 필터 지원)
- 취약점 목록에 유형(vulnerability_type) 필터 추가
- 대시보드 요약에 평균 보안 점수(avg_security_score) 포함

## 3. API 설계

### 3-1. GET /api/v1/dashboard/repo-scores

저장소별 보안 점수 목록 반환.

**응답 예시:**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "repo_id": "uuid",
        "repo_full_name": "org/repo",
        "security_score": 85.0,
        "open_vulns_count": 3,
        "total_vulns_count": 10
      }
    ],
    "total": 1
  }
}
```

### 3-2. GET /api/v1/dashboard/team-scores

팀 내 저장소들의 평균 보안 점수 집계.

**응답 예시:**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "team_id": "uuid",
        "avg_score": 80.0,
        "repo_count": 5,
        "total_open_vulns": 12
      }
    ],
    "total": 1
  }
}
```

### 3-3. GET /api/v1/dashboard/severity-distribution

심각도별 취약점 분포. `repository_id` 쿼리 파라미터로 필터 가능.

**응답 예시:**
```json
{
  "success": true,
  "data": {
    "critical": 2,
    "high": 5,
    "medium": 10,
    "low": 15,
    "total": 32
  }
}
```

### 3-4. GET /api/v1/dashboard/summary (수정)

기존 응답에 `avg_security_score` 필드 추가.

### 3-5. GET /api/v1/dashboard/trend (수정)

각 데이터 포인트에 `open_count` (미해결 누적 수) 추가.

### 3-6. GET /api/v1/vulns (수정)

`vulnerability_type` 쿼리 파라미터 필터 추가.

## 4. 보안 점수 계산 공식

```
score = max(0, 100 - (critical*25 + high*10 + medium*5 + low*1))
```

## 5. 스키마 변경

### 신규 스키마
- `RepoScoreItem`: repo_id, repo_full_name, security_score, open_vulns_count, total_vulns_count
- `RepoScoreResponse`: items, total
- `TeamScoreItem`: team_id, avg_score, repo_count, total_open_vulns
- `TeamScoreResponse`: items, total
- `SeverityDistributionResponse`: critical, high, medium, low, total

### 기존 스키마 수정
- `TrendDataPoint`: open_count 필드 추가
- `DashboardSummary`: avg_security_score 필드 추가

## 6. 인덱스 계획

- `idx_vulnerability_type` — vulnerability.vulnerability_type
- `idx_vulnerability_detected_at` — vulnerability.detected_at
