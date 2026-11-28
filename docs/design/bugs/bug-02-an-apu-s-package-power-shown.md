# Bug 2: An APU's package power shown as the GPU's

Plan: [plan/bugs/bug-02-an-amd-apu-s-package-power.md](../../plan/bugs/bug-02-an-amd-apu-s-package-power.md)


*[PLAN.md, Bug 2](../../plan/bugs/bug-02-an-amd-apu-s-package-power.md). Fixed in v0.5.0.* On an AMD APU hwmon has one
power reading, `power1` labelled `PPT`: the whole package's, processor
cores included (34 W under an all-core load with the GPU idle on a Ryzen
3 4300U). The generic source showed it as the GPU's *Power Usage*.
**Fix:** `GpuSummary.power_is_package`, set for an AMD APU; the Overview
tab calls it *Processor Package Power*. The AMD Details tab splits it
(cores, SoC; the GPU's own when the firmware reports it).
