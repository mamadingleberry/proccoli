# Bug 19: An idle Intel GPU's Overview card is a blank chart

Design note: [design/bugs/bug-19-an-idle-intel-gpu-s-overview.md](../../design/bugs/bug-19-an-idle-intel-gpu-s-overview.md)

*Fixed in v0.6.0.* As proposed, with two differences: the tests
use the i915 and xe file layouts on a fake root, since the reporter's
machine (and a capture of it) isn't available here; and the video figure
from the media GT goes to `decode`, which a GPU with `combined_video`
shows as its one *Video* line.

**Seen:** "why aren't GPU stats appearing on the overview page? it's just
a blank graph … it appears to be trying to display Intel GPU but that
individual pane is empty." On a Lenovo Legion with an Arrow Lake-U iGPU
(i915, `0000:00:02.0`) and an RTX 5060 Laptop GPU, GNOME on Wayland,
`prime-select` *on-demand*, with the laptop panel wired to the NVIDIA GPU
(`card1-eDP-1`). Every reading of the Intel GPU's summary was `None`
(usage, frequency, temperature, power, memory), tick after tick.

**Cause:**

1. **Nothing uses the Intel GPU.** gnome-shell, Xwayland and the rest
   render on the NVIDIA GPU (they hold `card1` and `renderD128`); no
   process has the Intel GPU's `card0` or `renderD129` open, and its
   frequency counters (`gt_act_freq_mhz`, `gt_cur_freq_mhz`) read 0:
   the GT is asleep in RC6.
2. **The summary source reads "no clients" as "no reading".**
   `GenericDrmBackend.refresh` takes usage from `gpu_busy_percent` (AMD
   only) or from the busiest engine in DRM fdinfo. With no clients the
   engine map is empty, so usage stays `None` rather than 0 %. The
   frequency is dropped too, because 0 MHz is treated as missing
   (`if mhz:`), and an iGPU has no `hwmon` for temperature or power.
3. **The detail source never runs here.** `intel_gpu_top` needs
   administrator rights. The window reads from the collector, which runs
   under the metrics profile (`gpu_elevate=False`) and never asks for a
   password, so the Intel GPU's Details stay off and can't fill the gap.

The NVIDIA GPU is unaffected: `nvidia-smi` reads its usage, memory,
power and temperature.

**Fix (proposed):**

1. **Usage from RC6 residency, without root:** i915 exposes
   `gt/gt<N>/rc6_residency_ms` per GT (render GT0, media GT1 on Meteor
   Lake and later) and xe exposes
   `device/tile<T>/gt<N>/gtidle/idle_residency_ms`; anyone can read them.
   Busy ≈ `100 × (1 − Δresidency / Δt)`. Used when fdinfo has no engine
   figures for the GPU; fdinfo's per-engine figures still win when there
   are clients. RC6 is entered a few ms after work stops, so this slightly
   overstates light loads; it reads 0 % for an idle GPU, which is the
   case that matters here.
2. **An idle frequency is a reading:** when the frequency file exists
   and reads 0, the summary says 0 Hz (the detail line "Idle"), not
   `None`; `GpuController.sample` stops treating 0 as missing.
3. **The media GT counts as video:** GT1's residency feeds the combined
   video figure when fdinfo has none, as `intel_gpu_top` does for i915.

| Step | Create / change | Test |
|---|---|---|
| B19.1 | `gpu/generic_drm.py`: a small residency sampler (pure: previous and current `(time, ms)` → percent) and its use in `refresh` for i915 and xe when fdinfo has no engines | Unit on a fixture `SysRoot`: residency advancing 1000 ms in 1 s gives 0 %, 250 ms gives 75 %; a counter that goes backwards (resume) gives `None` once, then resumes; fdinfo engines take precedence |
| B19.2 | `gpu/generic_drm.py`, `gpu/controller.py`: 0 MHz is a reading; the detail line says "Idle" | Unit: `gt_act_freq_mhz` = 0 gives `frequency_hz == 0` and the detail text "Idle" |
| B19.3 | Fixture of this machine's i915 sysfs (both GTs, no fdinfo clients) | Unit: the summary has a usage every tick; UI smoke: the Overview card for the fixture GPU draws a line at 0 % |
| B19.4 | [DESIGN §7](../../design/07-the-gpu-carve-out.md) (the summary source's sources of usage) and [Bug 19's design](../../design/bugs/bug-19-an-idle-intel-gpu-s-overview.md); README (*GPUs*: what the Intel card shows without administrator rights) | — |

**Done when:** an Intel GPU that nothing uses shows 0 % on its Overview
card and page, without a password, in the window and in the collector.
