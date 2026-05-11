#!/usr/bin/env bash
# Shared helpers for GitLab AI MCP installation scripts.
# Source this file: source "$(dirname "$0")/_common.sh"

set -euo pipefail

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ---------------------------------------------------------------------------
# Docker Compose detection (v1 / v2 compatible)
# ---------------------------------------------------------------------------
detect_docker_compose() {
    if command -v docker >/dev/null 2>&1; then
        if docker compose version >/dev/null 2>&1; then
            echo "docker compose"
            return 0
        fi
    fi
    if command -v docker-compose >/dev/null 2>&1; then
        echo "docker-compose"
        return 0
    fi
    return 1
}

# ---------------------------------------------------------------------------
# Container status (works with both Compose v1 and v2)
# ---------------------------------------------------------------------------
container_is_running() {
    local dc="$1" service="$2"
    local cid
    cid=$($dc ps -q "$service" 2>/dev/null | head -n1)
    [ -n "$cid" ] && [ "$(docker inspect --format='{{.State.Running}}' "$cid" 2>/dev/null)" = "true" ]
}

# ---------------------------------------------------------------------------
# .env helpers
# ---------------------------------------------------------------------------
env_get() {
    local file="$1" key="$2"
    grep "^${key}=" "$file" 2>/dev/null | tail -n1 | cut -d= -f2- \
        | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' \
              -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}

env_has_key() {
    local file="$1" key="$2"
    grep -q "^${key}=" "$file" 2>/dev/null
}

env_set() {
    local file="$1" key="$2" value="$3"
    if grep -q "^${key}=" "$file" 2>/dev/null; then
        # Update existing line (cross-platform sed)
        sed -i.bak "s|^${key}=.*|${key}=${value}|" "$file" && rm -f "${file}.bak"
    else
        echo "${key}=${value}" >> "$file"
    fi
}

env_is_placeholder() {
    local file="$1" key="$2" placeholder="$3"
    local val
    val=$(env_get "$file" "$key")
    [ "$val" = "$placeholder" ]
}

# ---------------------------------------------------------------------------
# URL normalizer
# ---------------------------------------------------------------------------
normalize_url() {
    local url="$1"
    # Trim whitespace
    url=$(echo "$url" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
    # Remove trailing slash(es)
    while [[ "$url" == */ ]]; do
        url="${url%/}"
    done
    # Add https:// if no scheme
    if [[ ! "$url" =~ ^https?:// ]]; then
        url="https://${url}"
    fi
    echo "$url"
}

# ---------------------------------------------------------------------------
# Colors / formatting
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
