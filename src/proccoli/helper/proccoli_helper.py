#!/usr/bin/python3 -I
"""Proccoli's privileged helper. Runs as root through pkexec, so it is
deliberately small: no Proccoli imports, no shell, every argument validated.

    proccoli-helper signal TERM|KILL|STOP|CONT TARGET...
    proccoli-helper renice TARGET NICE                 (-20..19)
    proccoli-helper affinity TARGET CPU[,CPU...]
    proccoli-helper dmidecode                          (memory devices, type 17)
    proccoli-helper processes [--interval MS] [--once] (I/O counters of every process)
    proccoli-helper gpu-top MS cardN                   (intel_gpu_top -J, relayed)

A TARGET is PID or PID@STARTTIME. With STARTTIME (field 22 of
/proc/PID/stat), the helper acts only if PID is still that process, so a
PID the kernel reused for another process while the password prompt was up
is left alone (DESIGN.md §11, Security). Signals go through a pidfd, so the
check and the signal refer to the same process.

Results are JSON on stdout. Exit status: 0 success, 1 the operation failed
(details in the JSON), 2 invalid arguments.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time

# What the app may send (it reads this line from the installed file, so an
# older installed helper isn't sent arguments it would refuse):
# 1 bare PIDs, 2 PID@STARTTIME targets (Milestone 40), 3 gpu-top (M42).
PROTOCOL = 3

SIGNALS = {"TERM": signal.SIGTERM, "KILL": signal.SIGKILL,
           "STOP": signal.SIGSTOP, "CONT": signal.SIGCONT}
DMIDECODE_PATHS = ("/usr/sbin/dmidecode", "/sbin/dmidecode", "/usr/bin/dmidecode")
MIN_INTERVAL_MS, MAX_INTERVAL_MS = 250, 10_000
INTEL_GPU_TOP_PATHS = ("/usr/bin/intel_gpu_top", "/usr/local/bin/intel_gpu_top")
GPU_TOP_MIN_MS = 100


class UsageError(Exception):
    pass


def _digits(text: str) -> bool:
    # ASCII only: str.isdigit() also accepts "²" and other scripts' digits.
    return text.isascii() and text.isdigit()


def parse_pid(text: str) -> int:
    if not _digits(text):
        raise UsageError(f"not a process ID: {text!r}")
    pid = int(text)
    # PID 1 (init) and the helper's own process are never targets.
    if pid <= 1 or pid == os.getpid():
        raise UsageError(f"refusing process ID {pid}")
    return pid


def parse_target(text: str) -> tuple[int, int | None]:
    """``PID`` or ``PID@STARTTIME`` -> (pid, start time or None)."""
    pid_text, sep, start_text = text.partition("@")
    if sep and not _digits(start_text):
        raise UsageError(f"not a start time: {start_text!r}")
    return parse_pid(pid_text), (int(start_text) if sep else None)


def start_time(pid: int) -> int | None:
    """Field 22 of /proc/PID/stat (clock ticks after boot), None if gone."""
    try:
        with open(f"/proc/{pid}/stat") as fh:
            stat = fh.read()
        return int(stat[stat.rindex(")") + 2:].split()[19])
    except (OSError, ValueError, IndexError):
        return None


class Replaced(Exception):
    """The PID now belongs to another process (or none)."""


def check_identity(pid: int, start: int | None) -> None:
    if start is not None and start_time(pid) != start:
        raise Replaced()


def send_signal(pid: int, start: int | None, sig: int) -> None:
    """Signal the process ``pid`` that started at ``start``: through a
    pidfd when the kernel has them, so a PID reused between the check and
    the signal can't be hit."""
    if start is None:
        os.kill(pid, sig)
        return
    try:
        fd = os.pidfd_open(pid)
    except (AttributeError, OSError) as exc:      # no pidfds: check, then kill
        if isinstance(exc, ProcessLookupError):
            raise
        check_identity(pid, start)
        os.kill(pid, sig)
        return
    try:
        check_identity(pid, start)                 # fd pins the process checked
        signal.pidfd_send_signal(fd, sig)
    finally:
        os.close(fd)


