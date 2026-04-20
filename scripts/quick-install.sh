#!/usr/bin/env bash
set -euo pipefail

# One-liner installer for GitLab AI MCP Server.
# Usage: curl -fsSL https://raw.githubusercontent.com/Wafiy-Firdaus/Gitlab_AI_MCP/main/scripts/quick-install.sh | bash

INSTALL_DIR="${HOME}/.gitlab-ai-mcp"
REPO_URL="https://github.com/Wafiy-Firdaus/Gitlab_AI_MCP.git"

echo "GitLab AI MCP Server — Quick Install"
echo "===================================="
echo ""

if [ -d "$INSTALL_DIR" ]; then
  echo "Directory already exists: $INSTALL_DIR"
  echo "Updating to latest version..."
  cd "$INSTALL_DIR"
  git pull --ff-only
else
  echo "Cloning into $INSTALL_DIR..."
  git clone "$REPO_URL" "$INSTALL_DIR"
  cd "$INSTALL_DIR"
fi

echo ""
exec ./scripts/install.sh "$@"
