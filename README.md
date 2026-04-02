# Gitlab_AI_MCP

`Gitlab_AI_MCP` is a Docker-first Model Context Protocol server for GitLab. It exposes project, issue, merge request, repository, search, and CI/CD tools over MCP stdio so clients such as Codex CLI, Claude Code, and Gemini CLI can operate on GitLab through one local server.

## Features

- Async GitLab client built on `httpx` with HTTP/2 and connection pooling
- FastMCP-based tool server with grouped tools for projects, issues, merge requests, repositories, search, and pipelines
- URL-aware tools that accept either explicit IDs or direct GitLab URLs for many workflows
- Optional local log triage through Ollama for failed CI jobs
- Docker Compose setup for a reproducible local runtime

## Requirements

- Docker and Docker Compose
- A GitLab Personal Access Token
- Python 3.12+ only if you want to run the project outside Docker

## Quick Start

1. Create your environment file:

```bash
cp .env.example .env
```

2. Update `.env`:

```bash
GITLAB_URL=https://gitlab.example.com
GITLAB_TOKEN=glpat-your-token
```

3. Start the local stack:

```bash
docker compose up -d --build
```

This starts:

- `gitlab-ai-mcp`: the MCP server runtime service
- `ollama`: optional local LLM service used by log-triage tools
- `ollama-pull`: helper container that pre-pulls the configured local model

## MCP Client Setup

All supported clients use the same launcher:

```bash
scripts/run_mcp.sh
```

The launcher executes:

```bash
docker compose exec -T gitlab-ai-mcp python server.py
```

### Codex CLI

```bash
codex mcp add Gitlab_AI_MCP -- "$(pwd)/scripts/run_mcp.sh"
```

### Claude Code

```bash
claude mcp add Gitlab_AI_MCP -- "$(pwd)/scripts/run_mcp.sh"
```

### Gemini CLI

```bash
gemini mcp add Gitlab_AI_MCP -- "$(pwd)/scripts/run_mcp.sh"
```

You can also use `codex.mcp.toml.example` as a template for a static MCP configuration entry.

## Running Checks

Smoke check:

```bash
docker compose exec gitlab-ai-mcp python run_tests.py
```

Unit tests:

```bash
docker compose exec gitlab-ai-mcp pytest -q
```

## Configuration

Example environment variables are defined in `.env.example`:

- `GITLAB_URL`: base URL of your GitLab instance
- `GITLAB_TOKEN`: GitLab Personal Access Token
- `DEBUG`: enable console-friendly logging
- `LOCAL_AI_URL`: Ollama base URL
- `LOCAL_AI_MODEL`: model name for local triage features

## Project Layout

- `server.py`: MCP entrypoint and prompt registration
- `config.py`: environment-backed settings
- `gitlab/`: async GitLab client and models
- `services/`: business logic and response shaping
- `tools/`: FastMCP tool definitions
- `docker-compose.yml`: local runtime stack
- `scripts/run_mcp.sh`: shared launcher for Codex, Claude Code, and Gemini CLI
- `run_tests.py`: smoke test for registration and wiring
- `tests/`: lightweight unit tests

## Notes

- Keep `.env` local and never commit tokens.
- Use least-privilege GitLab tokens where possible.
- Local AI is optional, but some job-triage tools depend on it.
- Upload fetching prefers authenticated headers and only falls back to query-string token auth when the GitLab web route rejects header-based auth.