def parse_int(text: str, low: int, high: int, what: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise UsageError(f"not a number: {text!r}") from None
    if not low <= value <= high:
        raise UsageError(f"{what} must be between {low} and {high}")
    return value


def cmd_signal(args: list[str]) -> int:
    if len(args) < 2 or args[0] not in SIGNALS:
        raise UsageError("usage: signal TERM|KILL|STOP|CONT TARGET...")
    sig = SIGNALS[args[0]]
    targets = [parse_target(a) for a in args[1:]]
    ok, failed = [], []
    for pid, start in targets:
        try:
            send_signal(pid, start, sig)
            ok.append(pid)
        except (ProcessLookupError, Replaced):
            ok.append(pid)                       # that process is already gone
        except OSError as exc:
            failed.append([pid, exc.strerror or str(exc)])
    print(json.dumps({"ok": ok, "failed": failed}))
    return 1 if failed else 0


def cmd_renice(args: list[str]) -> int:
    if len(args) != 2:
        raise UsageError("usage: renice TARGET NICE")
    pid, start = parse_target(args[0])
    nice = parse_int(args[1], -20, 19, "niceness")
    try:
        check_identity(pid, start)
        os.setpriority(os.PRIO_PROCESS, pid, nice)
    except Replaced:
        print(json.dumps({"ok": [], "failed": [[pid, "The process has exited"]]}))
        return 1
    except OSError as exc:
        print(json.dumps({"ok": [], "failed": [[pid, exc.strerror or str(exc)]]}))
        return 1
    print(json.dumps({"ok": [pid], "failed": []}))
    return 0


def cmd_affinity(args: list[str]) -> int:
    if len(args) != 2:
        raise UsageError("usage: affinity TARGET CPU[,CPU...]")
    pid, start = parse_target(args[0])
    count = os.cpu_count() or 1
    cpus = {parse_int(c, 0, count - 1, "CPU") for c in args[1].split(",") if c != ""}
    if not cpus:
        raise UsageError("at least one CPU is needed")
    try:
        check_identity(pid, start)
        os.sched_setaffinity(pid, cpus)
    except Replaced:
        print(json.dumps({"ok": [], "failed": [[pid, "The process has exited"]]}))
        return 1
    except OSError as exc:
        print(json.dumps({"ok": [], "failed": [[pid, exc.strerror or str(exc)]]}))
        return 1
    print(json.dumps({"ok": [pid], "failed": []}))
    return 0


def cmd_dmidecode(args: list[str]) -> int:
    if args:
        raise UsageError("usage: dmidecode")
    exe = next((p for p in DMIDECODE_PATHS if os.access(p, os.X_OK)), None)
    if exe is None:
        print(json.dumps({"error": "dmidecode is not installed"}))
        return 1
    try:
        result = subprocess.run([exe, "-t", "17"], capture_output=True, text=True, timeout=20)
    except subprocess.TimeoutExpired:
        print(json.dumps({"error": "dmidecode took too long"}))
        return 1
    print(json.dumps({"output": result.stdout, "error": result.stderr.strip()}))
    return 0 if result.returncode == 0 else 1


def io_counters() -> dict[str, list[int]]:
    out = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/io") as fh:
                fields = dict(line.split(": ", 1) for line in fh.read().splitlines())
            out[entry] = [int(fields["read_bytes"]), int(fields["write_bytes"])]
        except (OSError, KeyError, ValueError):
            continue
    return out


def cmd_processes(args: list[str]) -> int:
    interval, once = 1000, False
    it = iter(args)
    for a in it:
        if a == "--once":
            once = True
        elif a == "--interval":
            interval = parse_int(next(it, ""), MIN_INTERVAL_MS, MAX_INTERVAL_MS, "interval")
        else:
            raise UsageError("usage: processes [--interval MS] [--once]")
    # The stream is a JSON array that's never closed, like intel_gpu_top -J.
    sys.stdout.write("[\n")
    while True:
        sys.stdout.write(json.dumps({"io": io_counters()}) + ",\n")
        sys.stdout.flush()
        if once:
            return 0
        time.sleep(interval / 1000)


def relay(child, read, write) -> None:
    """Copy the child's output to ours until either side ends; then stop
    the child. intel_gpu_top ignores SIGPIPE, so without this it would run
    as root forever once Proccoli stops reading (Milestone 42)."""
    try:
        while True:
            data = read()
            if not data:
                break
            write(data)
    except (BrokenPipeError, OSError):
        pass
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


def cmd_gpu_top(args: list[str]) -> int:
    if len(args) != 2:
        raise UsageError("usage: gpu-top MS cardN")
    interval = parse_int(args[0], GPU_TOP_MIN_MS, MAX_INTERVAL_MS, "interval")
    card = args[1]
    if not (card.startswith("card") and _digits(card[4:])):
        raise UsageError(f"not a DRM card: {card!r}")
    exe = next((p for p in INTEL_GPU_TOP_PATHS if os.access(p, os.X_OK)), None)
    if exe is None:
        print("proccoli-helper: intel_gpu_top is not installed", file=sys.stderr)
        return 1
    # Fixed arguments only: no -o (it would write files as root).
    child = subprocess.Popen([exe, "-J", "-s", str(interval), "-d", f"drm:/dev/dri/{card}"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE)
    out = sys.stdout.buffer

    def write(data: bytes) -> None:
        out.write(data)
        out.flush()
    relay(child, lambda: os.read(child.stdout.fileno(), 65536), write)
    rc = child.wait()
    return rc if rc >= 0 else 0      # stopped by us: not an error


COMMANDS = {"signal": cmd_signal, "renice": cmd_renice, "affinity": cmd_affinity,
            "dmidecode": cmd_dmidecode, "processes": cmd_processes, "gpu-top": cmd_gpu_top}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in COMMANDS:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        return COMMANDS[argv[0]](argv[1:])
    except UsageError as exc:
        print(f"proccoli-helper: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:       # the app stopped reading the stream
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
