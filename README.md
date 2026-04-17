# Gitlab AI MCP Server

A high-performance, containerized [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for integrating AI coding assistants with any self-hosted or cloud GitLab instance.

## Capabilities

- **Projects & Issues** — list, search, create, update, labels, members, bundles.
- **Merge Requests** — metadata, diffs, discussions, approvals, merge, rebase.
- **MR Review Workflows** — draft notes, auto-resolved diff comments, review digests, suggested replies, bulk replies/resolves.
- **CI/CD** — pipelines, jobs, artifacts, variables, environments, failed-job analysis.
- **Repository** — file tree, raw content, batch commits, branches, tags, blame.
- **Search** — code search, global search, user search.
- **Security** — vulnerability findings, dependencies (SBOM), audit events.
- **Local AI (Ollama)** — triage job logs, summarize discussions, check MR privacy, triage issues — all processed locally.

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- A GitLab Personal Access Token with `api` scope

### 1. Clone and configure

```bash
git clone https://github.com/Wafiy-Firdaus/Gitlab_AI_MCP.git
cd Gitlab_AI_MCP
cp .env.example .env
```

Edit `.env` and set your values:

```env
GITLAB_URL=https://gitlab.example.com
GITLAB_TOKEN=glpat-your-token
```

### 2. Start the stack

Choose the setup that matches your machine:

**Option A — Core only** (no local AI, works on any machine):
```bash
docker compose up -d --build
```

**Option B — With local AI, CPU** (Ollama runs on CPU, no GPU required):
```bash
docker compose --profile ollama up -d --build
```

**Option C — With local AI, NVIDIA GPU** (fastest inference):
```bash
docker compose --profile ollama -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

> **Note:** Options B and C auto-download the `llama3.1:8b` model (~4 GB) on first run.
> Local AI features (`triage_job_log_locally`, `check_mr_privacy_locally`, etc.) return a
> friendly error if Ollama is not running — the rest of the server works fine without it.

### 3. Register with your AI CLI

Replace `/path/to/Gitlab_AI_MCP` with your actual checkout path.

**Claude Code:**
```bash
claude mcp add gitlab-ai-mcp -- /path/to/Gitlab_AI_MCP/scripts/run_codex_mcp.sh
```

**Codex CLI:**
```bash
codex mcp add gitlab-ai-mcp -- /path/to/Gitlab_AI_MCP/scripts/run_codex_mcp.sh
```

**Gemini CLI:**
```bash
gemini mcp add gitlab-ai-mcp -- /path/to/Gitlab_AI_MCP/scripts/run_codex_mcp.sh
```

**Kimi Code CLI:**
```bash
kimi mcp add gitlab-ai-mcp -- /path/to/Gitlab_AI_MCP/scripts/run_codex_mcp.sh
```

The launcher script executes:
```bash
docker compose exec -T gitlab-ai-mcp python server.py
```

## ⚙️ Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITLAB_URL` | Yes | — | Base URL of your GitLab instance |
| `GITLAB_TOKEN` | Yes | — | Personal Access Token (`api` scope) |
| `DEBUG` | No | `false` | Enable verbose console logging |
| `LOCAL_AI_URL` | No | `http://ollama:11434` | Ollama endpoint |
| `LOCAL_AI_MODEL` | No | `llama3.1:8b` | Ollama model for local triage |
| `GITLAB_MAX_RETRIES` | No | `3` | API retry attempts |
| `GITLAB_RETRY_DELAY` | No | `1.0` | Base retry delay in seconds |

## 📝 MR Review Workflows

### Draft-note flow (safe, human-in-the-loop)
1. **Read** — `get_merge_request_diffs`, `get_review_digest`, `get_unresolved_discussion_digest`
2. **Plan** — `get_draft_reply_plan`
3. **Stage** — `create_draft_note` (provide `new_path` + `new_line`; SHAs auto-resolve)
4. **Inspect** — `list_draft_notes`
5. **Publish** — `publish_draft_notes` after human approval

### Simple diff comments
`create_merge_request_discussion` and `create_draft_note` accept simple fields — no need to manually construct GitLab position objects:
- `new_path` (required)
- `old_path` (optional, defaults to `new_path`)
- `new_line` / `old_line` (at least one required)

### Bulk operations
- `bulk_reply_to_discussions` — reply to many threads (per-item errors isolated)
- `bulk_resolve_discussions` — resolve/reopen many threads (per-item errors isolated)

## ✅ Testing

```bash
# Run inside the container (any option A/B/C)
docker compose exec gitlab-ai-mcp python run_tests.py

# Run pytest suite on host (requires uv)
uv run pytest tests/ -v
```

## 📁 Project Structure

```
server.py           — MCP entrypoint
config.py           — Settings (pydantic-settings, reads .env)
gitlab/client.py    — Async HTTP/2 GitLab API client (singleton, retry logic)
services/
  gitlab_service.py — Business logic; AI-friendly response formatting
  local_ai_service.py — Ollama integration
  review_digest.py  — Pure MR discussion digest helpers
tools/              — MCP tool definitions (one file per domain)
tests/              — Pytest unit tests
scripts/run_codex_mcp.sh — Launcher used by all AI CLIs
docker-compose.yml        — Base stack (core server, Ollama optional via --profile ollama)
docker-compose.gpu.yml    — NVIDIA GPU override (stack with --profile ollama)
```
