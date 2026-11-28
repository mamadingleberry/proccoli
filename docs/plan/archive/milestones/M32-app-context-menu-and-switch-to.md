# Milestone 32: App context menu and Switch To

*✅ Done.* Switch To only for apps that can be asked (D-Bus-activatable or single-window), e.g. Files and Settings; not Firefox, Terminal or VS Code here

| Step | Create / change | Test |
|---|---|---|
| 32.1 | Right-click (or long-press, Menu key) on an Apps or Processes row selects it and opens a menu: Information, End, Kill, Halt, Continue (+ Options on Processes) | UI test |
| 32.2 | Apps: *Switch To*: brings the app's window to the front. GNOME on Wayland lets an app raise only itself, so Proccoli asks the app: `org.freedesktop.Application.Activate` over D-Bus for D-Bus-activatable apps (the app raises its own window); otherwise relaunching its `.desktop` entry, which single-instance apps treat as "show yourself". Through `System.activate_app`, so it's faked in tests. Disabled for System Processes. | Unit (fake System); UI test |
