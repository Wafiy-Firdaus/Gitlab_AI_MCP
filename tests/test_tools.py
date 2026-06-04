"""Integration tests for all MCP tool handlers.

Verifies that every tool:
1. Delegates to the service/client layer correctly
2. Returns a response contract-compliant dict (summary, key_findings, details, next_action)
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from tools.ci_cd import register_ci_cd_tools
from tools.issues import register_issue_tools
from tools.merge_requests import register_merge_request_tools
from tools.projects import register_project_tools
from tools.repository import register_repository_tools
from tools.search import register_search_tools
from tools.security import register_security_tools


def _make_mock_client():
    """Factory for a fully-mocked GitLabClient."""
    client = AsyncMock()
    client.client = AsyncMock()
    client.web_client = AsyncMock()
    client.base_url = "https://gitlab.example.com/api/v4"

    # Common return values
    client.get_current_user = AsyncMock(
        return_value={"username": "test", "name": "Test User", "id": 1}
    )
    from unittest.mock import Mock

    version_mock = AsyncMock()
    version_mock.json = Mock(return_value={"version": "16.0", "revision": "abc123"})
    client.get_version = AsyncMock(return_value=version_mock)
    client.get_issue = AsyncMock(
        return_value={
            "iid": 1,
            "title": "Test Issue",
            "state": "opened",
            "author": {"name": "Alice"},
            "assignees": [],
            "labels": [],
            "description": "Desc",
        }
    )
    client.get_issue_notes = AsyncMock(return_value=[])
    client.get_issue_discussions = AsyncMock(return_value=[])
    client.get_issue_related_mrs = AsyncMock(return_value=[])
    client.create_issue = AsyncMock(return_value={"iid": 99, "title": "New Issue", "labels": []})
    client.update_issue = AsyncMock(return_value={"iid": 1, "title": "Updated"})
    client.create_issue_note = AsyncMock(
        return_value={"id": 1, "body": "note", "author": {"name": "Alice"}}
    )
    client.reply_to_issue_discussion = AsyncMock(
        return_value={"id": 1, "author": {"name": "Alice"}}
    )
    client.update_note = AsyncMock(return_value={"id": 1})
    client.delete_note = AsyncMock(return_value=True)

    client.get_merge_request = AsyncMock(
        return_value={
            "iid": 1,
            "title": "Test MR",
            "state": "opened",
            "author": {"name": "Alice"},
            "source_branch": "feature",
            "target_branch": "main",
            "labels": [],
            "description": "Desc",
            "merge_status": "can_be_merged",
            "head_pipeline": None,
        }
    )
    client.get_merge_request_notes = AsyncMock(return_value=[])
    client.get_merge_request_discussions = AsyncMock(return_value=[])
    client.get_merge_request_diffs = AsyncMock(return_value=[])
    client.create_merge_request = AsyncMock(
        return_value={
            "iid": 2,
            "title": "New MR",
            "source_branch": "feat",
            "target_branch": "main",
            "author": {"name": "Alice"},
        }
    )
    client.update_merge_request = AsyncMock(return_value={"iid": 1})
    client.approve_merge_request = AsyncMock(return_value={"approved": True})
    client.create_merge_request_note = AsyncMock(
        return_value={"id": 1, "author": {"name": "Alice"}}
    )
    client.create_merge_request_discussion = AsyncMock(return_value={"id": 1, "notes": [{"id": 1}]})
    client.add_merge_request_discussion_note = AsyncMock(
        return_value={"id": 1, "author": {"name": "Alice"}}
    )
    client.resolve_merge_request_discussion = AsyncMock(return_value={"id": 1})
    client.get_merge_request_approvals = AsyncMock(return_value={"approved_by": []})
    client.rebase_merge_request = AsyncMock(return_value={"rebase_in_progress": False})
    client.merge_merge_request = AsyncMock(return_value={"title": "Merged"})
    client.get_latest_merge_request_version = AsyncMock(
        return_value={"base_sha": "abc", "start_sha": "def", "head_sha": "ghi"}
    )
    client.build_text_diff_position = AsyncMock(
        return_value={"base_sha": "abc", "start_sha": "def", "head_sha": "ghi"}
    )
    client.list_merge_request_pipelines = AsyncMock(return_value=[])

    client.get_project = AsyncMock(
        return_value={
            "id": 1,
            "name": "Test",
            "path_with_namespace": "group/project",
            "description": "A project",
            "web_url": "https://gitlab.example.com/group/project",
            "star_count": 0,
            "forks_count": 0,
            "last_activity_at": None,
            "visibility": "private",
        }
    )
    client.list_projects = AsyncMock(return_value=[{"id": 1, "name": "Test"}])
    client.list_group_projects = AsyncMock(return_value=[{"id": 1, "name": "Test"}])
    client.list_project_members = AsyncMock(return_value=[])
    client.list_project_environments = AsyncMock(return_value=[])
    client.list_project_labels = AsyncMock(return_value=[])
    client.create_project_label = AsyncMock(return_value={"name": "bug", "color": "#ff0000"})

    client.get_pipeline = AsyncMock(
        return_value={
            "id": 1,
            "status": "success",
            "ref": "main",
            "source": "push",
            "duration": 120,
        }
    )
    client.list_pipelines = AsyncMock(
        return_value=[
            {
                "id": 1,
                "status": "success",
                "ref": "main",
                "web_url": "https://gitlab.example.com/pipelines/1",
            }
        ]
    )
    client.list_pipeline_jobs = AsyncMock(return_value=[])
    client.get_job_log = AsyncMock(return_value="log content")
    client.analyze_failed_job = AsyncMock(return_value={"analysis": "done"})
    client.get_pipeline_bridges = AsyncMock(return_value=[])
    client.cancel_pipeline = AsyncMock(return_value={"status": "canceled"})
    client.cancel_job = AsyncMock(return_value={"status": "canceled"})
    client.play_job = AsyncMock(return_value={"status": "running"})
    client.retry_job = AsyncMock(return_value={"id": 1, "status": "running"})
    client.retry_pipeline = AsyncMock(return_value={"id": 1, "status": "running", "ref": "main"})
    client.trigger_pipeline = AsyncMock(
        return_value={
            "id": 2,
            "status": "running",
            "web_url": "https://gitlab.example.com/pipelines/2",
        }
    )
    client.list_project_variables = AsyncMock(return_value=[])
    client.create_project_variable = AsyncMock(
        return_value={"key": "VAR", "value": "1", "variable_type": "env_var"}
    )
    client.update_project_variable = AsyncMock(return_value={"key": "VAR", "value": "2"})
    client.delete_project_variable = AsyncMock(return_value=True)

    client.get_file_content = AsyncMock(
        return_value={
            "content": "aGVsbG8=",
            "file_name": "test.txt",
            "size": 5,
            "encoding": "base64",
        }
    )
    client.get_raw_file = AsyncMock(return_value="hello")
    client.get_repository_file_raw = AsyncMock(return_value="hello")
    client.list_repository_files = AsyncMock(return_value=[])
    client.create_repository_file = AsyncMock(
        return_value={"file_path": "test.txt", "branch": "main"}
    )
    client.update_repository_file = AsyncMock(
        return_value={"file_path": "test.txt", "branch": "main"}
    )
    client.create_batch_commit = AsyncMock(return_value={"id": "abc123"})
    client.list_repository_commits = AsyncMock(return_value=[])
    client.get_commit_details = AsyncMock(
        return_value={
            "id": "abc123",
            "title": "init",
            "message": "init",
            "author_name": "Alice",
            "author_email": "alice@example.com",
            "created_at": "2024-01-01T00:00:00Z",
            "stats": {"additions": 10, "deletions": 2},
        }
    )
    client.get_branch = AsyncMock(
        return_value={
            "name": "main",
            "commit": {"id": "abc123def"},
            "merged": False,
            "protected": True,
        }
    )
    client.get_branches = AsyncMock(return_value={"main": {"name": "main"}})
    client.create_branch = AsyncMock(return_value={"name": "feature", "commit": {"id": "abc123"}})
    client.list_repository_tags = AsyncMock(return_value=[])
    client.get_file_blame = AsyncMock(return_value=[])
    client.get_job_artifact_file = AsyncMock(return_value=b"artifact")
    client.get_job_artifacts_archive = AsyncMock(return_value=b"zip")
    client.fetch_upload = AsyncMock(return_value=(b"image", "image/png"))
    client.upload_file = AsyncMock(
        return_value={"url": "/uploads/abc/img.png", "markdown": "![img](/uploads/abc/img.png)"}
    )

    client.list_vulnerability_findings = AsyncMock(return_value=[])
    client.get_vulnerability_details = AsyncMock(return_value={"id": 1})
    client.list_project_dependencies = AsyncMock(return_value=[])
    client.list_audit_events = AsyncMock(return_value=[])

    client.search_code = AsyncMock(return_value=[])
    client.global_search = AsyncMock(return_value=[])
    client.search_users = AsyncMock(return_value=[])

    return client


def _assert_contract(result):
    """Parse tool result and assert response contract compliance."""
    assert isinstance(result, tuple)
    contents, raw = result
    assert isinstance(contents, list)
    assert len(contents) >= 1
    # Parse the JSON text content
    data = json.loads(contents[0].text)
    assert "summary" in data, f"Missing 'summary' in response: {data.keys()}"
    assert "key_findings" in data
    assert "details" in data
    assert "next_action" in data


@pytest.fixture
def mock_client_fixture(monkeypatch):
    mock_client = _make_mock_client()
    monkeypatch.setattr(
        "gitlab.client.GitLabClient.get_instance", AsyncMock(return_value=mock_client)
    )
    return mock_client


class TestIssueTools:
    @pytest.fixture
    def mcp(self):
        m = FastMCP("test-issues")
        register_issue_tools(m)
        return m

    @pytest.mark.asyncio
    async def test_list_all_issues(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("list_all_issues", {})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_get_issue_details(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("get_issue_details", {"project_id": 1, "issue_iid": 1})
        _assert_contract(result)
        data = json.loads(result[0][0].text)
        assert "Test Issue" in data["summary"]

    @pytest.mark.asyncio
    async def test_create_issue(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "create_issue", {"project_id": 1, "title": "New bug", "description": "Details"}
        )
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_update_issue(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "update_issue", {"project_id": 1, "issue_iid": 1, "title": "Updated"}
        )
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_get_issue_notes(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("get_issue_notes", {"project_id": 1, "issue_iid": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_create_issue_note(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "create_issue_note", {"project_id": 1, "issue_iid": 1, "body": "LGTM"}
        )
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_reply_to_issue_discussion(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "reply_to_issue_discussion",
            {"project_id": 1, "issue_iid": 1, "discussion_id": "abc", "body": "Reply"},
        )
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_update_issue_note(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "update_issue_note", {"project_id": 1, "issue_iid": 1, "note_id": 1, "body": "Edit"}
        )
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_delete_issue_note(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "delete_issue_note", {"project_id": 1, "issue_iid": 1, "note_id": 1}
        )
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_bundle_issue_context(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("bundle_issue_context", {"project_id": 1, "issue_iid": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_get_issue_attachments(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("get_issue_attachments", {"project_id": 1, "issue_iid": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_triage_issue_locally(self, mcp, mock_client_fixture):
        # Mock LocalAIService to avoid Ollama dependency
        with patch(
            "services.gitlab_service.LocalAIService.generate_summary",
            AsyncMock(return_value="Triage result"),
        ):
            result = await mcp.call_tool("triage_issue_locally", {"project_id": 1, "issue_iid": 1})
            _assert_contract(result)


class TestMergeRequestTools:
    @pytest.fixture
    def mcp(self):
        m = FastMCP("test-mrs")
        register_merge_request_tools(m)
        return m

    @pytest.mark.asyncio
    async def test_get_merge_request_details(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("get_merge_request_details", {"project_id": 1, "mr_iid": 1})
        _assert_contract(result)
        data = json.loads(result[0][0].text)
        assert "Test MR" in data["summary"]

    @pytest.mark.asyncio
    async def test_create_merge_request(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "create_merge_request",
            {
                "project_id": 1,
                "source_branch": "feat",
                "target_branch": "main",
                "title": "Add feature",
            },
        )
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_update_merge_request(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "update_merge_request", {"project_id": 1, "mr_iid": 1, "title": "Updated"}
        )
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_approve_merge_request(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("approve_merge_request", {"project_id": 1, "mr_iid": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_get_merge_request_notes(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("get_merge_request_notes", {"project_id": 1, "mr_iid": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_create_merge_request_note(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "create_merge_request_note", {"project_id": 1, "mr_iid": 1, "body": "LGTM"}
        )
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_get_merge_request_diffs(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("get_merge_request_diffs", {"project_id": 1, "mr_iid": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_get_merge_request_discussions(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "get_merge_request_discussions", {"project_id": 1, "mr_iid": 1}
        )
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_reply_to_discussion(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "reply_to_discussion",
            {"project_id": 1, "mr_iid": 1, "discussion_id": "abc", "body": "Reply"},
        )
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_create_merge_request_discussion(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "create_merge_request_discussion",
            {"project_id": 1, "mr_iid": 1, "body": "Comment"},
        )
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_merge_merge_request(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("merge_merge_request", {"project_id": 1, "mr_iid": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_rebase_merge_request(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("rebase_merge_request", {"project_id": 1, "mr_iid": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_upload_file_to_project(self, mcp, mock_client_fixture):
        import base64

        content = base64.b64encode(b"fake-image").decode()
        result = await mcp.call_tool(
            "upload_file_to_project",
            {"project_id": 1, "filename": "img.png", "file_content_base64": content},
        )
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_upload_file_rejects_oversized(self, mcp, mock_client_fixture):
        import base64

        content = base64.b64encode(b"x" * (11 * 1024 * 1024)).decode()
        result = await mcp.call_tool(
            "upload_file_to_project",
            {"project_id": 1, "filename": "big.bin", "file_content_base64": content},
        )
        _assert_contract(result)
        data = json.loads(result[0][0].text)
        assert "Error" in data["summary"]

    @pytest.mark.asyncio
    async def test_upload_file_rejects_invalid_base64(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "upload_file_to_project",
            {"project_id": 1, "filename": "bad.bin", "file_content_base64": "!!!"},
        )
        _assert_contract(result)
        data = json.loads(result[0][0].text)
        assert "Invalid base64" in data["summary"]

    @pytest.mark.asyncio
    async def test_get_merge_request_attachments(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "get_merge_request_attachments", {"project_id": 1, "mr_iid": 1}
        )
        _assert_contract(result)


class TestProjectTools:
    @pytest.fixture
    def mcp(self):
        m = FastMCP("test-projects")
        register_project_tools(m)
        return m

    @pytest.mark.asyncio
    async def test_ping_gitlab(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("ping_gitlab", {})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_list_projects(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("list_projects", {})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_get_project_details(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("get_project_details", {"project_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_list_project_members(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("list_project_members", {"project_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_bundle_project_intelligence(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("bundle_project_intelligence", {"project_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_list_project_labels(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("list_project_labels", {"project_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_create_project_label(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "create_project_label", {"project_id": 1, "name": "bug", "color": "#ff0000"}
        )
        _assert_contract(result)


class TestCiCdTools:
    @pytest.fixture
    def mcp(self):
        m = FastMCP("test-cicd")
        register_ci_cd_tools(m)
        return m

    @pytest.mark.asyncio
    async def test_list_project_pipelines(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("list_project_pipelines", {"project_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_get_pipeline_details(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("get_pipeline_details", {"project_id": 1, "pipeline_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_list_pipeline_jobs(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("list_pipeline_jobs", {"project_id": 1, "pipeline_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_get_job_log(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("get_job_log", {"project_id": 1, "job_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_analyze_failed_job(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("analyze_failed_job", {"project_id": 1, "job_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_analyze_failed_job_error_contract_on_missing_ids(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("analyze_failed_job", {})
        _assert_contract(result)
        data = json.loads(result[0][0].text)
        assert "Error" in data["summary"]

    @pytest.mark.asyncio
    async def test_cancel_pipeline(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("cancel_pipeline", {"project_id": 1, "pipeline_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_cancel_job(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("cancel_job", {"project_id": 1, "job_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_play_job(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("play_job", {"project_id": 1, "job_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_retry_job(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("retry_job", {"project_id": 1, "job_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_retry_pipeline(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("retry_pipeline", {"project_id": 1, "pipeline_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_trigger_pipeline(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("trigger_pipeline", {"project_id": 1, "ref": "main"})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_list_project_variables(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("list_project_variables", {"project_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_create_project_variable(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "create_project_variable", {"project_id": 1, "key": "FOO", "value": "bar"}
        )
        _assert_contract(result)


class TestRepositoryTools:
    @pytest.fixture
    def mcp(self):
        m = FastMCP("test-repo")
        register_repository_tools(m)
        return m

    @pytest.mark.asyncio
    async def test_get_file_content(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "get_file_content", {"project_id": 1, "file_path": "README.md"}
        )
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_get_raw_file_content(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "get_raw_file_content", {"raw_url": "https://gitlab.example.com/-/raw/main/README.md"}
        )
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_list_repository_files(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("list_repository_files", {"project_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_create_repository_file(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "create_repository_file",
            {
                "project_id": 1,
                "file_path": "test.txt",
                "branch": "main",
                "content": "hello",
                "commit_message": "add",
            },
        )
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_list_repository_commits(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("list_repository_commits", {"project_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_get_commit_details(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("get_commit_details", {"project_id": 1, "sha": "abc123"})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_get_branch(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("get_branch", {"project_id": 1, "branch": "main"})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_create_branch(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "create_branch", {"project_id": 1, "branch": "feature", "ref": "main"}
        )
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_list_repository_tags(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("list_repository_tags", {"project_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_fetch_gitlab_upload(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "fetch_gitlab_upload", {"upload_url": "/uploads/abc123/img.png"}
        )
        _assert_contract(result)


class TestSearchTools:
    @pytest.fixture
    def mcp(self):
        m = FastMCP("test-search")
        register_search_tools(m)
        return m

    @pytest.mark.asyncio
    async def test_search_code(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("search_code", {"project_id": 1, "search": "foo"})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_global_search(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("global_search", {"scope": "projects", "search": "foo"})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_search_users(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("search_users", {"search": "alice"})
        _assert_contract(result)


class TestSecurityTools:
    @pytest.fixture
    def mcp(self):
        m = FastMCP("test-security")
        register_security_tools(m)
        return m

    @pytest.mark.asyncio
    async def test_list_vulnerability_findings(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("list_vulnerability_findings", {"project_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_get_vulnerability_details(self, mcp, mock_client_fixture):
        result = await mcp.call_tool(
            "get_vulnerability_details", {"project_id": 1, "vulnerability_id": 1}
        )
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_list_project_dependencies(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("list_project_dependencies", {"project_id": 1})
        _assert_contract(result)

    @pytest.mark.asyncio
    async def test_list_audit_events(self, mcp, mock_client_fixture):
        result = await mcp.call_tool("list_audit_events", {"project_id": 1})
        _assert_contract(result)
