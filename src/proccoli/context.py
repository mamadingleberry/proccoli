"""The composition root: the one place that creates Proccoli's services and
wires them together (dependency injection by hand, DESIGN.md §4.2).

The application calls ``build_context()`` with defaults (the real system).
Tests call it with fakes (``Settings.for_tests()``, a fake ``System``, a
fixture ``SysRoot``), and get exactly the same object graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .core import pciids
from .core.applog import PerformanceLog
from .core.privileged import PrivilegedHelper, helper_argv, helper_protocol, optional_helper
from .core.sysroot import SysRoot
from .core.system import System
from .core.ticker import Ticker
from .devices.base import DeviceKind
from .devices.manager import DeviceManager
from .processes.actions import ProcessActions
from .processes.model import read_start_time
from .processes.apps import AppGrouper, AppIconLookup
from .processes.monitor import ProcessMonitor

_DEFAULT = object()


@dataclass
class AppContext:
    settings: object
    ticker: Ticker
    system: System
    sysroot: SysRoot
    pci: pciids.PciIds
    devices: Optional[DeviceManager]        # None: no device pages (placeholders)
    processes: Optional[ProcessMonitor]     # None: no Apps/Processes pages
    actions: ProcessActions
    grouper: AppGrouper
    app_icons: AppIconLookup                # app icon by PID (GPU Processes tab)
    helper: Optional[PrivilegedHelper]
    demo: bool = False
    pages: object = None        # ui.pages.factory.PageFactory; the window makes one if None
    theme: object = None        # ui.theme.Theme; the window makes one if None
    perf_log: object = None     # core.applog.PerformanceLog

    def start(self) -> None:
        if self.devices is not None:
            self.devices.start(self.ticker)
        if self.processes is not None:
            self.processes.follow(self.ticker)

    def stop(self) -> None:
        self.ticker.stop()
        if self.perf_log is not None:
            self.perf_log.shutdown()
            self.perf_log = None
        if self.devices is not None:
            self.devices.stop()


def build_context(settings, *, demo: bool = False, system: Optional[System] = None,
                  sysroot: Optional[SysRoot] = None, pci: Optional[pciids.PciIds] = None,
                  ticker: Optional[Ticker] = None,
                  helper_command: object = _DEFAULT,
                  connection_name: object = _DEFAULT,
                  gpu_registry=None) -> AppContext:
    """Wire up the app. Every argument defaults to the real system; pass
    fakes to test. ``helper_command=None`` disables privileged actions;
    ``connection_name=None`` skips NetworkManager; ``gpu_registry`` replaces
    the GPU backends (``gpu.registry.standard_registry()``)."""
    system = system or System()
    sysroot = sysroot or SysRoot("/")
    pci = pci if pci is not None else pciids.load()
    ticker = ticker or Ticker()
    ticker.follow(settings)
    if helper_command is _DEFAULT:
        argv = helper_argv(trusted=system.trusted_executable)
        helper = optional_helper(system, argv, helper_protocol(argv))
    else:
        helper = optional_helper(system, helper_command)

    devices = DeviceManager(sysroot, settings)
    if demo:
        from .devices.demo import DEMO_ROOT, DemoDiscoverer, DemoGpuDiscoverer
        devices.register(DemoDiscoverer())
        devices.register(DemoGpuDiscoverer(system))
        processes = None           # demo mode must not read the real system
    else:
        for discoverer in standard_discoverers(system, pci, connection_name, gpu_registry, helper):
            devices.register(discoverer)
        processes = ProcessMonitor(sysroot, settings, system,
                                   gpu_controllers=lambda: devices.monitors(DeviceKind.GPU))

    grouper = AppGrouper(system.desktop_app)
    # The demo's GPU clients have made-up PIDs: never look them up for real.
    icon_root = SysRoot(DEMO_ROOT) if demo else sysroot
    # Before anything else connects to the ticker, so it times whole ticks.
    perf_log = PerformanceLog(sysroot, system.clk_tck(), ticker, settings)
    # Start times identify processes for the root helper (DESIGN.md §11).
    actions = ProcessActions(system, helper, lambda pid: read_start_time(sysroot, pid))
    return AppContext(settings=settings, ticker=ticker, system=system, sysroot=sysroot,
                      pci=pci, devices=devices, processes=processes,
                      actions=actions, grouper=grouper,
                      app_icons=AppIconLookup(icon_root, grouper), helper=helper, demo=demo,
                      perf_log=perf_log)


def standard_discoverers(system: System, pci: pciids.PciIds,
                         connection_name: object = _DEFAULT, gpu_registry=None,
                         helper=None) -> list:
    from .devices.battery import BatteryDiscoverer
    from .devices.cpu import CpuDiscoverer
    from .devices.drive import DriveDiscoverer
    from .devices.memory import MemoryDiscoverer
    from .devices.network import NetworkDiscoverer
    from .gpu.controller import GpuDiscoverer
    from .gpu.registry import standard_registry

    if connection_name is _DEFAULT:
        from .devices.nm import NetworkManagerClient
        connection_name = NetworkManagerClient().connection_name
    return [
        CpuDiscoverer(system.machine()),
        MemoryDiscoverer(),
        GpuDiscoverer(gpu_registry or standard_registry(), pci, system, helper),
        DriveDiscoverer(),
        NetworkDiscoverer(pci, connection_name),
        BatteryDiscoverer(),
    ]
