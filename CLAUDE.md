# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A containerized [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that exposes GitLab API operations as MCP tools. AI assistants (Claude, Codex, Gemini, Kimi) connect to it and call tools to manage projects, MRs, issues, pipelines, repository files, and security findings. An optional Ollama sidecar enables local AI triage of job logs, secrets scanning of MR diffs, and issue analysis — with secrets scrubbed before any data leaves the container.

## Commands

```bash
# Install
pip install -e ".[dev]"          # or: uv pip install -e ".[dev]"

# Full check suite (lint + format-check + types + tests + smoke)
make check

# Individual steps
ruff check .                      # lint
ruff format .                     # auto-format (use --check to verify only)
mypy .                            # type check
python -m pytest -q               # unit tests
python -m pytest tests/test_gitlab_client.py -v          # single file
python -m pytest tests/test_review_digest.py -v -k "test_name"  # single test
python -m pytest --cov=gitlab --cov=services --cov=tools --cov-report=term-missing  # with coverage
python run_tests.py               # smoke test (no live GitLab needed)

# Docker
docker compose up -d --build
docker compose --profile ollama up -d --build            # + Ollama (CPU)
docker compose --profile ollama -f docker-compose.yml -f docker-compose.gpu.yml up -d --build  # + GPU
docker compose exec gitlab-ai-mcp python run_tests.py    # verify container
```

## Architecture

```
server.py          — FastMCP entrypoint; registers all tools, defines review_mr and debug_job prompt templates
config.py          — Pydantic Settings; reads GITLAB_URL, GITLAB_TOKEN, LOCAL_AI_* from .env
_version.py        — Single source of truth for package version
gitlab/
  client.py        — Singleton async HTTP/2 client (GitLabClient); all raw GitLab API calls live here
  models.py        — Pydantic models: GitLabProject, GitLabIssue, GitLabMergeRequest
services/
  gitlab_service.py    — Orchestration layer; called by tool handlers; shapes all responses
  local_ai_service.py  — Ollama client; scrubs secrets before sending; used by triage/summarise/privacy tools
  review_digest.py     — Pure, no-I/O helpers for normalising MR discussions and building digests
tools/             — One file per domain; each registers handlers with mcp via register_*_tools(mcp)
  _annotations.py  — Pre-built MCP ToolAnnotations: READ_ONLY, WRITE_IDEMPOTENT, WRITE_DESTRUCTIVE
  _utils.py        — Shared helpers: resolve_ids_or_fail(), register_diagnostic_tools()
  exceptions.py    — Structured error types: GitLabToolError, MissingIdentifierError, GitLabApiError
  ci_cd.py         — Pipelines, jobs, bridges, variables, artifacts, triggers
  issues.py        — Issues, notes, discussions, labels, triage
  merge_requests.py — MRs, diffs, discussions, approvals, drafts, reviews, merge, rebase
  projects.py      — Projects, groups, members, environments, intelligence bundles
  repository.py    — Files, branches, tags, commits, blame, batch commits
  search.py        — Code search, global search, user search
  security.py      — Vulnerability findings, dependencies, audit events
tests/             — pytest unit tests (no network required)
scripts/
  run_mcp.sh       — Launcher used by all AI CLIs; checks .env, auto-starts container, exec's server.py
  install.sh       — Interactive installer; detects Kimi/Claude/Codex/Gemini/Reasonix CLIs
```

### Key design decisions

**Layered call path** — Tools → `GitLabService` → `GitLabClient` → GitLab REST API v4. Tools must never call `GitLabClient` directly.

**Singleton `GitLabClient`** — `GitLabClient.get_instance()` returns a shared async `httpx` client with HTTP/2, a 100-connection pool, and exponential-backoff retry. Never instantiate `GitLabClient()` directly. The client maintains two underlying `httpx` clients: `self.client` (API calls with `PRIVATE-TOKEN` header) and `self.web_client` (web routes / uploads, no auth header).

**`GitLabService` per-call instantiation** — Construct a fresh service in every tool handler; do not cache across calls:
```python
client = await GitLabClient.get_instance()
service = GitLabService(client)
```

**Response contract** — Every `GitLabService` method must return exactly:
```python
{"summary": str, "key_findings": list[str], "details": dict, "next_action": str}
```

**URL or IDs** — Most handlers accept a full GitLab URL or explicit `project_id` + resource IID. Use `resolve_ids_or_fail()` from `tools/_utils.py` (wraps `service.resolve_url_or_ids()` and returns the error dict on failure). `GitLabClient.parse_gitlab_url()` parses URLs; `parse_mr_diff_url()` handles diff anchor URLs.

**`project_id` encoding** — `GitLabClient._format_project_id()` URL-encodes `"group/subgroup/project"` path strings. All client methods accept `int | str`.

**Pagination** — Use `client.get_all(endpoint, limit=N)` for paginated endpoints (follows `X-Next-Page`). Always pass `limit=` to avoid unbounded fetches.

**Retry / rate-limiting** — `_request()` retries on HTTP 429 (respects `Retry-After`), 5xx, and network errors. Backoff: `retry_delay * (2 ** attempt)`.

**MCP tool annotations** — Every `@mcp.tool()` must include `annotations=` using one of the three constants from `tools/_annotations.py`: `READ_ONLY`, `WRITE_IDEMPOTENT`, or `WRITE_DESTRUCTIVE`.

**Bundle tools** — High-level tools that fetch multiple resources in parallel to reduce round-trips and token usage: `bundle_merge_request_context`, `bundle_issue_context`, `bundle_project_intelligence`, `bundle_pipeline_context`.

**Local AI is optional** — `LocalAIService` degrades gracefully: unreachable Ollama returns an error string; all other tools remain functional. `scrub_secrets()` runs on every payload before it reaches Ollama (redacts IPs, GitLab tokens, AWS keys, long hex strings).

**Test env bootstrap** — `tests/conftest.py` injects dummy `GITLAB_URL` and `GITLAB_TOKEN` env vars before any project import so `Settings` never reads a local `.env`. Do not import `config` or tool modules at the top level of test files.

## Adding a new tool

1. Pick the right domain file in `tools/` (or create one if the domain is new).
2. Add an async handler that calls `GitLabService`; decorate with `@mcp.tool(annotations=READ_ONLY|WRITE_IDEMPOTENT|WRITE_DESTRUCTIVE)`.
3. Register the handler inside `register_*_tools(mcp)` in the same file.
4. If the operation needs a new GitLab API call, add a method to `GitLabClient` first, then expose it via `GitLabService`.
5. Add a unit test in `tests/` (mock `httpx` responses; no live GitLab required).
6. If you created a new `tools/*.py` file, import and call its `register_*_tools(mcp)` in `server.py`.
7. Update `AGENTS.md` if you change architecture or conventions.

## Environment variables

| Variable            | Required | Default                  |
| ------------------- | -------- | ------------------------ |
| `GITLAB_URL`        | Yes      | —                        |
| `GITLAB_TOKEN`      | Yes      | —                        |
| `GITLAB_READ_ONLY`  | No       | `false`                  |
| `DEBUG`             | No       | `false`                  |
| `LOCAL_AI_URL`      | No       | `http://ollama:11434`    |
| `LOCAL_AI_MODEL`    | No       | `llama3.1:8b`            |
| `GITLAB_MAX_RETRIES`| No       | `3`                      |
| `GITLAB_RETRY_DELAY`| No       | `1.0`                    |
