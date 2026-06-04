"""Tests for GitLab Pydantic models."""

from datetime import UTC, datetime

from gitlab.models import GitLabIssue, GitLabMergeRequest, GitLabProject


class TestGitLabProject:
    def test_minimal_creation(self):
        project = GitLabProject(
            id=1,
            name="test-project",
            path_with_namespace="group/test-project",
            web_url="https://gitlab.example.com/group/test-project",
        )
        assert project.id == 1
        assert project.star_count == 0
        assert project.forks_count == 0

    def test_full_creation(self):
        now = datetime.now(UTC)
        project = GitLabProject(
            id=1,
            name="test-project",
            path_with_namespace="group/test-project",
            description="A test project",
            web_url="https://gitlab.example.com/group/test-project",
            last_activity_at=now,
            star_count=5,
            forks_count=2,
            ssh_url_to_repo="git@gitlab.example.com:group/test-project.git",
            http_url_to_repo="https://gitlab.example.com/group/test-project.git",
        )
        assert project.description == "A test project"
        assert project.last_activity_at == now
        assert project.ssh_url_to_repo is not None


class TestGitLabIssue:
    def test_creation(self):
        now = datetime.now(UTC)
        issue = GitLabIssue(
            id=100,
            iid=1,
            project_id=5,
            title="Bug report",
            description="Something is broken",
            state="opened",
            web_url="https://gitlab.example.com/group/project/-/issues/1",
            created_at=now,
            updated_at=now,
            labels=["bug", "critical"],
            author={"name": "Alice", "id": 1},
            assignee={"name": "Bob", "id": 2},
        )
        assert issue.iid == 1
        assert issue.labels == ["bug", "critical"]
        assert issue.assignee is not None
        assert issue.assignee["name"] == "Bob"

    def test_optional_fields(self):
        now = datetime.now(UTC)
        issue = GitLabIssue(
            id=101,
            iid=2,
            project_id=5,
            title="Feature request",
            state="opened",
            web_url="https://gitlab.example.com/group/project/-/issues/2",
            created_at=now,
            updated_at=now,
            author={"name": "Alice", "id": 1},
        )
        assert issue.description is None
        assert issue.assignee is None
        assert issue.labels == []


class TestGitLabMergeRequest:
    def test_creation(self):
        mr = GitLabMergeRequest(
            id=200,
            iid=10,
            project_id=5,
            title="Add feature",
            description="Implement new feature",
            state="opened",
            web_url="https://gitlab.example.com/group/project/-/merge_requests/10",
            source_branch="feature",
            target_branch="main",
            author={"name": "Alice", "id": 1},
            assignee={"name": "Bob", "id": 2},
        )
        assert mr.iid == 10
        assert mr.source_branch == "feature"
        assert mr.target_branch == "main"

    def test_optional_fields(self):
        mr = GitLabMergeRequest(
            id=201,
            iid=11,
            project_id=5,
            title="Fix bug",
            state="merged",
            web_url="https://gitlab.example.com/group/project/-/merge_requests/11",
            source_branch="fix",
            target_branch="main",
            author={"name": "Alice", "id": 1},
        )
        assert mr.description is None
        assert mr.assignee is None
