import json
import logging
import re
from .schemas import MeetingMinutes, ActionItem

_log = logging.getLogger("minutesai.parser")


def _sanitize_json_string(text: str) -> str:
    """Fix common JSON issues from LLM output.

    The main problem: Llama 3.2 often outputs literal newlines, tabs, and
    other control characters inside JSON string values (especially in the
    'markdown' field). These are invalid JSON — json.loads rejects them with
    'Invalid control character'. This function escapes them so the JSON parses.
    """
    # Strategy: walk through the text tracking whether we're inside a JSON
    # string. Inside strings, replace unescaped control chars with their
    # escape sequences.
    result = []
    in_string = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == '\\' and i + 1 < len(text):
                # Escaped character — keep both
                result.append(ch)
                result.append(text[i + 1])
                i += 2
                continue
            elif ch == '"':
                in_string = False
                result.append(ch)
            elif ch == '\n':
                result.append('\\n')
            elif ch == '\r':
                result.append('\\r')
            elif ch == '\t':
                result.append('\\t')
            elif ord(ch) < 0x20:
                # Other control characters
                result.append(f'\\u{ord(ch):04x}')
            else:
                result.append(ch)
        else:
            if ch == '"':
                in_string = True
            result.append(ch)
        i += 1
    return ''.join(result)


def _extract_json_field(text: str, key: str) -> str | None:
    """Extract a simple string value for a given JSON key using regex.

    This is a fallback for when json.loads fails due to unescaped quotes
    or other issues in complex fields like 'markdown'. It finds the value
    between the key's colon and the next key (or end of object).
    """
    # Match "key": "value" — capture the value
    pattern = rf'"{re.escape(key)}"\s*:\s*"'
    match = re.search(pattern, text)
    if not match:
        return None
    start = match.end()
    # Walk forward to find the closing quote that isn't escaped
    # and that's followed by a comma, closing brace, or another key
    i = start
    depth = 0
    while i < len(text):
        ch = text[i]
        if ch == '\\' and i + 1 < len(text):
            i += 2
            continue
        if ch == '"':
            # Check if what follows looks like JSON structure
            rest = text[i + 1:].lstrip()
            if rest and rest[0] in (',', '}', ']'):
                return text[start:i]
            # Could be an unescaped quote inside the value — continue
        i += 1
    return text[start:]  # unterminated — return what we have


def _extract_json_array(text: str, key: str) -> list[str] | None:
    """Extract an array of strings for a given JSON key using regex."""
    pattern = rf'"{re.escape(key)}"\s*:\s*\['
    match = re.search(pattern, text)
    if not match:
        return None
    start = match.end()
    # Find the matching ]
    depth = 1
    i = start
    in_str = False
    while i < len(text) and depth > 0:
        ch = text[i]
        if in_str:
            if ch == '\\' and i + 1 < len(text):
                i += 2
                continue
            if ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
        i += 1
    if depth != 0:
        return None
    array_text = text[start:i - 1]
    # Extract string items
    items = re.findall(r'"((?:[^"\\]|\\.)*)"', array_text)
    return items


def _extract_action_items(text: str) -> list[dict] | None:
    """Extract action_items array of objects from raw text."""
    pattern = r'"action_items"\s*:\s*\['
    match = re.search(pattern, text)
    if not match:
        return None
    start = match.end()
    # Find matching ]
    depth = 1
    i = start
    in_str = False
    while i < len(text) and depth > 0:
        ch = text[i]
        if in_str:
            if ch == '\\' and i + 1 < len(text):
                i += 2
                continue
            if ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
        i += 1
    if depth != 0:
        return None
    array_text = text[start:i - 1]
    # Find each {...} object
    items = []
    obj_pattern = re.compile(r'\{[^{}]*\}')
    for obj_match in obj_pattern.finditer(array_text):
        obj_str = obj_match.group()
        try:
            obj = json.loads(obj_str)
            items.append(obj)
        except (json.JSONDecodeError, ValueError):
            # Try to extract fields with regex
            task = re.search(r'"task"\s*:\s*"((?:[^"\\]|\\.)*)"', obj_str)
            owner = re.search(r'"owner"\s*:\s*"((?:[^"\\]|\\.)*)"', obj_str)
            due = re.search(r'"due_date"\s*:\s*"((?:[^"\\]|\\.)*)"', obj_str)
            items.append({
                "task": task.group(1) if task else "",
                "owner": owner.group(1) if owner else "Not specified",
                "due_date": due.group(1) if due else "Not specified",
            })
    return items if items else None


