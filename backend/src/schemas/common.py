"""공통 응답 스키마 — 모든 API 응답의 표준 형식"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """표준 API 응답 래퍼.

    모든 엔드포인트는 이 형식으로 응답한다.

    Example:
        {
            "success": true,
            "data": { ... },
            "error": null
        }
    """

    success: bool = Field(description="요청 성공 여부")
    data: T | None = Field(default=None, description="응답 데이터")
    error: str | None = Field(default=None, description="에러 메시지 (실패 시)")


class PaginatedMeta(BaseModel):
    """페이지네이션 메타 정보"""

    page: int = Field(ge=1, description="현재 페이지 번호")
    per_page: int = Field(ge=1, le=100, description="페이지당 항목 수")
    total: int = Field(ge=0, description="전체 항목 수")
    total_pages: int = Field(ge=0, description="전체 페이지 수")


class PaginatedResponse(BaseModel, Generic[T]):
    """페이지네이션 응답 래퍼"""

    success: bool = True
    data: list[T] = Field(default_factory=list)
    error: str | None = None
    meta: PaginatedMeta


class ErrorResponse(BaseModel):
    """에러 응답 스키마"""

    success: bool = False
    data: None = None
    error: str = Field(description="에러 메시지")
    error_code: str | None = Field(default=None, description="에러 코드 (예: UNAUTHORIZED)")
