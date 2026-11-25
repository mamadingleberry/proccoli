# Security Policy

## Supported versions

Proccoli is a small project, so only the latest release gets security
fixes.

| Version | Supported |
|---|---|
| 0.4.x (latest) | ✅ |
| older | ❌ |

## Reporting a vulnerability

**Please don't open a public issue for a security problem.**

Report it privately through GitHub instead:
**[Report a vulnerability](https://github.com/mamadingleberry/proccoli/security/advisories/new)**
(the repository's *Security* tab → *Report a vulnerability*).

Please include:

- the Proccoli version (*About Proccoli*) and your distribution;
- what an attacker could do, and what they'd need first (a local
  account, a running Proccoli, a password prompt being accepted...);
- steps to reproduce, or a proof of concept;
- any fix you'd suggest.

This is maintained in spare time, so replies are best effort. You'll get
an answer in the advisory, and credit in the release notes if you'd like
it. Please give a fix time to ship before you publish details.

## What's most sensitive

These parts handle privileges or private data, so reports about them
matter most:

- **The privileged helper** (`proccoli-helper`, run as root through
  `pkexec` and the polkit policy `io.github.mamadingleberry.Proccoli.policy`).
  It only sends signals, changes priority and processor affinity, reads
  memory module details and process I/O counters, and relays
  `intel_gpu_top`. Any way to make it do something else, or to act on a
  process other than the one asked for, is a vulnerability.
- **The GNOME Shell extension** (`proccoli-windows@mamadingleberry.github.io`),
  which lists windows and brings one to the front over D-Bus.
- **Files Proccoli keeps** in `~/.local/state/proccoli/` (the history
  database and the diagnostics log), which should be readable only by
  you, and the folders *Export Statistics* writes.

Problems in GTK, libadwaita, polkit, `intel_gpu_top` or NVIDIA's tools
themselves belong with those projects, though a note here is welcome if
Proccoli makes one easier to reach.
