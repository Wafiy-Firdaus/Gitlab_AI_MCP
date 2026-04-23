# Contributing to GitLab AI MCP Server

Thanks for considering a contribution! This document will get you started.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/Wafiy-Firdaus/Gitlab_AI_MCP.git
cd Gitlab_AI_MCP

# Install dependencies (including dev dependencies)
pip install -e ".[dev]"

# Or with uv
uv pip install -e ".[dev]"
```

## Running Checks Locally

Before committing, run the full check suite:

```bash
# Linting
ruff check .

# Formatting
ruff format --check .

# Type checking
mypy .

# Unit tests
python -m pytest -q

# Smoke test
python run_tests.py

# With coverage
python -m pytest --cov=gitlab --cov=services --cov=tools --cov-report=term-missing
```

Alternatively, if you have `pre-commit` installed:

```bash
pre-commit install
pre-commit run --all-files
```

## Project Architecture

```
Tool handler (tools/*.py)
    ↓
GitLabService (services/gitlab_service.py)
    ↓
GitLabClient (gitlab/client.py)
    ↓
GitLab REST API v4
```

**Key rules:**
- Tools must **NOT** call `GitLabClient` directly — always go through `GitLabService`
- Every `GitLabService` method returns a dict with: `summary`, `key_findings`, `details`, `next_action`
- `GitLabClient.get_instance()` returns a shared async HTTP/2 client — never instantiate directly

## Adding a New Tool

1. Pick the right domain file in `tools/` (or create one)
2. Add an async handler that calls `GitLabService`; decorate with `@mcp.tool()`
3. Register the handler inside `register_*_tools(mcp)` in the same file
4. If you need a new GitLab API call, add it to `GitLabClient` first, then expose via `GitLabService`
5. Add a unit test in `tests/` (mock `httpx` responses — no live GitLab needed)
6. If you add a new `tools/*.py` file, import and register it in `server.py`
7. Update `AGENTS.md` if you change architecture or conventions

## Code Style

- **Line length:** 100
- **Target Python:** 3.12
- **Formatter/Linter:** `ruff` (configured in `pyproject.toml`)
- **Type hints:** Required throughout. `mypy` runs in CI.

## Commit Messages

Follow conventional commits:

```
feat: add new tool for listing project variables
fix: handle missing assignees in issue details
docs: update README with GPU setup instructions
refactor: extract shared URL resolution logic
test: add coverage for parse_gitlab_url
```

## Pull Request Process

1. Fork the repo and create a feature branch (`git checkout -b feat/my-feature`)
2. Make your changes and ensure all checks pass (`ruff`, `mypy`, `pytest`)
3. Update `CHANGELOG.md` under the `[Unreleased]` section
4. Open a PR with a clear description of the change and motivation
5. CI must pass before merge

## Questions?

Open an issue or discussion on GitHub. For architecture questions, check `AGENTS.md` first.
