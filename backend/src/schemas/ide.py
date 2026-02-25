"""IDE 전용 Pydantic 스키마 — 분석 요청/응답 데이터 검증"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# 지원 언어 목록 (ADR-F11-003)
SUPPORTED_LANGUAGES = frozenset({"python", "javascript", "typescript", "java", "go"})

# 최대 콘텐츠 크기 (1MB)
MAX_CONTENT_SIZE_BYTES = 1 * 1024 * 1024


# ──────────────────────────────────────────────────────────────
# 분석 요청/응답 스키마
# ──────────────────────────────────────────────────────────────

class IdeAnalyzeContext(BaseModel):
    """분석 컨텍스트 (선택적 메타데이터)."""

    workspace_name: str | None = None
    git_branch: str | None = None


class IdeAnalyzeRequest(BaseModel):
    """POST /api/v1/ide/analyze 요청 스키마."""

    file_path: str | None = Field(default=None, description="파일 경로")
    language: str = Field(..., description="프로그래밍 언어")
    content: str = Field(..., description="분석할 소스코드")
    context: IdeAnalyzeContext | None = None

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        """지원 언어 목록 검증."""
        if value.lower() not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"지원하지 않는 언어입니다: {value}. "
                f"지원 언어: {', '.join(sorted(SUPPORTED_LANGUAGES))}"
            )
        return value.lower()

    # content 크기 검증은 엔드포인트에서 명시적으로 400을 반환하도록 처리
    # (Pydantic validator는 422를 반환하므로 엔드포인트에서 별도 처리)


class IdeFinding(BaseModel):
    """개별 취약점 탐지 결과."""

    rule_id: str
    severity: str
    message: str
    file_path: str
    start_line: int
    end_line: int
    start_col: int = 0
    end_col: int = 0
    code_snippet: str = ""
    cwe_id: str = ""
    owasp_category: str = ""
    vulnerability_type: str = ""
    is_false_positive_filtered: bool = False


class IdeAnalyzeResponse(BaseModel):
    """POST /api/v1/ide/analyze 응답 스키마."""

    findings: list[IdeFinding]
    analysis_duration_ms: int
    semgrep_version: str = ""


# ──────────────────────────────────────────────────────────────
# FP 패턴 응답 스키마
# ──────────────────────────────────────────────────────────────

class IdeFalsePositivePattern(BaseModel):
    """오탐 패턴 항목."""

    id: uuid.UUID
    semgrep_rule_id: str
    file_pattern: str | None = None
    reason: str | None = None
    is_active: bool
    updated_at: datetime


class IdeFalsePositivePatternsResponse(BaseModel):
    """GET /api/v1/ide/false-positive-patterns 응답 스키마."""

    patterns: list[IdeFalsePositivePattern]
    last_updated: datetime | None = None
    etag: str


# ──────────────────────────────────────────────────────────────
# 패치 제안 요청/응답 스키마
# ──────────────────────────────────────────────────────────────

class IdePatchFinding(BaseModel):
    """패치 제안 요청의 finding 항목."""

    rule_id: str = Field(..., description="Semgrep 룰 ID")
    start_line: int = Field(..., description="취약 코드 시작 라인")
    end_line: int = Field(..., description="취약 코드 종료 라인")
    code_snippet: str = Field(default="", description="취약 코드 스니펫")
    message: str = Field(default="", description="취약점 설명")


class IdePatchSuggestionRequest(BaseModel):
    """POST /api/v1/ide/patch-suggestion 요청 스키마."""

    file_path: str | None = Field(default=None, description="파일 경로")
    language: str = Field(..., description="프로그래밍 언어")
    content: str = Field(..., description="파일 전체 소스코드")
    finding: IdePatchFinding = Field(..., description="패치 대상 취약점")


class VulnerabilityDetail(BaseModel):
    """취약점 상세 정보."""

    type: str
    severity: str
    cwe_id: str
    owasp_category: str
    description: str
    references: list[str]


class IdePatchSuggestionResponse(BaseModel):
    """POST /api/v1/ide/patch-suggestion 응답 스키마."""

    patch_diff: str
    patch_description: str
    vulnerability_detail: VulnerabilityDetail
