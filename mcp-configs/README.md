# Global MCP Config Templates

This directory contains ready-to-use **global MCP configuration templates** for every supported AI CLI.

> **Why global configs?**  
> The `.claude/settings.local.json` in the repo root is **not** MCP config — it's just local bash permissions for Claude Code when you happen to be inside this project directory.  
> If you want the GitLab MCP server available in **every project**, you need a **global/user-level** config.

---

## Quick Setup (CLI commands)

The easiest way to register globally is via your AI CLI's built-in command:

```bash
# Get the absolute path to the launcher
MCP_PATH="$(cd "$(dirname "$0")/.." && pwd)/scripts/run_mcp.sh"

# Kimi
kimi mcp add --transport stdio gitlab-ai-mcp -- "$MCP_PATH"

# Claude
claude mcp add --scope user gitlab-ai-mcp -- "$MCP_PATH"

# Codex
codex mcp add gitlab-ai-mcp -- "$MCP_PATH"

# Gemini
gemini mcp add gitlab-ai-mcp -- "$MCP_PATH"
```

---

## Manual Setup (config files)

If you prefer to edit config files directly, copy and adapt the templates below.

### 1. Replace the placeholder path

Every template contains:

```
/ABSOLUTE/PATH/TO/Gitlab_AI_MCP/scripts/run_mcp.sh
```

Replace it with the real absolute path on your machine, e.g.:

```
/home/wafiy/Gitlab_AI_MCP/scripts/run_mcp.sh
```

> **WSL2:** always use the Linux path (`/home/...`), not the Windows path (`\\wsl$\...`).

---

### Kimi Code CLI

| Item | Value |
|------|-------|
| **File** | `~/.kimi/mcp.json` |
| **Format** | JSON |
| **Template** | [`kimi.global.json`](./kimi.global.json) |

```bash
mkdir -p ~/.kimi
# If ~/.kimi/mcp.json already exists, merge the mcpServers block into it.
# If it does NOT exist, you can copy directly:
cp mcp-configs/kimi.global.json ~/.kimi/mcp.json
# edit ~/.kimi/mcp.json and fix the command path
```

---

### Claude Code

| Item | Value |
|------|-------|
| **File** | `~/.claude/settings.json` **or** `~/.mcp.json` |
| **Format** | JSON |
| **Template** | [`claude.global.json`](./claude.global.json) |

Claude Code supports two global locations:

1. **`~/.claude/settings.json`** — user settings (merge `mcpServers` into existing JSON)
2. **`~/.mcp.json`** — newer standalone shared MCP config

```bash
# Option A — ~/.claude/settings.json (merge into existing settings!)
mkdir -p ~/.claude
# WARNING: only copy if the file does NOT already exist.
# If it exists, manually add the "mcpServers" block from the template.
cp mcp-configs/claude.global.json ~/.claude/settings.json

# Option B — ~/.mcp.json (standalone shared config, safer)
cp mcp-configs/claude.global.json ~/.mcp.json

# edit and fix the command path
```

---

### Codex CLI

| Item | Value |
|------|-------|
| **File** | `~/.codex/config.toml` |
| **Format** | TOML |
| **Template** | [`codex.global.toml`](./codex.global.toml) |

```bash
mkdir -p ~/.codex
# WARNING: only copy if the file does NOT already exist.
# If ~/.codex/config.toml already exists, append the [mcp_servers.gitlab-ai-mcp]
# block from the template rather than overwriting.
cp mcp-configs/codex.global.toml ~/.codex/config.toml
# edit ~/.codex/config.toml and fix the command path
```

---

### Gemini CLI

| Item | Value |
|------|-------|
| **File** | `~/.gemini/settings.json` |
| **Format** | JSON |
| **Template** | [`gemini.global.json`](./gemini.global.json) |

```bash
mkdir -p ~/.gemini
# WARNING: only copy if the file does NOT already exist.
# If it exists, merge the "mcpServers" block from the template into it.
cp mcp-configs/gemini.global.json ~/.gemini/settings.json
# edit ~/.gemini/settings.json and fix the command path
```

---

## Verifying the connection

After configuring, open any project (not just `Gitlab_AI_MCP`) and run your AI CLI's MCP list command:

| CLI | Command |
|-----|---------|
| Kimi | `/mcp` inside the shell, or `kimi mcp list` |
| Claude | `/mcp` inside the shell, or `claude mcp list` |
| Codex | `codex mcp list` |
| Gemini | `/mcp` inside the shell, or `gemini mcp list` |

You should see `gitlab-ai-mcp` listed.
