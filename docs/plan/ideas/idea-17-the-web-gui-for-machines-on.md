# Idea 17: The Web GUI for machines on the local network (brainstorm)

Design note: [design/ideas/idea-17-the-web-gui-for-machines-on.md](../../design/ideas/idea-17-the-web-gui-for-machines-on.md)

**Goal:** one Web GUI (Idea 16) showing several machines at home or in a
small office, each running `proccoli-metrics`: a list of machines, each
with its Overview, and charts that compare them.

**Is it possible? Yes.** It's what tools like Netdata, Glances (server
mode) and Cockpit with PCP do. The parts are well known; the work is in
choosing a small, safe subset. This section is where to begin.

**The pieces, each with the simplest option first:**

1. **Each machine exposes its data.** Idea 16's API, listening on the
   network instead of localhost (a setting, off by default). Nothing new
   beyond that switch, which is exactly why the security below matters.
2. **Finding machines.** *DNS-SD over mDNS* (what printers and Chromecasts
   use): each collector announces `_proccoli._tcp` through Avahi, which
   Ubuntu and Debian desktops already run, over D-Bus with Gio (no new
   dependency). The hub lists what it hears. Fallback: type a host name
   or address.
3. **Trust (pairing).** The first time, the hub shows the machine's name
   and a short code; the machine shows the same code (in its GUI, or
   `proccoli-metrics --pair`); the user confirms both, like Bluetooth.
   They exchange a long random token, and the hub remembers the
   machine's TLS certificate fingerprint (self-signed, pinned, no
   certificate authority needed). After that the hub sends the token on
   every request and refuses a different certificate.
4. **Encryption.** HTTPS with that pinned self-signed certificate,
   through Python's `ssl` (standard library, no new package).
5. **Getting the data to the hub (two models):**

| | The hub pulls (asks each machine) | Machines push to the hub |
|---|---|---|
| Live view | SSE from each machine, straight to the browser or via the hub | each machine sends readings as they're taken |
| History | asked when shown, from each machine's own database | the hub keeps a copy of everyone's history |
| A machine off | shown as offline; its history comes back with it | the hub has the history up to when it went off |
| Storage | nothing new | the hub's database grows per machine |
| Firewall | the hub must reach each machine | each machine must reach the hub |

   *Leaning:* **pull first**. Each machine keeps its own history (it
   already does), the hub stores only the paired machines and their
   tokens, and nothing is copied. Push (a hub that remembers machines
   that are now off) can come later.
6. **Comparing machines:** the API's time-aligned buckets
   (`HistoryDb.buckets`) already put every device on the same grid, so
   "processor use on all machines, last day" is one request per machine,
   drawn on one chart. Clocks: times are UTC epoch milliseconds
   everywhere, so machines line up as long as they keep time (NTP);
   the hub shows a warning when a machine's clock is off by more than a
   few seconds.

**Risks and limits:**
- **Exposure:** a network-facing service shows hardware details and
  usage patterns (when someone's at the computer). Off by default,
  paired-only, read-only, process names off, and the README says plainly
  what's shared.
- **Guest and public networks:** listening only on interfaces the user
  picks, and never on a network NetworkManager marks as public.
- **mDNS doesn't cross routers or VLANs:** typed addresses cover those.
- **Scale:** a home or small office (2–20 machines) is the target, not
  a fleet; larger setups are what Prometheus and Grafana are for (Idea
  16's question 4).

**Where to begin (a path in small, useful steps):**
1. Idea 13 (the collector) and Idea 16's first slice (localhost web
   view): everything else builds on them.
2. A read-only API on the network with a token typed by hand (no
   discovery, no pairing UI): proves the model between two of your own
   machines.
3. The hub page: a list of typed addresses, each machine's Overview
   cards, offline shown as such.
4. TLS with pinned certificates, and pairing with codes, replacing the
   hand-typed token.
5. mDNS discovery.
6. Comparison charts across machines.
7. Maybe later: push, so the hub remembers machines that are off.

**Open questions for the user:**
1. Which machines do you have in mind (all Linux? servers, laptops that
   come and go?), and roughly how many?
2. Should the hub be any machine's Web GUI (every install can be a hub),
   or one chosen machine?
3. Pull (each machine keeps its own history; an off machine shows
   nothing new) or push (the hub keeps everyone's history) as the first
   model?
4. Is showing process names across the network ever wanted, or should
   remote views be devices only?
