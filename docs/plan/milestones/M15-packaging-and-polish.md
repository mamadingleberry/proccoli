# Milestone 15: Packaging and polish

*✅ Done.* CPU target not met under Broadway, see 15.4

| # | Create | Test |
|---|---|---|
| 15.1 | `data/` `.desktop` (`StartupWMClass`), metainfo, symbolic and full-color icons (SVG + PNG sizes) | `desktop-file-validate`, `appstreamcli validate` in `make test` |
| 15.2 | `packaging/install.sh` (PREFIX, DESTDIR, `--uninstall`) and `build-deb.sh` (dpkg-deb only). Depends: python3-gi, python3-gi-cairo, gir1.2-gtk-4.0, gir1.2-adw-1, pkexec. Recommends: intel-gpu-tools. | Build a .deb in CI and install it in a clean container |
| 15.3 | Keyboard shortcuts dialog, About dialog (with credits to Resources for the design and to intel_gpu_top_gui) | Manual |
| 15.4 | Performance pass: hidden pages skip redraws; process scan throttled when the window is hidden | Measure: under 2 % CPU idle at a 1 s refresh on this laptop |
| 15.5 | Accessibility pass: labels on graphs and meters, keyboard navigation of the sidebar | Orca walkthrough |

**Done:** `sudo apt install ./dist/proccoli_*.deb` gives a dock-pinnable app
that matches Resources' feature set, plus the detailed Intel GPU page.
