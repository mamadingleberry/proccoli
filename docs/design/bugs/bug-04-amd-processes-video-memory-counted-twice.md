# Bug 4: AMD processes' video memory counted twice

Plan: [plan/bugs/bug-04-amd-processes-video-memory-is-counted.md](../../plan/bugs/bug-04-amd-processes-video-memory-is-counted.md)


*[PLAN.md, Bug 4](../../plan/bugs/bug-04-amd-processes-video-memory-is-counted.md). Fixed in v0.5.0.* amdgpu's fdinfo lists each
memory region twice: `drm-total-vram` and the older `drm-memory-vram`
(the resident part). `parse_fdinfo` added every `drm-total-*` and
`drm-memory-*` key, so a process with 415 MB showed about 802 MB.
**Fix:** each region counts once, `drm-total-*` preferred,
`drm-memory-*` only on kernels without it.
