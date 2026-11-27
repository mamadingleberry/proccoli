# Milestone 47: Logo in the top-left corner

*✅ Done.* Logo, then burger, then sidebar toggle; the logo opens About

| Step | Create / change | Test |
|---|---|---|
| 47.1 | `page.app_logo_button()`: the app icon (24 px) as a flat button for `app.about`, tooltip *About Proccoli* | UI test: icon and action |
| 47.2 | First in the sidebar header and in each `PageContainer`'s `start_controls`: logo, burger, sidebar toggle | UI tests by window coordinates: logo in the corner, burger beside it, toggle after; the real `Application` leaves it clickable |
| 47.3 | `shoot.py`'s app gets `about`/`preferences`/`shortcuts` actions like the real one, so screenshots don't show the logo greyed out | Screenshots |
