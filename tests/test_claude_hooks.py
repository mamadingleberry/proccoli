"""The Stop hook that checks every response ends with its three parts."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "response_ending", os.path.join(ROOT, ".claude", "hooks", "response_ending.py"))
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

COMPLETE = "Done.\n\n**1. Summary**\nx\n\n**2. Test report**\nok\n\n**3. Next**\npick one"


class ResponseEndingTest(unittest.TestCase):

    def test_a_complete_ending_passes(self):
        self.assertEqual(hook.missing_parts(COMPLETE), [])
        self.assertEqual(hook.missing_parts("## Summary\n## Tests\n## Next steps"), [])

    def test_each_missing_part_is_named(self):
        self.assertEqual(hook.missing_parts("**Summary**\nx"), ["Test report", "Next"])
        self.assertEqual(hook.missing_parts(""), ["Summary", "Test report", "Next"])

    def test_a_word_inside_a_sentence_is_not_a_heading(self):
        self.assertEqual(hook.missing_parts("A summary of the next test."),
                         ["Summary", "Test report", "Next"])

    def test_it_blocks_once_and_says_what_is_missing(self):
        answer = hook.decide({"last_assistant_message": "All done."})
        self.assertEqual(answer["decision"], "block")
        self.assertIn("Summary, Test report, Next", answer["reason"])

    def test_it_never_blocks_twice(self):
        self.assertIsNone(hook.decide({"stop_hook_active": True,
                                       "last_assistant_message": "All done."}))

    def test_it_reads_the_transcript_when_the_message_is_not_given(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(folder))
        path = os.path.join(folder, "t.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}}) + "\n")
            f.write(json.dumps({"type": "assistant", "message": {
                "role": "assistant", "content": [{"type": "text", "text": COMPLETE}]}}) + "\n")
            f.write(json.dumps({"type": "assistant", "message": {
                "role": "assistant", "content": [{"type": "tool_use", "name": "Bash"}]}}) + "\n")
        self.assertEqual(hook.last_assistant_text(path), COMPLETE)
        self.assertIsNone(hook.decide({"transcript_path": path}))

    def test_nothing_to_check_is_allowed(self):
        self.assertIsNone(hook.decide({"transcript_path": "/nonexistent"}))


if __name__ == "__main__":
    unittest.main()
