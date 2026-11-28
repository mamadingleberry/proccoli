# Milestone 89: Recording from boot, offered once

*✅ Done.* Was Feature 22, option A. The window asks once whether to record
from boot (lingering, for that person's account); `proccoli
--start-at-boot` / `--no-start-at-boot`; `--status` says when it
doesn't. Option C became Feature 25

See [Feature 22](../../features/feature-22-recording-from-boot.md). Answers to its
questions: A now, C later
([Feature 25](../../features/feature-25-a-recorder-for-the-whole-machine.md)); a
one-time dialog; each person decides for their own account.

| Step | Create / change | Test |
|---|---|---|
| 89.1 | `core/background.py`: `should_offer_linger`, `linger_on`, `start_at_boot`, `linger_argv`; setting `linger-offered` (in the layout's `ELSEWHERE`) | Unit: when to offer (installed, on, history kept, lingering off, not asked before); lingering read through `loginctl`; on, off, the recorder itself off, no `loginctl`, a failure |
| 89.2 | `core/system.py`: `System.run` (synchronous, for the command line); `FakeSystem.run` | Unit: output, status and a missing program |
| 89.3 | `ui/dialogs/record_from_boot.py`: *Record from Boot?* (*Turn On*, *Not Now*); `Application.offer_record_from_boot` after the window appears, never over another dialog (the start-up authentication), not in `--demo` | UI: *Turn On* runs `loginctl enable-linger`; *Not Now* runs nothing; either way never asked again; not asked with lingering on, nor over another dialog (and then asked next time) |
| 89.4 | `metrics.py`: `--start-at-boot`, `--no-start-at-boot`; a `--status` line while lingering is off | Unit: the options (exclusive), the status line with lingering off and on |
| 89.5 | README (*Only the recorder*, *How Proccoli reads and records*); DESIGN (Feature 22's design: the sequence) | — |

**Done when:** a person whose recorder doesn't run from boot is asked
once, and can turn it on there, in Preferences or from a terminal.
