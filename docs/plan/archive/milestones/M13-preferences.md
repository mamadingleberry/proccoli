# Milestone 13: Preferences

*✅ Done.* Includes the GPU page (now a per-GPU detailed-statistics switch)

| # | Create | Test |
|---|---|---|
| 13.1 | `ui/dialogs/preferences.py`: General page (units, network bits, temperature unit, refresh speed, graph grids, data points, sidebar details, description and meter type, normalize CPU) | Smoke: each row is bound to its setting key |
| 13.2 | Apps and Processes pages (column toggles), Devices page (virtual drives and interfaces) | Smoke |
| 13.3 | *(Superseded by the GPU tabs refactor; see Progress.)* **GPU** page (Proccoli-only): per-GPU backend choice (Automatic, or each supported candidate), "Start detailed statistics with administrator rights automatically" | Unit: the combo lists registry candidates for each GPU |
| 13.4 | Live application: changing any setting updates open pages without restarting | UI test: toggle the grid → graphs redraw |

**Done:** every setting from [DESIGN §11](../../../design/11-cross-cutting-concerns.md) is in Preferences and applies
immediately.
