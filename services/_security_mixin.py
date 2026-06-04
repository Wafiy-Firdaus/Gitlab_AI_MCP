from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gitlab.client import GitLabClient
    from services.local_ai_service import LocalAIService


class _SecurityMixin:
    """Security scanning and local-AI triage methods for GitLabService."""

    client: GitLabClient
    local_ai: LocalAIService

    async def list_vulnerability_findings(
        self,
        project_id: int | str,
        severity: list[str] | None = None,
        report_type: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        List and format vulnerability findings for a project.
        """
        findings = await self.client.list_vulnerability_findings(project_id, severity, report_type)

        summary = f"Found {len(findings)} vulnerability findings for project {project_id}"
        key_findings = [
            f"[{f.get('severity', 'UNKNOWN')}] {f.get('name', 'Unnamed Finding')} - {f.get('location', {}).get('file', 'Unknown location')}"
            for f in findings[:10]
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"findings": findings},
            "next_action": "Analyze a specific vulnerability or use Local AI to propose a security fix.",
        }

    async def get_vulnerability_details(
        self, project_id: int | str, vulnerability_id: int
    ) -> dict[str, Any]:
        vuln = await self.client.get_vulnerability_details(project_id, vulnerability_id)

        summary = f"Details for Vulnerability {vulnerability_id}: {vuln.get('title')}"
        key_findings = [
            f"Severity: {vuln.get('severity')}",
            f"Confidence: {vuln.get('confidence')}",
            f"Status: {vuln.get('state')}",
            f"Location: {vuln.get('location', {}).get('file')}:{vuln.get('location', {}).get('line')}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": vuln,
            "next_action": "Review the code location and propose a remediation plan.",
        }

    async def list_project_dependencies(self, project_id: int | str) -> dict[str, Any]:
        deps = await self.client.list_project_dependencies(project_id)

        summary = f"Project {project_id} has {len(deps)} identified dependencies"

        # Count vulnerable dependencies
        vulnerable = [d for d in deps if d.get("vulnerabilities")]

        key_findings = [
            f"Total Dependencies: {len(deps)}",
            f"Vulnerable Dependencies: {len(vulnerable)}",
            f"Sample: {', '.join([d['name'] for d in deps[:5]])}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"dependencies": deps},
            "next_action": "Focus on remediating the vulnerable dependencies first.",
        }

    async def list_audit_events(self, project_id: int | str) -> dict[str, Any]:
        events = await self.client.list_audit_events(project_id)

        summary = f"Retrieved {len(events)} audit events for project {project_id}"
        key_findings = [
            f"[{e.get('created_at')}] {e.get('author_name')}: {e.get('details', {}).get('custom_message', 'No message')}"
            for e in events[:10]
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"audit_events": events},
            "next_action": "Check for unauthorized permission changes or sensitive configuration modifications.",
        }

    async def triage_job_log_locally(
        self, project_id: int | str, job_id: int | str
    ) -> dict[str, Any]:
        """
        [PHASE 2.1] Fetches a massive job log and uses a LOCAL AI to summarize it.
        Saves tokens by only sending the local AI's summary to Claude.
        """
        log_content = await self.client.get_job_log(project_id, job_id)

        # Call local AI for triage
        local_summary = await self.local_ai.triage_job_log(job_id, log_content)

        summary = f"Locally triaged job {job_id} using {self.local_ai.model}"
        key_findings = [
            "Log triaged locally (0 token cost for Expert AI)",
            f"Model used: {self.local_ai.model}",
            "Secret scrubbing applied automatically",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"local_ai_analysis": local_summary},
            "next_action": "Review the local summary. If more detail is needed, use analyze_failed_job.",
        }

    async def analyze_failed_job(self, project_id: int | str, job_id: int | str) -> dict[str, Any]:
        """
        Surgical extraction of error patterns from a failed job log.
        This tool uses regular expressions to find common failure patterns
        and then uses Local AI to provide a high-level summary.
        """
        log_content = await self.client.get_job_log(project_id, job_id)

        # Look for common error patterns (Python, JS, Go, etc.)
        error_patterns = [
            r"error: .*",
            r"fail: .*",
            r"Exception: .*",
            r"Stacktrace: .*",
            r"FATAL: .*",
            r"ERROR: .*",
        ]

        matches = []
        for pattern in error_patterns:
            matches.extend(re.findall(pattern, log_content, re.IGNORECASE))

        # Also get the last 50 lines for context
        log_lines = log_content.splitlines()
        tail = "\n".join(log_lines[-50:])

        # Triage locally
        local_analysis = await self.local_ai.triage_job_log(job_id, log_content)

        summary = f"Analyzed failed job {job_id}"
        key_findings = [
            f"Found {len(matches)} potential error lines",
            "Extracted tail context",
            f"Local AI summary provided by {self.local_ai.model}",
        ]

        # Scrub secrets from error lines and tail context before returning
        scrubbed_lines = []
        for line in matches[:10]:
            scrubbed_lines.append(self.local_ai.scrub_secrets(line))
        scrubbed_tail = self.local_ai.scrub_secrets(tail)

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {
                "error_lines": scrubbed_lines,
                "tail_context": scrubbed_tail,
                "local_ai_summary": local_analysis,
            },
            "next_action": "Evaluate the error lines and local summary to propose a fix.",
        }
