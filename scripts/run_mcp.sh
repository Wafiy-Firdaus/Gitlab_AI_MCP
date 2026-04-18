#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is required to run Gitlab_AI_MCP. Install Docker from https://docs.docker.com/get-docker/" >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo "ERROR: .env file not found." >&2
  echo "  Run: cp .env.example .env" >&2
  echo "  Then set GITLAB_URL and GITLAB_TOKEN in .env" >&2
  exit 1
fi

# docker compose ps --status exits 0 even when no container matches; check output instead
if [ -z "$(docker compose ps --status running --quiet gitlab-ai-mcp 2>/dev/null)" ]; then
  echo "ERROR: Gitlab_AI_MCP container is not running." >&2
  echo "  Start it with: docker compose up -d --build" >&2
  exit 1
fi

exec docker compose exec -T gitlab-ai-mcp python server.py
