#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

# ---------------------------------------------------------------------------
# Docker / Docker Compose detection
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
  echo "ERROR: Docker Compose is required to run Gitlab_AI_MCP." >&2
  echo "  Install Docker from https://docs.docker.com/get-docker/" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Environment check
# ---------------------------------------------------------------------------
if [ ! -f .env ]; then
  echo "ERROR: .env file not found in ${PROJECT_ROOT}." >&2
  echo "  Run: cp .env.example .env" >&2
  echo "  Then set GITLAB_URL and GITLAB_TOKEN in .env" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Container health check + auto-start
# ---------------------------------------------------------------------------
container_running() {
  [ -n "$(${DOCKER_COMPOSE} ps --status running --quiet gitlab-ai-mcp 2>/dev/null)" ]
}

if ! container_running; then
  echo "INFO: Gitlab_AI_MCP container is not running. Attempting to start..." >&2

  # Try a quick start first (assumes image already built)
  if ${DOCKER_COMPOSE} up -d gitlab-ai-mcp 2>/dev/null; then
    sleep 2
  fi

  # Re-check
  if ! container_running; then
    echo "ERROR: Container failed to start (image may need building)." >&2
    echo "  Build and start with:" >&2
    echo "    cd ${PROJECT_ROOT}" >&2
    echo "    ${DOCKER_COMPOSE} up -d --build" >&2
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Run MCP server inside container
# ---------------------------------------------------------------------------
exec ${DOCKER_COMPOSE} exec -T gitlab-ai-mcp python server.py
