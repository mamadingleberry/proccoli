"""Application settings.

``Settings`` wraps ``Gio.Settings`` (persistent, through dconf) and offers
the same interface over a plain dictionary when no compiled schema is
available. Defaults always come from the schema XML in ``data/``, so the two
behave the same.

Where the schema comes from:

1. in a source checkout, its own ``data/<APP_ID>.gschema.xml``, compiled
   into ``build/schemas/`` on demand (needs ``glib-compile-schemas``).
   Never the installed one first: an installed package may be older and
   lack keys this code uses, and GSettings aborts the whole program on an
   unknown key;
2. installed system-wide (the .deb, or ``make install``);
3. otherwise a non-persistent in-memory fallback, with a warning.

Any schema missing a key the app's schema description has is skipped
(``schema_covers``).

Values are plain Python: enum keys are their nick strings ("celsius"),
``a{ss}`` keys are dicts.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib, GObject  # noqa: E402

from .. import APP_ID  # noqa: E402

log = logging.getLogger(__name__)

ChangedCallback = Callable[[str, Any], None]

SOURCE_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_FILE = f"{APP_ID}.gschema.xml"


def source_schema_path() -> Optional[Path]:
    p = SOURCE_ROOT / "data" / SCHEMA_FILE
    return p if p.is_file() else None


# -- schema description (parsed from the XML) ----------------------------------

@dataclass
class KeySpec:
    name: str
    type: str                       # GVariant type string ("s" for enums)
    default: Any
    choices: Optional[list[str]] = None   # enum nicks
    range: Optional[tuple[Any, Any]] = None

    def check(self, value: Any) -> Any:
        """Validate and normalise a value for this key, or raise ValueError."""
        # GLib.Variant would accept any iterable for an array ("abc" -> as).
        if self.type.startswith("a") and isinstance(value, (str, bytes)):
            raise ValueError(f"{self.name}: {value!r} is not of type {self.type}")
        try:
            v = GLib.Variant(self.type, value).unpack()
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{self.name}: {value!r} is not of type {self.type}") from exc
        if self.choices is not None and v not in self.choices:
            raise ValueError(f"{self.name}: {v!r} is not one of {self.choices}")
        if self.range is not None and not self.range[0] <= v <= self.range[1]:
            raise ValueError(f"{self.name}: {v!r} is outside {self.range}")
        return v


@dataclass
class SchemaSpec:
    id: str
    keys: dict[str, KeySpec] = field(default_factory=dict)

    @classmethod
    def parse(cls, path: Path, schema_id: str = APP_ID) -> "SchemaSpec":
        root = ET.parse(path).getroot()
        enums = {e.get("id"): [v.get("nick") for v in e.findall("value")]
                 for e in root.findall("enum")}
        for schema in root.findall("schema"):
            if schema.get("id") != schema_id:
                continue
            spec = cls(schema_id)
            for k in schema.findall("key"):
                name = k.get("name")
                choices = None
                if k.get("enum"):
                    vtype, choices = "s", enums[k.get("enum")]
                else:
                    vtype = k.get("type")
                default = GLib.Variant.parse(
                    GLib.VariantType.new(vtype), k.findtext("default").strip(),
                    None, None).unpack()
                rng = None
                r = k.find("range")
                if r is not None:
                    t = GLib.VariantType.new(vtype)
                    rng = (GLib.Variant.parse(t, r.get("min"), None, None).unpack(),
                           GLib.Variant.parse(t, r.get("max"), None, None).unpack())
                spec.keys[name] = KeySpec(name, vtype, default, choices, rng)
            return spec
        raise KeyError(f"schema {schema_id} not found in {path}")

    @classmethod
    def from_gio(cls, schema: Gio.SettingsSchema) -> "SchemaSpec":
        """Description of an installed schema (no XML at hand)."""
        spec = cls(schema.get_id())
        for name in schema.list_keys():
            key = schema.get_key(name)
            rtype, rvalue = key.get_range().unpack()
            choices = list(rvalue) if rtype == "enum" else None
            rng = tuple(rvalue) if rtype == "range" else None
            spec.keys[name] = KeySpec(name, key.get_value_type().dup_string(),
                                      key.get_default_value().unpack(), choices, rng)
        return spec


# -- backends -------------------------------------------------------------------

class _GioStore:
    persistent = True

    def __init__(self, gsettings: Gio.Settings) -> None:
        self.gs = gsettings

    def get(self, spec: KeySpec) -> Any:
        return self.gs.get_value(spec.name).unpack()

    def set(self, spec: KeySpec, value: Any) -> None:
        self.gs.set_value(spec.name, GLib.Variant(spec.type, value))

    def connect(self, key: str, cb: Callable[[], None]) -> int:
        return self.gs.connect(f"changed::{key}", lambda *_: cb())

    def disconnect(self, handler: int) -> None:
        self.gs.disconnect(handler)

    def bind(self, key: str, obj: GObject.Object, prop: str) -> None:
        self.gs.bind(key, obj, prop, Gio.SettingsBindFlags.DEFAULT)


class _DictStore:
    persistent = False

    def __init__(self, spec: SchemaSpec) -> None:
        self.values = {k: s.default for k, s in spec.keys.items()}
        self.handlers: dict[int, tuple[str, Callable[[], None]]] = {}
        self.next_id = 1

    def get(self, spec: KeySpec) -> Any:
        return self.values[spec.name]

    def set(self, spec: KeySpec, value: Any) -> None:
        if self.values[spec.name] == value:
            return
        self.values[spec.name] = value
        for key, cb in list(self.handlers.values()):
            if key == spec.name:
                cb()

    def connect(self, key: str, cb: Callable[[], None]) -> int:
        hid = self.next_id
        self.next_id += 1
        self.handlers[hid] = (key, cb)
        return hid

    def disconnect(self, handler: int) -> None:
        self.handlers.pop(handler, None)

    def bind(self, key: str, obj: GObject.Object, prop: str) -> None:
        raise NotImplementedError  # handled generically in Settings.bind


# -- public API -------------------------------------------------------------------

class Settings:
    def __init__(self, spec: SchemaSpec, store) -> None:
        self.spec = spec
        self._store = store

    # construction

    @classmethod
    def load(cls) -> "Settings":
        """Persistent settings when possible (see module docstring)."""
        spec_path = source_schema_path()
        source = Gio.SettingsSchemaSource.get_default()
        candidates = []                  # (where, Gio.SettingsSchema), best first
        if spec_path is not None:
            schema_dir = compile_source_schema()
            if schema_dir is not None:
                own = Gio.SettingsSchemaSource.new_from_directory(
                    str(schema_dir), source, False).lookup(APP_ID, False)
                candidates.append(("source checkout", own))
        candidates.append(("installed", source.lookup(APP_ID, True) if source else None))
        spec = SchemaSpec.parse(spec_path) if spec_path else None
        schema = choose_schema(candidates, spec)
        if schema is not None:
            spec = spec or SchemaSpec.from_gio(schema)
            return cls(spec, _GioStore(Gio.Settings.new_full(schema, None, None)))
        if spec_path is None:
            raise RuntimeError(f"settings schema {APP_ID} is not installed")
        log.warning("settings schema not available: settings will not be saved")
        return cls(spec, _DictStore(spec))

    @classmethod
    def for_tests(cls, overrides: Optional[dict[str, Any]] = None,
                  schema_path: Optional[Path] = None) -> "Settings":
        """In-memory settings with schema defaults, never touching dconf."""
        spec = SchemaSpec.parse(schema_path or source_schema_path())
        s = cls(spec, _DictStore(spec))
        for k, v in (overrides or {}).items():
            s.set(k, v)
        return s

    @classmethod
    def in_memory_gio(cls, schema_dir: Path) -> "Settings":
        """Real Gio.Settings on a memory backend (used to test that both
        stores behave the same)."""
        source = Gio.SettingsSchemaSource.new_from_directory(str(schema_dir), None, False)
        schema = source.lookup(APP_ID, False)
        gs = Gio.Settings.new_full(schema, Gio.memory_settings_backend_new(), None)
        return cls(SchemaSpec.parse(source_schema_path()), _GioStore(gs))

    # access

    @property
    def persistent(self) -> bool:
        return self._store.persistent

    def keys(self) -> list[str]:
        return list(self.spec.keys)

    def _spec(self, key: str) -> KeySpec:
        try:
            return self.spec.keys[key]
        except KeyError:
            raise KeyError(f"unknown settings key {key!r}") from None

    def default(self, key: str) -> Any:
        return self._spec(key).default

    def get(self, key: str) -> Any:
        return self._store.get(self._spec(key))

    def set(self, key: str, value: Any) -> None:
        spec = self._spec(key)
        self._store.set(spec, spec.check(value))

    def reset(self, key: str) -> None:
        self.set(key, self.default(key))

    def connect_changed(self, key: str, callback: ChangedCallback) -> int:
        """Call ``callback(key, new_value)`` whenever ``key`` changes."""
        self._spec(key)
        return self._store.connect(key, lambda: callback(key, self.get(key)))

    def disconnect(self, handler: int) -> None:
        # A widget may disconnect from its destroy handler while garbage
        # collection is tearing down a cycle that includes this object;
        # its attributes may already be gone then, and there's nothing to do.
        store = getattr(self, "_store", None)
        if store is not None:
            store.disconnect(handler)

    def bind(self, key: str, obj: GObject.Object, prop: str) -> None:
        """Two-way binding between a key and a GObject property."""
        if isinstance(self._store, _GioStore):
            self._store.bind(key, obj, prop)
            return
        obj.set_property(prop, self.get(key))

        def to_obj(_k, value):
            if obj.get_property(prop) != value:
                obj.set_property(prop, value)

        def to_settings(*_a):
            value = obj.get_property(prop)
            if value != self.get(key):
                self.set(key, value)

        self.connect_changed(key, to_obj)
        obj.connect(f"notify::{prop}", to_settings)


def schema_covers(schema, spec: Optional["SchemaSpec"]) -> bool:
    """Whether the compiled ``schema`` has every key ``spec`` describes
    (an older installed schema doesn't, and GSettings aborts on a missing
    key)."""
    if schema is None:
        return False
    return spec is None or all(schema.has_key(k) for k in spec.keys)


def choose_schema(candidates, spec: Optional["SchemaSpec"]):
    """The first ``(where, schema)`` candidate that covers ``spec``."""
    for where, schema in candidates:
        if schema is None:
            continue
        if schema_covers(schema, spec):
            return schema
        missing = sorted(k for k in spec.keys if not schema.has_key(k))
        log.warning("ignoring the %s settings schema: it lacks %s", where, ", ".join(missing))
    return None


def compile_source_schema() -> Optional[Path]:
    """Compile the source checkout's schema into build/schemas (if stale)
    and return that directory, or None if it can't be done."""
    src = source_schema_path()
    tool = shutil.which("glib-compile-schemas")
    if src is None or tool is None:
        return None
    out = SOURCE_ROOT / "build" / "schemas"
    compiled = out / "gschemas.compiled"
    try:
        if compiled.exists() and compiled.stat().st_mtime >= src.stat().st_mtime:
            return out
        out.mkdir(parents=True, exist_ok=True)
        subprocess.run([tool, "--strict", f"--targetdir={out}", str(src.parent)],
                       check=True, capture_output=True, text=True)
        return out
    except (OSError, subprocess.CalledProcessError) as exc:
        log.warning("could not compile settings schema: %s",
                    getattr(exc, "stderr", None) or exc)
        return None


def migrate(settings) -> list[str]:
    """Carry choices over from keys that were replaced, once (Idea 6:
    *Refresh Speed* became *Update Interval*). The old key is reset after,
    so this does nothing on later starts or a fresh install. Returns what
    it did, for the log."""
    from .ticker import REFRESH_SPEED_TO_INTERVAL
    done = []
    old = settings.get("refresh-speed")
    if old != settings.default("refresh-speed"):
        new = REFRESH_SPEED_TO_INTERVAL.get(old, "1-second")
        settings.set("update-interval", new)
        settings.reset("refresh-speed")
        done.append(f"refresh-speed {old} -> update-interval {new}")
    intel = settings.get("intel-gpu-top-interval")
    if intel in REFRESH_SPEED_TO_INTERVAL:
        new = REFRESH_SPEED_TO_INTERVAL[intel]
        settings.set("intel-gpu-top-interval", new)
        done.append(f"intel-gpu-top-interval {intel} -> {new}")
    return done
