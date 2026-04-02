# Gitlab_AI_MCP

`Gitlab_AI_MCP` is a local Model Context Protocol server for GitLab. It gives MCP-capable coding agents such as Codex CLI, Claude Code, and Gemini CLI a practical interface to GitLab projects, merge requests, issues, repositories, and pipelines through one shared integration.

It is designed for local use with Docker and exposes the server over MCP stdio through a single launcher script.

## Why This Exists

Most coding agents are strong at reasoning over code but weak at navigating the operational side of a software project unless they have direct integrations. `Gitlab_AI_MCP` closes that gap by giving an agent structured access to the parts of GitLab that matter during real engineering work:

- code review
- issue triage
- pipeline debugging
- repository inspection
- project metadata and collaboration workflows

## What You Can Do With It

After setup, an MCP client can use this server to:

- list and inspect GitLab projects
- read, update, and comment on issues
- inspect merge requests, diffs, approvals, notes, and discussions
- reply to MR threads and manage review workflows
- browse repository files, commits, blame data, and raw file content
- inspect pipelines, jobs, logs, environments, variables, and artifacts
- run local AI-assisted job log triage with Ollama

## Typical Workflows

### 1. Review a Merge Request

Use your MCP client to:

- fetch MR details
- inspect diffs and discussions
- identify blockers or regressions
- reply to review threads
- summarize merge readiness

### 2. Debug a Failed Pipeline

Use your MCP client to:

- inspect the pipeline
- list jobs
- read failing logs
- extract artifacts
- triage the failure locally with Ollama

### 3. Work With a Repository Without Leaving the Agent

Use your MCP client to:

- list repository files
- read a config or source file
- inspect blame and commit history
- create or update files through GitLab APIs when appropriate

## Requirements

You need:

- Docker and Docker Compose
- a GitLab Personal Access Token
- one MCP-capable client such as Codex CLI, Claude Code, or Gemini CLI

Python 3.12+ is only needed if you want to run or test the project outside Docker.

## GitLab Token Guidance

Use a dedicated GitLab token for this integration where possible.

Recommended approach:

- create a token specifically for `Gitlab_AI_MCP`
- grant the smallest scope that supports your workflows
- avoid reusing a broad personal admin token unless you truly need it

Minimum scope depends on what you want the agent to do:

- read-only repository and MR inspection: a read-focused token is usually enough
- commenting, updating issues, approving or managing MR discussions: write API access is required
- pipeline control, variables, and environment management: broader API permissions may be required

If you are unsure, start with the smallest workable scope and expand only when a real workflow needs it.

## Quick Start

1. Create a local environment file:

```bash
cp .env.example .env
```

2. Edit `.env` and set your GitLab connection:

```bash
GITLAB_URL=https://gitlab.example.com
GITLAB_TOKEN=glpat-your-token
```

3. Start the local stack:

```bash
docker compose up -d --build
```

This starts:

- `gitlab-ai-mcp`: the MCP server runtime
- `ollama`: optional local LLM service used by local triage tools
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

## Main Tool Areas

This server is organized around a few high-value domains:

- `projects`: project metadata, labels, members, and discovery
- `issues`: issue details, notes, and updates
- `merge_requests`: MR details, diffs, approvals, notes, discussions, and merge actions
- `repository`: files, commits, blame, branches, raw content, and uploads
- `ci_cd`: pipelines, jobs, logs, artifacts, variables, environments, retries, and controls
- `search`: user lookup, code search, and global search

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

The main environment variables are:

- `GITLAB_URL`: base URL of your GitLab instance
- `GITLAB_TOKEN`: GitLab Personal Access Token
- `DEBUG`: enables console-friendly logging
- `LOCAL_AI_URL`: Ollama base URL
- `LOCAL_AI_MODEL`: model name for local triage features

Example values are included in `.env.example`.

## Tested Usage

This project is structured for:

- Codex CLI via `mcp add`
- Claude Code via `mcp add`
- Gemini CLI via `mcp add`

The shared launcher keeps all three clients on the same runtime path, which reduces client-specific drift.

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
- the token has enough scope for the action you are trying to perform

### Docker is installed but the launcher still fails

Make sure Docker is running and that `docker compose` works from the project directory.

### Ollama is unavailable

Most GitLab tools still work without Ollama. Only the local AI-assisted triage features depend on it.

### Push, merge, or variable-management actions fail

That usually means the token scope is too narrow or the GitLab account lacks permission in the target project.

## Security Notes

- keep `.env` local and never commit tokens
- use least-privilege GitLab tokens where possible
- use a dedicated token for this integration if you can
- upload fetching prefers authenticated headers and only falls back to query-string token auth when a GitLab web route rejects header-based auth

## Summary

If you want one GitLab MCP server that works the same way for Codex CLI, Claude Code, and Gemini CLI, this project is built for that exact use case.
