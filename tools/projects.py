from typing import Any

from mcp.server.fastmcp import FastMCP

from gitlab.client import GitLabClient
from services.gitlab_service import GitLabService


def register_project_tools(mcp: FastMCP):
    @mcp.tool()
    async def get_current_user() -> dict[str, Any]:
        """
        Get details of the currently authenticated GitLab user.
        Useful for identifying the current user ID and permissions.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_current_user()

    @mcp.tool()
    async def list_projects(search: str | None = None) -> dict[str, Any]:
        """
        List all projects accessible to the user.
        Optional 'search' parameter to filter by name.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_projects(search=search)

    @mcp.tool()
    async def get_project_details(project_id: int) -> dict[str, Any]:
        """
        Get metadata for a specific project.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_project_details(project_id)

    @mcp.tool()
    async def list_project_issues(project_id: int, state: str = "opened") -> dict[str, Any]:
        """
        List issues for a project. 'state' can be 'opened' or 'closed'.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_project_issues(project_id, state=state)

    @mcp.tool()
    async def list_project_merge_requests(project_id: int, state: str = "opened") -> dict[str, Any]:
        """
        List merge requests for a project. 'state' can be 'opened', 'closed', or 'merged'.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_project_merge_requests(project_id, state=state)

    @mcp.tool()
    async def list_project_labels(project_id: int | str) -> dict[str, Any]:
        """
        List all labels defined in a project.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_project_labels(project_id)

    @mcp.tool()
    async def create_project_label(project_id: int | str, name: str, color: str, description: str | None = None) -> dict[str, Any]:
        """
        Create a new label for a project.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.create_project_label(project_id, name, color, description)

    @mcp.tool()
    async def list_project_members(project_id: int | str, query: str | None = None) -> dict[str, Any]:
        """
        List members of a project and their access levels.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_project_members(project_id, query)
