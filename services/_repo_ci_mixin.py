from __future__ import annotations

import asyncio
import base64
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from gitlab.client import GitLabClient
    from services.local_ai_service import LocalAIService

logger = structlog.get_logger(__name__)


class _RepoCIMixin:
    """Repository and CI/CD domain methods for GitLabService."""

    client: GitLabClient
    local_ai: LocalAIService

    if TYPE_CHECKING:

        async def analyze_failed_job(
            self, project_id: int | str, job_id: int | str
        ) -> dict[str, Any]: ...

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
            content = await self.client.get_repository_file_raw(project_id, file_path, ref=ref)
            filename = file_path.split("/")[-1]
            source = f"project {project_id}, path {file_path}, ref {ref}"
        else:
            return {
                "summary": "Error: Missing required parameters",
                "key_findings": [
                    "Must provide either 'raw_url' or both 'project_id' and 'file_path'"
                ],
                "details": {},
                "next_action": "Provide the required parameters and try again.",
            }

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
            if isinstance(res, BaseException):
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
            if isinstance(res, BaseException):
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

    async def list_project_environments(self, project_id: int | str) -> dict[str, Any]:
        environments = await self.client.list_project_environments(project_id)

        return {
            "summary": f"Found {len(environments)} environments for project {project_id}",
            "key_findings": [
                f"{environment.get('name', 'N/A')}: {environment.get('state', 'unknown')}"
                for environment in environments[:10]
            ],
            "details": {"environments": environments},
            "next_action": "Review deployment environment status and URLs.",
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
        data: dict[str, Any] = {}
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

    async def bundle_pipeline_context(
        self, project_id: int | str, pipeline_id: int
    ) -> dict[str, Any]:
        """
        High-performance tool that bundles pipeline details, jobs, and failure analysis.
        """
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
            except Exception as e:
                logger.warning(
                    "bundle_pipeline_failed_job_analysis_error",
                    pipeline_id=pipeline_id,
                    job_id=first_failed_job["id"],
                    error=str(e),
                )
                failed_job_analysis = {"error": f"Failed to analyze job log: {e}"}

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
            "failed_job_analysis": failed_job_analysis.get("details")
            if failed_job_analysis
            else None,
        }

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": compact_context,
            "next_action": "Review the job statuses and failure analysis to diagnose the issue.",
        }
