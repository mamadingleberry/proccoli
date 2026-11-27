# Idea 11: A shorter, friendlier README

Design note: [design/ideas/idea-11-a-shorter-friendlier-readme.md](../../design/ideas/idea-11-a-shorter-friendlier-readme.md)

**Goal:** a README that answers what a person deciding whether to try
Proccoli asks, in a page or two, with screenshots. The full reference
(every menu, preference and file) stays, on a second page.

**Why:** the README has grown with every milestone into a complete
reference: long bullet lists, exact menu paths, file formats and units.
It's accurate, but someone landing on the repository can't tell in a
minute what Proccoli is for, what it looks like, or whether it runs on
their machine.

**What potential users care about,** in this order:

1. What it is and what it looks like: one sentence and a hero
   screenshot.
2. Will it run here: distributions, GPUs supported (Intel, NVIDIA, the
   rest generically), and no build step.
3. How to install it, in three commands.
4. What it's good for, as common tasks rather than features.
5. Privacy and safety: everything stays on the machine; when and why
   it asks for a password.
6. Where to get help or report a problem.

**Common tasks to show (each a short paragraph and, where marked, a
screenshot):**

| Task | Screenshot |
|---|---|
| "What's slowing my machine down?": the Overview's busiest apps, then Apps sorted by processor | Overview (light) |
| "Is my GPU busy, and with what?": the GPU page's Details and Processes tabs | GPU Details (dark) |
| "What happened while I was away?": a 1-day range, filled from the history, with the time Proccoli wasn't running shaded | A 1-day chart with a shaded stretch |
| Ending, pausing or reprioritising a stuck process | The Processes right-click menu |
| Keeping it small: Lightweight Mode and the icons-only sidebar | Icons-only sidebar |
| Getting the numbers out: *Export Statistics* to CSV | – |
| Making it yours: styles and palettes | Two palettes side by side |

**Design:**

- `README.md`: an intro and hero image, *Features at a glance* (6–8
  bullets), *Install*, *Common tasks* (the table above, as prose),
  *Privacy*, *Help*, *License*. Aim for under 150 lines.
- `docs/USER-GUIDE.md`: today's README sections, moved as they are
  (sidebar, preferences, keyboard shortcuts, files, troubleshooting), so
  nothing is lost; the README links to it.
- Screenshots in `docs/screenshots/`, made by `tests/ui/shoot.py` from
  the demo devices (never `--real` ones, which show the machine's own
  hardware and processes), so they're reproducible and can be refreshed
  with each release. A `make screenshots` target writes them there.
- Screenshots at 1024×768, PNG, kept small (under 200 KB each); light
  and dark both appear.

| Step | Create / change | Test |
|---|---|---|
| I11.1 | `docs/USER-GUIDE.md` from today's README | Run: every section is there, links work |
| I11.2 | `tests/ui/shoot.py` scenes for each screenshot; `make screenshots` into `docs/screenshots/` | `make ui-test` shoots them |
| I11.3 | The new `README.md` | Read on GitHub; a static test that every image the README links to exists |
| I11.4 | Metainfo screenshots point at the same images | `appstreamcli validate` |

**Done when:** the README fits on two screens, shows what Proccoli
looks like, and every detail it dropped is in the user guide.

**Open questions for the user:**
1. Keep the full reference as `docs/USER-GUIDE.md`, or as a GitHub wiki?
2. Should the hero image be a still, or a short animated GIF of the
   graphs moving?
3. Is there a task your own use of Proccoli centres on that should come
   first?
