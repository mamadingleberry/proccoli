# Milestone 19: Sidebar area charts

*✅ Done.*

Every sidebar entry except Apps and Processes shows a small area chart of
its recent usage, as Resources does.

| Step | Create / change | Test |
|---|---|---|
| 19.1 | `sidebar-meter-type` default becomes `graph` (the progress bar stays as an option) | Settings test |
| 19.2 | Sidebar graph: an area chart across the row's full width, 36 px high, grid hidden, rounded like page graphs | Widget test |
| 19.3 | `SidebarSummary.history` becomes `series` (a list): network shows receive and send (auto-scaled); CPU, memory, GPU, drives (busy time, as in Resources) and battery one percentage | Unit: every device page's summary has series; Apps/Processes have none |
| 19.4 | Screenshots of the sidebar in both meter types | `shoot.py` |

**Done when:** a fresh start shows area charts under Processor, Memory,
GPUs, drives, network interfaces and batteries, and none under Apps and
Processes.
