#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

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
  echo "ERROR: Docker Compose is required but not found." >&2
  exit 1
fi

cd "${PROJECT_ROOT}"

# ---------------------------------------------------------------------------
# Show logs
# ---------------------------------------------------------------------------
exec ${DOCKER_COMPOSE} logs -f --tail=100 gitlab-ai-mcp "$@"
