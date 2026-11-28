# Feature 23: Icons Only on narrow windows

Design note: [design/features/feature-23-icons-only-on-narrow-windows.md](../../design/features/feature-23-icons-only-on-narrow-windows.md)

**Goal:** a narrow window keeps a sidebar when one fits, and the main
menu always shows the sidebar mode the user chose.

**Seen:** "the Icon-only sidebar view autohides (ie. forcibly changes the
sidebar view in the menu to Hidden) when the viewing window isn't wide
enough" (raised as a bug, kept as a feature to find a solution).

**Today:** below 780 sp (`window.COLLAPSE_CONDITION`, Resources' breakpoint)
the `Adw.OverlaySplitView` collapses, whatever the sidebar style; a
collapsed sidebar is an overlay, closed until asked for
(`SidebarVisibility._on_collapsed`). The menu's mode is worked out from
what's shown (`mode_of(show_sidebar, style)`), so it reads *Hidden*,
though the user chose *Icons Only* (or *Full*), and their choice
(`sidebar-shown`, `sidebar-style`) is untouched and comes back when the
window widens. The breakpoint was made for the full sidebar (about
220 px); the icons-only one is about 56 px and would fit beside the
content far below 780 sp.

**Ways to do it:**

| | How | For | Against |
|---|---|---|---|
| A | **Icons Only never collapses:** the 780 sp breakpoint applies to *Full* only; with icons the sidebar stays beside the content down to the window's minimum width | Simple; what the user chose stays on screen | Very narrow windows (phones, tiled quarters) lose ~56 px to it |
| B | **Step down before hiding:** *Full* becomes icons-only below 780 sp, and only below a second, much narrower breakpoint (about 400 sp) does the sidebar fold into an overlay; widening restores the step above | Uses the room there is; the user still sees a sidebar on half-screen windows | Two breakpoints, and a style the window chose that isn't the user's setting (must not be saved) |
| C | **Truthful menu:** whatever folds away, the menu keeps the user's mode marked, with a note ("folded away: the window is narrow"), and picking it again opens the overlay | Fixes the confusing *Hidden* alone; small | The sidebar is still gone on narrow windows |

**Recommendation:** B with C: icons-only between the two breakpoints
(A's benefit for icon users at every width above 400 sp), and the menu
always showing the user's choice. The width decisions go in a pure,
display-free function so tests need no window.

| Step | Create / change | Test |
|---|---|---|
| F23.1 | `ui/sidebar_style.py`: `effective_layout(width_sp, chosen_mode) -> (shown style, beside or overlay)` | Unit, table-driven: Full above 780; icons 400–780; overlay below 400; Icons Only beside down to 400; Hidden stays hidden |
| F23.2 | `ui/window.py`: a second `Adw.Breakpoint`; `SidebarVisibility` applies `effective_layout` and never saves a style the window chose | UI: at 1024, 700 and 360 px wide: what's shown, and the settings unchanged |
| F23.3 | The menu marks the user's mode; folded away, a disabled note under it says why | UI: at 360 px with *Icons Only* chosen, the menu marks *Icons Only* |
| F23.4 | `shoot.py` scenes for the three widths; README (*Sidebar*), DESIGN | `make ui-test` |

**Open questions for the user:**
1. A, B, C, or B with C?
2. For B: is about 400 sp right for the narrow breakpoint, or should the
   sidebar fold away only at the window's minimum width?
3. Should a narrow window step *Full* down to icons at all, or keep
   *Full* until it must fold away (A's rule for both styles)?
