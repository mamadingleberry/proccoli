import errno
import os
import signal
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from helpers import FakeRoot, FakeSystem  # noqa: E402

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.gpu.backend import GpuProcessUsage  # noqa: E402
from proccoli.processes.actions import Action, message, send  # noqa: E402
from proccoli.core.system import AppInfo  # noqa: E402
from proccoli.processes.apps import SYSTEM_ID, AppGrouper, app_id_for_cgroup  # noqa: E402
from proccoli.processes.model import (  # noqa: E402
    containerization, display_name, parse_stat, read_proc)
from proccoli.processes.monitor import ProcessMonitor  # noqa: E402

TERMINAL = ("/user.slice/user-1000.slice/user@1000.service/app.slice/"
            "app-org.gnome.Terminal.slice/vte-spawn-1bcf6cd6-890a-4a06-92ac-d8320fdad1fb.scope")


def stat_line(pid, name, utime, stime, nice=0, start=100, state="S"):
    # pid (comm) state ppid pgrp session tty tpgid flags minflt cminflt majflt
    # cmajflt utime stime cutime cstime priority nice threads itreal starttime ...
    return (f"{pid} ({name}) {state} 1 {pid} {pid} 0 -1 4194304 10 0 0 0 "
            f"{utime} {stime} 0 0 20 {nice} 1 0 {start} 1000 100 0\n")


def add_proc(root, pid, name, utime=0, stime=0, uid=1000, rss_kb=1000, swap_kb=0,
             read=0, write=0, cgroup="/", cmdline=None, nice=0, start=100, io=True):
    base = f"/proc/{pid}"
    root.write(f"{base}/stat", stat_line(pid, name, utime, stime, nice, start))
    root.write(f"{base}/status", f"Name:\t{name[:15]}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n"
                                 f"VmRSS:\t{rss_kb} kB\nVmSwap:\t{swap_kb} kB\n")
    if io:
        root.write(f"{base}/io", f"rchar: 1\nread_bytes: {read}\nwrite_bytes: {write}\n")
    root.write(f"{base}/cgroup", f"0::{cgroup}\n")
    root.write(f"{base}/cmdline", (cmdline or name).replace(" ", "\0") + "\0")


class ModelTest(unittest.TestCase):
    def test_stat_with_awkward_name(self):
        p = parse_stat(stat_line(42, "Web Content (1)", 300, 100, nice=-5, start=777), 42)
        self.assertEqual((p.name, p.utime, p.stime, p.nice, p.starttime),
                         ("Web Content (1)", 300, 100, -5, 777))
        self.assertIsNone(parse_stat("garbage", 1))

    def test_display_name_uses_full_executable(self):
        self.assertEqual(display_name("gnome-calculato", "/usr/bin/gnome-calculator --x"),
                         "gnome-calculator")
        self.assertEqual(display_name("bash", "/bin/bash"), "bash")
        self.assertEqual(display_name("kworker/0:1-eve", ""), "kworker/0:1-eve")

    def test_display_name_of_a_script_is_the_script(self):
        # A script run by python3 shows as its own name, past the kernel's
        # 15-character cut ("gnome-shell-cal").
        self.assertEqual(display_name("gnome-shell-cal",
                                      "/usr/bin/python3 /usr/bin/gnome-shell-calendar-server"),
                         "gnome-shell-calendar-server")
        # Only the program or its script, never a later argument.
        self.assertEqual(display_name("gnome-shell-cal",
                                      "/usr/bin/python3 -u /tmp/gnome-shell-x"),
                         "gnome-shell-cal")
        self.assertEqual(display_name("python3", "/usr/bin/python3 /usr/bin/thing"), "python3")

    def test_the_background_collector_groups_with_proccoli(self):
        # Its unit runs in the desktop's app slice for Proccoli.
        from proccoli import APP_ID
        cgroup = ("0::/user.slice/user-1000.slice/user@1000.service/app.slice/"
                  f"app-{APP_ID}.slice/proccoli.service")
        self.assertEqual(app_id_for_cgroup(cgroup), APP_ID)

    def test_read_proc_and_cache(self):
        root = FakeRoot(self)
        add_proc(root, 7, "python3", rss_kb=2048, swap_kb=16, read=4096, cgroup=TERMINAL,
                 cmdline="python3 -m proccoli")
        p = read_proc(root.sysroot, 7)
        self.assertEqual((p.rss, p.swap, p.read_bytes, p.uid), (2048 * 1024, 16 * 1024, 4096, 1000))
        self.assertEqual(p.cmdline, "python3 -m proccoli")
        root.write("/proc/7/cmdline", "changed\0")
        self.assertEqual(read_proc(root.sysroot, 7, cached=p).cmdline, "python3 -m proccoli")
        self.assertIsNone(read_proc(root.sysroot, 8))           # exited

    def test_containerization(self):
        self.assertEqual(containerization("/app.slice/app-flatpak-org.x.Y-1.scope"), "Flatpak")
        self.assertEqual(containerization("/app.slice/snap.firefox.firefox-ab12cd34.scope"),
                         "Snap")
        self.assertEqual(containerization("/system.slice/docker-abc.scope"), "Container")
        self.assertIsNone(containerization(TERMINAL))


