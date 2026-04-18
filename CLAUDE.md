# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A containerized [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that exposes GitLab API operations as MCP tools. AI assistants (Claude, Codex, Gemini, Kimi) connect to it and call tools to manage projects, MRs, issues, pipelines, repository files, and security findings. An optional Ollama sidecar enables local AI triage of job logs, secrets scanning of MR diffs, and issue analysis — with secrets scrubbed before any data leaves the container.

## Commands

**Install dependencies (host development):**
```bash
pip install -e ".[dev]"   # or: uv pip install -e ".[dev]"
```

**Lint:**
```bash
ruff check .
ruff format --check .
```

**Unit tests:**
```bash
python -m pytest -q
# single test file:
python -m pytest tests/test_gitlab_client.py -v
```

**Smoke test (checks tool/prompt registration, no live GitLab needed):**
```bash
python run_tests.py
```

**Run the full stack:**
```bash
docker compose up -d --build                                                 # core only
docker compose --profile ollama up -d --build                               # + local AI on CPU
docker compose --profile ollama -f docker-compose.yml -f docker-compose.gpu.yml up -d --build  # + GPU
```

**Verify container health:**
```bash
docker compose ps
docker compose exec gitlab-ai-mcp python run_tests.py
```

## Architecture

```
server.py          — FastMCP entrypoint; registers all tools, defines review_mr and debug_job prompt templates
config.py          — Pydantic Settings; reads GITLAB_URL, GITLAB_TOKEN, LOCAL_AI_* from .env
gitlab/client.py   — Singleton async HTTP/2 client (GitLabClient); all raw GitLab API calls live here
services/
  gitlab_service.py    — Orchestration layer; called by tool handlers; returns structured {summary, key_findings, details, next_action}
  local_ai_service.py  — Ollama client; scrubs secrets before sending; used by triage/summarise/privacy tools
  review_digest.py     — Pure, no-I/O helpers for normalising MR discussions and building digests
tools/             — One file per domain; each registers handlers with mcp via register_*_tools(mcp)
  ci_cd.py  issues.py  merge_requests.py  projects.py  repository.py  search.py  security.py
tests/             — pytest unit tests (no network required)
scripts/
  run_mcp.sh        — Launcher used by AI CLIs; proxies stdin/stdout into the running container
  run_codex_mcp.sh  — Alias used when registering with Claude/Codex/Gemini/Kimi
```

### Key design decisions

**Singleton `GitLabClient`** — `GitLabClient.get_instance()` returns a shared async `httpx` client with HTTP/2, a 100-connection pool, and exponential-backoff retry (configurable via `GITLAB_MAX_RETRIES` / `GITLAB_RETRY_DELAY`). Never instantiate `GitLabClient()` directly in tools — always use `await GitLabClient.get_instance()`.

**Layered call path** — Tools call `GitLabService`, which calls `GitLabClient`. Tools must not call `GitLabClient` directly. This keeps response shaping in one place.

**Response contract** — Every `GitLabService` method returns `{summary: str, key_findings: list[str], details: dict, next_action: str}`. New service methods must follow this shape.

**`project_id` encoding** — `GitLabClient._format_project_id()` URL-encodes `"group/subgroup/project"` path strings. All client methods accept `int | str` for project IDs.

**Local AI is optional** — `LocalAIService` gracefully degrades: if Ollama is unreachable it returns an error string, so all other tools remain functional. `scrub_secrets()` runs on every payload before it reaches Ollama.

**Pagination** — Use `client.get_all()` for endpoints that paginate (follows `X-Next-Page`). Pass `limit=` to avoid fetching unbounded lists.

## Adding a new tool

1. Pick the right domain file in `tools/` (or create one if the domain is new).
2. Add an async handler that calls `GitLabService`; decorate with `@mcp.tool()`.
3. Register the handler inside `register_*_tools(mcp)` in the same file.
4. If the operation needs a new GitLab API call, add a method to `GitLabClient` first, then expose it via `GitLabService`.
5. Add a unit test in `tests/` (mock `httpx` responses; no live GitLab required).

## Environment variables

| Variable | Required | Default |
|---|---|---|
| `GITLAB_URL` | Yes | — |
| `GITLAB_TOKEN` | Yes | — |
| `DEBUG` | No | `false` |
| `LOCAL_AI_URL` | No | `http://ollama:11434` |
| `LOCAL_AI_MODEL` | No | `llama3.1:8b` |
| `GITLAB_MAX_RETRIES` | No | `3` |
| `GITLAB_RETRY_DELAY` | No | `1.0` |
