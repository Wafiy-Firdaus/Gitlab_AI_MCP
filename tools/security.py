from typing import Any

from mcp.server.fastmcp import FastMCP

from gitlab.client import GitLabClient
from services.gitlab_service import GitLabService
from tools._annotations import READ_ONLY


def register_security_tools(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def list_vulnerability_findings(
        project_id: int | str,
        severity: list[str] | None = None,
        report_type: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        List vulnerability findings for a project (SAST, DAST, Secret Detection).
        'severity' can be: info, low, medium, high, critical, unknown.
        'report_type' can be: sast, dast, dependency_scanning, container_scanning, secret_detection.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_vulnerability_findings(project_id, severity, report_type)

    @mcp.tool(annotations=READ_ONLY)
    async def get_vulnerability_details(
        project_id: int | str, vulnerability_id: int
    ) -> dict[str, Any]:
        """
        Get detailed information about a specific vulnerability.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.get_vulnerability_details(project_id, vulnerability_id)

    @mcp.tool(annotations=READ_ONLY)
    async def list_project_dependencies(project_id: int | str) -> dict[str, Any]:
        """
        List all dependencies identified for a project (Supply Chain / SBOM).
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_project_dependencies(project_id)

    @mcp.tool(annotations=READ_ONLY)
    async def list_audit_events(project_id: int | str) -> dict[str, Any]:
        """
        Retrieve audit events for a project to track sensitive changes.
        """
        client = await GitLabClient.get_instance()
        service = GitLabService(client)
        return await service.list_audit_events(project_id)
