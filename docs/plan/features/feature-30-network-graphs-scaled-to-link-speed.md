# Feature 30: Network sidebar graphs scaled to the link speed

Design note: [design/features/feature-30-network-graphs-scaled-to-link-speed.md](../../design/features/feature-30-network-graphs-scaled-to-link-speed.md)

*Open; settled with the user.* Ethernet and Wi-Fi sidebar graphs
auto-scale today, so the same traffic looks different minute to minute
and between interfaces. They scale to the interface's link speed
instead, with a small top label, like the percentage graphs.

**Today:** `NetworkSnapshot.link_speed_mbps` comes from
`/sys/class/net/<if>/speed`; Wi-Fi drivers usually report `-1` there.

| Step | Create / change | Test |
|---|---|---|
| F30.1 | Pure `network_scale(link_mbps, peak) -> top`: the link speed when known, else the next step of 1, 10, 100 Mb/s, 1, 10 Gb/s above the peak (never shrinking within the time range) | Unit, table-driven |
| F30.2 | Wi-Fi rate: the current bitrate through `System` (`iw dev <if> link`), when installed; else the stepped scale | Unit with `FakeSystem` |
| F30.3 | The sidebar meter and the page graph use the top, and show it as a label | UI smoke; `shoot.py` network scene |
| F30.4 | README (*Network*), DESIGN §6 | — |