class MonitorTest(unittest.TestCase):
    class FakeGpu:
        def process_usage(self):
            return {1: GpuProcessUsage(1, usage=30.0, vram=1024)}

    def setUp(self):
        self.root = FakeRoot(self, {"/proc/stat": "cpu 1 1 1 1\ncpu0 1\ncpu1 1\n"
                                                  "btime 1000000\n"})
        add_proc(self.root, 1, "firefox", utime=100, stime=0, read=0, cgroup=TERMINAL)
        add_proc(self.root, 2, "sshd", uid=0, io=False)
        self.settings = Settings.for_tests({"normalize-cpu-usage": False})
        self.m = ProcessMonitor(self.root.sysroot, self.settings, FakeSystem(),
                                gpu_controllers=lambda: [self.FakeGpu()])

    def test_rates(self):
        self.m.refresh(10.0)
        self.assertEqual(self.m.processes[1].cpu, 0.0)        # first sample
        add_proc(self.root, 1, "firefox", utime=150, stime=50, read=2_000_000,
                 cgroup=TERMINAL)
        self.m.refresh(12.0)
        p = self.m.processes[1]
        self.assertAlmostEqual(p.cpu, 50.0)                   # 100 ticks / 100 Hz / 2 s
        self.assertEqual(p.read_bps, 1_000_000.0)
        self.assertEqual((p.cpu_time_user, p.cpu_time_system), (1.5, 0.5))
        self.assertEqual(p.started, 1000000 + 1.0)            # btime + 100 ticks
        self.assertEqual(p.app_id, "org.gnome.Terminal")
        self.assertEqual((p.gpu, p.vram), (30.0, 1024))
        root_proc = self.m.processes[2]
        self.assertIsNone(root_proc.read_bps)                 # /proc/2/io not readable
        self.assertEqual(root_proc.user, "root")

    def test_normalized_cpu_divides_by_cpus(self):
        self.settings.set("normalize-cpu-usage", True)
        self.m.refresh(10.0)
        add_proc(self.root, 1, "firefox", utime=300, cgroup=TERMINAL)
        self.m.refresh(11.0)
        self.assertAlmostEqual(self.m.processes[1].cpu, 100.0)  # 200 % over 2 CPUs

    def test_reused_pid_is_a_new_process(self):
        self.m.refresh(10.0)
        add_proc(self.root, 1, "other", utime=5000, start=999)
        self.m.refresh(11.0)
        self.assertEqual(self.m.processes[1].cpu, 0.0)

    def test_exited_processes_disappear(self):
        self.m.refresh(10.0)
        self.root.remove("/proc/2")
        self.m.refresh(11.0)
        self.assertEqual(set(self.m.processes), {1})

    def test_only_scans_while_acquired(self):
        updates = []
        self.m.connect("updated", lambda *_: updates.append(1))
        self.m.tick(1.0)
        self.assertEqual(updates, [])
        self.m.acquire()
        self.m.tick(2.0)
        self.m.release()
        self.m.release()                                   # never below zero
        self.m.tick(3.0)
        self.assertEqual(updates, [1])


class ActionsTest(unittest.TestCase):
    def test_send(self):
        calls = []

        def kill(pid, sig):
            calls.append((pid, sig))
            if pid == 2:
                raise PermissionError(errno.EPERM, "Operation not permitted")
            if pid == 3:
                raise ProcessLookupError()
        r = send(Action.HALT, [1, 2, 3], kill=kill)
        self.assertEqual(calls[0], (1, signal.SIGSTOP))
        self.assertEqual(r.succeeded, [1, 3])
        self.assertEqual(r.failed, [(2, "Operation not permitted")])
        self.assertTrue(r.permission_denied)

    def test_messages(self):
        ok = send(Action.END, [1], kill=lambda *_: None)
        self.assertEqual(message(Action.END, ["firefox"], ok), "Ended firefox")
        self.assertEqual(message(Action.KILL, ["a", "b"], send(Action.KILL, [1, 2],
                                                               kill=lambda *_: None)),
                         "Killed 2 processes")
        bad = send(Action.KILL, [1], kill=lambda *_: (_ for _ in ()).throw(
            PermissionError(errno.EPERM, "Operation not permitted")))
        self.assertEqual(message(Action.KILL, ["sshd"], bad),
                         "Could not kill the process: Operation not permitted")


