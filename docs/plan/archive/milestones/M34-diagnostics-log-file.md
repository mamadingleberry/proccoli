# Milestone 34: Diagnostics log file

*✅ Done.* ~/.local/state/proccoli/proccoli.log, 1 MiB + one older file by default

| Step | Create / change | Test |
|---|---|---|
| 34.1 | `core/applog.py`: `log_path()` (`$XDG_STATE_HOME/proccoli/proccoli.log`), `install_file_log(path, max_kb, backups, level)` with a rotating handler: at most `max_kb × (backups + 1)` on disk | Unit in a temp dir: rotation keeps the cap |
| 34.2 | `PerformanceLog(sysroot, ticker, clock)`: every N minutes logs Proccoli's CPU %, memory (RSS), threads and the slowest tick | Unit with a fixture `/proc/self` |
| 34.3 | Schema `log-level` (off, warning, info, debug; default warning), `log-max-size` (KiB, default 1024), `log-performance-interval` (minutes, default 10, 0 off); applied live | Settings tests |
| 34.4 | Preferences → General → *Diagnostics*: level, size, interval, *Open Log Folder* | Dialog test |
