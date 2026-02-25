"""에러 메시지 국제화 (Korean/English)"""
from typing import Literal

Locale = Literal["ko", "en"]

MESSAGES: dict[str, dict[str, str]] = {
    "ko": {
        # 인증
        "invalid_credentials": "이메일 또는 비밀번호가 올바르지 않습니다.",
        "token_expired": "인증 토큰이 만료되었습니다. 다시 로그인해주세요.",
        "unauthorized": "인증이 필요합니다.",
        "forbidden": "권한이 없습니다.",
        # 저장소
        "repo_not_found": "저장소를 찾을 수 없습니다.",
        "repo_already_exists": "이미 연동된 저장소입니다.",
        "repo_access_denied": "저장소 접근 권한이 없습니다.",
        # 스캔
        "scan_not_found": "스캔 결과를 찾을 수 없습니다.",
        "scan_already_running": "이미 스캔이 진행 중입니다.",
        # 취약점
        "vuln_not_found": "취약점을 찾을 수 없습니다.",
        # 알림
        "notification_not_found": "알림 설정을 찾을 수 없습니다.",
        "webhook_url_invalid": "유효하지 않은 Webhook URL입니다.",
        # API Key
        "api_key_invalid": "유효하지 않은 API Key입니다.",
        "api_key_expired": "만료된 API Key입니다.",
        "api_key_revoked": "비활성화된 API Key입니다.",
        # 공통
        "not_found": "리소스를 찾을 수 없습니다.",
        "internal_error": "서버 오류가 발생했습니다.",
        "validation_error": "입력값이 올바르지 않습니다.",
        "rate_limit_exceeded": "요청 횟수를 초과했습니다. 잠시 후 다시 시도해주세요.",
    },
    "en": {
        # Auth
        "invalid_credentials": "Invalid email or password.",
        "token_expired": "Authentication token expired. Please log in again.",
        "unauthorized": "Authentication required.",
        "forbidden": "You do not have permission to perform this action.",
        # Repository
        "repo_not_found": "Repository not found.",
        "repo_already_exists": "Repository already connected.",
        "repo_access_denied": "Access denied to this repository.",
        # Scan
        "scan_not_found": "Scan not found.",
        "scan_already_running": "A scan is already in progress.",
        # Vulnerability
        "vuln_not_found": "Vulnerability not found.",
        # Notification
        "notification_not_found": "Notification configuration not found.",
        "webhook_url_invalid": "Invalid Webhook URL.",
        # API Key
        "api_key_invalid": "Invalid API key.",
        "api_key_expired": "API key has expired.",
        "api_key_revoked": "API key has been revoked.",
        # Common
        "not_found": "Resource not found.",
        "internal_error": "An internal server error occurred.",
        "validation_error": "Invalid input data.",
        "rate_limit_exceeded": "Rate limit exceeded. Please try again later.",
    },
}


def get_message(key: str, locale: Locale = "ko") -> str:
    """로케일에 맞는 에러 메시지 반환. 키가 없으면 한국어 폴백."""
    locale_msgs = MESSAGES.get(locale, MESSAGES["ko"])
    return locale_msgs.get(key, MESSAGES["ko"].get(key, key))


def get_locale_from_header(accept_language: str | None) -> Locale:
    """Accept-Language 헤더에서 locale 감지."""
    if not accept_language:
        return "ko"
    lang = accept_language.split(",")[0].strip().split(";")[0].strip().lower()
    if lang.startswith("en"):
        return "en"
    return "ko"
