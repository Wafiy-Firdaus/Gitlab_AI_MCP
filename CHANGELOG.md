# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
