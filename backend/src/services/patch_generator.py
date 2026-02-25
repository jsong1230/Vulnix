"""패치 생성 서비스 — LLM 패치를 GitHub PR로 제출하는 흐름 조율"""

import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.patch_pr import PatchPR
from src.models.vulnerability import Vulnerability
from src.services.github_app import GitHubAppService
from src.services.llm_agent import LLMAnalysisResult
from src.services.semgrep_engine import SemgrepFinding

logger = logging.getLogger(__name__)

# 심각도 → 수동 수정 우선순위 매핑
_SEVERITY_PRIORITY_MAP: dict[str, str] = {
    "critical": "P0",
    "high": "P1",
    "medium": "P2",
    "low": "P3",
}

# 심각도 → badge 이모지 매핑
_SEVERITY_BADGE_MAP: dict[str, str] = {
    "critical": ":red_circle:",
    "high": ":orange_circle:",
    "medium": ":yellow_circle:",
    "low": ":white_circle:",
}


class PatchGenerator:
    """LLM이 생성한 패치를 GitHub PR로 자동 제출하는 서비스.

    조율 흐름:
    1. LLM 분석 결과에서 패치 가능한 취약점 추출
    2. GitHubAppService로 패치 브랜치 생성 및 PR 제출
    3. PatchPR 레코드 DB 저장
    """

    def __init__(self) -> None:
        self._github_service = GitHubAppService()

    async def generate_patch_prs(
        self,
        repo_full_name: str,
        installation_id: int,
        base_branch: str,
        scan_job_id: uuid.UUID,
        repo_id: uuid.UUID,
        analysis_results: list[LLMAnalysisResult],
        findings: list[SemgrepFinding],
        db: AsyncSession,
    ) -> list[PatchPR]:
        """분석 결과에서 패치 PR을 생성하고 PatchPR 레코드를 반환한다.

        Args:
            repo_full_name: 저장소 전체 이름 (예: org/repo-name)
            installation_id: GitHub App 설치 ID
            base_branch: 기준 브랜치명
            scan_job_id: 스캔 작업 ID
            repo_id: 저장소 ID
            analysis_results: LLM 분석 결과 목록
            findings: Semgrep 탐지 결과 목록 (finding_id로 Vulnerability 조회에 필요)
            db: 비동기 DB 세션

        Returns:
            생성된 PatchPR ORM 객체 목록
        """
        if not analysis_results:
            return []

        # finding_id → SemgrepFinding 인덱스 (Vulnerability 조회용)
        finding_map: dict[str, SemgrepFinding] = {
            f.rule_id: f for f in findings
        }

        # 오탐 제외: is_true_positive=True 항목만 처리
        true_positive_results = [
            r for r in analysis_results if r.is_true_positive
        ]

        # 패치 불가 항목 처리 (is_true_positive=True 이지만 patch_diff=None)
        unpatchable_results = [
            r for r in true_positive_results if not r.patch_diff
        ]
        for result in unpatchable_results:
            await self._handle_unpatchable(
                result=result,
                finding_map=finding_map,
                scan_job_id=scan_job_id,
                repo_id=repo_id,
                db=db,
            )

        # 패치 가능 항목 필터링
        patchable_results = [
            r for r in true_positive_results if r.patch_diff
        ]

        if not patchable_results:
            return []

        # base_branch의 최신 SHA 조회 (모든 PR에 공통 사용)
        base_sha = await self._github_service.get_default_branch_sha(
            full_name=repo_full_name,
            installation_id=installation_id,
            branch=base_branch,
        )

        # asyncio.Semaphore(3)으로 GitHub API 동시 호출 제한
        semaphore = asyncio.Semaphore(3)

        async def create_single_pr(result: LLMAnalysisResult) -> PatchPR | None:
            """단일 취약점에 대한 PR을 생성하고 PatchPR 레코드를 반환한다."""
            async with semaphore:
                return await self._create_patch_pr_for_result(
                    result=result,
                    finding_map=finding_map,
                    repo_full_name=repo_full_name,
                    installation_id=installation_id,
                    base_branch=base_branch,
                    base_sha=base_sha,
                    scan_job_id=scan_job_id,
                    repo_id=repo_id,
                    db=db,
                )

        # 병렬 처리
        tasks = [create_single_pr(result) for result in patchable_results]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        patch_prs: list[PatchPR] = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"[PatchGenerator] 개별 PR 생성 실패: {r}")
                continue
            if r is not None:
                patch_prs.append(r)  # type: ignore[arg-type]

        return patch_prs

    async def _create_patch_pr_for_result(
        self,
        result: LLMAnalysisResult,
        finding_map: dict[str, SemgrepFinding],
        repo_full_name: str,
        installation_id: int,
        base_branch: str,
        base_sha: str,
        scan_job_id: uuid.UUID,
        repo_id: uuid.UUID,
        db: AsyncSession,
    ) -> PatchPR | None:
        """단일 LLMAnalysisResult에 대한 패치 PR을 생성한다.

        Returns:
            생성된 PatchPR 또는 None (실패 시)
        """
        finding = finding_map.get(result.finding_id)

        # Vulnerability DB 조회 (finding 유무에 따라 조회 조건 다름)
        if finding is not None:
            db_result = await db.execute(
                select(Vulnerability).where(
                    Vulnerability.scan_job_id == scan_job_id,
                    Vulnerability.semgrep_rule_id == result.finding_id,
                    Vulnerability.file_path == finding.file_path,
                    Vulnerability.start_line == finding.start_line,
                )
            )
        else:
            # finding_map 미매칭 시 finding_id=semgrep_rule_id와 scan_job_id만으로 조회
            db_result = await db.execute(
                select(Vulnerability).where(
                    Vulnerability.scan_job_id == scan_job_id,
                    Vulnerability.semgrep_rule_id == result.finding_id,
                )
            )
        vuln = db_result.scalar_one_or_none()

        if vuln is None:
            logger.warning(
                f"[PatchGenerator] Vulnerability를 찾을 수 없음: "
                f"rule_id={result.finding_id}"
            )
            return None

        # finding이 없으면 Vulnerability에서 파일 정보 사용
        file_path = finding.file_path if finding is not None else vuln.file_path
        start_line = finding.start_line if finding is not None else vuln.start_line
        end_line = finding.end_line if finding is not None else vuln.end_line
        cwe_list = finding.cwe if finding is not None else []
        description = finding.message if finding is not None else (vuln.description or "")

        # 브랜치명 생성
        branch_name = self._make_branch_name(
            vulnerability_type=result.vulnerability_type or "unknown",
            file_path=file_path,
            start_line=start_line,
        )

        # 브랜치 생성
        await self._github_service.create_branch(
            full_name=repo_full_name,
            installation_id=installation_id,
            branch_name=branch_name,
            base_sha=base_sha,
        )

        # 패치 적용 (원본 파일 내용 + diff → 수정된 파일 내용)
        apply_result = await self._apply_patch_diff(
            full_name=repo_full_name,
            installation_id=installation_id,
            file_path=file_path,
            patch_diff=result.patch_diff,  # type: ignore[arg-type]
            ref=base_branch,
        )

        # diff 적용 여부에 따라 파일 커밋 처리
        if apply_result is not None:
            # diff 적용 성공 → 수정된 파일 커밋
            patched_content, file_sha = apply_result
            commit_message = (
                f"[Vulnix] Fix {result.vulnerability_type or 'security issue'} "
                f"in {file_path}"
            )
            await self._github_service.create_file_commit(
                full_name=repo_full_name,
                installation_id=installation_id,
                branch_name=branch_name,
                file_path=file_path,
                content=patched_content,
                message=commit_message,
                file_sha=file_sha,
            )
        else:
            # diff 적용 실패 → 파일 커밋 없이 PR만 생성 (PR body에 diff 포함)
            logger.warning(
                f"[PatchGenerator] diff 적용 실패, PR body에 diff 포함하여 PR 생성: "
                f"{file_path}:{start_line}"
            )

        # PR 본문 생성
        pr_body = self._build_pr_body({
            "vulnerability_type": result.vulnerability_type,
            "cwe_id": cwe_list[0] if cwe_list else None,
            "severity": result.severity.lower(),
            "file_path": file_path,
            "start_line": start_line,
            "end_line": end_line,
            "description": description,
            "reasoning": result.reasoning,
            "patch_description": result.patch_description,
            "references": result.references,
            "patch_diff": result.patch_diff,
            "owasp_category": result.owasp_category,
            "test_suggestion": getattr(result, "test_suggestion", None),
        })

        # PR 생성
        pr_title = (
            f"[Vulnix] Fix {result.vulnerability_type or 'security issue'} "
            f"in {file_path}"
        )
        severity_lower = result.severity.lower()
        pr_data = await self._github_service.create_pull_request(
            full_name=repo_full_name,
            installation_id=installation_id,
            head=branch_name,
            base=base_branch,
            title=pr_title,
            body=pr_body,
            labels=["security", "vulnix-auto-patch", severity_lower],
        )

        # PatchPR 레코드 DB 저장
        patch_pr = PatchPR(
            vulnerability_id=vuln.id,
            repo_id=repo_id,
            github_pr_number=pr_data["number"],
            github_pr_url=pr_data["html_url"],
            branch_name=branch_name,
            status="created",
            patch_diff=result.patch_diff,
            patch_description=result.patch_description,
            test_suggestion=getattr(result, "test_suggestion", None),
            created_at=datetime.now(timezone.utc),
        )
        db.add(patch_pr)

        # Vulnerability 상태 → "patched"
        vuln.status = "patched"

        await db.commit()
        return patch_pr

    async def _handle_unpatchable(
        self,
        result: LLMAnalysisResult,
        finding_map: dict[str, SemgrepFinding],
        scan_job_id: uuid.UUID,
        repo_id: uuid.UUID,
        db: AsyncSession,
    ) -> None:
        """패치 불가 취약점에 수동 수정 가이드를 저장한다.

        Vulnerability.manual_guide, Vulnerability.manual_priority 업데이트.
        PatchPR 레코드는 생성하지 않는다 (ADR-F03-002).
        """
        finding = finding_map.get(result.finding_id)

        # finding이 있으면 파일/라인 정보를 포함한 정밀 조회, 없으면 rule_id만으로 조회
        if finding is not None:
            db_result = await db.execute(
                select(Vulnerability).where(
                    Vulnerability.scan_job_id == scan_job_id,
                    Vulnerability.semgrep_rule_id == result.finding_id,
                    Vulnerability.file_path == finding.file_path,
                    Vulnerability.start_line == finding.start_line,
                )
            )
        else:
            # finding_map 미매칭 시 finding_id(=semgrep_rule_id)와 scan_job_id만으로 조회
            db_result = await db.execute(
                select(Vulnerability).where(
                    Vulnerability.scan_job_id == scan_job_id,
                    Vulnerability.semgrep_rule_id == result.finding_id,
                )
            )
        vuln = db_result.scalar_one_or_none()

        if vuln is None:
            return

        # 심각도 기반 우선순위 결정
        severity_lower = (
            getattr(vuln, "severity", None) or result.severity
        ).lower()
        priority = _SEVERITY_PRIORITY_MAP.get(severity_lower, "P3")

        # 파일 정보: finding이 있으면 finding에서, 없으면 vuln에서
        fp = finding.file_path if finding is not None else getattr(vuln, "file_path", "")
        sl = finding.start_line if finding is not None else getattr(vuln, "start_line", 0)
        el = finding.end_line if finding is not None else getattr(vuln, "end_line", 0)

        # manual_guide 텍스트 구성 (설계서 4-5절 형식)
        manual_guide_content = getattr(result, "manual_guide", None)
        if manual_guide_content:
            guide_text = manual_guide_content
        else:
            guide_text = (
                f"이 취약점은 자동 패치가 불가능합니다. "
                f"수동으로 수정해야 합니다.\n\n"
                f"**분석 근거**: {result.reasoning}"
            )

        vuln.manual_guide = (
            f"## 수동 수정 가이드\n\n"
            f"### 취약점\n"
            f"- 유형: {result.vulnerability_type}\n"
            f"- 파일: {fp} (Line {sl}-{el})\n"
            f"- 심각도: {severity_lower}\n"
            f"- 우선순위: {priority}\n\n"
            f"### 왜 자동 패치가 불가능한가\n"
            f"{guide_text}\n\n"
            f"### 권장 수정 방법\n"
            f"{result.patch_description or '수동으로 취약점을 수정하세요.'}\n\n"
            f"### 참고 자료\n"
            + "\n".join(f"- {ref}" for ref in result.references)
        )
        vuln.manual_priority = priority

        await db.commit()

    async def _apply_patch_diff(
        self,
        full_name: str,
        installation_id: int,
        file_path: str,
        patch_diff: str,
        ref: str,
    ) -> tuple[str, str] | None:
        """unified diff를 원본 파일에 적용하여 수정된 파일 내용을 반환한다.

        Args:
            full_name: 저장소 전체 이름
            installation_id: GitHub App 설치 ID
            file_path: 수정할 파일 경로
            patch_diff: unified diff 문자열
            ref: 브랜치명 또는 커밋 SHA

        Returns:
            (수정된 파일 내용, 원본 파일의 blob SHA) 또는 None (적용 실패 시)
        """
        # 원본 파일 내용 + SHA 조회
        original_content, file_sha = await self._github_service.get_file_content(
            full_name=full_name,
            installation_id=installation_id,
            file_path=file_path,
            ref=ref,
        )

        # unified diff 파싱 및 적용
        patched_content = self._apply_unified_diff(original_content, patch_diff)
        if patched_content is None:
            return None

        return patched_content, file_sha

    @staticmethod
    def _apply_unified_diff(original: str, diff: str) -> str | None:
        """unified diff를 원본 문자열에 적용하고 결과를 반환한다.

        Args:
            original: 원본 파일 내용
            diff: unified diff 문자열

        Returns:
            패치된 파일 내용 또는 None (컨텍스트 불일치 시)
        """
        original_lines = original.splitlines(keepends=True)
        # 마지막 줄에 개행이 없는 경우 처리
        if original_lines and not original_lines[-1].endswith("\n"):
            original_lines[-1] = original_lines[-1]

        diff_lines = diff.splitlines()

        # diff 헤더 파싱 — @@ -start,count +start,count @@ 형식 hunk 탐색
        hunks: list[tuple[int, list[str]]] = []
        i = 0
        while i < len(diff_lines):
            line = diff_lines[i]
            if line.startswith("@@"):
                # @@ -old_start,old_count +new_start,new_count @@ 파싱
                try:
                    parts = line.split(" ")
                    old_info = parts[1]  # "-old_start,old_count"
                    old_start_str = old_info.lstrip("-").split(",")[0]
                    old_start = int(old_start_str)
                except (IndexError, ValueError):
                    i += 1
                    continue

                hunk_lines: list[str] = []
                i += 1
                while i < len(diff_lines) and not diff_lines[i].startswith("@@"):
                    hunk_lines.append(diff_lines[i])
                    i += 1
                hunks.append((old_start, hunk_lines))
            else:
                i += 1

        if not hunks:
            return None

        # hunk를 역순으로 적용 (앞쪽 hunk 적용이 뒤쪽 라인 번호에 영향을 미치지 않도록)
        result_lines = list(original_lines)

        for old_start, hunk_lines in reversed(hunks):
            # 1-based → 0-based 인덱스
            idx = old_start - 1

            # 컨텍스트 및 삭제 라인 추출
            context_and_remove: list[str] = []
            add_lines: list[str] = []
            remove_lines_positions: list[int] = []  # result_lines에서 삭제할 상대 위치

            pos = idx
            for hunk_line in hunk_lines:
                if hunk_line.startswith(" "):
                    # 컨텍스트 라인 — 원본에 존재해야 함
                    context_and_remove.append(hunk_line[1:])
                    pos += 1
                elif hunk_line.startswith("-"):
                    # 삭제 라인 — 원본에 존재해야 함
                    context_and_remove.append(hunk_line[1:])
                    pos += 1
                elif hunk_line.startswith("+"):
                    # 추가 라인
                    add_lines.append(hunk_line[1:])

            # fuzzy matching: 원본에서 컨텍스트 라인들이 순서대로 존재하는지 확인
            # 삭제/컨텍스트 라인 (원본에서 제거될 라인)
            remove_content: list[str] = []
            for hunk_line in hunk_lines:
                if hunk_line.startswith(" ") or hunk_line.startswith("-"):
                    remove_content.append(hunk_line[1:])

            # 원본 파일에서 삭제 대상 라인들이 idx 위치에 일치하는지 검증
            matched = True
            for j, expected_line in enumerate(remove_content):
                orig_idx = idx + j
                if orig_idx >= len(result_lines):
                    matched = False
                    break
                orig_line = result_lines[orig_idx].rstrip("\n")
                exp_line = expected_line.rstrip("\n")
                if orig_line != exp_line:
                    matched = False
                    break

            if not matched:
                return None  # context mismatch

            # 삭제 라인 수 계산
            remove_count = len(remove_content)

            # 추가 라인에 개행 보장
            normalized_add: list[str] = []
            for add_line in add_lines:
                if add_line and not add_line.endswith("\n"):
                    add_line = add_line + "\n"
                normalized_add.append(add_line)

            # result_lines에서 삭제 후 삽입
            result_lines[idx: idx + remove_count] = normalized_add

        return "".join(result_lines)

    @staticmethod
    def _make_branch_name(
        vulnerability_type: str,
        file_path: str,
        start_line: int,
    ) -> str:
        """패치 브랜치명을 생성한다.

        형식: vulnix/fix-{vulnerability_type}-{short_hash}
        hash 기준: SHA-256(vulnerability_type:file_path:start_line)[:7]
        """
        raw = f"{vulnerability_type}:{file_path}:{start_line}"
        short_hash = hashlib.sha256(raw.encode()).hexdigest()[:7]
        safe_type = vulnerability_type.lower().replace("_", "-")
        return f"vulnix/fix-{safe_type}-{short_hash}"

    def _build_pr_body(self, vulnerability: dict) -> str:
        """설계서 4-4절 PR 본문 템플릿으로 PR 본문을 생성한다.

        Args:
            vulnerability: 취약점 정보 딕셔너리

        Returns:
            마크다운 형식의 PR 본문
        """
        vuln_type = vulnerability.get("vulnerability_type", "unknown")
        cwe_id = vulnerability.get("cwe_id", "")
        severity = vulnerability.get("severity", "unknown")
        file_path = vulnerability.get("file_path", "")
        start_line = vulnerability.get("start_line", 0)
        end_line = vulnerability.get("end_line", 0)
        owasp_category = vulnerability.get("owasp_category", "")
        reasoning = vulnerability.get("reasoning", "")
        description = vulnerability.get("description", "")
        patch_description = vulnerability.get("patch_description", "")
        patch_diff = vulnerability.get("patch_diff", "")
        references = vulnerability.get("references", [])
        test_suggestion = vulnerability.get("test_suggestion")

        severity_badge = _SEVERITY_BADGE_MAP.get(severity.lower(), "")

        # 참고 자료 목록 구성
        refs_text = "\n".join(f"- {ref}" for ref in references) if references else "- 해당 없음"

        # 기본 본문
        body = f"""## Vulnix Security Patch

### 탐지된 취약점
- **유형**: {vuln_type} ({cwe_id})
- **심각도**: {severity_badge} {severity}
- **파일**: `{file_path}` (Line {start_line}-{end_line})
- **OWASP**: {owasp_category}

### 왜 위험한가 (취약점 설명)
{reasoning}

{description}

### 무엇을 어떻게 고쳤는가 (패치 설명)
{patch_description}

### 변경 코드
```diff
{patch_diff}
```

### 참고 자료
{refs_text}
"""

        # 테스트 제안이 있을 때만 추가
        if test_suggestion:
            body += f"""
### 테스트 제안 (선택적)
```python
{test_suggestion}
```
"""

        body += """
---
> 이 PR은 [Vulnix](https://vulnix.dev) 보안 에이전트가 자동 생성했습니다.
> 반드시 코드 리뷰 후 머지하세요.
"""
        return body
