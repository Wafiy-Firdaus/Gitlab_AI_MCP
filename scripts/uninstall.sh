#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${BLUE}ℹ${NC}  $*"; }
ok()    { echo -e "${GREEN}✓${NC}  $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
err()   { echo -e "${RED}✗${NC}  $*" >&2; }
bold()  { echo -e "${BOLD}$*${NC}"; }

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
echo ""
bold "GitLab AI MCP Server — Uninstaller"
echo "===================================="
echo ""

# ---------------------------------------------------------------------------
# 1. Docker / Docker Compose check
# ---------------------------------------------------------------------------
DOCKER_COMPOSE=""
if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
  fi
fi

# ---------------------------------------------------------------------------
# 2. Stop & remove container
# ---------------------------------------------------------------------------
if [ -n "${DOCKER_COMPOSE}" ] && [ -f "${PROJECT_ROOT}/docker-compose.yml" ]; then
  info "Stopping and removing container..."
  cd "${PROJECT_ROOT}"
  if ${DOCKER_COMPOSE} down --remove-orphans 2>/dev/null; then
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
