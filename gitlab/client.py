import re
import urllib.parse
from typing import Any, Optional

import httpx
import structlog

from config import settings

logger = structlog.get_logger(__name__)

class GitLabClient:
    _instance: Optional['GitLabClient'] = None
    
    def __init__(self):
        self.base_url = f"{settings.gitlab_url.rstrip('/')}/api/v4"
        self.headers = {
            "PRIVATE-TOKEN": settings.gitlab_token,
            "Accept": "application/json",
            "User-Agent": "Gitlab_AI_MCP/0.3.0"
        }
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=httpx.Timeout(30.0, connect=5.0),
            follow_redirects=True,
            http2=True,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
        )

    @classmethod
    async def get_instance(cls) -> 'GitLabClient':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def aclose(self):
        await self.client.aclose()
        if GitLabClient._instance is self:
            GitLabClient._instance = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def _format_project_id(self, project_id: int | str) -> str:
        """Encodes project path if it's a string."""
        if isinstance(project_id, str) and "/" in project_id:
            return urllib.parse.quote(project_id, safe="")
        return str(project_id)

    def _build_absolute_url(self, url_or_path: str) -> str:
        if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
            return url_or_path
        return f"{settings.gitlab_url.rstrip('/')}{url_or_path}"

    def _append_private_token(self, url: str) -> str:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}private_token={settings.gitlab_token}"

    def _redact_url(self, url: str) -> str:
        return re.sub(r"([?&]private_token=)[^&]+", r"\1[REDACTED]", url)

    def parse_gitlab_url(self, url: str) -> dict[str, Any]:
        """
        Parses a GitLab URL to extract project path, resource type, and ID.
        """
        pattern = r"https?://[^/]+/(.*?)/-/(merge_requests|jobs|pipelines|issues|repository/files)/?([^?#]*)"
        match = re.search(pattern, url)

        if not match:
            return {}

        project_path = match.group(1)
        resource_type = match.group(2)
        resource_id = match.group(3).strip("/")

        return {
            "project_path": project_path,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "full_path": url
        }

    def parse_mr_diff_url(self, url: str) -> dict[str, Any]:
        """
        Parses a GitLab MR diff URL into its components.
        Format: https://host/{project_path}/-/merge_requests/{mr_iid}/diffs?diff_id={version_id}#{anchor}
        Anchor format: {file_sha}_{old_line}_{new_line}
        """
        parsed = urllib.parse.urlparse(url)
        path_match = re.match(r"/(.*?)/-/merge_requests/(\d+)", parsed.path)
        if not path_match:
            return {}

        project_path = path_match.group(1)
        mr_iid = int(path_match.group(2))
        qs = urllib.parse.parse_qs(parsed.query)
        diff_id = int(qs["diff_id"][0]) if "diff_id" in qs else None
        anchor = parsed.fragment or None

        result: dict[str, Any] = {
            "project_path": project_path,
            "mr_iid": mr_iid,
            "diff_id": diff_id,
            "anchor": anchor,
        }

        # Parse anchor into line reference: {sha}_{old_line}_{new_line}
        if anchor:
            parts = anchor.rsplit("_", 2)
            if len(parts) == 3:
                result["anchor_file_sha"] = parts[0]
                result["anchor_old_line"] = int(parts[1]) if parts[1].isdigit() else None
                result["anchor_new_line"] = int(parts[2]) if parts[2].isdigit() else None

        return result

    async def get_mr_diff_version(self, project_id: int | str, mr_iid: int, version_id: int) -> dict[str, Any]:
        return await self.get(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/versions/{version_id}"
        )

    async def _request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        try:
            response = await self.client.request(method, endpoint, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            logger.error("gitlab_api_error", 
                         status_code=e.response.status_code, 
                         endpoint=endpoint, 
                         error=e.response.text)
            raise
        except Exception as e:
            logger.error("gitlab_unexpected_error", endpoint=endpoint, error=str(e))
            raise

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        response = await self._request("GET", endpoint, params=params)
        return response.json() if response.content else None

    async def get_all(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """
        Helper to fetch all pages for a paginated endpoint.
        """
        all_results = []
        current_params = (params or {}).copy()
        current_params["per_page"] = 100
        
        while True:
            response = await self._request("GET", endpoint, params=current_params)
            results = response.json()
            if not results:
                break
            
            all_results.extend(results)
            
            next_page = response.headers.get("X-Next-Page")
            if not next_page:
                break
            current_params["page"] = next_page
            
        return all_results

    async def post(self, endpoint: str, data: dict[str, Any] | None = None) -> Any:
        response = await self._request("POST", endpoint, json=data)
        return response.json() if response.content else None

    async def put(self, endpoint: str, data: dict[str, Any] | None = None) -> Any:
        response = await self._request("PUT", endpoint, json=data)
        return response.json() if response.content else None

    async def delete(self, endpoint: str) -> Any:
        response = await self._request("DELETE", endpoint)
        return response.json() if response.content else None

    async def get_current_user(self) -> dict[str, Any]:
        return await self.get("/user")

    async def list_all_issues(self, state: str = "opened", scope: str = "assigned_to_me") -> list[dict[str, Any]]:
        params = {"state": state, "scope": scope}
        return await self.get("/issues", params=params)

    async def list_projects(self, search: str | None = None, membership: bool = True) -> list[dict[str, Any]]:
        params = {"membership": str(membership).lower()}
        if search:
            params["search"] = search
        return await self.get("/projects", params=params)

    async def get_project(self, project_id: int | str) -> dict[str, Any]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}")

    async def list_issues(self, project_id: int | str, state: str = "opened") -> list[dict[str, Any]]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}/issues", params={"state": state})

    async def get_issue(self, project_id: int | str, issue_iid: int) -> dict[str, Any]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}/issues/{issue_iid}")

    async def update_issue(self, project_id: int | str, issue_iid: int, data: dict[str, Any]) -> dict[str, Any]:
        return await self.put(f"/projects/{self._format_project_id(project_id)}/issues/{issue_iid}", data=data)

    async def list_merge_requests(self, project_id: int | str, state: str = "opened") -> list[dict[str, Any]]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}/merge_requests", params={"state": state})

    async def get_merge_request(self, project_id: int | str, mr_iid: int) -> dict[str, Any]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}")

    async def update_merge_request(self, project_id: int | str, mr_iid: int, data: dict[str, Any]) -> dict[str, Any]:
        return await self.put(f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}", data=data)

    async def approve_merge_request(self, project_id: int | str, mr_iid: int) -> dict[str, Any]:
        return await self.post(f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/approve")

    async def get_issue_notes(self, project_id: int | str, issue_iid: int) -> list[dict[str, Any]]:
        return await self.get_all(f"/projects/{self._format_project_id(project_id)}/issues/{issue_iid}/notes")

    async def create_issue_note(self, project_id: int | str, issue_iid: int, body: str) -> dict[str, Any]:
        return await self.post(f"/projects/{self._format_project_id(project_id)}/issues/{issue_iid}/notes", data={"body": body})

    async def get_merge_request_notes(self, project_id: int | str, mr_iid: int) -> list[dict[str, Any]]:
        return await self.get_all(f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/notes")

    async def create_merge_request_note(self, project_id: int | str, mr_iid: int, body: str) -> dict[str, Any]:
        return await self.post(f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/notes", data={"body": body})

    async def get_merge_request_diffs(self, project_id: int | str, mr_iid: int) -> list[dict[str, Any]]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/diffs")

    async def get_repository_tree(self, project_id: int | str, path: str = "", ref: str = "main") -> list[dict[str, Any]]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}/repository/tree", params={"path": path, "ref": ref})

    async def get_file_content(self, project_id: int | str, file_path: str, ref: str = "main") -> dict[str, Any]:
        encoded_path = urllib.parse.quote(file_path, safe="")
        return await self.get(f"/projects/{self._format_project_id(project_id)}/repository/files/{encoded_path}", params={"ref": ref})

    async def list_pipelines(self, project_id: int | str) -> list[dict[str, Any]]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}/pipelines")

    async def get_pipeline(self, project_id: int | str, pipeline_id: int) -> dict[str, Any]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}/pipelines/{pipeline_id}")

    async def list_pipeline_jobs(self, project_id: int | str, pipeline_id: int) -> list[dict[str, Any]]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}/pipelines/{pipeline_id}/jobs")

    async def search_users(self, search: str) -> list[dict[str, Any]]:
        return await self.get("/users", params={"search": search})

    async def create_branch(self, project_id: int | str, branch: str, ref: str) -> dict[str, Any]:
        data = {"branch": branch, "ref": ref}
        return await self.post(f"/projects/{self._format_project_id(project_id)}/repository/branches", data=data)

    async def create_repository_file(self, project_id: int | str, file_path: str, branch: str, content: str, commit_message: str) -> dict[str, Any]:
        encoded_path = urllib.parse.quote(file_path, safe="")
        data = {
            "branch": branch,
            "content": content,
            "commit_message": commit_message
        }
        return await self.post(f"/projects/{self._format_project_id(project_id)}/repository/files/{encoded_path}", data=data)

    async def update_repository_file(self, project_id: int | str, file_path: str, branch: str, content: str, commit_message: str) -> dict[str, Any]:
        encoded_path = urllib.parse.quote(file_path, safe="")
        data = {
            "branch": branch,
            "content": content,
            "commit_message": commit_message
        }
        return await self.put(f"/projects/{self._format_project_id(project_id)}/repository/files/{encoded_path}", data=data)

    async def search_code(self, project_id: int | str, search: str) -> list[dict[str, Any]]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}/search", params={"scope": "blobs", "search": search})

    async def global_search(self, scope: str, search: str) -> list[dict[str, Any]]:
        return await self.get("/search", params={"scope": scope, "search": search})

    async def get_pipeline_bridges(self, project_id: int | str, pipeline_id: int) -> list[dict[str, Any]]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}/pipelines/{pipeline_id}/bridges")

    async def get_job_log(self, project_id: int | str, job_id: int) -> str:
        try:
            response = await self.client.get(f"/projects/{self._format_project_id(project_id)}/jobs/{job_id}/trace")
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            logger.error("job_log_error", status_code=e.response.status_code, job_id=job_id)
            raise

    async def get_merge_request_discussions(self, project_id: int | str, mr_iid: int) -> list[dict[str, Any]]:
        return await self.get_all(f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/discussions")

    async def resolve_merge_request_discussion(self, project_id: int | str, mr_iid: int, discussion_id: str, resolved: bool = True) -> dict[str, Any]:
        params = {"resolved": str(resolved).lower()}
        return await self.put(f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/discussions/{discussion_id}", data=params)

    async def retry_job(self, project_id: int | str, job_id: int) -> dict[str, Any]:
        return await self.post(f"/projects/{self._format_project_id(project_id)}/jobs/{job_id}/retry")

    async def retry_pipeline(self, project_id: int | str, pipeline_id: int) -> dict[str, Any]:
        return await self.post(f"/projects/{self._format_project_id(project_id)}/pipelines/{pipeline_id}/retry")

    async def get_job_artifact_file(self, project_id: int | str, job_id: int, artifact_path: str) -> str:
        response = await self.client.get(f"/projects/{self._format_project_id(project_id)}/jobs/{job_id}/artifacts/{artifact_path}")
        response.raise_for_status()
        return response.text

    async def list_repository_commits(self, project_id: int | str, ref_name: str | None = None) -> list[dict[str, Any]]:
        params = {}
        if ref_name:
            params["ref_name"] = ref_name
        return await self.get(f"/projects/{self._format_project_id(project_id)}/repository/commits", params=params)

    async def get_commit_details(self, project_id: int | str, sha: str) -> dict[str, Any]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}/repository/commits/{sha}")

    async def get_file_blame(self, project_id: int | str, file_path: str, ref: str = "main") -> list[dict[str, Any]]:
        encoded_path = urllib.parse.quote(file_path, safe="")
        return await self.get(f"/projects/{self._format_project_id(project_id)}/repository/files/{encoded_path}/blame", params={"ref": ref})

    async def list_project_labels(self, project_id: int | str) -> list[dict[str, Any]]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}/labels")

    async def create_project_label(self, project_id: int | str, name: str, color: str, description: str | None = None) -> dict[str, Any]:
        data = {"name": name, "color": color}
        if description:
            data["description"] = description
        return await self.post(f"/projects/{self._format_project_id(project_id)}/labels", data=data)

    async def update_project_label(self, project_id: int | str, label_id: int | str, data: dict[str, Any]) -> dict[str, Any]:
        return await self.put(f"/projects/{self._format_project_id(project_id)}/labels/{label_id}", data=data)

    async def delete_project_label(self, project_id: int | str, label_id: int | str) -> dict[str, Any]:
        return await self.delete(f"/projects/{self._format_project_id(project_id)}/labels/{label_id}")

    async def list_project_environments(self, project_id: int | str) -> list[dict[str, Any]]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}/environments")

    async def merge_merge_request(self, project_id: int | str, mr_iid: int, data: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.put(f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/merge", data=data)

    async def add_merge_request_discussion_note(self, project_id: int | str, mr_iid: int, discussion_id: str, body: str) -> dict[str, Any]:
        return await self.post(f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/discussions/{discussion_id}/notes", data={"body": body})

    async def create_merge_request_discussion(self, project_id: int | str, mr_iid: int, body: str, position: dict[str, Any] | None = None) -> dict[str, Any]:
        data = {"body": body}
        if position:
            data["position"] = position
        return await self.post(f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/discussions", data=data)

    async def update_note(self, project_id: int | str, resource_type: str, resource_iid: int, note_id: int, body: str) -> dict[str, Any]:
        return await self.put(f"/projects/{self._format_project_id(project_id)}/{resource_type}/{resource_iid}/notes/{note_id}", data={"body": body})

    async def delete_note(self, project_id: int | str, resource_type: str, resource_iid: int, note_id: int) -> dict[str, Any]:
        return await self.delete(f"/projects/{self._format_project_id(project_id)}/{resource_type}/{resource_iid}/notes/{note_id}")

    async def create_merge_request(self, project_id: int | str, data: dict[str, Any]) -> dict[str, Any]:
        return await self.post(f"/projects/{self._format_project_id(project_id)}/merge_requests", data=data)

    async def trigger_pipeline(self, project_id: int | str, ref: str, variables: list[dict[str, str]] | None = None) -> dict[str, Any]:
        data = {"ref": ref}
        if variables:
            data["variables"] = variables
        return await self.post(f"/projects/{self._format_project_id(project_id)}/pipeline", data=data)

    async def list_merge_request_pipelines(self, project_id: int | str, mr_iid: int) -> list[dict[str, Any]]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/pipelines")

    async def list_project_members(self, project_id: int | str, query: str | None = None) -> list[dict[str, Any]]:
        params = {}
        if query:
            params["query"] = query
        return await self.get(f"/projects/{self._format_project_id(project_id)}/members", params=params)

    async def create_batch_commit(self, project_id: int | str, data: dict[str, Any]) -> dict[str, Any]:
        return await self.post(f"/projects/{self._format_project_id(project_id)}/repository/commits", data=data)

    async def get_job_artifacts_archive(self, project_id: int | str, job_id: int) -> bytes:
        response = await self.client.get(f"/projects/{self._format_project_id(project_id)}/jobs/{job_id}/artifacts")
        response.raise_for_status()
        return response.content

    async def get_raw_file(self, raw_url: str) -> str:
        """Fetch raw file content from a GitLab /-/raw/ URL.
        Accepts full URL or a path relative to the GitLab root.
        Returns the raw text content.
        """
        raw_url = self._build_absolute_url(raw_url)

        response = await self.client.get(raw_url)
        response.raise_for_status()
        return response.text

    async def fetch_upload(self, upload_url: str) -> tuple[bytes, str]:
        """Fetch a GitLab upload attachment with authentication.
        Accepts full URL or path relative to the GitLab root (e.g. /uploads/<hash>/file.png).
        Returns (content_bytes, content_type).
        """
        upload_url = self._build_absolute_url(upload_url)
        response = await self.client.get(upload_url)

        if response.status_code in (401, 403):
            tokenized_url = self._append_private_token(upload_url)
            logger.warning(
                "upload_header_auth_failed_falling_back_to_query_token",
                url=self._redact_url(tokenized_url),
                status_code=response.status_code,
            )
            response = await self.client.get(tokenized_url)

        response.raise_for_status()
        return response.content, response.headers.get("content-type", "application/octet-stream")

    async def cancel_pipeline(self, project_id: int | str, pipeline_id: int) -> dict[str, Any]:
        return await self.post(f"/projects/{self._format_project_id(project_id)}/pipelines/{pipeline_id}/cancel")

    async def cancel_job(self, project_id: int | str, job_id: int) -> dict[str, Any]:
        return await self.post(f"/projects/{self._format_project_id(project_id)}/jobs/{job_id}/cancel")

    async def play_job(self, project_id: int | str, job_id: int) -> dict[str, Any]:
        return await self.post(f"/projects/{self._format_project_id(project_id)}/jobs/{job_id}/play")

    async def rebase_merge_request(self, project_id: int | str, mr_iid: int) -> dict[str, Any]:
        return await self.put(f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/rebase")

    async def get_merge_request_approvals(self, project_id: int | str, mr_iid: int) -> dict[str, Any]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/approvals")

    async def list_project_variables(self, project_id: int | str) -> list[dict[str, Any]]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}/variables")

    async def create_project_variable(self, project_id: int | str, data: dict[str, Any]) -> dict[str, Any]:
        return await self.post(f"/projects/{self._format_project_id(project_id)}/variables", data=data)

    async def update_project_variable(self, project_id: int | str, key: str, data: dict[str, Any]) -> dict[str, Any]:
        return await self.put(f"/projects/{self._format_project_id(project_id)}/variables/{key}", data=data)

    async def delete_project_variable(self, project_id: int | str, key: str) -> dict[str, Any]:
        return await self.delete(f"/projects/{self._format_project_id(project_id)}/variables/{key}")
