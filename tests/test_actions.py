import os
import signal
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from helpers import FakeSystem  # noqa: E402

from proccoli.core.privileged import HelperResult  # noqa: E402
from proccoli.processes.actions import Action, ProcessActions, message, send  # noqa: E402


class FakeHelper:
    def __init__(self, result=None):
        self.result = result or HelperResult(True, {"ok": [], "failed": []})
        self.calls = []

    def signal(self, name, pids, callback):
        self.calls.append(("signal", name, list(pids)))
        callback(self.result)

    def renice(self, pid, nice, callback, start=None):
        self.calls.append(("renice", pid, nice) + ((start,) if start is not None else ()))
        callback(self.result)

    def set_affinity(self, pid, cpus, callback, start=None):
        self.calls.append(("affinity", pid, cpus) + ((start,) if start is not None else ()))
        callback(self.result)


class IdentityTest(unittest.TestCase):
    """Milestone 40: the helper gets PID and start time, read when the user acts."""

    def setUp(self):
        self.system = FakeSystem()
        self.system.denied_pids = {6, 7}
        self.messages = []
        self.starts = {6: 600, 7: 700}

    def test_denied_processes_go_with_their_start_time(self):
        helper = FakeHelper(HelperResult(True, {"ok": [6, 7], "failed": []}))
        ProcessActions(self.system, helper, self.starts.get).signal(
            Action.KILL, [(6, "a"), (7, "b")], self.messages.append)
        self.assertEqual(helper.calls, [("signal", "KILL", [(6, 600), (7, 700)])])

    def test_process_gone_before_the_prompt_is_not_sent(self):
        del self.starts[7]
        helper = FakeHelper(HelperResult(True, {"ok": [6], "failed": []}))
        ProcessActions(self.system, helper, self.starts.get).signal(
            Action.KILL, [(6, "a"), (7, "b")], self.messages.append)
        self.assertEqual(helper.calls, [("signal", "KILL", [(6, 600)])])
        self.assertEqual(self.messages, ["Killed 2 processes"])

    def test_all_gone_means_no_prompt(self):
        helper = FakeHelper()
        ProcessActions(self.system, helper, lambda pid: None).signal(
            Action.END, [(6, "a")], self.messages.append)
        self.assertEqual(helper.calls, [])
        self.assertEqual(self.messages, ["Ended a"])

    def test_priority_and_affinity_carry_the_start_time(self):
        self.system.denied_pids = set()
        helper = FakeHelper()
        actions = ProcessActions(self.system, helper, self.starts.get)
        self.system.set_priority = lambda pid, nice: (_ for _ in ()).throw(
            PermissionError(1, "Operation not permitted"))
        self.system.set_affinity = self.system.set_priority
        actions.set_priority(6, -5, self.messages.append)
        actions.set_affinity(6, {0}, self.messages.append)
        self.assertEqual(helper.calls, [("renice", 6, -5, 600), ("affinity", 6, {0}, 600)])

    def test_read_start_time_from_proc(self):
        from helpers import FakeRoot
        from proccoli.processes.model import read_start_time
        # Fields after the name: state ppid pgrp session tty tpgid flags,
        # then minflt..cstime (8), priority nice threads itrealvalue, starttime.
        root = FakeRoot(self, {"/proc/42/stat": "42 (s h) S 1 42 42 0 -1 4194560 "
                               + "0 " * 8 + "20 0 1 0 98765 1000 100"}).sysroot
        self.assertEqual(read_start_time(root, 42), 98765)
        self.assertIsNone(read_start_time(root, 43))


