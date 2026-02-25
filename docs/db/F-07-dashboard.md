# F-07 대시보드 DB 스키마 확정본

## 변경 사항 요약

F-07은 신규 테이블을 추가하지 않으며, 기존 `vulnerability` 테이블에 성능 인덱스만 추가한다.

---

## 마이그레이션 파일

`alembic/versions/004_add_f07_indexes.py`

---

## 추가된 인덱스

### idx_vulnerability_type

| 항목 | 값 |
|------|------|
| 테이블 | vulnerability |
| 컬럼 | vulnerability_type |
| 유형 | B-Tree (기본) |
| 목적 | `GET /api/v1/vulnerabilities?vulnerability_type=...` 필터 성능 향상 |

### idx_vulnerability_detected_at

| 항목 | 값 |
|------|------|
| 테이블 | vulnerability |
| 컬럼 | detected_at |
| 유형 | B-Tree (기본) |
| 목적 | 날짜 범위 기반 추이 쿼리 (`trend` 엔드포인트) 성능 향상 |

---

## 기존 테이블 참조 (변경 없음)

### vulnerability 테이블 (F-07 관련 컬럼)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| vulnerability_type | VARCHAR(100) | 취약점 유형 (sql_injection, xss 등) — F-07 필터 대상 |
| detected_at | TIMESTAMP WITH TIME ZONE | 탐지 시각 — 추이 집계 기준 |
| resolved_at | TIMESTAMP WITH TIME ZONE | 해결 시각 — 추이 집계 기준 |
| severity | VARCHAR(20) | 심각도 (critical/high/medium/low) — 분포/점수 계산 |
| status | VARCHAR(20) | 상태 (open/patched/ignored/false_positive) — 점수 계산 |
| repo_id | UUID (FK) | 저장소 ID — 저장소별/팀별 집계 |

### repository 테이블 (F-07 관련 컬럼)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| security_score | NUMERIC(5,2) | 보안 점수 (F-07 공식으로 동기 계산, 취약점 상태 변경 시 갱신) |
| team_id | UUID (FK) | 팀 ID — 팀별 집계 기준 |

---

## 보안 점수 계산 공식

```python
score = max(0.0, 100.0 - (critical*25 + high*10 + medium*5 + low*1))
```

- open 상태 취약점만 감점 대상
- 취약점 0건이면 100점
- 계산 결과는 0.0 ~ 100.0 범위
