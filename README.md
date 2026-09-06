# GitLab AI MCP Server

A high-performance, containerized [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that connects AI coding assistants (Claude, Codex, Gemini, Kimi, Reasonix) to any GitLab instance — self-hosted or cloud.

## What you can do

| Area | Actions |
|------|---------|
| **Projects & Issues** | List, search, create, update, label, assign |
| **Merge Requests** | Review diffs, manage discussions, approve, merge, rebase |
| **CI/CD** | Inspect pipelines, read job logs, retry/cancel jobs, manage variables |
| **Repository** | Browse files, read content, create batch commits, manage branches & tags |
| **Search** | Code search, global search, user search |
| **Security** | Vulnerability findings, dependency list (SBOM), audit events |
| **Local AI** | Triage job logs, scan MR diffs for secrets, summarize discussions — all run locally via Ollama |
| **Diagnostics** | Health-check connectivity, verify token permissions, report GitLab version |

---

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose v2
- A GitLab [Personal Access Token](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html) with `api` scope

> **WSL2 (Windows users):** Install [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/) with the WSL2 backend enabled — this is the easiest path.
> All commands below are run inside your WSL2 terminal.

### 1. Install

**Option A — One-liner (fastest)**

Paste this into your terminal. It clones to `~/.gitlab-ai-mcp`, then runs the interactive installer:

```bash
curl -fsSL https://raw.githubusercontent.com/Wafiy-Firdaus/Gitlab_AI_MCP/main/scripts/quick-install.sh | bash
```

> **Want a different location?** Clone manually and run `./scripts/install.sh` instead.

**Option B — Clone + install (recommended if you prefer transparency)**

```bash
git clone https://github.com/Wafiy-Firdaus/Gitlab_AI_MCP.git ~/.gitlab-ai-mcp
cd ~/.gitlab-ai-mcp
./scripts/install.sh
```

> **Already have a token ready?** Skip the prompt:
> ```bash
> ./scripts/install.sh --gitlab-url https://gitlab.example.com
> ```

**Option C — Manual install**

If you prefer to run the steps yourself, or want to use the pre-built image from GitHub Container Registry:

```bash
# Pull pre-built image (no local build needed)
docker pull ghcr.io/wafiy-firdaus/gitlab-ai-mcp:latest
docker compose up -d

# Or build locally
docker compose up -d --build
```

For Ollama (local AI):
```bash
# CPU
docker compose --profile ollama up -d --build

# GPU (see setup below)
docker compose --profile ollama -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

Then register manually with your AI CLI:

```bash
# Kimi
kimi mcp add --transport stdio gitlab-ai-mcp -- $(pwd)/scripts/run_mcp.sh

# Claude
claude mcp add --scope user gitlab-ai-mcp -- $(pwd)/scripts/run_mcp.sh

# Codex
codex mcp add gitlab-ai-mcp -- $(pwd)/scripts/run_mcp.sh

# Gemini
gemini mcp add gitlab-ai-mcp -- $(pwd)/scripts/run_mcp.sh

# Reasonix (manual — Reasonix configures MCP servers via its config file)
mkdir -p ~/.reasonix
# If ~/.reasonix/config.json already exists, merge the mcpServers block manually.
# If it does NOT exist, copy the template:
cp mcp-configs/reasonix.global.json ~/.reasonix/config.json
# Then edit the command path in ~/.reasonix/config.json to point to
# $(pwd)/scripts/run_mcp.sh
```

Or copy a template from [`mcp-configs/`](./mcp-configs/) to your global config location.

> Options with Ollama enable extra AI features: log triage, privacy scanning, discussion summarisation.  
> If Ollama is not running, these features return a clear error — all other features work normally.

---

#### Setting up NVIDIA GPU (Option C only)

Skip this section if you don't have an NVIDIA GPU — the CPU option works fine.

**🐧 Native Linux**

```bash
# 1. Verify GPU drivers
nvidia-smi

# 2. Install NVIDIA Container Toolkit (Ubuntu/Debian)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update && sudo apt install -y nvidia-container-toolkit

# 3. Configure Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 4. Verify
docker run --rm --gpus all ubuntu nvidia-smi
```

For other distros, see the [official install guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

**🪟 WSL2 (Windows)**

WSL2 uses the NVIDIA drivers installed on **Windows** — do not install GPU drivers inside WSL.

1. Install [NVIDIA drivers on Windows](https://www.nvidia.com/en-us/drivers/) and reboot.
2. Verify inside WSL2: `nvidia-smi`
3. Install NVIDIA Container Toolkit inside WSL2 (same commands as Native Linux step 2 above).
4. Configure Docker Desktop → Settings → Resources → **GPU** → enable → Apply & Restart.
5. Verify: `docker run --rm --gpus all ubuntu nvidia-smi`

---

### 3. Verify

```bash
docker compose ps
```

You should see `gitlab-ai-mcp` with status `Up`. Test it directly:

```bash
docker compose exec gitlab-ai-mcp python run_tests.py
```

Then open any project in your AI CLI and check that the server is connected:

| AI CLI | Command |
|--------|---------|
| Kimi | `kimi mcp list` or `/mcp` inside the shell |
| Claude | `claude mcp list` or `/mcp` inside the shell |
| Codex | `codex mcp list` |
| Gemini | `gemini mcp list` or `/mcp` inside the shell |
| Reasonix | `reasonix mcp list` or `/mcp` inside the shell |

---

## 🌍 Global vs Local Configuration

This project is designed to be registered as a **global** MCP server so it is available in every project you open with your AI CLI.

- **Global configs** live in your home directory (e.g. `~/.kimi/mcp.json`, `~/.codex/config.toml`) and apply everywhere.
- **Local configs** (e.g. `.claude/settings.local.json`, `.gemini/settings.json` inside a project repo) only apply when you are inside that specific directory.

The `scripts/run_mcp.sh` launcher is path-agnostic — it automatically finds the project directory regardless of where your AI CLI invokes it — so global registration works correctly.

---

## ⚙️ Configuration

All settings go in your `.env` file:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITLAB_URL` | **Yes** | — | Base URL of your GitLab instance |
| `GITLAB_TOKEN` | **Yes** | — | Personal Access Token (`api` scope) |
| `GITLAB_READ_ONLY` | No | `false` | Disable all GitLab write operations when `true` |
| `DEBUG` | No | `false` | Enable verbose console logging |
| `LOCAL_AI_URL` | No | `http://ollama:11434` | Ollama endpoint (Options B/C only) |
| `LOCAL_AI_MODEL` | No | `llama3.1:8b` | Ollama model name |
| `GITLAB_MAX_RETRIES` | No | `3` | API retry attempts on failure |
| `GITLAB_RETRY_DELAY` | No | `1.0` | Base delay between retries (seconds) |

---

## 🔧 Troubleshooting

**Check status:**
```bash
./scripts/status.sh
```

**View logs:**
```bash
./scripts/logs.sh
```

**Update to latest version:**
```bash
./scripts/update.sh
```

**Uninstall:**
```bash
./scripts/uninstall.sh
```

**Container won't start:**
```bash
docker compose logs gitlab-ai-mcp
```

**`GITLAB_TOKEN` or `GITLAB_URL` errors:**
- Make sure your `.env` file exists and has no extra spaces around `=`
- Confirm your token has `api` scope in GitLab → Settings → Access Tokens

**Ollama model not downloading (Options B/C):**
```bash
docker compose logs gitlab-ai-ollama-pull
```

**GPU not detected (Option C):**
- Run `nvidia-smi` — if this fails, your drivers are not installed
- Run `docker run --rm --gpus all ubuntu nvidia-smi` — if this fails, the Container Toolkit is not configured

**WSL2 — `nvidia-smi` not found inside WSL:**
- Make sure you are on WSL2, not WSL1: run `wsl --list --verbose` in PowerShell and check the VERSION column
- Install NVIDIA drivers on **Windows** (not inside WSL) and reboot

**WSL2 — `systemctl: command not found`:**
- WSL2 does not use systemd by default — use `sudo service docker restart` instead
- Or enable systemd in WSL2: add `[boot] systemd=true` to `/etc/wsl.conf`, then restart WSL (`wsl --shutdown` in PowerShell)

**WSL2 — Docker Desktop GPU toggle missing:**
- Requires Docker Desktop 4.17 or later and WSL2 backend — update Docker Desktop if the GPU option is not visible

**WSL2 — `docker compose` not found:**
- Docker Desktop installs Compose automatically — open Docker Desktop and ensure it is running before using the WSL2 terminal

---

## 🛠️ Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run full check suite (lint + format + types + tests + smoke)
make check

# Run tests with coverage
make coverage

# See all available commands
make help
```

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for setup instructions, architecture overview, and PR guidelines.  
See [`CHANGELOG.md`](./CHANGELOG.md) for release history.

---

## 📁 Project Structure

```
server.py                  — MCP server entrypoint (103 tools, 2 prompt templates)
config.py                  — Settings (reads from .env)
_version.py                — Single source of truth for package version
gitlab/client.py           — Async HTTP/2 GitLab API client with retry + pagination
gitlab/models.py           — Pydantic models for GitLab resources
services/
  gitlab_service.py        — Thin facade; inherits all domain mixins
  _issue_mixin.py          — Issue CRUD, notes, discussions, triage, attachments
  _mr_mixin.py             — MR operations, diffs, reviews, draft notes, approvals
  _repo_ci_mixin.py        — Repository, CI/CD pipelines, jobs, variables
  _security_mixin.py       — Vulnerability findings, dependencies, audit events
  _utils.py                — Shared upload URL helpers
  local_ai_service.py      — Ollama integration (secret scrubbing + triage)
  review_digest.py         — Pure helpers for MR discussion normalisation
tools/                     — MCP tool definitions (one file per domain)
  _annotations.py          — Pre-built MCP ToolAnnotations constants
  _utils.py                — Shared helpers (URL resolution, error formatting)
  exceptions.py            — Structured error types for tool handlers
tests/                     — 187 unit tests (pytest, no network required)
scripts/
  quick-install.sh         — One-liner entrypoint (clone + run install.sh)
  install.sh               — Interactive installer (validates token, builds, registers)
  update.sh                — Pull latest code, rebuild container, keep .env backup
  status.sh                — Container health, GitLab connectivity, AI CLI registrations
  logs.sh                  — Tail container logs
  uninstall.sh             — Clean removal (stop container + unregister)
  run_mcp.sh               — Launcher script used by all AI CLIs
mcp-configs/               — Global MCP config templates (Claude, Codex, Gemini, Kimi, Reasonix)
.github/                   — CI workflows (lint, test, docker, release, Bandit SAST)
docker-compose.yml         — Base stack
docker-compose.gpu.yml     — NVIDIA GPU override (use with --profile ollama)
Makefile                   — Common dev tasks (check, coverage, docker-build)
.pre-commit-config.yaml    — Pre-commit hooks (ruff, mypy)
CHANGELOG.md               — Release history
CONTRIBUTING.md            — Contributor guide
AGENTS.md                  — AI coding agent guidance
```
