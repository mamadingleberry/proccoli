# Feature 33: Pane graphs sized as a group

Plan: [plan/features/feature-33-pane-graphs-sized-as-a-group.md](../../plan/features/feature-33-pane-graphs-sized-as-a-group.md)

*Proposed.* The size arithmetic sits in `ui/layout.py`, beside the
Overview's chart rules, so the device pages and the Overview follow one
set of rules; `GraphGroup` is only the widget that applies it.
