"""The privileged helper: argument validation (everything is refused before
anything runs), and the operations themselves on a child we own (no root
needed for those)."""

import contextlib
import io
import json
import os
import signal
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
import helpers  # noqa: E402,F401

from proccoli.helper import proccoli_helper as h  # noqa: E402

HELPER = h.__file__


def run(*argv):
    """main(argv) -> (exit status, parsed JSON stdout or text, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = h.main(list(argv))
    text = out.getvalue()
    try:
        data = json.loads(text) if text.strip() else None
    except ValueError:
        data = text
    return rc, data, err.getvalue()


def child():
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    return p


class ValidationTest(unittest.TestCase):
    BAD = [
        (),                                   # no subcommand
        ("rm", "-rf", "/"),                   # unknown subcommand
        ("signal",),                          # nothing to signal
        ("signal", "HUP", "1234"),            # signal not allowed
        ("signal", "TERM"),                   # no pid
        ("signal", "TERM", "abc"),
        ("signal", "TERM", "-5"),
        ("signal", "TERM", "1"),              # init
        ("signal", "TERM", "0"),
        ("signal", "TERM", "1234;reboot"),
        ("signal", "TERM", "\u00b2"),            # not an ASCII digit
        ("signal", "TERM", "\u0661\u0662\u0663"),   # Arabic-Indic digits
        ("signal", "TERM", "1234@"),            # empty start time
        ("signal", "TERM", "1234@x"),
        ("signal", "TERM", "@99"),
        ("signal", "TERM", "1@5"),              # still never init
        ("renice", "1234@-3", "5"),
        ("renice", "1234"),
        ("renice", "1234", "-21"),
        ("renice", "1234", "20"),
        ("renice", "1234", "x"),
        ("renice", "1", "5"),
        ("affinity", "1234"),
        ("affinity", "1234", ""),
        ("affinity", "1234", "99999"),
        ("affinity", "1234", "-1"),
        ("affinity", "1234", "a,b"),
        ("dmidecode", "-t", "1"),             # no arguments accepted
        ("processes", "--interval", "10"),    # too fast
        ("processes", "--interval", "999999"),
        ("processes", "--interval"),
        ("processes", "--bogus"),
        ("gpu-top",),                         # Milestone 42
        ("gpu-top", "1000"),
        ("gpu-top", "50", "card1"),           # too fast
        ("gpu-top", "1000", "card1;reboot"),
        ("gpu-top", "1000", "renderD128"),
        ("gpu-top", "1000", "card"),
        ("gpu-top", "1000", "../card1"),
        ("gpu-top", "1000", "card1", "-o"),   # no extra arguments (no -o files)
    ]

    def test_bad_arguments_exit_2_without_acting(self):
        with mock.patch.object(h.os, "kill") as kill, \
             mock.patch.object(h.os, "setpriority") as renice, \
             mock.patch.object(h.os, "sched_setaffinity") as affinity, \
             mock.patch.object(h.subprocess, "run") as run_, \
             mock.patch.object(h.subprocess, "Popen") as popen:
            for argv in self.BAD:
                rc, _, err = run(*argv)
                self.assertEqual(rc, 2, argv)
                self.assertTrue(err, argv)
            for m in (kill, renice, affinity, run_, popen):
                m.assert_not_called()

    def test_refuses_its_own_pid(self):
        rc, _, _ = run("signal", "KILL", str(os.getpid()))
        self.assertEqual(rc, 2)


class OperationsTest(unittest.TestCase):
    def setUp(self):
        self.p = child()
        self.addCleanup(self.p.wait)
        self.addCleanup(lambda: self.p.poll() is None and self.p.kill())

    def test_signal_stop_continue_term(self):
        for sig in ("STOP", "CONT"):
            rc, data, _ = run("signal", sig, str(self.p.pid))
            self.assertEqual((rc, data), (0, {"ok": [self.p.pid], "failed": []}))
        rc, data, _ = run("signal", "TERM", str(self.p.pid))
        self.assertEqual(rc, 0)
        self.assertEqual(self.p.wait(5), -signal.SIGTERM)

    def test_gone_process_counts_as_done(self):
        self.p.kill()
        self.p.wait()
        rc, data, _ = run("signal", "TERM", str(self.p.pid))
        self.assertEqual((rc, data["ok"]), (0, [self.p.pid]))

    def test_permission_failure_is_reported(self):
        with mock.patch.object(h.os, "kill", side_effect=PermissionError(1, "Operation not permitted")):
            rc, data, _ = run("signal", "TERM", str(self.p.pid))
        self.assertEqual(rc, 1)
        self.assertEqual(data["failed"], [[self.p.pid, "Operation not permitted"]])

    def test_renice_and_affinity(self):
        rc, data, _ = run("renice", str(self.p.pid), "9")
        self.assertEqual(rc, 0)
        self.assertEqual(os.getpriority(os.PRIO_PROCESS, self.p.pid), 9)
        cpu = min(os.sched_getaffinity(self.p.pid))
        rc, _, _ = run("affinity", str(self.p.pid), f"{cpu},")
        self.assertEqual(rc, 0)
        self.assertEqual(os.sched_getaffinity(self.p.pid), {cpu})

    def test_renice_failure(self):
        rc, data, _ = run("renice", str(self.p.pid), "-20")   # raising needs root
        if os.geteuid() != 0:
            self.assertEqual(rc, 1)
            self.assertTrue(data["failed"])


class IdentityTest(unittest.TestCase):
    """PID@STARTTIME: only the process the user picked (Milestone 40)."""

    def setUp(self):
        self.p = child()
        self.addCleanup(self.p.wait)
        self.addCleanup(lambda: self.p.poll() is None and self.p.kill())
        self.start = h.start_time(self.p.pid)

    def test_start_time_reads_proc(self):
        self.assertIsInstance(self.start, int)
        self.assertIsNone(h.start_time(2 ** 22 + 7))         # no such process

    def test_matching_start_time_is_signalled(self):
        rc, data, _ = run("signal", "TERM", f"{self.p.pid}@{self.start}")
        self.assertEqual((rc, data["ok"]), (0, [self.p.pid]))
        self.assertEqual(self.p.wait(5), -signal.SIGTERM)

    def test_reused_pid_is_left_alone(self):
        rc, data, _ = run("signal", "KILL", f"{self.p.pid}@{self.start + 1}")
        self.assertEqual((rc, data["ok"]), (0, [self.p.pid]))   # "that one is gone"
        self.assertIsNone(self.p.poll())                         # but nothing was hit

    def test_without_pidfds_it_still_checks(self):
        with mock.patch.object(h.os, "pidfd_open", side_effect=OSError(38, "ENOSYS")):
            run("signal", "KILL", f"{self.p.pid}@{self.start + 1}")
            self.assertIsNone(self.p.poll())
            run("signal", "TERM", f"{self.p.pid}@{self.start}")
        self.assertEqual(self.p.wait(5), -signal.SIGTERM)

    def test_renice_and_affinity_check_identity(self):
        rc, data, _ = run("renice", f"{self.p.pid}@{self.start + 1}", "7")
        self.assertEqual(rc, 1)
        self.assertEqual(data["failed"], [[self.p.pid, "The process has exited"]])
        self.assertNotEqual(os.getpriority(os.PRIO_PROCESS, self.p.pid), 7)
        rc, _, _ = run("renice", f"{self.p.pid}@{self.start}", "7")
        self.assertEqual(rc, 0)
        cpu = min(os.sched_getaffinity(self.p.pid))
        rc, _, _ = run("affinity", f"{self.p.pid}@{self.start + 1}", str(cpu))
        self.assertEqual(rc, 1)

    def test_runs_isolated(self):
        # -I: no script directory on sys.path, no PYTHON* variables, no user
        # site-packages, so nothing next to the helper can be imported as root.
        with open(HELPER, encoding="utf-8") as fh:
            self.assertEqual(fh.readline().strip(), "#!/usr/bin/python3 -I")


# A stand-in for intel_gpu_top: prints a record every 50 ms, ignores SIGPIPE
# (as the real one does) and optionally SIGTERM; writes its PID to a file.
FAKE_GPU_TOP = """#!{python}
import os, signal, sys, time
signal.signal(signal.SIGPIPE, signal.SIG_IGN)
if {ignore_term}:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
open({pidfile!r}, "w").write(str(os.getpid()))
sys.stdout.write("[\\n")
while True:
    try:
        sys.stdout.write('{{"period": {{}}}},\\n'); sys.stdout.flush()
    except OSError:
        pass
    time.sleep(0.05)
