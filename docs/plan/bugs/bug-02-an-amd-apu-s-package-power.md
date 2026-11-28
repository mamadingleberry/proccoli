# Bug 2: An AMD APU's package power is shown as the GPU's

Design note: [design/bugs/bug-02-an-apu-s-package-power-shown.md](../../design/bugs/bug-02-an-apu-s-package-power-shown.md)

*Fixed in v0.5.0.*

**Seen:** on a Ryzen 3 4300U (Radeon Vega 6), the GPU page's *Power
Usage* read 34 W under an all-core processor load with the GPU at 3 %.

**Cause:** an APU's hwmon has one power reading, `power1` labelled
`PPT`: the whole package's, processor cores included. The generic source
reports `power1` as the GPU's power for every GPU.

**Fix:** `GpuSummary.power_is_package` for an AMD APU, and the Overview
tab names the row *Processor Package Power*. The AMD Details tab (v0.5.0)
splits the package into cores and SoC from `gpu_metrics`.

| Step | Create / change | Test |
|---|---|---|
| B2.1 | `GpuSummary.power_is_package`; `GenericDrmBackend` sets it for an AMD APU | Unit on the fixture |
| B2.2 | `GpuPage`: `power_title` | UI: the APU's title; a discrete GPU's unchanged |
