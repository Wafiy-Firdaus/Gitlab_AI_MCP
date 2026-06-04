"""Tests for GitLabService business logic and response shaping."""

from unittest.mock import AsyncMock

import pytest

from gitlab.client import GitLabClient
from services.gitlab_service import (
    GitLabService,
    _extract_upload_urls,
    _is_gitlab_upload_url,
)


@pytest.fixture
def mock_client() -> GitLabClient:
    client = GitLabClient()
    client.client = AsyncMock()
    client.web_client = AsyncMock()
    return client


@pytest.fixture
def service(mock_client: GitLabClient) -> GitLabService:
    return GitLabService(mock_client)


class TestGetIssueDetails:
    @pytest.mark.asyncio
    async def test_returns_expected_shape(self, service: GitLabService, mock_client: GitLabClient):
        mock_client.get_issue = AsyncMock(
            return_value={
                "iid": 25,
                "title": "Test Issue",
                "state": "opened",
                "author": {"name": "Alice"},
                "assignees": [{"name": "Bob"}],
                "labels": ["bug", "P1"],
                "description": "Some description",
            }
        )

        result = await service.get_issue_details("group/project", 25)

        assert result["summary"] == "Details for Issue #25: Test Issue"
        assert "Status: opened" in result["key_findings"]
        assert "Author: Alice" in result["key_findings"]
        assert "Assignees: Bob" in result["key_findings"]
        assert "Labels: bug, P1" in result["key_findings"]
        assert result["details"]["iid"] == 25
        assert "next_action" in result

    @pytest.mark.asyncio
    async def test_handles_no_assignees(self, service: GitLabService, mock_client: GitLabClient):
        mock_client.get_issue = AsyncMock(
            return_value={
                "iid": 1,
                "title": "No Assignees",
                "state": "opened",
                "author": {"name": "Alice"},
                "assignees": [],
                "labels": [],
                "description": "",
            }
        )

        result = await service.get_issue_details("group/project", 1)

        assert "Assignees: None" in result["key_findings"]
        assert "Labels: None" in result["key_findings"]


class TestGetMergeRequestDetails:
    @pytest.mark.asyncio
    async def test_returns_expected_shape(self, service: GitLabService, mock_client: GitLabClient):
        mock_client.get_merge_request = AsyncMock(
            return_value={
                "iid": 42,
                "title": "Test MR",
                "state": "opened",
                "author": {"name": "Alice"},
                "source_branch": "feature",
                "target_branch": "main",
                "merge_status": "can_be_merged",
                "labels": ["enhancement"],
                "description": "MR description",
                "head_pipeline": {"id": 99, "status": "success"},
            }
        )
        mock_client.list_merge_request_pipelines = AsyncMock(return_value=[])

        result = await service.get_merge_request_details("group/project", 42)

        assert result["summary"] == "Details for Merge Request !42: Test MR"
        assert "Status: opened" in result["key_findings"]
        assert "Author: Alice" in result["key_findings"]
        assert "Source: feature -> Target: main" in result["key_findings"]
        assert result["details"]["iid"] == 42
        assert "next_action" in result

    @pytest.mark.asyncio
    async def test_includes_jobs_when_requested(
        self, service: GitLabService, mock_client: GitLabClient
    ):
        mock_client.get_merge_request = AsyncMock(
            return_value={
                "iid": 42,
                "title": "Test MR",
                "state": "opened",
                "author": {"name": "Alice"},
                "source_branch": "feature",
                "target_branch": "main",
                "merge_status": "can_be_merged",
                "labels": [],
                "description": "",
                "head_pipeline": {"id": 99, "status": "running"},
            }
        )
        mock_client.list_merge_request_pipelines = AsyncMock(
            return_value=[{"id": 99, "status": "running"}]
        )
        mock_client.list_pipeline_jobs = AsyncMock(
            return_value=[{"id": 1, "name": "test", "status": "running"}]
        )

        result = await service.get_merge_request_details("group/project", 42, include_jobs=True)

        assert "Jobs: 1 jobs retrieved for head pipeline" in result["key_findings"]
        assert "head_pipeline_jobs" in result["details"]


