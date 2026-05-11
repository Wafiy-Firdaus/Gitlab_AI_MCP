#!/usr/bin/env bash
set -euo pipefail

# One-liner installer for GitLab AI MCP Server.
# Usage: curl -fsSL https://raw.githubusercontent.com/Wafiy-Firdaus/Gitlab_AI_MCP/main/scripts/quick-install.sh | bash

INSTALL_DIR="${HOME}/.gitlab-ai-mcp"
REPO_URL="https://github.com/Wafiy-Firdaus/Gitlab_AI_MCP.git"

echo "GitLab AI MCP Server — Quick Install"
echo "===================================="
echo ""

# ---------------------------------------------------------------------------
# Prerequisites check
# ---------------------------------------------------------------------------
if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git is required but not installed." >&2
  echo "  Install git: https://git-scm.com/downloads" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is required but not installed." >&2
  echo "  Install curl via your package manager." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Clone or update
# ---------------------------------------------------------------------------
if [ -d "$INSTALL_DIR" ]; then
  echo "Directory already exists: $INSTALL_DIR"
  echo "Updating to latest version..."
  cd "$INSTALL_DIR"
  if ! git pull --ff-only 2>&1; then
    echo "ERROR: git pull failed. You may have local changes in ${INSTALL_DIR}." >&2
    echo "  Resolve conflicts manually, then re-run this installer." >&2
    exit 1
  fi
else
  echo "Cloning into $INSTALL_DIR..."
  if ! git clone "$REPO_URL" "$INSTALL_DIR" 2>&1; then
    echo "ERROR: git clone failed." >&2
    echo "  Check your internet connection and that you can reach GitHub." >&2
    exit 1
  fi
  cd "$INSTALL_DIR"
fi

echo ""
exec ./scripts/install.sh "$@"
