# Milestone 10: Processes page

*✅ Done.*

| # | Create | Test |
|---|---|---|
| 10.1 | `processes/model.py`: `ProcessInfo`, plus a `RawProc` parser for `/proc/PID/{stat,status,io,cgroup,cmdline}` | Fixtures: normal, kernel thread, zombie, a process exiting mid-read (missing files) |
| 10.2 | `processes/monitor.py`: `ProcfsSource` + `ProcessMonitor` (CPU % from deltas, normalised or not, I/O rates, GPU columns merged from every `GpuController.process_usage()`) | Fixture pair → expected `ProcessInfo` values |
| 10.3 | `ui/pages/processes.py`: `TablePage` base (search bar, toast overlay, action bar) + `ProcessesPage` (`Gtk.ColumnView`, `ProcessRow` with a `revision` diff update, sorters per column) | Unit: the diff keeps row objects for surviving PIDs. Smoke: 500 fake processes update in under 50 ms. |
| 10.4 | Column visibility from `processes-show-*` settings; sort column and order saved | Settings round-trip |
| 10.5 | Search: name, command line and PID filter (`Ctrl+F`) | Unit on the filter function |
| 10.6 | `processes/actions.py`: End (TERM), Kill, Halt (STOP), Continue for **own** processes with `os.kill`; multi-select; toast on success or failure | Unit with a mocked `os.kill`; the permission-denied path returns an `ActionResult` |
| 10.7 | Keyboard: `Delete`, `Ctrl+Delete`, `Ctrl+I` | Manual |

**Done:** the Processes page lists, sorts and searches processes, and can
end the user's own processes. The GPU column has values on this laptop.
