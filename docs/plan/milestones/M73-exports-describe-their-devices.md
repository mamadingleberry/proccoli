# Milestone 73: Exports describe their devices

*✅ Done.* Was Idea 14. The history keeps each device's description and properties when they change (schema 2); exports add a `machine` block, each device's details and changes in `export.json`, and `devices.csv`. Hardware addresses only with *Include Hardware Addresses*; never the host name

Was Idea 14 (kept below with its design). Steps I14.1–I14.5 as planned.

| Step | Create / change | Test |
|---|---|---|
| 73.1 | `core/history_db.py`: schema 2, `device_info` table, `record_info` (only on change, last row cached), `device_info(table, start, end)` | Unit: first sight writes, the same again doesn't, a change does; a new connection remembers; a range gets the row in effect and the changes; a version 1 database gains the table; a read-only old one returns none |
| 73.2 | `Monitor.described_properties()` (memory adds its modules, GPUs their detail source); `HistoryStore.commit` records each device once per commit | Unit: one row for two commits; a changed description adds one |
| 73.3 | `core/machine_info.py`: OS (`os-release`), kernel, architecture, DMI vendor, product and version, placeholders dropped | Unit with `FakeRoot`: all present; missing files and placeholders |
| 73.4 | `core/history_export.py`: `machine`, `devices` (details at the end, `since_utc`, `changes`, `as_of`), `devices.csv`, `IDENTIFYING`; `ui/export.py`: `export_details(ctx)`, `describe` and `settings` injected | Unit: the manifest; addresses only when asked; the CSV rows; an older history marked `as_of: export`; every property key on the fixture machines reviewed (`ExportPrivacyTest`); UI: the flow passes the details and the option |
| 73.5 | `export-hardware-addresses` key; Preferences → *History* → *Include Hardware Addresses*; README, [DESIGN §11](../../design/11-cross-cutting-concerns.md), [Idea 2's design](../../design/ideas/idea-02-metrics-history-in-a-sqlite-database.md), [Idea 14's design](../../design/ideas/idea-14-exported-statistics-describe-their-devices.md) | UI: the switch sets the key |

**Decisions on Idea 14's open questions:** (1) hardware addresses are
left out by default; (2) the `machine` block has the computer model and
OS; (3) no `README.txt`: `devices.csv` serves people without a JSON
viewer.

**Deviations from Idea 14, and why:**
- **Device details in a top-level `devices` list,** each naming its
  files, rather than repeated in every file entry (a device can have a
  detail and a minutes file).
- **No icon name:** it means nothing outside Proccoli.
- **`devices.csv` has a `files` column instead of `from_utc`:** the
  details are as they stood at the end of the export; when they changed
  is in `export.json`.
- **The option is a Preferences switch:** today's export has no dialog
  to hold it (Idea 7 would add one, and the switch can move there).
