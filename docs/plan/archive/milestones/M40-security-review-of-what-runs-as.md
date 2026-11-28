# Milestone 40: Security review of what runs as administrator

*✅ Done.* 2 high fixed (root code changeable by the user: source helper, `intel_gpu_top` on PATH), 1 medium (PID reuse), 4 low; [DESIGN §11.1](../../../design/11-cross-cutting-concerns.md)

The findings, severities and reasoning are in [DESIGN.md §11.1](../../../design/11-cross-cutting-concerns.md).

| Step | Create / change | Test |
|---|---|---|
| 40.1 | `core/trust.py`: `is_trusted_path` (file and every folder above it root-owned, not group/world-writable, symlinks resolved), `find_trusted(name)` in system folders only; `System.trusted_executable` (`FakeSystem.trusted`) | Unit with a fake filesystem; one real check (`/usr/bin/python3` yes, a file in the checkout no) |
| 40.2 | `helper_argv`: only a trusted installed helper; source checkout only with `PROCCOLI_DEV_HELPER=1`, through `python3 -I`; else no helper (actions off, logged) | Unit |
| 40.3 | intel_gpu_top elevated starts use `find_trusted`, never PATH; no trusted copy → `failed` with `UNTRUSTED_REASON`, nothing run | Unit |
| 40.4 | Process identity: `read_start_time`; `ProcessActions(start_time=...)` sends `(pid, start)`, skips processes already gone; `PrivilegedHelper` sends `PID@STARTTIME`; helper `parse_target`, `start_time`, `check_identity`, pidfd `send_signal`; renice/affinity check first | Unit on a real child process: match signalled, mismatch left alone, no-pidfd fallback, renice/affinity refused on mismatch |
| 40.5 | Helper hardening: `-I` shebang, ASCII-only digits, dmidecode timeout | Unit |
| 40.6 | `PROTOCOL = 2` in the helper; `helper_protocol(argv)` reads it from the file; older helpers get bare PIDs and a reinstall hint | Unit |
| 40.7 | Diagnostics log 0600 (also after rollover), folder 0700 | Unit |
| 40.8 | [DESIGN §11.1](../../../design/11-cross-cutting-concerns.md): what runs as root, threat model, findings, accepted risks, flow diagram | — |

**Done when:** nothing the user's own account can change is ever run as
root, root actions name processes by PID and start time, and the suite
passes.
