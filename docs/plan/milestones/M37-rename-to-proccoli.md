# Milestone 37: Rename to Proccoli

*✅ Done.* App ID `io.github.mamadingleberry.Proccoli`

Proccoli: *process* + *broccoli*.

| Step | Create / change | Test |
|---|---|---|
| 37.1 | Package renamed to `src/proccoli` (helper `proccoli_helper.py`, installed as `proccoli-helper`); `APP_ID` `io.github.mamadingleberry.Proccoli`, `APP_NAME` "Proccoli"; data files (desktop, metainfo, schema, polkit policy, icons) renamed; packaging, Makefile, docs, test env var `PROCCOLI_UI_TESTS`, log path `~/.local/state/proccoli/proccoli.log` | Whole suite; packaging tests check the names agree |
| 37.2 | *(Removed in M45.)* A one-time import of the preferences saved under the previous name | — |

**Done when:** `make run` shows "Proccoli" everywhere.
