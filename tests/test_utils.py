"""Tests for shared tool utilities."""

from gitlab.client import GitLabClient
from services.gitlab_service import GitLabService
from tools._utils import resolve_ids_or_fail
from tools.exceptions import GitLabApiError, GitLabToolError, MissingIdentifierError


class TestResolveIdsOrFail:
    def test_returns_ids_when_explicit(self):
        client = GitLabClient()
        service = GitLabService(client)

        result = resolve_ids_or_fail(service, None, 42, 7, "issue_iid")
        assert result == (42, 7)

    def test_returns_error_dict_when_missing(self):
        client = GitLabClient()
        service = GitLabService(client)

        result = resolve_ids_or_fail(service, None, None, None, "mr_iid")
        assert isinstance(result, dict)
        assert "summary" in result
        assert "Error" in result["summary"]
        assert "key_findings" in result
        assert "details" in result
        assert "next_action" in result

    def test_resolves_from_url(self):
        client = GitLabClient()
        service = GitLabService(client)

        url = "https://gitlab.example.com/group/project/-/issues/25"
        result = resolve_ids_or_fail(service, url, None, None, "issue_iid")
        assert result == ("group/project", 25)


class TestExceptions:
    def test_gitlab_tool_error_to_dict(self):
        err = GitLabToolError("something failed", details={"code": 500})
        d = err.to_dict()
        assert "something failed" in d["summary"]
        assert d["details"]["code"] == 500
        assert "key_findings" in d
        assert "next_action" in d

    def test_missing_identifier_error_message(self):
        err = MissingIdentifierError("issue_iid")
        assert "Missing" in err.message
        assert "issue_iid" in err.message

    def test_missing_identifier_error_to_dict(self):
        err = MissingIdentifierError("issue_iid")
        d = err.to_dict()
        assert "issue_iid" in d["summary"]
        assert "key_findings" in d
        assert "next_action" in d

    def test_gitlab_api_error_includes_status(self):
        err = GitLabApiError("not found", status_code=404)
        d = err.to_dict()
        assert d["details"]["status_code"] == 404


class TestResolveIdsOrFailNegativePaths:
    def test_returns_error_dict_when_no_url_and_no_ids(self):
        from services.gitlab_service import GitLabService
        from tools._utils import resolve_ids_or_fail

        client = GitLabClient()
        service = GitLabService(client)
        result = resolve_ids_or_fail(service, None, None, None, "issue_iid")
        assert isinstance(result, dict)
        assert "summary" in result
        assert "Error" in result["summary"]

    def test_returns_error_dict_when_url_does_not_match(self):
        from services.gitlab_service import GitLabService
        from tools._utils import resolve_ids_or_fail

        client = GitLabClient()
        service = GitLabService(client)
        result = resolve_ids_or_fail(service, "https://notgitlab.com/foo", None, None, "mr_iid")
        assert isinstance(result, dict)
        assert "Error" in result["summary"]
