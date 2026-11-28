# Bug 12: A test started the installed collector on the real history

Design note: [design/bugs/bug-12-a-test-started-the-installed-collector.md](../../design/bugs/bug-12-a-test-started-the-installed-collector.md)

*Fixed in v0.5.0.*

**Seen:** "what does this debug log imply? … WARNING
proccoli.metrics_service: can't serve io.github.mamadingleberry.Proccoli.Metrics:
no session bus, or another collector". Two collectors were running: the
systemd one, and one started at 15:31:47 from the terminal the tests ran
in, on a test bus that no longer existed.

**Cause:** the tests' private `dbus-daemon` used the standard session
configuration, which includes `/usr/share/dbus-1/services/`, where the
installed packages now put the collector's activation file. A call to
the collector's name with no owner (D-Bus calls auto-start by default)
made that bus start the installed `proccoli-metrics`, with the real
history. When the test bus closed it couldn't serve (the warning), but
kept running, and took over writing the real history when the systemd
collector restarted at the next reinstall. Its readings were the
machine's own, so nothing wrong was recorded.

**Fix:** the tests' bus has no service folders, so nothing can be started
on it; and the window's calls never auto-start (only the name watcher
may, when meant to).

| Step | Create / change | Test |
|---|---|---|
| B12.1 | `tests/helpers.PrivateBus`, `devices/remote.py` (`NO_START`) | `test_remote.NoStrayCollectorTest` |
