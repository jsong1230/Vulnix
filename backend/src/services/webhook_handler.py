"""Webhook 이벤트별 비즈니스 로직 처리 서비스"""

import uuid

from sqlalchemy import select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.repository import Repository
from src.models.scan_job import ScanJob
from src.services.github_app import GitHubAppService
from src.services.scan_orchestrator import ScanOrchestrator


class WebhookHandler:
    """GitHub Webhook 이벤트별 비즈니스 로직을 처리한다.

    webhooks.py (HTTP 레이어)에서 서명 검증 후 호출된다.
    DB 조회, 스캔 큐 등록 등의 실제 비즈니스 로직을 담당한다.
    """

    def __init__(
        self,
        db: AsyncSession,
        orchestrator: ScanOrchestrator,
        github_service: GitHubAppService | None = None,
    ) -> None:
        self.db = db
        self.orchestrator = orchestrator
        self.github_service = github_service or GitHubAppService()

    async def _get_active_repo_by_github_id(
        self, github_repo_id: int
    ) -> Repository | None:
        """github_repo_id로 활성화된 저장소를 조회한다."""
        result = await self.db.execute(
            select(Repository).where(
                Repository.github_repo_id == github_repo_id,
                Repository.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def handle_push(self, payload: dict) -> str | None:
        """push 이벤트를 처리한다.

        기본 브랜치에 Python 파일이 포함된 push만 스캔 큐에 등록한다.

        Args:
            payload: GitHub push 이벤트 페이로드

        Returns:
            등록된 ScanJob ID, 스캔 불필요 시 None
        """
        ref: str = payload.get("ref", "")
        # "refs/heads/main" -> "main"
        pushed_branch = ref.replace("refs/heads/", "")

        repo_info = payload.get("repository", {})
        github_repo_id: int = repo_info.get("id", 0)
        default_branch: str = repo_info.get("default_branch", "main")
        commit_sha: str = payload.get("after", "")

        # 기본 브랜치가 아닌 push는 무시
        if pushed_branch != default_branch:
            return None

        # 저장소가 등록되지 않았으면 무시
        repo = await self._get_active_repo_by_github_id(github_repo_id)
        if repo is None:
            return None

        # commits에서 Python 파일 추출 (added + modified, removed 제외)
        commits: list[dict] = payload.get("commits", [])
        changed_py_files: list[str] = []
        for commit in commits:
            for filepath in commit.get("added", []) + commit.get("modified", []):
                if filepath.endswith(".py"):
                    changed_py_files.append(filepath)
        # 여러 커밋에서 동일 파일이 중복될 수 있으므로 중복 제거
        changed_py_files = list(set(changed_py_files))

        # Python 파일 변경이 없으면 스캔 불필요
        if not changed_py_files:
            return None

        # 이미 진행 중인 스캔이 있으면 중복 방지
        if await self.orchestrator.has_active_scan(repo.id):
            return None

        job_id = await self.orchestrator.enqueue_scan(
            repo_id=repo.id,
            trigger="webhook",
            commit_sha=commit_sha,
            branch=pushed_branch,
            scan_type="incremental",
            changed_files=changed_py_files,
        )
        return job_id

    async def handle_pull_request(self, payload: dict, action: str) -> str | None:
        """pull_request 이벤트를 처리한다 (opened / synchronize).

        PR 변경 파일 중 Python 파일이 있으면 스캔 큐에 등록한다.
        synchronize 이벤트는 기존 PR 스캔을 취소하고 새로 등록한다.

        Args:
            payload: GitHub pull_request 이벤트 페이로드
            action: PR 액션 (opened / synchronize)

        Returns:
            등록된 ScanJob ID, 스캔 불필요 시 None
        """
        repo_info = payload.get("repository", {})
        github_repo_id: int = repo_info.get("id", 0)
        full_name: str = repo_info.get("full_name", "")

        pr_info = payload.get("pull_request", {})
        pr_number: int = pr_info.get("number", 0)
        head_info = pr_info.get("head", {})
        commit_sha: str = head_info.get("sha", "")
        head_ref: str = head_info.get("ref", "")

        installation_info = payload.get("installation", {})
        installation_id: int = installation_info.get("id", 0)

        # 저장소가 등록되지 않았으면 무시
        repo = await self._get_active_repo_by_github_id(github_repo_id)
        if repo is None:
            return None

        # GitHub API로 PR 변경 파일 조회 후 Python 파일 필터링
        all_changed_files = await self.github_service.get_pr_changed_files(
            full_name=full_name,
            installation_id=installation_id,
            pr_number=pr_number,
        )
        changed_py_files = [f for f in all_changed_files if f.endswith(".py")]

        # Python 파일 변경 없으면 스캔 불필요
        if not changed_py_files:
            return None

        # synchronize 이벤트: 동일 PR의 기존 스캔 취소 후 새로 등록
        if action == "synchronize":
            await self.orchestrator.cancel_active_scans_for_pr(
                repo_id=repo.id,
                pr_number=pr_number,
            )

        job_id = await self.orchestrator.enqueue_scan(
            repo_id=repo.id,
            trigger="webhook",
            commit_sha=commit_sha,
            branch=head_ref,
            pr_number=pr_number,
            scan_type="pr",
            changed_files=changed_py_files,
        )
        return job_id

    async def handle_installation_created(self, payload: dict) -> list[str]:
        """installation.created 이벤트를 처리한다 (GitHub App 설치).

        설치된 저장소를 DB에 등록하고 초기 스캔을 큐에 등록한다.

        Args:
            payload: GitHub installation.created 이벤트 페이로드

        Returns:
            등록/업데이트된 repo_id 목록
        """
        installation_info = payload.get("installation", {})
        installation_id: int = installation_info.get("id", 0)
        repositories: list[dict] = payload.get("repositories", [])

        repo_ids: list[str] = []

        for repo_data in repositories:
            github_repo_id: int = repo_data.get("id", 0)
            full_name: str = repo_data.get("full_name", "")

            # 이미 등록된 저장소인지 확인
            existing = await self._get_active_repo_by_github_id(github_repo_id)
            if existing is not None:
                # 이미 존재하면 installation_id 업데이트
                existing.installation_id = installation_id
                existing.is_active = True
                existing.is_initial_scan_done = False
                repo = existing
            else:
                # 없으면 새로 생성
                # 실제 구현에서는 sender.id -> User -> TeamMember -> Team 경로로 팀 조회
                # PoC에서는 임시 팀 ID 사용
                repo = Repository(
                    github_repo_id=github_repo_id,
                    full_name=full_name,
                    default_branch="main",
                    is_active=True,
                    installation_id=installation_id,
                    is_initial_scan_done=False,
                    team_id=uuid.uuid4(),
                )
                self.db.add(repo)
                await self.db.flush()

            repo_ids.append(str(repo.id))

            # 초기 스캔 큐 등록
            await self.orchestrator.enqueue_scan(
                repo_id=repo.id,
                trigger="webhook",
                scan_type="initial",
                changed_files=None,
            )

        return repo_ids

    async def _get_active_repo_by_platform_id(
        self, platform: str, platform_repo_id: str
    ) -> Repository | None:
        """platform + platform_repo_id로 활성화된 저장소를 조회한다."""
        result = await self.db.execute(
            select(Repository).where(
                Repository.platform == platform,
                Repository.platform_repo_id == platform_repo_id,
                Repository.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def handle_gitlab_push(self, payload: dict) -> str | None:
        """GitLab Push Hook 이벤트를 처리한다.

        기본 브랜치에 Python 파일이 포함된 push만 스캔 큐에 등록한다.

        Args:
            payload: GitLab Push Hook 페이로드

        Returns:
            등록된 ScanJob ID, 스캔 불필요 시 None
        """
        ref: str = payload.get("ref", "")
        pushed_branch = ref.replace("refs/heads/", "")

        project_info = payload.get("project", {})
        platform_repo_id = str(project_info.get("id", ""))
        default_branch: str = project_info.get("default_branch", "main")
        commit_sha: str = payload.get("checkout_sha", "")

        # 기본 브랜치가 아닌 push는 무시
        if pushed_branch != default_branch:
            return None

        # 저장소가 등록되지 않았으면 무시
        repo = await self._get_active_repo_by_platform_id("gitlab", platform_repo_id)
        if repo is None:
            return None

        # commits에서 Python 파일 추출 (added + modified, removed 제외)
        commits: list[dict] = payload.get("commits", [])
        changed_py_files: list[str] = []
        for commit in commits:
            for filepath in commit.get("added", []) + commit.get("modified", []):
                if filepath.endswith(".py"):
                    changed_py_files.append(filepath)
        changed_py_files = list(set(changed_py_files))

        # Python 파일 변경이 없으면 스캔 불필요
        if not changed_py_files:
            return None

        # 이미 진행 중인 스캔이 있으면 중복 방지
        if await self.orchestrator.has_active_scan(repo.id):
            return None

        job_id = await self.orchestrator.enqueue_scan(
            repo_id=repo.id,
            trigger="webhook",
            commit_sha=commit_sha,
            branch=pushed_branch,
            scan_type="incremental",
            changed_files=changed_py_files,
        )
        return job_id

    async def handle_gitlab_mr(self, payload: dict) -> str | None:
        """GitLab Merge Request Hook 이벤트를 처리한다.

        MR 변경 파일 중 Python 파일이 있으면 스캔 큐에 등록한다.

        Args:
            payload: GitLab Merge Request Hook 페이로드

        Returns:
            등록된 ScanJob ID, 스캔 불필요 시 None
        """
        project_info = payload.get("project", {})
        platform_repo_id = str(project_info.get("id", ""))

        mr_attrs = payload.get("object_attributes", {})
        action: str = mr_attrs.get("action", "")
        mr_iid: int = mr_attrs.get("iid", 0)
        source_branch: str = mr_attrs.get("source_branch", "")

        # open 또는 update 액션만 처리
        if action not in ("open", "update", "reopen"):
            return None

        # 저장소가 등록되지 않았으면 무시
        repo = await self._get_active_repo_by_platform_id("gitlab", platform_repo_id)
        if repo is None:
            return None

        job_id = await self.orchestrator.enqueue_scan(
            repo_id=repo.id,
            trigger="webhook",
            branch=source_branch,
            pr_number=mr_iid,
            scan_type="pr",
            changed_files=None,
        )
        return job_id

    async def handle_bitbucket_push(self, payload: dict) -> str | None:
        """Bitbucket repo:push 이벤트를 처리한다.

        기본 브랜치에 push된 경우 스캔 큐에 등록한다.

        Args:
            payload: Bitbucket repo:push 페이로드

        Returns:
            등록된 ScanJob ID, 스캔 불필요 시 None
        """
        repo_info = payload.get("repository", {})
        full_name: str = repo_info.get("full_name", "")
        mainbranch_info = repo_info.get("mainbranch") or {}
        default_branch: str = mainbranch_info.get("name", "main")

        # 저장소가 등록되지 않았으면 무시
        repo = await self._get_active_repo_by_platform_id("bitbucket", full_name)
        if repo is None:
            return None

        # push.changes에서 브랜치와 커밋 추출
        changes: list[dict] = payload.get("push", {}).get("changes", [])
        commit_sha = ""
        pushed_branch = ""

        for change in changes:
            new_info = change.get("new") or {}
            if new_info.get("type") == "branch":
                pushed_branch = new_info.get("name", "")
                commits = change.get("commits", [])
                if commits:
                    commit_sha = commits[0].get("hash", "")
                break

        # 기본 브랜치가 아닌 push는 무시
        if pushed_branch != default_branch:
            return None

        job_id = await self.orchestrator.enqueue_scan(
            repo_id=repo.id,
            trigger="webhook",
            commit_sha=commit_sha,
            branch=pushed_branch,
            scan_type="incremental",
            changed_files=None,
        )
        return job_id

    async def handle_bitbucket_pr(self, payload: dict) -> str | None:
        """Bitbucket pullrequest:created / pullrequest:updated 이벤트를 처리한다.

        Args:
            payload: Bitbucket pullrequest 페이로드

        Returns:
            등록된 ScanJob ID, 스캔 불필요 시 None
        """
        repo_info = payload.get("repository", {})
        full_name: str = repo_info.get("full_name", "")

        pr_info = payload.get("pullrequest", {})
        pr_id: int = pr_info.get("id", 0)
        source_branch: str = pr_info.get("source", {}).get("branch", {}).get("name", "")

        # 저장소가 등록되지 않았으면 무시
        repo = await self._get_active_repo_by_platform_id("bitbucket", full_name)
        if repo is None:
            return None

        job_id = await self.orchestrator.enqueue_scan(
            repo_id=repo.id,
            trigger="webhook",
            branch=source_branch,
            pr_number=pr_id,
            scan_type="pr",
            changed_files=None,
        )
        return job_id

    async def handle_installation_deleted(self, payload: dict) -> list[str]:
        """installation.deleted 이벤트를 처리한다 (GitHub App 삭제).

        해당 installation의 저장소를 비활성화하고
        진행 중인 스캔을 취소한다. 실제 데이터는 삭제하지 않는다.

        Args:
            payload: GitHub installation.deleted 이벤트 페이로드

        Returns:
            비활성화된 repo_id 목록
        """
        installation_info = payload.get("installation", {})
        installation_id: int = installation_info.get("id", 0)

        # installation_id로 모든 저장소 조회
        result = await self.db.execute(
            select(Repository).where(
                Repository.installation_id == installation_id,
            )
        )
        repos = result.scalars().all()

        deactivated_ids: list[str] = []

        for repo in repos:
            repo.is_active = False
            repo.installation_id = None

            # 진행 중인 스캔 모두 취소
            await self.db.execute(
                sql_update(ScanJob)
                .where(
                    ScanJob.repo_id == repo.id,
                    ScanJob.status.in_(["queued", "running"]),
                )
                .values(status="cancelled")
            )

            deactivated_ids.append(str(repo.id))

        return deactivated_ids
