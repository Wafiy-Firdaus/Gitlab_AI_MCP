from typing import Any

from mcp.server.fastmcp import FastMCP

from gitlab.client import GitLabClient
from services.gitlab_service import GitLabService


def register_ci_cd_tools(mcp: FastMCP):
    @mcp.tool()
    async def list_project_pipelines(project_id: int | str) -> dict[str, Any]:
        """
        List recent pipelines for a project.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_pipelines(project_id)

    @mcp.tool()
    async def get_pipeline_details(project_id: int | str, pipeline_id: int) -> dict[str, Any]:
        """
        Get detailed information about a specific pipeline.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_pipeline_details(project_id, pipeline_id)

    @mcp.tool()
    async def trigger_pipeline(
        project_id: int | str, ref: str, variables: list[dict[str, str]] | None = None
    ) -> dict[str, Any]:
        """
        Trigger a new pipeline for a specific branch or tag.
        'variables' should be a list of key-value pairs, e.g., [{"key": "VAR1", "value": "VAL1"}].
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.trigger_pipeline(project_id, ref, variables)

    @mcp.tool()
    async def list_pipeline_jobs(project_id: int | str, pipeline_id: int) -> dict[str, Any]:
        """
        List all jobs for a specific pipeline.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_pipeline_jobs(project_id, pipeline_id)

    @mcp.tool()
    async def get_job_log(project_id: int | str, job_id: int) -> dict[str, Any]:
        """
        Get the tail (last 100 lines) of a job's trace log.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_job_log(project_id, job_id)

    @mcp.tool()
    async def analyze_failed_job(
        project_id: int | str | None = None, job_id: int | None = None, url: str | None = None
    ) -> dict[str, Any]:
        """
        Specialized tool to analyze a failed job's log.
        Supports full GitLab job URL or explicit IDs.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        p_id, j_id = service.resolve_url_or_ids(url, project_id, job_id)
        if p_id is None or j_id is None:
            return {"error": "Missing project_id/job_id or valid URL"}
        return await service.analyze_failed_job(p_id, j_id)

    @mcp.tool()
    async def get_pipeline_bridges(project_id: int | str, pipeline_id: int) -> dict[str, Any]:
        """
        List bridge jobs (parent/child pipelines) for a specific pipeline.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_pipeline_bridges(project_id, pipeline_id)

    @mcp.tool()
    async def retry_job(project_id: int | str, job_id: int) -> dict[str, Any]:
        """
        Retry a specific CI/CD job.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.retry_job(project_id, job_id)

    @mcp.tool()
    async def retry_pipeline(project_id: int | str, pipeline_id: int) -> dict[str, Any]:
        """
        Retry all failed jobs in a pipeline.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.retry_pipeline(project_id, pipeline_id)

    @mcp.tool()
    async def cancel_pipeline(project_id: int | str, pipeline_id: int) -> dict[str, Any]:
        """
        Cancel a running pipeline.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.cancel_pipeline(project_id, pipeline_id)

    @mcp.tool()
    async def cancel_job(project_id: int | str, job_id: int) -> dict[str, Any]:
        """
        Cancel a running CI/CD job.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.cancel_job(project_id, job_id)

    @mcp.tool()
    async def play_job(project_id: int | str, job_id: int) -> dict[str, Any]:
        """
        Trigger a manual CI/CD job to run.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.play_job(project_id, job_id)

    @mcp.tool()
    async def get_job_artifact_file(
        project_id: int | str, job_id: int, artifact_path: str
    ) -> dict[str, Any]:
        """
        Read a specific file from a job's artifacts.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_job_artifact_file(project_id, job_id, artifact_path)

    @mcp.tool()
    async def get_job_artifacts_archive(project_id: int | str, job_id: int) -> dict[str, Any]:
        """
        Download the entire artifacts archive (zip) for a job.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_job_artifacts_archive(project_id, job_id)

    @mcp.tool()
    async def list_project_environments(project_id: int | str) -> dict[str, Any]:
        """
        List all deployment environments for a project.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_project_environments(project_id)

    @mcp.tool()
    async def triage_job_log_locally(project_id: int | str, job_id: int) -> dict[str, Any]:
        """
        [PHASE 2.1] Fetch a large job log and use a LOCAL AI (Ollama) to find the error.
        Extremely token-efficient way to debug long pipelines.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.triage_job_log_locally(project_id, job_id)

    @mcp.tool()
    async def list_project_variables(project_id: int | str) -> dict[str, Any]:
        """
        List all CI/CD variables defined for a project.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_project_variables(project_id)

    @mcp.tool()
    async def create_project_variable(
        project_id: int | str,
        key: str,
        value: str,
        variable_type: str = "env_var",
        protected: bool = False,
        masked: bool = False,
    ) -> dict[str, Any]:
        """
        Create a new CI/CD variable for a project.
        'variable_type' can be 'env_var' or 'file'.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.create_project_variable(
            project_id, key, value, variable_type, protected, masked
        )

    @mcp.tool()
    async def update_project_variable(
        project_id: int | str,
        key: str,
        value: str | None = None,
        variable_type: str | None = None,
        protected: bool | None = None,
        masked: bool | None = None,
    ) -> dict[str, Any]:
        """
        Update an existing CI/CD variable for a project.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.update_project_variable(
            project_id, key, value, variable_type, protected, masked
        )

    @mcp.tool()
    async def delete_project_variable(project_id: int | str, key: str) -> dict[str, Any]:
        """
        Delete a CI/CD variable from a project.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.delete_project_variable(project_id, key)

    @mcp.tool()
    async def bundle_pipeline_context(project_id: int | str, pipeline_id: int) -> dict[str, Any]:
        """
        High-performance tool that bundles pipeline details, jobs, and failure analysis.
        Saves tokens by providing a compact, summarized context in one call.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.bundle_pipeline_context(project_id, pipeline_id)
