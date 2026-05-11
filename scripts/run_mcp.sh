#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# shellcheck source=scripts/_common.sh
source "${SCRIPT_DIR}/_common.sh"

cd "${PROJECT_ROOT}"

# ---------------------------------------------------------------------------
# Docker / Docker Compose detection
# ---------------------------------------------------------------------------
DOCKER_COMPOSE=""
if ! DOCKER_COMPOSE=$(detect_docker_compose); then
  err "Docker Compose is required to run Gitlab_AI_MCP." >&2
  echo "  Install Docker from https://docs.docker.com/get-docker/" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Environment check
# ---------------------------------------------------------------------------
if [ ! -f .env ]; then
  err ".env file not found in ${PROJECT_ROOT}." >&2
  echo "  Run: cp .env.example .env" >&2
  echo "  Then set GITLAB_URL and GITLAB_TOKEN in .env" >&2
  exit 1
fi

# Validate .env has real values
MISSING_VARS=()
if ! env_has_key .env "GITLAB_URL" || env_is_placeholder .env "GITLAB_URL" "https://gitlab.example.com"; then
  MISSING_VARS+=("GITLAB_URL")
fi
if ! env_has_key .env "GITLAB_TOKEN" || env_is_placeholder .env "GITLAB_TOKEN" "glpat-your-token"; then
  MISSING_VARS+=("GITLAB_TOKEN")
fi

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
  err ".env is missing or has placeholder values for: ${MISSING_VARS[*]}" >&2
  echo "  Edit ${PROJECT_ROOT}/.env and set real values." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Container health check + auto-start
# ---------------------------------------------------------------------------
if container_is_running "$DOCKER_COMPOSE" "gitlab-ai-mcp"; then
  : # Container is running — proceed to exec
else
  info "Gitlab_AI_MCP container is not running. Attempting to start..." >&2

  # Try a quick start first (assumes image already built)
  if $DOCKER_COMPOSE up -d gitlab-ai-mcp 2>/dev/null; then
    sleep 2
  fi

  # Re-check
  if ! container_is_running "$DOCKER_COMPOSE" "gitlab-ai-mcp"; then
    info "Quick start failed — building image..." >&2

    if ! $DOCKER_COMPOSE up -d --build gitlab-ai-mcp 2>&1; then
      err "Container failed to start." >&2
      echo "  Build log:" >&2
      $DOCKER_COMPOSE logs gitlab-ai-mcp >&2 || true
      exit 1
    fi

    sleep 2
  fi

  if ! container_is_running "$DOCKER_COMPOSE" "gitlab-ai-mcp"; then
    err "Container is still not running after build." >&2
    echo "  Check logs: ${DOCKER_COMPOSE} logs gitlab-ai-mcp" >&2
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Run MCP server inside container
# ---------------------------------------------------------------------------
exec $DOCKER_COMPOSE exec -T gitlab-ai-mcp python server.py
