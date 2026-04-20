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

info()  { echo -e "${BLUE}ℹ${NC}  $*"; }
ok()    { echo -e "${GREEN}✓${NC}  $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
err()   { echo -e "${RED}✗${NC}  $*" >&2; }
bold()  { echo -e "${BOLD}$*${NC}"; }

echo ""
bold "GitLab AI MCP Server — Updater"
echo "================================"
echo ""

cd "${PROJECT_ROOT}"

# ---------------------------------------------------------------------------
# Validate git repo
# ---------------------------------------------------------------------------
if [ ! -d .git ]; then
  err "This directory is not a git repository. Cannot update."
  exit 1
fi

# ---------------------------------------------------------------------------
# Fetch latest
# ---------------------------------------------------------------------------
info "Fetching latest changes..."

OLD_COMMIT=$(git rev-parse HEAD)

if ! git fetch origin main 2>/dev/null; then
  err "Failed to fetch from origin."
  exit 1
fi

NEW_COMMIT=$(git rev-parse origin/main)

if [ "$OLD_COMMIT" = "$NEW_COMMIT" ]; then
  ok "Already on the latest version."
  exit 0
fi

warn "Update available: $(git log --oneline -1 "$OLD_COMMIT") → $(git log --oneline -1 "$NEW_COMMIT")"
echo ""

# Show changelog summary
COMMITS_BEHIND=$(git rev-list --count HEAD..origin/main)
echo "   ${COMMITS_BEHIND} new commit(s):"
git log --oneline --no-decorate HEAD..origin/main | sed 's/^/     - /'
echo ""

read -rp "Proceed with update? [Y/n]: " CONFIRM
CONFIRM="${CONFIRM:-Y}"

if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
  info "Update cancelled."
  exit 0
fi

# ---------------------------------------------------------------------------
# Backup .env
# ---------------------------------------------------------------------------
if [ -f .env ]; then
  cp .env .env.backup
  ok ".env backed up to .env.backup"
fi

# ---------------------------------------------------------------------------
# Pull and rebuild
# ---------------------------------------------------------------------------
info "Pulling latest code..."

if ! git pull --ff-only origin main; then
  err "git pull failed. You may have local changes."
  echo "   Resolve conflicts manually, then re-run this updater."
  exit 1
fi

ok "Code updated"

# ---------------------------------------------------------------------------
# Docker rebuild
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
  err "Docker Compose not found. Cannot rebuild container."
  exit 1
fi

info "Rebuilding container..."

if ! ${DOCKER_COMPOSE} up -d --build gitlab-ai-mcp 2>&1; then
  err "Container rebuild failed."
  echo "   Check logs: ${DOCKER_COMPOSE} logs gitlab-ai-mcp"
  exit 1
fi

sleep 2

if [ -n "$(${DOCKER_COMPOSE} ps --status running --quiet gitlab-ai-mcp 2>/dev/null)" ]; then
  ok "Container rebuilt and running"
else
  err "Container is not running after rebuild."
  exit 1
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
bold "Update Complete"
echo "==============="
ok "Updated to: $(git log --oneline -1)"

if [ -f .env.backup ]; then
  info ".env backup kept at: ${PROJECT_ROOT}/.env.backup"
  echo "   Delete it when you're confident the update is stable:"
  echo "     rm ${PROJECT_ROOT}/.env.backup"
fi

echo ""
