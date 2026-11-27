# Milestone 17: Light/dark style follows the system

*✅ Done.*

The app takes the system's light/dark preference by default, with an
override in Preferences.

| Step | Create / change | Test |
|---|---|---|
| 17.1 | Schema: `color-scheme` (`system` default, `light`, `dark`) | Settings tests; schema key used |
| 17.2 | `ui/theme.py`: `Theme(settings, style_manager)`. Maps the setting to an `Adw.ColorScheme` (`system` → `DEFAULT`, which follows the desktop) and follows changes. The style manager is injected, so tests use a fake. | Unit with a fake style manager: each nick, live changes, `shutdown()` disconnects |
| 17.3 | `AppContext.theme` (set by the UI, like `pages`); `Application` builds the `Theme`; `MainWindow` makes one if none was given | UI test: injected theme is used |
| 17.4 | Preferences → General → Appearance: *Style* (Follow System, Light, Dark) | Dialog test: the combo changes the setting and the fake style manager |

**Done when:** with no setting, Proccoli is dark when the desktop is dark
and light when it's light; the override applies immediately.
