"""Shared utilities for MCP tool handlers."""

from typing import Any

from services.gitlab_service import GitLabService
from tools.exceptions import MissingIdentifierError


def resolve_ids_or_fail(
    service: GitLabService,
    url: str | None,
    project_id: int | str | None,
    resource_id: int | None,
    resource_name: str = "resource",
) -> tuple[int | str, int | str] | dict[str, Any]:
    """
    Resolve URL or explicit IDs. Returns (project_id, resource_id) on success,
    or an error dict if resolution fails.
    """
    p_id, r_id = service.resolve_url_or_ids(url, project_id, resource_id)
    if p_id is None or r_id is None:
        return MissingIdentifierError(resource_name).to_dict()
    return p_id, r_id