class SignalTest(unittest.TestCase):
    def setUp(self):
        self.system = FakeSystem()
        self.messages = []

    def actions(self, helper=None):
        return ProcessActions(self.system, helper)

    def test_own_processes_need_no_helper(self):
        helper = FakeHelper()
        self.actions(helper).signal(Action.END, [(5, "a"), (6, "b")], self.messages.append)
        self.assertEqual(self.system.killed, [(5, signal.SIGTERM), (6, signal.SIGTERM)])
        self.assertEqual(helper.calls, [])
        self.assertEqual(self.messages, ["Ended 2 processes"])

    def test_denied_pids_go_to_the_helper_only(self):
        self.system.denied_pids = {6}
        helper = FakeHelper(HelperResult(True, {"ok": [6], "failed": []}))
        self.actions(helper).signal(Action.KILL, [(5, "a"), (6, "b")], self.messages.append)
        self.assertEqual(helper.calls, [("signal", "KILL", [6])])
        self.assertEqual(self.messages, ["Killed 2 processes"])

    def test_helper_failure_is_reported(self):
        self.system.denied_pids = {6}
        helper = FakeHelper(HelperResult(False, {"ok": [], "failed": [[6, "No such process"]]},
                                         "No such process"))
        self.actions(helper).signal(Action.HALT, [(6, "b")], self.messages.append)
        self.assertEqual(self.messages, ["Could not halt the process: No such process"])

    def test_helper_error_without_data(self):
        self.system.denied_pids = {6}
        helper = FakeHelper(HelperResult(False, {}, "exit status 1"))
        self.actions(helper).signal(Action.END, [(6, "b")], self.messages.append)
        self.assertEqual(self.messages, ["Could not end the process: exit status 1"])

    def test_cancelled_prompt_reports_the_original_failure(self):
        self.system.denied_pids = {6}
        helper = FakeHelper(HelperResult(False, error="cancelled", cancelled=True))
        self.actions(helper).signal(Action.END, [(6, "sshd")], self.messages.append)
        self.assertEqual(self.messages, ["Could not end the process: Operation not permitted"])

    def test_without_helper(self):
        self.system.denied_pids = {6}
        self.actions().signal(Action.CONTINUE, [(6, "x")], self.messages.append)
        self.assertIn("Operation not permitted", self.messages[0])

    def test_one_app_many_processes_reads_as_the_app(self):
        self.actions().signal(Action.END, [(5, "Firefox"), (6, "Firefox"), (7, "Firefox")],
                              self.messages.append)
        self.assertEqual(self.messages, ["Ended Firefox"])

    def test_send_and_message_edge_cases(self):
        r = send(Action.END, [], kill=lambda *_: None)
        self.assertEqual((r.succeeded, r.failed), ([], []))
        self.assertEqual(message(Action.CONTINUE, ["x"], r), "Continued x")
        self.assertEqual({a.helper_name for a in Action}, {"TERM", "KILL", "STOP", "CONT"})


class PriorityAffinityTest(unittest.TestCase):
    def setUp(self):
        self.system = FakeSystem()
        self.messages = []

    def test_direct(self):
        a = ProcessActions(self.system, FakeHelper())
        a.set_priority(5, 4, self.messages.append)
        a.set_affinity(5, {0, 1}, self.messages.append)
        self.assertEqual((self.system.priorities, self.system.affinities), ({5: 4}, {5: {0, 1}}))
        self.assertEqual(self.messages, ["Priority changed", "Processor affinity changed"])

    def test_permission_denied_uses_helper(self):
        self.system.denied_pids = {5}
        helper = FakeHelper()
        a = ProcessActions(self.system, helper)
        a.set_priority(5, -10, self.messages.append)
        a.set_affinity(5, {2}, self.messages.append)
        self.assertEqual(helper.calls, [("renice", 5, -10), ("affinity", 5, {2})])
        self.assertEqual(self.messages, ["Priority changed", "Processor affinity changed"])

    def test_permission_denied_without_helper(self):
        self.system.denied_pids = {5}
        ProcessActions(self.system).set_priority(5, -10, self.messages.append)
        self.assertEqual(self.messages, ["Could not apply: Operation not permitted"])

    def test_other_errors_are_reported(self):
        class Gone(FakeSystem):
            def set_priority(self, pid, nice):
                raise ProcessLookupError(3, "No such process")
        helper = FakeHelper()
        ProcessActions(Gone(), helper).set_priority(5, 1, self.messages.append)
        self.assertEqual(self.messages, ["Could not apply: No such process"])
        self.assertEqual(helper.calls, [])

    def test_helper_failure(self):
        self.system.denied_pids = {5}
        helper = FakeHelper(HelperResult(False, error="Operation not permitted"))
        ProcessActions(self.system, helper).set_affinity(5, {1}, self.messages.append)
        self.assertEqual(self.messages, ["Could not apply: Operation not permitted"])


if __name__ == "__main__":
    unittest.main()
