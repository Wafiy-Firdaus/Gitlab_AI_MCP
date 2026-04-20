"""Pure, deterministic review helpers for MR discussions.

No network I/O — callers fetch discussions and pass normalized data.
Ported from gitlab-review-mcp's review digest logic.
"""

from typing import Any


def _note_file_path(note: dict[str, Any]) -> str:
    pos = note.get("position")
    if not pos:
        return "MR_GENERAL"
    path = pos.get("new_path") or pos.get("old_path")
    if path and str(path).strip():
        return str(path)
    return "MR_GENERAL"


def _note_lines(note: dict[str, Any]) -> dict[str, int | None]:
    pos = note.get("position")
    if not pos:
        return {"old_line": None, "new_line": None}
    return {
        "old_line": pos.get("old_line"),
        "new_line": pos.get("new_line"),
    }


def normalize_discussion_note(raw: dict[str, Any]) -> dict[str, Any]:
    author = raw.get("author") or {}
    lines = _note_lines(raw)
    return {
        "id": raw.get("id"),
        "body": raw.get("body", ""),
        "author_name": author.get("name", ""),
        "author_username": author.get("username", ""),
        "created_at": raw.get("created_at", ""),
        "updated_at": raw.get("updated_at", ""),
        "system": raw.get("system", False),
        "resolvable": raw.get("resolvable") is True,
        "resolved": raw.get("resolved") is True,
        "type": raw.get("type"),
        "file_path": _note_file_path(raw),
        "old_line": lines["old_line"],
        "new_line": lines["new_line"],
    }


def normalize_discussion(raw: dict[str, Any]) -> dict[str, Any]:
    notes = [normalize_discussion_note(n) for n in raw.get("notes", [])]
    anchor = notes[0] if notes else None
    file_path = anchor["file_path"] if anchor else "MR_GENERAL"
    resolvable = any(n["resolvable"] for n in notes)
    unresolved = any(n["resolvable"] and not n["resolved"] for n in notes)
    return {
        "discussion_id": raw.get("id"),
        "individual_note": raw.get("individual_note", False),
        "note_count": len(notes),
        "unresolved": unresolved,
        "resolvable": resolvable,
        "file_path": file_path,
        "notes": notes,
    }


def build_review_summary(discussions: list[dict[str, Any]]) -> dict[str, Any]:
    total_discussions = len(discussions)
    unresolved_discussions = sum(1 for d in discussions if d["unresolved"])
    resolvable_discussions = sum(1 for d in discussions if d["resolvable"])
    individual_notes = sum(1 for d in discussions if d["individual_note"])

    by_file_map: dict[str, dict[str, int]] = {}
    for d in discussions:
        key = d["file_path"]
        cur = by_file_map.get(key, {"discussion_count": 0, "unresolved_count": 0})
        cur["discussion_count"] += 1
        if d["unresolved"]:
            cur["unresolved_count"] += 1
        by_file_map[key] = cur

    by_file: list[dict[str, Any]] = [
        {
            "file_path": fp,
            "discussion_count": v["discussion_count"],
            "unresolved_count": v["unresolved_count"],
        }
        for fp, v in by_file_map.items()
    ]
    by_file.sort(key=lambda x: (-int(x["unresolved_count"]), str(x["file_path"])))

    return {
        "total_discussions": total_discussions,
        "unresolved_discussions": unresolved_discussions,
        "resolvable_discussions": resolvable_discussions,
        "individual_notes": individual_notes,
        "by_file": by_file,
    }


def get_discussion_notes_chronological(discussion: dict[str, Any]) -> list[dict[str, Any]]:
    notes = [n for n in discussion.get("notes", []) if not n.get("system")]
    return sorted(notes, key=lambda x: x.get("created_at", ""))


def get_latest_discussion_note(discussion: dict[str, Any]) -> dict[str, Any] | None:
    human = get_discussion_notes_chronological(discussion)
    if human:
        return human[-1]
    all_notes = sorted(discussion.get("notes", []), key=lambda x: x.get("created_at", ""))
    return all_notes[-1] if all_notes else None


def infer_summary_hint(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("null", "undefined", "nil", "empty check", "npe")):
        return "null handling"
    if any(
        k in t
        for k in ("test", "tests", "testing", "coverage", "testcase", "jest", "mocha", "pytest")
    ):
        return "test coverage"
    if any(
        k in t
        for k in ("rename", "naming", "clarity", "readable", "readability", "confusing", "unclear")
    ):
        return "naming/clarity"
    if any(
        k in t
        for k in (
            "performance",
            "slow",
            "latency",
            "query",
            "n+1",
            "n + 1",
            "optimize",
            "optimization",
        )
    ):
        return "logic risk"
    if any(k in t for k in ("style", "lint", "format", "nit", "nitpick", "whitespace", "typo")):
        return "style/nit"
    return "general feedback"


