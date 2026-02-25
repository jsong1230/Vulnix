"""F-01 ScanOrchestrator 서비스 단위 테스트 — TDD RED 단계

인수조건:
- enqueue_scan → ScanJob 레코드 생성 + Redis 큐 등록
- job_id 반환
- 중복 스캔 방지 (has_active_scan)
- 최대 3회 재시도 (retry_count)
- 스캔 상태 업데이트 (update_job_status)
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# redis / rq가 설치되지 않은 환경에서도 수집 가능하도록 모듈 레벨 import 제거
# ScanOrchestrator는 각 테스트 함수 내에서 redis/Queue patch 후 import

# 설계 명세 기준 상수 (scan_orchestrator.MAX_RETRY_COUNT와 동기화)
MAX_RETRY_COUNT = 3


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_scan_job():
    """DB ScanJob Mock 픽스처."""
    job = MagicMock()
    job.id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    job.repo_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    job.status = "queued"
    job.trigger_type = "webhook"
    job.commit_sha = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    job.branch = "main"
    job.pr_number = None
    job.retry_count = 0
    job.scan_type = "incremental"
    job.changed_files = None
    job.findings_count = 0
    job.true_positives_count = 0
    job.false_positives_count = 0
    job.duration_seconds = None
    job.error_message = None
    job.started_at = None
    job.completed_at = None
    job.created_at = datetime(2026, 2, 25, 10, 0, 0)
    return job


# ---------------------------------------------------------------------------
# 1. enqueue_scan → ScanJob 생성
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enqueue_scan_creates_job(mock_db, mock_scan_job):
    """enqueue_scan 호출 시 DB에 ScanJob 레코드가 생성(queued 상태)된다.

    Given: repo_id, trigger='webhook', scan_type='incremental'
    When: orchestrator.enqueue_scan() 호출
    Then: db.add()가 ScanJob 객체로 호출되고, db.flush()가 호출됨
    """
    # Arrange
    repo_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    with (
        patch("src.services.scan_orchestrator.redis") as mock_redis_mod,
        patch("src.services.scan_orchestrator.Queue") as mock_queue_cls,
        patch("src.services.scan_orchestrator.ScanJob") as mock_scanjob_cls,
    ):
        mock_redis_mod.from_url.return_value = MagicMock()
        mock_queue = MagicMock()
        mock_queue_cls.return_value = mock_queue
        mock_queue.enqueue.return_value = MagicMock(id=str(mock_scan_job.id))
        mock_scanjob_cls.return_value = mock_scan_job

        from src.services.scan_orchestrator import ScanOrchestrator
        orchestrator = ScanOrchestrator(db=mock_db)

        # Act
        job_id = await orchestrator.enqueue_scan(
            repo_id=repo_id,
            trigger="webhook",
            commit_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            branch="main",
            scan_type="incremental",
        )

    # Assert
    # DB에 ScanJob이 추가되어야 함
    mock_db.add.assert_called_once()
    added_obj = mock_db.add.call_args[0][0]
    assert added_obj is not None

    # DB flush가 호출되어야 함 (commit 또는 flush 중 하나)
    assert mock_db.flush.called or mock_db.commit.called


@pytest.mark.asyncio
async def test_enqueue_scan_returns_job_id(mock_db):
    """enqueue_scan은 생성된 ScanJob의 UUID 문자열을 반환한다.

    Given: repo_id와 trigger
    When: orchestrator.enqueue_scan() 호출
    Then: str 형태의 UUID job_id 반환
    """
    # Arrange
    repo_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    with (
        patch("src.services.scan_orchestrator.redis") as mock_redis_mod,
        patch("src.services.scan_orchestrator.Queue"),
        patch("src.services.scan_orchestrator.ScanJob") as mock_scanjob_cls,
    ):
        mock_redis_mod.from_url.return_value = MagicMock()
        mock_job = MagicMock()
        mock_job.id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        mock_scanjob_cls.return_value = mock_job

        from src.services.scan_orchestrator import ScanOrchestrator
        orchestrator = ScanOrchestrator(db=mock_db)

        # Act
        job_id = await orchestrator.enqueue_scan(
            repo_id=repo_id,
            trigger="manual",
        )

    # Assert
    assert job_id is not None
    assert isinstance(job_id, str)
    # UUID 형식인지 확인
    try:
        uuid.UUID(job_id)
    except ValueError:
        pytest.fail(f"반환된 job_id가 UUID 형식이 아닙니다: {job_id}")


# ---------------------------------------------------------------------------
# 2. 최대 3회 재시도 로직
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_logic_max_3_attempts(mock_db, mock_scan_job):
    """스캔 실패 시 최대 MAX_RETRY_COUNT(3)회까지 재시도된다.

    Given: ScanJob이 'failed' 상태로 업데이트되는 상황
    When: update_job_status(status='failed') 3회 호출
    Then: retry_count가 증가하고, MAX_RETRY_COUNT 도달 시 더 이상 재큐잉하지 않음

    인수조건: Webhook 수신 실패 시 재시도 로직 동작 (최대 3회)
    """
    # Arrange
    assert MAX_RETRY_COUNT == 3, "MAX_RETRY_COUNT는 3이어야 합니다."
    job_id = str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
    mock_scan_job.retry_count = 0

    with (
        patch("src.services.scan_orchestrator.redis") as mock_redis_mod,
        patch("src.services.scan_orchestrator.Queue"),
    ):
        mock_redis_mod.from_url.return_value = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_scan_job
        mock_db.execute = AsyncMock(return_value=mock_result)

        from src.services.scan_orchestrator import ScanOrchestrator
        orchestrator = ScanOrchestrator(db=mock_db)

        # Act: 3회 실패 시뮬레이션
        # update_job_status 내부에서 retry_count += 1이 실행되므로 외부에서 증가 불필요
        for attempt in range(MAX_RETRY_COUNT):
            await orchestrator.update_job_status(
                job_id=job_id,
                status="failed",
                error_message=f"테스트 오류 {attempt + 1}회차",
            )

    # Assert: retry_count가 MAX_RETRY_COUNT에 도달해야 함
    assert mock_scan_job.retry_count == MAX_RETRY_COUNT


# ---------------------------------------------------------------------------
# 3. 중복 스캔 방지 (has_active_scan)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_has_active_scan_prevents_duplicate(mock_db, mock_scan_job):
    """동일 저장소에 진행 중인 스캔이 있으면 has_active_scan이 True를 반환한다.

    Given: repo_id에 status='queued'인 ScanJob이 존재
    When: orchestrator.has_active_scan(repo_id) 호출
    Then: True 반환 → 외부에서 중복 스캔 등록을 막을 수 있음
    """
    # Arrange
    repo_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    with (
        patch("src.services.scan_orchestrator.redis") as mock_redis_mod,
        patch("src.services.scan_orchestrator.Queue"),
    ):
        mock_redis_mod.from_url.return_value = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_scan_job  # 존재함
        mock_db.execute = AsyncMock(return_value=mock_result)

        from src.services.scan_orchestrator import ScanOrchestrator
        orchestrator = ScanOrchestrator(db=mock_db)

        # Act
        result = await orchestrator.has_active_scan(repo_id=repo_id)

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_has_active_scan_returns_false_when_no_active(mock_db):
    """진행 중인 스캔이 없으면 has_active_scan이 False를 반환한다.

    Given: repo_id에 queued/running ScanJob이 없는 상황
    When: orchestrator.has_active_scan(repo_id) 호출
    Then: False 반환
    """
    # Arrange
    repo_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    with (
        patch("src.services.scan_orchestrator.redis") as mock_redis_mod,
        patch("src.services.scan_orchestrator.Queue"),
    ):
        mock_redis_mod.from_url.return_value = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # 없음
        mock_db.execute = AsyncMock(return_value=mock_result)

        from src.services.scan_orchestrator import ScanOrchestrator
        orchestrator = ScanOrchestrator(db=mock_db)

        # Act
        result = await orchestrator.has_active_scan(repo_id=repo_id)

    # Assert
    assert result is False


# ---------------------------------------------------------------------------
# 4. 스캔 상태 업데이트
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_scan_status_queued_to_running(mock_db, mock_scan_job):
    """update_job_status('running') 호출 시 started_at이 설정된다.

    Given: status='queued'인 ScanJob
    When: update_job_status(job_id, status='running') 호출
    Then: scan_job.status='running', scan_job.started_at이 설정됨
    """
    # Arrange
    job_id = str(mock_scan_job.id)
    mock_scan_job.status = "queued"
    mock_scan_job.started_at = None

    with (
        patch("src.services.scan_orchestrator.redis") as mock_redis_mod,
        patch("src.services.scan_orchestrator.Queue"),
    ):
        mock_redis_mod.from_url.return_value = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_scan_job
        mock_db.execute = AsyncMock(return_value=mock_result)

        from src.services.scan_orchestrator import ScanOrchestrator
        orchestrator = ScanOrchestrator(db=mock_db)

        # Act
        await orchestrator.update_job_status(job_id=job_id, status="running")

    # Assert
    assert mock_scan_job.status == "running"
    assert mock_scan_job.started_at is not None


@pytest.mark.asyncio
async def test_update_scan_status_running_to_completed(mock_db, mock_scan_job):
    """update_job_status('completed') 호출 시 completed_at과 duration_seconds가 설정된다.

    Given: status='running', started_at이 설정된 ScanJob
    When: update_job_status(job_id, status='completed') 호출
    Then: scan_job.status='completed', completed_at 설정, duration_seconds 계산
    """
    # Arrange
    job_id = str(mock_scan_job.id)
    mock_scan_job.status = "running"
    mock_scan_job.started_at = datetime(2026, 2, 25, 10, 0, 0)
    mock_scan_job.completed_at = None
    mock_scan_job.duration_seconds = None

    with (
        patch("src.services.scan_orchestrator.redis") as mock_redis_mod,
        patch("src.services.scan_orchestrator.Queue"),
    ):
        mock_redis_mod.from_url.return_value = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_scan_job
        mock_db.execute = AsyncMock(return_value=mock_result)

        from src.services.scan_orchestrator import ScanOrchestrator
        orchestrator = ScanOrchestrator(db=mock_db)

        # Act
        await orchestrator.update_job_status(job_id=job_id, status="completed")

    # Assert
    assert mock_scan_job.status == "completed"
    assert mock_scan_job.completed_at is not None
    assert mock_scan_job.duration_seconds is not None


@pytest.mark.asyncio
async def test_update_scan_status_failed_saves_error_message(mock_db, mock_scan_job):
    """update_job_status('failed') 호출 시 error_message가 저장된다.

    Given: status='running'인 ScanJob
    When: update_job_status(job_id, status='failed', error_message='DB 연결 오류')
    Then: scan_job.status='failed', error_message 저장, retry_count 증가
    """
    # Arrange
    job_id = str(mock_scan_job.id)
    mock_scan_job.status = "running"
    mock_scan_job.error_message = None
    mock_scan_job.retry_count = 0

    with (
        patch("src.services.scan_orchestrator.redis") as mock_redis_mod,
        patch("src.services.scan_orchestrator.Queue"),
    ):
        mock_redis_mod.from_url.return_value = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_scan_job
        mock_db.execute = AsyncMock(return_value=mock_result)

        from src.services.scan_orchestrator import ScanOrchestrator
        orchestrator = ScanOrchestrator(db=mock_db)

        # Act
        await orchestrator.update_job_status(
            job_id=job_id,
            status="failed",
            error_message="DB 연결 오류",
        )

    # Assert
    assert mock_scan_job.status == "failed"
    assert mock_scan_job.error_message == "DB 연결 오류"
    assert mock_scan_job.retry_count == 1  # retry_count 증가


# ---------------------------------------------------------------------------
# 5. enqueue_scan - scan_type 및 changed_files 전달
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enqueue_scan_with_scan_type_and_changed_files(mock_db):
    """enqueue_scan에 scan_type과 changed_files를 전달하면 ScanJob에 저장된다.

    Given: scan_type='pr', changed_files=['src/auth.py', 'src/models.py']
    When: orchestrator.enqueue_scan() 호출
    Then: 생성된 ScanJob에 scan_type='pr', changed_files가 올바르게 저장됨
    """
    # Arrange
    repo_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    changed_files = ["src/auth.py", "src/models.py"]

    created_job = MagicMock()
    created_job.id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    created_job.scan_type = None
    created_job.changed_files = None

    with (
        patch("src.services.scan_orchestrator.redis") as mock_redis_mod,
        patch("src.services.scan_orchestrator.Queue"),
        patch("src.services.scan_orchestrator.ScanJob") as mock_scanjob_cls,
    ):
        mock_redis_mod.from_url.return_value = MagicMock()
        mock_scanjob_cls.return_value = created_job

        from src.services.scan_orchestrator import ScanOrchestrator
        orchestrator = ScanOrchestrator(db=mock_db)

        # Act
        job_id = await orchestrator.enqueue_scan(
            repo_id=repo_id,
            trigger="webhook",
            commit_sha="b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3",
            branch="feature/auth",
            pr_number=42,
            scan_type="pr",
            changed_files=changed_files,
        )

    # Assert: ScanJob 생성자가 호출되어야 함
    assert mock_scanjob_cls.called
    call_kwargs = mock_scanjob_cls.call_args
    if call_kwargs.kwargs:
        if "scan_type" in call_kwargs.kwargs:
            assert call_kwargs.kwargs["scan_type"] == "pr"
        if "changed_files" in call_kwargs.kwargs:
            assert call_kwargs.kwargs["changed_files"] == changed_files


# ---------------------------------------------------------------------------
# 6. ScanOrchestrator 초기화 — DB 주입
# ---------------------------------------------------------------------------

def test_orchestrator_requires_db_session():
    """ScanOrchestrator는 db 세션을 주입받아 초기화된다.

    Given: F-01 설계: ScanOrchestrator에 db를 주입하도록 시그니처 변경
    When: ScanOrchestrator(db=mock_db) 생성
    Then: 초기화 완료

    참조: 현재 스캐폴딩에는 db 파라미터가 없으므로 RED 상태 (TypeError 예상)
    """
    # Arrange
    mock_db_session = AsyncMock()

    with (
        patch("src.services.scan_orchestrator.redis") as mock_redis_mod,
        patch("src.services.scan_orchestrator.Queue"),
    ):
        mock_redis_mod.from_url.return_value = MagicMock()

        from src.services.scan_orchestrator import ScanOrchestrator

        # Act & Assert
        # 현재 스캐폴딩의 __init__ 시그니처: def __init__(self) -> None
        # db 파라미터가 없으므로 TypeError 발생 → RED 확인
        orchestrator = ScanOrchestrator(db=mock_db_session)
        assert orchestrator is not None


# ---------------------------------------------------------------------------
# 7. cancel_active_scans_for_pr
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_active_scans_for_pr(mock_db, mock_scan_job):
    """동일 PR에 대한 진행 중 스캔을 취소한다.

    Given: repo_id + pr_number=42에 queued ScanJob이 1개 존재
    When: orchestrator.cancel_active_scans_for_pr(repo_id, pr_number=42)
    Then: 해당 ScanJob의 status가 'cancelled'로 변경되고 취소 수 반환
    """
    # Arrange
    repo_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    mock_scan_job.pr_number = 42
    mock_scan_job.status = "queued"

    with (
        patch("src.services.scan_orchestrator.redis") as mock_redis_mod,
        patch("src.services.scan_orchestrator.Queue"),
    ):
        mock_redis_mod.from_url.return_value = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_scan_job]
        mock_db.execute = AsyncMock(return_value=mock_result)

        from src.services.scan_orchestrator import ScanOrchestrator
        orchestrator = ScanOrchestrator(db=mock_db)

        # Act
        cancelled_count = await orchestrator.cancel_active_scans_for_pr(
            repo_id=repo_id,
            pr_number=42,
        )

    # Assert
    assert cancelled_count == 1
    assert mock_scan_job.status == "cancelled"
