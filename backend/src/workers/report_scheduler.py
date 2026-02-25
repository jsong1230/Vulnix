"""RQ Scheduler 기반 리포트 자동 생성.

report_config 테이블의 next_generation_at을 주기적으로 확인하여
리포트 생성 작업을 큐에 등록한다.
"""

import uuid
from datetime import datetime, timedelta, timezone


def calculate_next_generation(schedule: str, current: datetime) -> datetime:
    """다음 생성 시각을 계산한다.

    Args:
        schedule: 스케줄 주기 (weekly / monthly / quarterly)
        current: 기준 시각 (timezone-aware)

    Returns:
        다음 생성 예정 시각 (UTC)

    Raises:
        ValueError: 지원하지 않는 주기인 경우
    """
    if schedule == "weekly":
        return current + timedelta(days=7)
    elif schedule == "monthly":
        # 다음달 1일 00:00 UTC
        year = current.year
        month = current.month + 1
        if month > 12:
            month = 1
            year += 1
        return datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
    elif schedule == "quarterly":
        # 현재 분기의 다음 분기 시작월 (1, 4, 7, 10월) 1일 00:00 UTC
        # 현재 분기 시작월 계산: 1~3월→1, 4~6월→4, 7~9월→7, 10~12월→10
        current_quarter_start = ((current.month - 1) // 3) * 3 + 1
        next_quarter_start_month = current_quarter_start + 3
        year = current.year
        if next_quarter_start_month > 12:
            next_quarter_start_month -= 12
            year += 1
        return datetime(year, next_quarter_start_month, 1, 0, 0, 0, tzinfo=timezone.utc)
    else:
        raise ValueError(f"지원하지 않는 주기: {schedule}")


async def check_and_enqueue_reports(db: object) -> list[uuid.UUID]:
    """현재 시각 기준으로 생성이 필요한 리포트를 큐에 등록한다.

    1. report_config에서 is_active=True AND next_generation_at <= now 조회
    2. 각 설정에 대해 리포트 생성 작업 큐 등록
    3. next_generation_at을 다음 주기로 업데이트

    Args:
        db: AsyncSession 인스턴스

    Returns:
        큐에 등록된 report_history ID 목록
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.models.report_config import ReportConfig
    from src.models.report_history import ReportHistory

    now = datetime.now(timezone.utc)
    queued_ids: list[uuid.UUID] = []

    # is_active=True이고 next_generation_at이 현재 시각 이전인 설정 조회
    result = await db.execute(
        select(ReportConfig).where(
            ReportConfig.is_active == True,  # noqa: E712
            ReportConfig.next_generation_at <= now,
            ReportConfig.next_generation_at.isnot(None),
        )
    )
    configs = list(result.scalars().all())

    for config in configs:
        # report_history 레코드 생성
        history = ReportHistory(
            id=uuid.uuid4(),
            config_id=config.id,
            team_id=config.team_id,
            report_type=config.report_type,
            format="pdf",
            file_path=None,
            period_start=now.date(),
            period_end=now.date(),
            status="generating",
        )
        db.add(history)
        await db.flush()

        queued_ids.append(history.id)

        # next_generation_at 업데이트
        config.next_generation_at = calculate_next_generation(config.schedule, now)
        config.last_generated_at = now

    await db.commit()
    return queued_ids
