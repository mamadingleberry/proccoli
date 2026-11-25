#!/bin/sh
# Install (or uninstall) Proccoli without pip or make.
#
#   packaging/install.sh                                 # -> /usr/local (needs sudo)
#   PREFIX=/usr packaging/install.sh                     # -> /usr
#   DESTDIR=/tmp/root PREFIX=/usr packaging/install.sh   # staged (for packages)
#   packaging/install.sh --uninstall
#
# Proccoli comes in two parts (packaging/split.py says which file
# is which), installed together by default:
#   --metrics   proccoli: the background collector and the library
#               both parts use; no GTK, fit for a machine without a screen
#   --gui       the window (needs the metrics part)
# --uninstall takes the same choice; the metrics part won't go while the
# window is still installed.
set -eu

cd "$(dirname "$0")/.."
NAME=proccoli
APP_ID=$(sed -n 's/^APP_ID = "\(.*\)"/\1/p' src/proccoli/__init__.py)
PREFIX=${PREFIX:-/usr/local}
DESTDIR=${DESTDIR:-}
PYTHON=${PYTHON:-python3}
SHARE="$PREFIX/share"
APPDIR="$SHARE/$NAME"
LIBEXECDIR="$PREFIX/libexec/$NAME"
USERUNITDIR="$PREFIX/lib/systemd/user"
USERPRESETDIR="$PREFIX/lib/systemd/user-preset"
DBUSSERVICE="$SHARE/dbus-1/services/$APP_ID.Metrics.service"
D="$DESTDIR"

UNINSTALL=no
PARTS=""
for arg in "$@"; do
    case "$arg" in
        --uninstall) UNINSTALL=yes ;;
        --metrics) PARTS="$PARTS metrics" ;;
        --gui) PARTS="$PARTS gui" ;;
        *) echo "usage: install.sh [--metrics] [--gui] [--uninstall]" >&2; exit 2 ;;
    esac
done
[ -n "$PARTS" ] || PARTS="metrics gui"
has() { case " $PARTS " in *" $1 "*) return 0 ;; esac; return 1; }

refresh_caches() {
    [ -z "$DESTDIR" ] || return 0     # packages refresh caches through triggers
    glib-compile-schemas "$SHARE/glib-2.0/schemas" 2>/dev/null || true
    if [ -f "$SHARE/icons/hicolor/icon-theme.cache" ]; then
        gtk-update-icon-cache -qf "$SHARE/icons/hicolor" 2>/dev/null || true
    fi
    update-desktop-database -q "$SHARE/applications" 2>/dev/null || true
}

python_files() {               # the Python files of one part, under src/proccoli
    "$PYTHON" packaging/split.py "$1"
}

launcher() {                   # launcher NAME MODULE
    install -d "$D$PREFIX/bin"
    cat > "$D$PREFIX/bin/$1" <<LAUNCHER
#!/usr/bin/python3
import sys
sys.path.insert(0, "$APPDIR")
from $2 import main
sys.exit(main())
LAUNCHER
    chmod 755 "$D$PREFIX/bin/$1"
}

install_python() {
    python_files "$1" | while read -r f; do
        install -Dm 644 "src/proccoli/$f" "$D$APPDIR/proccoli/$f"
    done
}

uninstall_python() {
    python_files "$1" | while read -r f; do
        rm -f "$D$APPDIR/proccoli/$f"
    done
    find "$D$APPDIR" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
    find "$D$APPDIR" -depth -type d -empty -delete 2>/dev/null || true
}

