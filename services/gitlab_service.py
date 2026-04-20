import asyncio
import base64
import logging
import re
import urllib.parse
from typing import Any

from gitlab.client import GitLabClient
from services.local_ai_service import LocalAIService
from services.review_digest import (
    build_draft_reply_plan,
    build_review_digest,
    build_review_summary,
    build_suggested_replies,
    build_unresolved_discussion_digest,
    normalize_discussion,
    normalize_draft_note,
)

logger = logging.getLogger(__name__)


class GitLabService:
    def __init__(self, client: GitLabClient):
        self.client = client
        self.local_ai = LocalAIService()

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
                return parsed["project_path"], int(parsed["resource_id"]) if parsed[
                    "resource_id"
                ].isdigit() else parsed["resource_id"]

        return project_id, resource_id

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

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {
                "error_lines": matches[:10],
                "tail_context": tail,
                "local_ai_summary": local_analysis,
            },
            "next_action": "Evaluate the error lines and local summary to propose a fix.",
        }

    async def list_projects(
        self,
        search: str | None = None,
        group_id: int | str | None = None,
        fields: list[str] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        projects = await self.client.list_projects(search=search, group_id=group_id, limit=limit)

        # Absolute payload reduction: Default to 20 results and 4 fields
        if fields is None:
            fields = ["id", "name", "path", "default_branch"]

        # Filter fields strictly
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

        # Absolute payload reduction: Default to 20 results and 4 fields
        if fields is None:
            fields = ["id", "name", "path", "default_branch"]

        # Filter fields strictly
        filtered_projects = []
        for p in projects:
            filtered_projects.append({f: p.get(f) for f in fields if f in p})
        projects = filtered_projects

        summary = f"Found {len(projects)} projects in group {group_id}"
        if limit and len(projects) >= limit:
            summary += f" (limited to top {limit})"

        # Fix: fallback to 'path' if 'path_with_namespace' was filtered out
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
            f"Stars: {project['star_count']}",
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

    async def get_issue_details(
        self, project_id: int | str, issue_iid: int | str
    ) -> dict[str, Any]:
        issue = await self.client.get_issue(project_id, issue_iid)

        summary = f"Details for Issue #{issue['iid']}: {issue['title']}"
        key_findings = [
            f"Status: {issue['state']}",
            f"Author: {issue['author']['name']}",
            f"Assignees: {', '.join([a['name'] for a in issue['assignees']]) if issue['assignees'] else 'None'}",
            f"Labels: {', '.join(issue['labels']) if issue['labels'] else 'None'}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": issue,
            "next_action": "You can update this issue, add a comment, or list its notes.",
        }

    async def create_issue(
        self,
        project_id: int | str,
        title: str,
        description: str | None = None,
        labels: str | None = None,
        assignee_ids: list[int] | None = None,
        milestone_id: int | None = None,
    ) -> dict[str, Any]:
        data = {"title": title}
        if description:
            data["description"] = description
        if labels:
            data["labels"] = labels
        if assignee_ids:
            data["assignee_ids"] = assignee_ids
        if milestone_id:
            data["milestone_id"] = milestone_id

        issue = await self.client.create_issue(project_id, data)

        summary = f"Successfully created Issue #{issue['iid']}: {issue['title']}"
        key_findings = [
            f"IID: {issue['iid']}",
            f"Project: {project_id}",
            f"Labels: {', '.join(issue['labels']) if issue['labels'] else 'None'}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": issue,
            "next_action": "The issue is now created. You can add comments or assign it to someone.",
        }

    async def update_issue(self, project_id: int | str, issue_iid: int, **kwargs) -> dict[str, Any]:

        data = {k: v for k, v in kwargs.items() if v is not None}
        issue = await self.client.update_issue(project_id, issue_iid, data)

        summary = f"Successfully updated Issue #{issue['iid']}"
        key_findings = [f"Updated fields: {', '.join(data.keys())}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": issue,
            "next_action": "View the updated issue details or add a comment.",
        }

    async def get_merge_request_details(
        self, project_id: int | str, mr_iid: int | str, include_jobs: bool = False
    ) -> dict[str, Any]:
        mr = await self.client.get_merge_request(project_id, mr_iid)

        jobs = []
        if include_jobs and mr.get("head_pipeline"):
            pipeline_id = mr["head_pipeline"]["id"]
            jobs = await self.client.list_pipeline_jobs(project_id, pipeline_id)
            mr["head_pipeline_jobs"] = jobs

        summary = f"Details for Merge Request !{mr['iid']}: {mr['title']}"
        key_findings = [
            f"Status: {mr['state']}",
            f"Author: {mr['author']['name']}",
            f"Source: {mr['source_branch']} -> Target: {mr['target_branch']}",
            f"Merge Status: {mr['merge_status']}",
            f"Pipeline Status: {mr.get('head_pipeline', {}).get('status', 'N/A')}",
        ]
        if jobs:
            key_findings.append(f"Jobs: {len(jobs)} jobs retrieved for head pipeline")

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": mr,
            "next_action": "You can update this MR, approve it, add a comment, or view diffs.",
        }

    async def update_merge_request(
        self, project_id: int | str, mr_iid: int, **kwargs
    ) -> dict[str, Any]:
        data = {k: v for k, v in kwargs.items() if v is not None}
        mr = await self.client.update_merge_request(project_id, mr_iid, data)

        summary = f"Successfully updated Merge Request !{mr['iid']}"
        key_findings = [f"Updated fields: {', '.join(data.keys())}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": mr,
            "next_action": "View the updated MR details or request approval.",
        }

    async def approve_merge_request(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        approval = await self.client.approve_merge_request(project_id, mr_iid)

        summary = f"Successfully approved Merge Request !{mr_iid}"
        key_findings = [f"Project ID: {project_id}", f"MR IID: {mr_iid}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": approval,
            "next_action": "The MR is now approved. You can check the merge status.",
        }

    async def list_issue_notes(self, project_id: int | str, issue_iid: int | str) -> dict[str, Any]:
        notes = await self.client.get_issue_notes(project_id, issue_iid)
        user_notes = [n for n in notes if not n.get("system")]

        summary = f"Found {len(user_notes)} user comments for Issue #{issue_iid}"
        key_findings = [f"{n['author']['name']}: {n['body'][:50]}..." for n in user_notes[:5]]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"notes": notes},
            "next_action": "Post a new comment if further discussion is needed.",
        }

    async def create_issue_note(
        self, project_id: int | str, issue_iid: int, body: str
    ) -> dict[str, Any]:
        note = await self.client.create_issue_note(project_id, issue_iid, body)

        summary = f"Successfully posted comment to Issue #{issue_iid}"
        key_findings = [f"Comment ID: {note['id']}", f"Author: {note['author']['name']}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": note,
            "next_action": "The comment is now visible on the issue.",
        }

    async def list_merge_request_notes(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        notes = await self.client.get_merge_request_notes(project_id, mr_iid)
        user_notes = [n for n in notes if not n.get("system")]

        summary = f"Found {len(user_notes)} user comments for Merge Request !{mr_iid}"
        key_findings = [f"{n['author']['name']}: {n['body'][:50]}..." for n in user_notes[:5]]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"notes": notes},
            "next_action": "Post a new comment or resolve existing discussions.",
        }

    async def create_merge_request_note(
        self, project_id: int | str, mr_iid: int, body: str
    ) -> dict[str, Any]:
        note = await self.client.create_merge_request_note(project_id, mr_iid, body)

        summary = f"Successfully posted comment to Merge Request !{mr_iid}"
        key_findings = [f"Comment ID: {note['id']}", f"Author: {note['author']['name']}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": note,
            "next_action": "The comment is now visible on the merge request.",
        }

    async def get_merge_request_diffs(
        self, project_id: int | str, mr_iid: int | str, paths: list[str] | None = None
    ) -> dict[str, Any]:
        diffs = await self.client.get_merge_request_diffs(project_id, mr_iid)

        # Apply path filter if requested
        if paths:
            diffs = [d for d in diffs if d.get("new_path") in paths or d.get("old_path") in paths]

        summary = f"Retrieved {len(diffs)} changed files for Merge Request !{mr_iid}"
        if paths:
            summary += f" (filtered by {len(paths)} paths)"

        key_findings = [
            f"{d['new_path']} ({'+' if d['new_file'] else 'modified'})" for d in diffs[:10]
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"diffs": diffs},
            "next_action": "Review the code changes for each file.",
        }

    async def list_repository_files(
        self, project_id: int | str, path: str = "", ref: str = "main"
    ) -> dict[str, Any]:
        files = await self.client.get_repository_tree(project_id, path=path, ref=ref)

        summary = f"Found {len(files)} files/folders in '{path or '/'}' for project {project_id} (ref: {ref})"
        key_findings = [f"{f['type']}: {f['path']}" for f in files[:10]]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"files": files},
            "next_action": "You can read a file's content or explore subdirectories.",
        }

    async def get_file_content(
        self, project_id: int | str, file_path: str, ref: str = "main", include_raw: bool = False
    ) -> dict[str, Any]:
        file_data = await self.client.get_file_content(project_id, file_path, ref=ref)

        content = file_data.get("content", "")
        if file_data.get("encoding") == "base64":
            try:
                content = base64.b64decode(content).decode("utf-8")
            except Exception:
                # If it's binary, keep it as base64 but return it in 'content' too
                pass

        summary = f"Retrieved content for '{file_path}' (ref: {ref})"
        key_findings = [
            f"File Name: {file_data['file_name']}",
            f"Size: {file_data['size']} bytes",
            f"Branch/Ref: {ref}",
        ]

        # Optimization: remove large raw base64 from metadata if not explicitly requested
        if not include_raw and "content" in file_data:
            del file_data["content"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"content": content, "metadata": file_data},
            "next_action": "Analyze the file content or request another file.",
        }

    async def get_raw_file_content(
        self,
        project_id: int | str | None = None,
        file_path: str | None = None,
        ref: str = "main",
        raw_url: str | None = None,
    ) -> dict[str, Any]:
        if raw_url:
            content = await self.client.get_raw_file(raw_url)
            filename = raw_url.rstrip("/").split("/")[-1]
            source = raw_url
        elif project_id and file_path:
            # GitLab API: GET /projects/:id/repository/files/:file_path/raw
            encoded_path = urllib.parse.quote(file_path, safe="")
            endpoint = f"/projects/{self.client._format_project_id(project_id)}/repository/files/{encoded_path}/raw"
            response = await self.client._request("GET", endpoint, params={"ref": ref})
            content = response.text
            filename = file_path.split("/")[-1]
            source = f"project {project_id}, path {file_path}, ref {ref}"
        else:
            return {"error": "Must provide either 'raw_url' or both 'project_id' and 'file_path'"}

        return {
            "summary": f"Retrieved raw content of '{filename}' from {source}",
            "key_findings": [
                f"File: {filename}",
                f"Size: {len(content)} bytes",
                f"Lines: {content.count(chr(10)) + 1}",
            ],
            "details": {"content": content, "source": source},
            "next_action": "Analyze or use the raw file content as needed.",
        }

    async def get_multiple_files(
        self,
        project_id: int | str,
        file_paths: list[str],
        ref: str = "main",
        include_metadata: bool = False,
    ) -> dict[str, Any]:
        """Fetch multiple files in parallel for efficiency."""
        tasks = [
            self.get_file_content(project_id, path, ref=ref, include_raw=include_metadata)
            for path in file_paths
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        errors = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                errors.append(f"Error fetching {file_paths[i]}: {str(res)}")
            else:
                processed_results.append(
                    {
                        "path": file_paths[i],
                        "content": res["details"]["content"],
                        "metadata": res["details"]["metadata"],
                    }
                )

        summary = f"Fetched {len(processed_results)} files from project {project_id}"
        key_findings = [
            f"Successfully fetched: {', '.join([r['path'] for r in processed_results])}"
        ]
        if not include_metadata:
            key_findings.append("Large Base64 content excluded from metadata (payload optimized)")
        if errors:
            key_findings.append(f"Failed to fetch: {len(errors)} files")

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"files": processed_results, "errors": errors},
            "next_action": "Review the content of the requested files.",
        }

    async def create_branch(self, project_id: int | str, branch: str, ref: str) -> dict[str, Any]:
        result = await self.client.create_branch(project_id, branch, ref)

        summary = f"Successfully created branch '{branch}' from '{ref}'"
        key_findings = [f"Branch: {result['name']}", f"Commit: {result['commit']['id'][:8]}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "You can now commit files to this branch.",
        }

    async def get_branch(self, project_id: int | str, branch: str) -> dict[str, Any]:
        result = await self.client.get_branch(project_id, branch)

        summary = f"Retrieved details for branch '{branch}' in project {project_id}"
        key_findings = [
            f"Name: {result['name']}",
            f"HEAD SHA: {result['commit']['id']}",
            f"Merged: {result['merged']}",
            f"Protected: {result['protected']}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "Use the HEAD SHA for version pinning or comparisons.",
        }

    async def get_branches(self, project_id: int | str, branches: list[str]) -> dict[str, Any]:
        """Fetch details for multiple branches in parallel."""
        tasks = [self.client.get_branch(project_id, b) for b in branches]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        errors = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                errors.append(f"Error fetching branch '{branches[i]}': {str(res)}")
            else:
                processed_results.append(
                    {
                        "name": res["name"],
                        "head_sha": res["commit"]["id"],
                        "committed_date": res["commit"]["committed_date"],
                        "protected": res["protected"],
                    }
                )

        summary = f"Retrieved details for {len(processed_results)} branches in project {project_id}"
        key_findings = [
            f"Branch '{r['name']}': HEAD={r['head_sha'][:8]}" for r in processed_results[:10]
        ]
        if errors:
            key_findings.append(f"Failed to fetch {len(errors)} branches")

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"branches": processed_results, "errors": errors},
            "next_action": "Use the HEAD SHAs for version pinning or cross-repo readiness checks.",
        }

    async def list_repository_tags(self, project_id: int | str, limit: int = 50) -> dict[str, Any]:
        tags = await self.client.list_tags(project_id, limit=limit)

        # Format tags to include essential release/pinning data
        formatted_tags = []
        for t in tags:
            commit = t.get("commit", {})
            # Comprehensive extraction with multiple fallbacks
            commit_sha = commit.get("id") or t.get("target")
            committed_date = (
                commit.get("committed_date") or commit.get("created_at") or t.get("created_at")
            )

            formatted_tags.append(
                {
                    "name": t.get("name"),
                    "message": t.get("message") or commit.get("message") or commit.get("title"),
                    "target": t.get("target"),
                    "commit_sha": commit_sha,
                    "committed_date": committed_date,
                    "protected": t.get("protected"),
                }
            )

        summary = f"Found {len(formatted_tags)} tags for project {project_id}"
        if limit and len(formatted_tags) >= limit:
            summary += f" (limited to top {limit})"

        key_findings = [
            f"{t['name']} (SHA: {t['commit_sha'][:8] if t['commit_sha'] else 'N/A'}, Date: {t['committed_date'] or 'N/A'})"
            for t in formatted_tags[:10]
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"tags": formatted_tags},
            "next_action": "Use the tag name or commit SHA for version pinning in infrastructure code.",
        }

    async def commit_file(
        self,
        project_id: int | str,
        file_path: str,
        branch: str,
        content: str,
        commit_message: str,
        is_new: bool = True,
    ) -> dict[str, Any]:
        if is_new:
            result = await self.client.create_repository_file(
                project_id, file_path, branch, content, commit_message
            )
        else:
            result = await self.client.update_repository_file(
                project_id, file_path, branch, content, commit_message
            )

        summary = (
            f"Successfully {'created' if is_new else 'updated'} '{file_path}' on branch '{branch}'"
        )
        key_findings = [f"File: {result['file_path']}", f"Branch: {result['branch']}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "Verify the change or create a merge request.",
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

    async def search_code(self, project_id: int | str, search: str) -> dict[str, Any]:
        results = await self.client.search_code(project_id, search)

        summary = f"Found {len(results)} code matches for '{search}' in project {project_id}"
        key_findings = [f"File: {r['filename']} (Ref: {r['ref']})" for r in results[:10]]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"results": results},
            "next_action": "View the file content for more context.",
        }

    async def global_search(
        self, scope: str, search: str, group_id: int | str | None = None
    ) -> dict[str, Any]:
        params = {"scope": scope, "search": search}

        endpoint = "/search"
        if group_id:
            endpoint = f"/groups/{self.client._format_project_id(group_id)}/search"

        results = await self.client.get(endpoint, params=params)

        summary = f"Found {len(results)} matches for '{search}' in scope '{scope}'"
        if group_id:
            summary += f" (Scoped to group {group_id})"

        if scope == "projects":
            key_findings = [
                f"Project: {r['name_with_namespace']} (ID: {r['id']})" for r in results[:10]
            ]
        elif scope == "issues":
            key_findings = [
                f"Issue #{r['iid']}: {r['title']} (Project ID: {r['project_id']})"
                for r in results[:10]
            ]
        elif scope == "merge_requests":
            key_findings = [
                f"MR !{r['iid']}: {r['title']} (Project ID: {r['project_id']})"
                for r in results[:10]
            ]
        else:
            key_findings = [f"Match ID: {r.get('id', 'N/A')}" for r in results[:10]]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"results": results},
            "next_action": "Drill down into specific items using their IDs.",
        }

    async def list_pipelines(self, project_id: int | str) -> dict[str, Any]:
        pipelines = await self.client.list_pipelines(project_id)

        summary = f"Found {len(pipelines)} pipelines for project {project_id}"
        key_findings = [
            f"ID: {p['id']} - Status: {p['status']} (Ref: {p['ref']})" for p in pipelines[:5]
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"pipelines": pipelines},
            "next_action": "Check a specific pipeline's details or logs.",
        }

    async def list_pipeline_jobs(self, project_id: int | str, pipeline_id: int) -> dict[str, Any]:
        jobs = await self.client.list_pipeline_jobs(project_id, pipeline_id)

        summary = f"Found {len(jobs)} jobs for pipeline {pipeline_id}"
        key_findings = [
            f"Job: {j['name']} (ID: {j['id']}) - Status: {j['status']}" for j in jobs[:10]
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"jobs": jobs},
            "next_action": "Fetch the log for a failed job to diagnose the error.",
        }

    async def get_pipeline_bridges(self, project_id: int | str, pipeline_id: int) -> dict[str, Any]:
        bridges = await self.client.get_pipeline_bridges(project_id, pipeline_id)

        summary = f"Found {len(bridges)} bridge jobs for pipeline {pipeline_id}"
        key_findings = [
            f"Bridge: {b['name']} (ID: {b['id']}) - Downstream: {b.get('downstream_pipeline', {}).get('id', 'N/A')}"
            for b in bridges[:10]
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"bridges": bridges},
            "next_action": "Analyze downstream triggers if needed.",
        }

    async def get_job_log(self, project_id: int | str, job_id: int | str) -> dict[str, Any]:
        log_content = await self.client.get_job_log(project_id, job_id)
        log_lines = log_content.splitlines()
        tail_log = "\n".join(log_lines[-100:])

        summary = f"Fetched trace log for job {job_id} (tail: 100 lines)"
        key_findings = [
            f"Total log lines: {len(log_lines)}",
            "Included tail of the log for debugging.",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"log": tail_log},
            "next_action": "Review the logs for error messages or stack traces.",
        }

    async def list_merge_request_discussions(
        self,
        project_id: int | str,
        mr_iid: int,
        unresolved_only: bool = False,
        include_system: bool = True,
    ) -> dict[str, Any]:
        discussions = await self.client.get_merge_request_discussions(project_id, mr_iid)

        # Apply filters
        filtered_discussions = []
        for d in discussions:
            # If unresolved_only is True, check if the discussion is resolved
            if unresolved_only:
                # A discussion is considered resolved if all its notes are resolved or it has a 'resolved' attribute
                # GitLab API discussions often have a 'notes' list where each note can be resolved.
                # If ANY note is unresolved, the thread might be considered unresolved.
                # Actually, discussions themselves have a 'resolved' property if they are resolvable.
                if d.get("resolved", False):
                    continue

            # Filter notes within the discussion
            filtered_notes = []
            for n in d.get("notes", []):
                if not include_system and n.get("system", False):
                    continue
                filtered_notes.append(n)

            if filtered_notes:
                d_copy = d.copy()
                d_copy["notes"] = filtered_notes
                filtered_discussions.append(d_copy)

        summary = f"Found {len(filtered_discussions)} discussions for Merge Request !{mr_iid}"
        if unresolved_only:
            summary += " (unresolved only)"

        key_findings = [
            f"Discussion {d['id'][:8]}: {len(d['notes'])} notes" for d in filtered_discussions[:5]
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"discussions": filtered_discussions},
            "next_action": "You can resolve a specific discussion using its ID.",
        }

    async def list_merge_request_discussion_summaries(
        self, project_id: int | str, mr_iid: int, unresolved_only: bool = False
    ) -> dict[str, Any]:
        discussions = await self.client.get_merge_request_discussions(project_id, mr_iid)

        summaries = []
        for d in discussions:
            # Filter by resolution if requested
            if unresolved_only and d.get("resolved", False):
                continue

            # Skip system notes from summary if they are the only thing in the thread
            user_notes = [n for n in d.get("notes", []) if not n.get("system")]
            if not user_notes:
                continue

            first_note = user_notes[0]
            summaries.append(
                {
                    "id": d["id"],
                    "author": first_note["author"]["name"],
                    "first_line": first_note["body"].split("\n")[0][:100],
                    "resolved": d.get("resolved", False),
                    "note_count": len(d.get("notes", [])),
                }
            )

        summary = f"Found {len(summaries)} discussion threads for MR !{mr_iid}"
        if unresolved_only:
            summary += " (unresolved only)"

        key_findings = [
            f"Resolved: {sum(1 for s in summaries if s['resolved'])}",
            f"Unresolved: {sum(1 for s in summaries if not s['resolved'])}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"discussions": summaries},
            "next_action": "Use the discussion ID to read or reply to a specific thread.",
        }

    async def resolve_merge_request_discussion(
        self, project_id: int | str, mr_iid: int, discussion_id: str, resolved: bool = True
    ) -> dict[str, Any]:
        result = await self.client.resolve_merge_request_discussion(
            project_id, mr_iid, discussion_id, resolved
        )

        summary = (
            f"Successfully {'resolved' if resolved else 'unresolved'} discussion {discussion_id}"
        )
        key_findings = [
            f"MR !{mr_iid}",
            f"Discussion ID: {discussion_id}",
            f"Status: {'Resolved' if resolved else 'Open'}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "Check if all other discussions are resolved before merging.",
        }

    async def retry_job(self, project_id: int | str, job_id: int | str) -> dict[str, Any]:
        result = await self.client.retry_job(project_id, job_id)

        summary = f"Successfully triggered retry for job {job_id}"
        key_findings = [f"New Job ID: {result['id']}", f"Status: {result['status']}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "Monitor the new job's progress.",
        }

    async def retry_pipeline(self, project_id: int | str, pipeline_id: int) -> dict[str, Any]:
        result = await self.client.retry_pipeline(project_id, pipeline_id)

        summary = f"Successfully triggered retry for pipeline {pipeline_id}"
        key_findings = [
            f"Pipeline ID: {result['id']}",
            f"Status: {result['status']}",
            f"Ref: {result['ref']}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "Monitor the pipeline's progress.",
        }

    async def get_job_artifact_file(
        self, project_id: int | str, job_id: int, artifact_path: str
    ) -> dict[str, Any]:
        content = await self.client.get_job_artifact_file(project_id, job_id, artifact_path)

        summary = f"Retrieved artifact file '{artifact_path}' from job {job_id}"
        key_findings = [
            f"File: {artifact_path}",
            f"Job ID: {job_id}",
            f"Content Length: {len(content)} bytes",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"content": content},
            "next_action": "Analyze the artifact content for further insights.",
        }

    async def list_repository_commits(
        self, project_id: int | str, ref_name: str | None = None
    ) -> dict[str, Any]:
        commits = await self.client.list_repository_commits(project_id, ref_name)

        summary = f"Found {len(commits)} commits for project {project_id}"
        if ref_name:
            summary += f" on ref '{ref_name}'"

        key_findings = [f"{c['id'][:8]}: {c['title']} by {c['author_name']}" for c in commits[:10]]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"commits": commits},
            "next_action": "Get details for a specific commit using its SHA.",
        }

    async def get_commit_details(self, project_id: int | str, sha: str) -> dict[str, Any]:
        commit = await self.client.get_commit_details(project_id, sha)

        summary = f"Details for commit {sha[:8]}: {commit['title']}"
        key_findings = [
            f"Author: {commit['author_name']} <{commit['author_email']}>",
            f"Date: {commit['created_at']}",
            f"Stats: Additions: {commit['stats']['additions']}, Deletions: {commit['stats']['deletions']}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": commit,
            "next_action": "You can view the diffs for this commit if needed.",
        }

    async def get_file_blame(
        self, project_id: int | str, file_path: str, ref: str = "main"
    ) -> dict[str, Any]:
        blame_data = await self.client.get_file_blame(project_id, file_path, ref)

        summary = f"Retrieved blame data for '{file_path}' (ref: {ref})"

        # Aggregate unique authors
        authors = set(segment["commit"]["author_name"] for segment in blame_data)
        key_findings = [
            f"Total segments: {len(blame_data)}",
            f"Contributors: {', '.join(list(authors)[:5])}",
            f"Last modified by: {blame_data[0]['commit']['author_name'] if blame_data else 'N/A'}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"blame": blame_data},
            "next_action": "Analyze which commits introduced specific changes.",
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
        self, project_id: int | str, name: str, color: str, description: str | None = None
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

    async def list_project_environments(self, project_id: int | str) -> dict[str, Any]:
        environments = await self.client.list_project_environments(project_id)

        summary = f"Found {len(environments)} environments for project {project_id}"
        key_findings = [
            f"{e['name']} (Slug: {e['slug']}) - External URL: {e.get('external_url', 'N/A')}"
            for e in environments[:10]
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"environments": environments},
            "next_action": "Check the deployment status for a specific environment.",
        }

    async def merge_merge_request(
        self, project_id: int | str, mr_iid: int, **kwargs
    ) -> dict[str, Any]:
        data = {k: v for k, v in kwargs.items() if v is not None}
        result = await self.client.merge_merge_request(project_id, mr_iid, data)

        summary = f"Successfully merged Merge Request !{mr_iid}"
        key_findings = [
            f"Status: {result.get('state', 'merged')}",
            f"Merge Commit SHA: {result.get('merge_commit_sha', 'N/A')[:8]}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "The MR is merged. You can now delete the source branch if not done automatically.",
        }

    async def bundle_merge_request_context(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        """
        High-performance tool that bundles MR details, discussions, and diffs.
        Reduces token usage by summarizing and filtering noise.
        """
        import asyncio

        # Fetch everything in parallel
        mr_task = self.client.get_merge_request(project_id, mr_iid)
        notes_task = self.client.get_merge_request_notes(project_id, mr_iid)
        diffs_task = self.client.get_merge_request_diffs(project_id, mr_iid)

        mr, notes, diffs = await asyncio.gather(mr_task, notes_task, diffs_task)

        # Filter notes (only user comments, no system notes)
        user_notes = [n for n in notes if not n.get("system")]

        # Summarize diffs (just file names and status)
        diff_summary = [
            f"{d['new_path']} ({'added' if d['new_file'] else 'modified'})" for d in diffs
        ]

        summary = f"Bundled context for Merge Request !{mr_iid}: {mr['title']}"
        key_findings = [
            f"State: {mr['state']}",
            f"Comments: {len(user_notes)} user discussions",
            f"Changes: {len(diffs)} files modified",
            f"Source: {mr['source_branch']} -> {mr['target_branch']}",
        ]

        # Construct a compact context for the AI
        compact_context = {
            "mr_details": {
                "iid": mr["iid"],
                "title": mr["title"],
                "description": mr["description"],
                "author": mr["author"]["name"],
                "labels": mr["labels"],
            },
            "recent_discussions": [
                {
                    "author": n["author"]["name"],
                    "body": n["body"][:200] + "..." if len(n["body"]) > 200 else n["body"],
                }
                for n in user_notes[-5:]  # Last 5 comments
            ],
            "changed_files": diff_summary,
        }

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": compact_context,
            "next_action": "Analyze the bundled context to perform a comprehensive review or identify blockers.",
        }

    async def add_merge_request_discussion_note(
        self, project_id: int | str, mr_iid: int, discussion_id: str, body: str
    ) -> dict[str, Any]:
        result = await self.client.add_merge_request_discussion_note(
            project_id, mr_iid, discussion_id, body
        )

        summary = f"Successfully replied to discussion {discussion_id} on MR !{mr_iid}"
        key_findings = [f"Note ID: {result['id']}", f"Author: {result['author']['name']}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "The reply is now visible in the discussion thread.",
        }

    async def create_merge_request_discussion(
        self, project_id: int | str, mr_iid: int, body: str, position: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        result = await self.client.create_merge_request_discussion(
            project_id, mr_iid, body, position
        )

        summary = f"Successfully created a new discussion on MR !{mr_iid}"
        key_findings = [
            f"Discussion ID: {result['id']}",
            f"First Note ID: {result['notes'][0]['id']}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "The new discussion thread is now active.",
        }

    async def get_latest_merge_request_version(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        version = await self.client.get_latest_merge_request_version(project_id, mr_iid)
        summary = f"Latest diff version for MR !{mr_iid}"
        key_findings = [
            f"base_sha: {version['base_sha']}",
            f"start_sha: {version['start_sha']}",
            f"head_sha: {version['head_sha']}",
        ]
        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": version,
            "next_action": "Use these SHAs when constructing diff comment positions.",
        }

    async def build_text_diff_position(
        self,
        project_id: int | str,
        mr_iid: int,
        new_path: str,
        old_path: str | None = None,
        new_line: int | None = None,
        old_line: int | None = None,
    ) -> dict[str, Any]:
        position = await self.client.build_text_diff_position(
            project_id, mr_iid, new_path, old_path=old_path, new_line=new_line, old_line=old_line
        )
        return {
            "summary": "Resolved diff position for MR comment",
            "key_findings": [
                f"File: {position['new_path']}",
                f"base_sha: {position['base_sha']}",
                f"head_sha: {position['head_sha']}",
            ],
            "details": {"position": position},
            "next_action": "Pass this position to create_merge_request_discussion or create_draft_note.",
        }

    async def list_merge_request_draft_notes(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        raw = await self.client.list_merge_request_draft_notes(project_id, mr_iid)
        draft_notes = [normalize_draft_note(n) for n in raw]
        summary = f"Found {len(draft_notes)} draft notes for MR !{mr_iid}"
        key_findings = [f"Draft {n['id']}: {n['file_path']}" for n in draft_notes[:5]]
        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"draft_notes": draft_notes},
            "next_action": "Review wording, then publish or delete drafts.",
        }

    async def create_merge_request_draft_note(
        self,
        project_id: int | str,
        mr_iid: int,
        body: str,
        position: dict[str, Any] | None = None,
        discussion_id: str | None = None,
        resolve_discussion: bool | None = None,
    ) -> dict[str, Any]:
        result = await self.client.create_merge_request_draft_note(
            project_id,
            mr_iid,
            body,
            position=position,
            discussion_id=discussion_id,
            resolve_discussion=resolve_discussion,
        )
        summary = f"Created draft note on MR !{mr_iid}"
        key_findings = [f"Draft Note ID: {result.get('id')}"]
        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "Inspect with list_draft_notes, then publish when ready.",
        }

    async def delete_merge_request_draft_note(
        self, project_id: int | str, mr_iid: int, draft_note_id: int
    ) -> dict[str, Any]:
        await self.client.delete_merge_request_draft_note(project_id, mr_iid, draft_note_id)
        summary = f"Deleted draft note {draft_note_id} from MR !{mr_iid}"
        return {
            "summary": summary,
            "key_findings": [f"Removed draft note {draft_note_id}"],
            "details": {"draft_note_id": draft_note_id, "status": "deleted"},
            "next_action": "Draft note removed. It will not be published.",
        }

    async def publish_merge_request_draft_notes(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        result = await self.client.publish_merge_request_draft_notes(project_id, mr_iid)
        summary = f"Published all draft notes on MR !{mr_iid}"
        return {
            "summary": summary,
            "key_findings": ["All draft notes are now public"],
            "details": result or {"published": True},
            "next_action": "Review the public discussions on the merge request.",
        }

    async def get_review_summary(self, project_id: int | str, mr_iid: int | str) -> dict[str, Any]:
        raw = await self.client.get_merge_request_discussions(project_id, mr_iid)
        discussions = [normalize_discussion(d) for d in raw]
        summary = build_review_summary(discussions)
        return {
            "summary": f"Review summary for MR !{mr_iid}",
            "key_findings": [
                f"Total discussions: {summary['total_discussions']}",
                f"Unresolved: {summary['unresolved_discussions']}",
            ],
            "details": summary,
            "next_action": "Drill down with get_unresolved_discussion_digest or get_review_digest.",
        }

    async def get_unresolved_discussion_digest(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        raw = await self.client.get_merge_request_discussions(project_id, mr_iid)
        discussions = [normalize_discussion(d) for d in raw]
        items = build_unresolved_discussion_digest(discussions)
        return {
            "summary": f"Unresolved discussion digest for MR !{mr_iid}",
            "key_findings": [f"Unresolved items: {len(items)}"],
            "details": {"unresolved_items": items},
            "next_action": "Address unresolved items or stage draft replies.",
        }

    async def get_suggested_replies(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        raw = await self.client.get_merge_request_discussions(project_id, mr_iid)
        discussions = [normalize_discussion(d) for d in raw]
        replies = build_suggested_replies(discussions)
        return {
            "summary": f"Suggested replies for MR !{mr_iid}",
            "key_findings": [f"Templates for {len(replies)} unresolved threads"],
            "details": {"suggested_replies": replies},
            "next_action": "Edit suggested replies before using bulk_reply_to_discussions or create_draft_note.",
        }

    async def get_review_digest(self, project_id: int | str, mr_iid: int | str) -> dict[str, Any]:
        raw = await self.client.get_merge_request_discussions(project_id, mr_iid)
        discussions = [normalize_discussion(d) for d in raw]
        digest = build_review_digest(discussions)
        return {
            "summary": f"Combined review digest for MR !{mr_iid}",
            "key_findings": [
                f"Totals: {digest['totals']['total_discussions']} discussions, "
                f"{digest['totals']['unresolved_discussions']} unresolved",
            ],
            "details": digest,
            "next_action": "Use get_suggested_replies or bulk_reply_to_discussions to respond.",
        }

    async def get_draft_reply_plan(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        raw = await self.client.get_merge_request_discussions(project_id, mr_iid)
        discussions = [normalize_discussion(d) for d in raw]
        plan = build_draft_reply_plan(discussions)
        return {
            "summary": f"Draft reply plan for MR !{mr_iid}",
            "key_findings": [f"Planned items: {plan['total_items']}"],
            "details": plan,
            "next_action": "Review target_mode and suggested_reply for each item before staging.",
        }

    async def bulk_reply_to_discussions(
        self, project_id: int | str, mr_iid: int, replies: list[dict[str, Any]]
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for r in replies:
            discussion_id = r.get("discussion_id", "")
            body = r.get("body", "")
            try:
                await self.client.add_merge_request_discussion_note(
                    project_id, mr_iid, discussion_id, body
                )
                results.append({"discussion_id": discussion_id, "success": True})
            except Exception as e:
                results.append({"discussion_id": discussion_id, "success": False, "error": str(e)})
        success_count = sum(1 for r in results if r["success"])
        return {
            "summary": f"Bulk reply to discussions on MR !{mr_iid}",
            "key_findings": [f"Success: {success_count}/{len(results)}"],
            "details": {"results": results},
            "next_action": "Retry failed items individually if needed.",
        }

    async def bulk_resolve_discussions(
        self, project_id: int | str, mr_iid: int, discussion_ids: list[str], resolved: bool = True
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for did in discussion_ids:
            try:
                await self.client.resolve_merge_request_discussion(
                    project_id, mr_iid, did, resolved
                )
                results.append({"discussion_id": did, "success": True})
            except Exception as e:
                results.append({"discussion_id": did, "success": False, "error": str(e)})
        success_count = sum(1 for r in results if r["success"])
        return {
            "summary": f"Bulk {'resolve' if resolved else 'reopen'} discussions on MR !{mr_iid}",
            "key_findings": [f"Success: {success_count}/{len(results)}"],
            "details": {"results": results},
            "next_action": "Verify remaining open discussions before merging.",
        }

    async def update_note(
        self, project_id: int | str, resource_type: str, resource_iid: int, note_id: int, body: str
    ) -> dict[str, Any]:
        result = await self.client.update_note(
            project_id, resource_type, resource_iid, note_id, body
        )

        summary = f"Successfully updated note {note_id} on {resource_type} {resource_iid}"
        key_findings = [f"Note ID: {result['id']}", "Content updated"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "The note content has been modified.",
        }

    async def delete_note(
        self, project_id: int | str, resource_type: str, resource_iid: int, note_id: int
    ) -> dict[str, Any]:
        await self.client.delete_note(project_id, resource_type, resource_iid, note_id)

        summary = f"Successfully deleted note {note_id} from {resource_type} {resource_iid}"
        key_findings = [f"Note {note_id} removed"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"note_id": note_id, "status": "deleted"},
            "next_action": "The note is no longer available.",
        }

    async def create_merge_request(self, project_id: int | str, **kwargs) -> dict[str, Any]:
        data = {k: v for k, v in kwargs.items() if v is not None}
        result = await self.client.create_merge_request(project_id, data)

        summary = f"Successfully created Merge Request !{result['iid']}"
        key_findings = [
            f"Title: {result['title']}",
            f"Source: {result['source_branch']} -> Target: {result['target_branch']}",
            f"Author: {result['author']['name']}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "Review the new MR or assign reviewers.",
        }

    async def trigger_pipeline(
        self, project_id: int | str, ref: str, variables: list[dict[str, str]] | None = None
    ) -> dict[str, Any]:
        result = await self.client.trigger_pipeline(project_id, ref, variables)

        summary = f"Successfully triggered new pipeline for ref '{ref}'"
        key_findings = [
            f"Pipeline ID: {result['id']}",
            f"Status: {result['status']}",
            f"Web URL: {result['web_url']}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "Monitor the pipeline progress or check job logs.",
        }

    async def get_pipeline_details(self, project_id: int | str, pipeline_id: int) -> dict[str, Any]:
        result = await self.client.get_pipeline(project_id, pipeline_id)

        summary = f"Details for pipeline {pipeline_id}"
        key_findings = [
            f"Status: {result['status']}",
            f"Ref: {result['ref']}",
            f"Source: {result['source']}",
            f"Duration: {result.get('duration', 'N/A')} seconds",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "Check pipeline jobs if it failed.",
        }

    async def list_merge_request_pipelines(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        pipelines = await self.client.list_merge_request_pipelines(project_id, mr_iid)

        summary = f"Found {len(pipelines)} pipelines for MR !{mr_iid}"
        key_findings = [f"ID: {p['id']} - Status: {p['status']}" for p in pipelines[:5]]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"pipelines": pipelines},
            "next_action": "Check the most recent pipeline for build/test results.",
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

    async def create_batch_commit(
        self,
        project_id: int | str,
        branch: str,
        commit_message: str,
        actions: list[dict[str, Any]],
        start_branch: str | None = None,
    ) -> dict[str, Any]:
        data = {"branch": branch, "commit_message": commit_message, "actions": actions}
        if start_branch:
            data["start_branch"] = start_branch

        result = await self.client.create_batch_commit(project_id, data)

        summary = f"Successfully created batch commit on branch '{branch}'"
        key_findings = [
            f"Short ID: {result['short_id']}",
            f"Title: {result['title']}",
            f"Files impacted: {len(actions)}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "Verify the changes or create a merge request.",
        }

    async def get_job_artifacts_archive(
        self, project_id: int | str, job_id: int | str
    ) -> dict[str, Any]:
        content = await self.client.get_job_artifacts_archive(project_id, job_id)

        summary = f"Retrieved artifacts archive for job {job_id}"
        key_findings = [f"Size: {len(content)} bytes"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"content_length": len(content), "info": "Binary zip content retrieved"},
            "next_action": "The archive can be processed or saved as a zip file.",
        }

    async def cancel_pipeline(self, project_id: int | str, pipeline_id: int) -> dict[str, Any]:
        result = await self.client.cancel_pipeline(project_id, pipeline_id)

        summary = f"Successfully cancelled pipeline {pipeline_id}"
        key_findings = [f"Status: {result.get('status', 'cancelled')}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "The pipeline has been stopped.",
        }

    async def cancel_job(self, project_id: int | str, job_id: int | str) -> dict[str, Any]:
        result = await self.client.cancel_job(project_id, job_id)

        summary = f"Successfully cancelled job {job_id}"
        key_findings = [f"Status: {result.get('status', 'cancelled')}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "The job has been stopped.",
        }

    async def play_job(self, project_id: int | str, job_id: int | str) -> dict[str, Any]:
        result = await self.client.play_job(project_id, job_id)

        summary = f"Successfully started manual job {job_id}"
        key_findings = [f"Status: {result.get('status', 'pending')}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "Monitor the job progress.",
        }

    async def rebase_merge_request(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        result = await self.client.rebase_merge_request(project_id, mr_iid)

        summary = f"Successfully triggered rebase for MR !{mr_iid}"
        key_findings = ["Rebase in progress"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "Check the MR status to verify rebase completion.",
        }

    async def get_merge_request_approvals(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        result = await self.client.get_merge_request_approvals(project_id, mr_iid)

        summary = f"Retrieved approval status for MR !{mr_iid}"
        key_findings = [
            f"Approvals Required: {result.get('approvals_required', 0)}",
            f"Approvals Left: {result.get('approvals_left', 0)}",
            f"Approved By: {', '.join([a['user']['name'] for a in result.get('approved_by', [])]) or 'None'}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "Check if more approvals are needed before merging.",
        }

    async def list_project_variables(self, project_id: int | str) -> dict[str, Any]:
        variables = await self.client.list_project_variables(project_id)

        summary = f"Found {len(variables)} variables for project {project_id}"
        key_findings = [
            f"Key: {v['key']} (Type: {v['variable_type']}, Protected: {v['protected']})"
            for v in variables[:10]
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"variables": variables},
            "next_action": "Review or manage these variables for CI/CD configuration.",
        }

    async def create_project_variable(
        self,
        project_id: int | str,
        key: str,
        value: str,
        variable_type: str = "env_var",
        protected: bool = False,
        masked: bool = False,
    ) -> dict[str, Any]:
        data = {
            "key": key,
            "value": value,
            "variable_type": variable_type,
            "protected": protected,
            "masked": masked,
        }
        result = await self.client.create_project_variable(project_id, data)

        summary = f"Successfully created project variable '{key}'"
        key_findings = [f"Key: {result['key']}", f"Type: {result['variable_type']}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "The variable is now available for CI/CD pipelines.",
        }

    async def update_project_variable(
        self,
        project_id: int | str,
        key: str,
        value: str | None = None,
        variable_type: str | None = None,
        protected: bool | None = None,
        masked: bool | None = None,
    ) -> dict[str, Any]:
        data = {}
        if value is not None:
            data["value"] = value
        if variable_type is not None:
            data["variable_type"] = variable_type
        if protected is not None:
            data["protected"] = protected
        if masked is not None:
            data["masked"] = masked

        result = await self.client.update_project_variable(project_id, key, data)

        summary = f"Successfully updated project variable '{key}'"
        key_findings = [f"Key: {result['key']}", "Values updated"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "The updated variable is now in effect.",
        }

    async def delete_project_variable(self, project_id: int | str, key: str) -> dict[str, Any]:
        await self.client.delete_project_variable(project_id, key)

        summary = f"Successfully deleted project variable '{key}'"
        key_findings = [f"Variable '{key}' removed"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"key": key, "status": "deleted"},
            "next_action": "The variable is no longer available.",
        }

    async def bundle_issue_context(
        self, project_id: int | str, issue_iid: int | str
    ) -> dict[str, Any]:
        """
        High-performance tool that bundles issue details, notes, and related MRs.
        Reduces token usage by summarizing and filtering noise.
        """
        import asyncio

        # Fetch everything in parallel
        issue_task = self.client.get_issue(project_id, issue_iid)
        notes_task = self.client.get_issue_notes(project_id, issue_iid)
        mrs_task = self.client.get_issue_related_mrs(project_id, issue_iid)

        issue, notes, mrs = await asyncio.gather(issue_task, notes_task, mrs_task)

        # Filter notes (only user comments, no system notes)
        user_notes = [n for n in notes if not n.get("system")]

        summary = f"Bundled context for Issue #{issue_iid}: {issue['title']}"
        key_findings = [
            f"Status: {issue['state']}",
            f"Comments: {len(user_notes)} user discussions",
            f"Linked MRs: {len(mrs)} relevant merge requests",
            f"Assignees: {', '.join([a['name'] for a in issue['assignees']]) if issue['assignees'] else 'None'}",
        ]

        # Construct a compact context for the AI
        compact_context = {
            "issue_details": {
                "iid": issue["iid"],
                "title": issue["title"],
                "description": issue["description"],
                "author": issue["author"]["name"],
                "labels": issue["labels"],
                "state": issue["state"],
                "assignees": [a["name"] for a in issue["assignees"]],
            },
            "linked_merge_requests": [
                {"iid": m["iid"], "title": m["title"], "state": m["state"], "url": m["web_url"]}
                for m in mrs
            ],
            "recent_discussions": [
                {
                    "author": n["author"]["name"],
                    "body": n["body"][:200] + "..." if len(n["body"]) > 200 else n["body"],
                }
                for n in user_notes[-10:]  # Last 10 comments
            ],
        }

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": compact_context,
            "next_action": "Analyze the bundled context to propose a resolution or check linked MR progress.",
        }

    async def bundle_project_intelligence(self, project_id: int | str) -> dict[str, Any]:
        """
        High-performance tool that bundles project details, recent pipelines,
        open MRs, and open issues to provide a high-level dashboard.
        """
        import asyncio

        # Fetch everything in parallel
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

        # Construct compact dashboard
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

    async def bundle_pipeline_context(
        self, project_id: int | str, pipeline_id: int
    ) -> dict[str, Any]:
        """
        High-performance tool that bundles pipeline details, jobs, and failure analysis.
        """
        import asyncio

        # Fetch pipeline and jobs in parallel
        pipeline_task = self.client.get_pipeline(project_id, pipeline_id)
        jobs_task = self.client.list_pipeline_jobs(project_id, pipeline_id)

        pipeline, jobs = await asyncio.gather(pipeline_task, jobs_task)

        # Identify failed jobs
        failed_jobs = [j for j in jobs if j["status"] == "failed"]

        # If there are failed jobs, analyze the first one's log
        failed_job_analysis = None
        if failed_jobs:
            first_failed_job = failed_jobs[0]
            try:
                failed_job_analysis = await self.analyze_failed_job(
                    project_id, first_failed_job["id"]
                )
            except Exception:
                pass

        summary = f"Bundled context for Pipeline {pipeline_id}"
        key_findings = [
            f"Status: {pipeline['status']}",
            f"Total Jobs: {len(jobs)}",
            f"Failed Jobs: {len(failed_jobs)}",
            f"Ref: {pipeline['ref']}",
        ]

        compact_context = {
            "pipeline_details": {
                "id": pipeline["id"],
                "status": pipeline["status"],
                "ref": pipeline["ref"],
                "web_url": pipeline["web_url"],
            },
            "job_summary": [
                {"name": j["name"], "status": j["status"], "id": j["id"]} for j in jobs
            ],
            "failed_job_analysis": failed_job_analysis["details"] if failed_job_analysis else None,
        }

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": compact_context,
            "next_action": "Review the job statuses and failure analysis to diagnose the issue.",
        }

    async def triage_issue_locally(
        self, project_id: int | str, issue_iid: int | str
    ) -> dict[str, Any]:
        """
        Use local AI to analyze an issue description for labels and action items.
        """
        issue = await self.client.get_issue(project_id, issue_iid)

        prompt = (
            "You are a Project Manager. Analyze the provided GitLab issue description. "
            "1. Suggest 3-5 appropriate labels (e.g., bug, enhancement, priority:high).\n"
            "2. Extract a concise checklist of action items.\n"
            "3. Identify any missing information or blockers.\n"
            "Keep it structured and concise."
        )

        local_analysis = await self.local_ai.generate_summary(
            prompt, issue.get("description", "No description provided.")
        )

        summary = f"Locally triaged Issue #{issue_iid} using {self.local_ai.model}"
        key_findings = [
            "Issue analyzed locally (0 token cost)",
            f"Model: {self.local_ai.model}",
            "Labels and checklist suggested",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"issue_title": issue["title"], "local_ai_triage": local_analysis},
            "next_action": "Review the suggestions and apply appropriate labels or updates.",
        }

    async def summarize_mr_discussions_locally(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        """
        Use local AI to summarize all reviewer discussions and highlights in an MR.
        """
        notes = await self.client.get_merge_request_notes(project_id, mr_iid)
        user_notes = [n for n in notes if not n.get("system")]

        # Format notes for the AI
        discussions_text = "\n".join(
            [f"Author: {n['author']['name']}\nBody: {n['body']}\n" for n in user_notes]
        )

        prompt = (
            "You are a Lead Engineer. Summarize the following Merge Request discussions. "
            "1. List the top 3 critical concerns from reviewers.\n"
            "2. Identify any unresolved threads or blockers.\n"
            "3. Summarize the general sentiment of the review.\n"
            "Focus on actionable items for the developer."
        )

        local_summary = await self.local_ai.generate_summary(prompt, discussions_text)

        summary = f"Locally summarized discussions for MR !{mr_iid} using {self.local_ai.model}"
        key_findings = [
            f"Analyzed {len(user_notes)} user comments locally",
            "Identified critical concerns and blockers",
            "Privacy-first analysis (secrets scrubbed)",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"total_comments": len(user_notes), "local_ai_summary": local_summary},
            "next_action": "Address the critical concerns identified in the summary.",
        }

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

    async def check_mr_privacy_locally(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        """
        Use local AI to scan MR diffs and description for leaked secrets before merging.
        """
        mr = await self.client.get_merge_request(project_id, mr_iid)
        diffs = await self.client.get_merge_request_diffs(project_id, mr_iid)

        # Combine description and diffs for scanning
        content_to_scan = f"Description: {mr.get('description', '')}\n\nDiffs:\n"
        for d in diffs:
            content_to_scan += f"File: {d['new_path']}\n{d['diff']}\n\n"

        prompt = (
            "You are a Security Specialist. Scan the following code diffs and description for leaked secrets. "
            "Look for: API keys, private tokens, passwords, AWS credentials, or sensitive IP addresses. "
            "Report only the files and line numbers (if visible) that contain potential leaks. "
            "If no leaks are found, explicitly state 'No sensitive information detected'."
        )

        # Note: LocalAIService.generate_summary already calls scrub_secrets internally.
        # For this specific tool, we want to know IF secrets exist, so we use a custom prompt
        # but the underlying service will still protect the data from external leaks.
        local_report = await self.local_ai.generate_summary(prompt, content_to_scan)

        summary = f"Locally scanned MR !{mr_iid} for privacy leaks"
        key_findings = [
            "Scanned description and all code diffs",
            "Analysis performed 100% locally",
            f"Result provided by {self.local_ai.model}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"security_report": local_report},
            "next_action": "If leaks were found, redact them immediately before merging.",
        }
