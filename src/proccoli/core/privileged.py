"""Client for the privileged helper (``proccoli-helper``, run through pkexec).

Every call is asynchronous, because pkexec shows a password prompt.
Callbacks receive a ``HelperResult``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Callable, Mapping, Optional, Sequence

from .trust import is_trusted_path

log = logging.getLogger(__name__)

# Where packaging/install.sh puts the helper (PREFIX=/usr or /usr/local).
INSTALLED_HELPERS = ("/usr/libexec/proccoli/proccoli-helper",
                     "/usr/local/libexec/proccoli/proccoli-helper")
SOURCE_HELPER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "helper", "proccoli_helper.py")

# pkexec's own exit codes.
PKEXEC_DISMISSED = 126     # the authentication dialog was dismissed or refused
PKEXEC_NOT_AUTHORIZED = 127


@dataclass
class HelperResult:
    ok: bool
    data: dict = field(default_factory=dict)
    error: str = ""
    cancelled: bool = False     # the user dismissed the password prompt


# Developers running from a source checkout can opt in to the checkout's
# helper (DESIGN.md §11, Security): it runs as root although the user's own
# account can change it.
DEV_HELPER_ENV = "PROCCOLI_DEV_HELPER"


def helper_argv(installed: Sequence[str] = INSTALLED_HELPERS,
                trusted: Callable[[str], bool] = is_trusted_path,
                env: Mapping[str, str] = os.environ,
                python: str = sys.executable) -> Optional[list[str]]:
    """How to start the helper as root, or None (no privileged actions).

    The installed program (matched by the polkit policy), but only if only
    root can change it (``core.trust``). A source checkout's script is
    used only when ``PROCCOLI_DEV_HELPER=1`` is set, through an isolated
    Python (``-I``)."""
    for path in installed:
        if os.path.exists(path):
            if trusted(path):
                return [path]
            log.warning("not using %s as root: it can be changed without "
                        "administrator rights", path)
    if env.get(DEV_HELPER_ENV) == "1" and trusted(python):
        log.warning("%s=1: running the source checkout's helper as root", DEV_HELPER_ENV)
        return [python, "-I", SOURCE_HELPER]
    log.info("no installed helper: actions that need administrator rights are off "
             "(install Proccoli, or set %s=1 in a source checkout)", DEV_HELPER_ENV)
    return None


PROTOCOL_IDENTITY = 2      # the helper understands PID@STARTTIME
PROTOCOL_GPU_TOP = 3       # ... and gpu-top (Milestone 42)


def helper_protocol(argv: Optional[Sequence[str]],
                    read: Callable[[str], str] = lambda p: open(p, encoding="utf-8").read()
                    ) -> int:
    """The ``PROTOCOL`` the helper file declares (1 if it declares none,
    i.e. a helper installed before Milestone 40). Read from the file
    itself, so it needs no administrator rights."""
    if not argv:
        return 1
    try:
        match = re.search(r"^PROTOCOL = (\d+)", read(argv[-1]), re.MULTILINE)
    except (OSError, UnicodeDecodeError):
        return 1
    return int(match.group(1)) if match else 1


def target_token(pid: int, start: Optional[int]) -> str:
    """``PID@STARTTIME`` (or ``PID``), the helper's process identity."""
    return f"{pid}@{start}" if start is not None else str(pid)


class PrivilegedHelper:
    def __init__(self, system, argv: Sequence[str],
                 protocol: int = PROTOCOL_IDENTITY) -> None:
        """``protocol``: what the helper understands (``helper_protocol``)."""
        self.system = system
        self.argv = list(argv)
        self.protocol = protocol
        if protocol < PROTOCOL_IDENTITY:
            log.warning("the installed helper is older than this Proccoli: it acts on "
                        "process IDs alone; reinstall Proccoli to update it")

    def _token(self, pid: int, start: Optional[int]) -> str:
        return target_token(pid, start if self.protocol >= PROTOCOL_IDENTITY else None)

    def command(self, *args: str) -> list[str]:
        return ["pkexec", *self.argv, *args]

    def _run(self, args: Sequence[str], callback: Callable[[HelperResult], None]) -> None:
        def done(rc: int, out: str, err: str) -> None:
            if rc in (PKEXEC_DISMISSED, PKEXEC_NOT_AUTHORIZED) and not out.strip():
                callback(HelperResult(False, error="Authentication was cancelled or refused",
                                      cancelled=True))
                return
            try:
                data = json.loads(out) if out.strip() else {}
            except ValueError:
                data = {}
            failed = data.get("failed") or []
            # Most specific first: the helper's own error, a per-process
            # reason, pkexec's stderr, and only then the bare exit status.
            error = (data.get("error") or (failed[0][1] if failed else "")
                     or err.strip() or ("" if rc == 0 else f"exit status {rc}"))
            callback(HelperResult(rc == 0, data, error))
        self.system.run_async(self.command(*args), done)

    # -- operations ---------------------------------------------------------------

    def signal(self, signal_name: str, targets: Sequence,
               callback: Callable[[HelperResult], None]) -> None:
        """``targets``: PIDs or ``(pid, start time)`` pairs."""
        tokens = [self._token(*t) if isinstance(t, tuple) else str(t) for t in targets]
        self._run(["signal", signal_name, *tokens], callback)

    def renice(self, pid: int, nice: int, callback, start: Optional[int] = None) -> None:
        self._run(["renice", self._token(pid, start), str(nice)], callback)

    def set_affinity(self, pid: int, cpus: set[int], callback,
                     start: Optional[int] = None) -> None:
        self._run(["affinity", self._token(pid, start), ",".join(map(str, sorted(cpus)))],
                  callback)

    def gpu_top_argv(self, interval_ms: int, card: str) -> Optional[list[str]]:
        """argv (for ``StreamReader.start(..., elevate=True)``) running
        intel_gpu_top through the helper, which stops it when Proccoli stops
        reading; None if the installed helper predates ``gpu-top``."""
        if self.protocol < PROTOCOL_GPU_TOP:
            return None
        return [*self.argv, "gpu-top", str(interval_ms), card]

    def dmidecode(self, callback) -> None:
        self._run(["dmidecode"], callback)

    def io_stream(self, interval_ms: int):
        """A started StreamReader emitting ``{"io": {pid: [read, write]}}``."""
        reader = self.system.stream_reader()
        reader.start([*self.argv, "processes", "--interval", str(interval_ms)], elevate=True)
        return reader


def optional_helper(system, argv: Optional[Sequence[str]],
                    protocol: int = PROTOCOL_IDENTITY) -> Optional[PrivilegedHelper]:
    """No helper without pkexec (then privileged actions are unavailable)."""
    if argv is None or system.which("pkexec") is None:
        return None
    return PrivilegedHelper(system, argv, protocol)
