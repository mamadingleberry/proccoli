#!/bin/sh
# Install (or uninstall) Proccoli without pip or make.
#
#   packaging/install.sh                                 # -> /usr/local (needs sudo)
#   PREFIX=/usr packaging/install.sh                     # -> /usr
#   DESTDIR=/tmp/root PREFIX=/usr packaging/install.sh   # staged (for packages)
#   packaging/install.sh --uninstall
set -eu

cd "$(dirname "$0")/.."
NAME=proccoli
APP_ID=$(sed -n 's/^APP_ID = "\(.*\)"/\1/p' src/proccoli/__init__.py)
PREFIX=${PREFIX:-/usr/local}
DESTDIR=${DESTDIR:-}
SHARE="$PREFIX/share"
APPDIR="$SHARE/$NAME"
LIBEXECDIR="$PREFIX/libexec/$NAME"
D="$DESTDIR"

refresh_caches() {
    [ -z "$DESTDIR" ] || return 0     # packages refresh caches through triggers
    glib-compile-schemas "$SHARE/glib-2.0/schemas" 2>/dev/null || true
    if [ -f "$SHARE/icons/hicolor/icon-theme.cache" ]; then
        gtk-update-icon-cache -qf "$SHARE/icons/hicolor" 2>/dev/null || true
    fi
    update-desktop-database -q "$SHARE/applications" 2>/dev/null || true
}

if [ "${1:-}" = "--uninstall" ]; then
    rm -rf "$D$APPDIR" "$D$LIBEXECDIR"
    rm -f "$D$PREFIX/bin/$NAME" \
          "$D$SHARE/applications/$APP_ID.desktop" \
          "$D$SHARE/metainfo/$APP_ID.metainfo.xml" \
          "$D$SHARE/glib-2.0/schemas/$APP_ID.gschema.xml" \
          "$D$SHARE/polkit-1/actions/$APP_ID.policy" \
          "$D$SHARE/icons/hicolor/scalable/apps/$APP_ID.svg" \
          "$D$SHARE"/icons/hicolor/*/apps/"$APP_ID"*.png \
          "$D$SHARE"/icons/hicolor/symbolic/apps/"$APP_ID"-*-symbolic.svg
    refresh_caches
    echo "Uninstalled $NAME from $D$PREFIX"
    exit 0
fi

# The Python package (tests and the helper's source copy aren't needed).
( cd src && find proccoli -name '*.py' ! -path '*/__pycache__/*' ) | while read -r f; do
    install -Dm 644 "src/$f" "$D$APPDIR/$f"
done

install -d "$D$PREFIX/bin"
cat > "$D$PREFIX/bin/$NAME" <<LAUNCHER
#!/usr/bin/python3
import sys
sys.path.insert(0, "$APPDIR")
from proccoli.app import main
sys.exit(main())
LAUNCHER
chmod 755 "$D$PREFIX/bin/$NAME"

# The privileged helper, where the polkit policy expects it.
install -Dm 755 src/proccoli/helper/proccoli_helper.py "$D$LIBEXECDIR/proccoli-helper"

install -Dm 644 "data/$APP_ID.desktop"       "$D$SHARE/applications/$APP_ID.desktop"
install -Dm 644 "data/$APP_ID.metainfo.xml"  "$D$SHARE/metainfo/$APP_ID.metainfo.xml"
install -Dm 644 "data/$APP_ID.gschema.xml"   "$D$SHARE/glib-2.0/schemas/$APP_ID.gschema.xml"
install -d "$D$SHARE/polkit-1/actions"
sed "s|@LIBEXECDIR@|$LIBEXECDIR|g" "data/$APP_ID.policy" > "$D$SHARE/polkit-1/actions/$APP_ID.policy"
chmod 644 "$D$SHARE/polkit-1/actions/$APP_ID.policy"
( cd data/icons && find hicolor -type f ) | while read -r f; do
    install -Dm 644 "data/icons/$f" "$D$SHARE/icons/$f"
done

refresh_caches
echo "Installed $NAME to $D$PREFIX"
