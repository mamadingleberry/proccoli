"""The real System, exercised only in ways that are safe on any machine."""

import os
import signal
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import helpers  # noqa: E402,F401 (sets sys.path)

from gi.repository import GLib  # noqa: E402

from proccoli.core.system import System  # noqa: E402


def pump(until, timeout=5.0):
    ctx = GLib.MainContext.default()
    end = time.monotonic() + timeout
    while time.monotonic() < end and not until():
        while ctx.pending():
            ctx.iteration(False)
        time.sleep(0.01)
    return until()


class SystemTest(unittest.TestCase):
    def setUp(self):
        self.s = System()

    def test_which(self):
        self.assertTrue(self.s.which("sh"))
        self.assertIsNone(self.s.which("no-such-program-proccoli"))

    def test_identity(self):
        self.assertEqual(self.s.geteuid(), os.geteuid())
        self.assertEqual(self.s.user_name(0), "root")
        self.assertEqual(self.s.user_name(None), "")
        self.assertEqual(self.s.user_name(4_000_000), "4000000")   # unknown uid
        self.assertGreater(self.s.clk_tck(), 0)
        self.assertEqual(self.s.machine(), os.uname().machine)
        self.assertFalse(self.s.has_file_capabilities("/nonexistent"))

    def test_user_names_are_cached(self):
        self.s.user_name(0)
        self.assertIn(0, self.s._user_names)

    def test_priority_and_affinity_of_own_child(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        self.s.set_priority(child.pid, 7)                  # lowering is always allowed
        self.assertEqual(self.s.get_priority(child.pid), 7)
        cpus = self.s.get_affinity(child.pid)
        one = {min(cpus)}
        self.s.set_affinity(child.pid, one)
        self.assertEqual(self.s.get_affinity(child.pid), one)
        self.s.kill(child.pid, signal.SIGTERM)
        self.assertEqual(child.wait(5), -signal.SIGTERM)

    def test_run_async(self):
        results = []
        self.s.run_async([sys.executable, "-c",
                          "import sys; print('out'); sys.stderr.write('err'); sys.exit(4)"],
                         lambda rc, out, err: results.append((rc, out, err)))
        self.assertTrue(pump(lambda: results))
        self.assertEqual(results, [(4, "out\n", "err")])

    def test_run_async_missing_program(self):
        results = []
        self.s.run_async(["/nonexistent/program"], lambda *r: results.append(r))
        self.assertTrue(pump(lambda: results))
        self.assertEqual(results[0][0], 127)

    def test_stream_reader_factory(self):
        from proccoli.core.runner import StreamReader
        self.assertIsInstance(self.s.stream_reader(), StreamReader)
        self.assertIsNot(self.s.stream_reader(), self.s.stream_reader())

    def test_desktop_app(self):
        self.assertIsNone(self.s.desktop_app("no.such.App.proccoli"))


if __name__ == "__main__":
    unittest.main()