def _fallback_regex_parse(text: str) -> dict:
    """Last-resort parser: extract fields individually using regex.

    When json.loads fails even after sanitization (e.g., because the markdown
    field contains unescaped double quotes), extract each field separately.
    """
    _log.info("parse_minutes: Attempting regex-based field extraction")
    data = {}

    for key in ("title", "date", "location", "summary"):
        val = _extract_json_field(text, key)
        if val is not None:
            # Unescape basic JSON escapes
            val = val.replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t")
            val = val.replace('\\"', '"').replace("\\\\", "\\")
            data[key] = val

    for key in ("attendees", "discussion_points", "takeaways"):
        val = _extract_json_array(text, key)
        if val is not None:
            data[key] = val

    action_items = _extract_action_items(text)
    if action_items is not None:
        data["action_items"] = action_items

    # Markdown is tricky — it often has unescaped quotes and newlines.
    # Extract it but accept that it may be incomplete.
    md = _extract_json_field(text, "markdown")
    if md is not None:
        md = md.replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t")
        md = md.replace('\\"', '"').replace("\\\\", "\\")
        data["markdown"] = md

    if data:
        _log.info("parse_minutes: Regex extraction found keys: %s", list(data.keys()))

    return data


def parse_minutes(raw: str) -> MeetingMinutes:
    """Parse the LLM response into a structured MeetingMinutes object.

    Handles:
    - Markdown code fences wrapping the JSON.
    - Literal newlines inside JSON string values (common with Llama 3.2).
    - Unescaped quotes inside string values (regex fallback).
    - Partial / malformed JSON (falls back gracefully).
    - action_items as dicts or plain strings.
    - Missing fields default to safe values; nothing is invented.
    """
    text = raw.strip()

    # Strip common markdown fences if the model ignores the JSON-only instruction.
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)

    start, end = text.find("{"), text.rfind("}")
    data = {}
    if start >= 0 and end > start:
        json_text = text[start : end + 1]
        # Pass 1: try parsing as-is (fast path for valid JSON)
        try:
            data = json.loads(json_text)
            _log.info("parse_minutes: JSON parsed on first try")
        except (json.JSONDecodeError, TypeError, ValueError) as e1:
            _log.warning("parse_minutes: First json.loads failed: %s", e1)
            # Pass 2: sanitize literal control chars and retry
            try:
                sanitized = _sanitize_json_string(json_text)
                data = json.loads(sanitized)
                _log.info("parse_minutes: JSON parsed after sanitizing control chars")
            except (json.JSONDecodeError, TypeError, ValueError) as e2:
                _log.warning("parse_minutes: Second json.loads failed: %s", e2)
                # Pass 3: regex-based field extraction
                data = _fallback_regex_parse(json_text)
    else:
        _log.warning("parse_minutes: No JSON object braces found in output")

    # --- Normalize action_items: accept list of dicts or list of strings ---
    raw_actions = data.get("action_items") or []
    actions = []
    for item in raw_actions:
        if isinstance(item, dict):
            actions.append(ActionItem(
                task=str(item.get("task", "")),
                owner=str(item.get("owner", "Not specified")),
                due_date=str(item.get("due_date", "Not specified")),
            ))
        else:
            actions.append(ActionItem(task=str(item)))

    # --- Build fields ---
    summary = str(data.get("summary") or "")
    markdown = str(data.get("markdown") or "")

    # If parsing produced nothing useful, put the raw text in markdown as a fallback.
    if not data:
        summary = "The model generated a report, but it could not be parsed into structured fields."
        markdown = raw

    return MeetingMinutes(
        title=str(data.get("title") or "Meeting Minutes"),
        date=str(data.get("date") or "Not specified"),
        location=str(data.get("location") or "Not specified"),
        attendees=[str(x) for x in (data.get("attendees") or [])],
        summary=summary,
        discussion_points=[str(x) for x in (data.get("discussion_points") or [])],
        takeaways=[str(x) for x in (data.get("takeaways") or [])],
        action_items=actions,
        markdown=markdown,
    )
