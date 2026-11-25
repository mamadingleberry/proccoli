# Proccoli

<img src="data/icons/hicolor/scalable/apps/io.github.mamadingleberry.Proccoli.svg" width="96" alt="Proccoli logo: a gauge whose needle is a broccoli">

*Process + broccoli.*

Proccoli is a system monitor for the Linux desktop. It shows what your
processor, memory, graphics card, drives, network and battery are doing,
and which apps and processes are using them. It looks and works like
**Resources**, the system monitor that ships with Ubuntu, and adds detailed
statistics for Intel and NVIDIA graphics.

## What it shows

Each part of your computer has its own entry in the sidebar, with a small
live chart:

| Entry | What you'll find |
|---|---|
| **Overview** | A live chart for every device at a glance, with the processor's temperature and each graphics card's temperature and memory (used / total), and the ten busiest apps and processes. Click a chart or row to open its page. Proccoli always opens here. |
| **Apps** | The apps you're running, with the processor, memory, drive and graphics use of all their processes combined |
| **Processes** | Every process on the system, with columns you can choose |
| **Processor** | Total usage, or one chart with a line per core and a legend in the same space (in the legend, click a core to hide or show its line, or right-click it to show only that core, and right-click again for all; deselecting the last core shown brings them all back; in a small window, hover over a core for its usage); speed, temperature and processor details |
| **Memory** | Memory and swap usage, and the memory modules' type and speed (e.g. "16.0 GB DDR4 @ 2667 MT/s") |
| **GPU** (one per graphics card) | Usage, video engines, video memory, speed, power and temperature. On Intel graphics, *Details* and *Processes* tabs add per-engine statistics and per-app graphics use. On NVIDIA graphics, a *Details* tab adds utilisation, video engines, memory, clocks, temperature, power and fan from NVIDIA's own tools. |
| **Drives** (one per drive) | How busy the drive is, read and write speeds, and totals |
| **Network** (one per connection) | Download and upload speeds, and totals |
| **Battery** (if you have one) | Charge, power draw and battery health |

Drives and network connections come and go as you plug them in or
remove them. If Proccoli can't read a device, its entry stays in the
sidebar and its page says what went wrong, with *Try Again*.

## Requirements

- **A recent Linux desktop:** Ubuntu 24.04 or newer, or Debian 13 or
  newer. Proccoli needs GTK 4.10 and libadwaita 1.5 or newer. It works on
  Wayland and on X11.
- **Python 3.10 or newer** with GTK bindings, all from the system's
  package manager:
  ```sh
  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
  ```
- **Optional:**
  - `intel-gpu-tools`: the detailed statistics for Intel graphics
  - NVIDIA's driver with `nvidia-settings` and/or `nvidia-smi` (from the
    driver's `nvidia-utils` package): the detailed statistics for NVIDIA
    graphics
  - `pkexec` (package `pkexec` or `policykit-1`): actions that need
    administrator rights
  - `dmidecode`: memory module details on systems that don't report them
    otherwise
  - NetworkManager: Wi-Fi network names

## Installing

From the project folder, build a package and install it:

```sh
packaging/build-deb.sh
sudo apt install ./dist/proccoli_0.3.0_all.deb
```

Proccoli then appears in your app grid. To install without a package
(into `/usr/local`), run `sudo packaging/install.sh` instead.

You can also run it straight from the folder without installing:

```sh
PYTHONPATH=src python3 -m proccoli
```

To look around without your own data, `--demo` shows made-up devices
and activity.

## Using Proccoli

- **Sidebar:**
  - The Proccoli logo in the top-left corner is the main menu: click it
    (or press F10) for *About Proccoli*, *Go To*, the sidebar's look,
    *Preferences* and more.
  - Choose how the sidebar looks from the logo → *Sidebar*: *Full*, *Icons
    Only* (a slim strip of icons; hover over one to see its name and
    usage) or *Hidden*. F9 hides it and shows it again as it was.
    Proccoli remembers your choice.
  - Without the sidebar, switch panes from the main menu: the logo →
    *Go To*.
  - Go back and forward through the panes you've visited with your mouse's
    back and forward buttons, or Alt+Left and Alt+Right.
  - Right-click an entry (or press the Menu key) to move it, minimise it
    to its name, or choose what it shows: name, description, usage and
    chart. You can also drag entries, or use Alt+Up and Alt+Down.
  - Overview, Apps and Processes always stay at the top.
- **Apps and Processes:**
  - Right-click a row for *Information*, *End*, *Kill*, *Halt* and
    *Continue*. Processes also has *Options*, for priority and which
    processor cores the process may use.
  - On Apps, *Switch To* brings the app's window to the front. GNOME lets
    an app bring only its own windows forward, so for apps that can't be
    asked to show themselves (Firefox, VS Code and many others) Proccoli
    needs its small GNOME Shell extension: Preferences → General →
    *Window Switching* → *Install* (or *Turn On* if Proccoli was installed
    as a package). After installing, log out and back in once. The
    extension can only list windows and bring one to the front. On an X11
    session, installing `wmctrl` works too.
  - Click a column header to sort by it, and type Ctrl+F to search.
