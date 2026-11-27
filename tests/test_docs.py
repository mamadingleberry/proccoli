"""The developer docs stay small indexes that link to one file per topic.

``docs/<Name>.md`` is the index of ``docs/<name>/``: every file in that
folder is linked from it, every relative link in the docs resolves, and an
index stays under a size budget so reading it is cheap.
"""

from __future__ import annotations

import os
import re
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")

# An index above this many bytes is growing history again: move it out.
INDEX_BUDGET = 32 * 1024

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def relative_links(text: str) -> list[str]:
    """Targets of the relative links in ``text``, outside code blocks."""
    out, fence = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        for target in LINK.findall(line):
            if re.match(r"[a-z]+:", target) or target.startswith("#"):
                continue
            out.append(target.split("#", 1)[0])
    return out


def markdown_files(docs: str) -> list[str]:
    found = []
    for dirpath, _dirs, files in os.walk(docs):
        found += [os.path.join(dirpath, f) for f in files if f.endswith(".md")]
    return sorted(found)


def indexes(docs: str) -> dict[str, str]:
    """``{folder: index file}``: ``docs/Plan.md`` indexes ``docs/plan/``."""
    return {name[:-3].lower(): os.path.join(docs, name)
            for name in os.listdir(docs)
            if name.endswith(".md") and os.path.isdir(os.path.join(docs, name[:-3].lower()))}


def broken_links(docs: str) -> list[str]:
    problems = []
    for path in markdown_files(docs):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for target in relative_links(text):
            if not os.path.exists(os.path.join(os.path.dirname(path), target)):
                problems.append(f"{os.path.relpath(path, docs)}: {target}")
    return problems


def unlisted_files(docs: str) -> list[str]:
    problems = []
    for folder, index in indexes(docs).items():
        with open(index, encoding="utf-8") as f:
            linked = {os.path.normpath(os.path.join(docs, t)) for t in relative_links(f.read())}
        for path in markdown_files(os.path.join(docs, folder)):
            if os.path.normpath(path) not in linked:
                problems.append(os.path.relpath(path, docs))
    return problems


class DocsTest(unittest.TestCase):

    def test_every_link_resolves(self):
        self.assertEqual(broken_links(DOCS), [])

    def test_every_topic_file_is_in_its_index(self):
        self.assertEqual(unlisted_files(DOCS), [])

    def test_both_indexes_exist(self):
        self.assertEqual(set(indexes(DOCS)), {"plan", "design"})

    def test_indexes_stay_small(self):
        for index in indexes(DOCS).values():
            self.assertLess(os.path.getsize(index), INDEX_BUDGET, index)


class DocsCheckTest(unittest.TestCase):
    """The checks themselves catch what they're for."""

    def make_docs(self, index: str, files: dict[str, str]) -> str:
        docs = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(docs))
        os.makedirs(os.path.join(docs, "notes"))
        with open(os.path.join(docs, "Notes.md"), "w", encoding="utf-8") as f:
            f.write(index)
        for name, text in files.items():
            with open(os.path.join(docs, "notes", name), "w", encoding="utf-8") as f:
                f.write(text)
        return docs

    def test_a_broken_link_is_found(self):
        docs = self.make_docs("[a](notes/a.md) [gone](notes/gone.md)", {"a.md": "[up](../Notes.md)"})
        self.assertEqual(broken_links(docs), ["Notes.md: notes/gone.md"])

    def test_an_unlisted_file_is_found(self):
        docs = self.make_docs("[a](notes/a.md)", {"a.md": "", "b.md": ""})
        self.assertEqual(unlisted_files(docs), [os.path.join("notes", "b.md")])

    def test_code_blocks_and_web_links_are_not_links(self):
        text = "```\n[x](nowhere.md)\n```\n[w](https://example.org) [s](#top) [f](a.md#part)"
        self.assertEqual(relative_links(text), ["a.md"])


if __name__ == "__main__":
    unittest.main()
