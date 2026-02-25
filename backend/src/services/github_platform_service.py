"""GitHubPlatformService — GitHubAppService를 GitPlatformService 인터페이스로 래핑"""
from __future__ import annotations

from pathlib import Path

from src.services.git_platform_service import GitPlatformService
from src.services.github_app import GitHubAppService


class GitHubPlatformService(GitPlatformService):
    """GitHub App 기반 플랫폼 서비스 어댑터.

    GitHubAppService를 GitPlatformService 추상 인터페이스에 맞게 래핑한다.
    platform_factory.py에서 `installation_id`와 함께 생성된다.
    """

    def __init__(self, installation_id: int) -> None:
        self._installation_id = installation_id
        self._svc = GitHubAppService()

    async def validate_credentials(self) -> bool:
        try:
            await self._svc.get_installation_token(self._installation_id)
            return True
        except Exception:
            return False

    async def list_repositories(self, **_kwargs) -> list[dict]:
        return await self._svc.get_installation_repos(self._installation_id)

    async def clone_repository(
        self, full_name: str, commit_sha: str, target_dir: Path
    ) -> None:
        await self._svc.clone_repository(
            full_name=full_name,
            installation_id=self._installation_id,
            commit_sha=commit_sha,
            target_dir=target_dir,
        )

    async def get_changed_files(
        self, full_name: str, mr_or_pr_number: int
    ) -> list[str]:
        return await self._svc.get_pr_changed_files(
            full_name=full_name,
            installation_id=self._installation_id,
            pr_number=mr_or_pr_number,
        )

    async def get_default_branch_sha(self, full_name: str, branch: str) -> str:
        return await self._svc.get_default_branch_sha(
            full_name=full_name,
            installation_id=self._installation_id,
            branch=branch,
        )

    async def create_branch(
        self, full_name: str, branch_name: str, base_sha: str
    ) -> None:
        await self._svc.create_branch(
            full_name=full_name,
            installation_id=self._installation_id,
            branch_name=branch_name,
            base_sha=base_sha,
        )

    async def get_file_content(
        self, full_name: str, file_path: str, ref: str
    ) -> tuple[str, str]:
        return await self._svc.get_file_content(
            full_name=full_name,
            installation_id=self._installation_id,
            file_path=file_path,
            ref=ref,
        )

    async def create_file_commit(
        self,
        full_name: str,
        branch_name: str,
        file_path: str,
        content: str,
        message: str,
        file_sha: str,
    ) -> dict:
        return await self._svc.create_file_commit(
            full_name=full_name,
            installation_id=self._installation_id,
            branch_name=branch_name,
            file_path=file_path,
            content=content,
            message=message,
            file_sha=file_sha,
        )

    async def create_merge_request(
        self,
        full_name: str,
        head: str,
        base: str,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> dict:
        return await self._svc.create_pull_request(
            full_name=full_name,
            installation_id=self._installation_id,
            head=head,
            base=base,
            title=title,
            body=body,
            labels=labels,
        )

    async def register_webhook(
        self,
        full_name: str,  # noqa: ARG002
        webhook_url: str,  # noqa: ARG002
        secret: str,  # noqa: ARG002
        events: list[str],  # noqa: ARG002
    ) -> None:
        # GitHub App의 경우 Webhook은 App 설치 시 자동 등록되므로 no-op
        pass
