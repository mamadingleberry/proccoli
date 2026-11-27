# Milestone 14: Battery (optional)

*✅ Done.* Fixture-tested only: this machine has no battery

| # | Create | Test |
|---|---|---|
| 14.1 | `devices/battery.py`: discover via `/sys/class/power_supply/*/type == Battery`; charge, power, health = full/design | Fixtures: laptop battery; desktop (none → no page) |
| 14.2 | `ui/pages/battery.py` | Smoke |
