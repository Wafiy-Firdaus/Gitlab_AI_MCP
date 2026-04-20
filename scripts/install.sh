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
# Parse arguments
# ---------------------------------------------------------------------------
ARG_GITLAB_URL=""
ARG_GITLAB_TOKEN=""
NON_INTERACTIVE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --gitlab-url)
      ARG_GITLAB_URL="$2"
      shift 2
      ;;
    --gitlab-token)
      ARG_GITLAB_TOKEN="$2"
      shift 2
      ;;
    --non-interactive)
      NON_INTERACTIVE=true
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --gitlab-url <url>      Set GitLab instance URL"
      echo "  --gitlab-token <token>  Set GitLab Personal Access Token"
      echo "  --non-interactive       Fail instead of prompting for missing values"
      echo "  -h, --help              Show this help"
      echo ""
      echo "Examples:"
      echo "  $0                      # Interactive mode"
      echo "  $0 --gitlab-url https://gitlab.example.com --gitlab-token glpat-xxx"
      exit 0
      ;;
    *)
      err "Unknown option: $1"
      echo "Run '$0 --help' for usage."
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
echo ""
bold "GitLab AI MCP Server — Installer"
echo "=================================="
echo ""

# ---------------------------------------------------------------------------
# 1. Docker / Docker Compose check
# ---------------------------------------------------------------------------
info "Checking prerequisites..."

DOCKER_COMPOSE=""
if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
  fi
fi

if [ -z "${DOCKER_COMPOSE}" ]; then
  err "Docker Compose is required but not found."
  echo "   Install Docker: https://docs.docker.com/get-docker/"
  exit 1
fi

# Verify daemon is actually running
if ! docker info >/dev/null 2>&1; then
  err "Docker daemon is not running."
  echo "   Start Docker Desktop or run: sudo service docker start"
  exit 1
fi

ok "Docker Compose found (${DOCKER_COMPOSE}) and daemon is running"

# ---------------------------------------------------------------------------
# 2. .env setup (interactive or flags)
# ---------------------------------------------------------------------------
info "Checking environment configuration..."

ENV_FILE="${PROJECT_ROOT}/.env"
ENV_NEEDS_WRITE=false

# Create .env from example if missing
if [ ! -f "$ENV_FILE" ]; then
  if [ -f "${PROJECT_ROOT}/.env.example" ]; then
    cp "${PROJECT_ROOT}/.env.example" "$ENV_FILE"
    ENV_NEEDS_WRITE=true
  else
    err ".env.example not found. Cannot create .env."
    exit 1
  fi
fi

# Check if current .env has placeholders
has_placeholders() {
  grep -qE '^(GITLAB_URL=https://gitlab\.example\.com|GITLAB_TOKEN=glpat-your-token)[[:space:]]*$' "$ENV_FILE"
}

if has_placeholders; then
  ENV_NEEDS_WRITE=true
fi

# Write .env if needed
if $ENV_NEEDS_WRITE; then
  GITLAB_URL=""
  GITLAB_TOKEN=""

  # Use CLI arguments if provided
  if [ -n "$ARG_GITLAB_URL" ]; then
    GITLAB_URL="$ARG_GITLAB_URL"
  fi
  if [ -n "$ARG_GITLAB_TOKEN" ]; then
    GITLAB_TOKEN="$ARG_GITLAB_TOKEN"
  fi

  # Prompt interactively for anything still missing
  if [ -z "$GITLAB_URL" ] || [ -z "$GITLAB_TOKEN" ]; then
    if $NON_INTERACTIVE; then
      err ".env is missing or contains placeholder values."
      echo "   Provide values via flags:"
      echo "     $0 --gitlab-url <url> --gitlab-token <token>"
      exit 1
    fi

    echo ""
    bold "GitLab Credentials Required"
    echo "---------------------------"
    echo "Create a token at: GitLab → User Settings → Access Tokens → Add new token"
    echo "(scope: api)"
    echo ""

    if [ -z "$GITLAB_URL" ]; then
      read -rp "GitLab instance URL [https://gitlab.example.com]: " GITLAB_URL
      GITLAB_URL="${GITLAB_URL:-https://gitlab.example.com}"
    fi

    if [ -z "$GITLAB_TOKEN" ]; then
      read -rsp "GitLab Personal Access Token: " GITLAB_TOKEN
      echo ""
    fi
  fi

  # Validate inputs
  if [ -z "$GITLAB_URL" ] || [ "$GITLAB_URL" = "https://gitlab.example.com" ]; then
    err "A real GitLab URL is required."
    exit 1
  fi
  if [ -z "$GITLAB_TOKEN" ] || [ "$GITLAB_TOKEN" = "glpat-your-token" ]; then
    err "A real GitLab token is required."
    exit 1
  fi

  # Write .env
  cat > "$ENV_FILE" << EOF
GITLAB_URL=${GITLAB_URL}
GITLAB_TOKEN=${GITLAB_TOKEN}
DEBUG=false
LOCAL_AI_URL=http://ollama:11434
LOCAL_AI_MODEL=llama3.1:8b
EOF

  ok ".env configured"
else
  ok ".env already configured"
fi

# ---------------------------------------------------------------------------
# 2b. Validate token against GitLab
# ---------------------------------------------------------------------------
GITLAB_URL=$(grep "^GITLAB_URL=" "$ENV_FILE" | cut -d= -f2-)
GITLAB_TOKEN=$(grep "^GITLAB_TOKEN=" "$ENV_FILE" | cut -d= -f2-)

info "Verifying GitLab credentials..."

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "PRIVATE-TOKEN: ${GITLAB_TOKEN}" "${GITLAB_URL}/api/v4/user" 2>/dev/null || true)
[ -z "$HTTP_CODE" ] && HTTP_CODE="000"

