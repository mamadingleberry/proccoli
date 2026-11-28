"""Release notes come from the release files."""

from __future__ import annotations

import glob
import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "release_notes", os.path.join(ROOT, "packaging", "release-notes.py"))
rn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rn)

FILE = """# Proccoli 9.9.0

*Released 2030-01-01* as tag `v9.9.0`.

What changed, in users' words.

## Features

- [Something new](../features/feature-01-something.md)

## Bugs fixed

- [Something wrong](../bugs/bug-02-wrong.md)

## Milestones (archive)

- [An old step](../archive/milestones/old.md)
"""


class NotesTest(unittest.TestCase):
    def test_description_then_features_and_bugs(self):
        text = rn.notes(FILE)
        self.assertTrue(text.startswith("What changed, in users' words."))
        self.assertIn("### Features", text)
        self.assertIn("### Bugs fixed", text)
        self.assertNotIn("Milestones", text)
        self.assertNotIn("Released 2030", text)

    def test_links_are_absolute(self):
        text = rn.notes(FILE)
        self.assertIn(rn.REPO + "docs/plan/features/feature-01-something.md", text)
        self.assertNotIn("](../", text)

    def test_published_notes_win_over_the_description(self):
        text = rn.notes(FILE.replace("## Features", "## Release notes\n\nAs published.\n\n## Features"))
        self.assertTrue(text.startswith("As published."))
        self.assertNotIn("in users' words", text)

    def test_a_release_without_features_has_no_empty_heading(self):
        text = rn.notes(FILE.replace("- [Something new](../features/feature-01-something.md)",
                                     "None tracked as features yet."))
        self.assertNotIn("### Features", text)

    def test_every_release_file_renders_with_working_links(self):
        for path in glob.glob(os.path.join(ROOT, "docs", "plan", "releases", "v*.md")):
            with self.subTest(path=os.path.basename(path)):
                with open(path, encoding="utf-8") as f:
                    text = rn.notes(f.read())
                self.assertTrue(text.strip())
                for target in rn.re.findall(r"\]\((" + rn.re.escape(rn.REPO) + r"[^)]+)\)", text):
                    local = os.path.join(ROOT, target[len(rn.REPO):])
                    self.assertTrue(os.path.exists(local), target)


if __name__ == "__main__":
    unittest.main()
