"""
Test suite for parse_minutes — verifies the parsing fix for Llama 3.2 output.
Tests the exact scenarios that caused the bug: literal newlines in JSON strings.
"""
import json
import re
import sys
import os

# Add the backend to the path so we can import parse_minutes
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.parse_minutes import parse_minutes


def test_valid_json():
    """Test 1: Valid JSON with properly escaped newlines — should parse perfectly."""
    raw = json.dumps({
        "title": "Q4 Planning Review",
        "date": "2026-11-15",
        "location": "Conference Room B",
        "attendees": ["Alice", "Bob", "Charlie"],
        "summary": "The team reviewed Q4 targets and assigned action items.",
        "discussion_points": ["Budget allocation for Q1", "Hiring timeline", "Product launch schedule"],
        "takeaways": ["Budget needs board approval", "Two new hires approved"],
        "action_items": [
            {"task": "Submit budget proposal", "owner": "Alice", "due_date": "2026-11-22"},
            {"task": "Post job listings", "owner": "Bob", "due_date": "2026-11-25"}
        ],
        "markdown": "# Q4 Planning\n\n## Summary\nReviewed targets.\n\n## Actions\n- Budget (Alice)\n- Hiring (Bob)"
    })
    m = parse_minutes(raw)
    assert m.title == "Q4 Planning Review", f"title: {m.title}"
    assert m.date == "2026-11-15", f"date: {m.date}"
    assert m.location == "Conference Room B", f"location: {m.location}"
    assert m.attendees == ["Alice", "Bob", "Charlie"], f"attendees: {m.attendees}"
    assert m.summary == "The team reviewed Q4 targets and assigned action items.", f"summary: {m.summary}"
    assert len(m.discussion_points) == 3, f"discussion_points count: {len(m.discussion_points)}"
    assert m.discussion_points[0] == "Budget allocation for Q1"
    assert len(m.takeaways) == 2, f"takeaways count: {len(m.takeaways)}"
    assert len(m.action_items) == 2, f"action_items count: {len(m.action_items)}"
    assert m.action_items[0].task == "Submit budget proposal"
    assert m.action_items[0].owner == "Alice"
    assert m.action_items[0].due_date == "2026-11-22"
    assert m.action_items[1].task == "Post job listings"
    assert m.action_items[1].owner == "Bob"
    assert m.markdown.startswith("# Q4 Planning")
    # summary must NOT be the raw JSON
    assert not m.summary.startswith("{"), "summary should not be raw JSON"
    print("  PASS: test_valid_json")


def test_literal_newlines_in_markdown():
    """Test 2: JSON with literal newlines in string values — the EXACT bug.
    Llama 3.2 3B outputs actual newline characters inside the markdown field
    instead of \\n escape sequences. json.loads rejects this as
    'Invalid control character'. The fix must sanitize and re-parse."""
    raw = '''{
    "title": "Q4 Planning Review",
    "date": "2026-11-15",
    "location": "Conference Room B",
    "attendees": ["Alice", "Bob", "Charlie"],
    "summary": "The team reviewed Q4 targets and assigned action items.",
    "discussion_points": ["Budget allocation for Q1", "Hiring timeline", "Product launch schedule"],
    "takeaways": ["Budget needs board approval", "Two new hires approved"],
    "action_items": [
        {"task": "Submit budget proposal", "owner": "Alice", "due_date": "2026-11-22"},
        {"task": "Post job listings", "owner": "Bob", "due_date": "2026-11-25"}
    ],
    "markdown": "# Q4 Planning Review

## Summary
The team reviewed Q4 targets and assigned action items.

## Discussion Points
- Budget allocation for Q1
- Hiring timeline
- Product launch schedule

## Action Items
- Submit budget proposal (Alice, due 2026-11-22)
- Post job listings (Bob, due 2026-11-25)"
}'''
    m = parse_minutes(raw)
    assert m.title == "Q4 Planning Review", f"title: {m.title}"
    assert m.date == "2026-11-15", f"date: {m.date}"
    assert m.location == "Conference Room B", f"location: {m.location}"
    assert m.attendees == ["Alice", "Bob", "Charlie"], f"attendees: {m.attendees}"
    assert m.summary == "The team reviewed Q4 targets and assigned action items.", f"summary: {m.summary}"
    assert len(m.discussion_points) == 3, f"discussion_points count: {len(m.discussion_points)}"
    assert len(m.takeaways) == 2, f"takeaways count: {len(m.takeaways)}"
    assert len(m.action_items) == 2, f"action_items count: {len(m.action_items)}"
    assert m.action_items[0].task == "Submit budget proposal"
    assert m.action_items[0].owner == "Alice"
    # summary must NOT contain the raw JSON
    assert not m.summary.startswith("{"), "summary should not be raw JSON"
    # markdown should be the actual markdown, not the raw JSON
    assert "# Q4 Planning Review" in m.markdown, f"markdown should contain report, got: {m.markdown[:50]}"
    print("  PASS: test_literal_newlines_in_markdown")


