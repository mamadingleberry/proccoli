# 5. Core layer

```mermaid
classDiagram
    direction LR
    class System {
        +which(name) str|None
        +geteuid() int
        +has_file_capabilities(path) bool
        +user_name(uid) str
        +clk_tck() int
        +machine() str
        +kill(pid, sig)
        +get_priority(pid) int
        +set_priority(pid, nice)
        +get_affinity(pid) set
        +set_affinity(pid, cpus)
        +stream_reader() StreamReader
        +run_async(argv, callback(rc, out, err))
        +desktop_app(app_id) AppInfo|None
        +app_switch_method(app_id) 'dbus'|'launch'|None
        +activate_app(app_id) bool
    }
    class SysRoot {
        +root: Path
        +read_text(path) str|None
        +read_line(path) str|None
        +read_int(path, base) int|None
        +listdir(path) list
        +exists(path) bool
        +is_dir(path) bool
        +readlink(path) str|None
        +link_name(path) str|None
    }
    class Settings {
        +load()$ Settings
        +for_tests(overrides)$ Settings
        +in_memory_gio(dir)$ Settings
        +get(key) Any
        +set(key, value)
        +reset(key)
        +connect_changed(key, cb) int
        +disconnect(handler)
        +bind(key, obj, prop)
    }
    class Ticker {
        <<GObject>>
        +interval_ms: int
        +start()
        +stop()
        +set_interval(ms)
        +follow(settings)
        +signal tick(now)
    }
    class History {
        +step_s: float
        +offline: deque~bool~
        +define(name, unit) Series
        +add(now, values, units)
        +add_gap(now)
        +series(name) Series
        +set_plan(points, every, step_s)
        +set_max_points(n)
        +backfill(times, values, offline)
        +write_csv(path)
    }
    class Series {
        +name, unit
        +values: deque
        +offline: deque~bool~ (the history's)
        +latest()
        +peak()
    }
    class StreamReader {
        <<GObject>>
        +start(argv, elevate)
        +start_generator(make, interval)
        +stop()
        +signal record(obj)
        +signal exited(rc, stderr, count)
    }
    class PrivilegedHelper {
        +argv: list
        +signal(name, pids, cb)
        +renice(pid, nice, cb)
        +set_affinity(pid, cpus, cb)
        +dmidecode(cb)
        +io_stream(interval_ms) StreamReader
    }
    class HelperResult {
        <<dataclass>>
        +ok: bool
        +data: dict
        +error: str
        +cancelled: bool
    }
    class PciIds {
        +vendor(id) str|None
        +device(vendor, device) str|None
    }
    History *-- Series
    StreamReader ..> JsonStreamParser
    System ..> StreamReader : creates
    PrivilegedHelper o-- System
    PrivilegedHelper ..> HelperResult
```

- **`System`** is the only OS facade. Tests use `FakeSystem`
  (`tests/helpers.py`), which records signals, priorities and child
  processes, and answers `which` and the user and app lookups from
  attributes.
- **`PrivilegedHelper`** runs `pkexec proccoli-helper <subcommand>`
  asynchronously, since the password prompt takes time. It turns pkexec's 126
  and 127 into `cancelled`. The helper itself
  (`helper/proccoli_helper.py`) is a standalone script with strict argument
  validation and no shell. Only a root-owned installed helper is used, and
  processes are named by PID *and* start time ([§11](11-cross-cutting-concerns.md), *Security*).
- **`Ticker`:** one app-wide timer at the *Update Interval* setting
  (`update-interval`: 1, 2, 3, 5 or 10 s; it replaced *Refresh Speed*,
  whose 0.5 and 0.25 s went too fast, Feature 6), so all graphs line up
  in time. Each tick is due at `start + n × interval` on the monotonic
  clock and armed as a one-shot timer for the time left: a repeating
  `GLib.timeout_add` counts from the end of the previous tick's work and
  drifted ~5 ms a tick. A late tick isn't made up; a timer that fires a
  fraction early never ticks the same due time twice; a handler that
  stops or re-arms the ticker leaves at most one timer.
- **`Settings`:** GSettings when the schema is installed or can be compiled
  from the checkout, otherwise a dictionary with the same defaults and
  validation. A source checkout always uses its own compiled schema first.
  `choose_schema` skips any schema missing a key the app's schema
  describes (`schema_covers`): GSettings aborts the whole program on an
  unknown key. This happened once, when an installed package older than
  the checkout lacked `sidebar-shown`.
