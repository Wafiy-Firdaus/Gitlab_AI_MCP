#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required to run Gitlab_AI_MCP" >&2
  exit 1
fi

if ! docker compose ps --status running gitlab-ai-mcp >/dev/null 2>&1; then
  echo "Gitlab_AI_MCP container is not running. Start it with: docker compose up -d --build" >&2
  exit 1
fi

exec docker compose exec -T gitlab-ai-mcp python server.py
