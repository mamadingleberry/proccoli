# Milestone 2: Core services

*✅ Done.* Last-viewed page done in 1.8

*Goal: the plumbing every monitor needs: time, settings, history, units and
filesystem access.*

| # | Create | Test |
|---|---|---|
| 2.1 | `core/sysroot.py`: `SysRoot(root)` with `read_text`, `read_int`, `listdir`, `exists`, `readlink` | Unit against `tests/fixtures/minimal/`: missing files return `None` instead of raising |
| 2.2 | `tests/fixtures/capture.sh`: copies the needed `/proc` and `/sys` files (as plain files) into a named fixture directory | Run once on this laptop → `tests/fixtures/alderlake-laptop/` |
| 2.3 | `core/units.py`: bytes (binary/decimal), bytes per second and bits per second, percent, frequency, power, temperature (°C/°F/K), duration | Table-driven unit tests (pattern from `test_graph_helpers.py`) |
| 2.4 | `core/history.py`: `Series` and `History` (ring buffer, gaps, `set_max_points`, CSV). Port from intel_gpu_top_gui `history.py` and generalise `add()` to take a flat `dict[str, float]`. | Port `test_history.py` and adapt it |
| 2.5 | `core/settings.py`: `Settings` wrapper over `Gio.Settings` with a dict fallback (used when the schema isn't installed, and via `Settings.for_tests()`) | Unit: get/set/changed callbacks on the fallback |
| 2.6 | `data/io.github.mamadingleberry.Proccoli.gschema.xml` with the Resources-equivalent keys from [DESIGN §11](../../design/11-cross-cutting-concerns.md). ✅ Compiled on demand into `build/schemas` by `Settings.load()` (no env var needed). | `glib-compile-schemas --strict --dry-run data/` in `make test` |
| 2.7 | `core/ticker.py`: `Ticker` (GObject, `tick` signal, `set_interval`) wired to `refresh-speed` | Unit with a fake clock: `set_interval` re-arms the timer and emits one tick per interval |
| 2.8 | Window size and maximised state saved and restored ✅ (last viewed page → step 1.8) | Unit test with a fake window: round trip, maximised keeps the unmaximised size |

**Done:** the app remembers its window and page. Ticker, Settings, History
and Units are fully unit-tested.
