#!/usr/bin/env bash
# Run a command on a private, headless GTK display (Broadway), isolated from
# the desktop session: no D-Bus session, in-memory GSettings.
#
#   tests/run-headless.sh python3 -m unittest discover -s tests
#
# Needs gtk4-broadwayd (package libgtk-4-bin).
set -euo pipefail

command -v gtk4-broadwayd >/dev/null || {
    echo "gtk4-broadwayd not found (sudo apt install libgtk-4-bin)" >&2
    exit 1
}

# Start a daemon on the first free display. A display is busy if its socket
# exists or its TCP port (8080 + n) is taken, e.g. by a daemon whose socket
# was deleted; so start one and keep it only if it is still running.
display=""
daemon=""
for n in $(seq 20 60); do
    [[ -e ${XDG_RUNTIME_DIR:-/tmp}/broadway$((n + 1)).socket ]] && continue
    [[ -e ${XDG_RUNTIME_DIR:-/tmp}/broadway$n.socket ]] && continue
    gtk4-broadwayd ":$n" >/dev/null 2>&1 &
    daemon=$!
    sleep 0.5
    if kill -0 "$daemon" 2>/dev/null; then
        display=$n
        break
    fi
done
[[ -n $display ]] || { echo "no free Broadway display" >&2; exit 1; }
socket=${XDG_RUNTIME_DIR:-/tmp}/broadway$((display + 1)).socket
# The daemon leaves its socket behind when killed: remove it, also when
# this script is interrupted, so later runs don't skip that display.
cleanup() { kill "$daemon" 2>/dev/null || true; rm -f "$socket"; }
trap cleanup EXIT
trap 'exit 130' INT TERM

export GDK_BACKEND=broadway BROADWAY_DISPLAY=":$display"
export GSETTINGS_BACKEND=memory DBUS_SESSION_BUS_ADDRESS=disabled:
export NO_AT_BRIDGE=1 PROCCOLI_UI_TESTS=1
# Show our own warnings, but not PyGObject's internal deprecation warnings
# on Python 3.14 (gi/events.py, gi/overrides), which we can't fix. Setting
# this also stops the unittest runner from re-enabling them.
export PYTHONWARNINGS="default,ignore::DeprecationWarning:gi.events,ignore::DeprecationWarning:gi.overrides"
"$@"
