# Feature 6: Update Interval instead of Refresh Speed

*✅ Built in v0.3.0.*

**Goal:** a plainer, safer choice of how often Proccoli takes readings.
*Refresh Speed* (from Resources) offers five vague words, and its fastest
settings, 0.5 s and 0.25 s, go too fast: every device, the process scan,
every graph and the history database run up to four times a second. That
costs processor time and battery for changes nobody can read that
quickly, and it makes the history and the *Details* tabs store four times
the rows.

**Why: what's wrong today**

| Today | Problem |
|---|---|
| *Very Slow, Slow, Normal, Fast, Very Fast* | The words don't say how often; users can't tell 0.5 s from 0.25 s |
| 0.25 s and 0.5 s | Too fast: a full refresh of every device and every process 4 times a second; the history writes 4× the rows; the Intel tab's *Update Interval* menu offers 0.25 s too |
| Slowest is 4 s | No choice for a quiet machine or a battery (5 or 10 s) |

**Design:**

- `update-interval` (enum, nicks `1-second`, `2-seconds`, `3-seconds`,
  `5-seconds`, `10-seconds`; **default 1 second**, what *Normal* was).
  Preferences → General → *Update Interval* with the times spelled out.
  Nothing faster than 1 s.
- `refresh-speed` stays in the schema only to **migrate** a choice once
  at start-up: *Very Slow* (4 s) → 5 seconds, *Slow* (2 s) → 2 seconds,
  anything else → 1 second; then it's reset, so the migration runs once
  and never again.
- The Intel tab's own interval (`intel-gpu-top-interval`) takes the same
  nicks (empty: the *Update Interval*); its old refresh-speed nicks are
  mapped the same way when read, and migrated at start-up.
- `core.ticker`: `UPDATE_INTERVALS_MS`, `interval_for(nick)` (new and old
  nicks), `update_interval_ms(settings)`; every reader of
  `refresh-speed` (ticker, device manager, history, charts, Processes,
  Intel and NVIDIA backends) reads `update-interval` instead.

| Step | Create / change | Test |
|---|---|---|
| F6.1 | Schema `update-interval` (enum); `core.ticker` intervals and `update_interval_ms`; every reader switched | Unit: intervals; the ticker follows the new key; the manager resizes on it |
| F6.2 | `core/settings.py`: `migrate(settings)` (refresh-speed and old Intel nicks, once); called by `Application` after loading | Unit: each old value, run twice, nothing to do on a fresh install |
| F6.3 | Preferences *Update Interval*; the Intel *Update Interval* menu and preference with the new choices | Dialog test; UI: the Intel menu |
| F6.4 | README, [DESIGN §11](../../design/11-cross-cutting-concerns.md) | – |

**Done when:** no choice refreshes faster than once a second, a user's
old choice carries over once, and nothing reads `refresh-speed` except
the migration.
