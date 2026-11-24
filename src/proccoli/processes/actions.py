"""Ending, killing, halting and continuing processes, and changing their
priority and CPU affinity.

``ProcessActions`` acts directly where the user may (their own processes),
and passes whatever was denied to the privileged helper, which asks for
authentication once. The helper gets each process's start time with its
PID, read when the user acts, so it won't touch a process that got the PID
while the password prompt was up (DESIGN.md §11, Security).
"""

from __future__ import annotations

import errno
import signal
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Sequence

Report = Callable[[str], None]


class Action(Enum):
    # (signal, verb for messages, helper signal name)
    END = (signal.SIGTERM, "end", "TERM")
    KILL = (signal.SIGKILL, "kill", "KILL")
    HALT = (signal.SIGSTOP, "halt", "STOP")
    CONTINUE = (signal.SIGCONT, "continue", "CONT")

    @property
    def signal(self) -> int:
        return self.value[0]

    @property
    def verb(self) -> str:
        return self.value[1]

    @property
    def helper_name(self) -> str:
        return self.value[2]


PAST = {"end": "Ended", "kill": "Killed", "halt": "Halted", "continue": "Continued"}


@dataclass
class ActionResult:
    succeeded: list[int] = field(default_factory=list)
    failed: list[tuple[int, str]] = field(default_factory=list)   # (pid, reason)
    denied: list[int] = field(default_factory=list)               # EPERM: try the helper

    @property
    def permission_denied(self) -> bool:
        return bool(self.denied)


def send(action: Action, pids: Sequence[int], kill: Callable[[int, int], None]) -> ActionResult:
    result = ActionResult()
    for pid in pids:
        try:
            kill(pid, action.signal)
            result.succeeded.append(pid)
        except ProcessLookupError:
            result.succeeded.append(pid)     # already gone: that's what END wanted
        except OSError as exc:
            result.failed.append((pid, exc.strerror or str(exc)))
            if exc.errno == errno.EPERM:
                result.denied.append(pid)
    return result


def message(action: Action, names: list[str], result: ActionResult) -> str:
    """A toast for the outcome, e.g. "Ended firefox" / "Could not kill 2 processes"."""
    if not result.failed:
        what = names[0] if len(names) == 1 else f"{len(names)} processes"
        return f"{PAST[action.verb]} {what}"
    n = len(result.failed)
    what = "the process" if n == 1 else f"{n} processes"
    return f"Could not {action.verb} {what}: {result.failed[0][1]}"


class ProcessActions:
    def __init__(self, system, helper=None,
                 start_time: Optional[Callable[[int], Optional[int]]] = None) -> None:
        """``start_time(pid)``: when the process started (None: it's gone),
        e.g. ``processes.model.read_start_time`` on the SysRoot."""
        self.system = system
        self.helper = helper            # core.privileged.PrivilegedHelper or None
        self.start_time = start_time

    def _identity(self, pid: int):
        """``(pid, start)`` for the helper, ``pid`` without a lookup, or
        None if the process is already gone."""
        if self.start_time is None:
            return pid
        start = self.start_time(pid)
        return None if start is None else (pid, start)

    def signal(self, action: Action, targets: Sequence[tuple[int, str]],
               report: Report) -> None:
        """Signal ``[(pid, name), ...]``; ``report(message)`` when done."""
        names = list(dict.fromkeys(n for _, n in targets))   # one per app
        result = send(action, [p for p, _ in targets], self.system.kill)
        if not result.denied or self.helper is None:
            report(message(action, names, result))
            return

        targets_for_helper = []
        for pid in result.denied:
            ident = self._identity(pid)
            if ident is None:                     # exited meanwhile: done
                result.succeeded.append(pid)
                result.failed = [f for f in result.failed if f[0] != pid]
            else:
                targets_for_helper.append(ident)
        result.denied = [t[0] if isinstance(t, tuple) else t for t in targets_for_helper]
        if not result.denied:
            report(message(action, names, result))
            return

        def done(helper_result) -> None:
            if helper_result.cancelled:
                report(message(action, names, result))
                return
            retried = set(result.denied)
            final = ActionResult(
                succeeded=result.succeeded + list(helper_result.data.get("ok", [])),
                failed=[f for f in result.failed if f[0] not in retried]
                + [(p, r) for p, r in helper_result.data.get("failed", [])])
            if not helper_result.ok and not helper_result.data:
                final.failed += [(p, helper_result.error) for p in retried]
            report(message(action, names, final))
        self.helper.signal(action.helper_name, targets_for_helper, done)

    def set_priority(self, pid: int, nice: int, report: Report) -> None:
        self._direct_or_helper(lambda: self.system.set_priority(pid, nice),
                               lambda cb: self.helper.renice(pid, nice, cb,
                                                             start=self._start(pid)),
                               "Priority changed", report)

    def set_affinity(self, pid: int, cpus: set[int], report: Report) -> None:
        self._direct_or_helper(lambda: self.system.set_affinity(pid, cpus),
                               lambda cb: self.helper.set_affinity(pid, cpus, cb,
                                                                   start=self._start(pid)),
                               "Processor affinity changed", report)

    def _start(self, pid: int) -> Optional[int]:
        return self.start_time(pid) if self.start_time is not None else None

    def _direct_or_helper(self, direct, via_helper, success: str, report: Report) -> None:
        try:
            direct()
            report(success)
            return
        except PermissionError as exc:
            if self.helper is None:
                report(f"Could not apply: {exc.strerror}")
                return
        except OSError as exc:
            report(f"Could not apply: {exc.strerror or exc}")
            return
        via_helper(lambda r: report(success if r.ok else f"Could not apply: {r.error}"))