def infer_suggested_reply(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("null", "undefined", "nil", "empty check", "npe")):
        return "Good catch. I'll add appropriate guards for null/empty cases and push an update."
    if any(
        k in t
        for k in ("test", "tests", "testing", "coverage", "testcase", "jest", "mocha", "pytest")
    ):
        return "Addressed in latest update. Added guard and test coverage."
    if any(
        k in t
        for k in ("rename", "naming", "clarity", "readable", "readability", "confusing", "unclear")
    ):
        return "Good catch. I'll align this implementation for clarity and consistency."
    if any(
        k in t
        for k in (
            "performance",
            "slow",
            "latency",
            "query",
            "n+1",
            "n + 1",
            "optimize",
            "optimization",
        )
    ):
        return "Thanks — I'll review performance here and optimize or document the tradeoff in the next commit."
    if any(k in t for k in ("style", "lint", "format", "nit", "nitpick", "whitespace", "typo")):
        return "Thanks, I'll clean this up and push a small follow-up commit."
    return "Thanks, I'll update this and push a follow-up commit."


def _draft_note_file_path(pos: dict[str, Any] | None) -> str:
    if not pos:
        return "MR_GENERAL"
    path = pos.get("new_path") or pos.get("old_path")
    if path and str(path).strip():
        return str(path)
    return "MR_GENERAL"


def _draft_note_lines(pos: dict[str, Any] | None) -> dict[str, int | None]:
    if not pos:
        return {"old_line": None, "new_line": None}
    return {
        "old_line": pos.get("old_line"),
        "new_line": pos.get("new_line"),
    }


def normalize_draft_note(raw: dict[str, Any]) -> dict[str, Any]:
    author = raw.get("author") or {}
    text = raw.get("note") or raw.get("body") or ""
    pos = raw.get("position")
    lines = _draft_note_lines(pos)
    return {
        "id": raw.get("id"),
        "body": text if isinstance(text, str) else "",
        "author_name": author.get("name", ""),
        "author_username": author.get("username", ""),
        "created_at": raw.get("created_at", ""),
        "updated_at": raw.get("updated_at", ""),
        "file_path": _draft_note_file_path(pos),
        "old_line": lines["old_line"],
        "new_line": lines["new_line"],
        "discussion_id": raw.get("discussion_id"),
        "resolvable": raw.get("resolvable") is True,
        "resolved": raw.get("resolved") is True,
    }


def _safe_file_path(d: dict[str, Any]) -> str:
    p = (d.get("file_path") or "").strip()
    return p if p else "MR_GENERAL"


def _thread_text_for_hints(d: dict[str, Any]) -> str:
    return "\n".join(n["body"] for n in d.get("notes", []) if not n.get("system"))


def build_unresolved_discussion_digest(discussions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for d in discussions:
        if not d.get("unresolved"):
            continue
        latest = get_latest_discussion_note(d)
        hint_source = _thread_text_for_hints(d) or (latest["body"] if latest else "")
        items.append(
            {
                "discussion_id": d["discussion_id"],
                "file_path": _safe_file_path(d),
                "latest_note_body": latest["body"] if latest else "",
                "latest_note_author": (latest["author_name"] if latest else "")
                or (latest["author_username"] if latest else ""),
                "latest_note_created_at": latest["created_at"] if latest else "",
                "unresolved": d["unresolved"],
                "resolvable": d["resolvable"],
                "note_count": d["note_count"],
                "summary_hint": infer_summary_hint(hint_source),
            }
        )
    return items


def build_suggested_replies(discussions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in discussions:
        if not d.get("unresolved"):
            continue
        latest = get_latest_discussion_note(d)
        text = _thread_text_for_hints(d) or (latest["body"] if latest else "")
        out.append(
            {
                "discussion_id": d["discussion_id"],
                "file_path": _safe_file_path(d),
                "suggested_reply": infer_suggested_reply(text),
            }
        )
    return out


def build_review_digest(discussions: list[dict[str, Any]]) -> dict[str, Any]:
    summary = build_review_summary(discussions)
    totals = {
        "total_discussions": summary["total_discussions"],
        "unresolved_discussions": summary["unresolved_discussions"],
        "resolvable_discussions": summary["resolvable_discussions"],
        "individual_notes": summary["individual_notes"],
    }
    top_files_with_unresolved = [f for f in summary["by_file"] if f["unresolved_count"] > 0][:10]
    return {
        "totals": totals,
        "top_files_with_unresolved": top_files_with_unresolved,
        "unresolved_items": build_unresolved_discussion_digest(discussions),
        "suggested_replies": build_suggested_replies(discussions),
    }


def build_draft_reply_plan(discussions: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for d in discussions:
        if not d.get("unresolved"):
            continue
        fp = _safe_file_path(d)
        latest = get_latest_discussion_note(d)
        text = _thread_text_for_hints(d) or (latest["body"] if latest else "")
        target_mode = "new_draft_general_note" if fp == "MR_GENERAL" else "new_draft_reply"
        did = d["discussion_id"]
        if did in seen:
            continue
        seen.add(did)
        items.append(
            {
                "discussion_id": did,
                "file_path": fp,
                "suggested_reply": infer_suggested_reply(text),
                "target_mode": target_mode,
            }
        )
    return {"total_items": len(items), "items": items}
