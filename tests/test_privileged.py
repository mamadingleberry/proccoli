import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from helpers import FakeSystem  # noqa: E402

from proccoli.core.privileged import (  # noqa: E402
    DEV_HELPER_ENV, PROTOCOL_GPU_TOP, SOURCE_HELPER, PrivilegedHelper, helper_argv,
    helper_protocol,
    optional_helper, target_token)


class HelperClientTest(unittest.TestCase):
    def setUp(self):
        self.system = FakeSystem()
        self.helper = PrivilegedHelper(self.system, ["/usr/libexec/proccoli/proccoli-helper"])
        self.results = []

    def call(self, method, *args, rc=0, out="", err=""):
        self.system.run_results.append((rc, out, err))
        getattr(self.helper, method)(*args, self.results.append)
        return self.results[-1]

    def test_commands(self):
        self.call("signal", "TERM", [5, 6], out='{"ok": [5, 6], "failed": []}')
        self.call("renice", 5, -3, out='{"ok": [5], "failed": []}')
        self.call("set_affinity", 5, {3, 1}, out='{"ok": [5], "failed": []}')
        self.call("dmidecode", out='{"output": "x", "error": ""}')
        helper = "/usr/libexec/proccoli/proccoli-helper"
        self.assertEqual(self.system.runs, [
            ["pkexec", helper, "signal", "TERM", "5", "6"],
            ["pkexec", helper, "renice", "5", "-3"],
            ["pkexec", helper, "affinity", "5", "1,3"],
            ["pkexec", helper, "dmidecode"]])

    def test_success(self):
        r = self.call("signal", "TERM", [5], out='{"ok": [5], "failed": []}')
        self.assertTrue(r.ok)
        self.assertEqual(r.data["ok"], [5])
        self.assertEqual(r.error, "")

    def test_partial_failure_reports_the_reason(self):
        r = self.call("signal", "KILL", [5], rc=1,
                      out=json.dumps({"ok": [], "failed": [[5, "No such process"]]}))
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "No such process")

    def test_cancelled_prompt(self):
        for rc in (126, 127):
            r = self.call("dmidecode", rc=rc, err="Error executing command as another user")
            self.assertTrue(r.cancelled)
            self.assertFalse(r.ok)

    def test_garbage_output(self):
        r = self.call("dmidecode", rc=3, out="not json", err="boom")
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "boom")
        r = self.call("dmidecode", rc=5)
        self.assertEqual(r.error, "exit status 5")

    def test_io_stream(self):
        reader = self.helper.io_stream(500)
        self.assertEqual(reader.started, (["/usr/libexec/proccoli/proccoli-helper",
                                           "processes", "--interval", "500"], True))


class LocatingTest(unittest.TestCase):
    """only a helper that only root can change runs as root."""

    def argv(self, installed, trusted=(), env=None):
        return helper_argv(installed, trusted=lambda p: p in trusted, env=env or {},
                           python="/usr/bin/python3")

    def test_installed_helper_wins(self):
        self.assertEqual(self.argv([sys.executable], {sys.executable}), [sys.executable])

    def test_untrusted_installed_helper_is_refused(self):
        with self.assertLogs("proccoli.core.privileged", "WARNING"):
            self.assertIsNone(self.argv([sys.executable], set()))

    def test_source_checkout_needs_an_explicit_opt_in(self):
        with self.assertLogs("proccoli.core.privileged", "INFO"):
            self.assertIsNone(self.argv(["/nonexistent/proccoli-helper"], {"/usr/bin/python3"}))
        with self.assertLogs("proccoli.core.privileged", "WARNING"):
            argv = self.argv(["/nonexistent/proccoli-helper"], {"/usr/bin/python3"},
                             env={DEV_HELPER_ENV: "1"})
        self.assertEqual(argv, ["/usr/bin/python3", "-I", SOURCE_HELPER])   # isolated
        self.assertTrue(os.path.isfile(SOURCE_HELPER))

    def test_opt_in_still_needs_a_trusted_python(self):
        with self.assertLogs("proccoli.core.privileged", "INFO"):
            self.assertIsNone(self.argv(["/nonexistent"], set(), env={DEV_HELPER_ENV: "1"}))

    def test_target_tokens(self):
        self.assertEqual(target_token(42, 1234), "42@1234")
        self.assertEqual(target_token(42, None), "42")

    def test_identities_reach_the_command_line(self):
        system = FakeSystem()
        helper = PrivilegedHelper(system, ["/usr/libexec/proccoli/proccoli-helper"])
        system.run_results += [(0, "{}", "")] * 3
        helper.signal("KILL", [(5, 900), 6], lambda r: None)
        helper.renice(5, 3, lambda r: None, start=900)
        helper.set_affinity(5, {0}, lambda r: None, start=900)
        self.assertEqual([r[2:] for r in system.runs],
                         [["signal", "KILL", "5@900", "6"], ["renice", "5@900", "3"],
                          ["affinity", "5@900", "0"]])

    def test_protocol_is_read_from_the_helper_file(self):
        self.assertEqual(helper_protocol([SOURCE_HELPER]), PROTOCOL_GPU_TOP)   # this version
        old = "#!/usr/bin/python3\nSIGNALS = {}\n"                    # an older helper
        self.assertEqual(helper_protocol(["/usr/libexec/x"], read=lambda p: old), 1)
        self.assertEqual(helper_protocol(None), 1)
        self.assertEqual(helper_protocol(["/nonexistent"]), 1)

    def test_an_older_helper_gets_bare_pids(self):
        system = FakeSystem()
        with self.assertLogs("proccoli.core.privileged", "WARNING"):
            helper = PrivilegedHelper(system, ["/usr/libexec/proccoli/proccoli-helper"], 1)
        system.run_results += [(0, "{}", "")] * 2
        helper.signal("KILL", [(5, 900)], lambda r: None)
        helper.renice(5, 3, lambda r: None, start=900)
        self.assertEqual([r[2:] for r in system.runs],
                         [["signal", "KILL", "5"], ["renice", "5", "3"]])

    def test_gpu_top_needs_protocol_3(self):
        argv = ["/usr/libexec/proccoli/proccoli-helper"]
        self.assertEqual(PrivilegedHelper(FakeSystem(), argv, 3).gpu_top_argv(500, "card1"),
                         [*argv, "gpu-top", "500", "card1"])
        with self.assertLogs("proccoli.core.privileged", "WARNING"):
            old = PrivilegedHelper(FakeSystem(), argv, 1)
        self.assertIsNone(old.gpu_top_argv(500, "card1"))
        self.assertIsNone(PrivilegedHelper(FakeSystem(), argv, 2).gpu_top_argv(500, "card1"))

    def test_no_helper_without_pkexec(self):
        self.assertIsNone(optional_helper(FakeSystem(programs={}), ["x"]))
        self.assertIsNone(optional_helper(FakeSystem(programs={"pkexec": "/usr/bin/pkexec"}),
                                          None))
        self.assertIsNotNone(optional_helper(
            FakeSystem(programs={"pkexec": "/usr/bin/pkexec"}), ["x"]))

if __name__ == "__main__":
    unittest.main()
