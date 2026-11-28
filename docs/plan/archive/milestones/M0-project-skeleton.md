# Milestone 0: Project skeleton

*✅ Done.*

*Goal: an empty libadwaita window opens from a source checkout, and the test
runner works.*

| # | Create | Test |
|---|---|---|
| 0.1 | `LICENSE` (0BSD, [DESIGN §11](../../../design/11-cross-cutting-concerns.md)), `.gitignore` (build/, dist/, `__pycache__/`) | – |
| 0.2 | `src/proccoli/__init__.py` (`APP_ID`, `APP_NAME`, `__version__`), `__main__.py` | `tests/test_meta.py`: the version string parses and `APP_ID` is a valid D-Bus name |
| 0.3 | `src/proccoli/app.py`: `Application(Adw.Application)`, argparse (`--version`, `--demo`, `--debug`) | `tests/test_app.py`: CLI parsing with `Application` mocked (same pattern as intel_gpu_top_gui) |
| 0.4 | `Makefile`: `run`, `demo`, `test`, `ui-test`, `clean` | `make test` runs and passes |
| 0.5 | An empty `MainWindow(Adw.ApplicationWindow)` titled "Proccoli" | Manual: `make run` opens a window |

**Done:** `make run` opens an empty window, and `make test` passes.
