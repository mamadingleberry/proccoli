#!/usr/bin/env python3
"""Turn a release file (docs/plan/releases/vX.Y.Z.md) into the notes for
its GitHub release and annotated tag, so the three always say the same.

The notes are the file's *Release notes* section when it has one (the
text users read on GitHub, kept as published), else its description
paragraph; then its *Features* and *Bugs fixed*, with links made
absolute so they work on GitHub. The archived milestones stay out.

    packaging/release-notes.py docs/plan/releases/v0.6.0.md > notes.md
"""

from __future__ import annotations

import os
import re
import sys

REPO = "https://github.com/mamadingleberry/proccoli/blob/main/"


def sections(text: str) -> dict[str, str]:
    """``{heading: body}`` for the ``## `` sections; ``""`` is the part
    before the first one (title, status line, description)."""
    out, name = {"": []}, ""
    for line in text.splitlines():
        if line.startswith("## "):
            name = line[3:].strip()
            out[name] = []
        else:
            out[name].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def description(head: str) -> str:
    """The paragraphs after the title and the status line."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", head) if p.strip()]
    return "\n\n".join(p for p in paragraphs
                       if not p.startswith("# ") and not p.startswith("*"))


def absolute_links(text: str, folder: str) -> str:
    """Relative links (``../features/x.md``) as links to the repository."""
    def fix(m):
        target = m.group(2)
        if re.match(r"[a-z]+:", target) or target.startswith("#"):
            return m.group(0)
        path = os.path.normpath(os.path.join(folder, target))
        return f"{m.group(1)}{REPO}{path}{m.group(3)}"
    return re.sub(r"(\]\()([^)\s]+)(\))", fix, text)


def notes(text: str, folder: str = "docs/plan/releases") -> str:
    parts = sections(text)
    published = re.sub(r"^As published on GitHub:\s*", "", parts.get("Release notes", ""))
    body = [published or description(parts[""])]
    for heading in ("Features", "Bugs fixed"):
        items = parts.get(heading, "")
        if items.startswith("- "):
            body.append(f"### {heading}\n\n{absolute_links(items, folder)}")
    return "\n\n".join(b for b in body if b) + "\n"


def main(argv) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1].strip(), file=sys.stderr)
        return 2
    path = argv[1]
    with open(path, encoding="utf-8") as f:
        sys.stdout.write(notes(f.read(), os.path.dirname(os.path.relpath(path))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
