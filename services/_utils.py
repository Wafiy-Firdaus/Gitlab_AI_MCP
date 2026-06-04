from __future__ import annotations

import re
import urllib.parse

from config import settings


def _is_gitlab_upload_url(url: str) -> bool:
    """Ensure an upload URL belongs to the configured GitLab instance or is relative."""
    if url.startswith("http://") or url.startswith("https://"):
        gitlab_host = urllib.parse.urlparse(settings.gitlab_url).netloc
        return urllib.parse.urlparse(url).netloc == gitlab_host
    # Relative URLs are assumed to be on the GitLab instance
    return url.startswith("/")


def _extract_upload_urls(text: str | None) -> list[str]:
    """Extract GitLab upload URLs from markdown/HTML text."""
    if not text:
        return []

    urls: set[str] = set()

    # Markdown images: ![alt](url) and links: [text](url)
    for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", text):
        url = match.group(1)
        if "/uploads/" in url and _is_gitlab_upload_url(url):
            urls.add(url)

    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
        url = match.group(1)
        if "/uploads/" in url and _is_gitlab_upload_url(url):
            urls.add(url)

    # HTML img tags
    for match in re.finditer(r'<img[^>]+src=["\']?([^"\'>\s]+)', text, re.IGNORECASE):
        url = match.group(1)
        if "/uploads/" in url and _is_gitlab_upload_url(url):
            urls.add(url)

    # Bare upload URLs (anything containing /uploads/)
    for match in re.finditer(r'(?:^|[\s(\[<])((?:https?://[^\s"\']+)?/uploads/[^\s"\'\])]+)', text):
        url = match.group(1)
        if url and _is_gitlab_upload_url(url):
            urls.add(url)

    return sorted(urls)
