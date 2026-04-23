"""Structured error types for MCP tool handlers."""

from typing import Any


class GitLabToolError(Exception):
    """Base exception for GitLab MCP tools."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": f"Error: {self.message}",
            "key_findings": [self.message],
            "details": self.details,
            "next_action": "Check your inputs and try again.",
        }


class MissingIdentifierError(GitLabToolError):
    """Raised when a required project/resource ID is missing."""

    def __init__(self, resource: str = "resource"):
        super().__init__(f"Missing project_id or {resource}_id, or valid URL")


class GitLabApiError(GitLabToolError):
    """Raised when the GitLab API returns an unexpected error."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, details={"status_code": status_code} if status_code else {})
