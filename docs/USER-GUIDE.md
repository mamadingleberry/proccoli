# Proccoli user guide

Everything Proccoli shows and does, every preference, the files it keeps,
and what to do when something goes wrong. The [README](../README.md) is
the short version.

## What it shows

Each part of your computer has its own entry in the sidebar, with a small
live chart. GPUs, drives, network connections and batteries sit beneath
a group entry for their kind (*GPUs*, *Drives*, *Network*, *Batteries*),
whose page compares them:

| Entry | What you'll find |
|---|---|
| **Overview** | A live chart for every device at a glance, with the processor's temperature and each graphics card's temperature and memory (used / total), and the ten busiest apps and processes. Click a chart or row to open its page. Proccoli always opens here. |
| **Apps** | The apps you're running, with the processor, memory, drive and graphics use of all their processes combined |
| **Processes** | Every process on the system, with columns you can choose |
| **Processor** | Total usage, or one chart with a line per core and a legend in the same space (in the legend, click a core to hide or show its line, or right-click it to show only that core, and right-click again for all; deselecting the last core shown brings them all back; in a small window, hover over a core for its usage); speed, temperature and processor details |
| **Memory** | Memory and swap usage, and the memory modules' type and speed (e.g. "16.0 GB DDR4 @ 2667 MT/s") |
| **GPU** (one per graphics card) | Usage, video engines, video memory, speed, power and temperature. On Intel graphics, *Details* and *Processes* tabs add per-engine statistics and per-app graphics use. On NVIDIA graphics, a *Details* tab adds utilisation, video engines, memory, clocks, temperature, power and fan from NVIDIA's own tools. On AMD graphics, a *Details* tab adds utilisation, engines, memory, clocks, temperatures, power, voltages and fan, with nothing extra to install. |
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
  The background recorder alone (`proccoli`, below) needs only
  `python3-gi`: no GTK, no desktop.
- **Optional:**
  - `intel-gpu-tools`: the detailed statistics for Intel graphics (AMD
    graphics need nothing extra)
  - NVIDIA's driver with `nvidia-settings` and/or `nvidia-smi` (from the
    driver's `nvidia-utils` package): the detailed statistics for NVIDIA
    graphics
  - `pkexec` (package `pkexec` or `policykit-1`): actions that need
    administrator rights
  - `dmidecode`: memory module details on systems that don't report them
    otherwise
  - NetworkManager: Wi-Fi network names

## Installing

Proccoli comes in two parts:

- **`proccoli-gui`:** the window.
- **`proccoli`:** the history and its background recorder. It
  needs no graphical libraries, so it can go on its own onto a server or
  any machine without a screen.

Installing `proccoli-gui` brings `proccoli` with it. Building the
packages needs `dpkg-deb` (on every Debian and Ubuntu system).

### The whole app

From the project folder:

```sh
packaging/build-deb.sh
sudo apt install ./dist/proccoli_0.6.0_all.deb ./dist/proccoli-gui_0.6.0_all.deb
```

Proccoli then appears in your app grid; from a terminal, the window is
`proccoli-gui`. Installing over an older Proccoli keeps your history and
settings. Before 0.5.0 the recorder was called `proccoli-metrics` and
the window `proccoli`; installing 0.5.0 removes the old
`proccoli-metrics` package and switches its recorder over to the new
name. `proccoli` starts recording at once for everyone logged in, and at
every log-in after that.

### Only the recorder

On a machine without a screen, install only `proccoli` (build the
packages there, or build them elsewhere and copy the file over):

```sh
sudo apt install ./dist/proccoli_0.6.0_all.deb
proccoli --start-at-boot                 # optional: record from boot
proccoli --status                        # is it recording?
```

Its history is the same file the window uses, so installing the window
later shows everything recorded so far.

### Updating

Build again and install the same way. If the version number hasn't
changed (a build of work in progress), add `--reinstall`, or apt skips
packages it thinks it already has:

```sh
sudo apt install --reinstall ./dist/proccoli_0.6.0_all.deb \
     ./dist/proccoli-gui_0.6.0_all.deb
```

Quit Proccoli first; a running recorder picks up the new version the next
time it starts (`systemctl --user restart proccoli`).

### Without a package

