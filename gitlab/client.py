import asyncio
import re
import urllib.parse
from typing import Any

import httpx
import structlog

from _version import __version__
from config import settings

logger = structlog.get_logger(__name__)


class GitLabClient:
    _instance: "GitLabClient | None" = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self):
        self.base_url = f"{settings.gitlab_url.rstrip('/')}/api/v4"
        self.headers = {
            "PRIVATE-TOKEN": settings.gitlab_token,
            "Accept": "application/json",
            "User-Agent": f"Gitlab_AI_MCP/{__version__}",
        }
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            # Maximize handshake buffer for slow self-hosted instances
            timeout=httpx.Timeout(60.0, connect=30.0),
            follow_redirects=True,
            http2=True,
            limits=httpx.Limits(
                max_keepalive_connections=20, max_connections=100, keepalive_expiry=60.0
            ),
        )
        # Dedicated client for web routes (uploads, raw files) without PRIVATE-TOKEN header
        self.web_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=30.0),
            follow_redirects=False,
            http2=True,
            limits=httpx.Limits(
                max_keepalive_connections=20, max_connections=100, keepalive_expiry=60.0
            ),
        )

    @classmethod
    async def get_instance(cls) -> "GitLabClient":
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    asyncio.create_task(cls._instance.warmup())
        return cls._instance

    async def warmup(self):
        """
        Warms up the connection pool with retries for cold starts.
        """
        for attempt in range(2):
            try:
                await self.get_current_user()
                logger.info("gitlab_connection_warmed_up", attempt=attempt + 1)
                return
            except Exception as e:
                if attempt == 0:
                    await asyncio.sleep(1.0)
                    continue
                logger.warning("gitlab_warmup_failed", error=str(e))

    async def aclose(self):
        await self.client.aclose()
        await self.web_client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

    def _format_project_id(self, project_id: int | str) -> str:
        """Encodes project path if it's a string."""
        if isinstance(project_id, str) and "/" in project_id:
            return urllib.parse.quote(project_id, safe="")
        return str(project_id)

    def _build_absolute_url(self, url_or_path: str) -> str:
        if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
            return url_or_path
        return f"{settings.gitlab_url.rstrip('/')}{url_or_path}"

    def _redact_url(self, url: str) -> str:
        return re.sub(r"([?&]private_token=)[^&]+", r"\1[REDACTED]", url)

    def _is_gitlab_host(self, url: str) -> bool:
        """Ensure a URL belongs to the configured GitLab instance."""
        parsed = urllib.parse.urlparse(url)
        gitlab_parsed = urllib.parse.urlparse(settings.gitlab_url)
        return parsed.netloc == gitlab_parsed.netloc

    def _is_secure_gitlab_url(self, url: str) -> bool:
        """Allow HTTPS GitLab URLs, plus HTTP for loopback development hosts."""
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme == "https" or (
            parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        )

    def parse_gitlab_url(self, url: str) -> dict[str, Any]:
        """
        Parses a GitLab URL to extract project path, resource type, and ID.
        """
        pattern = r"https?://[^/]+/(.*?)/-/(merge_requests|jobs|pipelines|issues|work_items|epics|snippets|blob|tree|commits|commit|repository/files)/?([^?#]*)"
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
            "full_path": url,
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

    async def get_mr_diff_version(
        self, project_id: int | str, mr_iid: int | str, version_id: int
    ) -> dict[str, Any]:
        return await self.get(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/versions/{version_id}"
        )

    async def get_latest_merge_request_version(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        """Fetches the latest MR diff version and returns normalized SHAs for diff comments."""
        versions = await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/versions"
        )
        if not versions:
            raise ValueError(
                "No merge request versions returned — cannot resolve base_sha/start_sha/head_sha for diff comments."
            )
        latest = versions[0]
        base_sha = latest.get("base_commit_sha", "")
        start_sha = latest.get("start_commit_sha", "")
        head_sha = latest.get("head_commit_sha", "")
        if not base_sha or not start_sha or not head_sha:
            raise ValueError(
                "Merge request version is missing base_commit_sha, start_commit_sha, or head_commit_sha."
            )
        return {
            "id": latest.get("id"),
            "base_sha": base_sha,
            "start_sha": start_sha,
            "head_sha": head_sha,
            "created_at": latest.get("created_at", ""),
            "real_size": latest.get("real_size", ""),
        }

    async def build_text_diff_position(
        self,
        project_id: int | str,
        mr_iid: int | str,
        new_path: str,
        old_path: str | None = None,
        new_line: int | None = None,
        old_line: int | None = None,
    ) -> dict[str, Any]:
        """Resolves the latest MR version SHAs and builds a GitLab text position object."""
        if not new_path or not new_path.strip():
            raise ValueError("Simple diff position requires non-empty new_path.")
        if new_line is None and old_line is None:
            raise ValueError(
                "Simple diff position requires at least one of old_line or new_line (positive integers)."
            )
        version = await self.get_latest_merge_request_version(project_id, mr_iid)
        position: dict[str, Any] = {
            "position_type": "text",
            "base_sha": version["base_sha"],
            "start_sha": version["start_sha"],
            "head_sha": version["head_sha"],
            "old_path": old_path.strip() if old_path and old_path.strip() else new_path.strip(),
            "new_path": new_path.strip(),
        }
        if old_line is not None:
            position["old_line"] = old_line
        if new_line is not None:
            position["new_line"] = new_line
        return position

    async def _request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """
        Centralized request method with rate-limiting and retry logic.
        """
        max_retries = settings.gitlab_max_retries
        retry_delay = settings.gitlab_retry_delay

        for attempt in range(max_retries + 1):
            try:
                # Handle relative endpoints
                url = endpoint
                if not url.startswith("http"):
                    url = f"{self.base_url}/{endpoint.lstrip('/')}"

                response = await self.client.request(method, url, **kwargs)

                # Check for 429 Too Many Requests
                if response.status_code == 429:
                    if attempt < max_retries:
                        # Extract Retry-After header if present
                        wait_time = float(
                            response.headers.get("Retry-After", retry_delay * (2**attempt))
                        )
                        logger.warning(
                            "rate_limit_exceeded",
                            attempt=attempt + 1,
                            wait_time=wait_time,
                            endpoint=self._redact_url(endpoint),
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        response.raise_for_status()

                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as e:
                # Only retry on 429 or 5xx
                if attempt < max_retries and (
                    e.response.status_code == 429 or 500 <= e.response.status_code < 600
                ):
                    wait_time = retry_delay * (2**attempt)
                    logger.warning(
                        "gitlab_retry_request",
                        status_code=e.response.status_code,
                        attempt=attempt + 1,
                        wait_time=wait_time,
                        endpoint=self._redact_url(endpoint),
                    )
                    await asyncio.sleep(wait_time)
                    continue

                error_text = e.response.text
                # Scrub potential secrets from error response before logging
                error_text = re.sub(
                    r"private_token=[^&\s]+", "private_token=[REDACTED]", error_text
                )
                error_text = re.sub(
                    r"glpat-[a-zA-Z0-9\-]{20,}", "[REDACTED_GITLAB_TOKEN]", error_text
                )
                error_text = re.sub(r"AKIA[0-9A-Z]{16}", "[REDACTED_AWS_KEY]", error_text)
                logger.error(
                    "gitlab_api_error",
                    status_code=e.response.status_code,
                    endpoint=self._redact_url(endpoint),
                    error=error_text,
                )
                raise
            except httpx.RequestError as e:
                if attempt < max_retries:
                    wait_time = retry_delay * (2**attempt)
                    logger.warning(
                        "gitlab_unexpected_retry",
                        error=str(e),
                        attempt=attempt + 1,
                        wait_time=wait_time,
                        endpoint=self._redact_url(endpoint),
                    )
                    await asyncio.sleep(wait_time)
                    continue

                logger.error(
                    "gitlab_unexpected_error", endpoint=self._redact_url(endpoint), error=str(e)
                )
                raise

        # This part should theoretically not be reached due to raises in the loop
        raise Exception(
            f"Failed to request {self._redact_url(endpoint)} after {max_retries} retries"
        )

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        response = await self._request("GET", endpoint, params=params)
        return response.json() if response.content else None

    async def get_all(
        self, endpoint: str, params: dict[str, Any] | None = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Helper to fetch all pages for a paginated endpoint, up to an optional limit.
        """
        all_results = []
        current_params = (params or {}).copy()
        # Optimization: Don't request 100 items if we only need a few
        current_params["per_page"] = min(100, limit or 100)

        while True:
            response = await self._request("GET", endpoint, params=current_params)
            results = response.json()
            if not results:
                break

            all_results.extend(results)

            # Stop if we've reached the limit
            if limit and len(all_results) >= limit:
                return all_results[:limit]

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

    async def get_version(self) -> httpx.Response:
        """Return raw httpx Response for the GitLab /version endpoint."""
        return await self._request("GET", "/version")

    async def list_all_issues(
        self, state: str = "opened", scope: str = "assigned_to_me"
    ) -> list[dict[str, Any]]:
        params = {"state": state, "scope": scope}
        return await self.get_all("/issues", params=params, limit=100)

    async def list_projects(
        self,
        search: str | None = None,
        membership: bool = True,
        group_id: int | str | None = None,
        limit: int | None = 100,
    ) -> list[dict[str, Any]]:
        params = {"membership": str(membership).lower()}
        if search:
            params["search"] = search

        endpoint = "/projects"
        if group_id:
            endpoint = f"/groups/{self._format_project_id(group_id)}/projects"

        return await self.get_all(endpoint, params=params, limit=limit)

    async def list_group_projects(
        self, group_id: int | str, limit: int | None = 100
    ) -> list[dict[str, Any]]:
        return await self.get_all(
            f"/groups/{self._format_project_id(group_id)}/projects", limit=limit
        )

    async def get_project(self, project_id: int | str) -> dict[str, Any]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}")

    async def list_branches(self, project_id: int | str) -> list[dict[str, Any]]:
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/repository/branches"
        )

    async def get_branch(self, project_id: int | str, branch: str) -> dict[str, Any]:
        return await self.get(
            f"/projects/{self._format_project_id(project_id)}/repository/branches/{urllib.parse.quote(branch, safe='')}"
        )

    async def list_tags(
        self, project_id: int | str, limit: int | None = 50
    ) -> list[dict[str, Any]]:
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/repository/tags", limit=limit
        )

    async def get_tag(self, project_id: int | str, tag: str) -> dict[str, Any]:
        return await self.get(
            f"/projects/{self._format_project_id(project_id)}/repository/tags/{urllib.parse.quote(tag, safe='')}"
        )

    async def list_issues(
        self, project_id: int | str, state: str = "opened", limit: int = 100
    ) -> list[dict[str, Any]]:
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/issues",
            params={"state": state},
            limit=limit,
        )

    async def get_issue(self, project_id: int | str, issue_iid: int | str) -> dict[str, Any]:
        return await self.get(f"/projects/{self._format_project_id(project_id)}/issues/{issue_iid}")

    async def create_issue(self, project_id: int | str, data: dict[str, Any]) -> dict[str, Any]:
        return await self.post(f"/projects/{self._format_project_id(project_id)}/issues", data=data)

    async def get_issue_related_mrs(
        self, project_id: int | str, issue_iid: int | str
    ) -> list[dict[str, Any]]:
        return await self.get(
            f"/projects/{self._format_project_id(project_id)}/issues/{issue_iid}/related_merge_requests"
        )

    async def update_issue(
        self, project_id: int | str, issue_iid: int | str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return await self.put(
            f"/projects/{self._format_project_id(project_id)}/issues/{issue_iid}", data=data
        )

    async def list_merge_requests(
        self, project_id: int | str, state: str = "opened", limit: int = 100
    ) -> list[dict[str, Any]]:
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/merge_requests",
            params={"state": state},
            limit=limit,
        )

    async def get_merge_request(self, project_id: int | str, mr_iid: int | str) -> dict[str, Any]:
        return await self.get(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}"
        )

    async def update_merge_request(
        self, project_id: int | str, mr_iid: int | str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return await self.put(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}", data=data
        )

    async def approve_merge_request(self, project_id: int | str, mr_iid: int | str) -> dict[str, Any]:
        return await self.post(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/approve"
        )

    async def get_issue_notes(self, project_id: int | str, issue_iid: int | str) -> list[dict[str, Any]]:
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/issues/{issue_iid}/notes"
        )

    async def create_issue_note(
        self, project_id: int | str, issue_iid: int | str, body: str
    ) -> dict[str, Any]:
        return await self.post(
            f"/projects/{self._format_project_id(project_id)}/issues/{issue_iid}/notes",
            data={"body": body},
        )

    async def get_merge_request_notes(
        self, project_id: int | str, mr_iid: int | str
    ) -> list[dict[str, Any]]:
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/notes"
        )

    async def create_merge_request_note(
        self, project_id: int | str, mr_iid: int | str, body: str
    ) -> dict[str, Any]:
        return await self.post(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/notes",
            data={"body": body},
        )

    async def get_merge_request_diffs(
        self, project_id: int | str, mr_iid: int | str
    ) -> list[dict[str, Any]]:
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/diffs"
        )

    async def get_repository_tree(
        self, project_id: int | str, path: str = "", ref: str | None = None
    ) -> list[dict[str, Any]]:
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/repository/tree",
            params={"path": path, "ref": ref or "HEAD"},
            limit=500,
        )

    async def get_file_content(
        self, project_id: int | str, file_path: str, ref: str | None = None
    ) -> dict[str, Any]:
        encoded_path = urllib.parse.quote(file_path, safe="")
        return await self.get(
            f"/projects/{self._format_project_id(project_id)}/repository/files/{encoded_path}",
            params={"ref": ref or "HEAD"},
        )

    async def list_pipelines(self, project_id: int | str, limit: int = 20) -> list[dict[str, Any]]:
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/pipelines", limit=limit
        )

    async def get_pipeline(self, project_id: int | str, pipeline_id: int | str) -> dict[str, Any]:
        return await self.get(
            f"/projects/{self._format_project_id(project_id)}/pipelines/{pipeline_id}"
        )

    async def list_pipeline_jobs(
        self, project_id: int | str, pipeline_id: int | str, limit: int = 200
    ) -> list[dict[str, Any]]:
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/pipelines/{pipeline_id}/jobs",
            limit=limit,
        )

    async def search_users(self, search: str) -> list[dict[str, Any]]:
        return await self.get_all("/users", params={"search": search}, limit=50)

    async def create_branch(self, project_id: int | str, branch: str, ref: str) -> dict[str, Any]:
        data = {"branch": branch, "ref": ref}
        return await self.post(
            f"/projects/{self._format_project_id(project_id)}/repository/branches", data=data
        )

    async def create_repository_file(
        self, project_id: int | str, file_path: str, branch: str, content: str, commit_message: str
    ) -> dict[str, Any]:
        encoded_path = urllib.parse.quote(file_path, safe="")
        data = {"branch": branch, "content": content, "commit_message": commit_message}
        return await self.post(
            f"/projects/{self._format_project_id(project_id)}/repository/files/{encoded_path}",
            data=data,
        )

    async def update_repository_file(
        self, project_id: int | str, file_path: str, branch: str, content: str, commit_message: str
    ) -> dict[str, Any]:
        encoded_path = urllib.parse.quote(file_path, safe="")
        data = {"branch": branch, "content": content, "commit_message": commit_message}
        return await self.put(
            f"/projects/{self._format_project_id(project_id)}/repository/files/{encoded_path}",
            data=data,
        )

    async def search_code(self, project_id: int | str, search: str) -> list[dict[str, Any]]:
        return await self.get(
            f"/projects/{self._format_project_id(project_id)}/search",
            params={"scope": "blobs", "search": search},
        )

    async def global_search(self, scope: str, search: str) -> list[dict[str, Any]]:
        return await self.get("/search", params={"scope": scope, "search": search})

    async def get_pipeline_bridges(
        self, project_id: int | str, pipeline_id: int | str
    ) -> list[dict[str, Any]]:
        return await self.get(
            f"/projects/{self._format_project_id(project_id)}/pipelines/{pipeline_id}/bridges"
        )

    async def get_job_log(self, project_id: int | str, job_id: int | str) -> str:
        response = await self._request(
            "GET", f"/projects/{self._format_project_id(project_id)}/jobs/{job_id}/trace"
        )
        return response.text

    async def get_merge_request_discussions(
        self, project_id: int | str, mr_iid: int | str
    ) -> list[dict[str, Any]]:
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/discussions"
        )

    async def resolve_merge_request_discussion(
        self, project_id: int | str, mr_iid: int | str, discussion_id: str, resolved: bool = True
    ) -> dict[str, Any]:
        params = {"resolved": str(resolved).lower()}
        return await self.put(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/discussions/{discussion_id}",
            data=params,
        )

    async def retry_job(self, project_id: int | str, job_id: int | str) -> dict[str, Any]:
        return await self.post(
            f"/projects/{self._format_project_id(project_id)}/jobs/{job_id}/retry"
        )

    async def retry_pipeline(self, project_id: int | str, pipeline_id: int | str) -> dict[str, Any]:
        return await self.post(
            f"/projects/{self._format_project_id(project_id)}/pipelines/{pipeline_id}/retry"
        )

    async def get_job_artifact_file(
        self, project_id: int | str, job_id: int | str, artifact_path: str
    ) -> str:
        response = await self._request(
            "GET",
            f"/projects/{self._format_project_id(project_id)}/jobs/{job_id}/artifacts/{artifact_path}",
        )
        return response.text

    async def list_repository_commits(
        self, project_id: int | str, ref_name: str | None = None
    ) -> list[dict[str, Any]]:
        params = {}
        if ref_name:
            params["ref_name"] = ref_name
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/repository/commits",
            params=params,
            limit=500,
        )

    async def get_commit_details(self, project_id: int | str, sha: str) -> dict[str, Any]:
        return await self.get(
            f"/projects/{self._format_project_id(project_id)}/repository/commits/{sha}"
        )

    async def get_file_blame(
        self, project_id: int | str, file_path: str, ref: str | None = None
    ) -> list[dict[str, Any]]:
        encoded_path = urllib.parse.quote(file_path, safe="")
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/repository/files/{encoded_path}/blame",
            params={"ref": ref or "HEAD"},
            limit=1000,
        )

    async def list_project_labels(self, project_id: int | str) -> list[dict[str, Any]]:
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/labels", limit=500
        )

    async def create_project_label(
        self, project_id: int | str, name: str, color: str, description: str | None = None
    ) -> dict[str, Any]:
        data = {"name": name, "color": color}
        if description:
            data["description"] = description
        return await self.post(f"/projects/{self._format_project_id(project_id)}/labels", data=data)

    async def update_project_label(
        self, project_id: int | str, label_id: int | str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return await self.put(
            f"/projects/{self._format_project_id(project_id)}/labels/{label_id}", data=data
        )

    async def delete_project_label(
        self, project_id: int | str, label_id: int | str
    ) -> dict[str, Any]:
        return await self.delete(
            f"/projects/{self._format_project_id(project_id)}/labels/{label_id}"
        )

    async def list_project_environments(self, project_id: int | str) -> list[dict[str, Any]]:
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/environments", limit=100
        )

    async def merge_merge_request(
        self, project_id: int | str, mr_iid: int | str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self.put(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/merge",
            data=data,
        )

    async def add_merge_request_discussion_note(
        self, project_id: int | str, mr_iid: int | str, discussion_id: str, body: str
    ) -> dict[str, Any]:
        return await self.post(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/discussions/{discussion_id}/notes",
            data={"body": body},
        )

    async def get_issue_discussions(
        self, project_id: int | str, issue_iid: int | str
    ) -> list[dict[str, Any]]:
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/issues/{issue_iid}/discussions"
        )

    async def reply_to_issue_discussion(
        self, project_id: int | str, issue_iid: int | str, discussion_id: str, body: str
    ) -> dict[str, Any]:
        return await self.post(
            f"/projects/{self._format_project_id(project_id)}/issues/{issue_iid}/discussions/{discussion_id}/notes",
            data={"body": body},
        )

    async def create_merge_request_discussion(
        self, project_id: int | str, mr_iid: int | str, body: str, position: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"body": body}
        if position:
            data["position"] = position
        return await self.post(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/discussions",
            data=data,
        )

    async def list_merge_request_draft_notes(
        self, project_id: int | str, mr_iid: int | str
    ) -> list[dict[str, Any]]:
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/draft_notes"
        )

    async def create_merge_request_draft_note(
        self,
        project_id: int | str,
        mr_iid: int | str,
        body: str,
        position: dict[str, Any] | None = None,
        discussion_id: str | None = None,
        resolve_discussion: bool | None = None,
        commit_id: str | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"note": body}
        if position is not None:
            data["position"] = position
        if discussion_id is not None:
            data["in_reply_to_discussion_id"] = discussion_id
        if resolve_discussion is not None:
            data["resolve_discussion"] = resolve_discussion
        if commit_id is not None:
            data["commit_id"] = commit_id
        return await self.post(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/draft_notes",
            data=data,
        )

    async def publish_merge_request_draft_notes(self, project_id: int | str, mr_iid: int | str) -> Any:
        response = await self._request(
            "POST",
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/draft_notes/bulk_publish",
        )
        return response.json() if response.content else None

    async def delete_merge_request_draft_note(
        self, project_id: int | str, mr_iid: int | str, draft_note_id: int | str | str
    ) -> Any:
        response = await self._request(
            "DELETE",
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/draft_notes/{draft_note_id}",
        )
        return response.json() if response.content else None

    async def update_note(
        self, project_id: int | str, resource_type: str, resource_iid: int | str, note_id: int | str, body: str
    ) -> dict[str, Any]:
        return await self.put(
            f"/projects/{self._format_project_id(project_id)}/{resource_type}/{resource_iid}/notes/{note_id}",
            data={"body": body},
        )

    async def delete_note(
        self, project_id: int | str, resource_type: str, resource_iid: int | str, note_id: int | str
    ) -> dict[str, Any]:
        return await self.delete(
            f"/projects/{self._format_project_id(project_id)}/{resource_type}/{resource_iid}/notes/{note_id}"
        )

    async def create_merge_request(
        self, project_id: int | str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return await self.post(
            f"/projects/{self._format_project_id(project_id)}/merge_requests", data=data
        )

    async def trigger_pipeline(
        self, project_id: int | str, ref: str, variables: list[dict[str, str]] | None = None
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"ref": ref}
        if variables:
            data["variables"] = variables
        return await self.post(
            f"/projects/{self._format_project_id(project_id)}/pipeline", data=data
        )

    async def list_merge_request_pipelines(
        self, project_id: int | str, mr_iid: int | str
    ) -> list[dict[str, Any]]:
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/pipelines"
        )

    async def list_project_members(
        self, project_id: int | str, query: str | None = None
    ) -> list[dict[str, Any]]:
        params = {}
        if query:
            params["query"] = query
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/members",
            params=params,
            limit=200,
        )

    async def create_batch_commit(
        self, project_id: int | str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return await self.post(
            f"/projects/{self._format_project_id(project_id)}/repository/commits", data=data
        )

    async def get_job_artifacts_archive(self, project_id: int | str, job_id: int | str) -> bytes:
        response = await self._request(
            "GET", f"/projects/{self._format_project_id(project_id)}/jobs/{job_id}/artifacts"
        )
        return response.content

    async def get_repository_file_raw(
        self, project_id: int | str, file_path: str, ref: str | None = None
    ) -> str:
        """Fetch raw file content via the GitLab API repository/files endpoint."""
        encoded_path = urllib.parse.quote(file_path, safe="")
        response = await self._request(
            "GET",
            f"/projects/{self._format_project_id(project_id)}/repository/files/{encoded_path}/raw",
            params={"ref": ref or "HEAD"},
        )
        return response.text

    async def get_raw_file(self, raw_url: str) -> str:
        """Fetch raw file content from a GitLab /-/raw/ URL.
        Accepts full URL or a path relative to the GitLab root.
        Returns the raw text content.
        """
        absolute_url = self._build_absolute_url(raw_url)
        if not self._is_gitlab_host(absolute_url):
            raise ValueError(
                f"Raw file URL host does not match configured GitLab instance: {raw_url}"
            )
        response = await self._request("GET", absolute_url)
        return response.text

    async def upload_file(
        self, project_id: int | str, filename: str, content: bytes, content_type: str
    ) -> dict[str, Any]:
        """Upload a file to a project and return the GitLab upload metadata (url, markdown, alt)."""
        files = {"file": (filename, content, content_type)}
        response = await self._request(
            "POST",
            f"/projects/{self._format_project_id(project_id)}/uploads",
            files=files,
        )
        return response.json()

    async def fetch_upload(
        self, upload_url: str, max_size_bytes: int = 5 * 1024 * 1024
    ) -> tuple[bytes, str]:
        """Fetch a GitLab upload attachment with authentication.
        Accepts full URL or path relative to the GitLab root (e.g. /uploads/<hash>/file.png).
        Returns (content_bytes, content_type).
        Raises ValueError if the file exceeds max_size_bytes.
        """
        upload_url = self._build_absolute_url(upload_url)

        if not self._is_gitlab_host(upload_url):
            raise ValueError(
                f"Upload URL host does not match configured GitLab instance: {upload_url}"
            )
        if not self._is_secure_gitlab_url(upload_url):
            raise ValueError("Upload URL must use HTTPS except for loopback development hosts")

        async def _fetch(url: str, authenticated: bool = True) -> tuple[bytes, str]:
            current_url = url
            for _ in range(10):
                headers = {"PRIVATE-TOKEN": settings.gitlab_token} if authenticated else None
                response = await self.web_client.get(
                    current_url,
                    headers=headers,
                    follow_redirects=False,
                )
                if response.is_redirect:
                    next_request = response.next_request
                    await response.aclose()
                    if next_request is None:
                        raise ValueError("Upload redirect did not include a target URL")
                    current_url = str(next_request.url)
                    if not self._is_gitlab_host(current_url):
                        raise ValueError(
                            "Upload redirect target does not match configured GitLab instance"
                        )
                    if not self._is_secure_gitlab_url(current_url):
                        raise ValueError(
                            "Upload redirect target must use HTTPS except for loopback development hosts"
                        )
                    continue

                response.raise_for_status()
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > max_size_bytes:
                    raise ValueError(
                        f"File size {content_length} bytes exceeds max {max_size_bytes} bytes"
                    )
                content = b""
                async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                    content += chunk
                    if len(content) > max_size_bytes:
                        raise ValueError(f"File exceeds max allowed size of {max_size_bytes} bytes")
                return content, response.headers.get("content-type", "application/octet-stream")

            raise ValueError("Upload exceeded the maximum number of redirects")

        try:
            return await _fetch(upload_url)
        except httpx.HTTPStatusError as e:
            # Public/CDN-backed uploads may not accept API authentication headers.
            if e.response.status_code in (401, 403):
                logger.warning(
                    "upload_auth_failed_falling_back_to_anonymous",
                    url=self._redact_url(upload_url),
                    status_code=e.response.status_code,
                )
                return await _fetch(upload_url, authenticated=False)
            raise

    async def cancel_pipeline(self, project_id: int | str, pipeline_id: int | str) -> dict[str, Any]:
        return await self.post(
            f"/projects/{self._format_project_id(project_id)}/pipelines/{pipeline_id}/cancel"
        )

    async def cancel_job(self, project_id: int | str, job_id: int | str) -> dict[str, Any]:
        return await self.post(
            f"/projects/{self._format_project_id(project_id)}/jobs/{job_id}/cancel"
        )

    async def play_job(self, project_id: int | str, job_id: int | str) -> dict[str, Any]:
        return await self.post(
            f"/projects/{self._format_project_id(project_id)}/jobs/{job_id}/play"
        )

    async def rebase_merge_request(self, project_id: int | str, mr_iid: int | str) -> dict[str, Any]:
        return await self.put(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/rebase"
        )

    async def get_merge_request_approvals(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        return await self.get(
            f"/projects/{self._format_project_id(project_id)}/merge_requests/{mr_iid}/approvals"
        )

    async def list_project_variables(self, project_id: int | str) -> list[dict[str, Any]]:
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/variables", limit=500
        )

    async def create_project_variable(
        self, project_id: int | str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return await self.post(
            f"/projects/{self._format_project_id(project_id)}/variables", data=data
        )

    async def update_project_variable(
        self, project_id: int | str, key: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return await self.put(
            f"/projects/{self._format_project_id(project_id)}/variables/{key}", data=data
        )

    async def delete_project_variable(self, project_id: int | str, key: str) -> dict[str, Any]:
        return await self.delete(f"/projects/{self._format_project_id(project_id)}/variables/{key}")

    async def list_vulnerability_findings(
        self,
        project_id: int | str,
        severity: list[str] | None = None,
        report_type: list[str] | None = None,
        scope: str = "all",
    ) -> list[dict[str, Any]]:
        """
        List vulnerability findings for a project.
        Requires GitLab Ultimate for some features, but basic findings often available in pipelines.
        """
        params: dict[str, Any] = {"scope": scope}
        if severity:
            params["severity"] = severity
        if report_type:
            params["report_type"] = report_type
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/vulnerability_findings",
            params=params,
            limit=500,
        )

    async def get_vulnerability_details(
        self, project_id: int | str, vulnerability_id: int | str
    ) -> dict[str, Any]:
        return await self.get(
            f"/projects/{self._format_project_id(project_id)}/vulnerabilities/{vulnerability_id}"
        )

    async def list_project_dependencies(self, project_id: int | str) -> list[dict[str, Any]]:
        """
        List dependencies for a project (Dependency Scanning).
        """
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/dependencies", limit=500
        )

    async def list_audit_events(self, project_id: int | str) -> list[dict[str, Any]]:
        """
        List audit events for a project.
        """
        return await self.get_all(
            f"/projects/{self._format_project_id(project_id)}/audit_events", limit=200
        )
