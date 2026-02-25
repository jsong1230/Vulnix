"""SQLAlchemy 모델 패키지 — Alembic이 모든 모델을 인식할 수 있도록 일괄 import"""

from src.models.api_key import ApiKey
from src.models.base import Base
from src.models.notification import NotificationConfig, NotificationLog
from src.models.patch_pr import PatchPR
from src.models.report_config import ReportConfig
from src.models.report_history import ReportHistory
from src.models.repository import Repository
from src.models.scan_job import ScanJob
from src.models.team import Team, TeamMember
from src.models.user import User
from src.models.vulnerability import Vulnerability

__all__ = [
    "ApiKey",
    "Base",
    "User",
    "Team",
    "TeamMember",
    "Repository",
    "ScanJob",
    "Vulnerability",
    "PatchPR",
    "NotificationConfig",
    "NotificationLog",
    "ReportConfig",
    "ReportHistory",
]
