"""오탐 필터 서비스 — Semgrep 결과에서 오탐 패턴 매칭 및 필터링"""

import fnmatch
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.false_positive import FalsePositiveLog, FalsePositivePattern
from src.services.semgrep_engine import SemgrepFinding

logger = logging.getLogger(__name__)


def calculate_fp_rate(true_positives: int, false_positives: int) -> float:
    """오탐율을 계산한다.

    Args:
        true_positives: 실제 취약점 건수
        false_positives: 오탐 건수

    Returns:
        오탐율 (백분율). total이 0이면 0.0 반환.
    """
    total = true_positives + false_positives
    if total == 0:
        return 0.0
    return round(false_positives / total * 100, 2)


class FPFilterService:
    """오탐 패턴 매칭 및 Semgrep findings 필터링 서비스.

    스캔 파이프라인에서 Semgrep 1차 결과 직후, LLM 호출 전에 오탐 패턴과
    일치하는 finding을 제거하여 LLM 호출 비용을 절감한다 (ADR-F06-004).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _load_patterns(self, team_id: uuid.UUID) -> list[FalsePositivePattern]:
        """팀의 활성 오탐 패턴 목록을 로드한다."""
        result = await self.db.execute(
            select(FalsePositivePattern).where(
                FalsePositivePattern.team_id == team_id,
                FalsePositivePattern.is_active.is_(True),
            )
        )
        return list(result.scalars().all())

    def _matches(self, finding: SemgrepFinding, pattern: FalsePositivePattern) -> bool:
        """finding이 패턴과 일치하는지 확인한다.

        매칭 조건 (AND):
        1. finding.rule_id == pattern.semgrep_rule_id
        2. pattern.file_pattern이 null이면 무조건 매칭
           pattern.file_pattern이 있으면 fnmatch(finding.file_path, pattern.file_pattern)
        """
        # rule_id 정확 일치
        if finding.rule_id != pattern.semgrep_rule_id:
            return False
        # file_pattern이 없으면 모든 파일에 매칭
        if pattern.file_pattern is None:
            return True
        # glob 패턴 매칭 (fnmatch)
        return fnmatch.fnmatch(finding.file_path, pattern.file_pattern)

    async def filter(
        self,
        findings: list[SemgrepFinding],
        team_id: uuid.UUID,
    ) -> list[SemgrepFinding]:
        """오탐 패턴과 일치하는 finding을 제거하고 나머지를 반환한다.

        Args:
            findings: Semgrep 탐지 결과 목록
            team_id: 팀 ID (패턴 조회용)

        Returns:
            필터링된 findings 목록 (오탐 패턴과 일치하지 않는 것만)
        """
        patterns = await self._load_patterns(team_id)
        if not patterns:
            return findings

        result = []
        for finding in findings:
            matched = False
            for pattern in patterns:
                if self._matches(finding, pattern):
                    pattern.matched_count += 1
                    matched = True
                    break
            if not matched:
                result.append(finding)

        return result

    async def filter_findings(
        self,
        findings: list[SemgrepFinding],
        team_id: uuid.UUID,
        scan_job_id: uuid.UUID,
    ) -> tuple[list[SemgrepFinding], int]:
        """오탐 패턴 매칭 + 필터링 이력 기록.

        Semgrep findings에서 오탐 패턴과 일치하는 항목을 제외하고,
        필터링 이력(FalsePositiveLog)을 기록하며 matched_count를 갱신한다.

        Args:
            findings: Semgrep 탐지 결과 목록
            team_id: 팀 ID (패턴 조회용)
            scan_job_id: 스캔 작업 ID (로그 기록용)

        Returns:
            (필터링된 findings, 자동 필터링 건수)
        """
        try:
            patterns = await self._load_patterns(team_id)
        except Exception as exc:
            # DB 조회 실패 시 fail-open: 모든 findings를 LLM으로 전달
            logger.warning(
                f"[FPFilterService] 패턴 로드 실패 — 필터링 건너뜀 (team_id={team_id}): {exc}"
            )
            return findings, 0

        if not patterns:
            return findings, 0

        filtered: list[SemgrepFinding] = []
        auto_filtered_count = 0
        now = datetime.now(timezone.utc)

        for finding in findings:
            matched_pattern: FalsePositivePattern | None = None
            for pattern in patterns:
                try:
                    if self._matches(finding, pattern):
                        matched_pattern = pattern
                        break
                except Exception as exc:
                    # 패턴 매칭 중 예외 → 해당 패턴 건너뜀
                    logger.warning(
                        f"[FPFilterService] 패턴 매칭 오류 (pattern_id={pattern.id}): {exc}"
                    )
                    continue

            if matched_pattern is not None:
                # matched_count / last_matched_at 업데이트
                matched_pattern.matched_count += 1
                matched_pattern.last_matched_at = now

                # 필터링 이력 기록
                log_entry = FalsePositiveLog(
                    pattern_id=matched_pattern.id,
                    scan_job_id=scan_job_id,
                    semgrep_rule_id=finding.rule_id,
                    file_path=finding.file_path,
                    start_line=finding.start_line,
                    filtered_at=now,
                )
                self.db.add(log_entry)
                auto_filtered_count += 1
            else:
                filtered.append(finding)

        return filtered, auto_filtered_count
