# Feature 16: A Web GUI, hosted locally (brainstorm)

Design note: [design/features/feature-16-a-web-gui-hosted-locally.md](../../design/features/feature-16-a-web-gui-hosted-locally.md)

**Goal:** see Proccoli in a browser: the Overview, each device's charts
and the history, served by the machine itself, without GTK. Useful on a
machine without a desktop (with `proccoli-metrics` from Feature 15), from a
phone on the couch, or in a second monitor's browser tab.

**Status: a brainstorm, not a design yet.** The choices below need the
user's answers before steps can be written.

**What already makes it possible:**
- **The data is already separate from the window:** the history
  database (v0.3.0, with device details since v0.5.0) and, with Feature 13, a
  display-free process that keeps it current. A web server inside
  `proccoli-metrics` can read the same `Monitor`s and the same database.
- **The rules for charts are display-free:** time ranges and points
  (`ticker.history_plan`), units and formatting (`core/units.py`),
  palettes (`core/palette.py`), axes ticks (`ui/axes.py` is pure). A web
  page can be sent ready-to-draw series, so the browser only draws.

**Where it runs (options):**

| | Inside `proccoli-metrics` | Its own process, `proccoli-web` |
|---|---|---|
| Live readings | the collector's own, no second reader | reads the database (10 s behind) or asks the collector |
| Install | one service | one more unit, its own package (Feature 15) |
| Failure | a web bug can stop recording | isolated |

*Leaning:* inside `proccoli-metrics`, off by default, behind a setting;
split later if it grows.

**How it's served, with only system packages** (no pip, no build step,
the project's rule):
- **Server:** Python's `http.server` on its own thread, or
  `Gio.SocketService` on the main loop (already a dependency, no
  threads). JSON for data; **Server-Sent Events** for live readings
  (one-way, plain HTTP, reconnects by itself, no WebSocket library).
- **Page:** static HTML, CSS and plain JavaScript modules shipped with
  Proccoli, no framework and no bundler. Charts drawn on `<canvas>` with
  the same look (fill, axes, the "not running" dither of v0.4.0) from a
  small hand-written drawing module, or SVG. No CDN: everything is
  served locally, so it works offline and leaks nothing.
- **API sketch:** `GET /api/devices` (with details, v0.5.0),
  `GET /api/history?device=…&range=1-hour` (points ready to draw, from
  `HistoryDb.buckets`), `GET /api/live` (SSE: every reading),
  `GET /api/processes?top=10` (optional, see privacy).

**Security, which decides most of the design:**
- **Listens on `127.0.0.1` only by default:** a browser on the same
  machine, nothing else. Listening on the network is Feature 17's question.
- **Even on localhost, other users and web pages can reach a local
  port:** so a random per-user token in the URL or a cookie (printed by
  `proccoli-metrics --web-url`, opened by the GUI's *Open in Browser*),
  `Host` header checks against DNS rebinding, no CORS, and only `GET`.
- **Read-only:** no ending processes or changing priorities from the
  web, ever, at least to start: those need the root helper and a
  password prompt the browser can't show safely.
- **Process names and command lines are personal:** off by default in
  the web view, a setting to turn on.

**What it could show, in order of cost:**
1. The Overview: a card per device with its current reading and a chart
   of the chosen range (from the history, then live).
2. A device page: its charts and its properties.
3. The busiest apps and processes (if allowed).
4. GPU Details tabs (the detail readings are already in the history as
   `detail/<key>` columns).

**Leaning, as a first slice:** inside `proccoli-metrics`, localhost only
with a token, read-only, the Overview and device pages from the history
plus SSE live readings, plain JS and canvas. Everything else waits.

**Open questions for the user:**
1. Who is it for first: you on the same machine, a phone or tablet on
   the home network (that's Feature 17's security questions), or a
   headless server?
2. Should it look like the GTK app (same cards and colors), or be its
   own simpler dashboard?
3. Read-only forever, or eventually actions (end a process) behind
   extra confirmation?
4. Is a Prometheus-style `/metrics` endpoint wanted too, so existing
   tools (Grafana and the like) can read Proccoli? It's cheap to add next
   to the JSON API.
