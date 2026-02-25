"""LLM 에이전트 — Claude API 기반 오탐 필터 + 패치 코드 생성"""

import asyncio
import json
import logging
from dataclasses import dataclass, field

import anthropic

from src.config import get_settings
from src.services.semgrep_engine import SemgrepFinding

logger = logging.getLogger(__name__)
settings = get_settings()

# 사용할 Claude 모델
CLAUDE_MODEL = "claude-sonnet-4-6"

# 1차 분석 시스템 프롬프트
_ANALYSIS_SYSTEM_PROMPT = """당신은 10년 이상 경력의 시니어 보안 엔지니어입니다.
정적 분석 도구의 결과를 검증하여 실제 취약점과 오탐을 구분합니다.
반드시 JSON 형식으로만 응답하세요."""

# 패치 생성 시스템 프롬프트
_PATCH_SYSTEM_PROMPT = """당신은 시니어 보안 엔지니어입니다. 보안 취약점에 대한 최소 패치 코드를 생성합니다."""


@dataclass
class LLMAnalysisResult:
    """LLM 분석 결과 데이터 구조.

    system-design.md 3-4절 기준. owasp_category, vulnerability_type 필드 추가.
    """

    finding_id: str
    is_true_positive: bool      # 실제 취약점 여부
    confidence: float           # 0.0 ~ 1.0
    severity: str               # Critical / High / Medium / Low / Informational
    reasoning: str              # 판단 근거
    patch_diff: str | None      # unified diff 형식 패치 (실제 취약점인 경우)
    patch_description: str      # 패치 설명
    owasp_category: str | None = None   # OWASP Top 10 카테고리
    vulnerability_type: str | None = None  # LLM이 분류한 취약점 유형
    references: list[str] = field(default_factory=list)  # CVE, OWASP 참조 링크
    # F-03 확장 필드
    patchable: bool = True                   # 자동 패치 가능 여부
    test_suggestion: str | None = None       # LLM이 제안한 테스트 코드
    manual_guide: str | None = None          # 수동 수정 가이드 (패치 불가 시)


