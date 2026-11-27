# Bug 6: An AMD GPU's fdinfo is read twice per update

Design note: [design/bugs/bug-06-an-amd-gpu-s-fdinfo-was.md](../../design/bugs/bug-06-an-amd-gpu-s-fdinfo-was.md)

*Fixed in Milestone 75.*

**Seen:** profiling `proccoli-metrics` showed `FdinfoReader.read` called
twice per update for the Ryzen's Vega 6, about half of each update's
time. The window did the same.

**Cause:** the GPU's summary backend (`GenericDrmBackend`) and its AMD
Details backend (`AmdgpuBackend`, M70) each built their own
`FdinfoReader` for the same GPU, so every process's DRM `fdinfo` files
were read and parsed twice.

**Fix:** `GpuDeps.fdinfo` holds one reader per GPU, `fdinfo.shared_reader`
hands it to both backends, and a second `read()` at the same update time
does nothing. 1.33 % → 1.08 % of one core in the collector.

| Step | Create / change | Test |
|---|---|---|
| B6.1 | `gpu/backend.py` (`GpuDeps.fdinfo`), `gpu/fdinfo.py` (`shared_reader`, the same-time check), `generic_drm.py`, `amdgpu/backend.py` | `test_amdgpu.SharedFdinfoTest`: one reader, two reads for two updates (four without the fix) |
