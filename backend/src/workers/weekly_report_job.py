"""주간 보안 리포트 워커 — 설정된 팀에 주간 리포트를 발송한다.

실행 방법:
    python -m src.workers.weekly_report_job

Railway cron 또는 RQ Scheduler로 매주 실행:
    rq-scheduler ... --url $REDIS_URL
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.models.notification import NotificationConfig
from src.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _get_async_session(db_url: str):
    """주간 리포트 워커 전용 비동기 DB 세션 컨텍스트 매니저."""
    engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
            await engine.dispose()


async def _send_weekly_reports_async(db_url: str) -> dict:
    """비동기 주간 리포트 발송 파이프라인.

    weekly_report_enabled=True인 설정을 가진 팀 전체에 주간 리포트를 발송한다.

    Args:
        db_url: 비동기 DB 연결 URL

    Returns:
        발송 결과 요약 딕셔너리
    """
    service = NotificationService()
    sent_count = 0
    failed_count = 0

    async with _get_async_session(db_url) as db:
        # weekly_report_enabled 팀 목록 조회 (팀 중복 제거)
        result = await db.execute(
            select(NotificationConfig.team_id).where(
                NotificationConfig.is_active.is_(True),
                NotificationConfig.weekly_report_enabled.is_(True),
            ).distinct()
        )
        team_ids = list(result.scalars().all())

        logger.info(f"[WeeklyReportJob] 대상 팀: {len(team_ids)}개")

        for team_id in team_ids:
            try:
                await service.send_weekly_report(db=db, team_id=team_id)
                sent_count += 1
                logger.info(f"[WeeklyReportJob] 팀 {team_id} 리포트 발송 완료")
            except Exception as e:
                failed_count += 1
                logger.error(f"[WeeklyReportJob] 팀 {team_id} 리포트 발송 실패: {e}")

    return {
        "total_teams": len(team_ids) if "team_ids" in dir() else 0,
        "sent": sent_count,
        "failed": failed_count,
    }


def send_weekly_reports(db_url: str) -> dict:
    """주간 리포트를 모든 대상 팀에 발송한다 (동기 래퍼).

    RQ Job 또는 cron 트리거로 실행된다.

    Args:
        db_url: DB 연결 URL (postgresql+asyncpg://...)

    Returns:
        발송 결과 요약 딕셔너리
    """
    logger.info("[WeeklyReportJob] 주간 리포트 발송 시작")
    try:
        result = asyncio.run(_send_weekly_reports_async(db_url))
        logger.info(f"[WeeklyReportJob] 완료: {result}")
        return result
    except Exception as e:
        logger.error(f"[WeeklyReportJob] 발송 실패: {e}")
        raise


class WeeklyReportJob:
    """주간 리포트 RQ 호환 워커 클래스.

    RQ에서 직접 클래스 메서드를 호출하거나,
    Railway cron에서 run() 메서드를 실행한다.
    """

    def __init__(self, db_url: str) -> None:
        self.db_url = db_url

    def run(self) -> dict:
        """주간 리포트를 발송한다."""
        return send_weekly_reports(self.db_url)

    @staticmethod
    def enqueue(db_url: str) -> dict:
        """RQ 없이 직접 실행하는 정적 메서드."""
        return send_weekly_reports(db_url)


if __name__ == "__main__":
    import os

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/vulnix",
    )
    result = send_weekly_reports(db_url)
    logger.info(f"[WeeklyReportJob] 결과: {result}")
