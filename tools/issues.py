from typing import Any

from mcp.server.fastmcp import FastMCP

from gitlab.client import GitLabClient
from services.gitlab_service import GitLabService


def register_issue_tools(mcp: FastMCP):
    @mcp.tool()
    async def list_all_issues(state: str = "opened", scope: str = "assigned_to_me") -> dict[str, Any]:
        """
        List all issues across all projects.
        'state' can be 'opened' or 'closed'.
        'scope' can be 'assigned_to_me', 'created_by_me', or 'all'.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_all_issues(state=state, scope=scope)

    @mcp.tool()
    async def get_issue_details(
        project_id: int | str | None = None, 
        issue_iid: int | None = None,
        url: str | None = None
    ) -> dict[str, Any]:
        """
        Get detailed information about an issue.
        Supports full GitLab URL or explicit IDs.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        p_id, i_iid = service.resolve_url_or_ids(url, project_id, issue_iid)
        if p_id is None or i_iid is None:
            return {"error": "Missing project_id/issue_iid or valid URL"}
        return await service.get_issue_details(p_id, i_iid)

    @mcp.tool()
    async def create_issue(
        project_id: int | str,
        title: str,
        description: str | None = None,
        labels: str | None = None,
        assignee_ids: list[int] | None = None,
        milestone_id: int | None = None
    ) -> dict[str, Any]:
        """
        Create a new issue in a project.
        'labels' should be a comma-separated string.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.create_issue(
            project_id,
            title,
            description=description,
            labels=labels,
            assignee_ids=assignee_ids,
            milestone_id=milestone_id
        )

    @mcp.tool()
    async def update_issue(
        project_id: int | str, 
        issue_iid: int, 
        title: str | None = None,
        description: str | None = None,
        labels: str | None = None,
        assignee_ids: list[int] | None = None,
        milestone_id: int | None = None,
        state_event: str | None = None
    ) -> dict[str, Any]:
        """
        Update an existing issue.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.update_issue(
            project_id, 
            issue_iid, 
            title=title,
            description=description,
            labels=labels,
            assignee_ids=assignee_ids,
            milestone_id=milestone_id,
            state_event=state_event
        )

    @mcp.tool()
    async def get_issue_notes(
        project_id: int | str | None = None, 
        issue_iid: int | None = None,
        url: str | None = None
    ) -> dict[str, Any]:
        """
        List comments for an issue.
        Supports full URL or explicit IDs.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        p_id, i_iid = service.resolve_url_or_ids(url, project_id, issue_iid)
        return await service.list_issue_notes(p_id, i_iid)

    @mcp.tool()
    async def create_issue_note(project_id: int | str, issue_iid: int, body: str) -> dict[str, Any]:
        """
        Post a new comment to an issue.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.create_issue_note(project_id, issue_iid, body)

    @mcp.tool()
    async def update_issue_note(project_id: int | str, issue_iid: int, note_id: int, body: str) -> dict[str, Any]:
        """
        Update an existing comment on an issue.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.update_note(project_id, "issues", issue_iid, note_id, body)

    @mcp.tool()
    async def delete_issue_note(project_id: int | str, issue_iid: int, note_id: int) -> dict[str, Any]:
        """
        Delete a comment from an issue.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.delete_note(project_id, "issues", issue_iid, note_id)

    @mcp.tool()
    async def bundle_issue_context(project_id: int | str, issue_iid: int) -> dict[str, Any]:
        """
        High-performance tool that bundles issue details and notes.
        Saves tokens by providing a compact, summarized context in one call.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.bundle_issue_context(project_id, issue_iid)

    @mcp.tool()
    async def triage_issue_locally(
        project_id: int | str | None = None,
        issue_iid: int | None = None,
        url: str | None = None
    ) -> dict[str, Any]:
        """
        Use local AI (Ollama) to analyze an issue description for labels and action items.
        Analysis is performed 100% locally for privacy.
        Supports full URL or explicit IDs.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        p_id, i_iid = service.resolve_url_or_ids(url, project_id, issue_iid)
        return await service.triage_issue_locally(p_id, i_iid)