`sudo packaging/install.sh` installs into `/usr/local` (`PREFIX=/usr` for
`/usr`): both parts by default, or `--metrics` for the recorder alone
(add `--gui` later for the window, which needs the recorder's part).

### From the folder, without installing

```sh
PYTHONPATH=src python3 -m proccoli            # the window (proccoli-gui)
PYTHONPATH=src python3 -m proccoli.metrics    # the recorder (proccoli), in the foreground (Ctrl+C stops it)
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
  - **Groups:** GPUs, Drives, Network and Batteries each have a group
    entry with their devices indented beneath it. The group's page shows
    a card per device side by side; Network and Drives also show their
    total (download and upload, reads and writes) on the group's entry.
    Click the arrow on a group to hide or show its devices; Proccoli
    remembers. A device moves only within its group; a group moves with
    its devices.
- **Apps and Processes:**
  - Right-click a row for *Information*, *End*, *Kill*, *Halt* and
    *Continue*. Processes also has *Options*, for priority and which
    processor cores the process may use.
  - On Apps, *Switch To* brings the app's window to the front. GNOME lets
    an app bring only its own windows forward, so for apps that can't be
    asked to show themselves (Firefox, VS Code and many others) Proccoli
    needs its small GNOME Shell extension: Preferences → System →
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
  memory than ten minutes, and 30 days no more than a day; a short spike
  looks smaller there than at a shorter range. Beyond a day, charts are
  drawn from each minute's average in the history, so 30 days is the
  longest range. Without *Keep History*, a chart only shows this run, and
  at a long range each point appears once its readings are in (at 30
  days, every 36 minutes).
- **Toolbar:** under each page's title, buttons for what you change
  most while looking at charts: *Time Range* (its *Custom…* sets any
  range from 10 seconds to 30 days), *Graph Axes* and *Graph Grid*. Each has its name above it; the menus show their
  current choice, and the switches slide right and take the accent
  color when on. On the Processor page, a *Logical CPUs* switch is
  always at the end. The toolbar shows only on pages with charts, and
  every switch applies to every chart: *Graph Grid* draws grid lines on
  the page's charts, the Overview cards and the sidebar's charts alike.
  The ⋮ menu at its right end (or a right-click on it) removes or adds
  back *Time Range*, *Graph Axes* and *Graph Grid*. Drag one to move it, or focus it and press Ctrl+Shift+Left or Right. *Reset
  Toolbar* puts it back as it was. Changes show in Preferences too, and
  the other way round. To give the charts the room, turn it off: the
  logo → *Show Toolbar*; the Processor page then shows its own *Show
  Usages of Logical CPUs* switch instead.
- **How Proccoli reads and records:** a small helper, `proccoli`,
  takes every reading and keeps the history, from when you log in,
  window or not; the window shows what it sends and reads nothing itself.
  It's on for everyone once installed, and opening Proccoli starts it if
  it isn't running. *Start at Boot* (Preferences → *Recording*)
  also has it record before you log in and after you log out; the
  first time Proccoli opens with it off, it asks once whether to turn it
  on (for your account only). If the
  window stops getting readings, a banner above the pages says so, with
  *Try Again*. It has no window and never asks for a password, so Intel
  GPU *Details*, which need one, aren't available for now (the other
  readings of an Intel GPU are). It uses about 35 MiB of memory and
  around 1 % of one processor core. On the *Apps* page it counts as part
  of Proccoli; on *Processes* it's `proccoli`. *Recording* in
  Preferences says since when. From a terminal: `proccoli
  --status` says the same (and whether it records from boot), `proccoli
  --watch` prints each reading as it's taken, and `proccoli
  --start-at-boot` or `--no-start-at-boot` turns recording from boot on
  or off.
- **Exporting statistics:** the logo → *Export Statistics…* (or
  Preferences → *Recording* → *Export…*) saves every reading
  since Proccoli started to a folder you choose. Proccoli makes a new
  folder there (`proccoli-statistics-20261124T101530Z`), so nothing is
  overwritten. It holds one CSV file per device, which opens in any
  spreadsheet: the first column is the time in UTC (for example
  `2026-11-24T05:05:15.244Z`) and the others name the reading and its
  unit (`usage_percent`, `temperature_celsius`, `read_bytes_per_second`,
  `used_bytes`). If Proccoli has been running longer than it keeps every
  reading (a day, by default), the earlier part is in a
  `…-minutes.csv` file with each minute's average, minimum and maximum.
  `export.json` lists the files, devices and units. It also says what
  each device is (its description and the details its page lists under
  *Properties*, such as the model, driver or capacity, and anything that
  changed while it was recorded) and which computer, operating system,
  kernel and Proccoli version the readings came from. `devices.csv` has
  the same device details for a spreadsheet, one row per detail. The
  computer's name is never included, and neither are network cards'
  hardware addresses unless you turn on Preferences → *Recording* →
  *Include Hardware Addresses*.
- **An Intel GPU nothing is using** shows 0 % and its speed as *Idle*,
  without a password (laptops that draw the desktop on another GPU often
  leave the Intel one asleep). Until a program opens it, its usage comes
  from how long the GPU spends asleep, which reads a little high for
  light loads.
- **Graphics details:** on an Intel GPU, open the *Details* tab for
  per-engine charts, frequency, power, memory bandwidth and interrupts,
  and the *Processes* tab for each app's graphics use. In a chart's
  legend, click a line to hide or show it, or right-click it to show only
  that line (right-click again for all). ⋮ → *Update Interval* sets how
  often `intel_gpu_top` takes a reading. On an NVIDIA GPU, the *Details*
  tab shows what NVIDIA's tools report, laid out the same way; its first
  line says which tool is in use. On an AMD GPU, the *Details* tab reads
  the driver's own statistics, so it needs no tool and no password. On a
  processor with built-in AMD graphics it also shows the processor's
  side: the package's power split into the cores and the rest of the
  chip, the hottest core's temperature, and what's holding the speed back
  (a power or temperature limit) under *Power*. Its *Engines* chart counts
  only the apps Proccoli can see (yours, or every app after *Show All
  Details*). On all three, the charts fill the window in
  columns, start in the GPU's sidebar color, show their readings in your
  units, and follow every chart preference (axes, grids, *Graph Time
  Range*) as soon as you change it. A chart with one line has no legend;
  its value is under its title. The GPU page's *Detailed Statistics* property says
  what Proccoli found for that card, or why there's nothing more.
- **Built-in AMD graphics:** such a GPU uses the computer's own memory.
  The *Overview* tab shows it as *Graphics Memory*: the part set aside
  for graphics plus the shared memory the GPU is using, and the *Video
  Memory* columns of Apps and Processes count both too. The power
  reading there is the whole processor's (*Processor Package Power*),
  because that's what the chip reports.
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
| Alt+Up / Alt+Down | Move the selected sidebar entry |
| Ctrl+Shift+Left / Right | Move the focused toolbar button |
| F2 (or Ctrl+,) | Preferences |
| F1 (or Ctrl+?) | Keyboard shortcuts |
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
Details…*. To stop the offer at start-up, turn off Preferences → System
→ *Ask for Administrator Rights at Start-Up*.

When you agree, your system asks for your password, and Proccoli runs a
small helper as administrator. The helper does only these specific jobs
and checks everything it's asked to do. These features need Proccoli to
be **installed**: a copy run straight from the project folder leaves them
off, because its files can be changed without administrator rights.

## Preferences

Open with F2 (or Ctrl+,) or from the main menu.

Six pages, chosen at the bottom; the search button finds any setting.

- **Appearance:**
  - *Style:* style and color palette. Styles: *Follow System*,
    *Light*, *Dark*; light tints (*Sand*, *Sky*, *Mint*, *Rose*,
    *Lavender*, *Paper*, *Solarized Light*, *Gruvbox Light*, *Catppuccin
    Latte*, *High Contrast Light*); dark tints (*Twilight*, *Midnight*,
    *Nord*, *Dracula*, *Gruvbox Dark*, *Solarized Dark*, *Catppuccin
    Mocha*, *Tokyo Night*, *Forest*, *Ember*, *Black*, *High Contrast
    Dark*). Palettes for the charts: *System* (your desktop's
    accent color first); five made to stay distinguishable with color
    blindness (*Okabe–Ito*, *Tol Bright*, *Tol Vibrant*, *Tol Muted*,
    *Viridis*); data-visualization sets (*Tableau 10*, *Matplotlib*,
    *ColorBrewer Set 1* and *Dark 2*); editor themes (*Catppuccin*,
    *Gruvbox*, *One*, *Tokyo Night*); and terminal schemes (*GNOME*,
    *Tango*, *Solarized*, *Linux Console*, *XTerm*, *Rxvt*, *Nord*).
  - *Graphs:* axes, grids, and *Graph Time Range* (how much time charts
    show, whatever the update interval: 30 seconds to a day, or
    *Custom…*, any number of seconds, minutes, hours or days from 10
    seconds to 30 days).
  - *Units:* data units, network speeds in bits, temperature unit.
- **Sidebar:** full entries or icons only, the *Graph Type* (an area
  chart or a progress bar), and for each entry what it shows, where it
  sits, and its own *Graph Type* if it should differ from the rest
  (*Default* follows the one for all entries).
- **Tables:** *Normalize Processor Usage* (on, each app's or process's
  processor use is its share of the whole processor, so the column adds
  up to the total; off, one fully busy core is 100 %, as in `top`), *Show
  Niceness Values*, and which columns *Apps* and *Processes* show (each
  list opens in place).
- **Recording:**
  - *History:* keep a history of every reading (on by default), how many
    hours every reading is kept, the most it may take on disk (512 MiB by
    default).
  - *In the Background:* *Record in the Background* (off turns the
    recorder off, and with it the window's readings, until Proccoli is
    opened again) and *Start at Boot*.
  - *Exports:* whether exports include network cards' hardware addresses
    (off by default).
  - *Status and Actions:* since when it's been recording, how much the
    history takes now with *Delete History…*, and *Export…*.
- **Devices:** whether to list virtual drives and network connections;
  detailed GPU statistics on or off per graphics card, and how often
  `intel_gpu_top` takes a reading (how much time their charts show is
  the *Graph Time Range*).
- **System:**
  - *Memory Use:* *Lightweight Mode* (see *Lightweight mode* below).
  - *Readings:* *Update Interval* (how often Proccoli takes readings:
    every 1, 2, 3, 5 or 10 seconds; 1 by default. It replaced *Refresh
    Speed*, whose fastest choices went too fast; a choice you made there
    carries over).
  - *Administrator Rights:* whether to offer them at start-up.
  - *Window Switching:* whether the extension that lets *Switch To*
    reach every app is on, with a button to install or turn it on.
  - *Diagnostics:* the log's detail level and size, with a button to
    open its folder.

## Lightweight mode

For older machines, or to leave Proccoli running all day: Preferences →
System → *Memory Use* → *Lightweight Mode*, then *Restart Now* (or start
it once with `proccoli --lightweight`). Proccoli then uses less than half
the memory and processor time of the full window:

- pages are built when you open them, and let go a minute after you leave;
- the Overview lists every device's readings with a small chart of its
  recent use, and the five busiest apps and processes (without icons);
- each device page draws only its main chart; the others show their
  figures as text;
- the sidebar is *Icons Only* or *Hidden* (logo → *Sidebar*), so the
  charts are on the Overview, in one place;
- charts show at most a minute, without axes or grids, and there's no
  toolbar;
- Apps and Processes show name, ID, processor and memory, without icons;
- it draws without the graphics card's 3D driver (plain software drawing,
  which takes far less memory);
- the system style and colors are used, the log keeps only warnings,
  and GPU detailed statistics aren't started.

Your own choices for all of these are kept and come back when you turn
the mode off. Preferences says so at the top of each page that has some,
and shows them greyed out with a padlock (point at it for why); its
*Lightweight Mode* switch shows the mode Proccoli is running in; flip it
and *Restart Now* to change.

## Files Proccoli keeps

- **Settings:** in your desktop's settings store (dconf), under
  `/io/github/mamadingleberry/Proccoli/`. To reset everything:
  `dconf reset -f /io/github/mamadingleberry/Proccoli/`
- **History:** `~/.local/state/proccoli/history.sqlite3`, readable only
  by you. Every reading Proccoli shows, with times in UTC: every reading
  for a day (*Keep Every Reading For*), then each minute's average,
  minimum and maximum for 30 days, then each hour's for as long as there's
  room. It also notes what each device is (its description and details)
  whenever that changes, so exports can say so. That's typically 40–50
  MiB after a year and about 120 MiB after
  ten; it never grows past *Maximum Size* (512 MiB by default), dropping
  the oldest hours first. Turn it off, change the limits, or delete it in
  Preferences → *Recording*. Older versions of Proccoli kept CSV
  files in `~/.local/state/proccoli/stats/`; they're moved into the
  history the first time this version starts, and the folder is removed.
- **Background recording:** `proccoli` keeps its own log beside
  the window's, `~/.local/state/proccoli/proccoli.log`, with the
  same level and size limit, and `history.lock` there says which of the
  two is writing the history. Its systemd user unit is
  `proccoli.service` (`journalctl --user -u proccoli`
  shows its messages too). One recorder per user is enough: started
  again while one runs, `proccoli` says which process records and exits.
  If it stops for any reason other than `systemctl --user stop
  proccoli`, systemd starts it again within 10 seconds.
- **Diagnostics log:** the window's is
  `~/.local/state/proccoli/proccoli-gui.log` (`proccoli.log` before
  0.5.0, which is now the recorder's), readable
  only by you. By default it records everything (*Everything (Debug)*),
  with times in UTC (for example `2026-11-23T21:41:25.154Z`). It's capped
  at 1 MiB by default, plus one older file. Set the level or size, or turn
  it off, in Preferences → System → *Diagnostics*.

## Troubleshooting

- **No Details tab on an Intel GPU:** install `intel-gpu-tools`.
- **No Details tab on an AMD GPU:** older AMD cards use the `radeon`
  driver, which doesn't publish these statistics; only cards using
  `amdgpu` get the tab. The GPU page's *Detailed Statistics* property
  says which applies.
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
  log (Preferences → System → *Diagnostics* → *Open Folder*). If the
  window ever stops responding for more than a few seconds, Proccoli
  writes details of where it was stuck there.

## Uninstalling

```sh
systemctl --user disable --now proccoli   # if you turned on background recording
sudo apt remove proccoli-gui proccoli   # if you installed the packages
sudo packaging/install.sh --uninstall  # if you used install.sh
```

To keep the recorder but remove the window: `sudo apt remove proccoli-gui`, or `sudo packaging/install.sh --gui --uninstall`.
Removing Proccoli never deletes your history or settings; *Files
Proccoli keeps* (above) says where they are.
