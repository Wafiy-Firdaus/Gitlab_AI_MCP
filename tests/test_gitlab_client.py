import pytest

from gitlab.client import GitLabClient


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset GitLabClient singleton between tests to prevent state leakage."""
    GitLabClient._instance = None
    yield
    GitLabClient._instance = None


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


class TestHostValidation:
    def test_is_gitlab_host_accepts_matching_host(self):
        client = GitLabClient()
        assert client._is_gitlab_host("https://gitlab.example.com/uploads/file.png") is True

    def test_is_gitlab_host_rejects_different_host(self):
        client = GitLabClient()
        assert client._is_gitlab_host("https://attacker.com/uploads/file.png") is False

    def test_is_gitlab_host_rejects_subdomain(self):
        client = GitLabClient()
        assert client._is_gitlab_host("https://evil.gitlab.example.com/uploads/file.png") is False


@pytest.mark.asyncio
async def test_fetch_upload_rejects_external_url():
    client = GitLabClient()
    with pytest.raises(ValueError, match="does not match configured GitLab instance"):
        await client.fetch_upload("https://attacker.com/exfil.png")


@pytest.mark.asyncio
async def test_fetch_upload_rejects_http_url():
    client = GitLabClient()
    with pytest.raises(ValueError, match="must use HTTPS"):
        await client.fetch_upload("http://gitlab.example.com/uploads/file.png")


@pytest.mark.asyncio
async def test_fetch_upload_uses_auth_header_not_query_token(monkeypatch):
    import httpx

    client = GitLabClient()
    request = httpx.Request("GET", "https://gitlab.example.com/uploads/file.png")
    response = httpx.Response(
        200,
        content=b"image",
        headers={"content-type": "image/png"},
        request=request,
    )
    calls = []

    async def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return response

    monkeypatch.setattr(client.web_client, "get", fake_get)

    content, content_type = await client.fetch_upload("/uploads/file.png")

    assert content == b"image"
    assert content_type == "image/png"
    assert calls[0][0] == "https://gitlab.example.com/uploads/file.png"
    assert calls[0][1]["headers"] == {"PRIVATE-TOKEN": "test-token"}


@pytest.mark.asyncio
async def test_get_raw_file_rejects_external_url():
    client = GitLabClient()
    with pytest.raises(ValueError, match="does not match configured GitLab instance"):
        await client.get_raw_file("https://attacker.com/raw/file.txt")


@pytest.mark.asyncio
async def test_aexit_calls_aclose():
    client = GitLabClient()
    # Just verify aclose cleans up both clients without error
    await client.aclose()


class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_request_retries_on_429(self, monkeypatch):
        import httpx

        client = GitLabClient()
        call_count = 0

        async def fake_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                response = httpx.Response(429, request=httpx.Request("GET", "https://example.com"))
                raise httpx.HTTPStatusError(
                    "Rate limited", request=response.request, response=response
                )
            return httpx.Response(
                200, json={"ok": True}, request=httpx.Request("GET", "https://example.com")
            )

        monkeypatch.setattr(client.client, "request", fake_request)

        # Patch sleep to avoid delays
        async def _noop_sleep(x):
            pass

        monkeypatch.setattr("asyncio.sleep", _noop_sleep)

        result = await client._request("GET", "/test")
        assert result.status_code == 200
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_request_retries_on_500(self, monkeypatch):
        import httpx

        client = GitLabClient()
        call_count = 0

        async def fake_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                response = httpx.Response(503, request=httpx.Request("GET", "https://example.com"))
                raise httpx.HTTPStatusError(
                    "Unavailable", request=response.request, response=response
                )
            return httpx.Response(
                200, json={"ok": True}, request=httpx.Request("GET", "https://example.com")
            )

        monkeypatch.setattr(client.client, "request", fake_request)

        async def _noop_sleep(x):
            pass

        monkeypatch.setattr("asyncio.sleep", _noop_sleep)

        result = await client._request("GET", "/test")
        assert result.status_code == 200
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_request_does_not_retry_on_400(self, monkeypatch):
        import httpx

        client = GitLabClient()
        call_count = 0

        async def fake_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = httpx.Response(400, request=httpx.Request("GET", "https://example.com"))
            raise httpx.HTTPStatusError("Bad Request", request=response.request, response=response)

        monkeypatch.setattr(client.client, "request", fake_request)

        with pytest.raises(httpx.HTTPStatusError):
            await client._request("GET", "/test")
        assert call_count == 1


class TestPagination:
    @pytest.mark.asyncio
    async def test_get_all_follows_next_page(self, monkeypatch):
        import httpx

        client = GitLabClient()
        page = 0

        async def fake_request(method, url, **kwargs):
            nonlocal page
            page += 1
            if page == 1:
                headers = {"X-Next-Page": "2"}
                data = [{"id": 1}, {"id": 2}]
            else:
                headers = {}
                data = [{"id": 3}]
            return httpx.Response(
                200, json=data, headers=headers, request=httpx.Request("GET", "https://example.com")
            )

        monkeypatch.setattr(client.client, "request", fake_request)

        results = await client.get_all("/items")
        assert len(results) == 3
        assert results[2]["id"] == 3

    @pytest.mark.asyncio
    async def test_get_all_respects_limit(self, monkeypatch):
        import httpx

        client = GitLabClient()

        async def fake_request(method, url, **kwargs):
            data = [{"id": i} for i in range(1, 101)]
            return httpx.Response(
                200, json=data, request=httpx.Request("GET", "https://example.com")
            )

        monkeypatch.setattr(client.client, "request", fake_request)

        results = await client.get_all("/items", limit=5)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_merge_request_diffs_are_paginated(self, monkeypatch):
        client = GitLabClient()
        expected = [{"id": 1}, {"id": 2}]

        async def fake_get_all(*args, **kwargs):
            return expected

        monkeypatch.setattr(client, "get_all", fake_get_all)

        results = await client.get_merge_request_diffs("group/project", 7)

        assert results == expected


class TestUploadRedirects:
    @pytest.mark.asyncio
    async def test_fetch_upload_rejects_cross_host_redirect(self, monkeypatch):
        import httpx

        client = GitLabClient()

        class RedirectResponse:
            is_redirect = True
            next_request = httpx.Request("GET", "https://attacker.example/file.png")

            async def aclose(self):
                pass

        async def fake_get(*args, **kwargs):
            return RedirectResponse()

        monkeypatch.setattr(client.web_client, "get", fake_get)

        with pytest.raises(ValueError, match="redirect target"):
            await client.fetch_upload("/uploads/file.png")

    @pytest.mark.asyncio
    async def test_fetch_upload_rejects_http_redirect(self, monkeypatch):
        import httpx

        client = GitLabClient()

        class RedirectResponse:
            is_redirect = True
            next_request = httpx.Request("GET", "http://gitlab.example.com/file.png")

            async def aclose(self):
                pass

        async def fake_get(*args, **kwargs):
            return RedirectResponse()

        monkeypatch.setattr(client.web_client, "get", fake_get)

        with pytest.raises(ValueError, match="must use HTTPS"):
            await client.fetch_upload("/uploads/file.png")
