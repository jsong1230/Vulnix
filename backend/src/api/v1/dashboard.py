"""대시보드 통계 엔드포인트 (설계서 4-5절, 4-6절, F-07)"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import CurrentUser, DbSession
from src.models.repository import Repository
from src.models.scan_job import ScanJob
from src.models.team import TeamMember
from src.models.vulnerability import Vulnerability
from src.schemas.common import ApiResponse
from src.schemas.dashboard import (
    DashboardSummary,
    RecentScanItem,
    RepoScoreItem,
    RepoScoreResponse,
    SeverityDistributionResponse,
    TeamScoreItem,
    TeamScoreResponse,
    TrendDataPoint,
    TrendResponse,
)
from src.services.fp_filter_service import calculate_fp_rate
from src.services.security_score import calc_security_score

router = APIRouter()


# ---------------------------------------------------------------------------
# DB 헬퍼 함수
# ---------------------------------------------------------------------------

async def _get_user_team_ids(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[uuid.UUID]:
    """현재 사용자가 속한 팀 ID 목록을 반환한다."""
    try:
        result = await db.execute(
            select(TeamMember.team_id).where(TeamMember.user_id == user_id)
        )
        rows = result.scalars().all()
        return [row for row in (rows or []) if isinstance(row, uuid.UUID)]
    except Exception:
        return []


async def _get_repos_by_teams(
    db: AsyncSession,
    team_ids: list[uuid.UUID],
) -> list[Repository]:
    """팀 ID 목록으로 저장소 목록을 반환한다."""
    if not team_ids:
        return []
    try:
        result = await db.execute(
            select(Repository).where(Repository.team_id.in_(team_ids))
        )
        rows = result.scalars().all()
        return list(rows) if rows else []
    except Exception:
        return []


async def _get_vulns_by_repos(
    db: AsyncSession,
    repo_ids: list[uuid.UUID],
) -> list[Vulnerability]:
    """저장소 ID 목록으로 취약점 목록을 반환한다."""
    if not repo_ids:
        return []
    try:
        result = await db.execute(
            select(Vulnerability).where(Vulnerability.repo_id.in_(repo_ids))
        )
        rows = result.scalars().all()
        return list(rows) if rows else []
    except Exception:
        return []


async def _get_recent_scans(
    db: AsyncSession,
    repo_ids: list[uuid.UUID],
    limit: int = 5,
) -> list[ScanJob]:
    """저장소 ID 목록으로 최근 스캔 목록을 반환한다 (최대 limit건)."""
    if not repo_ids:
        return []
    try:
        result = await db.execute(
            select(ScanJob)
            .where(ScanJob.repo_id.in_(repo_ids))
            .order_by(ScanJob.created_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return list(rows) if rows else []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# 보안 점수 계산 헬퍼 (F-07)
# ---------------------------------------------------------------------------

def _calc_security_score_f07(vulns: list[Vulnerability]) -> float:
    """F-07 보안 점수 계산 공식.

    score = max(0, 100 - (critical*25 + high*10 + medium*5 + low*1))
    open 상태 취약점만 감점 대상으로 한다.
    취약점이 0건이면 100점.
    calc_security_score 공통 유틸을 사용한다.
    """
    open_vulns = [v for v in vulns if str(v.status) == "open"]
    if not open_vulns:
        return 100.0

    sev_counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for v in open_vulns:
        sev = str(v.severity) if v.severity else "low"
        if sev in sev_counts:
            sev_counts[sev] += 1

    return calc_security_score(
        critical=sev_counts["critical"],
        high=sev_counts["high"],
        medium=sev_counts["medium"],
        low=sev_counts["low"],
    )


# ---------------------------------------------------------------------------
# 통계 계산 헬퍼
# ---------------------------------------------------------------------------

def _build_summary(
    vulns: list[Vulnerability],
    recent_scans: list[ScanJob],
    repos: list[Repository],
) -> DashboardSummary:
    """대시보드 요약 통계를 계산한다.

    resolution_rate = (patched + false_positive) / total * 100
    avg_security_score = 저장소들의 보안 점수 평균 (F-07)
    """
    total = len(vulns)

    # 심각도별 분포 초기화
    severity_distribution: dict[str, int] = {
        "critical": 0, "high": 0, "medium": 0, "low": 0
    }
    # 상태별 분포 초기화
    status_distribution: dict[str, int] = {
        "open": 0, "patched": 0, "ignored": 0, "false_positive": 0
    }

    for v in vulns:
        sev = str(v.severity) if v.severity else "low"
        if sev in severity_distribution:
            severity_distribution[sev] += 1

        st = str(v.status) if v.status else "open"
        if st in status_distribution:
            status_distribution[st] += 1

    # 해결률 계산 (ZeroDivisionError 방지)
    resolved_count = status_distribution["patched"] + status_distribution["false_positive"]
    resolution_rate = (resolved_count / total * 100) if total > 0 else 0.0

    # 최근 스캔 항목 구성 (repo_full_name 포함)
    repo_map = {r.id: r.full_name for r in repos}
    recent_scan_items: list[RecentScanItem] = []
    for scan in recent_scans[:5]:
        repo_full_name = repo_map.get(scan.repo_id, "unknown/repo")
        recent_scan_items.append(
            RecentScanItem(
                id=scan.id,
                repo_full_name=str(repo_full_name),
                status=str(scan.status),
                findings_count=int(scan.findings_count) if scan.findings_count else 0,
                true_positives_count=int(scan.true_positives_count) if scan.true_positives_count else 0,
                created_at=scan.created_at,
            )
        )

    # 마지막 스캔 완료 시각
    completed_scans = [s for s in recent_scans if s.completed_at is not None]
    last_scan_at = completed_scans[0].completed_at if completed_scans else None

    # F-07: 저장소별 보안 점수 평균 계산
    avg_security_score = _calc_avg_security_score(vulns=vulns, repos=repos)

    return DashboardSummary(
        total_vulnerabilities=total,
        severity_distribution=severity_distribution,
        status_distribution=status_distribution,
        resolution_rate=round(resolution_rate, 1),
        recent_scans=recent_scan_items,
        repo_count=len(repos),
        last_scan_at=last_scan_at,
        avg_security_score=avg_security_score,
    )


def _calc_avg_security_score(
    vulns: list[Vulnerability],
    repos: list[Repository],
) -> float:
    """팀 저장소들의 평균 보안 점수를 계산한다.

    저장소가 없으면 0.0 반환.
    각 저장소의 보안 점수를 F-07 공식으로 계산 후 평균.
    """
    if not repos:
        return 0.0

    # 저장소별 취약점 분류
    repo_vuln_map: dict[uuid.UUID, list[Vulnerability]] = {r.id: [] for r in repos}
    for v in vulns:
        if v.repo_id in repo_vuln_map:
            repo_vuln_map[v.repo_id].append(v)

    # 각 저장소 점수 계산
    scores = [
        _calc_security_score_f07(repo_vulns)
        for repo_vulns in repo_vuln_map.values()
    ]

    return round(sum(scores) / len(scores), 1) if scores else 0.0


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=ApiResponse[DashboardSummary])
async def get_dashboard_summary(
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[DashboardSummary]:
    """전체 요약 통계 (설계서 4-5절).

    반환 데이터:
    - 총 취약점 수 (심각도/상태별 분포)
    - 해결률 (patched + false_positive) / total
    - 최근 스캔 목록 (최대 5개, repo_full_name 포함)
    - 저장소 수
    - F-07: 평균 보안 점수 (avg_security_score)

    ADR-F04-002: Redis 캐시 TTL 5분 (PoC에서는 DB 직접 조회)
    """
    # 현재 사용자의 팀 저장소 목록 조회
    team_ids = await _get_user_team_ids(db=db, user_id=current_user.id)
    repos = await _get_repos_by_teams(db=db, team_ids=team_ids)
    repo_ids = [r.id for r in repos if isinstance(r.id, uuid.UUID)]

    # 취약점 목록 및 최근 스캔 조회
    vulns = await _get_vulns_by_repos(db=db, repo_ids=repo_ids)
    recent_scans = await _get_recent_scans(db=db, repo_ids=repo_ids, limit=5)

    summary = _build_summary(
        vulns=vulns,
        recent_scans=recent_scans,
        repos=repos,
    )

    return ApiResponse(
        success=True,
        data=summary,
        error=None,
    )


@router.get("/false-positive-rate", response_model=ApiResponse[dict])
async def get_dashboard_fp_rate(
    current_user: CurrentUser,
    db: DbSession,
    days: int = 30,
) -> ApiResponse[dict]:
    """오탐율 통계 조회 (설계서 3-6절).

    Args:
        days: 조회 기간 (기본 30일, 최대 90일로 클램핑)

    Returns:
        current_fp_rate, total 집계, trend 배열
    """
    # 최대 90일 제한
    days = min(days, 90)

    # 현재 사용자의 팀 저장소 목록 조회
    team_ids = await _get_user_team_ids(db=db, user_id=current_user.id)
    repos = await _get_repos_by_teams(db=db, team_ids=team_ids)
    repo_ids = [r.id for r in repos if isinstance(r.id, uuid.UUID)]

    if not repo_ids:
        return ApiResponse(
            success=True,
            data={
                "current_fp_rate": 0.0,
                "previous_fp_rate": 0.0,
                "improvement": 0.0,
                "total_scanned": 0,
                "total_true_positives": 0,
                "total_false_positives": 0,
                "total_auto_filtered": 0,
                "trend": [],
                "top_fp_rules": [],
            },
            error=None,
        )

    # 기간 내 스캔 조회
    start_dt = datetime.now(timezone.utc) - timedelta(days=days)
    try:
        scan_result = await db.execute(
            select(ScanJob).where(
                ScanJob.repo_id.in_(repo_ids),
                ScanJob.status == "completed",
                ScanJob.created_at >= start_dt,
            ).order_by(ScanJob.created_at.asc())
        )
        scans = list(scan_result.scalars().all() or [])
    except Exception:
        scans = []

    # 전체 집계
    total_tp = sum(int(s.true_positives_count or 0) for s in scans)
    total_fp = sum(int(s.false_positives_count or 0) for s in scans)
    auto_filtered = sum(
        int(getattr(s, "auto_filtered_count", 0) or 0) for s in scans
    )
    current_fp_rate = calculate_fp_rate(total_tp, total_fp)

    # 이전 기간 집계 (이전 days 기간)
    prev_start_dt = start_dt - timedelta(days=days)
    try:
        prev_scan_result = await db.execute(
            select(ScanJob).where(
                ScanJob.repo_id.in_(repo_ids),
                ScanJob.status == "completed",
                ScanJob.created_at >= prev_start_dt,
                ScanJob.created_at < start_dt,
            )
        )
        prev_scans = list(prev_scan_result.scalars().all() or [])
    except Exception:
        prev_scans = []

    prev_tp = sum(int(s.true_positives_count or 0) for s in prev_scans)
    prev_fp = sum(int(s.false_positives_count or 0) for s in prev_scans)
    previous_fp_rate = calculate_fp_rate(prev_tp, prev_fp)
    improvement = round(previous_fp_rate - current_fp_rate, 2)

    # 일별 추이 집계
    trend_map: dict[str, dict[str, float | int]] = {}
    for i in range(days):
        day = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        trend_map[day] = {"fp_rate": 0.0, "auto_filtered_count": 0}

    for scan in scans:
        if scan.created_at is not None:
            try:
                day_key = scan.created_at.strftime("%Y-%m-%d")
                if day_key in trend_map:
                    s_tp = int(scan.true_positives_count or 0)
                    s_fp = int(scan.false_positives_count or 0)
                    trend_map[day_key]["fp_rate"] = calculate_fp_rate(s_tp, s_fp)
                    trend_map[day_key]["auto_filtered_count"] += int(
                        getattr(scan, "auto_filtered_count", 0) or 0
                    )
            except Exception:
                pass

    trend = [
        {
            "date": day,
            "fp_rate": float(values["fp_rate"]),
            "auto_filtered_count": int(values["auto_filtered_count"]),
        }
        for day, values in sorted(trend_map.items())
    ]

    return ApiResponse(
        success=True,
        data={
            "current_fp_rate": current_fp_rate,
            "previous_fp_rate": previous_fp_rate,
            "improvement": improvement,
            "total_scanned": total_tp + total_fp,
            "total_true_positives": total_tp,
            "total_false_positives": total_fp,
            "total_auto_filtered": auto_filtered,
            "trend": trend,
            "top_fp_rules": [],
        },
        error=None,
    )


@router.get("/trend", response_model=ApiResponse[TrendResponse])
async def get_vulnerability_trend(
    current_user: CurrentUser,
    db: DbSession,
    days: int = 30,
) -> ApiResponse[TrendResponse]:
    """기간별 취약점 발견/해결 추이 (설계서 4-6절).

    Args:
        days: 조회할 일수 (기본 30일, 최대 90일)

    날짜별 신규 취약점 수, 해결 취약점 수, 미해결 누적 수(F-07)를 반환한다.
    """
    # 최대 90일 제한
    days = min(days, 90)

    # 현재 사용자의 팀 저장소 목록 조회
    team_ids = await _get_user_team_ids(db=db, user_id=current_user.id)
    repos = await _get_repos_by_teams(db=db, team_ids=team_ids)
    repo_ids = [r.id for r in repos if isinstance(r.id, uuid.UUID)]

    # 기간 내 취약점 조회
    start_dt = datetime.now(timezone.utc) - timedelta(days=days)

    if repo_ids:
        try:
            result = await db.execute(
                select(Vulnerability).where(
                    Vulnerability.repo_id.in_(repo_ids),
                    Vulnerability.detected_at >= start_dt,
                )
            )
            vulns = list(result.scalars().all() or [])
        except Exception:
            vulns = []
    else:
        vulns = []

    # 날짜별 집계 맵 생성
    trend_map: dict[str, dict[str, int]] = {}
    for i in range(days):
        day = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        trend_map[day] = {"new_count": 0, "resolved_count": 0}

    # 취약점 데이터 집계
    for v in vulns:
        if v.detected_at is not None:
            try:
                day_key = v.detected_at.strftime("%Y-%m-%d")
                if day_key in trend_map:
                    trend_map[day_key]["new_count"] += 1
            except Exception:
                pass

        if v.resolved_at is not None:
            try:
                resolved_day = v.resolved_at.strftime("%Y-%m-%d")
                if resolved_day in trend_map:
                    trend_map[resolved_day]["resolved_count"] += 1
            except Exception:
                pass

    # F-07: 날짜별 open_count 누적 계산
    # 시작 시점의 open 취약점 수 = 전체 - 기간 내 신규 취약점
    # 간단히 새로 탐지된 취약점 수에서 해결된 수를 빼는 방식으로 누적 계산
    running_open = 0
    sorted_days = sorted(trend_map.keys())
    for day in sorted_days:
        running_open += trend_map[day]["new_count"]
        running_open -= trend_map[day]["resolved_count"]
        running_open = max(0, running_open)
        trend_map[day]["open_count"] = running_open

    # 날짜별 데이터 포인트 목록 구성
    data_points = [
        TrendDataPoint(
            date=day,
            new_count=values["new_count"],
            resolved_count=values["resolved_count"],
            open_count=values["open_count"],
        )
        for day, values in sorted(trend_map.items())
    ]

    return ApiResponse(
        success=True,
        data=TrendResponse(days=days, data=data_points),
        error=None,
    )


@router.get("/repo-scores", response_model=ApiResponse[RepoScoreResponse])
async def get_repo_scores(
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[RepoScoreResponse]:
    """저장소별 보안 점수 조회 (F-07 설계서 3-1절).

    각 저장소의 보안 점수, 미해결/전체 취약점 수를 반환한다.
    보안 점수 공식: max(0, 100 - (critical*25 + high*10 + medium*5 + low*1))
    """
    team_ids = await _get_user_team_ids(db=db, user_id=current_user.id)
    repos = await _get_repos_by_teams(db=db, team_ids=team_ids)

    if not repos:
        return ApiResponse(
            success=True,
            data=RepoScoreResponse(items=[], total=0),
            error=None,
        )

    repo_ids = [r.id for r in repos if isinstance(r.id, uuid.UUID)]
    vulns = await _get_vulns_by_repos(db=db, repo_ids=repo_ids)

    # 저장소별 취약점 분류
    repo_vuln_map: dict[uuid.UUID, list[Vulnerability]] = {r.id: [] for r in repos}
    for v in vulns:
        if v.repo_id in repo_vuln_map:
            repo_vuln_map[v.repo_id].append(v)

    # 저장소 ID -> full_name 맵
    repo_name_map = {r.id: r.full_name for r in repos}

    items = []
    for repo in repos:
        repo_vulns = repo_vuln_map.get(repo.id, [])
        score = _calc_security_score_f07(repo_vulns)
        open_count = sum(1 for v in repo_vulns if str(v.status) == "open")
        items.append(
            RepoScoreItem(
                repo_id=repo.id,
                repo_full_name=str(repo_name_map.get(repo.id, "unknown/repo")),
                security_score=score,
                open_vulns_count=open_count,
                total_vulns_count=len(repo_vulns),
            )
        )

    return ApiResponse(
        success=True,
        data=RepoScoreResponse(items=items, total=len(items)),
        error=None,
    )


@router.get("/team-scores", response_model=ApiResponse[TeamScoreResponse])
async def get_team_scores(
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[TeamScoreResponse]:
    """팀 내 저장소들의 보안 점수 집계 (F-07 설계서 3-2절).

    팀별로 평균 보안 점수, 저장소 수, 전체 미해결 취약점 수를 반환한다.
    """
    team_ids = await _get_user_team_ids(db=db, user_id=current_user.id)

    if not team_ids:
        return ApiResponse(
            success=True,
            data=TeamScoreResponse(items=[], total=0),
            error=None,
        )

    repos = await _get_repos_by_teams(db=db, team_ids=team_ids)

    if not repos:
        return ApiResponse(
            success=True,
            data=TeamScoreResponse(items=[], total=0),
            error=None,
        )

    repo_ids = [r.id for r in repos if isinstance(r.id, uuid.UUID)]
    vulns = await _get_vulns_by_repos(db=db, repo_ids=repo_ids)

    # 저장소별 취약점 분류
    repo_vuln_map: dict[uuid.UUID, list[Vulnerability]] = {r.id: [] for r in repos}
    for v in vulns:
        if v.repo_id in repo_vuln_map:
            repo_vuln_map[v.repo_id].append(v)

    # 팀별 집계
    team_data: dict[uuid.UUID, dict] = {}
    for repo in repos:
        tid = repo.team_id
        if not isinstance(tid, uuid.UUID):
            continue
        if tid not in team_data:
            team_data[tid] = {"scores": [], "open_vulns": 0, "repo_count": 0}

        repo_vulns = repo_vuln_map.get(repo.id, [])
        score = _calc_security_score_f07(repo_vulns)
        open_count = sum(1 for v in repo_vulns if str(v.status) == "open")

        team_data[tid]["scores"].append(score)
        team_data[tid]["open_vulns"] += open_count
        team_data[tid]["repo_count"] += 1

    items = []
    for tid, tdata in team_data.items():
        scores = tdata["scores"]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
        items.append(
            TeamScoreItem(
                team_id=tid,
                avg_score=avg_score,
                repo_count=tdata["repo_count"],
                total_open_vulns=tdata["open_vulns"],
            )
        )

    return ApiResponse(
        success=True,
        data=TeamScoreResponse(items=items, total=len(items)),
        error=None,
    )


@router.get("/severity-distribution", response_model=ApiResponse[SeverityDistributionResponse])
async def get_severity_distribution(
    current_user: CurrentUser,
    db: DbSession,
    repository_id: uuid.UUID | None = Query(default=None, description="특정 저장소 필터"),
) -> ApiResponse[SeverityDistributionResponse]:
    """심각도별 취약점 분포 조회 (F-07 설계서 3-3절).

    Args:
        repository_id: 특정 저장소로 필터링 (None이면 팀 전체)

    Returns:
        critical, high, medium, low, total 분포
    """
    team_ids = await _get_user_team_ids(db=db, user_id=current_user.id)
    repos = await _get_repos_by_teams(db=db, team_ids=team_ids)

    if not repos:
        return ApiResponse(
            success=True,
            data=SeverityDistributionResponse(
                critical=0, high=0, medium=0, low=0, total=0
            ),
            error=None,
        )

    repo_ids = [r.id for r in repos if isinstance(r.id, uuid.UUID)]

    # repository_id 필터 적용 (팀 소속 검증)
    if repository_id is not None:
        if repository_id not in repo_ids:
            return ApiResponse(
                success=True,
                data=SeverityDistributionResponse(
                    critical=0, high=0, medium=0, low=0, total=0
                ),
                error=None,
            )
        filter_ids = [repository_id]
    else:
        filter_ids = repo_ids

    vulns = await _get_vulns_by_repos(db=db, repo_ids=filter_ids)

    dist: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for v in vulns:
        sev = str(v.severity) if v.severity else "low"
        if sev in dist:
            dist[sev] += 1

    total = sum(dist.values())

    return ApiResponse(
        success=True,
        data=SeverityDistributionResponse(
            critical=dist["critical"],
            high=dist["high"],
            medium=dist["medium"],
            low=dist["low"],
            total=total,
        ),
        error=None,
    )
