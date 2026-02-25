"""GitLab PAT 기반 플랫폼 서비스 구현

GitLab REST API v4를 사용한다.
인증: Personal Access Token (PRIVATE-TOKEN 헤더)
"""

import base64
from pathlib import Path
from urllib.parse import quote

import httpx

from src.services.git_platform_service import GitPlatformService


class GitLabPlatformService(GitPlatformService):
    """GitLab REST API v4 기반 플랫폼 서비스.

    Personal Access Token(PAT)으로 인증한다.
    Self-managed 인스턴스를 위해 base_url을 설정할 수 있다.
    """

    def __init__(
        self,
        access_token: str,
        base_url: str = "https://gitlab.com",
    ) -> None:
        """초기화.

        Args:
            access_token: GitLab Personal Access Token
            base_url: GitLab 인스턴스 URL (트레일링 슬래시 자동 제거)
        """
        self.access_token = access_token
        # 트레일링 슬래시 정규화
        self.base_url = base_url.rstrip("/")
        self._api_base = f"{self.base_url}/api/v4"
        self._headers = {"PRIVATE-TOKEN": self.access_token}

    def _encode_path(self, full_name: str) -> str:
        """저장소 경로를 URL 인코딩한다 (슬래시 → %2F)."""
        return quote(full_name, safe="")

    async def _get_project_id(self, full_name: str) -> int:
        """저장소 전체 이름으로 GitLab project ID를 조회한다.

        Args:
            full_name: 저장소 전체 이름 (예: group/repo)

        Returns:
            GitLab project_id (정수)

        Raises:
            httpx.HTTPStatusError: GitLab API 호출 실패 시
        """
        encoded = self._encode_path(full_name)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._api_base}/projects/{encoded}",
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()["id"]

    async def validate_credentials(self) -> bool:
        """PAT 유효성 검증.

        GET /api/v4/user 를 호출하여 200이면 True, 아니면 False 반환.
        """
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._api_base}/user",
                headers=self._headers,
            )
            return resp.status_code == 200

    async def list_repositories(self, **kwargs) -> list[dict]:
        """접근 가능한 GitLab 프로젝트 목록 조회.

        x-next-page 헤더를 추적하여 전체 페이지를 수집한다.

        Returns:
            저장소 정보 딕셔너리 목록
        """
        results: list[dict] = []
        page = 1

        async with httpx.AsyncClient() as client:
            while True:
                resp = await client.get(
                    f"{self._api_base}/projects",
                    headers=self._headers,
                    params={
                        "membership": "true",
                        "per_page": 100,
                        "page": page,
                    },
                )
                resp.raise_for_status()
                projects = resp.json()
                for project in projects:
                    results.append({
                        "platform_repo_id": str(project["id"]),
                        "full_name": project["path_with_namespace"],
                        "private": project.get("visibility") != "public",
                        "default_branch": project.get("default_branch", "main"),
                        "language": project.get("language"),
                        "platform_url": project.get("web_url", ""),
                    })

                # x-next-page 헤더로 다음 페이지 확인
                next_page = resp.headers.get("x-next-page", "")
                if not next_page:
                    break
                page = int(next_page)

        return results

    async def clone_repository(
        self, full_name: str, commit_sha: str, target_dir: Path
    ) -> None:
        """저장소를 클론한다.

        git clone https://oauth2:{token}@{host}/{full_name}.git 방식 사용.
        """
        import subprocess

        host = self.base_url.replace("https://", "").replace("http://", "")
        scheme = "https" if self.base_url.startswith("https") else "http"
        clone_url = f"{scheme}://oauth2:{self.access_token}@{host}/{full_name}.git"

        subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, str(target_dir)],
            check=True,
            capture_output=True,
        )

    async def get_changed_files(
        self, full_name: str, mr_or_pr_number: int
    ) -> list[str]:
        """MR 변경 파일 목록 조회.

        GET /api/v4/projects/{id}/merge_requests/{mr_iid}/changes

        Args:
            full_name: 저장소 전체 이름
            mr_or_pr_number: MR iid

        Returns:
            변경 파일 경로 목록
        """
        project_id = await self._get_project_id(full_name)

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._api_base}/projects/{project_id}/merge_requests/{mr_or_pr_number}/changes",
                headers=self._headers,
            )
            resp.raise_for_status()
            changes = resp.json().get("changes", [])
            return [change["new_path"] for change in changes]

    async def get_default_branch_sha(
        self, full_name: str, branch: str
    ) -> str:
        """브랜치 최신 커밋 SHA 조회.

        GET /api/v4/projects/{id}/repository/branches/{branch}
        """
        project_id = await self._get_project_id(full_name)
        encoded_branch = quote(branch, safe="")

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._api_base}/projects/{project_id}/repository/branches/{encoded_branch}",
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()["commit"]["id"]

    async def create_branch(
        self, full_name: str, branch_name: str, base_sha: str
    ) -> None:
        """새 브랜치 생성.

        POST /api/v4/projects/{id}/repository/branches
        """
        project_id = await self._get_project_id(full_name)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._api_base}/projects/{project_id}/repository/branches",
                headers=self._headers,
                json={
                    "branch": branch_name,
                    "ref": base_sha,
                },
            )
            resp.raise_for_status()

    async def get_file_content(
        self, full_name: str, file_path: str, ref: str
    ) -> tuple[str, str]:
        """파일 내용 + blob SHA 조회.

        GET /api/v4/projects/{id}/repository/files/{encoded_path}?ref={ref}

        Returns:
            (decoded_content, blob_id) 튜플
        """
        project_id = await self._get_project_id(full_name)
        encoded_file_path = quote(file_path, safe="")

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._api_base}/projects/{project_id}/repository/files/{encoded_file_path}",
                headers=self._headers,
                params={"ref": ref},
            )
            resp.raise_for_status()
            data = resp.json()
            # GitLab은 base64 인코딩으로 반환
            content = base64.b64decode(data["content"]).decode("utf-8")
            blob_sha = data["blob_id"]
            return content, blob_sha

    async def create_file_commit(
        self,
        full_name: str,
        branch_name: str,
        file_path: str,
        content: str,
        message: str,
        file_sha: str,
    ) -> dict:
        """파일 수정 커밋 생성.

        PUT /api/v4/projects/{id}/repository/files/{encoded_path}
        """
        project_id = await self._get_project_id(full_name)
        encoded_file_path = quote(file_path, safe="")
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self._api_base}/projects/{project_id}/repository/files/{encoded_file_path}",
                headers=self._headers,
                json={
                    "branch": branch_name,
                    "content": encoded_content,
                    "encoding": "base64",
                    "commit_message": message,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def create_merge_request(
        self,
        full_name: str,
        head: str,
        base: str,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> dict:
        """MR 생성.

        POST /api/v4/projects/{id}/merge_requests

        Returns:
            {"number": iid, "html_url": web_url}
        """
        project_id = await self._get_project_id(full_name)

        payload: dict = {
            "source_branch": head,
            "target_branch": base,
            "title": title,
            "description": body,
        }
        if labels:
            payload["labels"] = ",".join(labels)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._api_base}/projects/{project_id}/merge_requests",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "number": data["iid"],
                "html_url": data["web_url"],
            }

    async def register_webhook(
        self,
        full_name: str,
        webhook_url: str,
        secret: str,
        events: list[str],
    ) -> None:
        """GitLab Webhook 등록.

        POST /api/v4/projects/{id}/hooks

        Args:
            full_name: 저장소 전체 이름
            webhook_url: Webhook 수신 URL
            secret: Webhook 서명용 토큰
            events: 구독 이벤트 목록 (예: ["push_events", "merge_requests_events"])
        """
        project_id = await self._get_project_id(full_name)

        # 기본 이벤트 플래그 설정
        hook_payload: dict = {
            "url": webhook_url,
            "token": secret,
            "push_events": False,
            "merge_requests_events": False,
            "enable_ssl_verification": True,
        }

        # 요청된 이벤트 활성화
        for event in events:
            hook_payload[event] = True

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._api_base}/projects/{project_id}/hooks",
                headers=self._headers,
                json=hook_payload,
            )
            resp.raise_for_status()
