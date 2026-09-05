# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-09-05

### Security

- Validate every upload redirect target against the configured GitLab host before
  following it or forwarding the private token.

### Fixed

- Paginate merge request diffs so large reviews include all changed files.
- Retry only transient HTTP request errors instead of masking programming errors.
- Declare the `dev` optional dependency group so `pip install -e ".[dev]"` installs
  the complete CI and development toolchain.

## [1.0.0] - 2026-06-04

### Added

- **Service split** — `gitlab_service.py` (2420 lines) refactored into four focused domain mixins:
  `_issue_mixin.py`, `_mr_mixin.py`, `_repo_ci_mixin.py`, `_security_mixin.py`.
  Public API is unchanged; tool files require no updates.
- **Reasonix support** — MCP config template added (`mcp-configs/reasonix.global.json`);
  `install.sh` now auto-detects and registers Reasonix CLI.
- **Test suite** — 187 tests across 12 files (up from ~60). New coverage:
  bundle tools, scrub edge cases, negative-path resolution, model validation, tool handlers.
- `asyncio_mode = "auto"` in `pyproject.toml` — removes `@pytest.mark.asyncio` boilerplate.
- `HEALTHCHECK` instruction added to `Dockerfile`.
- All mixin classes declare `client` and `local_ai` type annotations under `TYPE_CHECKING` for full mypy coverage.

### Changed

- `gitlab_service.py` reduced from 2420 lines to 440 lines (thin facade pattern).
- All `register_*_tools()` functions annotated with `-> None`.
- All `@mcp.tool()` decorators include explicit `annotations=` constant (`READ_ONLY`, `WRITE_IDEMPOTENT`, or `WRITE_DESTRUCTIVE`).
- All list-returning client methods now use `get_all()` with explicit `limit=` — no silent truncation.
- `ref` parameters default to `None` (falls back to `HEAD`) instead of hardcoded `"main"`.
- `scrub_secrets()` is now synchronous (was incorrectly declared `async`).
- All service modules use `structlog` consistently (no plain `logging` calls).
- `datetime.utcnow()` replaced with `datetime.now(UTC)` in tests.
- `_extract_upload_urls` naming consistent across all service modules (no alias).

### Security

- `asyncio.Lock` double-checked locking on `GitLabClient.get_instance()` — fixes concurrent initialisation race condition.
- Docker base image digest-pinned: `python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203`.
- All GitHub Actions SHA-pinned across `ci.yml`, `docker.yml`, and `release.yml`.
- Bandit SAST scan (`-ll -ii`) added as a dedicated CI job.
- `.dockerignore` hardened — blocks `.env`, `.git`, `tests/`, and build artifacts from the Docker image.

### Fixed

- `bundle_pipeline_context` raised `KeyError: 'details'` when a job log fetch failed — fixed with `.get("details")`.
- `list_project_variables`, `list_repository_commits`, `get_file_blame`, and `list_vulnerability_findings`
  were silently truncating results at GitLab's default page size — now fully paginated.
- Dead `import logging` removed from `gitlab_service.py`.
- `_repo_ci_mixin.py` was using `logging.getLogger` for structlog-style keyword arguments — fixed to `structlog.get_logger`.
- `list_project_environments`, `list_project_labels`, `list_project_members`, and `list_pipeline_jobs`
  were using unbounded `get_all()` — now have explicit `limit=` guards.

## [0.5.2] - 2026-04-23

### Added

- Expanded URL parsing to support `work_items`, `epics`, `snippets`, `blob`, `tree`, `commits`, `commit` resource types.
- `bundle_issue_context` and `bundle_merge_request_context` now accept full GitLab URLs via the `url` parameter.
- `AGENTS.md` — project-specific guidance for AI coding agents.
- Shared utilities module (`tools/_utils.py`) for common tool handler patterns.
- Structured error types (`tools/exceptions.py`) for consistent error reporting.
- Diagnostic tool `ping_gitlab` for connectivity health checks.
- Single source of truth for version (`_version.py`).

### Changed

- `fetch_gitlab_upload` reverted to return base64-encoded dict instead of inline `ImageContent`.
- Removed embedded image extraction from issue and MR detail tools.

### Security

- URL redaction in logs — `private_token` query parameters are scrubbed before logging.
- Dedicated `web_client` for upload routes to avoid auth header confusion.

### Fixed

- `GitLabClient.__aexit__` now properly calls `aclose()` to clean up both HTTP clients.
- User-Agent string now dynamically reads from package version.

## [0.4.0] - 2026-04-20

### Added

- One-command install via `scripts/quick-install.sh`.
- Global MCP config templates for Kimi, Claude, Codex, and Gemini.
- Auto-start launcher (`scripts/run_mcp.sh`).
- Docker Compose stack with optional Ollama sidecar.
- Pre-built images published to GHCR.

## [0.3.0] - 2026-04-17

### Added

- Initial MCP tool suite covering projects, issues, merge requests, CI/CD, repository, search, and security.
- Local AI integration via Ollama for job log triage, MR privacy scanning, and discussion summarisation.
- Async HTTP/2 GitLab client with retry logic.
