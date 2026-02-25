"""알림 메시지 포맷터 — Slack Block Kit / Teams Adaptive Cards 형식 생성"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.vulnerability import Vulnerability


# 심각도별 색상 코드 (Slack attachment color 또는 Teams themeColor)
SEVERITY_COLORS: dict[str, str] = {
    "critical": "#D00000",  # 빨간색
    "high": "#FF6B00",      # 주황색
    "medium": "#FFD600",    # 노란색
    "low": "#00C853",       # 초록색
}

# 심각도 이모지 (Block Kit 텍스트용)
_SEVERITY_EMOJI: dict[str, str] = {
    "critical": ":red_circle:",
    "high": ":orange_circle:",
    "medium": ":yellow_circle:",
    "low": ":green_circle:",
}

# Slack danger/warning/good 레이블 매핑
_SLACK_COLOR_LABEL: dict[str, str] = {
    "critical": "danger",
    "high": "warning",
    "medium": "#FFD600",
    "low": "good",
}


class SlackFormatter:
    """Slack Block Kit 포맷터.

    취약점 알림 및 주간 리포트를 Slack Block Kit JSON으로 변환한다.
    """

    def format_vulnerability_alert(
        self,
        vuln: "Vulnerability",
        repo_name: str,
        patch_pr_url: str | None = None,
    ) -> dict:
        """취약점 발견 알림을 Slack Block Kit 형식으로 포맷한다.

        Args:
            vuln: 취약점 모델 인스턴스
            repo_name: 저장소 전체 이름 (예: test-org/test-repo)
            patch_pr_url: 자동 생성된 패치 PR URL (없으면 None)

        Returns:
            Slack API에 전송할 payload dict
        """
        severity = (vuln.severity or "unknown").lower()
        color = _SLACK_COLOR_LABEL.get(severity, "#888888")
        emoji = _SEVERITY_EMOJI.get(severity, ":white_circle:")

        title = f"{emoji} [{severity.upper()}] 보안 취약점 발견 — {repo_name}"
        description = (
            f"*유형:* {vuln.vulnerability_type}\n"
            f"*파일:* `{vuln.file_path}` (L{vuln.start_line})\n"
            f"*CWE:* {vuln.cwe_id or 'N/A'}\n"
            f"*설명:* {vuln.description or '설명 없음'}"
        )

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"[{severity.upper()}] 보안 취약점 발견",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"{emoji} *{repo_name}* 저장소에서 취약점이 발견되었습니다.\n\n"
                        f"*심각도:* {severity.upper()}\n"
                        f"*유형:* {vuln.vulnerability_type}\n"
                        f"*파일:* `{vuln.file_path}` (Line {vuln.start_line})\n"
                        f"*CWE:* {vuln.cwe_id or 'N/A'}"
                    ),
                },
            },
        ]

        # 설명 블록 추가
        if vuln.description:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*설명:*\n{vuln.description}",
                    },
                }
            )

        # 패치 PR 링크 블록 추가
        if patch_pr_url:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*자동 패치 PR:* <{patch_pr_url}|패치 PR 바로가기>",
                    },
                }
            )

        blocks.append({"type": "divider"})

        return {
            "attachments": [
                {
                    "color": color,
                    "blocks": blocks,
                    "fallback": title,
                }
            ],
            "blocks": blocks,
        }


class TeamsFormatter:
    """Teams Adaptive Cards 포맷터.

    취약점 알림 및 주간 리포트를 Teams Adaptive Cards JSON으로 변환한다.
    """

    def format_vulnerability_alert(
        self,
        vuln: "Vulnerability",
        repo_name: str,
        patch_pr_url: str | None = None,
    ) -> dict:
        """취약점 발견 알림을 Teams Adaptive Cards 형식으로 포맷한다.

        Args:
            vuln: 취약점 모델 인스턴스
            repo_name: 저장소 전체 이름
            patch_pr_url: 자동 생성된 패치 PR URL (없으면 None)

        Returns:
            Teams webhook API에 전송할 payload dict
        """
        severity = (vuln.severity or "unknown").lower()
        color = SEVERITY_COLORS.get(severity, "#888888")

        body = [
            {
                "type": "TextBlock",
                "size": "Large",
                "weight": "Bolder",
                "text": f"[{severity.upper()}] 보안 취약점 발견",
                "color": _teams_color(severity),
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "저장소", "value": repo_name},
                    {"title": "심각도", "value": severity.upper()},
                    {"title": "유형", "value": vuln.vulnerability_type},
                    {"title": "파일", "value": f"{vuln.file_path} (L{vuln.start_line})"},
                    {"title": "CWE", "value": vuln.cwe_id or "N/A"},
                ],
            },
        ]

        if vuln.description:
            body.append(
                {
                    "type": "TextBlock",
                    "text": vuln.description,
                    "wrap": True,
                }
            )

        actions = []
        if patch_pr_url:
            actions.append(
                {
                    "type": "Action.OpenUrl",
                    "title": "패치 PR 바로가기",
                    "url": patch_pr_url,
                }
            )

        adaptive_card = {
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": body,
            "actions": actions,
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "msteams": {
                "themeColor": color,
            },
        }

        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "contentUrl": None,
                    "content": adaptive_card,
                }
            ],
        }


def _teams_color(severity: str) -> str:
    """Teams Adaptive Card TextBlock 색상 이름 반환"""
    mapping = {
        "critical": "Attention",
        "high": "Warning",
        "medium": "Warning",
        "low": "Good",
    }
    return mapping.get(severity, "Default")


def format_weekly_report(stats: dict, platform: str) -> dict:
    """주간 보안 리포트를 플랫폼에 맞는 형식으로 포맷한다.

    Args:
        stats: 주간 통계 딕셔너리
            - total_new: 신규 취약점 수
            - critical_count: critical 건수
            - high_count: high 건수
            - medium_count: medium 건수
            - low_count: low 건수
            - patched_count: 패치 완료 건수
            - open_count: 미해결 건수
            - week_start: 주 시작일 (YYYY-MM-DD)
            - week_end: 주 종료일 (YYYY-MM-DD)
        platform: "slack" 또는 "teams"

    Returns:
        플랫폼별 webhook payload dict
    """
    total_new = stats.get("total_new", 0)
    critical = stats.get("critical_count", 0)
    high = stats.get("high_count", 0)
    medium = stats.get("medium_count", 0)
    low = stats.get("low_count", 0)
    patched = stats.get("patched_count", 0)
    open_count = stats.get("open_count", 0)
    week_start = stats.get("week_start", "")
    week_end = stats.get("week_end", "")

    if platform == "slack":
        return _format_weekly_slack(
            total_new=total_new,
            critical=critical,
            high=high,
            medium=medium,
            low=low,
            patched=patched,
            open_count=open_count,
            week_start=week_start,
            week_end=week_end,
        )
    else:
        return _format_weekly_teams(
            total_new=total_new,
            critical=critical,
            high=high,
            medium=medium,
            low=low,
            patched=patched,
            open_count=open_count,
            week_start=week_start,
            week_end=week_end,
        )


def _format_weekly_slack(
    total_new: int,
    critical: int,
    high: int,
    medium: int,
    low: int,
    patched: int,
    open_count: int,
    week_start: str,
    week_end: str,
) -> dict:
    """Slack 주간 리포트 payload 생성"""
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"주간 보안 리포트 ({week_start} ~ {week_end})",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*신규 취약점:* {total_new}건\n\n"
                    f":red_circle: Critical: {critical}건\n"
                    f":orange_circle: High: {high}건\n"
                    f":yellow_circle: Medium: {medium}건\n"
                    f":green_circle: Low: {low}건"
                ),
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*패치 완료:* {patched}건"},
                {"type": "mrkdwn", "text": f"*미해결:* {open_count}건"},
            ],
        },
        {"type": "divider"},
    ]

    return {"blocks": blocks}


def _format_weekly_teams(
    total_new: int,
    critical: int,
    high: int,
    medium: int,
    low: int,
    patched: int,
    open_count: int,
    week_start: str,
    week_end: str,
) -> dict:
    """Teams 주간 리포트 payload 생성"""
    adaptive_card = {
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "size": "Large",
                "weight": "Bolder",
                "text": f"주간 보안 리포트 ({week_start} ~ {week_end})",
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "신규 취약점", "value": f"{total_new}건"},
                    {"title": "Critical", "value": f"{critical}건"},
                    {"title": "High", "value": f"{high}건"},
                    {"title": "Medium", "value": f"{medium}건"},
                    {"title": "Low", "value": f"{low}건"},
                    {"title": "패치 완료", "value": f"{patched}건"},
                    {"title": "미해결", "value": f"{open_count}건"},
                ],
            },
        ],
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
    }

    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": adaptive_card,
            }
        ],
    }
