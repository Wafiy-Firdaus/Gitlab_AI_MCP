import pytest

from gitlab.client import GitLabClient


@pytest.fixture
def client():
    return GitLabClient()


@pytest.mark.asyncio
async def test_build_text_diff_position_success(client, monkeypatch):
    async def mock_version(self, project_id, mr_iid):
        return {
            "base_sha": "base123",
            "start_sha": "start123",
            "head_sha": "head123",
        }

    monkeypatch.setattr(GitLabClient, "get_latest_merge_request_version", mock_version)

    position = await client.build_text_diff_position("group/project", 1, "src/main.py", new_line=10)
    assert position["position_type"] == "text"
    assert position["base_sha"] == "base123"
    assert position["start_sha"] == "start123"
    assert position["head_sha"] == "head123"
    assert position["new_path"] == "src/main.py"
    assert position["old_path"] == "src/main.py"
    assert position["new_line"] == 10
    assert "old_line" not in position


@pytest.mark.asyncio
async def test_build_text_diff_position_with_old_path_and_lines(client, monkeypatch):
    async def mock_version(self, project_id, mr_iid):
        return {
            "base_sha": "base123",
            "start_sha": "start123",
            "head_sha": "head123",
        }

    monkeypatch.setattr(GitLabClient, "get_latest_merge_request_version", mock_version)

    position = await client.build_text_diff_position(
        "group/project", 1, "src/main.py", old_path="src/old.py", old_line=5, new_line=15
    )
    assert position["old_path"] == "src/old.py"
    assert position["new_path"] == "src/main.py"
    assert position["old_line"] == 5
    assert position["new_line"] == 15


@pytest.mark.asyncio
async def test_build_text_diff_position_missing_new_path(client):
    with pytest.raises(ValueError, match="non-empty new_path"):
        await client.build_text_diff_position("group/project", 1, "")


@pytest.mark.asyncio
async def test_build_text_diff_position_missing_lines(client):
    with pytest.raises(ValueError, match="at least one of old_line or new_line"):
        await client.build_text_diff_position("group/project", 1, "src/main.py")
