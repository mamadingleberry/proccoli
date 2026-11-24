# Proccoli

<img src="data/icons/hicolor/scalable/apps/io.github.mamadingleberry.Proccoli.svg" width="96" alt="Proccoli logo: a gauge whose needle is a broccoli">

*Process + broccoli.*

Proccoli is a system monitor for the Linux desktop. It shows what your
processor, memory, graphics card, drives, network and battery are doing,
and which apps and processes are using them. It looks and works like
**Resources**, the system monitor that ships with Ubuntu, and adds detailed
statistics for Intel graphics.

## What it shows

Each part of your computer has its own entry in the sidebar, with a small
live chart:

| Entry | What you'll find |
|---|---|
| **Overview** | A live chart for every device at a glance, and the ten busiest apps and processes. Click a chart or row to open its page. |
| **Apps** | The apps you're running, with the processor, memory, drive and graphics use of all their processes combined |
| **Processes** | Every process on the system, with columns you can choose |
| **Processor** | Total usage (or one chart per core), speed, temperature and processor details |
| **Memory** | Memory and swap usage, and the memory modules' type and speed (e.g. "16.0 GB DDR4 @ 2667 MT/s") |
| **GPU** (one per graphics card) | Usage, video engines, video memory, speed, power and temperature. On Intel graphics, *Details* and *Processes* tabs add per-engine statistics and per-app graphics use. |
| **Drives** (one per drive) | How busy the drive is, read and write speeds, and totals |
| **Network** (one per connection) | Download and upload speeds, and totals |
| **Battery** (if you have one) | Charge, power draw and battery health |

Drives and network connections come and go as you plug them in or
remove them.

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
  - `pkexec` (package `pkexec` or `policykit-1`): actions that need
    administrator rights
  - `dmidecode`: memory module details on systems that don't report them
    otherwise
  - NetworkManager: Wi-Fi network names

## Installing

From the project folder, build a package and install it:

```sh
packaging/build-deb.sh
sudo apt install ./dist/proccoli_0.1.0_all.deb
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
  - The top-left corner always holds the Proccoli logo (click it for
    *About*) and the main menu (≡).
  - Hide or show the sidebar with ≡ → *Show Sidebar*, or press F9.
    Proccoli remembers your choice.
  - Without the sidebar, switch panes from the main menu: ≡ → *Go To*.
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
  - On Apps, *Switch To* brings the app's window to the front, for apps
    that support it.
  - Click a column header to sort by it, and type Ctrl+F to search.
- **Graphics details:** on an Intel GPU, open the *Details* tab for
  per-engine charts, frequency, power and memory bandwidth, and the
  *Processes* tab for each app's graphics use.
- **Narrow and portrait windows:** the sidebar folds away and opens over
  the page with ≡ → *Show Sidebar* (or F9). Charts rearrange to fit tall screens.
  On the Overview, the charts form a grid that fills as much of the
  window as it can without any chart becoming taller than it is wide.
  When they'd get too small, the busiest apps and processes move
  below them, a scroll away.

### Keyboard shortcuts

| Keys | Action |
|---|---|
| F9 | Show or hide the sidebar |
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
  - *Appearance:* style (Follow System, Light, Dark, Sand, Sky, Twilight,
    Midnight) and colour palette for the charts.
  - *Units:* data units, network speeds in bits, temperature unit.
  - *User Interface:* refresh speed, chart grids and axes, how much
    history charts show, normalised processor usage.
  - *Diagnostics:* the log's detail level and size, with a button to
    open its folder.
- **Sidebar:** the chart style, and for each entry, what it shows and
  where it sits.
- **Apps** and **Processes:** which columns to show.
- **Devices:** whether to list virtual drives and network connections.
- **GPU:** detailed statistics on or off per graphics card, and their
  refresh speed and history length.

## Files Proccoli keeps

- **Settings:** in your desktop's settings store (dconf), under
  `/io/github/mamadingleberry/Proccoli/`. To reset everything:
  `dconf reset -f /io/github/mamadingleberry/Proccoli/`
- **Diagnostics log:** `~/.local/state/proccoli/proccoli.log`, readable
  only by you. It's capped at 1 MiB by default, plus one older file. Set
  the size or turn it off in Preferences → General → *Diagnostics*.

## Troubleshooting

- **No Details tab on an Intel GPU:** install `intel-gpu-tools`.
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
