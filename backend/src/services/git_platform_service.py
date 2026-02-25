"""Git 플랫폼 공통 추상 인터페이스 (Strategy Pattern)

GitHub / GitLab / Bitbucket 구현체가 이 계약을 따른다.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class GitPlatformService(ABC):
    """Git 플랫폼 공통 인터페이스.

    각 플랫폼 구현체(GitHubPlatformService, GitLabPlatformService,
    BitbucketPlatformService)가 반드시 구현해야 한다.
    """

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """자격증명 유효성 검증 (API 호출 테스트).

        Returns:
            유효하면 True, 그렇지 않으면 False
        """

    @abstractmethod
    async def list_repositories(self, **kwargs) -> list[dict]:
        """접근 가능한 저장소 목록 조회.

        Returns:
            저장소 정보 딕셔너리 목록
            각 항목: {platform_repo_id, full_name, private, default_branch, language, platform_url}
        """

    @abstractmethod
    async def clone_repository(
        self, full_name: str, commit_sha: str, target_dir: Path
    ) -> None:
        """저장소 클론.

        Args:
            full_name: 저장소 전체 이름 (예: group/repo)
            commit_sha: 클론할 커밋 SHA
            target_dir: 대상 디렉토리
        """

    @abstractmethod
    async def get_changed_files(
        self, full_name: str, mr_or_pr_number: int
    ) -> list[str]:
        """MR/PR 변경 파일 목록 조회.

        Args:
            full_name: 저장소 전체 이름
            mr_or_pr_number: MR(GitLab) 또는 PR(GitHub/Bitbucket) 번호

        Returns:
            변경 파일 경로 목록
        """

    @abstractmethod
    async def get_default_branch_sha(
        self, full_name: str, branch: str
    ) -> str:
        """브랜치 최신 커밋 SHA 조회.

        Args:
            full_name: 저장소 전체 이름
            branch: 브랜치 이름

        Returns:
            최신 커밋 SHA 문자열
        """

    @abstractmethod
    async def create_branch(
        self, full_name: str, branch_name: str, base_sha: str
    ) -> None:
        """새 브랜치 생성.

        Args:
            full_name: 저장소 전체 이름
            branch_name: 생성할 브랜치 이름
            base_sha: 브랜치를 생성할 기준 커밋 SHA
        """

    @abstractmethod
    async def get_file_content(
        self, full_name: str, file_path: str, ref: str
    ) -> tuple[str, str]:
        """파일 내용 + blob SHA 조회.

        Args:
            full_name: 저장소 전체 이름
            file_path: 조회할 파일 경로
            ref: 브랜치 이름 또는 커밋 SHA

        Returns:
            (decoded_content, blob_sha) 튜플
        """

    @abstractmethod
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

        Args:
            full_name: 저장소 전체 이름
            branch_name: 커밋할 브랜치
            file_path: 수정할 파일 경로
            content: 파일 새 내용
            message: 커밋 메시지
            file_sha: 기존 파일의 blob SHA (업데이트 충돌 방지)

        Returns:
            커밋 결과 딕셔너리
        """

    @abstractmethod
    async def create_merge_request(
        self,
        full_name: str,
        head: str,
        base: str,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> dict:
        """MR/PR 생성.

        Args:
            full_name: 저장소 전체 이름
            head: 소스 브랜치 이름
            base: 대상 브랜치 이름
            title: MR/PR 제목
            body: MR/PR 본문 설명
            labels: 레이블 목록 (선택)

        Returns:
            {"number": int, "html_url": str} 형식의 딕셔너리
        """

    @abstractmethod
    async def register_webhook(
        self,
        full_name: str,
        webhook_url: str,
        secret: str,
        events: list[str],
    ) -> None:
        """Webhook 등록.

        Args:
            full_name: 저장소 전체 이름
            webhook_url: Webhook 수신 URL
            secret: Webhook 서명 검증용 시크릿
            events: 구독할 이벤트 목록
        """
