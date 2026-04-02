from typing import Any

from mcp.server.fastmcp import FastMCP

from gitlab.client import GitLabClient
from services.gitlab_service import GitLabService


def register_repository_tools(mcp: FastMCP):
    @mcp.tool()
    async def list_repository_files(project_id: int | str, path: str = "", ref: str = "main") -> dict[str, Any]:
        """
        Explore the repository tree at a specific path and reference.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_repository_files(project_id, path=path, ref=ref)

    @mcp.tool()
    async def get_file_content(project_id: int | str, file_path: str, ref: str = "main") -> dict[str, Any]:
        """
        Read the content of a file. Automatically decodes Base64 content.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_file_content(project_id, file_path, ref=ref)

    @mcp.tool()
    async def create_branch(project_id: int | str, branch: str, ref: str = "main") -> dict[str, Any]:
        """
        Create a new branch in the repository.
        'ref' is the branch name or commit SHA to create the new branch from.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.create_branch(project_id, branch, ref)

    @mcp.tool()
    async def create_repository_file(project_id: int | str, file_path: str, branch: str, content: str, commit_message: str) -> dict[str, Any]:
        """
        Create a new file in the repository.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.commit_file(project_id, file_path, branch, content, commit_message, is_new=True)

    @mcp.tool()
    async def update_repository_file(project_id: int | str, file_path: str, branch: str, content: str, commit_message: str) -> dict[str, Any]:
        """
        Update an existing file in the repository.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.commit_file(project_id, file_path, branch, content, commit_message, is_new=False)

    @mcp.tool()
    async def create_batch_commit(
        project_id: int | str, 
        branch: str, 
        commit_message: str, 
        actions: list[dict[str, Any]], 
        start_branch: str | None = None
    ) -> dict[str, Any]:
        """
        Create a batch commit with multiple file actions (create, delete, update, move, chmod).
        'actions' is a list of dicts: [{"action": "create", "file_path": "foo", "content": "bar"}, ...]
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.create_batch_commit(project_id, branch, commit_message, actions, start_branch)

    @mcp.tool()
    async def list_repository_commits(project_id: int | str, ref_name: str | None = None) -> dict[str, Any]:
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
    async def get_file_blame(project_id: int | str, file_path: str, ref: str = "main") -> dict[str, Any]:
        """
        Get the blame data for a file, showing who changed each line and when.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_file_blame(project_id, file_path, ref)

    @mcp.tool()
    async def get_raw_file_content(raw_url: str) -> dict[str, Any]:
        """
        Fetch the raw text content of a file using a GitLab /-/raw/ URL.
        Example: https://gitlab.example.com/group/project/-/raw/main/path/to/file.sh
        Accepts a full URL or a path relative to the GitLab root.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_raw_file_content(raw_url)

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
        key_findings = [
            f"Content Type: {content_type}",
            f"Size: {len(content)} bytes"
        ]
        
        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {
                "content_type": content_type,
                "content_base64": base64.b64encode(content).decode("utf-8"),
                "size_bytes": len(content),
            },
            "next_action": "The file content is available in base64 format for display or processing."
        }
