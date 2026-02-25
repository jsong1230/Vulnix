"""Bitbucket App Password 기반 플랫폼 서비스 구현

Bitbucket REST API 2.0을 사용한다.
인증: App Password (HTTP Basic Auth: username:app_password)
"""

from pathlib import Path
from urllib.parse import quote

import httpx

from src.services.git_platform_service import GitPlatformService

_BITBUCKET_API_BASE = "https://api.bitbucket.org/2.0"


class BitbucketPlatformService(GitPlatformService):
    """Bitbucket REST API 2.0 기반 플랫폼 서비스.

    App Password를 사용한 Basic Auth로 인증한다.
    """

    def __init__(
        self,
        username: str,
        app_password: str,
    ) -> None:
        """초기화.

        Args:
            username: Bitbucket 사용자명
            app_password: Bitbucket App Password
        """
        self.username = username
        self.app_password = app_password
        self._auth = (username, app_password)

    def _split_full_name(self, full_name: str) -> tuple[str, str]:
        """저장소 전체 이름을 workspace와 slug로 분리한다.

        Args:
            full_name: "workspace/repo-slug" 형식

        Returns:
            (workspace, repo_slug) 튜플
        """
        parts = full_name.split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"잘못된 저장소 이름 형식: {full_name} (workspace/repo-slug 필요)")
        return parts[0], parts[1]

    async def validate_credentials(self) -> bool:
        """App Password 유효성 검증.

        GET /2.0/user 를 호출하여 200이면 True, 아니면 False 반환.
        """
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_BITBUCKET_API_BASE}/user",
                auth=self._auth,
            )
            return resp.status_code == 200

    async def list_repositories(self, workspace: str = "", **kwargs) -> list[dict]:
        """접근 가능한 Bitbucket 저장소 목록 조회.

        next URL을 추적하여 전체 페이지를 수집한다.

        Args:
            workspace: Bitbucket workspace 이름

        Returns:
            저장소 정보 딕셔너리 목록
        """
        results: list[dict] = []
        # URL 인코딩 처리 (특수문자 포함 workspace 대응)
        encoded_workspace = quote(workspace, safe="-_.")
        url: str | None = f"{_BITBUCKET_API_BASE}/repositories/{encoded_workspace}"

        async with httpx.AsyncClient() as client:
            while url:
                resp = await client.get(
                    url,
                    auth=self._auth,
                )
                resp.raise_for_status()
                data = resp.json()

                for repo in data.get("values", []):
                    mainbranch = repo.get("mainbranch") or {}
                    results.append({
                        "platform_repo_id": repo.get("uuid", ""),
                        "full_name": repo.get("full_name", ""),
                        "private": repo.get("is_private", True),
                        "default_branch": mainbranch.get("name", "main"),
                        "language": repo.get("language"),
                        "platform_url": repo.get("links", {}).get("html", {}).get("href", ""),
                    })

                # next URL로 다음 페이지 확인
                url = data.get("next")

        return results

    async def clone_repository(
        self, full_name: str, commit_sha: str, target_dir: Path
    ) -> None:
        """저장소를 클론한다.

        git clone https://{username}:{app_password}@bitbucket.org/{full_name}.git 방식 사용.
        """
        import subprocess

        clone_url = (
            f"https://{quote(self.username, safe='')}:{quote(self.app_password, safe='')}@"
            f"bitbucket.org/{full_name}.git"
        )

        subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, str(target_dir)],
            check=True,
            capture_output=True,
        )

    async def get_changed_files(
        self, full_name: str, mr_or_pr_number: int
    ) -> list[str]:
        """PR diffstat 조회.

        GET /2.0/repositories/{workspace}/{slug}/pullrequests/{id}/diffstat

        Args:
            full_name: 저장소 전체 이름 (workspace/slug)
            mr_or_pr_number: PR ID

        Returns:
            변경 파일 경로 목록
        """
        workspace, repo_slug = self._split_full_name(full_name)

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_BITBUCKET_API_BASE}/repositories/{workspace}/{repo_slug}"
                f"/pullrequests/{mr_or_pr_number}/diffstat",
                auth=self._auth,
            )
            resp.raise_for_status()
            values = resp.json().get("values", [])
            # new.path가 있으면 사용, 없으면 old.path 사용 (삭제된 파일)
            paths = []
            for item in values:
                new_info = item.get("new") or {}
                old_info = item.get("old") or {}
                path = new_info.get("path") or old_info.get("path", "")
                if path:
                    paths.append(path)
            return paths

    async def get_default_branch_sha(
        self, full_name: str, branch: str
    ) -> str:
        """브랜치 최신 커밋 해시 조회.

        GET /2.0/repositories/{workspace}/{slug}/refs/branches/{branch}
        """
        workspace, repo_slug = self._split_full_name(full_name)
        encoded_branch = quote(branch, safe="")

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_BITBUCKET_API_BASE}/repositories/{workspace}/{repo_slug}"
                f"/refs/branches/{encoded_branch}",
                auth=self._auth,
            )
            resp.raise_for_status()
            return resp.json()["target"]["hash"]

    async def create_branch(
        self, full_name: str, branch_name: str, base_sha: str
    ) -> None:
        """새 브랜치 생성.

        POST /2.0/repositories/{workspace}/{slug}/refs/branches
        """
        workspace, repo_slug = self._split_full_name(full_name)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_BITBUCKET_API_BASE}/repositories/{workspace}/{repo_slug}/refs/branches",
                auth=self._auth,
                json={
                    "name": branch_name,
                    "target": {"hash": base_sha},
                },
            )
            resp.raise_for_status()

    async def get_file_content(
        self, full_name: str, file_path: str, ref: str
    ) -> tuple[str, str]:
        """파일 내용 조회.

        GET /2.0/repositories/{workspace}/{slug}/src/{commit}/{path}

        Returns:
            (content, "") 튜플 (Bitbucket은 별도 blob SHA 없음 — 빈 문자열 반환)
        """
        workspace, repo_slug = self._split_full_name(full_name)
        encoded_path = quote(file_path, safe="/")

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_BITBUCKET_API_BASE}/repositories/{workspace}/{repo_slug}"
                f"/src/{ref}/{encoded_path}",
                auth=self._auth,
            )
            resp.raise_for_status()
            return resp.text, ""

    async def create_file_commit(
        self,
        full_name: str,
        branch_name: str,
        file_path: str,
        content: str,
        message: str,
        file_sha: str,
    ) -> dict:
        """파일 수정 커밋 생성 (form-data 형식).

        POST /2.0/repositories/{workspace}/{slug}/src

        Bitbucket src API는 multipart form-data로 파일 내용을 전달한다.

        Returns:
            Location 헤더를 포함한 결과 딕셔너리
        """
        workspace, repo_slug = self._split_full_name(full_name)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_BITBUCKET_API_BASE}/repositories/{workspace}/{repo_slug}/src",
                auth=self._auth,
                data={
                    "message": message,
                    "branch": branch_name,
                    file_path: content,
                },
            )
            resp.raise_for_status()
            return {"location": resp.headers.get("Location", "")}

    async def create_merge_request(
        self,
        full_name: str,
        head: str,
        base: str,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> dict:
        """PR 생성.

        POST /2.0/repositories/{workspace}/{slug}/pullrequests

        Returns:
            {"number": id, "html_url": links.html.href}
        """
        workspace, repo_slug = self._split_full_name(full_name)

        payload: dict = {
            "title": title,
            "description": body,
            "source": {"branch": {"name": head}},
            "destination": {"branch": {"name": base}},
            "close_source_branch": False,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_BITBUCKET_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests",
                auth=self._auth,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "number": data["id"],
                "html_url": data["links"]["html"]["href"],
            }

    async def register_webhook(
        self,
        full_name: str,
        webhook_url: str,
        secret: str,
        events: list[str],
    ) -> None:
        """Bitbucket Webhook 등록.

        POST /2.0/repositories/{workspace}/{slug}/hooks
        """
        workspace, repo_slug = self._split_full_name(full_name)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_BITBUCKET_API_BASE}/repositories/{workspace}/{repo_slug}/hooks",
                auth=self._auth,
                json={
                    "description": "Vulnix Security Scanner",
                    "url": webhook_url,
                    "secret": secret,
                    "active": True,
                    "events": events,
                },
            )
            resp.raise_for_status()
