# Bug 21: An NVIDIA GPU too new for pci.ids is named "NVIDIA GPU"

Design note: [design/bugs/bug-21-an-nvidia-gpu-too-new-for.md](../../design/bugs/bug-21-an-nvidia-gpu-too-new-for.md)

*Fixed in v0.6.0.*

**Seen:** while diagnosing Bug 19: the RTX 5060 Laptop GPU (`10de:2d59`)
is listed, on its card, page and sidebar entry, as "NVIDIA GPU".

**Cause:** `discover_gpus` names a GPU from the system's `pci.ids`
(`pretty_name`). Ubuntu's `hwdata` doesn't list `10de:2d59` yet, so the
name falls back to the vendor prefix. The NVIDIA driver knows it:
`/proc/driver/nvidia/gpus/<slot>/information` says
`Model: NVIDIA GeForce RTX 5060 Laptop GPU` (world-readable), and
`nvidia-smi` returns the same `name` on every sample (`NvidiaSample.name`),
but neither is used for the name.

**Fix:** at discovery, for a GPU on the `nvidia` driver, read
the `Model:` line of the driver's `information` file through `SysRoot`
and prefer it to `pci.ids` (it already starts with "NVIDIA", as
`pretty_name` wants). It's a file
read, so discovery stays fast and the collector sends the right name to
the window in `describe()`; no renaming after start. `pci.ids` stays the
fallback (nouveau, a missing file).

| Step | Create / change | Test |
|---|---|---|
| B21.1 | `gpu/info.py`: `nvidia_model(sysroot, slot)` and `gpu_name()`, used by `discover_gpus` | `NvidiaNameTest`: the captured driver file (`tests/fixtures/nvidia/information-rtx5060-laptop.txt`) names the RTX 5060 (fails without the fix); without the file, "NVIDIA GPU"; on `nouveau` the file isn't asked; the `Model:` line's parsing |
| B21.2 | [DESIGN §7](../../design/07-the-gpu-carve-out.md) (where GPU names come from) and [Bug 21's design](../../design/bugs/bug-21-an-nvidia-gpu-too-new-for.md) | — |

**Done when:** a GPU the driver knows but `pci.ids` doesn't is listed by
its model name.

**Found while doing it:** on the reporting machine, discovery now gives
`['Intel Graphics', 'NVIDIA GeForce RTX 5060 Laptop GPU']`.
