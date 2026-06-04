from __future__ import annotations

import asyncio
import base64
import re
from typing import Any

from gitlab.client import GitLabClient
from services._issue_mixin import _IssueMixin
from services._mr_mixin import _MRMixin
from services._repo_ci_mixin import _RepoCIMixin
from services._security_mixin import _SecurityMixin
from services._utils import (
    _extract_upload_urls,  # noqa: F401
    _is_gitlab_upload_url,  # noqa: F401 — re-exported for backward compat
)
from services.local_ai_service import LocalAIService


class GitLabService(_IssueMixin, _MRMixin, _RepoCIMixin, _SecurityMixin):
    def __init__(self, client: GitLabClient) -> None:
        self.client = client
        self.local_ai = LocalAIService()

    # ------------------------------------------------------------------
    # URL / ID resolution
    # ------------------------------------------------------------------

    def resolve_url_or_ids(
        self, url: str | None, project_id: int | str | None, resource_id: int | None
    ) -> tuple[int | str | None, int | str | None]:
        """
        Helper to resolve either a full URL or explicit IDs.
        Returns (project_id, resource_id).
        """
        if url:
            parsed = self.client.parse_gitlab_url(url)
            if parsed:
                res_id = parsed["resource_id"]
                try:
                    return parsed["project_path"], int(res_id)
                except ValueError:
                    return parsed["project_path"], res_id

        return project_id, resource_id

    # ------------------------------------------------------------------
    # Project / user methods (not in any domain mixin)
    # ------------------------------------------------------------------

    async def list_projects(
        self,
        search: str | None = None,
        group_id: int | str | None = None,
        fields: list[str] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        projects = await self.client.list_projects(search=search, group_id=group_id, limit=limit)

        if fields is None:
            fields = ["id", "name", "path", "default_branch"]

        filtered_projects = []
        for p in projects:
            filtered_projects.append({f: p.get(f) for f in fields if f in p})
        projects = filtered_projects

        summary = f"Found {len(projects)} projects"
        if limit and len(projects) >= limit:
            summary += f" (limited to top {limit})"

        if search:
            summary += f" matching '{search}'"
        if group_id:
            summary += f" in group {group_id}"

        key_findings = [
            f"{p.get('name', 'N/A')} (ID: {p.get('id', 'N/A')}, Path: {p.get('path_with_namespace', p.get('path', 'N/A'))})"
            for p in projects[:5]
        ]
        if len(projects) > 5:
            key_findings.append(f"... and {len(projects) - 5} more")

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"projects": projects},
            "next_action": "Select a project ID to view issues or merge requests.",
        }

    async def list_group_projects(
        self, group_id: int | str, fields: list[str] | None = None, limit: int = 20
    ) -> dict[str, Any]:
        projects = await self.client.list_group_projects(group_id, limit=limit)

        if fields is None:
            fields = ["id", "name", "path", "default_branch"]

        filtered_projects = []
        for p in projects:
            filtered_projects.append({f: p.get(f) for f in fields if f in p})
        projects = filtered_projects

        summary = f"Found {len(projects)} projects in group {group_id}"
        if limit and len(projects) >= limit:
            summary += f" (limited to top {limit})"

        key_findings = [
            f"{p.get('name', 'N/A')} (ID: {p.get('id', 'N/A')}, Path: {p.get('path_with_namespace', p.get('path', 'N/A'))})"
            for p in projects[:10]
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"projects": projects},
            "next_action": "Explore a specific project or its repository.",
        }

    async def get_current_user(self) -> dict[str, Any]:
        user = await self.client.get_current_user()

        summary = f"Authenticated as {user['name']} (@{user['username']})"
        key_findings = [
            f"User ID: {user['id']}",
            f"Email: {user['email']}",
            f"Web URL: {user['web_url']}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": user,
            "next_action": "You can now list issues or projects assigned to you.",
        }

    async def ping_gitlab(self) -> dict[str, Any]:
        """Check connectivity: current user + GitLab version."""
        user = await self.client.get_current_user()
        version_resp = await self.client.get_version()
        version_data = version_resp.json()

        return {
            "summary": f"GitLab {version_data.get('version', 'unknown')} is reachable",
            "key_findings": [
                f"Connected as: {user.get('name', 'unknown')} (@{user.get('username', 'unknown')})",
                f"GitLab version: {version_data.get('version', 'unknown')}",
                f"Revision: {version_data.get('revision', 'unknown')[:8] if version_data.get('revision') else 'unknown'}",
            ],
            "details": {
                "user": user,
                "version": version_data,
            },
            "next_action": "Connection is healthy. You can start using other tools.",
        }

    async def list_all_issues(
        self, state: str = "opened", scope: str = "assigned_to_me"
    ) -> dict[str, Any]:
        issues = await self.client.list_all_issues(state=state, scope=scope)

        summary = f"Found {len(issues)} {state} issues (Scope: {scope})"
        key_findings = [
            f"#{i['iid']} ({i['references']['full']}): {i['title']}" for i in issues[:10]
        ]
        if len(issues) > 10:
            key_findings.append(f"... and {len(issues) - 10} more")

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"issues": issues},
            "next_action": "View details for a specific issue using its project ID and IID.",
        }

    async def get_project_details(self, project_id: int | str) -> dict[str, Any]:
        project = await self.client.get_project(project_id)

        summary = f"Details for project: {project['name']}"
        key_findings = [
            f"Namespace: {project['path_with_namespace']}",
            f"Stars: {project.get('star_count', 0)}",
            f"Forks: {project['forks_count']}",
            f"Last Activity: {project['last_activity_at']}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": project,
            "next_action": "You can list issues, merge requests, or browse files for this project.",
        }

    async def list_project_issues(
        self, project_id: int | str, state: str = "opened"
    ) -> dict[str, Any]:
        issues = await self.client.list_issues(project_id, state=state)

        summary = f"Found {len(issues)} {state} issues for project {project_id}"
        key_findings = [f"#{i['iid']}: {i['title']}" for i in issues[:5]]
        if len(issues) > 5:
            key_findings.append(f"... and {len(issues) - 5} more")

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"issues": issues},
            "next_action": "View a specific issue by providing its IID.",
        }

    async def list_project_merge_requests(
        self, project_id: int | str, state: str = "opened"
    ) -> dict[str, Any]:
        mrs = await self.client.list_merge_requests(project_id, state=state)

        summary = f"Found {len(mrs)} {state} merge requests for project {project_id}"
        key_findings = [
            f"!{mr['iid']}: {mr['title']} ({mr['source_branch']} -> {mr['target_branch']})"
            for mr in mrs[:5]
        ]
        if len(mrs) > 5:
            key_findings.append(f"... and {len(mrs) - 5} more")

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"merge_requests": mrs},
            "next_action": "Review a merge request by providing its IID.",
        }

    async def list_project_labels(self, project_id: int | str) -> dict[str, Any]:
        labels = await self.client.list_project_labels(project_id)

        summary = f"Found {len(labels)} labels for project {project_id}"
        key_findings = [f"{lbl['name']} (Color: {lbl['color']})" for lbl in labels[:10]]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"labels": labels},
            "next_action": "Use these labels for issues or merge requests.",
        }

    async def create_project_label(
        self,
        project_id: int | str,
        name: str,
        color: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        label = await self.client.create_project_label(project_id, name, color, description)

        summary = f"Successfully created label '{name}'"
        key_findings = [
            f"Name: {label['name']}",
            f"Color: {label['color']}",
            f"Description: {label.get('description', 'N/A')}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": label,
            "next_action": "You can now apply this label to resources in the project.",
        }

    async def list_project_members(
        self, project_id: int | str, query: str | None = None
    ) -> dict[str, Any]:
        members = await self.client.list_project_members(project_id, query)

        summary = f"Found {len(members)} members for project {project_id}"
        key_findings = [
            f"{m['name']} (@{m['username']}) - Access Level: {m['access_level']}"
            for m in members[:10]
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"members": members},
            "next_action": "Use member IDs for assignments or mentions.",
        }

    async def bundle_project_intelligence(self, project_id: int | str) -> dict[str, Any]:
        """
        High-performance tool that bundles project details, recent pipelines,
        open MRs, and open issues to provide a high-level dashboard.
        """
        project_task = self.client.get_project(project_id)
        pipelines_task = self.client.list_pipelines(project_id)
        mrs_task = self.client.list_merge_requests(project_id, state="opened")
        issues_task = self.client.list_issues(project_id, state="opened")

        project, pipelines, mrs, issues = await asyncio.gather(
            project_task, pipelines_task, mrs_task, issues_task
        )

        summary = f"Project Intelligence for {project['name']} ({project['path_with_namespace']})"
        key_findings = [
            f"Open Issues: {len(issues)}",
            f"Open MRs: {len(mrs)}",
            f"Recent Pipeline Status: {pipelines[0]['status'] if pipelines else 'N/A'}",
            f"Last Activity: {project['last_activity_at']}",
        ]

        dashboard = {
            "project_info": {
                "id": project["id"],
                "name": project["name"],
                "description": project.get("description"),
                "visibility": project["visibility"],
                "web_url": project["web_url"],
                "stats": {
                    "star_count": project["star_count"],
                    "forks_count": project["forks_count"],
                },
            },
            "recent_pipelines": [
                {"id": p["id"], "status": p["status"], "ref": p["ref"], "web_url": p["web_url"]}
                for p in pipelines[:5]
            ],
            "open_merge_requests": [
                {
                    "iid": m["iid"],
                    "title": m["title"],
                    "author": m["author"]["name"],
                    "url": m["web_url"],
                }
                for m in mrs[:5]
            ],
            "open_issues": [
                {
                    "iid": i["iid"],
                    "title": i["title"],
                    "author": i["author"]["name"],
                    "url": i["web_url"],
                }
                for i in issues[:5]
            ],
        }

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": dashboard,
            "next_action": "Use the dashboard to identify critical tasks or check the health of recent builds.",
        }

    async def upload_file_to_project(
        self,
        project_id: int | str,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> dict[str, Any]:
        result = await self.client.upload_file(project_id, filename, content, content_type)
        markdown = result.get("markdown", f"![]({result.get('url', '')})")
        return {
            "summary": f"Uploaded '{filename}' to project {project_id}",
            "key_findings": [f"Embed in comments with: {markdown}"],
            "details": result,
            "next_action": "Use the markdown snippet in your comment body to embed the file.",
        }

    async def search_users(self, search: str) -> dict[str, Any]:
        users = await self.client.search_users(search)

        summary = f"Found {len(users)} users matching '{search}'"
        key_findings = [f"{u['name']} (@{u['username']}) - ID: {u['id']}" for u in users[:10]]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"users": users},
            "next_action": "Use the user ID for assignees or reviewers.",
        }

    async def fetch_upload(self, upload_url: str) -> dict[str, Any]:
        """Fetch a GitLab upload attachment (image/file) with authentication."""
        content, content_type = await self.client.fetch_upload(upload_url)

        return {
            "summary": f"Successfully fetched upload from {upload_url}",
            "key_findings": [f"Content Type: {content_type}", f"Size: {len(content)} bytes"],
            "details": {
                "content_type": content_type,
                "content_base64": base64.b64encode(content).decode("utf-8"),
                "size_bytes": len(content),
            },
            "next_action": "The file content is available in base64 format for display or processing.",
        }

    async def _fetch_uploads(self, urls: list[str]) -> list[dict[str, Any]]:
        if not urls:
            return []

        max_attachments = 20
        skipped = 0
        if len(urls) > max_attachments:
            skipped = len(urls) - max_attachments
            urls = urls[:max_attachments]

        tasks = [self.client.fetch_upload(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        uploads: list[dict[str, Any]] = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                error_msg = str(result)
                error_msg = re.sub(r"private_token=[^&\s]+", "private_token=[REDACTED]", error_msg)
                uploads.append(
                    {
                        "url": url,
                        "error": error_msg,
                        "content_base64": None,
                        "content_type": None,
                        "size_bytes": None,
                    }
                )
            else:
                content, content_type = result
                uploads.append(
                    {
                        "url": url,
                        "content_base64": base64.b64encode(content).decode("utf-8"),
                        "content_type": content_type,
                        "size_bytes": len(content),
                    }
                )

        if skipped:
            uploads.append(
                {
                    "url": "",
                    "error": f"Skipped {skipped} additional attachment(s) beyond the limit of {max_attachments}",
                    "content_base64": None,
                    "content_type": None,
                    "size_bytes": None,
                }
            )

        return uploads
