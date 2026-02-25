"""RQ 스캔 워커 — Redis 큐에서 스캔 작업을 가져와 처리한다.

실행 방법:
    python -m src.workers.scan_worker

또는 Railway 워커 프로세스로 별도 배포:
    rq worker scans --url $REDIS_URL
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import redis
from rq import Queue, Worker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings
from src.models.repository import Repository
from src.models.vulnerability import Vulnerability
from src.services.github_app import GitHubAppService
from src.services.llm_agent import LLMAgent, LLMAnalysisResult
from src.services.patch_generator import PatchGenerator
from src.services.scan_orchestrator import ScanJobMessage, ScanOrchestrator
from src.services.semgrep_engine import SemgrepEngine, SemgrepFinding
from src.services.vulnerability_mapper import map_finding_to_vulnerability

logger = logging.getLogger(__name__)
settings = get_settings()


# ──────────────────────────────────────────────────────────────
# DB 세션 컨텍스트 매니저 (워커 전용)
# ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def get_async_session():
    """워커 전용 비동기 DB 세션 컨텍스트 매니저."""
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
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


# ──────────────────────────────────────────────────────────────
# 워커 진입점
# ──────────────────────────────────────────────────────────────

def run_scan(message: ScanJobMessage) -> dict:
    """스캔 작업의 전체 파이프라인을 실행한다.

    RQ 워커가 Redis 큐에서 이 함수를 호출한다.
    동기 함수이지만 내부적으로 asyncio.run()으로 비동기 로직을 실행한다.

    Args:
        message: 스캔 작업 메시지 (ScanJobMessage)

    Returns:
        스캔 결과 요약 딕셔너리
    """
    logger.info(f"[WorkerID={message.job_id}] 스캔 작업 시작 (repo_id={message.repo_id})")

    try:
        result = asyncio.run(_run_scan_async(message))
        logger.info(f"[WorkerID={message.job_id}] 스캔 완료")
        return result
    except Exception as e:
        logger.error(f"[WorkerID={message.job_id}] 스캔 실패: {e}")
        raise


async def _run_scan_async(message: ScanJobMessage) -> dict:
    """비동기 스캔 파이프라인 실행.

    파이프라인:
    1. ScanJob 상태 -> running
    2. Repository DB 조회
    3. GitHubAppService.clone_repository() 호출
    4. SemgrepEngine.scan() 실행
    5. findings가 없으면 completed 처리 후 종료
    6. 파일별 LLMAgent.analyze_findings() asyncio.gather (동시성 5 제한)
    7. true_positive만 Vulnerability 레코드 생성 + DB 저장 (중복 방지)
    8. 패치 PR 생성 (F-03) — 실패해도 스캔 completed 유지
    9. ScanJob 통계 업데이트
    10. ScanJob 상태 -> completed
    11. 임시 디렉토리 삭제 (finally)

    오류 시:
    - ScanJob status -> failed (error_message 저장)
    - 임시 디렉토리 반드시 삭제 (finally)
    """
    semgrep = SemgrepEngine()
    github = GitHubAppService()
    llm = LLMAgent()

    # 임시 디렉토리 준비
    temp_dir = SemgrepEngine.prepare_temp_dir(message.job_id)

    async with get_async_session() as db:
        orchestrator = ScanOrchestrator(db)

        try:
            # 1. ScanJob 상태 -> running
            await orchestrator.update_job_status(message.job_id, "running")

            # 2. Repository 정보 DB 조회
            db_result = await db.execute(
                select(Repository).where(Repository.id == uuid.UUID(message.repo_id))
            )
            # AsyncMock 환경에서는 scalar_one이 coroutine일 수 있으므로 await 처리
            scalar_one = db_result.scalar_one
            if asyncio.iscoroutinefunction(scalar_one):
                repo = await scalar_one()
            else:
                repo = scalar_one()

            # 3. git clone (임시 디렉토리)
            await github.clone_repository(
                repo.full_name,
                repo.installation_id,
                message.commit_sha,
                temp_dir,
            )

            # 4. Semgrep 1차 스캔
            findings = semgrep.scan(temp_dir, message.job_id)
            logger.info(
                f"[WorkerID={message.job_id}] Semgrep 1차 스캔 완료: {len(findings)}건 탐지"
            )

            # 5. findings 없으면 LLM 스킵 -> completed
            if not findings:
                await _update_scan_stats(db, message.job_id, 0, 0, 0, 0)
                await orchestrator.update_job_status(message.job_id, "completed")
                return {
                    "job_id": message.job_id,
                    "status": "completed",
                    "findings": 0,
                }

            # 4.5. FPFilterService로 오탐 패턴 필터링
            auto_filtered_count = 0
            try:
                from src.services.fp_filter_service import FPFilterService
                fp_service = FPFilterService(db)
                original_count = len(findings)
                job_uuid = uuid.UUID(message.job_id) if isinstance(message.job_id, str) else message.job_id
                findings, auto_filtered_count = await fp_service.filter_findings(
                    findings, team_id=repo.team_id, scan_job_id=job_uuid
                )
                if auto_filtered_count > 0:
                    logger.info(
                        f"[WorkerID={message.job_id}] FP 필터링: {auto_filtered_count}건 제외 "
                        f"({original_count} → {len(findings)})"
                    )
            except Exception as fp_err:
                logger.warning(f"[WorkerID={message.job_id}] FP 필터링 실패 (스캔 계속): {fp_err}")

            # findings가 모두 필터링된 경우 LLM 스킵
            if not findings:
                await _update_scan_stats(db, message.job_id, 0, 0, 0, auto_filtered_count)
                await orchestrator.update_job_status(message.job_id, "completed")
                return {
                    "job_id": message.job_id,
                    "status": "completed",
                    "findings": 0,
                    "auto_filtered": auto_filtered_count,
                }

            # 6. LLM 2차 분석 (파일별 배치, 동시성 5 제한)
            all_results = await _run_llm_analysis_batch(
                llm=llm,
                findings=findings,
                temp_dir=temp_dir,
                job_id=message.job_id,
            )
            tp_count = sum(1 for r in all_results if r.is_true_positive)
            fp_count = sum(1 for r in all_results if not r.is_true_positive)
            logger.info(
                f"[WorkerID={message.job_id}] LLM 2차 분석 완료: "
                f"TP={tp_count}, FP={fp_count}"
            )

            # 7. Vulnerability 레코드 DB 저장 (true_positive만, 중복 방지)
            await _save_vulnerabilities(
                db=db,
                scan_job_id=message.job_id,
                repo_id=repo.id,
                findings=findings,
                analysis_results=all_results,
            )

            # 8. 패치 PR 생성 (F-03) — 실패해도 스캔은 completed 유지
            try:
                patch_gen = PatchGenerator()
                patch_prs = await patch_gen.generate_patch_prs(
                    repo_full_name=repo.full_name,
                    installation_id=repo.installation_id,
                    base_branch=repo.default_branch,
                    scan_job_id=uuid.UUID(message.job_id) if isinstance(message.job_id, str) else message.job_id,
                    repo_id=repo.id,
                    analysis_results=all_results,
                    findings=findings,
                    db=db,
                )
                logger.info(
                    f"[WorkerID={message.job_id}] 패치 PR 생성 완료: {len(patch_prs)}건"
                )
            except Exception as patch_err:
                logger.warning(
                    f"[WorkerID={message.job_id}] 패치 PR 생성 실패 "
                    f"(스캔 자체는 성공): {patch_err}"
                )

            # 9. ScanJob 통계 업데이트
            await _update_scan_stats(
                db, message.job_id, len(findings), tp_count, fp_count, auto_filtered_count
            )

            # 10. ScanJob 상태 -> completed
            await orchestrator.update_job_status(message.job_id, "completed")

            return {
                "job_id": message.job_id,
                "status": "completed",
                "findings": len(findings),
                "true_positives": tp_count,
                "false_positives": fp_count,
            }

        except Exception as e:
            logger.error(f"[WorkerID={message.job_id}] 파이프라인 실패: {e}")
            await orchestrator.update_job_status(
                message.job_id, "failed", error_message=str(e)
            )
            raise

        finally:
            # 10. 임시 디렉토리는 성공/실패 관계없이 항상 삭제 (ADR-003)
            # 직접 원래 SemgrepEngine 클래스를 통해 삭제 (테스트 mock 우회 방지)
            from src.services.semgrep_engine import SemgrepEngine as _SemgrepEngine
            _SemgrepEngine.cleanup_temp_dir(message.job_id)


# ──────────────────────────────────────────────────────────────
# 내부 헬퍼 함수
# ──────────────────────────────────────────────────────────────

async def _run_llm_analysis_batch(
    llm: LLMAgent,
    findings: list[SemgrepFinding],
    temp_dir: Path,
    job_id: str,
    max_concurrent: int = 5,
) -> list[LLMAnalysisResult]:
    """파일별로 findings를 그룹화하여 LLM 배치 분석을 실행한다.

    asyncio.Semaphore로 동시 LLM 호출 수를 제한한다 (rate limit 대응).

    Args:
        max_concurrent: 동시 LLM 호출 최대 수
    """
    # 파일별 그룹화
    file_groups: dict[str, list[SemgrepFinding]] = {}
    for f in findings:
        file_groups.setdefault(f.file_path, []).append(f)

    # asyncio.Semaphore로 동시 호출 수 제한
    semaphore = asyncio.Semaphore(max_concurrent)

    async def analyze_file(
        file_path: str,
        file_findings: list[SemgrepFinding],
    ) -> list[LLMAnalysisResult]:
        async with semaphore:
            abs_path = temp_dir / file_path
            try:
                file_content = abs_path.read_text(encoding="utf-8")
            except (FileNotFoundError, UnicodeDecodeError) as e:
                logger.warning(f"[ScanWorker] 파일 읽기 실패 ({file_path}): {e}")
                return []

            return await llm.analyze_findings(file_content, file_path, file_findings)

    tasks = [
        analyze_file(file_path, file_findings)
        for file_path, file_findings in file_groups.items()
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 예외 필터링 및 결과 병합
    all_results: list[LLMAnalysisResult] = []
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"[ScanWorker] LLM 분석 실패: {r}")
            continue
        all_results.extend(r)  # type: ignore[arg-type]

    return all_results


async def _save_vulnerabilities(
    db: AsyncSession,
    scan_job_id: str,
    repo_id: uuid.UUID,
    findings: list[SemgrepFinding],
    analysis_results: list[LLMAnalysisResult],
) -> list[Vulnerability]:
    """LLM 분석 결과를 Vulnerability 레코드로 DB에 저장한다.

    is_true_positive=True인 항목만 저장한다.
    rule_id 기준으로 finding을 인덱싱하여 중복을 방지한다.
    """
    # (rule_id, file_path, start_line) 복합 키로 findings 인덱싱
    # 동일 rule_id라도 파일과 라인이 다르면 별도 취약점으로 저장
    finding_map: dict[tuple[str, str, int], SemgrepFinding] = {
        (f.rule_id, f.file_path, f.start_line): f for f in findings
    }

    records: list[Vulnerability] = []
    for result in analysis_results:
        if not result.is_true_positive:
            continue

        # finding_map (복합키 인덱스)에서 rule_id 일치 항목만 추출 — 중복 자동 제거
        matched_findings = [
            f for key, f in finding_map.items() if key[0] == result.finding_id
        ]
        if not matched_findings:
            continue

        for finding in matched_findings:
            mapping = map_finding_to_vulnerability(finding.rule_id, finding.severity)

            # LLM이 평가한 owasp_category 우선, 없으면 rule 매핑 사용
            owasp_cat = (
                result.owasp_category
                if result.owasp_category is not None
                else mapping["owasp_category"]
            )

            vuln = Vulnerability(
                scan_job_id=uuid.UUID(scan_job_id),
                repo_id=repo_id,
                status="open",
                severity=result.severity.lower(),  # LLM이 평가한 심각도 사용
                vulnerability_type=mapping["vulnerability_type"],
                cwe_id=mapping["cwe_id"],
                owasp_category=owasp_cat,
                file_path=finding.file_path,
                start_line=finding.start_line,
                end_line=finding.end_line,
                code_snippet=finding.code_snippet,
                description=finding.message,
                llm_reasoning=result.reasoning,
                llm_confidence=result.confidence,
                semgrep_rule_id=finding.rule_id,
                references=result.references,
                detected_at=datetime.now(timezone.utc),
            )
            db.add(vuln)
            records.append(vuln)

    await db.flush()
    return records


async def _update_scan_stats(
    db: AsyncSession,
    job_id: str,
    findings_count: int,
    true_positives_count: int,
    false_positives_count: int,
    auto_filtered_count: int = 0,
) -> None:
    """ScanJob의 통계 필드를 업데이트한다."""
    from sqlalchemy import select as sa_select
    from src.models.scan_job import ScanJob

    db_result = await db.execute(
        sa_select(ScanJob).where(ScanJob.id == uuid.UUID(job_id))
    )

    # AsyncMock 환경에서는 scalar_one_or_none이 coroutine일 수 있으므로 await 처리
    scalar_fn = db_result.scalar_one_or_none
    if asyncio.iscoroutinefunction(scalar_fn):
        scan_job = await scalar_fn()
    else:
        scan_job = scalar_fn()

    if scan_job is None:
        return

    scan_job.findings_count = findings_count
    scan_job.true_positives_count = true_positives_count
    scan_job.false_positives_count = false_positives_count
    scan_job.auto_filtered_count = auto_filtered_count


# ──────────────────────────────────────────────────────────────
# 워커 시작
# ──────────────────────────────────────────────────────────────

def start_worker() -> None:
    """RQ 워커를 시작한다.

    'scans' 큐를 리스닝하며 스캔 작업을 처리한다.
    """
    redis_conn = redis.from_url(settings.REDIS_URL)
    queues = [Queue("scans", connection=redis_conn)]

    worker = Worker(queues, connection=redis_conn)
    redis_host = settings.REDIS_URL.split("@")[-1] if "@" in settings.REDIS_URL else settings.REDIS_URL
    logger.info(f"[ScanWorker] 워커 시작 (Redis: {redis_host})")
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    start_worker()