if [ "$UNINSTALL" = yes ]; then
    if has metrics && ! has gui && [ -f "$D$APPDIR/proccoli/app.py" ]; then
        echo "The window (proccoli-gui) needs the metrics part: uninstall it first," \
             "or both with --uninstall alone." >&2
        exit 1
    fi
    if has gui; then
        uninstall_python gui
        rm -rf "$D$LIBEXECDIR"
        rm -f "$D$PREFIX/bin/$NAME-gui" \
              "$D$SHARE/applications/$APP_ID.desktop" \
              "$D$SHARE/metainfo/$APP_ID.metainfo.xml" \
              "$D$SHARE/polkit-1/actions/$APP_ID.policy" \
              "$D$SHARE/icons/hicolor/scalable/apps/$APP_ID.svg" \
              "$D$SHARE"/icons/hicolor/*/apps/"$APP_ID"*.png \
              "$D$SHARE"/icons/hicolor/symbolic/apps/"$APP_ID"-*-symbolic.svg
        rm -rf "$D$SHARE"/gnome-shell/extensions/proccoli-windows@*
    fi
    if has metrics; then
        if [ -z "$DESTDIR" ] && [ -f "$USERUNITDIR/proccoli.service" ]; then
            # Every user's background collector stops with it; their history stays.
            systemctl --global disable proccoli.service 2>/dev/null || true
        fi
        uninstall_python metrics
        rm -f "$D$PREFIX/bin/$NAME" \
              "$D$USERUNITDIR/proccoli.service" \
              "$D$USERPRESETDIR/90-proccoli.preset" "$D$DBUSSERVICE" \
              "$D$SHARE/glib-2.0/schemas/$APP_ID.gschema.xml"
    fi
    [ -d "$D$APPDIR" ] && find "$D$APPDIR" -depth -type d -empty -delete 2>/dev/null || true
    refresh_caches
    echo "Uninstalled$PARTS from $D$PREFIX"
    exit 0
fi

if has gui && ! has metrics && [ ! -f "$D$APPDIR/proccoli/metrics.py" ]; then
    echo "The window needs the metrics part: install it too (--metrics --gui)." >&2
    exit 1
fi

if has metrics; then
    install_python metrics
    # The settings schema: the collector follows the same preferences.
    install -Dm 644 "data/$APP_ID.gschema.xml" "$D$SHARE/glib-2.0/schemas/$APP_ID.gschema.xml"
    # The background collector and its systemd user unit, off
    # until the user turns it on.
    # Before 0.5.0 the recorder was proccoli-metrics (and $NAME the window).
    if [ -z "$DESTDIR" ] && [ -f "$USERUNITDIR/proccoli-metrics.service" ]; then
        systemctl --global disable proccoli-metrics.service 2>/dev/null || true
    fi
    rm -f "$D$PREFIX/bin/$NAME-metrics" "$D$USERUNITDIR/proccoli-metrics.service"
    launcher "$NAME" proccoli.metrics
    install -d "$D$USERUNITDIR"
    sed -e "s|@BINDIR@|$PREFIX/bin|g" -e "s|@APP_ID@|$APP_ID|g" data/proccoli.service \
        > "$D$USERUNITDIR/proccoli.service"
    chmod 644 "$D$USERUNITDIR/proccoli.service"
    # Always on: enabled for every user, and started on demand
    # when a window asks for readings (D-Bus activation).
    install -Dm 644 data/proccoli.preset "$D$USERPRESETDIR/90-proccoli.preset"
    install -d "$(dirname "$D$DBUSSERVICE")"
    sed -e "s|@BINDIR@|$PREFIX/bin|g" -e "s|@APP_ID@|$APP_ID|g" data/dbus-metrics.service.in \
        > "$D$DBUSSERVICE"
    chmod 644 "$D$DBUSSERVICE"
    if [ -z "$DESTDIR" ]; then
        systemctl --global enable proccoli.service 2>/dev/null || true
    fi
fi

if has gui; then
    install_python gui
    launcher "$NAME-gui" proccoli.app
    # The privileged helper, where the polkit policy expects it.
    install -Dm 755 src/proccoli/helper/proccoli_helper.py "$D$LIBEXECDIR/proccoli-helper"
    install -Dm 644 "data/$APP_ID.desktop"       "$D$SHARE/applications/$APP_ID.desktop"
    install -Dm 644 "data/$APP_ID.metainfo.xml"  "$D$SHARE/metainfo/$APP_ID.metainfo.xml"
    install -d "$D$SHARE/polkit-1/actions"
    sed "s|@LIBEXECDIR@|$LIBEXECDIR|g" "data/$APP_ID.policy" \
        > "$D$SHARE/polkit-1/actions/$APP_ID.policy"
    chmod 644 "$D$SHARE/polkit-1/actions/$APP_ID.policy"
    ( cd data/icons && find hicolor -type f ) | while read -r f; do
        install -Dm 644 "data/icons/$f" "$D$SHARE/icons/$f"
    done
    # The GNOME Shell extension for Switch To (off until the user turns it
    # on in Preferences → General → Window Switching).
    ( cd data && find gnome-shell -type f ) | while read -r f; do
        install -Dm 644 "data/$f" "$D$SHARE/$f"
    done
fi

refresh_caches
echo "Installed$PARTS to $D$PREFIX"
