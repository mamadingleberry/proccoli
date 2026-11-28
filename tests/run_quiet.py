"""Run the test suite and print only what's needed: one line when every
test passes, and for each failing test its name and the end of its
traceback. ``make test-verbose`` keeps unittest's full output.

    python3 tests/run_quiet.py [start folder]

The exit status is unittest's: 0 when everything passed.
"""

from __future__ import annotations

import io
import os
import sys
import unittest

TRACEBACK_LINES = 12      # the end of a traceback: where it failed, and why


def short(traceback: str, lines: int = TRACEBACK_LINES) -> str:
    """The last ``lines`` lines of ``traceback``, marked when cut."""
    parts = traceback.rstrip().splitlines()
    if len(parts) <= lines:
        return "\n".join(parts)
    return "\n".join(["  …"] + parts[-lines:])


def report(result: unittest.TestResult) -> str:
    """One summary line, then each failure and error, shortened."""
    out = []
    for kind, items in (("FAIL", result.failures), ("ERROR", result.errors),
                        ("UNEXPECTED SUCCESS", [(t, "") for t in result.unexpectedSuccesses])):
        for test, traceback in items:
            out.append(f"{kind}: {test.id()}")
            if traceback:
                out.append(short(traceback))
    skipped = len(result.skipped)
    status = "OK" if result.wasSuccessful() else (
        f"FAILED (failures={len(result.failures)}, errors={len(result.errors)})")
    out.append(f"Ran {result.testsRun} tests: {status}"
               + (f", {skipped} skipped" if skipped else ""))
    return "\n".join(out)


def run(start: str, stream=None) -> unittest.TestResult:
    """Discover and run the tests under ``start``; unittest's own output
    goes to ``stream`` (thrown away by default)."""
    suite = unittest.defaultTestLoader.discover(start, top_level_dir=start)
    runner = unittest.TextTestRunner(stream=stream or io.StringIO(), verbosity=0)
    return runner.run(suite)


def silenced(fn, fds=(1, 2)):
    """Call ``fn`` with the process's standard output and error going
    nowhere (tests, their child processes, GTK's warnings and C code all
    print there), and give them back afterwards, so only the report reaches
    the terminal. A failing test's traceback is in the report anyway; a
    crash of the whole process still shows in the exit status, and
    ``make test-verbose`` shows everything."""
    for stream in (sys.stdout, sys.stderr):
        stream.flush()
    saved = {fd: os.dup(fd) for fd in fds}
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        for fd in fds:
            os.dup2(devnull, fd)
        return fn()
    finally:
        for stream in (sys.stdout, sys.stderr):
            stream.flush()
        for fd, copy in saved.items():
            os.dup2(copy, fd)
            os.close(copy)
        os.close(devnull)


def main(argv) -> int:
    start = argv[1] if len(argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    result = silenced(lambda: run(start))
    print(report(result))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
