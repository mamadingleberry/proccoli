"""The machine an export came from: operating
system, kernel, architecture and the computer's model, for ``export.json``.

Read through ``SysRoot`` (every file is readable by any user) and
``System.machine()``; anything missing is left out. The host name is
never included: an export is often shared.
"""

from __future__ import annotations

import shlex

from .sysroot import SysRoot

OS_RELEASE = ("/etc/os-release", "/usr/lib/os-release")
KERNEL = "/proc/sys/kernel/osrelease"
DMI = "/sys/class/dmi/id"
# Firmware placeholders that say nothing about the computer.
_UNSET = {"", "to be filled by o.e.m.", "default string", "system product name",
          "system manufacturer", "not applicable", "none", "n/a"}


def os_name(sysroot: SysRoot) -> str:
    """``PRETTY_NAME`` from os-release (``Ubuntu 24.04.1 LTS``), or ``NAME``."""
    for path in OS_RELEASE:
        text = sysroot.read_text(path)
        if not text:
            continue
        fields = {}
        for line in text.splitlines():
            key, sep, value = line.partition("=")
            if sep:
                try:
                    fields[key.strip()] = " ".join(shlex.split(value))
                except ValueError:
                    fields[key.strip()] = value.strip().strip('"')
        return fields.get("PRETTY_NAME") or fields.get("NAME", "")
    return ""


def computer_model(sysroot: SysRoot) -> str:
    """``LENOVO 82LM`` from DMI: vendor and product, placeholders dropped."""
    parts = []
    for name in ("sys_vendor", "product_name", "product_version"):
        value = (sysroot.read_line(f"{DMI}/{name}") or "").strip()
        if value.lower() not in _UNSET and value not in parts:
            parts.append(value)
    return " ".join(parts)


def machine_info(sysroot: SysRoot, system) -> dict[str, str]:
    info = {"operating_system": os_name(sysroot),
            "kernel": (sysroot.read_line(KERNEL) or "").strip(),
            "architecture": system.machine() if system is not None else "",
            "computer": computer_model(sysroot)}
    return {k: v for k, v in info.items() if v}
