#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# shellcheck source=scripts/_common.sh
source "${SCRIPT_DIR}/_common.sh"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
ARG_GITLAB_URL=""
NON_INTERACTIVE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --gitlab-url)
      ARG_GITLAB_URL="$2"
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
      echo "  --non-interactive       Fail instead of prompting for missing values"
      echo "  -h, --help              Show this help"
      echo ""
      echo "Examples:"
      echo "  $0                      # Interactive mode"
      echo "  $0 --gitlab-url https://gitlab.example.com"
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
if ! DOCKER_COMPOSE=$(detect_docker_compose); then
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
    (umask 077 && cp "${PROJECT_ROOT}/.env.example" "$ENV_FILE")
    ENV_NEEDS_WRITE=true
  else
    err ".env.example not found. Cannot create .env."
    exit 1
  fi
fi

# Determine whether we need to write .env
HAS_PLACEHOLDERS=false
if env_is_placeholder "$ENV_FILE" "GITLAB_URL" "https://gitlab.example.com"; then
  HAS_PLACEHOLDERS=true
fi
if env_is_placeholder "$ENV_FILE" "GITLAB_TOKEN" "glpat-your-token"; then
  HAS_PLACEHOLDERS=true
fi

# If the user explicitly passed a URL, always update it.
FLAGS_PROVIDED=false
if [ -n "$ARG_GITLAB_URL" ]; then
  FLAGS_PROVIDED=true
fi

if $HAS_PLACEHOLDERS || $FLAGS_PROVIDED; then
  GITLAB_URL=""
  GITLAB_TOKEN=""

  # Use CLI arguments if provided
  if [ -n "$ARG_GITLAB_URL" ]; then
    GITLAB_URL="$ARG_GITLAB_URL"
  fi
  # Prompt interactively for anything still missing
  if [ -z "$GITLAB_URL" ] || [ -z "$GITLAB_TOKEN" ]; then
    if $NON_INTERACTIVE; then
      err ".env is missing or contains placeholder values."
      echo "   Provide --gitlab-url and enter the token when prompted."
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
  GITLAB_URL=$(normalize_url "$GITLAB_URL")
  if [ -z "$GITLAB_URL" ] || [ "$GITLAB_URL" = "https://gitlab.example.com" ]; then
    err "A real GitLab URL is required."
    exit 1
  fi
  if [ -z "$GITLAB_TOKEN" ] || [ "$GITLAB_TOKEN" = "glpat-your-token" ]; then
    err "A real GitLab token is required."
    exit 1
  fi

  # Write / update .env safely (preserve existing keys, add missing ones)
  env_set "$ENV_FILE" "GITLAB_URL"  "$GITLAB_URL"
  env_set "$ENV_FILE" "GITLAB_TOKEN" "$GITLAB_TOKEN"
  env_set "$ENV_FILE" "DEBUG" "false"
  env_set "$ENV_FILE" "LOCAL_AI_URL" "http://ollama:11434"
  env_set "$ENV_FILE" "LOCAL_AI_MODEL" "llama3.1:8b"

  ok ".env configured"
else
  ok ".env already configured"
fi

chmod 600 "$ENV_FILE"

# ---------------------------------------------------------------------------
# 2b. Validate token against GitLab
# ---------------------------------------------------------------------------
GITLAB_URL=$(env_get "$ENV_FILE" "GITLAB_URL")
GITLAB_TOKEN=$(env_get "$ENV_FILE" "GITLAB_TOKEN")

info "Verifying GitLab credentials..."

HTTP_CODE=$(printf 'PRIVATE-TOKEN: %s\n' "$GITLAB_TOKEN" | curl -s -o /dev/null -w "%{http_code}" -H @- "${GITLAB_URL}/api/v4/user" 2>/dev/null || true)
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

if container_is_running "$DOCKER_COMPOSE" "gitlab-ai-mcp"; then
  info "Container already running — skipping build."
else
  info "Building and starting container..."

  if ! $DOCKER_COMPOSE up -d --build gitlab-ai-mcp 2>&1; then
    err "Container failed to start."
    echo "   Check the logs:"
    echo "     cd ${PROJECT_ROOT}"
    echo "     ${DOCKER_COMPOSE} logs gitlab-ai-mcp"
    exit 1
  fi

  # Wait briefly for container to be ready
  sleep 3
fi

if ! container_is_running "$DOCKER_COMPOSE" "gitlab-ai-mcp"; then
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

SMOKE_OUTPUT=""
if SMOKE_OUTPUT=$($DOCKER_COMPOSE exec -T gitlab-ai-mcp python run_tests.py 2>&1); then
  ok "Smoke test passed"
