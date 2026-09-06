"""Tests for bundle tools — parallel asyncio.gather paths in GitLabService."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from gitlab.client import GitLabClient
from services.gitlab_service import GitLabService


@pytest.fixture
def mock_client() -> Any:
    client = GitLabClient()
    return client


@pytest.fixture
def service(mock_client: Any) -> GitLabService:
    return GitLabService(mock_client)


class TestBundleMergeRequestContext:
    @pytest.mark.asyncio
    async def test_returns_expected_shape(self, service: GitLabService, mock_client: Any):
        mock_client.get_merge_request = AsyncMock(
            return_value={
                "iid": 5,
                "title": "Add feature",
                "description": "A great feature",
                "state": "opened",
                "author": {"name": "Alice"},
                "labels": ["feature"],
                "source_branch": "feat/x",
                "target_branch": "main",
            }
        )
        mock_client.get_merge_request_notes = AsyncMock(
            return_value=[
                {"body": "Looks good!", "author": {"name": "Bob"}, "system": False},
                {"body": "CI passed", "author": {"name": "CI"}, "system": True},
            ]
        )
        mock_client.get_merge_request_diffs = AsyncMock(
            return_value=[
                {"new_path": "src/feature.py", "new_file": True, "diff": "@@ +1 @@"},
            ]
        )

        result = await service.bundle_merge_request_context("group/project", 5)

        assert result["summary"].startswith("Bundled context for Merge Request !5")
        assert any("1" in f and "file" in f.lower() for f in result["key_findings"])
        assert any("1" in f and "discussion" in f.lower() for f in result["key_findings"])
        details = result["details"]
        assert details["mr_details"]["iid"] == 5
        assert details["mr_details"]["title"] == "Add feature"
        assert len(details["changed_files"]) == 1
        assert len(details["recent_discussions"]) == 1  # system note excluded
        assert "next_action" in result

    @pytest.mark.asyncio
    async def test_filters_system_notes(self, service: GitLabService, mock_client: Any):
        mock_client.get_merge_request = AsyncMock(
            return_value={
                "iid": 1,
                "title": "Fix",
                "description": "",
                "state": "merged",
                "author": {"name": "Dev"},
                "labels": [],
                "source_branch": "fix",
                "target_branch": "main",
            }
        )
        mock_client.get_merge_request_notes = AsyncMock(
            return_value=[{"body": "merged", "author": {"name": "GitLab"}, "system": True}]
        )
        mock_client.get_merge_request_diffs = AsyncMock(return_value=[])

        result = await service.bundle_merge_request_context("group/project", 1)

        assert result["details"]["recent_discussions"] == []


class TestBundleProjectIntelligence:
    @pytest.mark.asyncio
    async def test_returns_dashboard_shape(self, service: GitLabService, mock_client: Any):
        mock_client.get_project = AsyncMock(
            return_value={
                "id": 10,
                "name": "MyProject",
                "path_with_namespace": "group/myproject",
                "description": "Test project",
                "visibility": "private",
                "web_url": "https://gitlab.example.com/group/myproject",
                "star_count": 3,
                "forks_count": 1,
                "last_activity_at": "2026-06-01T00:00:00Z",
            }
        )
        mock_client.list_pipelines = AsyncMock(
            return_value=[{"id": 99, "status": "success", "ref": "main", "web_url": "http://x"}]
        )
        mock_client.list_merge_requests = AsyncMock(
            return_value=[
                {"iid": 2, "title": "MR 2", "author": {"name": "Dev"}, "web_url": "http://mr2"}
            ]
        )
        mock_client.list_issues = AsyncMock(
            return_value=[
                {"iid": 3, "title": "Issue 3", "author": {"name": "QA"}, "web_url": "http://i3"}
            ]
        )

        result = await service.bundle_project_intelligence(10)

        assert "MyProject" in result["summary"]
        assert "Open Issues: 1" in result["key_findings"]
        assert "Open MRs: 1" in result["key_findings"]
        dashboard = result["details"]
        assert dashboard["project_info"]["id"] == 10
        assert len(dashboard["recent_pipelines"]) == 1
        assert dashboard["recent_pipelines"][0]["status"] == "success"
        assert len(dashboard["open_merge_requests"]) == 1
        assert len(dashboard["open_issues"]) == 1
        assert "next_action" in result

    @pytest.mark.asyncio
    async def test_empty_project_no_activity(
        self, service: GitLabService, mock_client: Any
    ):
        mock_client.get_project = AsyncMock(
            return_value={
                "id": 1,
                "name": "Empty",
                "path_with_namespace": "g/empty",
                "description": None,
                "visibility": "private",
                "web_url": "http://x",
                "star_count": 0,
                "forks_count": 0,
                "last_activity_at": "2024-01-01T00:00:00Z",
            }
        )
        mock_client.list_pipelines = AsyncMock(return_value=[])
        mock_client.list_merge_requests = AsyncMock(return_value=[])
        mock_client.list_issues = AsyncMock(return_value=[])

        result = await service.bundle_project_intelligence(1)

        assert "Open Issues: 0" in result["key_findings"]
        assert "Open MRs: 0" in result["key_findings"]
        assert "N/A" in result["key_findings"][2]  # pipeline status N/A


class TestBundlePipelineContext:
    @pytest.mark.asyncio
    async def test_returns_shape_for_passing_pipeline(
        self, service: GitLabService, mock_client: Any
    ):
        mock_client.get_pipeline = AsyncMock(
            return_value={
                "id": 50,
                "status": "success",
                "ref": "main",
                "web_url": "https://gitlab.example.com/pipelines/50",
            }
        )
        mock_client.list_pipeline_jobs = AsyncMock(
            return_value=[
                {"id": 101, "name": "test", "status": "success"},
                {"id": 102, "name": "build", "status": "success"},
            ]
        )

        result = await service.bundle_pipeline_context("group/project", 50)

        assert "50" in result["summary"]
        assert "Status: success" in result["key_findings"]
        assert "Total Jobs: 2" in result["key_findings"]
        assert "Failed Jobs: 0" in result["key_findings"]
        details = result["details"]
        assert details["pipeline_details"]["id"] == 50
        assert len(details["job_summary"]) == 2
        assert details["failed_job_analysis"] is None

    @pytest.mark.asyncio
    async def test_analyzes_first_failed_job(
        self, service: GitLabService, mock_client: Any
    ):
        mock_client.get_pipeline = AsyncMock(
            return_value={
                "id": 51,
                "status": "failed",
                "ref": "feat/x",
                "web_url": "https://gitlab.example.com/pipelines/51",
            }
        )
        mock_client.list_pipeline_jobs = AsyncMock(
            return_value=[
                {"id": 200, "name": "test", "status": "failed"},
                {"id": 201, "name": "build", "status": "success"},
            ]
        )
        mock_client.get_job_log = AsyncMock(
            return_value="Error: assertion failed on line 42\nFATAL: tests exited with code 1"
        )

        with patch.object(
            service.local_ai, "triage_job_log", new=AsyncMock(return_value="AI summary")
        ):
            result = await service.bundle_pipeline_context("group/project", 51)

        assert "Failed Jobs: 1" in result["key_findings"]
        assert result["details"]["failed_job_analysis"] is not None

    @pytest.mark.asyncio
    async def test_graceful_on_log_fetch_error(
        self, service: GitLabService, mock_client: Any
    ):
        mock_client.get_pipeline = AsyncMock(
            return_value={
                "id": 52,
                "status": "failed",
                "ref": "main",
                "web_url": "https://gitlab.example.com/pipelines/52",
            }
        )
        mock_client.list_pipeline_jobs = AsyncMock(
            return_value=[{"id": 300, "name": "deploy", "status": "failed"}]
        )
        mock_client.get_job_log = AsyncMock(side_effect=Exception("Connection timeout"))

        result = await service.bundle_pipeline_context("group/project", 52)

        # Should not raise — log fetch error is swallowed and details are None
        assert result["details"]["failed_job_analysis"] is None
        assert "next_action" in result
