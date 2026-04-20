from typing import Any

from mcp.server.fastmcp import FastMCP

from gitlab.client import GitLabClient
from services.gitlab_service import GitLabService


def register_repository_tools(mcp: FastMCP):
    @mcp.tool()
    async def list_repository_files(
        project_id: int | str, path: str = "", ref: str = "main"
    ) -> dict[str, Any]:
        """
        Explore the repository tree at a specific path and reference.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_repository_files(project_id, path=path, ref=ref)

    @mcp.tool()
    async def get_file_content(
        project_id: int | str, file_path: str, ref: str = "main", include_raw: bool = False
    ) -> dict[str, Any]:
        """
        Read the content of a file. Automatically decodes Base64 content.
        Set 'include_raw' to True to include the original base64 content in metadata.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_file_content(
            project_id, file_path, ref=ref, include_raw=include_raw
        )

    @mcp.tool()
    async def get_multiple_files(
        project_id: int | str,
        file_paths: list[str],
        ref: str = "main",
        include_metadata: bool = False,
    ) -> dict[str, Any]:
        """
        Fetch multiple files from a project in a single parallel request.
        Set 'include_metadata' to True to include original Base64 content in metadata.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_multiple_files(
            project_id, file_paths, ref=ref, include_metadata=include_metadata
        )

    @mcp.tool()
    async def create_branch(
        project_id: int | str, branch: str, ref: str = "main"
    ) -> dict[str, Any]:
        """
        Create a new branch in the repository.
        'ref' is the branch name or commit SHA to create the new branch from.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.create_branch(project_id, branch, ref)

    @mcp.tool()
    async def get_branch(project_id: int | str, branch: str) -> dict[str, Any]:
        """
        Get details of a specific branch, including its HEAD commit SHA.
        Useful for pinning Terraform modules or other dependencies to a specific commit.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_branch(project_id, branch)

    @mcp.tool()
    async def get_branches(project_id: int | str, branches: list[str]) -> dict[str, Any]:
        """
        Fetch details for multiple branches in parallel.
        Useful for gathering HEAD SHAs for multiple repositories at once.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_branches(project_id, branches)

    @mcp.tool()
    async def list_repository_tags(project_id: int | str, limit: int = 50) -> dict[str, Any]:
        """
        List all tags in the repository.
        Useful for identifying stable releases or semantic version tags.
        'limit' restricts the number of tags returned (default: 50).
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_repository_tags(project_id, limit=limit)

    @mcp.tool()
    async def create_repository_file(
        project_id: int | str, file_path: str, branch: str, content: str, commit_message: str
    ) -> dict[str, Any]:
        """
        Create a new file in the repository.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.commit_file(
            project_id, file_path, branch, content, commit_message, is_new=True
        )

    @mcp.tool()
    async def update_repository_file(
        project_id: int | str, file_path: str, branch: str, content: str, commit_message: str
    ) -> dict[str, Any]:
        """
        Update an existing file in the repository.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.commit_file(
            project_id, file_path, branch, content, commit_message, is_new=False
        )

    @mcp.tool()
    async def create_batch_commit(
        project_id: int | str,
        branch: str,
        commit_message: str,
        actions: list[dict[str, Any]],
        start_branch: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a batch commit with multiple file actions (create, delete, update, move, chmod).
        'actions' is a list of dicts: [{"action": "create", "file_path": "foo", "content": "bar"}, ...]
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.create_batch_commit(
            project_id, branch, commit_message, actions, start_branch
        )

    @mcp.tool()
    async def list_repository_commits(
        project_id: int | str, ref_name: str | None = None
    ) -> dict[str, Any]:
        """
        List commits for a project or specific branch/ref.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_repository_commits(project_id, ref_name)

    @mcp.tool()
    async def get_commit_details(project_id: int | str, sha: str) -> dict[str, Any]:
        """
        Get detailed information about a specific commit by its SHA.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_commit_details(project_id, sha)

    @mcp.tool()
    async def get_file_blame(
        project_id: int | str, file_path: str, ref: str = "main"
    ) -> dict[str, Any]:
        """
        Get the blame data for a file, showing who changed each line and when.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_file_blame(project_id, file_path, ref)

    @mcp.tool()
    async def get_raw_file_content(
        project_id: int | str | None = None,
        file_path: str | None = None,
        ref: str = "main",
        raw_url: str | None = None,
    ) -> dict[str, Any]:
        """
        Fetch the raw text content of a file from GitLab.
        You can provide either:
        1. 'raw_url': A full GitLab /-/raw/ URL.
        2. 'project_id' + 'file_path' (+ optional 'ref'): For structured API access.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_raw_file_content(project_id, file_path, ref, raw_url)

    @mcp.tool()
    async def fetch_gitlab_upload(upload_url: str) -> dict[str, Any]:
        """
        Fetch an image or file attached to a GitLab comment, issue, or MR.
        Pass the full URL or relative path from the note body
        (e.g. /uploads/abc123/image.png or https://gitlab.example.com/uploads/abc123/image.png).
        Returns base64-encoded content and content-type so images can be displayed inline.
        """
        import base64

        client = await GitLabClient.get_instance()
        content, content_type = await client.fetch_upload(upload_url)

        summary = f"Successfully fetched upload from {upload_url}"
        key_findings = [f"Content Type: {content_type}", f"Size: {len(content)} bytes"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {
                "content_type": content_type,
                "content_base64": base64.b64encode(content).decode("utf-8"),
                "size_bytes": len(content),
            },
            "next_action": "The file content is available in base64 format for display or processing.",
        }
