# Milestone 81: Lightweight Mode draws with Cairo; gaps, the switch, references

*✅ Done.* Measured on the real display, Lightweight Mode (OpenGL) used *more* than the full window (128 MiB private, 19.8 % of a core vs 117 MiB, 15.1 %); with Cairo it's 56 MiB and 10.4 %. Fixes Bug 9 (a window's first seconds missing from its graphs), Bug 10 (the Lightweight switch showed the setting, not the mode) and Bug 11 (Lightweight Mode's Processor and Memory pages blank). Planning references removed from code, with a static check and a CLAUDE.md rule

Asked for after M80: Lightweight Mode "uses less compute but it seems to
use more mem", it "still freezes on restart", "why are there gaps in
data", the Preferences switch "should be set to the current state", and
no "Bug #" (or other planning) references in code.

| Step | Create / change | Test |
|---|---|---|
| 81.1 | `Profile.renderer` ("cairo" in Lightweight Mode); `profile.apply_renderer(profile, env)` sets `GSK_RENDERER` before any window, leaves a user's own choice alone, and clears its own when *Restart Now* carries it into the full profile (`PROCCOLI_SET_GSK_RENDERER` marks it) | Unit: Lightweight gets Cairo; back to full clears ours; the user's choice wins in both |
| 81.2 | Bug 9: the collector commits what it holds when a window subscribes | Unit on a private bus: buffered rows are in the database once `Subscribe` returns (fails without the fix) |
| 81.3 | Bug 10: Preferences' Lightweight switch shows the running mode; flipping it sets the next start's mode; *Restart to Apply* says which way ("turns on/off at the next start") | UI: started with `--lightweight` (setting off) shows on; a pending change says what happens next; flipping back clears it |
| 81.4 | Planning references (milestone, idea, bug, step numbers, DESIGN/PLAN sections) removed from code, comments, docstrings, tests, scripts and data; CLAUDE.md rule 6; the `proccoli-change` skill; `NoPlanningReferencesTest` | Static: none in `src/`, `tests/`, `packaging/`, `data/` |
| 81.5 | Bug 11: a device replacing a placeholder removes it before its lazy page is registered | UI: the Memory page is built when visited in Lightweight Mode on a collector |

**Measured on the real display** (GNOME on Wayland, the Ryzen 3 4300U,
the Overview, 60 s after 20 s settling; each window on a private bus with
its own collector, settings in memory):

| Window | Processor | Private (RssAnon) | Total (VmRSS) | PSS |
|---|---|---|---|---|
| Full | 15.1 % | 116.7 MiB | 224.8 MiB | 136.9 MiB |
| Lightweight, OpenGL (until now) | 19.8 % | 128.0 MiB | 236.6 MiB | 148.4 MiB |
| Lightweight, Cairo | 10.4 % | 55.7 MiB | 115.7 MiB | 68.1 MiB |

*Found while doing 81:*
- **Every earlier memory figure was taken on the headless display**
  (Broadway, which draws with Cairo), so none included OpenGL's driver
  memory, which is the same whatever the window shows. That's why
  Lightweight Mode looked like half the full window (M66, M71) and
  measured more than it on a real desktop. Figures now come from the real
  display as well.
- **The code clean-up's first pass removed every empty `()`** in comments
  and docstrings (meant for brackets emptied by a removed reference).
  Calls written in the last commit were put back exactly (43), dotted
  ones in newer text by rule (47, five wrong ones fixed by hand); some
  single-word mentions in newer text stay without brackets.
