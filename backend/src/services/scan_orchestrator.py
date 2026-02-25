"""스캔 오케스트레이터 — 스캔 작업 큐잉, 상태 추적, 실패 재시도"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import redis
from rq import Queue, Retry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models.scan_job import ScanJob

settings = get_settings()

# 최대 재시도 횟수
MAX_RETRY_COUNT = 3


@dataclass
class ScanJobMessage:
    """Redis 큐에 등록할 스캔 작업 메시지.

    이 구조체가 워커로 전달된다.
    """

    job_id: str
    repo_id: str
    trigger: str       # webhook / manual / schedule
    commit_sha: str | None
    branch: str | None
    pr_number: int | None
    scan_type: str
    changed_files: list[str] | None
    created_at: str    # ISO 8601 형식


class ScanOrchestrator:
    """스캔 작업의 생명주기를 관리하는 오케스트레이터.

    역할:
    - 스캔 작업을 Redis 큐에 등록
    - 작업 상태 추적 (queued -> running -> completed / failed)
    - 실패 시 재시도 (최대 3회)
    """

    def __init__(self, db: AsyncSession) -> None:
        """DB 세션을 주입받아 초기화한다."""
        self.db = db
        self._redis_conn = redis.from_url(settings.REDIS_URL)
        self._queue = Queue("scans", connection=self._redis_conn)

    async def enqueue_scan(
        self,
        repo_id: uuid.UUID,
        trigger: str,
        commit_sha: str | None = None,
        branch: str | None = None,
        pr_number: int | None = None,
        scan_type: str = "incremental",
        changed_files: list[str] | None = None,
    ) -> str:
        """새 스캔 작업을 생성하고 Redis 큐에 등록한다.

        Args:
            repo_id: 스캔할 저장소 ID
            trigger: 트리거 유형 (webhook / manual / schedule)
            commit_sha: 스캔할 커밋 SHA
            branch: 스캔할 브랜치명
            pr_number: PR 트리거 시 PR 번호
            scan_type: 스캔 유형 (incremental / initial / pr / full)
            changed_files: 변경된 파일 목록

        Returns:
            생성된 ScanJob의 ID (str)
        """
        # ScanJob 레코드 생성 (status=queued)
        scan_job = ScanJob(
            repo_id=repo_id,
            status="queued",
            trigger_type=trigger,
            commit_sha=commit_sha,
            branch=branch,
            pr_number=pr_number,
            scan_type=scan_type,
            changed_files=changed_files,
            retry_count=0,
        )
        self.db.add(scan_job)
        await self.db.flush()

        job_id = str(scan_job.id)

        # Redis 큐에 메시지 등록
        message = ScanJobMessage(
            job_id=job_id,
            repo_id=str(repo_id),
            trigger=trigger,
            commit_sha=commit_sha,
            branch=branch,
            pr_number=pr_number,
            scan_type=scan_type,
            changed_files=changed_files,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        self._queue.enqueue(
            "src.workers.scan_worker.run_scan",
            args=(message,),
            job_id=job_id,
            retry=Retry(max=3, interval=[10, 30, 60]),
            job_timeout="10m",
        )

        return job_id

    async def has_active_scan(self, repo_id: uuid.UUID) -> bool:
        """동일 저장소에 진행 중인 스캔이 있는지 확인한다.

        Args:
            repo_id: 확인할 저장소 ID

        Returns:
            queued 또는 running 상태의 스캔이 있으면 True
        """
        result = await self.db.execute(
            select(ScanJob).where(
                ScanJob.repo_id == repo_id,
                ScanJob.status.in_(["queued", "running"]),
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def cancel_active_scans_for_pr(
        self,
        repo_id: uuid.UUID,
        pr_number: int,
    ) -> int:
        """동일 PR에 대한 진행 중 스캔을 모두 취소한다.

        Args:
            repo_id: 저장소 ID
            pr_number: PR 번호

        Returns:
            취소된 스캔 수
        """
        result = await self.db.execute(
            select(ScanJob).where(
                ScanJob.repo_id == repo_id,
                ScanJob.pr_number == pr_number,
                ScanJob.status.in_(["queued", "running"]),
            )
        )
        active_jobs = result.scalars().all()

        for job in active_jobs:
            job.status = "cancelled"

        return len(active_jobs)

    async def get_job_status(self, job_id: str) -> str:
        """Redis 큐에서 작업 상태를 조회한다.

        Returns:
            queued / running / completed / failed
        """
        result = await self.db.execute(
            select(ScanJob).where(ScanJob.id == uuid.UUID(job_id))
        )
        job = result.scalar_one_or_none()
        if job is None:
            raise ValueError(f"ScanJob을 찾을 수 없습니다: {job_id}")
        return job.status

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """스캔 작업 상태를 DB에 업데이트한다.

        Args:
            job_id: 업데이트할 ScanJob ID
            status: 새 상태 (running / completed / failed / cancelled)
            error_message: 실패 시 에러 메시지
        """
        result = await self.db.execute(
            select(ScanJob).where(ScanJob.id == uuid.UUID(job_id))
        )
        scan_job = result.scalar_one_or_none()
        if scan_job is None:
            return

        scan_job.status = status
        now = datetime.now(timezone.utc)

        if status == "running":
            scan_job.started_at = now

        elif status == "completed":
            scan_job.completed_at = now
            if scan_job.started_at is not None:
                try:
                    # started_at이 timezone-aware이면 그대로, naive이면 UTC로 처리
                    started = scan_job.started_at
                    if started.tzinfo is None:
                        started = started.replace(tzinfo=timezone.utc)
                    delta = now - started
                    scan_job.duration_seconds = int(delta.total_seconds())
                except (TypeError, AttributeError):
                    scan_job.duration_seconds = 0

        elif status == "failed":
            scan_job.error_message = error_message
            scan_job.retry_count += 1

        await self.db.commit()
