# Milestone 44: Stall watchdog

*✅ Done.* A frozen main loop is logged with stack samples (diagnosing M43 on the desktop)

While diagnosing M43: a frozen window writes nothing to its log, because
the main loop that would write is the thing that's stuck.

| Step | Create / change | Test |
|---|---|---|
| 44.1 | `core/watchdog.py`: `StallWatchdog(logger, timeout_s, clock, stacks, sleep, schedule)`: `beat()` from a 250 ms main-loop timeout, `check()` from a daemon thread; after 3 s, one error with 3 stack samples; a warning when it recovers; `format_stacks` (main thread first) | Unit with a fake clock: quiet while beating, one report per stall, recovery, thread list, start/stop |
| 44.2 | `Application` starts it after the file log and stops it on shutdown | App test |
| 44.3 | [DESIGN §11](../../../design/11-cross-cutting-concerns.md), *Stall watchdog* (sequence diagram) | — |
