# Idea 14: Exported statistics describe their devices

Design note: [design/ideas/idea-14-exported-statistics-describe-their-devices.md](../../design/ideas/idea-14-exported-statistics-describe-their-devices.md)

*Done as Milestone 73* (its decisions and deviations are listed there).

**Goal:** an export can be read on its own, months later or on another
machine. Next to the readings it says **what each device is**: its
sidebar name and **description** ("wlp43s0", "Ryzen 3 4300U with Radeon
Graphics"), and the **details** its page shows under *Properties*
(model, driver, capacity, cores, link speed...), plus the machine they
came from and the Proccoli version.

**Why:** today a file is named after the device ID
(`gpu-0000-03-00.0.csv`), and `export.json` adds only the name and kind.
Someone looking at the numbers can't tell which GPU, drive model or
network interface they belong to, which matters when comparing two
machines or sending the files with a bug report.

**What's missing today:** the history's `device` table keeps only `id`,
`name` and `kind` (M62). `DeviceInfo` also has `description` and
`properties` (what the page's *Properties* list shows), but they're never
stored, so an export of earlier sessions can't know them, and they can
change (a new driver, a different connection name, battery health going
down).

**Design ([Idea 14's design](../../design/ideas/idea-14-exported-statistics-describe-their-devices.md)):**

- **Stored with the history:** a new table `device_info (tbl, time,
  description, properties)`, where `properties` is JSON. A row is
  written when a device is first recorded in a run **and only when
  something changed** since its last row, so it costs a few rows per
  device, not one per reading. `HistoryDb.device_info(tbl, start_ms,
  end_ms)` returns the rows in effect over a range (the last one before
  the start, then every change in it). Schema version 2: the table is
  added on open (`CREATE TABLE IF NOT EXISTS`, nothing to migrate); an
  older Proccoli opening a version 2 database just doesn't see it.
- **Facts, not readings:** `properties` is what describes the device
  (model, driver, capacity); readings already in a CSV column aren't
  stored twice. Slow-changing facts like *Battery Health* are why a
  change writes a new row.
- **In the export:**
  - `export.json`: each file's device gets `description`, `icon`,
    `properties` (as in effect at the end of the range) and, when they
    changed during it, `changes` (time and the values that changed).
    A top-level `machine` block: Proccoli version, operating system
    (`/etc/os-release` `PRETTY_NAME`), kernel release, architecture,
    and the computer's model (DMI vendor and product, through
    `SysRoot`, already read for memory devices). Times in UTC as
    elsewhere.
  - `devices.csv`: for spreadsheets, one row per device and property in
    long form: `file, device_id, name, kind, description, property,
    value, from_utc`. Long form because every kind of device has
    different properties.
  - Devices recorded before this version (no `device_info` rows): the
    name and kind as today, and the current description and properties
    if the device is present now, marked `"as_of": "export"`.
- **Privacy:** an export is often shared. *Hardware Address* (a network
  card's MAC) and the host name identify the machine, so they're left
  out by default; the export dialog (Idea 7) gets *Include Hardware
  Addresses*. Nothing else in *Properties* is personal (no serial
  numbers are shown today; a static test keeps a list of the property
  keys that are left out, so a new identifying one has to be added to
  it on purpose).
- **Works with Idea 7 and Idea 13:** any range, and whichever process
  writes the history writes `device_info` the same way
  (`HistoryStore`).

| Step | Create / change | Test |
|---|---|---|
| I14.1 | `core/history_db.py`: `device_info` table, `record_info` (writes only on change), `device_info(tbl, start, end)`; schema 2 | Unit (temporary database): first sight writes a row; the same info again writes none; a changed driver writes one; a range gets the row before it and the changes in it; a version 1 database gains the table |
| I14.2 | `core/history_store.py`: record each device's info on its first reading of a run and when `DeviceInfo` changes | Unit: two runs with the same info, one row; a run with a new description, two |
| I14.3 | `core/machine_info.py`: OS, kernel, architecture, computer model through `SysRoot` / `System` | Unit with fixtures (`/etc/os-release`, DMI files), and missing files |
| I14.4 | `core/history_export.py`: the `machine` block, device details and changes in `export.json`, `devices.csv`, identifying keys left out unless asked | Unit: the manifest for a fixture history; a MAC address absent by default and present with the option; an older history's devices marked `as_of: export`; static: the left-out keys list |
| I14.5 | Export dialog: *Include Hardware Addresses* (with Idea 7's dialog, or a switch in today's flow); README *Exporting statistics*; [Idea 14's design](../../design/ideas/idea-14-exported-statistics-describe-their-devices.md) as built | UI: the switch reaches `export_range` |

**Done when:** an export of any range lists, for every file, the device's
name, description and properties as they were during that range (and
what changed), names the machine and Proccoli version, has the same in
`devices.csv`, and leaves out the hardware address unless asked.

**Open questions for the user:**
1. Leave hardware addresses out by default (as designed), or always
   include them?
2. Is the computer's model and OS wanted in `machine`, or only the
   Proccoli version?
3. Besides `export.json` and `devices.csv`, a plain `README.txt` in the
   folder summarizing the devices for someone without a JSON viewer?
