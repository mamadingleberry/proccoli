# Bug 4: AMD processes' video memory is counted twice

Design note: [design/bugs/bug-04-amd-processes-video-memory-counted-twice.md](../../design/bugs/bug-04-amd-processes-video-memory-counted-twice.md)

*Fixed in v0.5.0.*

**Seen:** a process with `drm-total-vram: 415160 KiB` showed about
802 MB of video memory.

**Cause:** amdgpu lists each memory region twice in fdinfo:
`drm-total-vram` and the older `drm-memory-vram` (its resident part).
`parse_fdinfo` added every `drm-total-*` and `drm-memory-*` key.

**Fix:** each region counts once: `drm-total-*` when there is one (as
i915 and xe report), `drm-memory-*` on kernels without it.

| Step | Create / change | Test |
|---|---|---|
| B4.1 | `gpu/fdinfo.py`: `parse_fdinfo` per region | Unit with this machine's fdinfo; fails on the old code |
