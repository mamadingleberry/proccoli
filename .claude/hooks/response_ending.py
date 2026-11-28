#!/usr/bin/env python3
"""Stop hook: every response ends with a summary, a test report and the
next steps (the software-design skill, "The end of every response").

Reads the Stop event's JSON on stdin. If the last assistant message lacks
any of the three parts, it blocks the stop once and says which are
missing; when Claude has already been sent back once
(``stop_hook_active``), it lets the stop through so it can never loop.
"""

from __future__ import annotations

import json
import re
import sys

PARTS = {
    "Summary": re.compile(r"^\s*(#+\s*|\*\*)?(\d\.\s*)?summary\b", re.I | re.M),
    "Test report": re.compile(r"^\s*(#+\s*|\*\*)?(\d\.\s*)?tests?\s*(report|results)?\b", re.I | re.M),
    "Next": re.compile(r"^\s*(#+\s*|\*\*)?(\d\.\s*)?next\b", re.I | re.M),
}


def missing_parts(text: str) -> list[str]:
    """The parts of the ending that ``text`` doesn't have, in order."""
    return [name for name, pattern in PARTS.items() if not pattern.search(text or "")]


def last_assistant_text(transcript_path: str) -> str:
    """The text of the last assistant message in a JSONL transcript."""
    text = ""
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                message = entry.get("message") or {}
                if entry.get("type") != "assistant" and message.get("role") != "assistant":
                    continue
                content = message.get("content")
                if isinstance(content, str):
                    parts = [content]
                else:
                    parts = [c.get("text", "") for c in content or []
                             if isinstance(c, dict) and c.get("type") == "text"]
                if any(p.strip() for p in parts):
                    text = "\n".join(parts)
    except OSError:
        return ""
    return text


def decide(event: dict) -> dict | None:
    """The hook's answer for a Stop ``event``: a block, or None to allow."""
    if event.get("stop_hook_active"):
        return None
    text = event.get("last_assistant_message")
    if not isinstance(text, str):
        text = last_assistant_text(event.get("transcript_path", ""))
    if not text:
        return None
    missing = missing_parts(text)
    if not missing:
        return None
    return {"decision": "block",
            "reason": ("This response is missing the required ending: "
                       + ", ".join(missing) + ". End it as the software-design skill's "
                       "'The end of every response' says: 1. Summary (with the paths of "
                       "docs written), 2. Test report, 3. Next (the open bugs and "
                       "features to choose from, and an offer to update docs or skills).")}


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    answer = decide(event)
    if answer:
        print(json.dumps(answer))
    return 0


if __name__ == "__main__":
    sys.exit(main())
