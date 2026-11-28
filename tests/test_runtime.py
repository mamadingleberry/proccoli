"""The diagnostics both programs start: log file, watchdog, exception hook."""

from __future__ import annotations

import logging
import unittest

from proccoli.core.runtime import Runtime, console_logging


class Recorder:
    def __init__(self, *args):
        self.args = args
        self.calls = []

    def start(self):
        self.calls.append("start")

    def stop(self):
        self.calls.append("stop")

    def shutdown(self):
        self.calls.append("shutdown")


class FakeSys:
    def __init__(self):
        self.seen = []
        self.excepthook = lambda *a: self.seen.append(a[0])


class RuntimeTest(unittest.TestCase):
    def make(self):
        self.logs, self.dogs, self.sys = [], [], FakeSys()

        def file_log(settings, path):
            self.logs.append(Recorder(settings, path))
            return self.logs[-1]

        def watchdog():
            self.dogs.append(Recorder())
            return self.dogs[-1]
        return Runtime("settings", "/tmp/x.log", file_log, watchdog, self.sys)

    def test_start_opens_the_log_and_starts_the_watchdog(self):
        runtime = self.make().start()
        self.assertEqual(self.logs[0].args[0], "settings")
        self.assertEqual(str(self.logs[0].args[1]), "/tmp/x.log")
        self.assertEqual(self.dogs[0].calls, ["start"])
        self.assertIs(runtime.file_log, self.logs[0])

    def test_an_uncaught_exception_is_logged_then_passed_on(self):
        self.make().start()
        try:
            raise ValueError("boom")
        except ValueError as exc:
            info = (type(exc), exc, exc.__traceback__)
        with self.assertLogs("proccoli.core.runtime", "CRITICAL") as logs:
            self.sys.excepthook(*info)
        self.assertIn("uncaught exception", logs.output[0])
        self.assertEqual(self.sys.seen, [ValueError])

    def test_ctrl_c_is_not_logged_as_a_crash(self):
        self.make().start()
        logger = logging.getLogger("proccoli.core.runtime")
        with self.assertNoLogs(logger, "CRITICAL"):
            self.sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
        self.assertEqual(self.sys.seen, [KeyboardInterrupt])

    def test_shutdown_undoes_everything_once(self):
        runtime = self.make()
        original = self.sys.excepthook
        runtime.start()
        runtime.shutdown()
        runtime.shutdown()
        self.assertEqual(self.dogs[0].calls, ["start", "stop"])
        self.assertEqual(self.logs[0].calls, ["shutdown"])
        self.assertIs(self.sys.excepthook, original)


class ConsoleLoggingTest(unittest.TestCase):
    def test_the_level_and_format(self):
        got = {}
        console_logging(logging.INFO, configure=lambda **kw: got.update(kw))
        self.assertEqual(got["level"], logging.INFO)
        self.assertIn("%(name)s", got["format"])


if __name__ == "__main__":
    unittest.main()
