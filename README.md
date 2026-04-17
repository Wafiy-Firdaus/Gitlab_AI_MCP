# GitLab AI MCP Server

A high-performance, containerized [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that connects AI coding assistants (Claude, Codex, Gemini, Kimi) to any GitLab instance — self-hosted or cloud.

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

---

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose v2
- A GitLab [Personal Access Token](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html) with `api` scope

> **WSL2 (Windows users):** Install [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/) with the WSL2 backend enabled — this is the easiest path.
> All commands below are run inside your WSL2 terminal.

### 1. Clone and configure

```bash
git clone https://github.com/Wafiy-Firdaus/Gitlab_AI_MCP.git
cd Gitlab_AI_MCP
cp .env.example .env
```

Edit `.env`:

```env
GITLAB_URL=https://gitlab.example.com   # your GitLab instance URL
GITLAB_TOKEN=glpat-your-token           # your Personal Access Token
```

### 2. Choose your setup and start

**Option A — Core only** *(recommended to start — no local AI, works on any machine):*
```bash
docker compose up -d --build
```

**Option B — With local AI on CPU** *(Ollama runs on CPU, ~4 GB model download on first run):*
```bash
docker compose --profile ollama up -d --build
```

**Option C — With local AI on NVIDIA GPU** *(fastest inference — requires extra setup below):*
```bash
docker compose --profile ollama -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

> Options B and C enable extra AI features: log triage, privacy scanning, discussion summarisation.
> If Ollama is not running, these features return a clear error — all other features work normally.

#### Setting up NVIDIA GPU (Option C only)

Skip this section if you don't have an NVIDIA GPU — Option B works fine on CPU.

---

**🐧 Native Linux**

**Step 1 — Verify your NVIDIA drivers are installed:**
```bash
nvidia-smi
```
You should see your GPU listed. If not, install the drivers for your distro first:
[NVIDIA Driver Downloads](https://www.nvidia.com/en-us/drivers/)

**Step 2 — Install NVIDIA Container Toolkit (Ubuntu/Debian):**
```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update && sudo apt install -y nvidia-container-toolkit
```

For other distros, see the [official install guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

**Step 3 — Configure Docker and verify:**
```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Confirm Docker can see your GPU
docker run --rm --gpus all ubuntu nvidia-smi
```

**Step 4 — Start the stack:**
```bash
docker compose --profile ollama -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

---

**🪟 WSL2 (Windows)**

WSL2 uses the NVIDIA drivers installed on **Windows** — you do not install GPU drivers inside WSL.

**Step 1 — Install NVIDIA drivers on Windows (if not already installed):**

Download and install from [NVIDIA Driver Downloads](https://www.nvidia.com/en-us/drivers/).
Reboot Windows after installing.

**Step 2 — Verify GPU is visible inside WSL2:**
```bash
nvidia-smi
```
If this works, your GPU is available in WSL2. If not, make sure you have WSL2 (not WSL1):
```bash
wsl --set-default-version 2
```

**Step 3 — Install NVIDIA Container Toolkit inside WSL2:**
```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update && sudo apt install -y nvidia-container-toolkit
```

**Step 4 — Configure Docker:**

If using **Docker Desktop for Windows** (recommended):
- Open Docker Desktop → Settings → Resources → **GPU** → enable your GPU → Apply & Restart

If using **Docker Engine directly in WSL2**:
```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo service docker restart   # WSL2 uses service, not systemctl
```

**Step 5 — Verify Docker can see your GPU:**
```bash
docker run --rm --gpus all ubuntu nvidia-smi
```

**Step 6 — Start the stack:**
```bash
docker compose --profile ollama -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

### 3. Verify the server is running

```bash
docker compose ps
```

You should see `gitlab-ai-mcp` with status `Up`. Test it directly:

```bash
docker compose exec gitlab-ai-mcp python run_tests.py
```

### 4. Register with your AI CLI

First, get your checkout path:
```bash
pwd   # run this inside the Gitlab_AI_MCP directory
```

> **WSL2 users:** Use the Linux path shown by `pwd` (e.g. `/home/yourname/Gitlab_AI_MCP`), not the Windows path.
> Your AI CLI must be running inside the same WSL2 terminal for this path to work.

Then register using that path:

**Claude Code:**
```bash
claude mcp add gitlab-ai-mcp -- /your/path/to/Gitlab_AI_MCP/scripts/run_codex_mcp.sh
```

**Codex CLI:**
```bash
codex mcp add gitlab-ai-mcp -- /your/path/to/Gitlab_AI_MCP/scripts/run_codex_mcp.sh
```

**Gemini CLI:**
```bash
gemini mcp add gitlab-ai-mcp -- /your/path/to/Gitlab_AI_MCP/scripts/run_codex_mcp.sh
```

**Kimi Code CLI:**
```bash
kimi mcp add gitlab-ai-mcp -- /your/path/to/Gitlab_AI_MCP/scripts/run_codex_mcp.sh
```

---

## ⚙️ Configuration

All settings go in your `.env` file:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITLAB_URL` | **Yes** | — | Base URL of your GitLab instance |
| `GITLAB_TOKEN` | **Yes** | — | Personal Access Token (`api` scope) |
| `DEBUG` | No | `false` | Enable verbose console logging |
| `LOCAL_AI_URL` | No | `http://ollama:11434` | Ollama endpoint (Options B/C only) |
| `LOCAL_AI_MODEL` | No | `llama3.1:8b` | Ollama model name |
| `GITLAB_MAX_RETRIES` | No | `3` | API retry attempts on failure |
| `GITLAB_RETRY_DELAY` | No | `1.0` | Base delay between retries (seconds) |

---

## 🔧 Troubleshooting

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

## 📁 Project Structure

```
server.py                  — MCP server entrypoint
config.py                  — Settings (reads from .env)
gitlab/client.py           — Async HTTP/2 GitLab API client
services/
  gitlab_service.py        — Business logic and response formatting
  local_ai_service.py      — Ollama integration for local AI features
  review_digest.py         — MR discussion digest helpers
tools/                     — MCP tool definitions (one file per domain)
tests/                     — Unit tests
scripts/run_codex_mcp.sh   — Launcher used by all AI CLIs
docker-compose.yml         — Base stack
docker-compose.gpu.yml     — NVIDIA GPU override (use with --profile ollama)
```
