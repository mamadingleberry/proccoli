"""Which page shows which kind of device: a registry, filled by the
composition root, so new device kinds (or test doubles) plug in without
touching the window."""

from __future__ import annotations

import logging
from typing import Callable

from ...devices.base import DeviceKind, Monitor
from ..page import ResourcePage

PageBuilder = Callable[[Monitor], ResourcePage]

log = logging.getLogger(__name__)


class PageFactory:
    def __init__(self) -> None:
        self._builders: dict[DeviceKind, PageBuilder] = {}

    def register(self, kind: DeviceKind, builder: PageBuilder) -> None:
        self._builders[DeviceKind(kind)] = builder

    def kinds(self) -> list[DeviceKind]:
        return list(self._builders)

    def create(self, monitor: Monitor) -> ResourcePage:
        """The device's page, or an ``ErrorPage`` when the device
        failed to set up or its page raised while being built."""
        from ...devices.base import FailedMonitor
        from .error import ErrorPage, error_text
        if isinstance(monitor, FailedMonitor):
            return ErrorPage(monitor, *error_text(monitor))
        try:
            builder = self._builders[monitor.info.kind]
        except KeyError:
            raise ValueError(f"no page registered for {monitor.info.kind}") from None
        try:
            return builder(monitor)
        except Exception as exc:  # noqa: BLE001 - one broken page must not stop the window
            log.exception("building the page for %s failed", monitor.info.id)
            return ErrorPage(monitor, *error_text(monitor, exc))


def standard_page_factory(ctx) -> PageFactory:
    """Pages for every device kind, wired to the context's services."""
    from .battery import BatteryPage
    from .cpu import CpuPage
    from .demo import DemoPage
    from .drive import DrivePage
    from .memory import MemoryPage
    from .gpu import GpuPage
    from .network import NetworkPage

    settings = ctx.settings
    factory = PageFactory()
    factory.register(DeviceKind.CPU, lambda m: CpuPage(m, settings))
    factory.register(DeviceKind.MEMORY, lambda m: MemoryPage(
        m, settings, authenticate=memory_authenticator(ctx.helper)))
    factory.register(DeviceKind.DRIVE, lambda m: DrivePage(m, settings))
    factory.register(DeviceKind.NETWORK, lambda m: NetworkPage(m, settings))
    factory.register(DeviceKind.BATTERY, lambda m: BatteryPage(m, settings))
    factory.register(DeviceKind.DEMO, lambda m: DemoPage(m, settings))
    # The GPU carve-out: Overview + the detail source's tabs.
    app_icon = ctx.app_icons.icon_for_pid if ctx.app_icons is not None else None
    factory.register(DeviceKind.GPU, lambda m: GpuPage(m, settings, app_icon))
    return factory


def memory_authenticator(helper):
    """The Memory page's *Authenticate* action: read the modules with
    ``dmidecode`` through the privileged helper."""
    if helper is None:
        return None
    from ...devices.memory import parse_dmidecode_memory

    def authenticate(page, finished=None) -> None:
        """``finished(ok)``, if given, is called once it worked or failed."""
        def done(result) -> None:
            if result.ok:
                page.monitor.modules = parse_dmidecode_memory(result.data.get("output", ""))
                page.show_modules()
            elif not result.cancelled:
                page.report(f"Could not read memory properties: {result.error}")
            if finished is not None:
                finished(bool(result.ok))
        helper.dmidecode(done)
    return authenticate
