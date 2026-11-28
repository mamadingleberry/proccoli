# Bug 22: The window freezes after unlocking or waking from suspend

Plan: [plan/bugs/bug-22-the-window-freezes-after-unlocking-or.md](../../plan/bugs/bug-22-the-window-freezes-after-unlocking-or.md)


*[PLAN.md, Bug 22](../../plan/bugs/bug-22-the-window-freezes-after-unlocking-or.md). Fixed (to confirm over a locked night).* The window that froze had been stalling for
18 hours before the unlock: 9–24 s at a time, every stack in a table
page's `update_rows` (`store.append` and `store.remove`), while a
container restarted every 15 s, with 1.1 GiB and 94 % of a core at the
end. The table diffs one row at a time, so each row added or removed is
a separate `items-changed` through the filter, the sorter and the column
view, and `store.find` is a linear scan:

```mermaid
flowchart LR
    T["tick"] --> M["ProcessMonitor.refresh"]
    M -->|updated| U["TablePage.update_rows"]
    U -->|"per new row"| A["store.append"]
    U -->|"per gone row"| R["store.find + store.remove"]
    A & R --> C["items-changed →<br/>FilterListModel → SortListModel →<br/>ColumnView"]
    U --> S["sorter.changed(DIFFERENT)"]
```

The fix, after a benchmark showed the column view rebinding every visible
cell on each of hundreds of changes per refresh:

```mermaid
flowchart LR
    T["tick"] --> M["ProcessMonitor.refresh"]
    M -->|updated| U["TablePage.update_rows"]
    U --> P["table_diff.plan_splice<br/>(pure: first gone row → kept + new)"]
    P --> S1["one store.splice → one items-changed"]
    W["window surface: notify::state"] -->|"SUSPENDED (locked, minimized)"| R["release the monitor: no scans"]
    W -->|"shown again"| A["acquire: the next scan refreshes once"]
```

- `self.rows` (a dict) keeps the store's order, so positions come from
  it, not from `store.find`.
- Selected rows that the splice puts back are selected again.
- `compat.toplevel_suspended()` reads `Gdk.ToplevelState.SUSPENDED`
  (GTK ≥ 4.12); older GTK never reports it, and the table keeps scanning
  as before.
