# Bug 10: The Lightweight switch shows the setting, not the mode

Design note: [design/bugs/bug-10-the-lightweight-switch-showed-the-setting.md](../../design/bugs/bug-10-the-lightweight-switch-showed-the-setting.md)

*Fixed in Milestone 81.*

**Seen:** "the Preferences menu's slidebar for lightweight mode should be
set to the current state (i.e. turned on if currently in lightweight
mode)".

**Cause:** the switch showed the saved setting, which differs from the
running mode after `--lightweight` (a one-off flag) and after a change
that waits for a restart.

**Fix:** the switch shows the running mode; flipping it chooses the next
start's mode, and *Restart to Apply* says which way.

| Step | Create / change | Test |
|---|---|---|
| B10.1 | `ui/dialogs/preferences.py` | `test_ui_lightweight`: the switch shows the mode; a pending change |