"""


class GpuTopTest(unittest.TestCase):
    """Milestone 42: the helper stops intel_gpu_top when the app stops reading."""

    def fake(self, ignore_term=False):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        exe = os.path.join(tmp.name, "intel_gpu_top")
        pidfile = os.path.join(tmp.name, "pid")
        with open(exe, "w") as fh:
            fh.write(FAKE_GPU_TOP.format(python=sys.executable, ignore_term=ignore_term,
                                         pidfile=pidfile))
        os.chmod(exe, 0o755)
        return exe, pidfile

    def run_until_reader_leaves(self, exe, reads_before_leaving=3):
        """main(gpu-top) with a stdout that breaks like a closed pipe."""
        written = []

        class Out:
            def write(self, data):
                if len(written) >= reads_before_leaving:
                    raise BrokenPipeError(32, "Broken pipe")
                written.append(data)

            def flush(self):
                pass

        class Stdout:
            buffer = Out()
        with mock.patch.object(h, "INTEL_GPU_TOP_PATHS", (exe,)), \
             mock.patch.object(h.sys, "stdout", Stdout()):
            rc = h.main(["gpu-top", "1000", "card1"])
        return rc, written

    def assert_gone(self, pidfile):
        with open(pidfile) as fh:
            pid = int(fh.read())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)                               # reaped: no such process

    def test_child_is_stopped_when_the_app_stops_reading(self):
        exe, pidfile = self.fake()
        rc, written = self.run_until_reader_leaves(exe)
        self.assertEqual(rc, 0)
        self.assertTrue(written[0].startswith(b"["))
        self.assertTrue(any(b'"period"' in w for w in written))
        self.assert_gone(pidfile)

    def test_a_child_ignoring_sigterm_is_killed(self):
        exe, pidfile = self.fake(ignore_term=True)
        self.run_until_reader_leaves(exe, reads_before_leaving=1)
        self.assert_gone(pidfile)

    def test_fixed_arguments(self):
        with mock.patch.object(h, "INTEL_GPU_TOP_PATHS", ("/x/intel_gpu_top",)), \
             mock.patch.object(h.os, "access", return_value=True), \
             mock.patch.object(h.subprocess, "Popen") as popen, \
             mock.patch.object(h, "relay"):
            popen.return_value.wait.return_value = 0
            h.main(["gpu-top", "500", "card2"])
        self.assertEqual(popen.call_args[0][0],
                         ["/x/intel_gpu_top", "-J", "-s", "500", "-d", "drm:/dev/dri/card2"])

    def test_missing_intel_gpu_top(self):
        with mock.patch.object(h, "INTEL_GPU_TOP_PATHS", ("/nonexistent",)):
            rc, _, err = run("gpu-top", "1000", "card1")
        self.assertEqual(rc, 1)
        self.assertIn("not installed", err)


class DmidecodeTest(unittest.TestCase):
    def test_slow_dmidecode_is_an_error_not_a_crash(self):
        with mock.patch.object(h.os, "access", return_value=True), \
             mock.patch.object(h.subprocess, "run",
                               side_effect=h.subprocess.TimeoutExpired("dmidecode", 20)):
            rc, data, _ = run("dmidecode")
        self.assertEqual((rc, data), (1, {"error": "dmidecode took too long"}))

    def test_missing_dmidecode(self):
        with mock.patch.object(h, "DMIDECODE_PATHS", ("/nonexistent/dmidecode",)):
            rc, data, _ = run("dmidecode")
        self.assertEqual((rc, data), (1, {"error": "dmidecode is not installed"}))

    def test_runs_type_17_only(self):
        fake = mock.Mock(returncode=0, stdout="Memory Device\n", stderr="")
        with mock.patch.object(h, "DMIDECODE_PATHS", (sys.executable,)), \
             mock.patch.object(h.subprocess, "run", return_value=fake) as run_:
            rc, data, _ = run("dmidecode")
        self.assertEqual(run_.call_args.args[0], [sys.executable, "-t", "17"])
        self.assertEqual((rc, data["output"]), (0, "Memory Device\n"))


class ProcessesStreamTest(unittest.TestCase):
    def test_once_is_a_parseable_stream_with_our_counters(self):
        from proccoli.core.jsonstream import JsonStreamParser
        rc, text, _ = run("processes", "--once")
        self.assertEqual(rc, 0)
        [record] = JsonStreamParser().feed(text)
        self.assertIn(str(os.getpid()), record["io"])
        read, write = record["io"][str(os.getpid())]
        self.assertGreaterEqual(read, 0)

    def test_script_runs_standalone(self):
        """Installed, it runs as its own program: no Proccoli imports."""
        r = subprocess.run([sys.executable, "-I", HELPER, "processes", "--once"],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run([sys.executable, "-I", HELPER], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("proccoli-helper signal", r.stderr)

    def test_no_proccoli_imports(self):
        with open(HELPER) as fh:
            text = fh.read()
        self.assertNotIn("import proccoli", text)
        self.assertNotIn("from proccoli", text)
        self.assertNotIn("shell=True", text)


if __name__ == "__main__":
    unittest.main()
