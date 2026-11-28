# Milestone 49: Back and forward

*✅ Done.* Mouse thumb buttons and Alt+Left/Right move through the panes visited; unplugged panes are skipped

| Step | Create / change | Test |
|---|---|---|
| 49.1 | `NavigationHistory` (no display): `visit`, `back`, `forward`, `remove` (forget, merge equal neighbours), limit 50; `mouse_direction` (8/11 back, 9/10 forward) | Unit: round trip, new branch drops forward, duplicates, limit, removal (current or not), button mapping |
| 49.2 | `MainWindow`: records every page change except its own back/forward; `go_back`/`go_forward`; `win.back`/`win.forward` on Alt+Left/Alt+Right, enabled when possible; `remove_page` updates history | UI tests: back and forward across sidebar and Go To changes, actions' state, removed pages skipped |
| 49.3 | Mouse: `GestureClick(button=0)` on the window, capture phase; `on_mouse_button` claims back/forward buttons and denies others at once; nothing while a dialog is open | UI tests with a fake gesture (real thumb-button presses can't be sent headless) |
| 49.4 | Keyboard Shortcuts dialog lists Back and Forward | Dialog test |