class TestBundleIssueContext:
    @pytest.mark.asyncio
    async def test_bundles_issue_notes_and_related_mrs(
        self, service: GitLabService, mock_client: GitLabClient
    ):
        mock_client.get_issue = AsyncMock(
            return_value={
                "iid": 25,
                "title": "Bundled Issue",
                "state": "opened",
                "author": {"name": "Alice"},
                "labels": ["bug"],
                "description": "Description here",
                "assignees": [],
            }
        )
        mock_client.get_issue_notes = AsyncMock(
            return_value=[
                {"author": {"name": "Bob"}, "body": "First comment"},
                {"author": {"name": "Charlie"}, "body": "Second comment"},
            ]
        )
        mock_client.get_issue_related_mrs = AsyncMock(
            return_value=[
                {
                    "iid": 10,
                    "title": "Related MR",
                    "state": "merged",
                    "web_url": "http://example.com",
                }
            ]
        )

        result = await service.bundle_issue_context("group/project", 25)

        assert result["summary"] == "Bundled context for Issue #25: Bundled Issue"
        assert "Comments: 2 user discussions" in result["key_findings"]
        assert "Linked MRs: 1 relevant merge requests" in result["key_findings"]
        assert result["details"]["issue_details"]["title"] == "Bundled Issue"
        assert len(result["details"]["recent_discussions"]) == 2
        assert len(result["details"]["linked_merge_requests"]) == 1
        assert "next_action" in result


class TestBundleMergeRequestContext:
    @pytest.mark.asyncio
    async def test_bundles_mr_notes_and_diffs(
        self, service: GitLabService, mock_client: GitLabClient
    ):
        mock_client.get_merge_request = AsyncMock(
            return_value={
                "iid": 42,
                "title": "Bundled MR",
                "state": "opened",
                "author": {"name": "Alice"},
                "labels": [],
                "description": "MR description",
                "source_branch": "feature",
                "target_branch": "main",
            }
        )
        mock_client.get_merge_request_notes = AsyncMock(
            return_value=[{"author": {"name": "Bob"}, "body": "LGTM"}]
        )
        mock_client.get_merge_request_diffs = AsyncMock(
            return_value=[
                {"new_path": "README.md", "new_file": True},
                {"new_path": "app.py", "new_file": False},
            ]
        )

        result = await service.bundle_merge_request_context("group/project", 42)

        assert result["summary"] == "Bundled context for Merge Request !42: Bundled MR"
        assert "Comments: 1 user discussions" in result["key_findings"]
        assert "Changes: 2 files modified" in result["key_findings"]
        assert result["details"]["mr_details"]["title"] == "Bundled MR"
        assert len(result["details"]["recent_discussions"]) == 1
        assert len(result["details"]["changed_files"]) == 2
        assert "next_action" in result


class TestResolveUrlOrIds:
    def test_resolves_explicit_ids(self, service: GitLabService):
        p_id, res_id = service.resolve_url_or_ids(None, 123, 45)
        assert p_id == 123
        assert res_id == 45

    def test_resolves_from_url(self, service: GitLabService):
        url = "https://gitlab.example.com/group/project/-/merge_requests/42"
        p_id, res_id = service.resolve_url_or_ids(url, None, None)
        assert p_id == "group/project"
        assert res_id == 42

    def test_prefers_url_over_explicit_ids(self, service: GitLabService):
        url = "https://gitlab.example.com/group/project/-/issues/99"
        p_id, res_id = service.resolve_url_or_ids(url, 1, 2)
        assert p_id == "group/project"
        assert res_id == 99

    def test_handles_non_numeric_resource_id_in_url(self, service: GitLabService):
        url = "https://gitlab.example.com/group/project/-/blob/main/README.md"
        p_id, res_id = service.resolve_url_or_ids(url, None, None)
        assert p_id == "group/project"
        assert res_id == "main/README.md"


