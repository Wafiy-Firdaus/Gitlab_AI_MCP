from datetime import datetime
from typing import Any

from pydantic import BaseModel


class GitLabProject(BaseModel):
    id: int
    name: str
    path_with_namespace: str
    description: str | None = None
    web_url: str
    last_activity_at: datetime | None = None
    star_count: int = 0
    forks_count: int = 0
    ssh_url_to_repo: str | None = None
    http_url_to_repo: str | None = None

class GitLabIssue(BaseModel):
    id: int
    iid: int
    project_id: int
    title: str
    description: str | None = None
    state: str
    web_url: str
    created_at: datetime
    updated_at: datetime
    labels: list[str] = []
    author: dict[str, Any]
    assignee: dict[str, Any] | None = None

class GitLabMergeRequest(BaseModel):
    id: int
    iid: int
    project_id: int
    title: str
    description: str | None = None
    state: str
    web_url: str
    source_branch: str
    target_branch: str
    author: dict[str, Any]
    assignee: dict[str, Any] | None = None
