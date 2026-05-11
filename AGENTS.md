<!-- AGENTS.md — GitLab AI MCP Server -->

This file contains project-specific context for AI coding agents. Read this first before modifying code.

---

## Project Overview

**GitLab AI MCP Server** is a containerized [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that exposes GitLab API operations as MCP tools. AI assistants (Claude, Codex, Gemini, Kimi) connect to it and call tools to manage projects, merge requests, issues, CI/CD pipelines, repository files, security findings, and more.

An optional Ollama sidecar enables local AI triage of job logs, secrets scanning of MR diffs, and discussion summarisation — with secrets scrubbed before any data leaves the container.

- **Version**: 0.5.2 (single source of truth in `_version.py`)
- **Language**: Python 3.12+
- **License**: See `LICENSE` file

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Runtime | Python 3.12+ |
| MCP Framework | `mcp[cli]>=1.2.1` (FastMCP) |
| HTTP Client | `httpx[http2]>=0.27.0` (async, HTTP/2, connection pooling) |
| Validation/Config | `pydantic>=2.6.0`, `pydantic-settings>=2.2.0` |
| Logging | `structlog>=24.1.0` (JSON in production, console in debug) |
| CLI Output | `rich>=13.7.0` |
| Build Backend | `hatchling` |
| Dev Tooling | `ruff>=0.3.0`, `pytest>=8.0.0`, `pytest-asyncio>=0.23.0`, `pytest-cov>=5.0.0`, `mypy` |

Key configuration files:
- `pyproject.toml` — Project metadata, dependencies, ruff config, hatchling wheel config
- `mypy.ini` — Type checker configuration (`disallow_untyped_defs = False`, module-specific overrides for `warn_return_any`)
- `docker-compose.yml` — Base stack (gitlab-ai-mcp + optional ollama profile)
- `docker-compose.gpu.yml` — NVIDIA GPU override for Ollama
- `Dockerfile` — `python:3.12-slim` based image
- `.env` — Runtime settings (see `.env.example` for template)

---

## Project Structure

```
server.py                  — FastMCP entrypoint; registers all tools and defines prompt templates
config.py                  — Pydantic Settings; reads GITLAB_URL, GITLAB_TOKEN, LOCAL_AI_* from .env
_version.py                — Single source of truth for package version
gitlab/
  client.py                — Singleton async HTTP/2 client (GitLabClient); all raw GitLab API calls
  models.py                — Pydantic models for GitLabProject, GitLabIssue, GitLabMergeRequest
services/
  gitlab_service.py        — Orchestration layer; called by tool handlers; shapes responses
  local_ai_service.py      — Ollama client; scrubs secrets before sending; used by triage/summarise/privacy tools
  review_digest.py         — Pure, no-I/O helpers for normalising MR discussions and building digests
tools/                     — One file per domain; each registers handlers with mcp via register_*_tools(mcp)
  _utils.py                — Shared helpers (URL resolution, error formatting)
  exceptions.py            — Structured error types for tool handlers (GitLabToolError, MissingIdentifierError, GitLabApiError)
  ci_cd.py
  issues.py
  merge_requests.py
  projects.py
  repository.py
  search.py
  security.py
tests/                     — pytest unit tests (no network required)
  conftest.py              — Bootstraps test env with dummy GITLAB_URL and GITLAB_TOKEN
  test_gitlab_client.py    — Client utility tests (URL parsing, project ID encoding)
  test_review_digest.py    — Review digest pure-function tests
  test_diff_position.py    — Async diff position builder tests
scripts/
  run_mcp.sh               — Launcher used by all AI CLIs; checks .env, auto-starts container, execs server.py
  install.sh               — Interactive installer (validates token, builds, registers)
  quick-install.sh         — One-liner entrypoint (clone + run install.sh)
  update.sh                — Pull latest code, rebuild container, keep .env backup
  status.sh                — Container health, GitLab connectivity, AI CLI registrations
  logs.sh                  — Tail container logs
  uninstall.sh             — Clean removal (stop container + unregister)
mcp-configs/               — Global MCP config templates for Kimi, Claude, Codex, Gemini
.github/workflows/
  ci.yml                   — GitHub Actions: ruff lint/format check, mypy, pytest, smoke test, docker-smoke
  docker.yml               — GitHub Actions: build and push image to GHCR on version tags
run_tests.py               — Smoke test script (checks tool/prompt registration, no live GitLab needed)
Makefile                   — Common dev tasks (check, coverage, docker-build, etc.)
.pre-commit-config.yaml    — Pre-commit hooks (ruff, mypy)
```

---

## Architecture and Design Decisions

### Layered Call Path

```
Tool handler (tools/*.py)
    ↓
GitLabService (services/gitlab_service.py)
    ↓
GitLabClient (gitlab/client.py)
    ↓
GitLab REST API v4
```

**Tools must NOT call `GitLabClient` directly.** This keeps response shaping and business logic in one place.

### Singleton `GitLabClient`

- `GitLabClient.get_instance()` returns a shared async `httpx` client with HTTP/2, a 100-connection pool, and exponential-backoff retry.
- Never instantiate `GitLabClient()` directly in tools — always use `await GitLabClient.get_instance()`.
- Configurable via `GITLAB_MAX_RETRIES` (default 3) and `GITLAB_RETRY_DELAY` (default 1.0s).
- Maintains two clients:
  - `self.client` — for API calls with `PRIVATE-TOKEN` header
  - `self.web_client` — for web routes (uploads, raw files) without auth header to avoid conflicting auth schemes
- Proactive connection warmup runs in the background on first `get_instance()` call.

### `GitLabService` Per-Call Instantiation

Tools always construct a fresh service per handler invocation:

```python
client = await GitLabClient.get_instance()
service = GitLabService(client)
```

`GitLabService.__init__` also creates a `LocalAIService`, so do **not** hold service instances across calls.

### Response Contract

Every `GitLabService` method returns a dict with this exact shape:

```python
{
    "summary": str,
    "key_findings": list[str],
    "details": dict,
    "next_action": str,
}
```

New service methods must follow this shape.

### URL or IDs

Most tool handlers accept either a full GitLab URL or explicit `project_id` + resource IID. Use:

```python
p_id, res_id = service.resolve_url_or_ids(url, project_id, resource_id)
```

`GitLabClient.parse_gitlab_url()` does the URL parsing; `parse_mr_diff_url()` handles diff anchor URLs.

### `project_id` Encoding

`GitLabClient._format_project_id()` URL-encodes `"group/subgroup/project"` path strings. All client methods accept `int | str` for project IDs.

### Pagination

Use `client.get_all(endpoint, limit=N)` for paginated endpoints (follows `X-Next-Page`). Pass `limit=` to avoid fetching unbounded lists.

### Retry and Rate-Limiting

The central `_request()` method retries on:
- HTTP 429 (Too Many Requests) — respects `Retry-After` header
- 5xx server errors
- Network/request errors

Wait time uses exponential backoff: `retry_delay * (2 ** attempt)`.

### Local AI (Optional)

`LocalAIService` gracefully degrades: if Ollama is unreachable it returns an error string, so all other tools remain functional.

`scrub_secrets()` runs on every payload before it reaches Ollama. It redacts:
- IPv4 addresses
- GitLab tokens (`glpat-...`)
- AWS access keys (`AKIA...`)
- AWS secret keys
- Generic password/secret/token assignments
- Long hex strings (potential keys)

### Bundle Tools

Several high-performance tools fetch multiple resources in parallel and return compact summaries to reduce token usage:
- `bundle_merge_request_context` — MR details + discussions + diffs
- `bundle_issue_context` — issue details + notes + related MRs
- `bundle_project_intelligence` — project details + pipelines + open MRs + open issues
- `bundle_pipeline_context` — pipeline details + jobs + failed job analysis

### Review Digest Helpers

`services/review_digest.py` contains pure, no-I/O functions for normalising discussions, building summaries, and generating suggested replies. These are tested without mocking.

---

## Code Style Guidelines

- **Formatter/Linter**: `ruff` (configured in `pyproject.toml`)
- **Line length**: 100
- **Target Python**: 3.12
- **Enabled rules**: `E`, `F`, `I`, `N`, `UP`, `ASYNC`
- **Ignored rules**: `E501` (line-too-long) — unavoidable in f-string prompt templates and long error messages
- **Type hints**: Used throughout. `mypy` is run in CI but `disallow_untyped_defs = False`.
- **Module-level imports**: Prefer top-level imports. Do not import `config` or tool modules at the top level of test files (see `tests/conftest.py` rationale below).
- **Commit messages**: Follow conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`).

---

## Build and Test Commands

### Host Development

```bash
# Install dependencies (uv is used as the package manager)
pip install -e ".[dev]"   # or: uv pip install -e ".[dev]"

# Lint
ruff check .

# Auto-format
ruff format .

# Check formatting without modifying
ruff format --check .

# Type check
mypy .

# Unit tests
python -m pytest -q
# single test file:
python -m pytest tests/test_gitlab_client.py -v
# single test by name:
python -m pytest tests/test_review_digest.py -v -k "test_name"

# Tests with coverage
python -m pytest --cov=gitlab --cov=services --cov=tools --cov-report=term-missing

# Smoke test (no live GitLab needed)
python run_tests.py

# Full check suite (lint + format + types + tests + smoke)
make check

# See all available commands
make help
```

### Pre-commit Hooks

```bash
pre-commit install
pre-commit run --all-files
```

### Docker

```bash
# Core only
docker compose up -d --build

# With Ollama (CPU)
docker compose --profile ollama up -d --build

# With Ollama (GPU)
docker compose --profile ollama -f docker-compose.yml -f docker-compose.gpu.yml up -d --build

# Verify
docker compose exec gitlab-ai-mcp python run_tests.py
```

---

## Testing Instructions

- **Framework**: pytest + pytest-asyncio
- **No network required**: All unit tests mock `httpx` responses or test pure functions.
- **Test env bootstrap**: `tests/conftest.py` sets `GITLAB_URL` and `GITLAB_TOKEN` environment variables before any project import so the `Settings` singleton never reads a local `.env` during tests.
- **Smoke test**: `run_tests.py` verifies singleton initialisation, tool registration, and prompt registration without calling GitLab.
- **CI**: GitHub Actions runs `ruff check .`, `ruff format --check .`, `mypy .`, `pytest -q`, and `python run_tests.py` on every push/PR. A separate `docker-smoke` job builds the image and runs smoke tests inside the container.

---

## Environment Variables

All settings are read from `.env` (see `.env.example` for template):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITLAB_URL` | **Yes** | — | Base URL of your GitLab instance |
| `GITLAB_TOKEN` | **Yes** | — | Personal Access Token (`api` scope) |
| `DEBUG` | No | `false` | Enable verbose console logging |
| `LOCAL_AI_URL` | No | `http://localhost:11434` | Ollama endpoint (overridden to `http://ollama:11434` in Docker Compose) |
| `LOCAL_AI_MODEL` | No | `llama3.1:8b` | Ollama model name |
| `GITLAB_MAX_RETRIES` | No | `3` | API retry attempts on failure |
| `GITLAB_RETRY_DELAY` | No | `1.0` | Base delay between retries (seconds) |

---

## Security Considerations

- **GitLab Token**: Stored in `.env` and passed as `PRIVATE-TOKEN` header. Never log the raw token.
- **URL Redaction**: `GitLabClient._redact_url()` strips `private_token` query params from logged URLs.
- **Secret Scrubbing**: `LocalAIService.scrub_secrets()` redacts sensitive patterns before any data is sent to the local Ollama model.
- **Upload Auth Fallback**: `fetch_upload()` appends the private token as a query parameter for GitLab upload routes (which do not accept the `PRIVATE-TOKEN` header) and falls back to anonymous access if CDN redirects strip auth.
- **No External AI Calls**: All AI-powered features (triage, summarisation, privacy scan) use the locally-hosted Ollama instance. No data is sent to third-party AI APIs.

---

## Adding a New Tool

1. Pick the right domain file in `tools/` (or create one if the domain is new).
2. Add an async handler that calls `GitLabService`; decorate with `@mcp.tool()`.
3. Register the handler inside `register_*_tools(mcp)` in the same file.
4. If the operation needs a new GitLab API call, add a method to `GitLabClient` first, then expose it via `GitLabService`.
5. Add a unit test in `tests/` (mock `httpx` responses; no live GitLab required).
6. If you add a new `tools/*.py` file, import and register it in `server.py`.
7. Update `AGENTS.md` if you change architecture or conventions.

---

## Deployment

The project is designed to run as a **global** MCP server inside a Docker container:

- **Base image**: `python:3.12-slim`
- **Pre-built images**: Published to `ghcr.io/wafiy-firdaus/gitlab-ai-mcp:latest` on version tags
- **Launcher**: `scripts/run_mcp.sh` is path-agnostic and auto-starts the container before exec'ing `server.py`
- **AI CLI Registration**: `scripts/install.sh` detects Kimi, Claude, Codex, and Gemini CLIs and registers the server globally
- **Ollama Sidecar**: Optional; enabled via `--profile ollama` in Docker Compose. GPU support via `docker-compose.gpu.yml`
