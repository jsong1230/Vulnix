"""리포트 생성 서비스 — 데이터 수집, PDF/JSON 생성, 파일 저장"""

import os
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.report import ReportData
from src.services.report_renderer import get_report_renderer


class ReportService:
    """리포트 생성 및 관리 서비스.

    역할:
    1. 리포트 데이터 수집 (저장소, 취약점, 스캔 데이터)
    2. PDF/JSON 렌더링
    3. 파일 저장 (로컬)
    4. 이메일 발송 (EmailService 위임)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def collect_report_data(
        self,
        team_id: uuid.UUID,
        period_start: date,
        period_end: date,
    ) -> ReportData:
        """리포트에 필요한 데이터를 수집한다.

        Args:
            team_id: 팀 UUID
            period_start: 리포트 대상 기간 시작일
            period_end: 리포트 대상 기간 종료일

        Returns:
            ReportData 인스턴스
        """
        from src.models.repository import Repository
        from src.models.scan_job import ScanJob
        from src.models.team import Team, TeamMember
        from src.models.vulnerability import Vulnerability

        # 팀 이름 조회
        team_result = await self.db.execute(
            select(Team).where(Team.id == team_id)
        )
        team = team_result.scalar_one_or_none()
        team_name = team.name if team is not None else "Unknown Team"

        # 저장소 목록 조회
        repo_result = await self.db.execute(
            select(Repository).where(Repository.team_id == team_id)
        )
        repositories = list(repo_result.scalars().all())
        repo_ids = [r.id for r in repositories]

        # 취약점 조회 (전 기간)
        if repo_ids:
            vuln_result = await self.db.execute(
                select(Vulnerability).where(
                    Vulnerability.repo_id.in_(repo_ids)
                )
            )
            all_vulns = list(vuln_result.scalars().all())
        else:
            all_vulns = []

        # 스캔 이력 조회
        if repo_ids:
            scan_result = await self.db.execute(
                select(ScanJob).where(ScanJob.repo_id.in_(repo_ids))
            )
            all_scans = list(scan_result.scalars().all())
        else:
            all_scans = []

        # 취약점 통계 계산
        total_vulns = len(all_vulns)

        period_start_dt = datetime.combine(period_start, datetime.min.time()).replace(
            tzinfo=timezone.utc
        )
        period_end_dt = datetime.combine(period_end, datetime.max.time()).replace(
            tzinfo=timezone.utc
        )

        new_vulns = [
            v for v in all_vulns
            if v.detected_at is not None
            and period_start_dt <= v.detected_at <= period_end_dt
        ]

        resolved_vulns = [
            v for v in all_vulns
            if v.status in ("patched",)
            and v.resolved_at is not None
            and period_start_dt <= v.resolved_at <= period_end_dt
        ]

        # 심각도 분포
        severity_distribution = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for v in all_vulns:
            sev = v.severity if v.severity in severity_distribution else "low"
            severity_distribution[sev] += 1

        # 상태 분포
        status_distribution = {"open": 0, "patched": 0, "ignored": 0, "false_positive": 0}
        for v in all_vulns:
            st = v.status if v.status in status_distribution else "open"
            status_distribution[st] += 1

        # 해결률
        resolution_rate = (
            (len(resolved_vulns) / total_vulns * 100) if total_vulns > 0 else 0.0
        )

        # 취약점 유형 Top 10
        type_counter: dict[str, int] = {}
        for v in all_vulns:
            vtype = getattr(v, "vulnerability_type", "unknown") or "unknown"
            type_counter[vtype] = type_counter.get(vtype, 0) + 1
        vuln_type_top10 = sorted(
            [{"type": k, "count": cnt} for k, cnt in type_counter.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:10]

        # 보안 점수 (평균)
        scores = [r.security_score for r in repositories if getattr(r, "security_score", None) is not None]
        current_score = sum(scores) / len(scores) if scores else 0.0

        # 저장소 점수 랭킹
        repo_ranking = sorted(
            [
                {
                    "full_name": r.full_name,
                    "score": r.security_score or 0.0,
                    "open_vulns": sum(
                        1 for v in all_vulns
                        if v.repo_id == r.id and v.status == "open"
                    ),
                }
                for r in repositories
            ],
            key=lambda x: x["score"],
            reverse=True,
        )

        # 평균 대응 시간 (탐지→패치) 계산
        response_times = []
        for v in all_vulns:
            if (
                v.status == "patched"
                and v.detected_at is not None
                and v.resolved_at is not None
            ):
                delta = v.resolved_at - v.detected_at
                response_times.append(delta.total_seconds() / 3600)

        avg_response_time = (
            sum(response_times) / len(response_times) if response_times else 0.0
        )

        # 자동 패치 적용률 (patch_pr가 있는 취약점 / 전체)
        auto_patched = sum(
            1 for v in all_vulns if getattr(v, "patch_pr", None) is not None
        )
        auto_patch_rate = (auto_patched / total_vulns * 100) if total_vulns > 0 else 0.0

        # 스캔 이력 직렬화
        scan_job_list = [
            {
                "id": str(s.id),
                "repo_name": next(
                    (r.full_name for r in repositories if r.id == s.repo_id), "unknown"
                ),
                "status": s.status,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "findings_count": getattr(s, "findings_count", 0) or 0,
            }
            for s in all_scans
        ]

        # 패치 PR 직렬화 (간략)
        patch_pr_list: list[dict] = []

        # 미조치 Critical 취약점
        unresolved_critical = [
            {
                "id": str(v.id),
                "file_path": getattr(v, "file_path", "") or "",
                "type": getattr(v, "vulnerability_type", "") or "",
                "severity": v.severity,
                "detected_at": v.detected_at.isoformat() if v.detected_at else None,
            }
            for v in all_vulns
            if v.severity == "critical" and v.status == "open"
        ]

        # 저장소 직렬화
        repo_list = [
            {
                "id": str(r.id),
                "full_name": r.full_name,
                "platform": getattr(r, "platform", "github"),
                "security_score": r.security_score or 0.0,
            }
            for r in repositories
        ]

        return ReportData(
            team_name=team_name,
            period_start=period_start,
            period_end=period_end,
            repositories=repo_list,
            total_repo_count=len(repositories),
            total_vulnerabilities=total_vulns,
            new_vulnerabilities=len(new_vulns),
            resolved_vulnerabilities=len(resolved_vulns),
            severity_distribution=severity_distribution,
            status_distribution=status_distribution,
            resolution_rate=resolution_rate,
            vulnerability_type_top10=vuln_type_top10,
            current_security_score=current_score,
            previous_security_score=0.0,
            score_trend=[],
            avg_response_time_hours=avg_response_time,
            auto_patch_rate=auto_patch_rate,
            repo_score_ranking=repo_ranking,
            scan_jobs=scan_job_list,
            total_scans=len(all_scans),
            patch_prs=patch_pr_list,
            unresolved_critical=unresolved_critical,
        )

    async def generate_report(
        self,
        report_id: uuid.UUID,
        report_type: str,
        team_id: uuid.UUID,
        period_start: date,
        period_end: date,
        report_format: str = "pdf",
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
        from src.models.report_history import ReportHistory

        # 저장 디렉토리 생성
        storage_path = os.environ.get("REPORT_STORAGE_PATH", "/tmp/reports")
        os.makedirs(storage_path, exist_ok=True)

        ext = "pdf" if report_format == "pdf" else "json"
        file_path = os.path.join(storage_path, f"{report_id}.{ext}")

        data = await self.collect_report_data(team_id, period_start, period_end)
        renderer = get_report_renderer(report_type)

        if report_format == "pdf":
            renderer.render_pdf(data, file_path)
        else:
            renderer.render_json(data, file_path)

        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        # report_history 상태 업데이트
        history_result = await self.db.execute(
            select(ReportHistory).where(ReportHistory.id == report_id)
        )
        history = history_result.scalar_one_or_none()
        if history is not None:
            history.status = "completed"
            history.file_path = file_path
            history.file_size_bytes = file_size
            history.metadata = {
                "security_score": data.current_security_score,
                "total_vulnerabilities": data.total_vulnerabilities,
                "critical_count": data.severity_distribution.get("critical", 0),
            }
            await self.db.flush()
            await self.db.commit()

        return file_path
