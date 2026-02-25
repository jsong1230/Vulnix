#!/usr/bin/env bash
# SessionStart 훅: compact/resume 시 프로젝트 상태를 stdout으로 출력하여 컨텍스트 복구

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

echo "=== 프로젝트 상태 복구 ==="
echo ""

# 환경변수 파일 안내
if [ -n "$CLAUDE_ENV_FILE" ] && [ -f "$CLAUDE_ENV_FILE" ]; then
  echo "📋 환경변수 파일: $CLAUDE_ENV_FILE"
  echo ""
fi

# 마지막 저장된 파이프라인 상태
if [ -f "$PROJECT_DIR/.claude/.pipeline-state" ]; then
  echo "## 마지막 파이프라인 상태 (compact 이전)"
  cat "$PROJECT_DIR/.claude/.pipeline-state"
  echo ""
fi

# 진행중인 기능
echo "## 진행중인 기능"
if [ -f "$PROJECT_DIR/docs/project/features.md" ]; then
  ACTIVE=$(grep "🔄 진행중" "$PROJECT_DIR/docs/project/features.md" 2>/dev/null | head -5)
  if [ -n "$ACTIVE" ]; then
    echo "$ACTIVE"
  else
    echo "  없음"
  fi
else
  echo "  features.md 없음 — /init-project 먼저 실행하세요"
fi
echo ""

# 진행중 태스크 [→]
echo "## 진행중 태스크 [→]"
ACTIVE_TASKS=$(grep -r '\[→\]' "$PROJECT_DIR/docs/specs/"*/plan.md 2>/dev/null | head -10)
if [ -n "$ACTIVE_TASKS" ]; then
  echo "$ACTIVE_TASKS"
else
  echo "  없음"
fi
echo ""

# Git 상태
echo "## Git 상태"
GIT_STATUS=$(cd "$PROJECT_DIR" && git status --short 2>/dev/null | head -10)
if [ -n "$GIT_STATUS" ]; then
  echo "$GIT_STATUS"
else
  echo "  변경사항 없음"
fi
echo ""

# 최근 커밋
echo "## 최근 커밋 (5개)"
cd "$PROJECT_DIR" && git log --oneline -5 2>/dev/null || echo "  커밋 없음"
