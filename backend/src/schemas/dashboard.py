"""대시보드 관련 요청/응답 스키마 (설계서 4-5절, F-07)"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class RecentScanItem(BaseModel):
    """최근 스캔 항목 (대시보드 요약에 포함)"""

    id: uuid.UUID
    repo_full_name: str
    status: str
    findings_count: int
    true_positives_count: int
    created_at: datetime


class DashboardSummary(BaseModel):
    """대시보드 요약 통계"""

    total_vulnerabilities: int
    # 심각도별 분포: critical / high / medium / low
    severity_distribution: dict[str, int]
    # 상태별 분포: open / patched / ignored / false_positive
    status_distribution: dict[str, int]
    # 해결률: (patched + false_positive) / total * 100
    resolution_rate: float
    # 최근 5건 스캔 목록
    recent_scans: list[RecentScanItem]
    # 저장소 수
    repo_count: int
    # 마지막 스캔 완료 시각
    last_scan_at: datetime | None
    # F-07: 팀 저장소들의 평균 보안 점수
    avg_security_score: float = 0.0


class TrendDataPoint(BaseModel):
    """날짜별 취약점 추이 데이터 포인트"""

    date: str
    # 해당 날짜에 신규 탐지된 취약점 수
    new_count: int
    # 해당 날짜에 해결된 취약점 수 (patched + false_positive)
    resolved_count: int
    # F-07: 해당 날짜 기준 미해결(open) 누적 취약점 수
    open_count: int = 0


class TrendResponse(BaseModel):
    """취약점 추이 응답"""

    days: int
    data: list[TrendDataPoint]


# ---------------------------------------------------------------------------
# F-07 신규 스키마
# ---------------------------------------------------------------------------


class RepoScoreItem(BaseModel):
    """저장소별 보안 점수 항목"""

    repo_id: uuid.UUID
    repo_full_name: str
    security_score: float
    open_vulns_count: int
    total_vulns_count: int


class RepoScoreResponse(BaseModel):
    """저장소별 보안 점수 응답"""

    items: list[RepoScoreItem]
    total: int


class TeamScoreItem(BaseModel):
    """팀별 보안 점수 집계 항목"""

    team_id: uuid.UUID
    avg_score: float
    repo_count: int
    total_open_vulns: int


class TeamScoreResponse(BaseModel):
    """팀별 보안 점수 집계 응답"""

    items: list[TeamScoreItem]
    total: int


class SeverityDistributionResponse(BaseModel):
    """심각도별 취약점 분포 응답"""

    critical: int
    high: int
    medium: int
    low: int
    total: int
