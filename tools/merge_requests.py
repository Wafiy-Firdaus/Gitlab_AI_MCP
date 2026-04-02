from typing import Any

from mcp.server.fastmcp import FastMCP

from gitlab.client import GitLabClient
from services.gitlab_service import GitLabService


def register_merge_request_tools(mcp: FastMCP):
    @mcp.tool()
    async def get_merge_request_details(
        project_id: int | str | None = None, 
        mr_iid: int | None = None,
        url: str | None = None
    ) -> dict[str, Any]:
        """
        Get detailed information about a merge request.
        You can either provide a full GitLab URL or explicit project_id and mr_iid.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        p_id, m_iid = service.resolve_url_or_ids(url, project_id, mr_iid)
        if p_id is None or m_iid is None:
            return {"error": "Missing project_id/mr_iid or valid URL"}
        return await service.get_merge_request_details(p_id, m_iid)

    @mcp.tool()
    async def create_merge_request(
        project_id: int | str,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str | None = None,
        assignee_id: int | None = None,
        reviewer_ids: list[int] | None = None,
        labels: str | None = None,
        remove_source_branch: bool = True
    ) -> dict[str, Any]:
        """
        Create a new merge request.
        'labels' should be a comma-separated string.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.create_merge_request(
            project_id=project_id,
            source_branch=source_branch,
            target_branch=target_branch,
            title=title,
            description=description,
            assignee_id=assignee_id,
            reviewer_ids=reviewer_ids,
            labels=labels,
            remove_source_branch=remove_source_branch
        )

    @mcp.tool()
    async def update_merge_request(
        project_id: int | str, 
        mr_iid: int, 
        title: str | None = None,
        description: str | None = None,
        labels: str | None = None,
        assignee_ids: list[int] | None = None,
        reviewer_ids: list[int] | None = None,
        milestone_id: int | None = None,
        state_event: str | None = None,
        target_branch: str | None = None
    ) -> dict[str, Any]:
        """
        Update an existing merge request.
        'labels' should be a comma-separated string.
        'state_event' can be 'close' or 'reopen'.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.update_merge_request(
            project_id, 
            mr_iid, 
            title=title,
            description=description,
            labels=labels,
            assignee_ids=assignee_ids,
            reviewer_ids=reviewer_ids,
            milestone_id=milestone_id,
            state_event=state_event,
            target_branch=target_branch
        )

    @mcp.tool()
    async def approve_merge_request(project_id: int | str, mr_iid: int) -> dict[str, Any]:
        """
        Approve a specific merge request.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.approve_merge_request(project_id, mr_iid)

    @mcp.tool()
    async def get_merge_request_notes(
        project_id: int | str | None = None, 
        mr_iid: int | None = None,
        url: str | None = None
    ) -> dict[str, Any]:
        """
        List comments and discussions for a merge request.
        Supports full URL or explicit IDs.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        p_id, m_iid = service.resolve_url_or_ids(url, project_id, mr_iid)
        return await service.list_merge_request_notes(p_id, m_iid)

    @mcp.tool()
    async def create_merge_request_note(project_id: int | str, mr_iid: int, body: str) -> dict[str, Any]:
        """
        Post a new comment to a merge request.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.create_merge_request_note(project_id, mr_iid, body)

    @mcp.tool()
    async def update_merge_request_note(project_id: int | str, mr_iid: int, note_id: int, body: str) -> dict[str, Any]:
        """
        Update an existing comment on a merge request.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.update_note(project_id, "merge_requests", mr_iid, note_id, body)

    @mcp.tool()
    async def delete_merge_request_note(project_id: int | str, mr_iid: int, note_id: int) -> dict[str, Any]:
        """
        Delete a comment from a merge request.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.delete_note(project_id, "merge_requests", mr_iid, note_id)

    @mcp.tool()
    async def get_merge_request_diffs(
        project_id: int | str | None = None, 
        mr_iid: int | None = None,
        url: str | None = None
    ) -> dict[str, Any]:
        """
        View code changes (diffs) for a merge request.
        Supports full URL or explicit IDs.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        p_id, m_iid = service.resolve_url_or_ids(url, project_id, mr_iid)
        return await service.get_merge_request_diffs(p_id, m_iid)

    @mcp.tool()
    async def get_merge_request_discussions(project_id: int | str, mr_iid: int) -> dict[str, Any]:
        """
        List all discussions (threads) for a merge request.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_merge_request_discussions(project_id, mr_iid)

    @mcp.tool()
    async def add_merge_request_discussion_note(project_id: int | str, mr_iid: int, discussion_id: str, body: str) -> dict[str, Any]:
        """
        Reply to an existing discussion thread on a merge request.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.add_merge_request_discussion_note(project_id, mr_iid, discussion_id, body)

    @mcp.tool()
    async def create_merge_request_discussion(
        project_id: int | str, 
        mr_iid: int, 
        body: str, 
        position: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Create a new discussion thread on a merge request.
        Can be used for inline diff comments by providing 'position'.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.create_merge_request_discussion(project_id, mr_iid, body, position)

    @mcp.tool()
    async def list_merge_request_pipelines(project_id: int | str, mr_iid: int) -> dict[str, Any]:
        """
        List pipelines associated with a merge request.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_merge_request_pipelines(project_id, mr_iid)

    @mcp.tool()
    async def resolve_merge_request_discussion(project_id: int | str, mr_iid: int, discussion_id: str, resolved: bool = True) -> dict[str, Any]:
        """
        Mark a discussion thread as resolved or unresolved.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.resolve_merge_request_discussion(project_id, mr_iid, discussion_id, resolved)

    @mcp.tool()
    async def bundle_merge_request_context(project_id: int | str, mr_iid: int) -> dict[str, Any]:
        """
        [PHASE 1.2] High-performance tool that bundles MR details, discussions, and diffs.
        Saves tokens by providing a compact, summarized context in one call.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.bundle_merge_request_context(project_id, mr_iid)

    @mcp.tool()
    async def merge_merge_request(
        project_id: int | str, 
        mr_iid: int,
        merge_commit_message: str | None = None,
        squash_commit_message: str | None = None,
        squash: bool = False,
        should_remove_source_branch: bool = True,
        merge_when_pipeline_succeeds: bool = False
    ) -> dict[str, Any]:
        """
        [PHASE 3.1] Merge an existing merge request.
        Supports squashing and source branch removal.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.merge_merge_request(
            project_id, 
            mr_iid,
            merge_commit_message=merge_commit_message,
            squash_commit_message=squash_commit_message,
            squash=squash,
            should_remove_source_branch=should_remove_source_branch,
            merge_when_pipeline_succeeds=merge_when_pipeline_succeeds
        )

    @mcp.tool()
    async def rebase_merge_request(project_id: int | str, mr_iid: int) -> dict[str, Any]:
        """
        Rebase a merge request onto the target branch.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.rebase_merge_request(project_id, mr_iid)

    @mcp.tool()
    async def get_merge_request_approvals(project_id: int | str, mr_iid: int) -> dict[str, Any]:
        """
        Check the approval status and required approvals for a merge request.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_merge_request_approvals(project_id, mr_iid)

    @mcp.tool()
    async def summarize_mr_discussions_locally(
        project_id: int | str | None = None,
        mr_iid: int | None = None,
        url: str | None = None
    ) -> dict[str, Any]:
        """
        Use local AI (Ollama) to summarize all reviewer discussions and highlights in an MR.
        Identifies critical concerns and blockers locally for privacy.
        Supports full URL or explicit IDs.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        p_id, m_iid = service.resolve_url_or_ids(url, project_id, mr_iid)
        return await service.summarize_mr_discussions_locally(p_id, m_iid)

    @mcp.tool()
    async def check_mr_privacy_locally(
        project_id: int | str | None = None,
        mr_iid: int | None = None,
        url: str | None = None
    ) -> dict[str, Any]:
        """
        Use local AI (Ollama) to scan MR diffs and description for leaked secrets before merging.
        Look for: API keys, tokens, passwords, and sensitive credentials.
        Analysis is performed 100% locally.
        Supports full URL or explicit IDs.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        p_id, m_iid = service.resolve_url_or_ids(url, project_id, mr_iid)
        return await service.check_mr_privacy_locally(p_id, m_iid)
