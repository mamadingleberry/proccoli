"""Which programs Proccoli may start as root (Security).

pkexec runs whatever path it's given as root once the user types their
password. If that file, or any directory above it, can be changed by the
user's own account, then any program running as the user could replace it
and turn the user's next password prompt into root for itself. So Proccoli
only elevates programs that only root can change: the file and every
directory up to ``/`` owned by root and not writable by group or others.
That rules out a source checkout in the home folder and ``~/.local/bin``
on ``PATH``.

Pure apart from ``os.stat`` and ``os.path.realpath``, which tests replace.
"""

from __future__ import annotations

import os
import stat as stat_module
from typing import Callable, Iterable, Optional

# Where system packages and ``sudo make install`` put programs. PATH is
# never used for programs run as root.
SYSTEM_BIN_DIRS = ("/usr/bin", "/usr/sbin", "/bin", "/sbin",
                   "/usr/local/bin", "/usr/local/sbin")

StatFn = Callable[[str], os.stat_result]


def root_only(st: os.stat_result) -> bool:
    """Owned by root and not writable by group or others."""
    return st.st_uid == 0 and not st.st_mode & (stat_module.S_IWGRP | stat_module.S_IWOTH)


def is_trusted_path(path: str, stat: StatFn = os.stat,
                    realpath: Callable[[str], str] = os.path.realpath) -> bool:
    """Whether only root can change ``path`` (a regular, executable file)
    and every directory above it, symlinks resolved."""
    try:
        real = realpath(path)
        st = stat(real)
        if not stat_module.S_ISREG(st.st_mode) or not st.st_mode & 0o111:
            return False
        if not root_only(st):
            return False
        directory = os.path.dirname(real)
        while True:
            if not root_only(stat(directory)):
                return False
            parent = os.path.dirname(directory)
            if parent == directory:
                return True
            directory = parent
    except OSError:
        return False


def find_trusted(name: str, trusted: Callable[[str], bool],
                 dirs: Iterable[str] = SYSTEM_BIN_DIRS) -> Optional[str]:
    """The first ``dirs/name`` that ``trusted`` accepts, or None."""
    for d in dirs:
        path = os.path.join(d, name)
        if trusted(path):
            return path
    return None
