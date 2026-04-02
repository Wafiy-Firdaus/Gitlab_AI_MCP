from typing import Any

from mcp.server.fastmcp import FastMCP

from gitlab.client import GitLabClient
from services.gitlab_service import GitLabService


def register_search_tools(mcp: FastMCP):
    @mcp.tool()
    async def search_users(search: str) -> dict[str, Any]:
        """
        Search for GitLab users by name, username, or email.
        Useful for finding user IDs for assignments.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.search_users(search)

    @mcp.tool()
    async def search_code(project_id: int, search: str) -> dict[str, Any]:
        """
        Search for a string in the project's code (blobs).
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.search_code(project_id, search)

    @mcp.tool()
    async def global_search(scope: str, search: str) -> dict[str, Any]:
        """
        Global search across GitLab.
        Scope can be: 'projects', 'issues', 'merge_requests', 'milestones', 'users'.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.global_search(scope, search)
