from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from services._utils import _extract_upload_urls
from services.review_digest import (
    build_draft_reply_plan,
    build_review_digest,
    build_review_summary,
    build_suggested_replies,
    build_unresolved_discussion_digest,
    normalize_discussion,
    normalize_draft_note,
)

if TYPE_CHECKING:
    from gitlab.client import GitLabClient
    from services.local_ai_service import LocalAIService


class _MRMixin:
    """Merge-request-domain methods for GitLabService."""

    client: GitLabClient
    local_ai: LocalAIService

    if TYPE_CHECKING:
        async def _fetch_uploads(self, urls: list[str]) -> list[dict[str, Any]]: ...

    async def get_merge_request_details(
        self, project_id: int | str, mr_iid: int | str, include_jobs: bool = False
    ) -> dict[str, Any]:
        mr = await self.client.get_merge_request(project_id, mr_iid)

        jobs: list[Any] = []
        if include_jobs and mr.get("head_pipeline"):
            pipeline_id = mr["head_pipeline"]["id"]
            jobs = await self.client.list_pipeline_jobs(project_id, pipeline_id)
            mr["head_pipeline_jobs"] = jobs

        summary = f"Details for Merge Request !{mr['iid']}: {mr['title']}"
        key_findings = [
            f"Status: {mr['state']}",
            f"Author: {mr['author']['name']}",
            f"Source: {mr['source_branch']} -> Target: {mr['target_branch']}",
            f"Merge Status: {mr['merge_status']}",
            f"Pipeline Status: {(mr.get('head_pipeline') or {}).get('status', 'N/A')}",
        ]
        if jobs:
            key_findings.append(f"Jobs: {len(jobs)} jobs retrieved for head pipeline")

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": mr,
            "next_action": "You can update this MR, approve it, add a comment, or view diffs.",
        }

    async def update_merge_request(
        self, project_id: int | str, mr_iid: int, **kwargs: Any
    ) -> dict[str, Any]:
        data = {k: v for k, v in kwargs.items() if v is not None}
        mr = await self.client.update_merge_request(project_id, mr_iid, data)

        summary = f"Successfully updated Merge Request !{mr['iid']}"
        key_findings = [f"Updated fields: {', '.join(data.keys())}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": mr,
            "next_action": "View the updated MR details or request approval.",
        }

    async def approve_merge_request(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        approval = await self.client.approve_merge_request(project_id, mr_iid)

        summary = f"Successfully approved Merge Request !{mr_iid}"
        key_findings = [f"Project ID: {project_id}", f"MR IID: {mr_iid}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": approval,
            "next_action": "The MR is now approved. You can check the merge status.",
        }

    async def list_merge_request_notes(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        notes = await self.client.get_merge_request_notes(project_id, mr_iid)
        user_notes = [n for n in notes if not n.get("system")]

        summary = f"Found {len(user_notes)} user comments for Merge Request !{mr_iid}"
        key_findings = [f"{n['author']['name']}: {n['body'][:50]}..." for n in user_notes[:5]]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"notes": notes},
            "next_action": "Post a new comment or resolve existing discussions.",
        }

    async def create_merge_request_note(
        self, project_id: int | str, mr_iid: int, body: str
    ) -> dict[str, Any]:
        note = await self.client.create_merge_request_note(project_id, mr_iid, body)

        summary = f"Successfully posted comment to Merge Request !{mr_iid}"
        key_findings = [f"Comment ID: {note['id']}", f"Author: {note['author']['name']}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": note,
            "next_action": "The comment is now visible on the merge request.",
        }

    async def get_merge_request_diffs(
        self, project_id: int | str, mr_iid: int | str, paths: list[str] | None = None
    ) -> dict[str, Any]:
        diffs = await self.client.get_merge_request_diffs(project_id, mr_iid)

        if paths:
            diffs = [d for d in diffs if d.get("new_path") in paths or d.get("old_path") in paths]

        summary = f"Retrieved {len(diffs)} changed files for Merge Request !{mr_iid}"
        if paths:
            summary += f" (filtered by {len(paths)} paths)"

        key_findings = [
            f"{d['new_path']} ({'+' if d['new_file'] else 'modified'})" for d in diffs[:10]
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"diffs": diffs},
            "next_action": "Review the code changes for each file.",
        }

    async def list_merge_request_discussions(
        self,
        project_id: int | str,
        mr_iid: int,
        unresolved_only: bool = False,
        include_system: bool = True,
    ) -> dict[str, Any]:
        discussions = await self.client.get_merge_request_discussions(project_id, mr_iid)

        filtered_discussions = []
        for d in discussions:
            if unresolved_only:
                if d.get("resolved", False):
                    continue

            filtered_notes = []
            for n in d.get("notes", []):
                if not include_system and n.get("system", False):
                    continue
                filtered_notes.append(n)

            if filtered_notes:
                d_copy = d.copy()
                d_copy["notes"] = filtered_notes
                filtered_discussions.append(d_copy)

        summary = f"Found {len(filtered_discussions)} discussions for Merge Request !{mr_iid}"
        if unresolved_only:
            summary += " (unresolved only)"

        key_findings = [
            f"Discussion {d['id'][:8]}: {len(d['notes'])} notes" for d in filtered_discussions[:5]
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"discussions": filtered_discussions},
            "next_action": "You can resolve a specific discussion using its ID.",
        }

    async def list_merge_request_discussion_summaries(
        self, project_id: int | str, mr_iid: int, unresolved_only: bool = False
    ) -> dict[str, Any]:
        discussions = await self.client.get_merge_request_discussions(project_id, mr_iid)

        summaries = []
        for d in discussions:
            if unresolved_only and d.get("resolved", False):
                continue

            user_notes = [n for n in d.get("notes", []) if not n.get("system")]
            if not user_notes:
                continue

            first_note = user_notes[0]
            summaries.append(
                {
                    "id": d["id"],
                    "author": first_note["author"]["name"],
                    "first_line": first_note["body"].split("\n")[0][:100],
                    "resolved": d.get("resolved", False),
                    "note_count": len(d.get("notes", [])),
                }
            )

        summary = f"Found {len(summaries)} discussion threads for MR !{mr_iid}"
        if unresolved_only:
            summary += " (unresolved only)"

        key_findings = [
            f"Resolved: {sum(1 for s in summaries if s['resolved'])}",
            f"Unresolved: {sum(1 for s in summaries if not s['resolved'])}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"discussions": summaries},
            "next_action": "Use the discussion ID to read or reply to a specific thread.",
        }

    async def resolve_merge_request_discussion(
        self, project_id: int | str, mr_iid: int, discussion_id: str, resolved: bool = True
    ) -> dict[str, Any]:
        result = await self.client.resolve_merge_request_discussion(
            project_id, mr_iid, discussion_id, resolved
        )

        summary = (
            f"Successfully {'resolved' if resolved else 'unresolved'} discussion {discussion_id}"
        )
        key_findings = [
            f"MR !{mr_iid}",
            f"Discussion ID: {discussion_id}",
            f"Status: {'Resolved' if resolved else 'Open'}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "Check if all other discussions are resolved before merging.",
        }

    async def get_latest_merge_request_version(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        version = await self.client.get_latest_merge_request_version(project_id, mr_iid)
        summary = f"Latest diff version for MR !{mr_iid}"
        key_findings = [
            f"base_sha: {version['base_sha']}",
            f"start_sha: {version['start_sha']}",
            f"head_sha: {version['head_sha']}",
        ]
        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": version,
            "next_action": "Use these SHAs when constructing diff comment positions.",
        }

    async def build_text_diff_position(
        self,
        project_id: int | str,
        mr_iid: int,
        new_path: str,
        old_path: str | None = None,
        new_line: int | None = None,
        old_line: int | None = None,
    ) -> dict[str, Any]:
        position = await self.client.build_text_diff_position(
            project_id, mr_iid, new_path, old_path=old_path, new_line=new_line, old_line=old_line
        )
        return {
            "summary": "Resolved diff position for MR comment",
            "key_findings": [
                f"File: {position['new_path']}",
                f"base_sha: {position['base_sha']}",
                f"head_sha: {position['head_sha']}",
            ],
            "details": {"position": position},
            "next_action": "Pass this position to create_merge_request_discussion or create_draft_note.",
        }

    async def list_merge_request_draft_notes(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        raw = await self.client.list_merge_request_draft_notes(project_id, mr_iid)
        draft_notes = [normalize_draft_note(n) for n in raw]
        summary = f"Found {len(draft_notes)} draft notes for MR !{mr_iid}"
        key_findings = [f"Draft {n['id']}: {n['file_path']}" for n in draft_notes[:5]]
        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"draft_notes": draft_notes},
            "next_action": "Review wording, then publish or delete drafts.",
        }

    async def create_merge_request_draft_note(
        self,
        project_id: int | str,
        mr_iid: int,
        body: str,
        position: dict[str, Any] | None = None,
        discussion_id: str | None = None,
        resolve_discussion: bool | None = None,
    ) -> dict[str, Any]:
        result = await self.client.create_merge_request_draft_note(
            project_id,
            mr_iid,
            body,
            position=position,
            discussion_id=discussion_id,
            resolve_discussion=resolve_discussion,
        )
        summary = f"Created draft note on MR !{mr_iid}"
        key_findings = [f"Draft Note ID: {result.get('id')}"]
        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "Inspect with list_draft_notes, then publish when ready.",
        }

    async def delete_merge_request_draft_note(
        self, project_id: int | str, mr_iid: int, draft_note_id: int
    ) -> dict[str, Any]:
        await self.client.delete_merge_request_draft_note(project_id, mr_iid, draft_note_id)
        summary = f"Deleted draft note {draft_note_id} from MR !{mr_iid}"
        return {
            "summary": summary,
            "key_findings": [f"Removed draft note {draft_note_id}"],
            "details": {"draft_note_id": draft_note_id, "status": "deleted"},
            "next_action": "Draft note removed. It will not be published.",
        }

    async def publish_merge_request_draft_notes(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        result = await self.client.publish_merge_request_draft_notes(project_id, mr_iid)
        summary = f"Published all draft notes on MR !{mr_iid}"
        return {
            "summary": summary,
            "key_findings": ["All draft notes are now public"],
            "details": result or {"published": True},
            "next_action": "Review the public discussions on the merge request.",
        }

    async def get_review_summary(self, project_id: int | str, mr_iid: int | str) -> dict[str, Any]:
        raw = await self.client.get_merge_request_discussions(project_id, mr_iid)
        discussions = [normalize_discussion(d) for d in raw]
        summary = build_review_summary(discussions)
        return {
            "summary": f"Review summary for MR !{mr_iid}",
            "key_findings": [
                f"Total discussions: {summary['total_discussions']}",
                f"Unresolved: {summary['unresolved_discussions']}",
            ],
            "details": summary,
            "next_action": "Drill down with get_unresolved_discussion_digest or get_review_digest.",
        }

    async def get_unresolved_discussion_digest(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        raw = await self.client.get_merge_request_discussions(project_id, mr_iid)
        discussions = [normalize_discussion(d) for d in raw]
        items = build_unresolved_discussion_digest(discussions)
        return {
            "summary": f"Unresolved discussion digest for MR !{mr_iid}",
            "key_findings": [f"Unresolved items: {len(items)}"],
            "details": {"unresolved_items": items},
            "next_action": "Address unresolved items or stage draft replies.",
        }

    async def get_suggested_replies(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        raw = await self.client.get_merge_request_discussions(project_id, mr_iid)
        discussions = [normalize_discussion(d) for d in raw]
        replies = build_suggested_replies(discussions)
        return {
            "summary": f"Suggested replies for MR !{mr_iid}",
            "key_findings": [f"Templates for {len(replies)} unresolved threads"],
            "details": {"suggested_replies": replies},
            "next_action": "Edit suggested replies before using bulk_reply_to_discussions or create_draft_note.",
        }

    async def get_review_digest(self, project_id: int | str, mr_iid: int | str) -> dict[str, Any]:
        raw = await self.client.get_merge_request_discussions(project_id, mr_iid)
        discussions = [normalize_discussion(d) for d in raw]
        digest = build_review_digest(discussions)
        return {
            "summary": f"Combined review digest for MR !{mr_iid}",
            "key_findings": [
                f"Totals: {digest['totals']['total_discussions']} discussions, "
                f"{digest['totals']['unresolved_discussions']} unresolved",
            ],
            "details": digest,
            "next_action": "Use get_suggested_replies or bulk_reply_to_discussions to respond.",
        }

    async def get_draft_reply_plan(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        raw = await self.client.get_merge_request_discussions(project_id, mr_iid)
        discussions = [normalize_discussion(d) for d in raw]
        plan = build_draft_reply_plan(discussions)
        return {
            "summary": f"Draft reply plan for MR !{mr_iid}",
            "key_findings": [f"Planned items: {plan['total_items']}"],
            "details": plan,
            "next_action": "Review target_mode and suggested_reply for each item before staging.",
        }

    async def bulk_reply_to_discussions(
        self, project_id: int | str, mr_iid: int, replies: list[dict[str, Any]]
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for r in replies:
            discussion_id = r.get("discussion_id", "")
            body = r.get("body", "")
            try:
                await self.client.add_merge_request_discussion_note(
                    project_id, mr_iid, discussion_id, body
                )
                results.append({"discussion_id": discussion_id, "success": True})
            except Exception as e:
                results.append({"discussion_id": discussion_id, "success": False, "error": str(e)})
        success_count = sum(1 for r in results if r["success"])
        return {
            "summary": f"Bulk reply to discussions on MR !{mr_iid}",
            "key_findings": [f"Success: {success_count}/{len(results)}"],
            "details": {"results": results},
            "next_action": "Retry failed items individually if needed.",
        }

    async def bulk_resolve_discussions(
        self,
        project_id: int | str,
        mr_iid: int,
        discussion_ids: list[str],
        resolved: bool = True,
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for did in discussion_ids:
            try:
                await self.client.resolve_merge_request_discussion(
                    project_id, mr_iid, did, resolved
                )
                results.append({"discussion_id": did, "success": True})
            except Exception as e:
                results.append({"discussion_id": did, "success": False, "error": str(e)})
        success_count = sum(1 for r in results if r["success"])
        return {
            "summary": f"Bulk {'resolve' if resolved else 'reopen'} discussions on MR !{mr_iid}",
            "key_findings": [f"Success: {success_count}/{len(results)}"],
            "details": {"results": results},
            "next_action": "Verify remaining open discussions before merging.",
        }

    async def add_merge_request_discussion_note(
        self, project_id: int | str, mr_iid: int, discussion_id: str, body: str
    ) -> dict[str, Any]:
        result = await self.client.add_merge_request_discussion_note(
            project_id, mr_iid, discussion_id, body
        )

        summary = f"Successfully replied to discussion {discussion_id} on MR !{mr_iid}"
        key_findings = [f"Note ID: {result['id']}", f"Author: {result['author']['name']}"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "The reply is now visible in the discussion thread.",
        }

    async def create_merge_request_discussion(
        self,
        project_id: int | str,
        mr_iid: int,
        body: str,
        position: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = await self.client.create_merge_request_discussion(
            project_id, mr_iid, body, position
        )

        summary = f"Successfully created a new discussion on MR !{mr_iid}"
        key_findings = [
            f"Discussion ID: {result['id']}",
            f"First Note ID: {result.get('notes', [{}])[0].get('id', 'N/A')}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "The new discussion thread is now active.",
        }

    async def update_note(
        self,
        project_id: int | str,
        resource_type: str,
        resource_iid: int,
        note_id: int,
        body: str,
    ) -> dict[str, Any]:
        result = await self.client.update_note(
            project_id, resource_type, resource_iid, note_id, body
        )

        summary = f"Successfully updated note {note_id} on {resource_type} {resource_iid}"
        key_findings = [f"Note ID: {result['id']}", "Content updated"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "The note content has been modified.",
        }

    async def delete_note(
        self,
        project_id: int | str,
        resource_type: str,
        resource_iid: int,
        note_id: int,
    ) -> dict[str, Any]:
        await self.client.delete_note(project_id, resource_type, resource_iid, note_id)

        summary = f"Successfully deleted note {note_id} from {resource_type} {resource_iid}"
        key_findings = [f"Note {note_id} removed"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"note_id": note_id, "status": "deleted"},
            "next_action": "The note is no longer available.",
        }

    async def create_merge_request(self, project_id: int | str, **kwargs: Any) -> dict[str, Any]:
        data = {k: v for k, v in kwargs.items() if v is not None}
        result = await self.client.create_merge_request(project_id, data)

        summary = f"Successfully created Merge Request !{result['iid']}"
        key_findings = [
            f"Title: {result['title']}",
            f"Source: {result.get('source_branch', 'N/A')} -> Target: {result.get('target_branch', 'N/A')}",
            f"Author: {result.get('author', {}).get('name', 'Unknown')}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "Review the new MR or assign reviewers.",
        }

    async def merge_merge_request(
        self, project_id: int | str, mr_iid: int, **kwargs: Any
    ) -> dict[str, Any]:
        data = {k: v for k, v in kwargs.items() if v is not None}
        result = await self.client.merge_merge_request(project_id, mr_iid, data)

        summary = f"Successfully merged Merge Request !{mr_iid}"
        key_findings = [
            f"Status: {result.get('state', 'merged')}",
            f"Merge Commit SHA: {result.get('merge_commit_sha', 'N/A')[:8]}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "The MR is merged. You can now delete the source branch if not done automatically.",
        }

    async def rebase_merge_request(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        result = await self.client.rebase_merge_request(project_id, mr_iid)

        summary = f"Successfully triggered rebase for MR !{mr_iid}"
        key_findings = ["Rebase in progress"]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "Check the MR status to verify rebase completion.",
        }

    async def get_merge_request_approvals(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        result = await self.client.get_merge_request_approvals(project_id, mr_iid)

        summary = f"Retrieved approval status for MR !{mr_iid}"
        key_findings = [
            f"Approvals Required: {result.get('approvals_required', 0)}",
            f"Approvals Left: {result.get('approvals_left', 0)}",
            f"Approved By: {', '.join([a['user']['name'] for a in result.get('approved_by', [])]) or 'None'}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": result,
            "next_action": "Check if more approvals are needed before merging.",
        }

    async def list_merge_request_pipelines(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        pipelines = await self.client.list_merge_request_pipelines(project_id, mr_iid)

        summary = f"Found {len(pipelines)} pipelines for MR !{mr_iid}"
        key_findings = [f"ID: {p['id']} - Status: {p['status']}" for p in pipelines[:5]]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"pipelines": pipelines},
            "next_action": "Check the most recent pipeline for build/test results.",
        }

    async def summarize_mr_discussions_locally(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        """
        Use local AI to summarize all reviewer discussions and highlights in an MR.
        """
        notes = await self.client.get_merge_request_notes(project_id, mr_iid)
        user_notes = [n for n in notes if not n.get("system")]

        discussions_text = "\n".join(
            [f"Author: {n['author']['name']}\nBody: {n['body']}\n" for n in user_notes]
        )

        prompt = (
            "You are a Lead Engineer. Summarize the following Merge Request discussions. "
            "1. List the top 3 critical concerns from reviewers.\n"
            "2. Identify any unresolved threads or blockers.\n"
            "3. Summarize the general sentiment of the review.\n"
            "Focus on actionable items for the developer."
        )

        local_summary = await self.local_ai.generate_summary(prompt, discussions_text)

        summary = f"Locally summarized discussions for MR !{mr_iid} using {self.local_ai.model}"
        key_findings = [
            f"Analyzed {len(user_notes)} user comments locally",
            "Identified critical concerns and blockers",
            "Privacy-first analysis (secrets scrubbed)",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"total_comments": len(user_notes), "local_ai_summary": local_summary},
            "next_action": "Address the critical concerns identified in the summary.",
        }

    async def check_mr_privacy_locally(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        """
        Use local AI to scan MR diffs and description for leaked secrets before merging.
        """
        mr = await self.client.get_merge_request(project_id, mr_iid)
        diffs = await self.client.get_merge_request_diffs(project_id, mr_iid)

        content_to_scan = f"Description: {mr.get('description', '')}\n\nDiffs:\n"
        for d in diffs:
            content_to_scan += f"File: {d['new_path']}\n{d['diff']}\n\n"

        prompt = (
            "You are a Security Specialist. Scan the following code diffs and description for leaked secrets. "
            "Look for: API keys, private tokens, passwords, AWS credentials, or sensitive IP addresses. "
            "Report only the files and line numbers (if visible) that contain potential leaks. "
            "If no leaks are found, explicitly state 'No sensitive information detected'."
        )

        local_report = await self.local_ai.generate_summary(prompt, content_to_scan)

        summary = f"Locally scanned MR !{mr_iid} for privacy leaks"
        key_findings = [
            "Scanned description and all code diffs",
            "Analysis performed 100% locally",
            f"Result provided by {self.local_ai.model}",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": {"security_report": local_report},
            "next_action": "If leaks were found, redact them immediately before merging.",
        }

    async def bundle_merge_request_context(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        """
        High-performance tool that bundles MR details, discussions, and diffs.
        Reduces token usage by summarizing and filtering noise.
        """
        mr_task = self.client.get_merge_request(project_id, mr_iid)
        notes_task = self.client.get_merge_request_notes(project_id, mr_iid)
        diffs_task = self.client.get_merge_request_diffs(project_id, mr_iid)

        mr, notes, diffs = await asyncio.gather(mr_task, notes_task, diffs_task)

        user_notes = [n for n in notes if not n.get("system")]

        diff_summary = [
            f"{d['new_path']} ({'added' if d['new_file'] else 'modified'})" for d in diffs
        ]

        summary = f"Bundled context for Merge Request !{mr_iid}: {mr['title']}"
        key_findings = [
            f"State: {mr['state']}",
            f"Comments: {len(user_notes)} user discussions",
            f"Changes: {len(diffs)} files modified",
            f"Source: {mr['source_branch']} -> {mr['target_branch']}",
        ]

        compact_context: dict[str, Any] = {
            "mr_details": {
                "iid": mr["iid"],
                "title": mr["title"],
                "description": mr["description"],
                "author": mr["author"]["name"],
                "labels": mr["labels"],
            },
            "recent_discussions": [
                {
                    "author": n["author"]["name"],
                    "body": n["body"][:200] + "..." if len(n["body"]) > 200 else n["body"],
                }
                for n in user_notes[-5:]
            ],
            "changed_files": diff_summary,
        }

        return {
            "summary": summary,
            "key_findings": key_findings,
            "details": compact_context,
            "next_action": "Analyze the bundled context to perform a comprehensive review or identify blockers.",
        }

    async def get_merge_request_attachments(
        self, project_id: int | str, mr_iid: int | str
    ) -> dict[str, Any]:
        mr = await self.client.get_merge_request(project_id, mr_iid)
        notes = await self.client.get_merge_request_notes(project_id, mr_iid)
        discussions = await self.client.get_merge_request_discussions(project_id, mr_iid)

        texts: list[str] = []
        if mr.get("description"):
            texts.append(mr["description"])
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
            "summary": f"Found {len(uploads)} attachment(s) in Merge Request !{mr_iid}",
            "key_findings": [u["url"] for u in uploads if not u.get("error")],
            "details": {"mr_iid": mr_iid, "uploads": uploads},
            "next_action": "Use the markdown snippet or base64 content to display the images.",
        }
