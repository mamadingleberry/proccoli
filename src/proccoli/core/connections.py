"""Signal handlers that are disconnected together.

Objects that listen to settings, devices or widgets keep their handler
ids so they can let go on shutdown; otherwise a dropped page or
backend would keep being called (and kept alive) by what it listened
to. ``Connections`` holds those ids with their sources:

    self.connections = Connections()
    self.connections.connect(monitor, "updated", self._on_updated)
    self.connections.watch(settings, ("palette", "color-scheme"), self._restyle)
    ...
    self.connections.disconnect_all()

A source is anything with ``connect(...) -> id`` and ``disconnect(id)``:
GObjects, and ``Settings`` through ``watch`` (``connect_changed``). No
GTK, so it's testable anywhere.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Union


class Connections:
    """Handler ids with their sources, disconnected in one call."""

    def __init__(self) -> None:
        self._held: list[tuple[Any, int]] = []

    def connect(self, source, signal: str, callback: Callable, *args) -> int:
        """``source.connect(signal, callback, *args)``, held."""
        return self.add(source, source.connect(signal, callback, *args))

    def watch(self, settings, keys: Union[str, Iterable[str]],
              callback: Callable[[str, Any], None]) -> list[int]:
        """``settings.connect_changed`` for one key or several, held."""
        if isinstance(keys, str):
            keys = (keys,)
        return [self.add(settings, settings.connect_changed(key, callback)) for key in keys]

    def add(self, source, handler: int) -> int:
        """Hold a handler connected elsewhere (``source`` disconnects it)."""
        self._held.append((source, handler))
        return handler

    def adopt(self, source, handlers: Iterable[int]) -> None:
        """Hold several handlers on one source."""
        for handler in handlers:
            self.add(source, handler)

    def disconnect_all(self) -> None:
        """Disconnect everything held, newest first; safe to call twice."""
        held, self._held = self._held, []
        for source, handler in reversed(held):
            source.disconnect(handler)

    def __len__(self) -> int:
        return len(self._held)