class TestExtractUploadUrls:
    def test_extracts_markdown_image(self):
        text = "See ![screenshot](/uploads/abc123/image.png) here"
        assert _extract_upload_urls(text) == ["/uploads/abc123/image.png"]

    def test_extracts_markdown_link(self):
        text = "Download [file](/uploads/abc123/report.pdf)"
        assert _extract_upload_urls(text) == ["/uploads/abc123/report.pdf"]

    def test_extracts_html_img(self):
        text = '<img src="/uploads/abc123/image.png" alt="test">'
        assert _extract_upload_urls(text) == ["/uploads/abc123/image.png"]

    def test_extracts_full_url(self):
        text = "See ![img](https://gitlab.example.com/uploads/abc123/image.png)"
        assert _extract_upload_urls(text) == ["https://gitlab.example.com/uploads/abc123/image.png"]

    def test_ignores_external_domain(self):
        text = "See ![img](https://attacker.com/uploads/abc123/image.png)"
        assert _extract_upload_urls(text) == []

    def test_returns_empty_for_none(self):
        assert _extract_upload_urls(None) == []

    def test_deduplicates_urls(self):
        text = "![a](/uploads/abc123/img.png) and [b](/uploads/abc123/img.png)"
        assert _extract_upload_urls(text) == ["/uploads/abc123/img.png"]


class TestIsGitlabUploadUrl:
    def test_relative_url_is_valid(self):
        assert _is_gitlab_upload_url("/uploads/abc123/file.png") is True

    def test_matching_host_is_valid(self):
        assert _is_gitlab_upload_url("https://gitlab.example.com/uploads/abc123/file.png") is True

    def test_external_host_is_invalid(self):
        assert _is_gitlab_upload_url("https://attacker.com/uploads/abc123/file.png") is False

    def test_non_upload_path_is_invalid(self):
        assert _is_gitlab_upload_url("https://example.com/other/path.png") is False


class TestUploadFileToProject:
    @pytest.mark.asyncio
    async def test_returns_expected_shape(self, service: GitLabService, mock_client: GitLabClient):
        mock_client.upload_file = AsyncMock(
            return_value={
                "url": "/uploads/abc123/screenshot.png",
                "markdown": "![screenshot](/uploads/abc123/screenshot.png)",
                "alt": "screenshot",
            }
        )

        result = await service.upload_file_to_project(
            "group/project", "screenshot.png", b"fake-image-data", "image/png"
        )

        assert result["summary"] == "Uploaded 'screenshot.png' to project group/project"
        assert (
            "Embed in comments with: ![screenshot](/uploads/abc123/screenshot.png)"
            in result["key_findings"]
        )
        assert result["details"]["url"] == "/uploads/abc123/screenshot.png"
        assert "next_action" in result

    @pytest.mark.asyncio
    async def test_fallback_markdown_when_missing(
        self, service: GitLabService, mock_client: GitLabClient
    ):
        mock_client.upload_file = AsyncMock(return_value={"url": "/uploads/abc123/file.txt"})

        result = await service.upload_file_to_project(
            "group/project", "file.txt", b"data", "text/plain"
        )

        assert "![](/uploads/abc123/file.txt)" in result["key_findings"][0]


