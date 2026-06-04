from typing import Any

from mcp.server.fastmcp import FastMCP

from gitlab.client import GitLabClient
from services.gitlab_service import GitLabService
from tools._annotations import READ_ONLY, WRITE_DESTRUCTIVE


def register_project_tools(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def get_current_user() -> dict[str, Any]:
        """
        Get details of the currently authenticated GitLab user.
        Useful for identifying the current user ID and permissions.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_current_user()

    @mcp.tool(annotations=READ_ONLY)
    async def ping_gitlab() -> dict[str, Any]:
        """
        Check connectivity to the GitLab instance.
        Returns basic system status, current user info, and GitLab version.
        """
        try:
            client = await GitLabClient.get_instance()
            service = GitLabService(client)
            return await service.ping_gitlab()
        except Exception as exc:
            return {
                "summary": "GitLab connection failed",
                "key_findings": [str(exc)],
                "details": {"error": str(exc)},
                "next_action": "Check GITLAB_URL and GITLAB_TOKEN in your .env file.",
            }

    @mcp.tool(annotations=READ_ONLY)
    async def list_projects(
        search: str | None = None,
        group_id: int | str | None = None,
        fields: list[str] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """
        List all projects accessible to the user.
        Optional 'search' parameter to filter by name.
        Optional 'group_id' or 'group_path' to filter by group.
        'fields' is an optional list of fields to include (default: id, name, path, default_branch).
        'limit' restricts the number of projects returned (default: 20).
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_projects(
            search=search, group_id=group_id, fields=fields, limit=limit
        )

    @mcp.tool(annotations=READ_ONLY)
    async def list_group_projects(
        group_id: int | str, fields: list[str] | None = None, limit: int = 20
    ) -> dict[str, Any]:
        """
        List all projects within a specific group.
        'group_id' can be the group's numeric ID or its full path (e.g., 'group/subgroup').
        'fields' is an optional list of fields to include (default: id, name, path, default_branch).
        'limit' is an optional parameter to restrict the number of projects returned (default: 20).
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_group_projects(group_id, fields=fields, limit=limit)

    @mcp.tool(annotations=READ_ONLY)
    async def get_project_details(project_id: int | str) -> dict[str, Any]:
        """
        Get metadata for a specific project.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_project_details(project_id)

    @mcp.tool(annotations=READ_ONLY)
    async def list_project_issues(project_id: int | str, state: str = "opened") -> dict[str, Any]:
        """
        List issues for a project. 'state' can be 'opened' or 'closed'.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_project_issues(project_id, state=state)

    @mcp.tool(annotations=READ_ONLY)
    async def list_project_merge_requests(
        project_id: int | str, state: str = "opened"
    ) -> dict[str, Any]:
        """
        List merge requests for a project. 'state' can be 'opened', 'closed', or 'merged'.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_project_merge_requests(project_id, state=state)

    @mcp.tool(annotations=READ_ONLY)
    async def list_project_labels(project_id: int | str) -> dict[str, Any]:
        """
        List all labels defined in a project.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_project_labels(project_id)

    @mcp.tool(annotations=WRITE_DESTRUCTIVE)
    async def create_project_label(
        project_id: int | str, name: str, color: str, description: str | None = None
    ) -> dict[str, Any]:
        """
        Create a new label for a project.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.create_project_label(project_id, name, color, description)

    @mcp.tool(annotations=READ_ONLY)
    async def list_project_members(
        project_id: int | str, query: str | None = None
    ) -> dict[str, Any]:
        """
        List members of a project and their access levels.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_project_members(project_id, query)

    @mcp.tool(annotations=READ_ONLY)
    async def bundle_project_intelligence(project_id: int | str) -> dict[str, Any]:
        """
        High-performance tool that bundles project details, recent pipelines,
        open MRs, and open issues to provide a high-level dashboard.
        Saves tokens by providing a compact, summarized context in one call.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.bundle_project_intelligence(project_id)
