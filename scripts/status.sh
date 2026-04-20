#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

ok()    { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC} $*"; }
err()   { echo -e "${RED}✗${NC} $*"; }
info()  { echo -e "${BLUE}ℹ${NC} $*"; }
bold()  { echo -e "${BOLD}$*${NC}"; }

echo ""
bold "GitLab AI MCP Server — Status"
echo "==============================="
echo ""

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------
DOCKER_COMPOSE=""
if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
  fi
fi

if [ -z "${DOCKER_COMPOSE}" ]; then
  err "Docker Compose not found"
else
  ok "Docker Compose: ${DOCKER_COMPOSE}"
fi

if ! docker info >/dev/null 2>&1; then
  err "Docker daemon is not running"
else
  ok "Docker daemon running"
fi

# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------
echo ""
bold "Container"
echo "---------"

if [ -n "${DOCKER_COMPOSE}" ]; then
  cd "${PROJECT_ROOT}"
  STATUS=$(${DOCKER_COMPOSE} ps --format json gitlab-ai-mcp 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('State','unknown') if isinstance(d,dict) else 'unknown')" 2>/dev/null || echo "unknown")

  if [ "$STATUS" = "running" ]; then
    ok "gitlab-ai-mcp is running"
    UPTIME=$(${DOCKER_COMPOSE} ps --format json gitlab-ai-mcp 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Health','').replace('Up ','') if isinstance(d,dict) else '?')" 2>/dev/null || echo "?")
    info "Status: ${STATUS}"
  else
    warn "gitlab-ai-mcp is NOT running"
    info "Start it: ${DOCKER_COMPOSE} up -d"
  fi
else
  err "Cannot check container status (Docker unavailable)"
fi

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
echo ""
bold "Environment"
echo "-----------"

ENV_FILE="${PROJECT_ROOT}/.env"
if [ ! -f "$ENV_FILE" ]; then
  err ".env not found"
  info "Run: cp .env.example .env"
elif grep -qE '^(GITLAB_URL=https://gitlab\.example\.com|GITLAB_TOKEN=glpat-your-token)[[:space:]]*$' "$ENV_FILE"; then
  warn ".env contains placeholder values"
else
  ok ".env configured"
  GITLAB_URL=$(grep "^GITLAB_URL=" "$ENV_FILE" | cut -d= -f2-)
  info "GitLab URL: ${GITLAB_URL}"
fi

# ---------------------------------------------------------------------------
# GitLab connectivity
# ---------------------------------------------------------------------------
echo ""
bold "GitLab Connectivity"
echo "-------------------"

if [ -f "$ENV_FILE" ] && ! grep -qE '^(GITLAB_URL=https://gitlab\.example\.com|GITLAB_TOKEN=glpat-your-token)[[:space:]]*$' "$ENV_FILE"; then
  GITLAB_URL=$(grep "^GITLAB_URL=" "$ENV_FILE" | cut -d= -f2-)
  GITLAB_TOKEN=$(grep "^GITLAB_TOKEN=" "$ENV_FILE" | cut -d= -f2-)

  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "PRIVATE-TOKEN: ${GITLAB_TOKEN}" "${GITLAB_URL}/api/v4/user" 2>/dev/null || true)
  [ -z "$HTTP_CODE" ] && HTTP_CODE="000"

  if [ "$HTTP_CODE" = "200" ]; then
    ok "GitLab API reachable (HTTP 200)"
  elif [ "$HTTP_CODE" = "401" ]; then
    warn "GitLab API returned 401 — token may be invalid or expired"
  elif [ "$HTTP_CODE" = "000" ]; then
    err "Cannot reach GitLab — check URL and network"
  else
    warn "GitLab API returned HTTP ${HTTP_CODE}"
  fi
else
  info "Skipped (credentials not configured)"
fi

# ---------------------------------------------------------------------------
# AI CLI Registrations
# ---------------------------------------------------------------------------
echo ""
bold "AI CLI Registrations"
echo "--------------------"

check_config() {
  local name="$1"
  local file="$2"
  local pattern="$3"

  if [ -f "$file" ]; then
    if grep -q "$pattern" "$file" 2>/dev/null; then
      ok "${name}: registered"
    else
      info "${name}: not registered"
    fi
  else
    info "${name}: config file not found (${file})"
  fi
}

check_config "Kimi"     "${HOME}/.kimi/mcp.json"        "gitlab-ai-mcp"
check_config "Claude"   "${HOME}/.claude/settings.json" "gitlab-ai-mcp"
check_config "Claude"   "${HOME}/.mcp.json"             "gitlab-ai-mcp"
check_config "Codex"    "${HOME}/.codex/config.toml"    "gitlab-ai-mcp"
check_config "Gemini"   "${HOME}/.gemini/settings.json" "gitlab-ai-mcp"

echo ""