- **Charts:** hover over a chart on a page or the Overview to see each
  line's value at that moment, and how long ago it was. With *Show Graph
  Axes* on, every chart has a value scale on its left: percentages, and
  speeds, clocks, power and temperatures in your *Data Unit Prefix*,
  network bits and *Temperature Unit*. Charts start
  full: when Proccoli starts, or you change the *Graph Time Range* or
  *Update Interval*, they show the readings it kept before, redrawn for
  the new range, and so do the GPU *Details* charts. The time Proccoli
  wasn't running is shaded with a dark dotted bar; hover over it to see
  how long that was. A plain break in a line means a reading was missing
  while Proccoli was running. Ranges of 30 minutes or more show each
  point as the average of several readings, so a day takes no more
  memory than ten minutes; a short spike looks smaller there than at a
  shorter range. Without *Keep History*, a chart only shows this run.
- **Exporting statistics:** the logo → *Export Statistics…* (or
  Preferences → General → *History* → *Export…*) saves every reading
  since Proccoli started to a folder you choose. Proccoli makes a new
  folder there (`proccoli-statistics-20261124T101530Z`), so nothing is
  overwritten. It holds one CSV file per device, which opens in any
  spreadsheet: the first column is the time in UTC (for example
  `2026-11-24T05:05:15.244Z`) and the others name the reading and its
  unit (`usage_percent`, `temperature_celsius`, `read_bytes_per_second`,
  `used_bytes`). If Proccoli has been running longer than it keeps every
  reading (a day, by default), the earlier part is in a
  `…-minutes.csv` file with each minute's average, minimum and maximum.
  `export.json` lists the files, devices and units.
- **Graphics details:** on an Intel GPU, open the *Details* tab for
  per-engine charts, frequency, power, memory bandwidth and interrupts,
  and the *Processes* tab for each app's graphics use. In a chart's
  legend, click a line to hide or show it, or right-click it to show only
  that line (right-click again for all). ⋮ → *Update Interval* sets how
  often `intel_gpu_top` takes a reading. On an NVIDIA GPU, the *Details*
  tab shows what NVIDIA's tools report, laid out the same way; its first
  line says which tool is in use. On both, the charts fill the window in
  columns, start in the GPU's sidebar color, show their readings in your
  units, and follow every chart preference (axes, grids, *Graph Time
  Range*) as soon as you change it. A chart with one line has no legend;
  its value is under its title. The GPU page's *Detailed Statistics* property says
  what Proccoli found for that card, or why there's nothing more.
- **Narrow and portrait windows:** the sidebar folds away and opens over
  the page with the logo → *Sidebar* → *Full* or *Icons Only* (or F9). Charts
  rearrange to fit tall screens.
  On the Overview, the charts form a grid that fills as much of the
  window as it can without any chart becoming taller than it is wide.
  When they'd get too small, the busiest apps and processes move
  below them, a scroll away.

### Keyboard shortcuts

| Keys | Action |
|---|---|
| F9 | Show or hide the sidebar |
| F10 | Open the main menu |
| Alt+Left / Alt+Right | Back / forward to the panes you visited |
| Ctrl+, | Preferences |
| Ctrl+? | Keyboard shortcuts |
| Ctrl+Q | Quit |
| Ctrl+F | Search Apps or Processes |
| Ctrl+I | Information about the selected app or process |
| Delete | End the selected app or process |
| Ctrl+Delete | Kill the selected app or process |

## Administrator rights

Proccoli can show and do most things without a password. A few things
need administrator rights:
- detailed Intel graphics statistics, on most systems;
- ending, halting or changing the priority of other users' processes;
- drive activity of other users' processes;
- memory module details, on systems that don't report them otherwise.

At start-up Proccoli offers to unlock these, and you can say *Not Now*.
Each page also keeps its own button, and the main menu has *Show All
Details…*. To stop the offer at start-up, turn off Preferences → General
→ *Ask for Administrator Rights at Start-Up*.

When you agree, your system asks for your password, and Proccoli runs a
small helper as administrator. The helper does only these specific jobs
and checks everything it's asked to do. These features need Proccoli to
be **installed**: a copy run straight from the project folder leaves them
off, because its files can be changed without administrator rights.

## Preferences

Open with Ctrl+, or from the main menu.

