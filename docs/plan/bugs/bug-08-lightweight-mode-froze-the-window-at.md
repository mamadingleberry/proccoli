# Bug 8: Lightweight Mode froze the window at start (a remote device's chart lines)

Design note: [design/bugs/bug-08-lightweight-mode-froze-the-window-at.md](../../design/bugs/bug-08-lightweight-mode-froze-the-window-at.md)

*Fixed in Milestone 79 (found after it was first built).*

**Seen:** after reinstalling with 19b, *Restart Now* into Lightweight
Mode took a long time to show device data and the window froze for about
20 s, then offered the administrator password. The log showed the stall
watchdog catching Ubuntu's crash reporter (apport) gathering package
information; `/var/crash` held the cause: `AttributeError: 'NoneType'
object has no attribute 'offline'` in `Graph.offline_flags`.

**Cause:** a local monitor defines its history's lines when it's
created; a `RemoteMonitor` only got them with its first reading.
Lightweight Mode's Overview charts every device at once, before any
reading, so `history.series("usage")` was `None` and every draw raised.
The password prompt was the usual start-up offer (other users' drive
activity on *Processes*), shown late because of the freeze.

**Fix:** `Devices()` carries each device's lines (`history`), and
`RemoteMonitor` defines them up front; `Graph.set_series` skips a missing
line with a warning instead of failing in every draw.

| Step | Create / change | Test |
|---|---|---|
| B8.1 | `metrics_service.device_info`, `devices/remote.py`, `ui/widgets/graph.py` | `test_remote`: every remote monitor has its local twin's lines before a reading; `test_ui_remote`: a Lightweight window on a collector that hasn't sent anything draws without error (fails without the fix); `test_ui_widgets`: a missing series is skipped |
