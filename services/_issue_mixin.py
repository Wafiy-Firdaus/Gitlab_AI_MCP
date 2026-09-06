from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gitlab.client import GitLabClient
    from services.local_ai_service import LocalAIService

from services._utils import _extract_upload_urls


class _IssueMixin:
    """Issue-domain methods for GitLabService."""

    client: GitLabClient
    local_ai: LocalAIService

    if TYPE_CHECKING:

        async def _fetch_uploads(self, urls: list[str]) -> list[dict[str, Any]]: ...

    # --- Issue CRUD ---

    async def get_issue_details(
        self, project_id: int | str, issue_iid: int | str
    ) -> dict[str, Any]:
        issue = await self.client.get_issue(project_id, issue_iid)

        summary = f"Details for Issue #{issue['iid']}: {issue['title']}"
        key_findings = [
            f"Status: {issue['state']}",
            f"Author: {issue['author']['name']}",
            f"Assignees: {', '.join([a['name'] for a in issue['assignees']]) if issue['assignees'] else 'None'}",
            f"Labels: {', '.join(issue.get('labels', [])) if issue.get('labels') else 'None'}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": issue,
            "next_action": "You can update this issue, add a comment, or list its notes.",
        }

    async def create_issue(
        self,
        project_id: int | str,
        title: str,
        description: str | None = None,
        labels: str | None = None,
        assignee_ids: list[int] | None = None,
        milestone_id: int | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"title": title}
        if description:
            data["description"] = description
        if labels:
            data["labels"] = labels
        if assignee_ids:
            data["assignee_ids"] = assignee_ids
        if milestone_id:
            data["milestone_id"] = milestone_id

        issue = await self.client.create_issue(project_id, data)

        summary = f"Successfully created Issue #{issue['iid']}: {issue['title']}"
        key_findings = [
            f"IID: {issue['iid']}",
            f"Project: {project_id}",
            f"Labels: {', '.join(issue['labels']) if issue['labels'] else 'None'}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": issue,
            "next_action": "The issue is now created. You can add comments or assign it to someone.",
        }

    async def update_issue(
        self, project_id: int | str, issue_iid: int, **kwargs: Any
    ) -> dict[str, Any]:
        data = {k: v for k, v in kwargs.items() if v is not None}
        issue = await self.client.update_issue(project_id, issue_iid, data)

        summary = f"Successfully updated Issue #{issue['iid']}"
        key_findings = [f"Updated fields: {', '.join(data.keys())}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": issue,
            "next_action": "View the updated issue details or add a comment.",
        }

    # --- Issue notes ---

    async def list_issue_notes(self, project_id: int | str, issue_iid: int | str) -> dict[str, Any]:
        notes = await self.client.get_issue_notes(project_id, issue_iid)
        user_notes = [n for n in notes if not n.get("system")]

        # Build note_id -> discussion_id map from discussions
        discussions = await self.client.get_issue_discussions(project_id, issue_iid)
        note_to_discussion: dict[int, str] = {}
        for d in discussions:
            for note in d.get("notes", []):
                note_to_discussion[note["id"]] = d["id"]

        # Attach discussion_id to each note
        for note in notes:
            note["discussion_id"] = note_to_discussion.get(note["id"])

        summary = f"Found {len(user_notes)} user comments for Issue #{issue_iid}"
        key_findings = [f"{n['author']['name']}: {n['body'][:50]}..." for n in user_notes[:5]]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"notes": notes},
            "next_action": "Post a new comment if further discussion is needed.",
        }

    async def create_issue_note(
        self, project_id: int | str, issue_iid: int, body: str
    ) -> dict[str, Any]:
        note = await self.client.create_issue_note(project_id, issue_iid, body)

        summary = f"Successfully posted comment to Issue #{issue_iid}"
        key_findings = [
            f"Comment ID: {note.get('id')}",
            f"Author: {note.get('author', {}).get('name', 'Unknown')}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": note,
            "next_action": "The comment is now visible on the issue.",
        }

    async def reply_to_issue_discussion(
        self, project_id: int | str, issue_iid: int, discussion_id: str, body: str
    ) -> dict[str, Any]:
        note = await self.client.reply_to_issue_discussion(
            project_id, issue_iid, discussion_id, body
        )

        summary = f"Successfully replied to discussion on Issue #{issue_iid}"
        key_findings = [f"Note ID: {note['id']}", f"Author: {note['author']['name']}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": note,
            "next_action": "The reply is now visible in the discussion thread.",
        }

    # --- Bundle / triage ---

    async def bundle_issue_context(
        self, project_id: int | str, issue_iid: int | str
    ) -> dict[str, Any]:
        """
        High-performance tool that bundles issue details, notes, and related MRs.
        Reduces token usage by summarizing and filtering noise.
        """
        issue_task = self.client.get_issue(project_id, issue_iid)
        notes_task = self.client.get_issue_notes(project_id, issue_iid)
        mrs_task = self.client.get_issue_related_mrs(project_id, issue_iid)

        issue, notes, mrs = await asyncio.gather(issue_task, notes_task, mrs_task)

        user_notes = [n for n in notes if not n.get("system")]

        summary = f"Bundled context for Issue #{issue_iid}: {issue['title']}"
        key_findings = [
            f"Status: {issue['state']}",
            f"Comments: {len(user_notes)} user discussions",
            f"Linked MRs: {len(mrs)} relevant merge requests",
            f"Assignees: {', '.join([a['name'] for a in issue['assignees']]) if issue['assignees'] else 'None'}",
        ]

        compact_context: dict[str, Any] = {
            "issue_details": {
                "iid": issue["iid"],
                "title": issue["title"],
                "description": issue["description"],
                "author": issue["author"]["name"],
                "labels": issue["labels"],
                "state": issue["state"],
                "assignees": [a["name"] for a in issue["assignees"]],
            },
            "linked_merge_requests": [
                {"iid": m["iid"], "title": m["title"], "state": m["state"], "url": m["web_url"]}
                for m in mrs
            ],
            "recent_discussions": [
                {
                    "author": n["author"]["name"],
                    "body": n["body"][:200] + "..." if len(n["body"]) > 200 else n["body"],
                }
                for n in user_notes[-10:]
            ],
        }

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": compact_context,
            "next_action": "Analyze the bundled context to propose a resolution or check linked MR progress.",
        }

    async def triage_issue_locally(
        self, project_id: int | str, issue_iid: int | str
    ) -> dict[str, Any]:
        """
        Use local AI to analyze an issue description for labels and action items.
        """
        issue = await self.client.get_issue(project_id, issue_iid)

        prompt = (
            "You are a Project Manager. Analyze the provided GitLab issue description. "
            "1. Suggest 3-5 appropriate labels (e.g., bug, enhancement, priority:high).\n"
            "2. Extract a concise checklist of action items.\n"
            "3. Identify any missing information or blockers.\n"
            "Keep it structured and concise."
        )

        local_analysis = await self.local_ai.generate_summary(
            prompt, issue.get("description", "No description provided.")
        )

        summary = f"Locally triaged Issue #{issue_iid} using {self.local_ai.model}"
        key_findings = [
            "Issue analyzed locally (0 token cost)",
            f"Model: {self.local_ai.model}",
            "Labels and checklist suggested",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"issue_title": issue["title"], "local_ai_triage": local_analysis},
            "next_action": "Review the suggestions and apply appropriate labels or updates.",
        }

    # --- Attachments ---

    async def get_issue_attachments(
        self, project_id: int | str, issue_iid: int | str
    ) -> dict[str, Any]:
        issue = await self.client.get_issue(project_id, issue_iid)
        notes = await self.client.get_issue_notes(project_id, issue_iid)
        discussions = await self.client.get_issue_discussions(project_id, issue_iid)

        texts: list[str] = []
        if issue.get("description"):
            texts.append(issue["description"])
        for note in notes:
            if note.get("body"):
                texts.append(note["body"])
        for discussion in discussions:
            for note in discussion.get("notes", []):
                if note.get("body"):
                    texts.append(note["body"])

        all_urls: set[str] = set()
        for text in texts:
            all_urls.update(_extract_upload_urls(text))

        uploads = await self._fetch_uploads(list(all_urls))

        return {
            "summary": f"Found {len(uploads)} attachment(s) in Issue #{issue_iid}",
            "key_findings": [u["url"] for u in uploads if not u.get("error")],
            "details": {"issue_iid": issue_iid, "uploads": uploads},
            "next_action": "Use the markdown snippet or base64 content to display the images.",
        }
