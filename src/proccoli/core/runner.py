"""Runs a child process that streams JSON records, on a worker thread.

Generalised from intel_gpu_top_gui's ``Sampler``: any command, optionally
run through ``pkexec``, or a Python generator (for demo mode). Signals are
always emitted on the GLib main loop.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from typing import Callable, Iterator, Optional, Sequence

from gi.repository import GLib, GObject

from .jsonstream import JsonStreamParser


class StreamReader(GObject.Object):
    __gsignals__ = {
        "record": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        # (return code, stderr text, number of records received). Not emitted
        # after stop().
        "exited": (GObject.SignalFlags.RUN_FIRST, None, (int, str, int)),
    }

    def __init__(self) -> None:
        super().__init__()
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._generation = 0
        self._stopping = False

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, argv: Sequence[str], elevate: bool = False) -> None:
        """Run ``argv`` (through pkexec when ``elevate``)."""
        gen = self._restart()
        cmd = ["pkexec", *argv] if elevate else list(argv)
        try:
            self._proc = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True)  # Ctrl+C in a terminal mustn't hit it twice
        except OSError as exc:
            GLib.idle_add(self._finish, gen, 127, str(exc), 0)
            return
        self._thread = threading.Thread(target=self._run_process, args=(gen, self._proc),
                                        daemon=True)
        self._thread.start()

    def start_generator(self, make: Callable[[], Iterator[dict]], interval_s: float) -> None:
        """Emit records from a generator every ``interval_s`` (demo mode)."""
        gen = self._restart()
        self._thread = threading.Thread(target=self._run_generator,
                                        args=(gen, make, interval_s), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping = True
        self._generation += 1
        proc, self._proc = self._proc, None
        if proc is None:
            return
        # The reader thread notices the generation change after its next read
        # and closes the pipe, so the child dies of SIGPIPE on its next write.
        # That matters under pkexec, where we may not signal a root process.
        try:
            proc.send_signal(signal.SIGTERM)
        except (PermissionError, ProcessLookupError, OSError):
            pass

    # -- worker threads ---------------------------------------------------------

    def _restart(self) -> int:
        self.stop()
        self._generation += 1
        self._stopping = False
        return self._generation

    def _deliver(self, gen: int, record: dict) -> bool:
        if gen == self._generation:
            self.emit("record", record)
        return False

    def _finish(self, gen: int, rc: int, err: str, count: int) -> bool:
        if gen == self._generation and not self._stopping:
            self.emit("exited", rc, err, count)
        return False

    def _run_process(self, gen: int, proc: subprocess.Popen) -> None:
        parser = JsonStreamParser()
        count = 0
        err_chunks: list[bytes] = []

        def read_stderr() -> None:
            try:
                for chunk in iter(lambda: proc.stderr.read1(4096), b""):
                    err_chunks.append(chunk)
            except (ValueError, OSError):
                pass
            finally:
                proc.stderr.close()

        err_thread = threading.Thread(target=read_stderr, daemon=True)
        err_thread.start()
        fd = proc.stdout.fileno()
        try:
            while True:
                data = os.read(fd, 65536)
                if not data or gen != self._generation:
                    break
                for record in parser.feed(data.decode("utf-8", "replace")):
                    count += 1
                    GLib.idle_add(self._deliver, gen, record)
        except (ValueError, OSError):
            pass
        proc.stdout.close()
        if gen != self._generation:
            # Stopped: don't wait on a process we may not be able to kill.
            threading.Thread(target=proc.wait, daemon=True).start()
            return
        try:
            rc = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            rc = -1
        err_thread.join(timeout=1)
        GLib.idle_add(self._finish, gen, rc,
                      b"".join(err_chunks).decode("utf-8", "replace"), count)

    def _run_generator(self, gen: int, make, interval_s: float) -> None:
        for record in make():
            if gen != self._generation:
                return
            GLib.idle_add(self._deliver, gen, record)
            time.sleep(interval_s)
