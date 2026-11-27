# Idea 22: Recording from boot (lingering)

Design note: [design/ideas/idea-22-recording-from-boot.md](../../design/ideas/idea-22-recording-from-boot.md)

*Done as Milestone 89 (option A).* Answers:
A now, with a one-time dialog, each person's own choice; C kept as
[Idea 25](idea-25-a-recorder-for-the-whole-machine.md).

**Goal:** the history has no gap between boot and log-in, or after
log-out: the recorder runs whenever the machine does.

**Today:** `proccoli.service` is a systemd *user* unit, enabled for every
user by the package (`systemctl --global enable`), so it starts when a
user logs in and stops when their last session ends. It runs from boot
only with *lingering* on for that user (`loginctl enable-linger`), which
Preferences → General → History → *Start at Boot* switches
(`core/background.py`, `set_linger`); it's off unless the user finds it.
Asked about in M84 ("does proccoli systemd start on boot now?"): on this
machine it doesn't (`Linger=no`).

**Ways to do it:**

| | How | For | Against |
|---|---|---|---|
| A | **Offer lingering** where it matters: once, after the first install or first window (a dialog like *Show All Details?*), and from `proccoli --status` ("not recording before log-in: `proccoli --start-at-boot`"); a `--start-at-boot` / `--no-start-at-boot` option on the recorder | Stays the user's choice; no new parts; works on a server through the command | Still a step to take |
| B | **The package turns lingering on** in `postinst` for each person with a login (UID ≥ 1000 with a login shell), and off again in `postrm` for the ones it turned on (remembered in `/var/lib/proccoli/linger`) | Nothing to do | Lingering starts *all* of that user's enabled user services at boot, not only Proccoli's; changes the system for users who didn't ask; new users after installing get nothing |
| C | **A system-wide recorder**: a system unit (`proccoli-system.service`) running as its own user (`DynamicUser=`), writing `/var/lib/proccoli/history.sqlite3`; windows read it, and per-user recorders stand down | Runs from boot for everyone; one history per machine (fits a server, and the Web GUI of Ideas 16 and 17) | A large change: a second history location and its permissions, settings that aren't per-user (the user's *Update Interval*, *Keep History* limits), per-user process names need care |

**Recommendation:** A now (small, keeps the choice with the person); C
later, together with the Web GUI ideas, where one machine-wide history
is the point. B only if asked: it does more than Proccoli needs.

| Step (A) | Create / change | Test |
|---|---|---|
| I22.1 | `core/background.py`: `should_offer_linger(state, settings)` (pure: recorder enabled, lingering off, not offered before); a setting `linger-offered` | Unit: when to offer, and never twice |
| I22.2 | The window: a one-time *Record from Boot?* dialog after start-up; Preferences' *Start at Boot* row unchanged | UI: shown once with lingering off; not with it on; *Turn On* calls `set_linger` (faked `System`) |
| I22.3 | `metrics.py`: `--start-at-boot` / `--no-start-at-boot`, and a line in `--status` when lingering is off | Unit: arguments call `loginctl` through `System`; the status line |
| I22.4 | README (*Background recording*, *Only the recorder*), DESIGN | `make ui-test` |

**Open questions for the user:**
1. A, B or C (or A now and C later)?
2. For A: offer it in a dialog at the first start, or only show a note
   on the *History* group until it's on?
3. On a machine with several people, should one person's choice light
   up recording from boot for the others too? (A and B: no, each
   person's own; C: yes, it's machine-wide.)
