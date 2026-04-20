
from services.review_digest import (
    build_draft_reply_plan,
    build_review_digest,
    build_review_summary,
    build_suggested_replies,
    build_unresolved_discussion_digest,
    infer_suggested_reply,
    infer_summary_hint,
    normalize_discussion,
    normalize_discussion_note,
    normalize_draft_note,
)


def test_normalize_discussion_note():
    raw = {
        "id": 1,
        "body": "Looks good",
        "author": {"name": "Alice", "username": "alice"},
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "system": False,
        "resolvable": True,
        "resolved": False,
        "type": "DiffNote",
        "position": {"new_path": "src/main.py", "new_line": 10},
    }
    note = normalize_discussion_note(raw)
    assert note["body"] == "Looks good"
    assert note["author_name"] == "Alice"
    assert note["file_path"] == "src/main.py"
    assert note["new_line"] == 10
    assert note["resolvable"] is True
    assert note["resolved"] is False


def test_normalize_discussion():
    raw = {
        "id": "abc123",
        "individual_note": False,
        "notes": [
            {
                "id": 1,
                "body": "Issue here",
                "author": {"name": "Bob", "username": "bob"},
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "system": False,
                "resolvable": True,
                "resolved": False,
                "position": {"new_path": "src/app.py", "old_path": "src/app.py", "new_line": 5},
            }
        ],
    }
    d = normalize_discussion(raw)
    assert d["discussion_id"] == "abc123"
    assert d["unresolved"] is True
    assert d["resolvable"] is True
    assert d["file_path"] == "src/app.py"
    assert d["note_count"] == 1


def test_build_review_summary():
    discussions = [
        {
            "discussion_id": "d1",
            "individual_note": False,
            "note_count": 2,
            "unresolved": True,
            "resolvable": True,
            "file_path": "src/a.py",
            "notes": [],
        },
        {
            "discussion_id": "d2",
            "individual_note": True,
            "note_count": 1,
            "unresolved": False,
            "resolvable": True,
            "file_path": "src/a.py",
            "notes": [],
        },
        {
            "discussion_id": "d3",
            "individual_note": False,
            "note_count": 1,
            "unresolved": True,
            "resolvable": True,
            "file_path": "src/b.py",
            "notes": [],
        },
    ]
    summary = build_review_summary(discussions)
    assert summary["total_discussions"] == 3
    assert summary["unresolved_discussions"] == 2
    assert summary["resolvable_discussions"] == 3
    assert summary["individual_notes"] == 1
    # src/a.py should come first because it has 1 unresolved vs src/b.py 1 unresolved -> tie, alphabetical
    by_file = summary["by_file"]
    assert len(by_file) == 2


def test_build_unresolved_discussion_digest():
    discussions = [
        {
            "discussion_id": "d1",
            "individual_note": False,
            "note_count": 1,
            "unresolved": True,
            "resolvable": True,
            "file_path": "src/a.py",
            "notes": [
                {
                    "body": "null pointer risk",
                    "system": False,
                    "author_name": "Alice",
                    "author_username": "alice",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ],
        },
        {
            "discussion_id": "d2",
            "individual_note": False,
            "note_count": 1,
            "unresolved": False,
            "resolvable": True,
            "file_path": "src/b.py",
            "notes": [
                {
                    "body": "ok",
                    "system": False,
                    "author_name": "Bob",
                    "author_username": "bob",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ],
        },
    ]
    items = build_unresolved_discussion_digest(discussions)
    assert len(items) == 1
    assert items[0]["discussion_id"] == "d1"
    assert items[0]["summary_hint"] == "null handling"


def test_build_suggested_replies():
    discussions = [
        {
            "discussion_id": "d1",
            "individual_note": False,
            "note_count": 1,
            "unresolved": True,
            "resolvable": True,
            "file_path": "src/a.py",
            "notes": [
                {
                    "body": "missing tests",
                    "system": False,
                    "author_name": "Alice",
                    "author_username": "alice",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ],
        },
    ]
    replies = build_suggested_replies(discussions)
    assert len(replies) == 1
    assert (
        "test coverage" in replies[0]["suggested_reply"].lower()
        or "Addressed" in replies[0]["suggested_reply"]
    )


def test_build_review_digest():
    discussions = [
        {
            "discussion_id": "d1",
            "individual_note": False,
            "note_count": 1,
            "unresolved": True,
            "resolvable": True,
            "file_path": "src/a.py",
            "notes": [
                {
                    "body": "style issue",
                    "system": False,
                    "author_name": "Alice",
                    "author_username": "alice",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ],
        },
    ]
    digest = build_review_digest(discussions)
    assert digest["totals"]["total_discussions"] == 1
    assert len(digest["unresolved_items"]) == 1
    assert len(digest["suggested_replies"]) == 1


def test_build_draft_reply_plan():
    discussions = [
        {
            "discussion_id": "d1",
            "individual_note": False,
            "note_count": 1,
            "unresolved": True,
            "resolvable": True,
            "file_path": "MR_GENERAL",
            "notes": [
                {
                    "body": "general feedback",
                    "system": False,
                    "author_name": "Alice",
                    "author_username": "alice",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ],
        },
        {
            "discussion_id": "d2",
            "individual_note": False,
            "note_count": 1,
            "unresolved": True,
            "resolvable": True,
            "file_path": "src/a.py",
            "notes": [
                {
                    "body": "nit",
                    "system": False,
                    "author_name": "Bob",
                    "author_username": "bob",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ],
        },
    ]
    plan = build_draft_reply_plan(discussions)
    assert plan["total_items"] == 2
    modes = {item["target_mode"] for item in plan["items"]}
    assert modes == {"new_draft_general_note", "new_draft_reply"}


def test_infer_summary_hint():
    assert infer_summary_hint("missing null check") == "null handling"
    assert infer_summary_hint("add more tests") == "test coverage"
    assert infer_summary_hint("naming is confusing") == "naming/clarity"
    assert infer_summary_hint("slow query here") == "logic risk"
    assert infer_summary_hint("fix whitespace") == "style/nit"
    assert infer_summary_hint("looks fine") == "general feedback"


def test_infer_suggested_reply():
    assert "null" in infer_suggested_reply("null pointer").lower()
    assert "coverage" in infer_suggested_reply("test missing").lower()


def test_normalize_draft_note():
    raw = {
        "id": 99,
        "note": "Draft comment",
        "author": {"name": "Alice", "username": "alice"},
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "position": {"new_path": "src/x.py", "new_line": 7},
        "resolvable": True,
        "resolved": False,
    }
    dn = normalize_draft_note(raw)
    assert dn["body"] == "Draft comment"
    assert dn["file_path"] == "src/x.py"
    assert dn["new_line"] == 7
