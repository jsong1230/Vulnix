"""플랫폼 서비스 팩토리

Repository 모델의 platform 필드에 따라 적절한 GitPlatformService 구현체를 반환한다.
"""

from src.services.git_platform_service import GitPlatformService
from src.services.token_crypto import decrypt_token


def get_platform_service(repo: "Repository") -> GitPlatformService:  # noqa: F821
    """Repository의 platform에 맞는 서비스 인스턴스를 반환한다.

    Args:
        repo: Repository 모델 인스턴스

    Returns:
        플랫폼에 맞는 GitPlatformService 구현체

    Raises:
        ValueError: 지원하지 않는 플랫폼인 경우
    """
    match repo.platform:
        case "github":
            from src.services.github_platform_service import GitHubPlatformService
            return GitHubPlatformService(installation_id=repo.installation_id)
        case "gitlab":
            from src.services.gitlab_service import GitLabPlatformService
            token = _decrypt_token(repo.platform_access_token_enc)
            return GitLabPlatformService(
                access_token=token,
                base_url=repo.platform_base_url or "https://gitlab.com",
            )
        case "bitbucket":
            from src.services.bitbucket_service import BitbucketPlatformService
            token = _decrypt_token(repo.platform_access_token_enc)
            return BitbucketPlatformService(
                username=repo.external_username or "",
                app_password=token,
            )
        case _:
            raise ValueError(f"지원하지 않는 플랫폼: {repo.platform}")


def _decrypt_token(encrypted_token: str | None) -> str:
    """암호화된 토큰을 복호화한다.

    token_crypto.decrypt_token을 통해 Fernet 복호화를 수행한다.

    Args:
        encrypted_token: Fernet으로 암호화된 토큰 문자열

    Returns:
        복호화된 토큰 문자열. 실패 시 빈 문자열.
    """
    if not encrypted_token:
        return ""
    return decrypt_token(encrypted_token)