if [ "$HTTP_CODE" = "200" ]; then
  ok "GitLab API reachable (token is valid)"
elif [ "$HTTP_CODE" = "401" ]; then
  err "GitLab returned 401 Unauthorized — your token is invalid or expired."
  echo "   Create a new token at: ${GITLAB_URL}/-/profile/personal_access_tokens"
  exit 1
elif [ "$HTTP_CODE" = "000" ]; then
  err "Cannot reach GitLab at ${GITLAB_URL}"
  echo "   Check the URL and your network connection."
  exit 1
else
  warn "GitLab returned HTTP ${HTTP_CODE} — continuing anyway"
fi

# ---------------------------------------------------------------------------
# 3. Build & start container
# ---------------------------------------------------------------------------
cd "${PROJECT_ROOT}"

container_running() {
  [ -n "$(${DOCKER_COMPOSE} ps --status running --quiet gitlab-ai-mcp 2>/dev/null)" ]
}

if container_running; then
  info "Container already running — skipping build."
else
  info "Building and starting container..."

  if ! ${DOCKER_COMPOSE} up -d --build gitlab-ai-mcp 2>&1; then
    err "Container failed to start."
    echo "   Check the logs:"
    echo "     cd ${PROJECT_ROOT}"
    echo "     ${DOCKER_COMPOSE} logs gitlab-ai-mcp"
    exit 1
  fi

  # Wait briefly for container to be ready
  sleep 3
fi

if ! container_running; then
  err "Container is not running after start."
  echo "   Check the logs:"
  echo "     cd ${PROJECT_ROOT}"
  echo "     ${DOCKER_COMPOSE} logs gitlab-ai-mcp"
  exit 1
fi

ok "Container 'gitlab-ai-mcp' is running"

# ---------------------------------------------------------------------------
# 4. Smoke test
# ---------------------------------------------------------------------------
info "Running smoke test..."

if ! ${DOCKER_COMPOSE} exec -T gitlab-ai-mcp python run_tests.py >/dev/null 2>&1; then
  warn "Smoke test had warnings (this is usually OK if GitLab is unreachable)."
else
  ok "Smoke test passed"
fi

# ---------------------------------------------------------------------------
# 5. Detect & register with AI CLIs
# ---------------------------------------------------------------------------
info "Detecting AI CLIs..."

MCP_PATH="${PROJECT_ROOT}/scripts/run_mcp.sh"
REGISTERED=()
FAILED=()

register_kimi() {
  if command -v kimi >/dev/null 2>&1; then
    info "Registering with Kimi Code CLI..."
    if kimi mcp add --transport stdio gitlab-ai-mcp -- "$MCP_PATH" 2>/dev/null; then
      ok "Registered with Kimi"
      REGISTERED+=("Kimi")
    else
      warn "Could not auto-register with Kimi (may already be registered)"
      FAILED+=("Kimi")
    fi
  fi
}

register_claude() {
  if command -v claude >/dev/null 2>&1; then
    info "Registering with Claude Code..."
    if claude mcp add --scope user gitlab-ai-mcp -- "$MCP_PATH" 2>/dev/null; then
      ok "Registered with Claude Code"
      REGISTERED+=("Claude Code")
    else
      warn "Could not auto-register with Claude Code (may already be registered)"
      FAILED+=("Claude Code")
    fi
  fi
}

register_codex() {
  if command -v codex >/dev/null 2>&1; then
    info "Registering with Codex CLI..."
    if codex mcp add gitlab-ai-mcp -- "$MCP_PATH" 2>/dev/null; then
      ok "Registered with Codex"
      REGISTERED+=("Codex")
    else
      warn "Could not auto-register with Codex (may already be registered)"
      FAILED+=("Codex")
    fi
  fi
}

register_gemini() {
  if command -v gemini >/dev/null 2>&1; then
    info "Registering with Gemini CLI..."
    if gemini mcp add gitlab-ai-mcp -- "$MCP_PATH" 2>/dev/null; then
      ok "Registered with Gemini"
      REGISTERED+=("Gemini")
    else
      warn "Could not auto-register with Gemini (may already be registered)"
      FAILED+=("Gemini")
    fi
  fi
}

register_kimi
register_claude
register_codex
register_gemini

# ---------------------------------------------------------------------------
# 6. Summary
# ---------------------------------------------------------------------------
echo ""
bold "Installation Summary"
echo "===================="
echo ""

if [ ${#REGISTERED[@]} -gt 0 ]; then
  ok "Successfully registered with: ${REGISTERED[*]}"
fi

if [ ${#FAILED[@]} -gt 0 ]; then
  warn "Could not auto-register with: ${FAILED[*]}"
  echo "   If these are newly installed, you may need to restart your shell first."
fi

DETECTED_COUNT=$((${#REGISTERED[@]} + ${#FAILED[@]}))
if [ "$DETECTED_COUNT" -eq 0 ]; then
  warn "No AI CLIs detected on this system."
  echo ""
  echo "   When you install one, register manually:"
  echo "     <cli> mcp add gitlab-ai-mcp -- ${MCP_PATH}"
  echo ""
  echo "   Or re-run this installer after installing your AI CLI."
fi

echo ""
info "Project directory: ${PROJECT_ROOT}"
info "Launcher script:   ${MCP_PATH}"
echo ""
echo "   Do NOT move or delete this directory — the global MCP configs"
echo "   contain absolute paths pointing to it."
echo ""
echo "   To uninstall later, run:"
echo "     ${PROJECT_ROOT}/scripts/uninstall.sh"
echo ""

if [ ${#REGISTERED[@]} -gt 0 ]; then
  bold "Next step: open any project in your AI CLI and run /mcp (or <cli> mcp list)"
  echo ""
fi