class TestGetIssueAttachments:
    @pytest.mark.asyncio
    async def test_fetches_attachments_from_description_and_notes(
        self, service: GitLabService, mock_client: GitLabClient
    ):
        mock_client.get_issue = AsyncMock(
            return_value={
                "iid": 1,
                "title": "Bug",
                "description": "See ![img](/uploads/abc123/bug.png)",
            }
        )
        mock_client.get_issue_notes = AsyncMock(
            return_value=[{"body": "Also ![img2](/uploads/def456/note.png)"}]
        )
        mock_client.get_issue_discussions = AsyncMock(return_value=[])
        mock_client.fetch_upload = AsyncMock(
            side_effect=[
                (b"fake-image-1", "image/png"),
                (b"fake-image-2", "image/png"),
            ]
        )

        result = await service.get_issue_attachments("group/project", 1)

        assert result["summary"] == "Found 2 attachment(s) in Issue #1"
        assert len(result["details"]["uploads"]) == 2
        assert result["details"]["uploads"][0]["content_base64"] is not None
        assert result["details"]["uploads"][0]["content_type"] == "image/png"

    @pytest.mark.asyncio
    async def test_handles_fetch_errors_gracefully(
        self, service: GitLabService, mock_client: GitLabClient
    ):
        mock_client.get_issue = AsyncMock(
            return_value={
                "iid": 1,
                "title": "Bug",
                "description": "![img](/uploads/abc123/bug.png)",
            }
        )
        mock_client.get_issue_notes = AsyncMock(return_value=[])
        mock_client.get_issue_discussions = AsyncMock(return_value=[])
        mock_client.fetch_upload = AsyncMock(side_effect=Exception("Network error"))

        result = await service.get_issue_attachments("group/project", 1)

        assert len(result["details"]["uploads"]) == 1
        assert result["details"]["uploads"][0]["error"] is not None
        assert result["details"]["uploads"][0]["content_base64"] is None

    @pytest.mark.asyncio
    async def test_respects_max_attachment_limit(
        self, service: GitLabService, mock_client: GitLabClient
    ):
        # Create 25 unique upload URLs in description
        urls = " ".join([f"![img](/uploads/abc{i:03d}/img.png)" for i in range(25)])
        mock_client.get_issue = AsyncMock(
            return_value={"iid": 1, "title": "Bug", "description": urls}
        )
        mock_client.get_issue_notes = AsyncMock(return_value=[])
        mock_client.get_issue_discussions = AsyncMock(return_value=[])
        mock_client.fetch_upload = AsyncMock(return_value=(b"x", "image/png"))

        result = await service.get_issue_attachments("group/project", 1)

        uploads = result["details"]["uploads"]
        # 20 fetched + 1 skipped entry
        assert len(uploads) == 21
        assert any("Skipped 5" in str(u.get("error", "")) for u in uploads)


class TestGetMergeRequestAttachments:
    @pytest.mark.asyncio
    async def test_fetches_attachments_from_description_and_discussions(
        self, service: GitLabService, mock_client: GitLabClient
    ):
        mock_client.get_merge_request = AsyncMock(
            return_value={
                "iid": 1,
                "title": "Feature",
                "description": "See ![img](/uploads/abc123/feature.png)",
            }
        )
        mock_client.get_merge_request_notes = AsyncMock(return_value=[])
        mock_client.get_merge_request_discussions = AsyncMock(
            return_value=[{"notes": [{"body": "Review ![img](/uploads/def456/review.png)"}]}]
        )
        mock_client.fetch_upload = AsyncMock(
            side_effect=[
                (b"fake-image-1", "image/png"),
                (b"fake-image-2", "image/png"),
            ]
        )

        result = await service.get_merge_request_attachments("group/project", 1)

        assert result["summary"] == "Found 2 attachment(s) in Merge Request !1"
        assert len(result["details"]["uploads"]) == 2


class TestErrorContractCompliance:
    @pytest.mark.asyncio
    async def test_get_raw_file_content_returns_contract_on_missing_params(
        self, service: GitLabService, mock_client: GitLabClient
    ):
        result = await service.get_raw_file_content(raw_url=None, project_id=None, file_path=None)

        assert "summary" in result
        assert "key_findings" in result
        assert "details" in result
        assert "next_action" in result
        assert "Error" in result["summary"]
