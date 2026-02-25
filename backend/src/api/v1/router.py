"""API v1 라우터 — 모든 엔드포인트 라우터를 통합한다"""

from fastapi import APIRouter

from src.api.v1 import (
    auth,
    dashboard,
    false_positives,
    ide,
    notifications,
    patches,
    repos,
    repos_bitbucket,
    repos_gitlab,
    reports,
    scans,
    vulns,
    webhooks,
    webhooks_bitbucket,
    webhooks_gitlab,
)

api_router = APIRouter()

# GitHub Webhook (인증 없음 — HMAC-SHA256 서명 검증)
api_router.include_router(
    webhooks.router,
    prefix="/webhooks",
    tags=["webhooks"],
)

# GitLab Webhook (인증 없음 — X-Gitlab-Token 검증, F-09)
api_router.include_router(
    webhooks_gitlab.router,
    prefix="/webhooks",
    tags=["webhooks"],
)

# Bitbucket Webhook (인증 없음 — X-Hub-Signature HMAC-SHA256 검증, F-09)
api_router.include_router(
    webhooks_bitbucket.router,
    prefix="/webhooks",
    tags=["webhooks"],
)

# 인증
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["auth"],
)

# 스캔
api_router.include_router(
    scans.router,
    prefix="/scans",
    tags=["scans"],
)

# 저장소 (GitHub)
api_router.include_router(
    repos.router,
    prefix="/repos",
    tags=["repos"],
)

# GitLab 저장소 연동 (F-09)
api_router.include_router(
    repos_gitlab.router,
    prefix="/repos/gitlab",
    tags=["repos", "gitlab"],
)

# Bitbucket 저장소 연동 (F-09)
api_router.include_router(
    repos_bitbucket.router,
    prefix="/repos/bitbucket",
    tags=["repos", "bitbucket"],
)

# 취약점
api_router.include_router(
    vulns.router,
    prefix="/vulnerabilities",
    tags=["vulnerabilities"],
)

# 패치 PR
api_router.include_router(
    patches.router,
    prefix="/patches",
    tags=["patches"],
)

# 대시보드
api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["dashboard"],
)

# 오탐 패턴 관리
api_router.include_router(
    false_positives.router,
    prefix="/false-positives",
    tags=["false-positives"],
)

# 알림 설정 (Slack/Teams)
api_router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["notifications"],
)

# 리포트 (CISO/CSAP/ISO27001/ISMS, F-10)
api_router.include_router(
    reports.router,
    prefix="/reports",
    tags=["reports"],
)

# IDE 플러그인 (F-11) — analyze, false-positive-patterns, patch-suggestion, api-keys
api_router.include_router(
    ide.router,
    prefix="/ide",
    tags=["ide"],
)