else
  warn "Smoke test failed"
  echo ""
  echo "$SMOKE_OUTPUT"
  echo ""
  echo "   This usually means a code or dependency issue inside the container."
  echo "   Check the logs: ${DOCKER_COMPOSE} logs gitlab-ai-mcp"
  exit 1
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
    local out
    if out=$(kimi mcp add --transport stdio gitlab-ai-mcp -- "$MCP_PATH" 2>&1); then
      ok "Registered with Kimi"
      REGISTERED+=("Kimi")
    else
      warn "Could not register with Kimi"
      echo "   Error: $out" >&2
      FAILED+=("Kimi")
    fi
  fi
}

register_claude() {
  if command -v claude >/dev/null 2>&1; then
    info "Registering with Claude Code..."
    local out
    if out=$(claude mcp add --scope user gitlab-ai-mcp -- "$MCP_PATH" 2>&1); then
      ok "Registered with Claude Code"
      REGISTERED+=("Claude Code")
    else
      warn "Could not register with Claude Code"
      echo "   Error: $out" >&2
      FAILED+=("Claude Code")
    fi
  fi
}

register_codex() {
  if command -v codex >/dev/null 2>&1; then
    info "Registering with Codex CLI..."
    local out
    if out=$(codex mcp add gitlab-ai-mcp -- "$MCP_PATH" 2>&1); then
      ok "Registered with Codex"
      REGISTERED+=("Codex")
    else
      warn "Could not register with Codex"
      echo "   Error: $out" >&2
      FAILED+=("Codex")
    fi
  fi
}

register_gemini() {
  if command -v gemini >/dev/null 2>&1; then
    info "Registering with Gemini CLI..."
    local out
    if out=$(gemini mcp add gitlab-ai-mcp -- "$MCP_PATH" 2>&1); then
      ok "Registered with Gemini"
      REGISTERED+=("Gemini")
    else
      warn "Could not register with Gemini"
      echo "   Error: $out" >&2
      FAILED+=("Gemini")
    fi
  fi
}

register_reasonix() {
  if command -v reasonix >/dev/null 2>&1; then
    info "Reasonix detected."
    local REASONIX_CONFIG="${HOME}/.reasonix/config.json"
    local TEMPLATE="${PROJECT_ROOT}/mcp-configs/reasonix.global.json"

    if [ -f "$REASONIX_CONFIG" ]; then
      info "Reasonix config found at ${REASONIX_CONFIG}"

      if command -v jq >/dev/null 2>&1; then
        # Use jq to add/update the gitlab-ai-mcp entry with the real path
        local tmp_config="${REASONIX_CONFIG}.tmp.$$"
        if jq --arg cmd "${MCP_PATH}" \
               '.mcpServers."gitlab-ai-mcp" = {"command": $cmd, "args": []}' \
               "$REASONIX_CONFIG" > "$tmp_config" 2>/dev/null; then
          mv "$tmp_config" "$REASONIX_CONFIG"
          ok "Registered with Reasonix"
          REGISTERED+=("Reasonix")
        else
          rm -f "$tmp_config"
          warn "Failed to update Reasonix config — merge manually below"
          echo "     \"gitlab-ai-mcp\": {"
          echo "       \"command\": \"${MCP_PATH}\","
          echo "       \"args\": []"
          echo "     }"
          FAILED+=("Reasonix")
        fi
      else
        info "jq not found — printing manual registration instructions"
        echo "   To register, add this to the \"mcpServers\" block in ${REASONIX_CONFIG}:"
        echo ""
        echo "     \"gitlab-ai-mcp\": {"
        echo "       \"command\": \"${MCP_PATH}\","
        echo "       \"args\": []"
        echo "     }"
        echo ""
        echo "   Or copy the template and merge manually:"
        echo "     cat ${TEMPLATE}"
        REGISTERED+=("Reasonix (manual)")
      fi
    else
      warn "Reasonix config not found at ${REASONIX_CONFIG}"
      info "Creating from template with real path..."
      mkdir -p "${HOME}/.reasonix"
      sed "s|/ABSOLUTE/PATH/TO/Gitlab_AI_MCP|${PROJECT_ROOT}|g" \
        "$TEMPLATE" > "$REASONIX_CONFIG"
      ok "Created Reasonix config at ${REASONIX_CONFIG}"
      REGISTERED+=("Reasonix")
    fi
  fi
}

register_kimi
register_claude
register_codex
register_gemini
register_reasonix

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
  warn "Could not register with: ${FAILED[*]}"
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
