# Gitlab_AI_MCP

`Gitlab_AI_MCP` is a local MCP server for GitLab. It lets MCP-capable coding agents such as Codex CLI, Claude Code, and Gemini CLI work with GitLab projects, merge requests, issues, repositories, and pipelines through one shared integration.

This project is designed to run locally with Docker and expose the server over MCP stdio through a small launcher script.

## What You Can Do With It

After setup, an MCP client can use this server to:

- list and inspect GitLab projects
- read and update issues
- inspect merge requests, diffs, notes, and discussions
- reply to MR threads and manage review workflows
- browse repository files, commits, and blame data
- inspect pipelines, jobs, logs, and artifacts
- run local AI-assisted job log triage with Ollama

## Requirements

You need:

- Docker and Docker Compose
- a GitLab Personal Access Token
- one MCP-capable client such as Codex CLI, Claude Code, or Gemini CLI

Python 3.12+ is only needed if you want to run or test the project outside Docker.

## Quick Start

1. Create a local environment file:

```bash
cp .env.example .env
```

2. Edit `.env` and set your GitLab details:

```bash
GITLAB_URL=https://gitlab.example.com
GITLAB_TOKEN=glpat-your-token
```

3. Start the local services:

```bash
docker compose up -d --build
```

This starts:

- `gitlab-ai-mcp`: the MCP server runtime
- `ollama`: optional local LLM service for log-triage tools
- `ollama-pull`: helper container that pre-pulls the configured local model

4. Register the MCP server in your client using the shared launcher:

```bash
scripts/run_mcp.sh
```

The launcher checks that Docker is available and that the `gitlab-ai-mcp` service is running, then executes:

```bash
docker compose exec -T gitlab-ai-mcp python server.py
```

## Client Setup

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

If you prefer a static MCP config file, use `codex.mcp.toml.example` as a starting point.

## Configuration

The main environment variables are:

- `GITLAB_URL`: base URL of your GitLab instance
- `GITLAB_TOKEN`: GitLab Personal Access Token
- `DEBUG`: enables console-friendly logging
- `LOCAL_AI_URL`: Ollama base URL
- `LOCAL_AI_MODEL`: model name for local triage features

Example values are included in `.env.example`.

## Running Checks

Smoke check:

```bash
docker compose exec gitlab-ai-mcp python run_tests.py
```

Unit tests:

```bash
docker compose exec gitlab-ai-mcp pytest -q
```

## Project Layout

- `server.py`: MCP entrypoint and prompt registration
- `config.py`: environment-backed settings
- `gitlab/`: async GitLab client and models
- `services/`: business logic and response shaping
- `tools/`: FastMCP tool definitions
- `scripts/run_mcp.sh`: shared launcher for Codex, Claude Code, and Gemini CLI
- `docker-compose.yml`: local runtime stack
- `run_tests.py`: smoke test for registration and wiring
- `tests/`: lightweight unit tests

## Troubleshooting

### `gitlab-ai-mcp container is not running`

Start the stack first:

```bash
docker compose up -d --build
```

### GitLab requests fail with authentication errors

Check that:

- `GITLAB_URL` is correct
- `GITLAB_TOKEN` is valid
- the token has enough scope for the actions you want to perform

### Docker is installed but the launcher still fails

Make sure Docker is running and that `docker compose` works from the project directory.

### Ollama is unavailable

Most GitLab tools still work without Ollama. Only the local AI-assisted triage features depend on it.

## Notes

- Keep `.env` local and never commit tokens.
- Use least-privilege GitLab tokens where possible.
- Upload fetching prefers authenticated headers and only falls back to query-string token auth when a GitLab web route rejects header-based auth.
