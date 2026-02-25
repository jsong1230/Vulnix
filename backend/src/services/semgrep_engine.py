"""Semgrep 1차 탐지 엔진 — CLI 실행 및 결과 파싱"""

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# 커스텀 룰 디렉토리 경로
_RULES_DIR = Path(__file__).parent.parent / "rules"


@dataclass
class SemgrepFinding:
    """Semgrep 탐지 결과를 내부 모델로 변환한 데이터 구조.

    system-design.md 3-3절 기준.
    """

    rule_id: str           # 예: "python.flask.security.xss"
    severity: str          # ERROR / WARNING / INFO
    file_path: str         # 취약 코드 위치 (상대 경로)
    start_line: int
    end_line: int
    code_snippet: str      # 해당 코드 조각
    message: str           # 룰 설명
    cwe: list[str] = field(default_factory=list)   # CWE 매핑 목록


class SemgrepEngine:
    """Semgrep CLI를 실행하고 결과를 파싱하는 서비스.

    코드 보안 원칙 (system-design.md ADR-003):
    - 고객 코드는 임시 디렉토리에만 저장
    - 스캔 완료 후 즉시 삭제 (shutil.rmtree)
    - 임시 디렉토리 경로: /tmp/vulnix-scan-{job_id}/
    """

    def __init__(self) -> None:
        self._rules_dir = _RULES_DIR

    def scan(self, target_dir: Path, job_id: str) -> list[SemgrepFinding]:
        """Semgrep으로 대상 디렉토리를 스캔한다.

        Args:
            target_dir: 스캔할 소스코드 디렉토리
            job_id: 스캔 작업 ID (로깅용)

        Returns:
            탐지된 취약점 목록

        Raises:
            RuntimeError: Semgrep 실행 실패 시
        """
        # 설계서 3-1-1 기준 커맨드 구성 (--config=auto 제외, 커스텀 룰만 사용)
        cmd = [
            "semgrep", "scan",
            "--config", str(self._rules_dir),
            "--json",
            "--quiet",
            "--timeout", "300",
            "--max-target-bytes", "1000000",
            "--jobs", "4",
            str(target_dir),
        ]

        # Semgrep CLI 실행 후 JSON 파싱
        raw = self._run_semgrep_cli(cmd)

        # 부분 에러가 있으면 경고 로그 남기되 중단하지 않음
        if raw.get("errors"):
            logger.warning(
                f"[SemgrepEngine] 스캔 중 부분 에러 발생 (job_id={job_id}): "
                f"{len(raw['errors'])}건 — 부분 결과로 계속 진행"
            )

        return self._parse_results(raw, target_dir)

    def _run_semgrep_cli(self, cmd: list[str]) -> dict:
        """Semgrep CLI를 실행하고 JSON 결과를 반환한다.

        Args:
            cmd: 실행할 Semgrep 커맨드 목록

        Returns:
            Semgrep JSON 출력 딕셔너리

        Raises:
            RuntimeError: Semgrep 미설치, 타임아웃, 내부 에러 시
        """
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 전체 실행 타임아웃 10분
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"Semgrep 실행 타임아웃 (600초 초과): {e}") from e
        except FileNotFoundError as e:
            raise RuntimeError("Semgrep CLI가 설치되지 않았습니다") from e

        # returncode 해석:
        # 0 = 클린 (취약점 없음)
        # 1 = 취약점 발견 (정상)
        # 2+ = Semgrep 내부 에러
        if result.returncode >= 2:
            raise RuntimeError(
                f"Semgrep 실행 에러 (returncode={result.returncode}): {result.stderr}"
            )

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Semgrep 출력 JSON 파싱 실패: {e}") from e

    def _parse_results(self, semgrep_output: dict, base_dir: Path) -> list[SemgrepFinding]:
        """Semgrep JSON 출력을 SemgrepFinding 목록으로 변환한다.

        Args:
            semgrep_output: semgrep --json 출력 결과
            base_dir: 상대 경로 계산 기준 디렉토리

        Returns:
            SemgrepFinding 목록
        """
        findings: list[SemgrepFinding] = []

        for result in semgrep_output.get("results", []):
            # 파일 경로를 base_dir 기준 상대 경로로 변환
            abs_path = Path(result["path"])
            try:
                rel_path = str(abs_path.relative_to(base_dir))
            except ValueError:
                rel_path = str(abs_path)

            extra = result.get("extra", {})
            metadata = extra.get("metadata", {})

            finding = SemgrepFinding(
                rule_id=result["check_id"],
                severity=extra.get("severity", "WARNING"),
                file_path=rel_path,
                start_line=result["start"]["line"],
                end_line=result["end"]["line"],
                code_snippet=extra.get("lines", ""),
                message=extra.get("message", ""),
                cwe=metadata.get("cwe", []),
            )
            findings.append(finding)

        return findings

    @staticmethod
    def prepare_temp_dir(job_id: str) -> Path:
        """스캔용 임시 디렉토리를 생성한다.

        Returns:
            /tmp/vulnix-scan-{job_id}/ 경로
        """
        temp_path = Path(f"/tmp/vulnix-scan-{job_id}")
        temp_path.mkdir(parents=True, exist_ok=True)
        return temp_path

    @staticmethod
    def cleanup_temp_dir(job_id: str) -> None:
        """스캔 완료 후 임시 디렉토리를 즉시 삭제한다.

        ADR-003: 고객 코드를 파일시스템에 잔존시키지 않는다.
        삭제 실패 시 경고 로그를 남기되 예외를 발생시키지 않는다.
        """
        temp_path = Path(f"/tmp/vulnix-scan-{job_id}")
        if temp_path.exists():
            try:
                shutil.rmtree(temp_path)
                logger.info(f"[SemgrepEngine] 임시 디렉토리 삭제 완료: {temp_path}")
            except OSError as e:
                logger.warning(f"[SemgrepEngine] 임시 디렉토리 삭제 실패 (무시): {e}")
