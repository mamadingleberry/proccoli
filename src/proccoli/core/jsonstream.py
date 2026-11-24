"""Incremental decoding of a stream of concatenated JSON objects.

Tools like ``intel_gpu_top -J`` write one JSON object per period inside a
never-terminated array (``[ {...}, {...},``), so the output is never valid
JSON as a whole. Ported from intel_gpu_top_gui.
"""

from __future__ import annotations

import json


class JsonStreamParser:
    _SEPARATORS = " \t\r\n,[]"

    def __init__(self) -> None:
        self._buf = ""
        self._decoder = json.JSONDecoder()

    def feed(self, text: str) -> list[dict]:
        """Add text; return the objects that are now complete."""
        self._buf += text
        out = []
        while True:
            i, n = 0, len(self._buf)
            while i < n and self._buf[i] in self._SEPARATORS:
                i += 1
            self._buf = self._buf[i:]
            if not self._buf:
                break
            try:
                obj, end = self._decoder.raw_decode(self._buf)
            except json.JSONDecodeError:
                # Incomplete object: wait for more. Garbage that can never
                # decode is skipped up to the next "{".
                if self._buf[0] != "{":
                    nxt = self._buf.find("{")
                    self._buf = self._buf[nxt:] if nxt >= 0 else ""
                    continue
                break
            self._buf = self._buf[end:]
            if isinstance(obj, dict):
                out.append(obj)
        return out
