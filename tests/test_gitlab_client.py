import pytest

from gitlab.client import GitLabClient


def test_format_project_id_path_encodes_slashes():
    client = GitLabClient()
    assert client._format_project_id("group/subgroup/project") == "group%2Fsubgroup%2Fproject"


def test_parse_gitlab_url_for_merge_request():
    client = GitLabClient()
    parsed = client.parse_gitlab_url("https://gitlab.example.com/group/project/-/merge_requests/42")

    assert parsed["project_path"] == "group/project"
    assert parsed["resource_type"] == "merge_requests"
    assert parsed["resource_id"] == "42"


def test_parse_gitlab_url_for_work_item():
    client = GitLabClient()
    parsed = client.parse_gitlab_url("https://gitlab.example.com/group/project/-/work_items/25")

    assert parsed["project_path"] == "group/project"
    assert parsed["resource_type"] == "work_items"
    assert parsed["resource_id"] == "25"


def test_parse_gitlab_url_for_epic():
    client = GitLabClient()
    parsed = client.parse_gitlab_url("https://gitlab.example.com/group/project/-/epics/7")

    assert parsed["project_path"] == "group/project"
    assert parsed["resource_type"] == "epics"
    assert parsed["resource_id"] == "7"


def test_parse_gitlab_url_for_snippet():
    client = GitLabClient()
    parsed = client.parse_gitlab_url("https://gitlab.example.com/group/project/-/snippets/12")

    assert parsed["project_path"] == "group/project"
    assert parsed["resource_type"] == "snippets"
    assert parsed["resource_id"] == "12"


def test_parse_gitlab_url_for_blob():
    client = GitLabClient()
    parsed = client.parse_gitlab_url(
        "https://gitlab.example.com/group/project/-/blob/main/README.md"
    )

    assert parsed["project_path"] == "group/project"
    assert parsed["resource_type"] == "blob"
    assert parsed["resource_id"] == "main/README.md"


def test_parse_gitlab_url_for_commit():
    client = GitLabClient()
    parsed = client.parse_gitlab_url("https://gitlab.example.com/group/project/-/commit/abc123")

    assert parsed["project_path"] == "group/project"
    assert parsed["resource_type"] == "commit"
    assert parsed["resource_id"] == "abc123"


def test_parse_mr_diff_url_extracts_anchor_lines():
    client = GitLabClient()
    parsed = client.parse_mr_diff_url(
        "https://gitlab.example.com/group/project/-/merge_requests/5/diffs?diff_id=77#abc123_10_14"
    )

    assert parsed["project_path"] == "group/project"
    assert parsed["mr_iid"] == 5
    assert parsed["diff_id"] == 77
    assert parsed["anchor_file_sha"] == "abc123"
    assert parsed["anchor_old_line"] == 10
    assert parsed["anchor_new_line"] == 14


def test_build_absolute_url_uses_base_for_relative_paths():
    client = GitLabClient()
    assert (
        client._build_absolute_url("/uploads/file.txt")
        == "https://gitlab.example.com/uploads/file.txt"
    )


def test_append_private_token_preserves_existing_query():
    client = GitLabClient()
    original = "https://gitlab.example.com/uploads/file.txt?foo=bar"
    tokenized = client._append_private_token(original)
    assert tokenized.startswith(original + "&private_token=")


def test_redact_url_hides_private_token_value():
    client = GitLabClient()
    redacted = client._redact_url(
        "https://gitlab.example.com/uploads/file.txt?private_token=test-token"
    )
    assert redacted.endswith("private_token=[REDACTED]")


def test_web_client_exists_without_auth_header():
    client = GitLabClient()
    assert hasattr(client, "web_client")
    assert "PRIVATE-TOKEN" not in client.web_client.headers


@pytest.mark.asyncio
async def test_aexit_calls_aclose():
    client = GitLabClient()
    # Just verify aclose cleans up both clients without error
    await client.aclose()
