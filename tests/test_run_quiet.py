"""The quiet test runner: one line when all pass, failures in short."""

from __future__ import annotations

import os
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import run_quiet  # noqa: E402


class QuietRunnerTest(unittest.TestCase):
    def suite(self, body: str) -> str:
        folder = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(folder))
        with open(os.path.join(folder, "test_sample.py"), "w") as f:
            f.write("import unittest\n\n" + textwrap.dedent(body))
        sys.modules.pop("test_sample", None)
        self.addCleanup(sys.modules.pop, "test_sample", None)
        return folder

    def test_all_passing_is_one_line(self):
        folder = self.suite("""
            class T(unittest.TestCase):
                def test_a(self): pass
                def test_b(self): pass
                @unittest.skip("no display")
                def test_c(self): pass
            """)
        text = run_quiet.report(run_quiet.run(folder))
        self.assertEqual(text, "Ran 3 tests: OK, 1 skipped")

    def test_a_failure_names_the_test_and_why(self):
        folder = self.suite("""
            class T(unittest.TestCase):
                def test_ok(self): pass
                def test_wrong(self): self.assertEqual(1, 2)
                def test_broken(self): raise RuntimeError("boom")
            """)
        result = run_quiet.run(folder)
        text = run_quiet.report(result)
        self.assertIn("FAIL: test_sample.T.test_wrong", text)
        self.assertIn("AssertionError: 1 != 2", text)
        self.assertIn("ERROR: test_sample.T.test_broken", text)
        self.assertIn("RuntimeError: boom", text)
        self.assertNotIn("test_ok", text)
        self.assertTrue(text.endswith("Ran 3 tests: FAILED (failures=1, errors=1)"))

    def test_long_tracebacks_keep_their_end(self):
        tb = "\n".join(f"line {i}" for i in range(40))
        cut = run_quiet.short(tb, 5)
        self.assertEqual(cut.splitlines(), ["  …", "line 35", "line 36", "line 37", "line 38",
                                            "line 39"])
        self.assertEqual(run_quiet.short("one\ntwo"), "one\ntwo")


    def test_silenced_gives_the_output_back(self):
        before = [os.fstat(fd) for fd in (1, 2)]
        got = run_quiet.silenced(lambda: os.write(1, b"") == 0 and "done")
        self.assertEqual(got, "done")
        after = [os.fstat(fd) for fd in (1, 2)]
        self.assertEqual([(s.st_dev, s.st_ino) for s in before],
                         [(s.st_dev, s.st_ino) for s in after])

    def test_silenced_gives_it_back_after_an_error(self):
        before = os.fstat(1)
        with self.assertRaises(ValueError):
            run_quiet.silenced(lambda: (_ for _ in ()).throw(ValueError("x")))
        self.assertEqual((os.fstat(1).st_dev, os.fstat(1).st_ino), (before.st_dev, before.st_ino))


if __name__ == "__main__":
    unittest.main()
