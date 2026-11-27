# Bug 12: A test started the installed collector

Plan: [plan/bugs/bug-12-a-test-started-the-installed-collector.md](../../plan/bugs/bug-12-a-test-started-the-installed-collector.md)


*[PLAN.md, Bug 12](../../plan/bugs/bug-12-a-test-started-the-installed-collector.md). Fixed in M82.* The tests' `dbus-daemon` read the session
configuration's service folders, so a call to the collector's unowned
name activated the installed one (on the real history). `PrivateBus`
now has its own configuration without service folders, and the window's
calls use `NO_AUTO_START`.