def test_code_fenced_json():
    """Test 3: JSON wrapped in ```json code fences."""
    inner = json.dumps({
        "title": "Sprint Retro",
        "date": "2026-11-20",
        "location": "Zoom",
        "attendees": ["Dev Team"],
        "summary": "Reviewed sprint velocity.",
        "discussion_points": ["Velocity dropped 15%"],
        "takeaways": ["Reduce meeting overhead"],
        "action_items": [{"task": "Cancel standups on Fridays", "owner": "Scrum Master", "due_date": "Next sprint"}],
        "markdown": "# Sprint Retro\n\nVelocity reviewed."
    })
    raw = f"```json\n{inner}\n```"
    m = parse_minutes(raw)
    assert m.title == "Sprint Retro", f"title: {m.title}"
    assert m.date == "2026-11-20"
    assert len(m.action_items) == 1
    assert m.action_items[0].owner == "Scrum Master"
    print("  PASS: test_code_fenced_json")


def test_completely_unparseable():
    """Test 4: Totally non-JSON output — should fall back gracefully."""
    raw = "Here are the meeting minutes:\n\n## Summary\nWe discussed things.\n\n## Action Items\n- Do stuff"
    m = parse_minutes(raw)
    assert m.title == "Meeting Minutes"  # default
    assert m.date == "Not specified"
    assert "could not be parsed" in m.summary.lower() or m.summary != ""
    assert m.markdown == raw, "markdown should contain the raw text as fallback"
    assert len(m.discussion_points) == 0
    assert len(m.action_items) == 0
    print("  PASS: test_completely_unparseable")


def test_summary_never_contains_full_json():
    """Test 5: Verify summary is never the entire JSON object string.
    This is the specific UI bug — the Executive Summary showed the raw JSON."""
    raw = '''{
    "title": "Team Sync",
    "date": "2026-11-18",
    "location": "Not specified",
    "attendees": ["Alice"],
    "summary": "Quick sync on project status.",
    "discussion_points": ["Timeline update"],
    "takeaways": ["On track for deadline"],
    "action_items": [],
    "markdown": "# Team Sync

Quick sync on project status.

## Discussion
- Timeline update"
}'''
    m = parse_minutes(raw)
    assert m.summary == "Quick sync on project status.", f"summary: {m.summary}"
    assert "{" not in m.summary, "summary must not contain JSON braces"
    assert "title" not in m.summary.lower() or "Team" not in m.summary, "summary must not be the JSON object"
    assert m.date == "2026-11-18", f"date: {m.date}"
    assert len(m.discussion_points) == 1
    assert m.discussion_points[0] == "Timeline update"
    print("  PASS: test_summary_never_contains_full_json")


def test_action_items_as_strings():
    """Test 6: action_items as plain strings instead of objects."""
    raw = json.dumps({
        "title": "Standup",
        "date": "2026-11-21",
        "location": "Slack",
        "attendees": ["Team"],
        "summary": "Daily standup.",
        "discussion_points": ["Blockers"],
        "takeaways": ["No blockers"],
        "action_items": ["Review PR #42", "Deploy staging"],
        "markdown": "# Standup\n\nDaily standup."
    })
    m = parse_minutes(raw)
    assert len(m.action_items) == 2
    assert m.action_items[0].task == "Review PR #42"
    assert m.action_items[0].owner == "Not specified"
    assert m.action_items[1].task == "Deploy staging"
    print("  PASS: test_action_items_as_strings")


def test_missing_optional_fields():
    """Test 7: JSON with some fields missing — should use safe defaults."""
    raw = json.dumps({
        "title": "Quick Chat",
        "summary": "Discussed the roadmap."
    })
    m = parse_minutes(raw)
    assert m.title == "Quick Chat"
    assert m.summary == "Discussed the roadmap."
    assert m.date == "Not specified"
    assert m.location == "Not specified"
    assert m.attendees == []
    assert m.discussion_points == []
    assert m.takeaways == []
    assert m.action_items == []
    print("  PASS: test_missing_optional_fields")


if __name__ == "__main__":
    print("Running parse_minutes tests...\n")
    test_valid_json()
    test_literal_newlines_in_markdown()
    test_code_fenced_json()
    test_completely_unparseable()
    test_summary_never_contains_full_json()
    test_action_items_as_strings()
    test_missing_optional_fields()
    print(f"\nAll 7 tests passed.")
