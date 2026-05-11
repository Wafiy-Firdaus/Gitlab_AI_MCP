#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# shellcheck source=scripts/_common.sh
source "${SCRIPT_DIR}/_common.sh"

echo ""
bold "GitLab AI MCP Server — Status"
echo "==============================="
echo ""

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------
DOCKER_COMPOSE=""
if ! DOCKER_COMPOSE=$(detect_docker_compose); then
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
  CID=$($DOCKER_COMPOSE ps -q gitlab-ai-mcp 2>/dev/null | head -n1)

  if [ -n "$CID" ]; then
    STATE=$(docker inspect --format='{{.State.Status}}' "$CID" 2>/dev/null || echo "unknown")
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$CID" 2>/dev/null || echo "N/A")
    STARTED=$(docker inspect --format='{{.State.StartedAt}}' "$CID" 2>/dev/null || echo "?")

    if [ "$STATE" = "running" ]; then
      ok "gitlab-ai-mcp is running"
      info "Started: ${STARTED}"
      if [ "$HEALTH" != "N/A" ]; then
        info "Health: ${HEALTH}"
      fi
    else
      warn "gitlab-ai-mcp is ${STATE}"
      info "Start it: ${DOCKER_COMPOSE} up -d"
    fi
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
elif env_is_placeholder "$ENV_FILE" "GITLAB_URL" "https://gitlab.example.com" || env_is_placeholder "$ENV_FILE" "GITLAB_TOKEN" "glpat-your-token"; then
  warn ".env contains placeholder values"
else
  ok ".env configured"
  GITLAB_URL=$(env_get "$ENV_FILE" "GITLAB_URL")
  info "GitLab URL: ${GITLAB_URL}"
fi

# ---------------------------------------------------------------------------
# GitLab connectivity
# ---------------------------------------------------------------------------
echo ""
bold "GitLab Connectivity"
echo "-------------------"

if [ -f "$ENV_FILE" ] && ! env_is_placeholder "$ENV_FILE" "GITLAB_URL" "https://gitlab.example.com" && ! env_is_placeholder "$ENV_FILE" "GITLAB_TOKEN" "glpat-your-token"; then
  GITLAB_URL=$(env_get "$ENV_FILE" "GITLAB_URL")
  GITLAB_TOKEN=$(env_get "$ENV_FILE" "GITLAB_TOKEN")

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
