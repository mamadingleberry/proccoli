#!/usr/bin/env python3
"""Which install each source file belongs to.

- **metrics** (``proccoli``): everything without a display: the
  library both parts use (``core/``, ``devices/``, ``processes/``, the GPU
  backends) and the collector (``metrics.py``). No Gtk, Gdk or Adw.
- **gui** (``proccoli-gui``): the window: ``ui/``, ``app.py``,
  ``__main__.py``, the root helper (``helper/``) and the view modules that
  live beside their GPU backends (``GUI_IN_DOMAIN``), which the backends
  reach only through the lazy import in ``create_views()``.

``tests/test_static.py`` checks the rule (the library never imports the
GUI side, at any level), and ``install.sh`` installs from these lists, so
no file is in both packages and none is left out.

    python3 packaging/split.py metrics|gui # the files, one per line
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src", "proccoli")

GUI_DIRS = ("ui/", "helper/")
GUI_FILES = frozenset({"app.py", "__main__.py"})
# View modules beside their domain code (the GPU tabs).
GUI_IN_DOMAIN = frozenset({"gpu/intel_gpu_top/views.py", "gpu/intel_gpu_top/clients.py",
                           "gpu/nvidia/views.py", "gpu/amdgpu/views.py"})


def part(rel: str) -> str:
    """"gui" or "metrics" for a path relative to ``src/proccoli``."""
    rel = rel.replace(os.sep, "/")
    if rel.startswith(GUI_DIRS) or rel in GUI_FILES or rel in GUI_IN_DOMAIN:
        return "gui"
    return "metrics"


def sources(src: str = SRC) -> list[str]:
    """Every ``.py`` file under ``src``, relative, sorted (no caches)."""
    out = []
    for dirpath, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in files:
            if name.endswith(".py"):
                out.append(os.path.relpath(os.path.join(dirpath, name), src).replace(os.sep, "/"))
    return sorted(out)


def files(which: str, src: str = SRC) -> list[str]:
    return [rel for rel in sources(src) if part(rel) == which]


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("metrics", "gui"):
        sys.exit("usage: split.py metrics|gui")
    print("\n".join(files(sys.argv[1])))
