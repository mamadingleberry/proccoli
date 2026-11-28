# Bug 21: An NVIDIA GPU too new for pci.ids is named "NVIDIA GPU"

Plan: [plan/bugs/bug-21-an-nvidia-gpu-too-new-for.md](../../plan/bugs/bug-21-an-nvidia-gpu-too-new-for.md)


*[PLAN.md, Bug 21](../../plan/bugs/bug-21-an-nvidia-gpu-too-new-for.md). Fixed.* Names came from `pci.ids` alone; a device ID it
doesn't list (`10de:2d59`, RTX 5060 Laptop GPU, on Ubuntu's `hwdata`)
fell back to the vendor prefix. The fix: for the `nvidia` driver, the
`Model:` line of `/proc/driver/nvidia/gpus/<slot>/information`
(world-readable, read through `SysRoot` at discovery) wins over
`pci.ids` ([§7.4](../07.4-backend-selection.md), *A GPU's name*).
