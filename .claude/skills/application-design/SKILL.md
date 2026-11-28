---
name: application-design
description: High-level application design - splitting a background service from the user-facing frontend, the user's flow, usability and accessibility (color blindness, contrast, keyboard), and optional standards such as i18n that are applied only when the user asks. Use with every code change (via software-project) and when designing features or UI.
---

# Application design standards

Architecture patterns in general are in the `engineering-skills`
plugin's `senior-architect`; this skill is about the application's shape
and its users, and wins where they differ.

## The shape of the application

- **Split collecting from showing** when data should exist while nobody
  is looking. A background service (a systemd user or system unit) collects,
  stores the history and serves current readings; the frontend only
  subscribes and shows. This gives history from before the window opened,
  one reader of the hardware however many windows, a frontend that starts
  fast and uses little, and room for other frontends (a web view, a CLI,
  exports).
- The frontend reads what changes too fast or is too large to send
  (process tables) itself, or asks the service on demand.
- One writer for shared state; readers never take over silently.
- Every program installs and works on its own: the service without the
  GUI, the GUI with a clear message when the service is missing.
- Privileged work goes in a small, separate helper with a narrow command
  set, never in the GUI.

## The user's flow

- Start where the user most often wants to be; remember where they left.
- The common task in one or two steps; rare ones may take more.
- Show state truthfully: what the user chose stays chosen even when the
  layout must adapt; say why something is missing or empty.
- Don't block: long work runs in the background with feedback, and the
  window stays responsive.
- Efficient by default: do no work for what isn't on screen.

## Usability and accessibility

For web frontends, the `engineering-skills` plugin's `a11y-audit` checks
WCAG 2.2; for native desktop apps these rules apply.

- **Color blindness:** never use color as the only signal; pair it with
  labels, patterns, shapes or position. Offer palettes that stay apart
  under protanopia, deuteranopia and tritanopia.
- **Contrast:** text at least 4.5:1 against its background (3:1 for large
  text and graph lines); offer high-contrast styles.
- **Keyboard:** everything reachable by keyboard; common actions have
  shortcuts, listed in a shortcuts window; focus is visible.
- **Screen readers:** label controls and charts (accessible names and
  descriptions).
- Follow the platform's interface guidelines (on GNOME, the HIG) for
  wording, layout and capitalisation; respect the system's light/dark
  style, text size and reduced motion.
- Units follow the user's choice (SI or binary, Celsius or Fahrenheit).

## Optional standards: consider, apply only when asked

Note where these would matter, but apply them only when the user
explicitly asks:

- **i18n / l10n:** translatable strings (gettext), locale-aware numbers
  and dates, right-to-left layouts.
- Remote or multi-machine access, authentication, telemetry.
- Packaging for other distributions or app stores (Flatpak, Snap).
