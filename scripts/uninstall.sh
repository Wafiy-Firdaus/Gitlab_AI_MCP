#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# shellcheck source=scripts/_common.sh
source "${SCRIPT_DIR}/_common.sh"

echo ""
bold "GitLab AI MCP Server — Uninstaller"
echo "===================================="
echo ""

# ---------------------------------------------------------------------------
# 1. Docker / Docker Compose check
# ---------------------------------------------------------------------------
DOCKER_COMPOSE=""
if ! DOCKER_COMPOSE=$(detect_docker_compose); then
  warn "Docker Compose not found — skipping container removal"
fi

# ---------------------------------------------------------------------------
# 2. Stop & remove container
# ---------------------------------------------------------------------------
if [ -n "${DOCKER_COMPOSE}" ] && [ -f "${PROJECT_ROOT}/docker-compose.yml" ]; then
  info "Stopping and removing container..."
  cd "${PROJECT_ROOT}"
  if $DOCKER_COMPOSE down --remove-orphans 2>/dev/null; then
    ok "Container stopped and removed"
  else
    warn "Could not stop container (it may not be running)"
  fi
else
  warn "Docker Compose not found — skipping container removal"
fi

# ---------------------------------------------------------------------------
# 3. Remove MCP registrations
# ---------------------------------------------------------------------------
info "Removing MCP registrations..."

REMOVED=()
MISSING=()

remove_kimi() {
  if command -v kimi >/dev/null 2>&1; then
    if kimi mcp remove gitlab-ai-mcp 2>/dev/null; then
      ok "Removed from Kimi"
      REMOVED+=("Kimi")
    else
      MISSING+=("Kimi")
    fi
  fi
}

remove_claude() {
  if command -v claude >/dev/null 2>&1; then
    if claude mcp remove gitlab-ai-mcp 2>/dev/null; then
      ok "Removed from Claude Code"
      REMOVED+=("Claude Code")
    else
      MISSING+=("Claude Code")
    fi
  fi
}

remove_codex() {
  if command -v codex >/dev/null 2>&1; then
    if codex mcp remove gitlab-ai-mcp 2>/dev/null; then
      ok "Removed from Codex"
      REMOVED+=("Codex")
    else
      MISSING+=("Codex")
    fi
  fi
}

remove_gemini() {
  if command -v gemini >/dev/null 2>&1; then
    if gemini mcp remove gitlab-ai-mcp 2>/dev/null; then
      ok "Removed from Gemini"
      REMOVED+=("Gemini")
    else
      MISSING+=("Gemini")
    fi
  fi
}

remove_kimi
remove_claude
remove_codex
remove_gemini

# ---------------------------------------------------------------------------
# 4. Summary
# ---------------------------------------------------------------------------
echo ""
bold "Uninstall Summary"
echo "================="
echo ""

if [ ${#REMOVED[@]} -gt 0 ]; then
  ok "Removed from: ${REMOVED[*]}"
fi

if [ ${#MISSING[@]} -gt 0 ]; then
  warn "Was not registered with (or already removed): ${MISSING[*]}"
fi

TOTAL=$((${#REMOVED[@]} + ${#MISSING[@]}))
if [ "$TOTAL" -eq 0 ]; then
  warn "No AI CLIs detected — nothing to unregister"
fi

echo ""
info "To completely remove the project, you can now delete:"
echo "   ${PROJECT_ROOT}"
echo ""
