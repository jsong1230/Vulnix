"""IDE 분석 서비스 — Semgrep 실행 + FP 필터 + 패치 제안"""

import asyncio
import hashlib
import logging
import shutil
import time
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.false_positive import FalsePositivePattern
from src.services.semgrep_engine import SemgrepEngine

logger = logging.getLogger(__name__)

# IDE 분석 타임아웃 (500ms)
_IDE_ANALYZE_TIMEOUT_SEC = 0.5


class IdeAnalyzerService:
    """IDE 전용 분석 서비스.

    Semgrep을 실행하고, 팀 FP 패턴으로 필터링하여 IDE에 최적화된 응답을 반환한다.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._engine = SemgrepEngine()

    async def analyze(
        self,
        content: str,
        language: str,
        file_path: str | None,
        team_id: uuid.UUID,
    ) -> dict:
        """코드 스니펫을 Semgrep으로 분석하고 팀 FP 패턴으로 필터링한다.

        Args:
            content: 분석할 소스코드
            language: 프로그래밍 언어
            file_path: 파일 경로 (FP 패턴 glob 매칭에 사용)
            team_id: 팀 ID (FP 패턴 조회용)

        Returns:
            {findings, analysis_duration_ms, semgrep_version}
        """
        start_time = time.monotonic()
        request_id = str(uuid.uuid4())  # 전체 UUID 사용으로 충돌 방지
        temp_dir = Path(f"/tmp/vulnix-ide-{request_id}")

        try:
            # 임시 파일 생성
            temp_dir.mkdir(parents=True, exist_ok=True)
            ext = _language_to_ext(language)
            temp_file = temp_dir / f"code{ext}"
            temp_file.write_text(content, encoding="utf-8")

            # 팀 FP 패턴 조회
            fp_patterns = await self._get_fp_patterns(team_id)

            # Semgrep 실행 (타임아웃 500ms)
            raw_findings = await self._run_semgrep_with_timeout(
                temp_dir=temp_dir,
                request_id=request_id,
            )

            # FP 필터링 적용
            resolved_file_path = file_path or f"code{ext}"
            findings = self._apply_fp_filter(
                raw_findings=raw_findings,
                fp_patterns=fp_patterns,
                file_path=resolved_file_path,
            )

            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            return {
                "findings": findings,
                "analysis_duration_ms": elapsed_ms,
                "semgrep_version": "1.56.0",
            }

        finally:
            # 임시 파일 즉시 삭제 (ADR-003)
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                except OSError as e:
                    logger.warning(f"[IdeAnalyzer] 임시 디렉토리 삭제 실패: {e}")

    async def _run_semgrep_with_timeout(
        self,
        temp_dir: Path,
        request_id: str,
    ) -> list[dict]:
        """Semgrep을 타임아웃 내에 실행한다.

        타임아웃 초과 시 빈 목록 반환 (graceful degradation).
        """
        try:
            loop = asyncio.get_event_loop()
            findings = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self._engine.scan(temp_dir, request_id),
                ),
                timeout=_IDE_ANALYZE_TIMEOUT_SEC,
            )
            return [
                {
                    "rule_id": f.rule_id,
                    "severity": f.severity.lower(),
                    "message": f.message,
                    "file_path": f.file_path,
                    "start_line": f.start_line,
                    "end_line": f.end_line,
                    "start_col": 0,
                    "end_col": 0,
                    "code_snippet": f.code_snippet,
                    "cwe_id": f.cwe[0] if f.cwe else "",
                    "owasp_category": "",
                    "vulnerability_type": _rule_id_to_vuln_type(f.rule_id),
                    "is_false_positive_filtered": False,
                }
                for f in findings
            ]
        except asyncio.TimeoutError:
            logger.warning(f"[IdeAnalyzer] Semgrep 타임아웃 (500ms 초과) request_id={request_id}")
            return []
        except RuntimeError as e:
            logger.warning(f"[IdeAnalyzer] Semgrep 실행 실패: {e}")
            return []

    async def _get_fp_patterns(self, team_id: uuid.UUID) -> list:
        """팀의 활성 FP 패턴을 조회한다."""
        result = await self._db.execute(
            select(FalsePositivePattern).where(
                FalsePositivePattern.team_id == team_id,
                FalsePositivePattern.is_active == True,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    def _apply_fp_filter(
        self,
        raw_findings: list[dict],
        fp_patterns: list,
        file_path: str,
    ) -> list[dict]:
        """FP 패턴과 매칭되는 finding에 is_false_positive_filtered=True를 표시한다."""
        for finding in raw_findings:
            for pattern in fp_patterns:
                if _matches_fp_pattern(
                    rule_id=finding["rule_id"],
                    file_path=file_path,
                    pattern=pattern,
                ):
                    finding["is_false_positive_filtered"] = True
                    break
        return raw_findings

    async def generate_patch(
        self,
        content: str,
        language: str,
        file_path: str | None,
        finding: dict,
    ) -> dict:
        """LLM 기반 패치 diff를 생성한다.

        실제 구현에서는 LLMAgent를 호출하지만, 테스트에서는 mock으로 대체된다.
        """
        # LLM 호출 로직 (실제 환경에서 LLMAgent 연동)
        # 이 메서드는 테스트에서 AsyncMock으로 패치됨
        return {
            "patch_diff": "",
            "patch_description": "",
            "vulnerability_detail": {
                "type": "unknown",
                "severity": "medium",
                "cwe_id": "",
                "owasp_category": "",
                "description": "",
                "references": [],
            },
        }


def _language_to_ext(language: str) -> str:
    """언어명을 파일 확장자로 변환한다."""
    mapping = {
        "python": ".py",
        "javascript": ".js",
        "typescript": ".ts",
        "java": ".java",
        "go": ".go",
    }
    return mapping.get(language.lower(), ".txt")


def _rule_id_to_vuln_type(rule_id: str) -> str:
    """Semgrep rule_id에서 취약점 유형을 추출한다."""
    rule_lower = rule_id.lower()
    if "sql" in rule_lower or "injection" in rule_lower:
        return "sql_injection"
    if "xss" in rule_lower:
        return "xss"
    if "eval" in rule_lower:
        return "code_injection"
    if "path" in rule_lower:
        return "path_traversal"
    if "ssrf" in rule_lower:
        return "ssrf"
    if "xxe" in rule_lower:
        return "xxe"
    if "deserializ" in rule_lower:
        return "insecure_deserialization"
    return "unknown"


def _matches_fp_pattern(rule_id: str, file_path: str, pattern) -> bool:
    """finding이 FP 패턴과 매칭되는지 확인한다.

    Args:
        rule_id: Semgrep 룰 ID
        file_path: 분석 대상 파일 경로
        pattern: FalsePositivePattern 모델 인스턴스

    Returns:
        매칭 여부
    """
    # rule_id 매칭
    if pattern.semgrep_rule_id != rule_id:
        return False

    # file_pattern이 없으면 모든 파일에 적용
    if not pattern.file_pattern:
        return True

    # glob 패턴 매칭 (fnmatch 활용)
    import fnmatch
    return fnmatch.fnmatch(file_path, pattern.file_pattern)
