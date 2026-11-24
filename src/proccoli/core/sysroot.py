"""Access to /proc and /sys through an exchangeable root directory.

Every read of kernel interfaces goes through a ``SysRoot``. The app uses
``SysRoot("/")``; tests use a fixture tree such as
``SysRoot("tests/fixtures/alderlake-laptop")``. Paths are always given as
absolute kernel paths ("/proc/stat") and resolved inside the root.

Reads never raise for the usual reasons a kernel file can't be read: it's
missing, a device went away mid-read, or it's permission-protected. They
return ``None`` (or an empty list) instead, and callers treat that as "no
data".
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

PathLike = Union[str, "os.PathLike[str]"]


class SysRoot:
    def __init__(self, root: PathLike = "/") -> None:
        self.root = Path(root)
        # Reads happen thousands of times per second: resolve with plain
        # strings, not pathlib.
        self._prefix = str(self.root).rstrip("/")

    def __repr__(self) -> str:
        return f"SysRoot({str(self.root)!r})"

    def path(self, path: PathLike) -> Path:
        """Translate an absolute kernel path into a path inside the root."""
        rel = str(path).lstrip("/")
        return self.root / rel if rel else self.root

    def _p(self, path: PathLike) -> str:
        p = str(path)
        return self._prefix + (p if p.startswith("/") else "/" + p)

    def read_text(self, path: PathLike) -> Optional[str]:
        try:
            with open(self._p(path), encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except (OSError, ValueError):
            return None

    def read_line(self, path: PathLike) -> Optional[str]:
        """First line, stripped: the common shape of sysfs attributes."""
        text = self.read_text(path)
        if text is None:
            return None
        return text.split("\n", 1)[0].strip()

    def read_int(self, path: PathLike, base: int = 10) -> Optional[int]:
        """Integer attribute. ``base=0`` accepts prefixes such as 0x8086."""
        line = self.read_line(path)
        if not line:
            return None
        try:
            return int(line, base)
        except ValueError:
            return None

    def listdir(self, path: PathLike) -> list[str]:
        try:
            return sorted(os.listdir(self._p(path)))
        except OSError:
            return []

    def exists(self, path: PathLike) -> bool:
        return os.path.lexists(self._p(path))

    def is_dir(self, path: PathLike) -> bool:
        return os.path.isdir(self._p(path))

    def readlink(self, path: PathLike) -> Optional[str]:
        """Target of a symlink as stored (sysfs links are relative)."""
        try:
            return os.readlink(self._p(path))
        except OSError:
            return None

    def link_name(self, path: PathLike) -> Optional[str]:
        """Last component of a symlink's target, e.g. the driver name from
        ``/sys/class/net/eth0/device/driver``."""
        target = self.readlink(path)
        return os.path.basename(target.rstrip("/")) if target else None