class LLMAgent:
    """Claude API를 사용하여 Semgrep 결과를 분석하고 패치를 생성하는 에이전트.

    비용 절감 전략:
    - Semgrep 결과가 없으면 호출하지 않음
    - Finding별 개별 호출 대신 파일 단위 배치 처리
    """

    MAX_RETRIES = 3

    def __init__(self) -> None:
        # 비동기 클라이언트 사용 (asyncio.gather 병렬 호출을 위해 필수)
        # 테스트 환경에서는 _client를 직접 교체하므로 생성 실패 시 MagicMock으로 폴백
        try:
            self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        except Exception:
            # 테스트 환경 등에서 AsyncAnthropic 생성 실패 시 임시 객체로 초기화
            # (테스트 픽스처에서 _client를 직접 교체함)
            from unittest.mock import MagicMock
            self._client = MagicMock()

    async def analyze_findings(
        self,
        file_content: str,
        file_path: str,
        findings: list[SemgrepFinding],
    ) -> list[LLMAnalysisResult]:
        """파일 단위로 Semgrep 탐지 결과를 배치 분석한다.

        처리 흐름:
        1. findings 없으면 LLM 호출 없이 빈 목록 반환
        2. _prepare_file_content()로 파일 내용 최적화
        3. Claude API 1차 호출: 오탐 필터 + 심각도 분류
        4. true_positive 항목에 대해 _generate_patch() 호출
        5. LLMAnalysisResult 목록 반환

        Args:
            file_content: 분석할 소스 파일 전체 내용
            file_path: 파일 경로 (컨텍스트용)
            findings: 이 파일에서 탐지된 Semgrep 결과 목록

        Returns:
            분석 결과 목록
        """
        # findings가 없으면 LLM 호출 스킵
        if not findings:
            return []

        # 토큰 최적화: 500줄 초과 시 관련 라인만 추출
        optimized_content = self._prepare_file_content(file_content, findings)

        # 1차 분석 프롬프트 생성
        user_prompt = self._build_analysis_prompt(optimized_content, file_path, findings)

        # Claude API 호출 (오탐 필터 + 심각도 평가)
        raw_response = await self._call_claude_with_retry(
            messages=[{"role": "user", "content": user_prompt}],
            system=_ANALYSIS_SYSTEM_PROMPT,
        )

        # 응답 파싱
        parsed_items = self._parse_analysis_response(raw_response)

        # LLMAnalysisResult 목록 구성
        results: list[LLMAnalysisResult] = []
        for item in parsed_items:
            is_tp = item.get("is_true_positive", False)
            cwe_id = item.get("cwe_id", "")
            owasp_category = item.get("owasp_category", "")
            result = LLMAnalysisResult(
                finding_id=item.get("rule_id", ""),
                is_true_positive=is_tp,
                confidence=float(item.get("confidence", 0.0)),
                severity=item.get("severity", "Medium"),
                reasoning=item.get("reasoning", ""),
                patch_diff=None,
                patch_description="",
                owasp_category=owasp_category if owasp_category else None,
                vulnerability_type=item.get("vulnerability_type"),
                references=self._build_references(cwe_id, owasp_category),
            )

            # true_positive인 항목만 패치 생성
            if is_tp:
                # rule_id에 해당하는 finding 조회
                matching_finding = next(
                    (f for f in findings if f.rule_id == item.get("rule_id")),
                    None,
                )
                if matching_finding is not None:
                    patch_diff = await self._generate_patch(
                        finding=matching_finding,
                        file_content=file_content,
                    )
                    result.patch_diff = patch_diff

            results.append(result)

        return results

    def _prepare_file_content(
        self,
        content: str,
        findings: list[SemgrepFinding],
        max_lines: int = 500,
    ) -> str:
        """파일 내용을 LLM 전송용으로 최적화한다.

        - 500줄 이하: 전체 전송
        - 500줄 초과 + findings 5건 이상: 전체 전송
        - 500줄 초과 + findings 5건 미만: findings 주변 ±50줄만 추출
        """
        lines = content.split("\n")

        # 500줄 이하이거나 findings가 5개 이상이면 전체 반환
        if len(lines) <= max_lines or len(findings) >= 5:
            return content

        # 취약점 주변 ±50줄 범위 추출
        relevant_ranges: set[int] = set()
        for f in findings:
            start = max(0, f.start_line - 50)
            end = min(len(lines), f.end_line + 50)
            for i in range(start, end):
                relevant_ranges.add(i)

        sorted_lines = sorted(relevant_ranges)
        result_parts: list[str] = []
        prev_line = -2

        for line_num in sorted_lines:
            if line_num - prev_line > 1:
                if prev_line >= 0:
                    result_parts.append(f"\n... (생략: 라인 {prev_line + 2}~{line_num}) ...\n")
            result_parts.append(f"{line_num + 1}: {lines[line_num]}")
            prev_line = line_num

        return "\n".join(result_parts)

    def _detect_language_from_path(self, file_path: str) -> str:
        """파일 확장자에서 언어 이름을 반환한다.

        Args:
            file_path: 파일 경로 문자열 (예: "src/main.py", "app.js")

        Returns:
            언어 이름 문자열. 미인식 확장자는 "소스"를 반환한다.
        """
        from pathlib import Path

        ext_map: dict[str, str] = {
            ".py": "Python",
            ".js": "JavaScript",
            ".jsx": "JavaScript (React)",
            ".ts": "TypeScript",
            ".tsx": "TypeScript (React)",
            ".java": "Java",
            ".go": "Go",
        }
        ext = Path(file_path).suffix.lower()
        return ext_map.get(ext, "소스")

    def _build_analysis_prompt(
        self,
        file_content: str,
        file_path: str,
        findings: list[SemgrepFinding],
    ) -> str:
        """오탐 필터 + 심각도 평가 프롬프트를 생성한다."""
        findings_text = "\n".join(
            f"- Rule: {f.rule_id}, Line {f.start_line}-{f.end_line}: {f.message}\n"
            f"  Code: {f.code_snippet}"
            for f in findings
        )

        language = self._detect_language_from_path(file_path)

        return f"""다음 {language} 코드에서 정적 분석 도구가 탐지한 취약점 목록입니다.
각 항목에 대해:
1. 코드의 전체 컨텍스트를 고려하여 실제 취약점인지 오탐인지 판단하세요
2. 실제 취약점이면 심각도를 평가하세요
3. 판단 근거를 설명하세요
4. OWASP Top 10 카테고리를 매핑하세요

판단 기준:
- 사용자 입력이 실제로 제어 가능한 경로로 전달되는지 확인
- 입력 검증/이스케이프 로직이 코드 내에 이미 존재하는지 확인
- 테스트 코드, 주석, 상수 할당 등은 오탐으로 분류
- 환경변수에서 읽는 값은 하드코딩으로 분류하지 않음

--- 파일: {file_path} ---
{file_content}

--- 탐지 결과 ---
{findings_text}

JSON 응답 형식:
{{
  "results": [
    {{
      "rule_id": "해당 Semgrep 룰 ID",
      "is_true_positive": true,
      "confidence": 0.95,
      "severity": "Critical/High/Medium/Low/Informational",
      "reasoning": "판단 근거 2-3문장",
      "owasp_category": "A03:2021 - Injection",
      "vulnerability_type": "sql_injection"
    }}
  ]
}}"""

    def _build_patch_prompt(
        self,
        finding: SemgrepFinding,
        file_content: str,
    ) -> str:
        """패치 코드 생성 프롬프트를 생성한다."""
        return f"""다음 취약점에 대한 패치 코드를 생성하세요.
규칙:
- 기존 코드 스타일(들여쓰기, 네이밍 컨벤션)을 유지하세요
- 최소한의 변경으로 취약점만 수정하세요
- 기능 동작을 변경하지 마세요
- unified diff 형식으로 출력하세요
- 패치 설명을 간단히 추가하세요

--- 취약점 정보 ---
Rule: {finding.rule_id}
파일: {finding.file_path} (Line {finding.start_line}-{finding.end_line})
설명: {finding.message}
코드: {finding.code_snippet}

--- 원본 코드 ---
{file_content}

JSON 응답 형식:
{{
  "patch_diff": "--- a/file.py\\n+++ b/file.py\\n@@ ... @@\\n...",
  "patch_description": "패치 설명",
  "references": ["https://cwe.mitre.org/..."]
}}"""

    async def _generate_patch(
        self,
        finding: SemgrepFinding,
        file_content: str,
    ) -> str | None:
        """단일 취약점에 대한 패치 diff를 생성한다.

        Returns:
            unified diff 형식 패치 문자열 또는 None (패치 생성 불가 시)
        """
        prompt = self._build_patch_prompt(finding, file_content)

        try:
            raw_response = await self._call_claude_with_retry(
                messages=[{"role": "user", "content": prompt}],
                system=_PATCH_SYSTEM_PROMPT,
            )
        except Exception as e:
            logger.warning(f"[LLMAgent] 패치 생성 실패 ({finding.rule_id}): {e}")
            return None

        # JSON 파싱으로 patch_diff 추출
        try:
            parsed = json.loads(self._strip_json_wrapper(raw_response))
            return parsed.get("patch_diff")  # None이면 그대로 None 반환
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"[LLMAgent] 패치 응답 파싱 실패: {e}")
            return None

    async def _call_claude_with_retry(
        self,
        messages: list[dict],
        system: str = "",
        max_retries: int = 3,
    ) -> str:
        """Claude API를 호출하고 rate limit/서버 에러 시 지수 백오프 재시도한다.

        Args:
            messages: Claude API 메시지 목록
            system: 시스템 프롬프트
            max_retries: 최대 재시도 횟수 (기본 3)

        Returns:
            응답 텍스트

        Raises:
            anthropic.RateLimitError: max_retries 초과 시
            anthropic.APIStatusError: 4xx 에러 (rate limit 제외) 즉시 발생
        """
        kwargs: dict = {
            "model": CLAUDE_MODEL,
            "max_tokens": 4096,
            "temperature": 0.0,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        for attempt in range(max_retries + 1):
            try:
                response = await self._client.messages.create(**kwargs)
                return response.content[0].text

            except anthropic.RateLimitError:
                if attempt == max_retries:
                    raise
                wait = 2 ** (attempt + 1)  # 2초, 4초, 8초
                logger.warning(
                    f"[LLMAgent] Rate limit 도달, {wait}초 후 재시도 "
                    f"({attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(wait)

            except anthropic.APITimeoutError:
                if attempt == max_retries:
                    raise
                logger.warning(
                    f"[LLMAgent] API 타임아웃, 재시도 ({attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(2)

            except anthropic.APIStatusError as e:
                # 5xx 서버 에러는 재시도, 4xx는 즉시 raise
                if e.status_code >= 500:
                    if attempt == max_retries:
                        raise
                    wait = 2 ** (attempt + 1)
                    logger.warning(
                        f"[LLMAgent] 서버 에러({e.status_code}), "
                        f"{wait}초 후 재시도 ({attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait)
                else:
                    # 401, 403 등 4xx는 재시도 없이 즉시 발생
                    raise

        # 이 코드는 실제로 도달하지 않지만 타입 검사를 위해 유지
        raise RuntimeError("예상치 못한 재시도 루프 탈출")

    def _parse_analysis_response(self, response: str) -> list[dict]:
        """Claude 응답에서 분석 결과 JSON을 파싱한다.

        ```json ... ``` 코드블록을 처리한다.
        파싱 실패 시 경고 로그를 남기고 빈 목록을 반환한다.
        """
        cleaned = self._strip_json_wrapper(response)
        try:
            data = json.loads(cleaned)
            return data.get("results", [])
        except json.JSONDecodeError as e:
            logger.warning(f"LLM 응답 JSON 파싱 실패: {e}. 응답: {cleaned[:200]}")
            return []

    def _build_references(self, cwe_id: str, owasp_category: str) -> list[str]:
        """CWE ID와 OWASP 카테고리로부터 참조 URL 목록을 생성한다.

        Args:
            cwe_id: CWE 식별자 (예: "CWE-89")
            owasp_category: OWASP Top 10 카테고리 문자열

        Returns:
            참조 URL 목록
        """
        refs: list[str] = []
        if cwe_id:
            cwe_num = cwe_id.replace("CWE-", "")
            refs.append(f"https://cwe.mitre.org/data/definitions/{cwe_num}.html")
        if owasp_category:
            refs.append("https://owasp.org/Top10/")
        return refs

    @staticmethod
    def _strip_json_wrapper(text: str) -> str:
        """```json ... ``` 또는 ``` ... ``` 래퍼를 제거한다."""
        stripped = text.strip()

        # ```json 래퍼 처리
        if stripped.startswith("```json"):
            stripped = stripped[7:]
        elif stripped.startswith("```"):
            stripped = stripped[3:]

        if stripped.endswith("```"):
            stripped = stripped[:-3]

        return stripped.strip()