- **General:**
  - *Memory Use:* *Lightweight Mode* (see *Lightweight mode* above).
  - *Appearance:* style (Follow System, Light, Dark, Sand, Sky, Twilight,
    Midnight) and color palette for the charts.
  - *Units:* data units, network speeds in bits, temperature unit.
  - *User Interface:* *Update Interval* (how often Proccoli takes
    readings: every 1, 2, 3, 5 or 10 seconds; 1 by default. It replaced
    *Refresh Speed*, whose fastest choices went too fast; a choice you made
    there carries over), chart grids and axes, *Graph Time Range* (how
    much time charts show: 30 seconds to a day, whatever the update
    interval), and *Normalize Processor Usage*: on, each app's or
    process's processor use is its share of the whole processor (the
    column adds up to the total); off, one fully busy core is 100 %, as in
    `top`.
  - *Diagnostics:* the log's detail level and size, with a button to
    open its folder.
  - *Window Switching:* whether the extension that lets *Switch To*
    reach every app is on, with a button to install or turn it on.
  - *History:* keep a history of every reading (on by default), how many
    hours every reading is kept, the most it may take on disk (512 MiB by
    default), how much it takes now, *Delete History…* and *Export…*.
- **Sidebar:** full entries or icons only, the chart style, and for each
  entry, what it shows and where it sits.
- **Apps** and **Processes:** which columns to show.
- **Devices:** whether to list virtual drives and network connections.
- **GPU:** detailed statistics on or off per graphics card, and how
  often `intel_gpu_top` takes a reading. How much time their charts show is the *Graph Time
  Range*.

## Lightweight mode

For older machines, or to leave Proccoli running all day: Preferences →
General → *Memory Use* → *Lightweight Mode*, then *Restart Now* (or start
it once with `proccoli --lightweight`). Proccoli then uses about half the
memory while it shows the Overview:

- pages are built when you open them, and let go a minute after you leave;
- the Overview is a list of every device's readings, without charts or
  the busiest apps and processes;
- each device page draws only its main chart; the others show their
  figures as text;
- the sidebar shows a usage bar instead of a chart;
- charts show at most a minute, without axes or grids;
- Apps and Processes show name, ID, processor and memory, without icons;
- the system style and colors are used, the log keeps only warnings,
  and GPU detailed statistics aren't started.

Your own choices for all of these are kept and come back when you turn
the mode off. Preferences shows the ones the mode fixes greyed out.

## Files Proccoli keeps

- **Settings:** in your desktop's settings store (dconf), under
  `/io/github/mamadingleberry/Proccoli/`. To reset everything:
  `dconf reset -f /io/github/mamadingleberry/Proccoli/`
- **History:** `~/.local/state/proccoli/history.sqlite3`, readable only
  by you. Every reading Proccoli shows, with times in UTC: every reading
  for a day (*Keep Every Reading For*), then each minute's average,
  minimum and maximum for 30 days, then each hour's for as long as there's
  room. That's typically 40–50 MiB after a year and about 120 MiB after
  ten; it never grows past *Maximum Size* (512 MiB by default), dropping
  the oldest hours first. Turn it off, change the limits, or delete it in
  Preferences → General → *History*. Older versions of Proccoli kept CSV
  files in `~/.local/state/proccoli/stats/`; they're moved into the
  history the first time this version starts, and the folder is removed.
- **Diagnostics log:** `~/.local/state/proccoli/proccoli.log`, readable
  only by you. By default it records everything (*Everything (Debug)*),
  with times in UTC (for example `2026-11-23T21:41:25.154Z`). It's capped
  at 1 MiB by default, plus one older file. Set the level or size, or turn
  it off, in Preferences → General → *Diagnostics*.

## Troubleshooting

- **No Details tab on an Intel GPU:** install `intel-gpu-tools`.
- **NVIDIA details come from nvidia-smi, not nvidia-settings:**
  `nvidia-settings` can only read usage in an X11 session. In a Wayland
  session (Ubuntu's default) Proccoli uses `nvidia-smi` instead, and the
  *Details* tab says so. The open `nouveau` driver isn't supported by
  NVIDIA's tools.
- **A page says a device "isn't available":** Proccoli couldn't read it.
  The page says why; *Technical Details* has more (*Copy Details* copies
  it for a bug report), and *Try Again* tries once more.
- **"Show Detailed Statistics" or process actions do nothing:** make sure
  Proccoli is installed (not only run from the folder) and that `pkexec`
  is installed.
- **Something looks wrong or the window stops responding:** check the
  log (Preferences → General → *Diagnostics* → *Open Folder*). If the
  window ever stops responding for more than a few seconds, Proccoli
  writes details of where it was stuck there.

## Uninstalling

```sh
sudo apt remove proccoli               # if you installed the package
sudo packaging/install.sh --uninstall  # if you used install.sh
```

## Disclaimer

This application was created with the help of
[Claude](https://claude.com/claude-code), an AI assistant made by Anthropic.
It is an independent project and is not affiliated with or endorsed by
Intel, GNOME or the authors of Resources.

## License

[0BSD](LICENSE): use it for anything, no fee and no attribution required.
