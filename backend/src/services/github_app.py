"""GitHub App 연동 서비스 — Webhook 수신, 코드 클론, PR 생성"""

import base64
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Installation Token 캐시 구조: {installation_id: {"token": str, "expires_at": datetime}}
_token_cache: dict[int, dict[str, Any]] = {}


class GitHubAppService:
    """GitHub App API 연동 서비스.

    역할:
    - GitHub App JWT 생성
    - Installation Access Token 발급
    - 저장소 코드 클론 (read)
    - 패치 PR 생성 (write)

    주요 기술: PyJWT + httpx + GitHub REST API v3
    """

    def __init__(self) -> None:
        self._app_id = settings.GITHUB_APP_ID
        self._private_key = settings.GITHUB_APP_PRIVATE_KEY

    def _generate_jwt(self) -> str:
        """GitHub App JWT를 생성한다.

        GitHub App은 RS256 알고리즘으로 서명된 JWT를 사용하여
        Installation Access Token을 발급받는다.

        Returns:
            RS256 서명된 JWT 문자열

        Raises:
            RuntimeError: JWT 생성 실패 시
        """
        import time

        import jwt as pyjwt

        now = int(time.time())
        # 클럭 드리프트 여유: 60초 이전부터 시작
        iat = now - 60
        exp = iat + 10 * 60  # 10분

        payload = {
            "iat": iat,
            "exp": exp,
            "iss": str(self._app_id),  # PyJWT v2: iss must be a string
        }

        try:
            token: str = pyjwt.encode(payload, self._private_key, algorithm="RS256")
            return token
        except Exception as e:
            logger.error(f"GitHub App JWT 생성 실패: {e}")
            raise RuntimeError(f"GitHub App JWT 생성 실패: {e}") from e

    async def get_installation_token(self, installation_id: int) -> str:
        """GitHub App Installation Access Token을 발급받는다.

        인메모리 캐시를 사용하여 만료 5분 전까지 재사용한다.

        Args:
            installation_id: GitHub App 설치 ID

        Returns:
            Installation Access Token (1시간 유효)
        """
        # 캐시 확인
        if installation_id in _token_cache:
            cached = _token_cache[installation_id]
            expires_at: datetime = cached["expires_at"]
            now = datetime.now(timezone.utc)
            # 만료 5분 전이면 갱신
            if (expires_at - now).total_seconds() > 300:
                return cached["token"]

        # 새 토큰 발급
        jwt_token = self._generate_jwt()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()
            data = response.json()

        token: str = data["token"]
        expires_at_str: str = data["expires_at"]
        expires_at_dt = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))

        # 캐시 저장
        _token_cache[installation_id] = {
            "token": token,
            "expires_at": expires_at_dt,
        }

        return token

    async def get_all_installations(self) -> list[dict]:
        """GitHub App에 설치된 모든 installation 목록을 조회한다.

        Returns:
            installation 정보 목록 (id, account, ...)
        """
        jwt_token = self._generate_jwt()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/app/installations",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                params={"per_page": 100},
            )
            response.raise_for_status()
            return response.json()

    async def get_installation_repos(self, installation_id: int) -> list[dict]:
        """GitHub App 설치에서 접근 가능한 저장소 목록을 조회한다.

        Args:
            installation_id: GitHub App 설치 ID

        Returns:
            저장소 정보 목록 (id, full_name, private, default_branch, language)
        """
        token = await self.get_installation_token(installation_id)

        repos: list[dict] = []
        page = 1

        async with httpx.AsyncClient() as client:
            while True:
                response = await client.get(
                    "https://api.github.com/installation/repositories",
                    headers={
                        "Authorization": f"token {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    params={"per_page": 100, "page": page},
                )
                response.raise_for_status()
                data = response.json()
                batch: list[dict] = data.get("repositories", [])

                for repo in batch:
                    repos.append({
                        "id": repo["id"],
                        "full_name": repo["full_name"],
                        "private": repo.get("private", False),
                        "default_branch": repo.get("default_branch", "main"),
                        "language": repo.get("language"),
                    })

                # 다음 페이지가 없으면 종료
                if len(batch) < 100:
                    break
                page += 1

        return repos

    async def get_pr_changed_files(
        self,
        full_name: str,
        installation_id: int,
        pr_number: int,
    ) -> list[str]:
        """PR의 변경 파일 목록을 조회한다.

        Args:
            full_name: 저장소 전체 이름 (예: org/repo-name)
            installation_id: GitHub App 설치 ID
            pr_number: PR 번호

        Returns:
            변경된 파일 경로 목록
        """
        token = await self.get_installation_token(installation_id)

        files: list[str] = []
        page = 1

        async with httpx.AsyncClient() as client:
            while True:
                response = await client.get(
                    f"https://api.github.com/repos/{full_name}/pulls/{pr_number}/files",
                    headers={
                        "Authorization": f"token {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    params={"per_page": 100, "page": page},
                )
                response.raise_for_status()
                batch: list[dict] = response.json()

                for file_info in batch:
                    files.append(file_info["filename"])

                if len(batch) < 100:
                    break
                page += 1

        return files

    async def get_default_branch_sha(
        self,
        full_name: str,
        installation_id: int,
        branch: str,
    ) -> str:
        """특정 브랜치의 최신 커밋 SHA를 조회한다.

        Args:
            full_name: 저장소 전체 이름
            installation_id: GitHub App 설치 ID
            branch: 브랜치명

        Returns:
            최신 커밋 SHA (40자)
        """
        token = await self.get_installation_token(installation_id)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/repos/{full_name}/branches/{branch}",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()
            data = response.json()

        return data["commit"]["sha"]

    async def clone_repository(
        self,
        full_name: str,
        installation_id: int,
        commit_sha: str,
        target_dir: Path,
    ) -> None:
        """저장소를 특정 커밋 기준으로 임시 디렉토리에 다운로드한다.

        GitHub API의 tarball 엔드포인트를 사용해 git 바이너리 없이 저장소를
        다운로드하고 target_dir에 압축 해제한다. private repo도 지원.

        Args:
            full_name: 저장소 전체 이름 (예: org/repo-name)
            installation_id: GitHub App 설치 ID
            commit_sha: 대상 커밋 SHA (빈 문자열이면 HEAD 사용)
            target_dir: 압축 해제할 로컬 디렉토리 경로
        """
        import tarfile
        import tempfile

        token = await self.get_installation_token(installation_id)
        ref = commit_sha if commit_sha else "HEAD"

        target_dir.mkdir(parents=True, exist_ok=True)

        # GitHub API tarball 다운로드 (리다이렉트 자동 추적)
        async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
            response = await client.get(
                f"https://api.github.com/repos/{full_name}/tarball/{ref}",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()
            tarball_bytes = response.content

        # 임시 파일에 tarball 저장 후 압축 해제
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp.write(tarball_bytes)
            tmp_path = Path(tmp.name)

        try:
            with tarfile.open(tmp_path, "r:gz") as tar:
                members = tar.getmembers()
                if not members:
                    raise RuntimeError(f"빈 tarball: {full_name}@{ref}")

                # GitHub tarball의 루트 디렉토리 이름 (예: owner-repo-abc1234/)
                root_prefix = members[0].name.split("/")[0] + "/"

                # 루트 디렉토리를 제거하고 target_dir에 직접 추출
                for member in members:
                    if member.name.startswith(root_prefix):
                        member.name = member.name[len(root_prefix):]
                    if not member.name:
                        continue
                    tar.extract(member, path=target_dir, filter="data")
        finally:
            tmp_path.unlink(missing_ok=True)

        logger.info(f"[GitHubApp] 저장소 클론 완료: {full_name}@{ref} → {target_dir}")

    async def create_patch_pr(
        self,
        full_name: str,
        installation_id: int,
        base_branch: str,
        patch_branch: str,
        patch_diff: str,
        pr_title: str,
        pr_body: str,
    ) -> dict:
        """패치 PR을 생성한다."""
        raise NotImplementedError("TODO: 패치 PR 생성 구현")

    async def create_branch(
        self,
        full_name: str,
        installation_id: int,
        branch_name: str,
        base_sha: str,
    ) -> None:
        """GitHub ref를 생성하여 새 브랜치를 만든다.

        GitHub API: POST /repos/{owner}/{repo}/git/refs

        Args:
            full_name: 저장소 전체 이름 (예: org/repo-name)
            installation_id: GitHub App 설치 ID
            branch_name: 생성할 브랜치명
            base_sha: 기준 커밋 SHA

        Raises:
            httpx.HTTPStatusError: API 호출 실패 시 (422 제외 — 이미 존재하는 브랜치 허용)
        """
        token = await self.get_installation_token(installation_id)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"https://api.github.com/repos/{full_name}/git/refs",
                    headers={
                        "Authorization": f"token {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    json={
                        "ref": f"refs/heads/{branch_name}",
                        "sha": base_sha,
                    },
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                # 422: 이미 존재하는 브랜치 — 기존 브랜치를 삭제 후 재생성
                if e.response.status_code == 422:
                    logger.warning(
                        f"[GitHubApp] 브랜치 이미 존재, 삭제 후 재생성: {branch_name}"
                    )
                    await client.delete(
                        f"https://api.github.com/repos/{full_name}/git/refs/heads/{branch_name}",
                        headers={
                            "Authorization": f"token {token}",
                            "Accept": "application/vnd.github+json",
                            "X-GitHub-Api-Version": "2022-11-28",
                        },
                    )
                    response2 = await client.post(
                        f"https://api.github.com/repos/{full_name}/git/refs",
                        headers={
                            "Authorization": f"token {token}",
                            "Accept": "application/vnd.github+json",
                            "X-GitHub-Api-Version": "2022-11-28",
                        },
                        json={
                            "ref": f"refs/heads/{branch_name}",
                            "sha": base_sha,
                        },
                    )
                    response2.raise_for_status()
                else:
                    raise

    async def get_file_content(
        self,
        full_name: str,
        installation_id: int,
        file_path: str,
        ref: str,
    ) -> tuple[str, str]:
        """파일 내용과 blob SHA를 조회한다.

        GitHub API: GET /repos/{owner}/{repo}/contents/{path}?ref={ref}

        Args:
            full_name: 저장소 전체 이름
            installation_id: GitHub App 설치 ID
            file_path: 파일 경로
            ref: 브랜치명 또는 커밋 SHA

        Returns:
            (파일 내용 문자열, blob SHA)

        Raises:
            httpx.HTTPStatusError: 파일 없음(404) 등 API 호출 실패 시
        """
        token = await self.get_installation_token(installation_id)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/repos/{full_name}/contents/{file_path}",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                params={"ref": ref},
            )
            response.raise_for_status()
            data = response.json()

        # base64 디코딩 (GitHub API는 개행 포함 base64 반환)
        encoded_content: str = data["content"]
        # 개행 문자 제거 후 디코딩
        decoded_content = base64.b64decode(
            encoded_content.replace("\n", "")
        ).decode("utf-8")
        blob_sha: str = data["sha"]

        return decoded_content, blob_sha

    async def create_file_commit(
        self,
        full_name: str,
        installation_id: int,
        branch_name: str,
        file_path: str,
        content: str,
        message: str,
        file_sha: str,
    ) -> dict:
        """브랜치에 파일 수정 커밋을 생성한다.

        GitHub API: PUT /repos/{owner}/{repo}/contents/{path}

        Args:
            full_name: 저장소 전체 이름
            installation_id: GitHub App 설치 ID
            branch_name: 커밋을 추가할 브랜치명
            file_path: 수정할 파일 경로
            content: 수정된 파일 내용 (평문)
            message: 커밋 메시지
            file_sha: 기존 파일의 blob SHA (Contents API 업데이트에 필수)

        Returns:
            커밋 결과 딕셔너리 (commit.sha, content.sha 포함)
        """
        token = await self.get_installation_token(installation_id)

        # 파일 내용을 base64로 인코딩
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"https://api.github.com/repos/{full_name}/contents/{file_path}",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={
                    "message": message,
                    "content": encoded_content,
                    "branch": branch_name,
                    "sha": file_sha,
                },
            )
            response.raise_for_status()
            return response.json()

    async def create_pull_request(
        self,
        full_name: str,
        installation_id: int,
        head: str,
        base: str,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> dict:
        """Pull Request를 생성한다.

        GitHub API: POST /repos/{owner}/{repo}/pulls

        Args:
            full_name: 저장소 전체 이름
            installation_id: GitHub App 설치 ID
            head: PR의 head 브랜치
            base: PR의 base 브랜치
            title: PR 제목
            body: PR 본문
            labels: 추가할 라벨 목록 (선택)

        Returns:
            {"number": int, "html_url": str} 형식의 딕셔너리
        """
        token = await self.get_installation_token(installation_id)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.github.com/repos/{full_name}/pulls",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={
                    "title": title,
                    "body": body,
                    "head": head,
                    "base": base,
                },
            )
            response.raise_for_status()
            data = response.json()

        result = {
            "number": data["number"],
            "html_url": data["html_url"],
        }

        # 라벨 추가 (선택적) — PR 생성 후 별도 호출
        if labels:
            pr_number = data["number"]
            try:
                async with httpx.AsyncClient() as client:
                    label_response = await client.post(
                        f"https://api.github.com/repos/{full_name}/issues/{pr_number}/labels",
                        headers={
                            "Authorization": f"token {token}",
                            "Accept": "application/vnd.github+json",
                            "X-GitHub-Api-Version": "2022-11-28",
                        },
                        json={"labels": labels},
                    )
                    label_response.raise_for_status()
            except Exception as e:
                # 라벨 추가 실패는 경고만 기록 (PR 생성은 성공으로 유지)
                logger.warning(
                    f"[GitHubApp] 라벨 추가 실패 (PR #{pr_number}): {e}"
                )

        return result
