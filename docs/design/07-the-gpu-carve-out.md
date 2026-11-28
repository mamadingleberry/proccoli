# 7. The GPU carve-out

This is the one place where Proccoli differs from Resources on purpose. Every
GPU gets **one page with up to three tabs**:

| Tab | Content | Comes from |
|---|---|---|
| **Overview** | Resources' GPU page (usage, video engine, VRAM, frequency, power, temperature, properties) | the GPU's **summary source**, which always runs |
| **Details** | the vendor's own view: for Intel, intel_gpu_top_gui's graph grid (per-engine utilisation, frequency, power, RC6, memory bandwidth, interrupts); for NVIDIA, its tools' readings (v0.2.0); for AMD, amdgpu's own statistics files (v0.5.0) | the GPU's **detail source**, if one exists |
| **Processes** | the vendor's per-process view: for Intel, engine-class use per client | the detail source |

The Overview is always first. The vendor tabs are a second level of
information for the same GPU, so they're **tabs, not a drill-down**:

- **Peer views, switched often.** Engine graphs and the summary are both
  "now" views that users flip between while monitoring. Tabs are one click
  each way with no back button.
- **intel_gpu_top_gui's own shape.** Its Resources | Processes switcher maps
  one-to-one onto Details | Processes.
- **No tabs without a vendor tool.** A GPU without a detail source shows no
  switcher, just the overview, exactly like Resources.
- **The overview links to the details.** It has a "Detailed Statistics"
  row, so they're discoverable from the Resources-style view.