class AppsTest(unittest.TestCase):
    def test_cgroup_forms(self):
        cases = {
            TERMINAL: "org.gnome.Terminal",
            "/user.slice/u@1000.service/app.slice/app-gnome-org.gnome.Nautilus-12345.scope":
                "org.gnome.Nautilus",
            "/app.slice/app-flatpak-org.mozilla.firefox-4321.scope": "org.mozilla.firefox",
            "/app.slice/snap.firefox.firefox-1e6d2f7a-2b2c-4c4e-9a1b-0123456789ab.scope":
                "firefox_firefox",
            "/app.slice/app-gnome-google\\x2dchrome-99.scope": "google-chrome",
            "/app.slice/app-org.example.Tool@abc123.service": "org.example.Tool",
            "/session.slice/org.gnome.Shell@ubuntu.service": None,
            "/system.slice/cups.service": None,
            "/": None,
        }
        for cgroup, expected in cases.items():
            self.assertEqual(app_id_for_cgroup(cgroup), expected, cgroup)

    def test_grouping_and_totals(self):
        root = FakeRoot(self, {"/proc/stat": "cpu 1\ncpu0 1\nbtime 0\n"})
        add_proc(root, 1, "gnome-terminal-", cgroup=TERMINAL, rss_kb=1000)
        add_proc(root, 2, "bash", cgroup=TERMINAL, rss_kb=500, swap_kb=100)
        add_proc(root, 3, "systemd", cgroup="/init.scope", rss_kb=10)
        add_proc(root, 4, "mystery", cgroup="/app.slice/app-gnome-not.Installed-1.scope")
        m = ProcessMonitor(root.sysroot, Settings.for_tests(), FakeSystem())
        m.refresh(1.0)
        lookups = []

        def lookup(app_id):
            lookups.append(app_id)
            return AppInfo("Terminal") if app_id == "org.gnome.Terminal" else None
        grouper = AppGrouper(lookup)
        apps = grouper.group(m.processes.values())
        self.assertEqual(set(apps), {"org.gnome.Terminal", SYSTEM_ID})
        term = apps["org.gnome.Terminal"]
        self.assertEqual((term.name, sorted(term.pids)), ("Terminal", [1, 2]))
        self.assertEqual(term.memory, 1500 * 1024)
        self.assertEqual(term.combined_memory, 1600 * 1024)
        self.assertEqual(sorted(apps[SYSTEM_ID].pids), [3, 4])   # no .desktop file
        grouper.group(m.processes.values())
        self.assertEqual(sorted(lookups), ["not.Installed", "org.gnome.Terminal"])  # cached

    def test_icon_for_a_pid(self):
        from proccoli.processes.apps import AppIconLookup
        root = FakeRoot(self, {})
        add_proc(root, 7, "firefox", cgroup=TERMINAL)
        add_proc(root, 8, "systemd", cgroup="/init.scope")
        icon = object()
        lookups = []

        def lookup(app_id):
            lookups.append(app_id)
            return AppInfo("Terminal", icon) if app_id == "org.gnome.Terminal" else None
        icons = AppIconLookup(root.sysroot, AppGrouper(lookup))
        self.assertIs(icons.icon_for_pid(7), icon)
        self.assertIsNone(icons.icon_for_pid(8))           # not an app: puzzle piece
        self.assertIsNone(icons.icon_for_pid(99))          # gone
        self.assertIsNone(icons.icon_for_pid(0))           # kernel / unknown
        root.remove("/proc/7")
        self.assertIs(icons.icon_for_pid(7), icon)         # cached per PID
        self.assertEqual(lookups, ["org.gnome.Terminal"])
        add_proc(root, 99, "late", cgroup=TERMINAL)
        self.assertIs(icons.icon_for_pid(99), icon)        # a miss isn't cached

    def test_icon_for_a_process_is_its_apps_icon(self):
        root = FakeRoot(self, {"/proc/stat": "cpu 1\ncpu0 1\nbtime 0\n"})
        add_proc(root, 1, "gnome-terminal-", cgroup=TERMINAL)
        add_proc(root, 2, "bash", cgroup=TERMINAL)
        add_proc(root, 3, "systemd", cgroup="/init.scope")
        add_proc(root, 4, "iconless", cgroup="/app.slice/app-gnome-org.example.Bare-1.scope")
        m = ProcessMonitor(root.sysroot, Settings.for_tests(), FakeSystem())
        m.refresh(1.0)
        icon = object()
        grouper = AppGrouper({"org.gnome.Terminal": AppInfo("Terminal", icon),
                              "org.example.Bare": AppInfo("Bare")}.get)
        p = m.processes
        self.assertIs(grouper.icon_for(p[1]), icon)
        self.assertIs(grouper.icon_for(p[2]), icon)          # same app, same icon
        self.assertIsNone(grouper.icon_for(p[3]))            # no app
        self.assertIsNone(grouper.icon_for(p[4]))            # an app without an icon


if __name__ == "__main__":
    unittest.main()
