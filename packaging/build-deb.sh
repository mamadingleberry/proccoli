#!/bin/sh
# Build Proccoli's .debs with nothing but dpkg-deb:
#
#   proccoli       the background collector and the library; no GTK
#   proccoli-gui   the window; needs proccoli of the same version
#
# Installing proccoli-gui brings proccoli with it.
set -eu

cd "$(dirname "$0")/.."
VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/proccoli/__init__.py)
BUILD=build/deb
MAINTAINER="The Proccoli contributors <maintainers@example.invalid>"
# The single package before the split: these take its files over.
# Before 0.5.0 the collector was the proccoli-metrics package and its
# program, /usr/bin/proccoli was the window, and "proccoli" only pulled
# in both. The new proccoli package takes their files over and removes
# proccoli-metrics; its upgrade from the old proccoli is an ordinary one.
COLLECTOR_TAKES_OVER="Conflicts: proccoli-metrics
Replaces: proccoli-metrics, proccoli-gui (<< 0.5.0)
Breaks: proccoli-gui (<< 0.5.0)"

rm -rf "$BUILD"
mkdir -p "$BUILD" dist

stage() {                       # stage DIR PART...: install.sh into DIR
    dir=$1; shift
    flags=""
    for part in "$@"; do flags="$flags --$part"; done
    # shellcheck disable=SC2086
    DESTDIR="$PWD/$dir" PREFIX=/usr packaging/install.sh $flags >/dev/null
}

control() {                     # control DIR PACKAGE SECTION DEPENDS RECOMMENDS EXTRA DESCRIPTION
    dir=$1 package=$2 section=$3 depends=$4 recommends=$5 extra=$6 description=$7
    install -Dm 644 LICENSE "$dir/usr/share/doc/$package/copyright"
    size=$(du -sk "$dir/usr" | cut -f1)
    mkdir -p "$dir/DEBIAN"
    {
        echo "Package: $package"
        echo "Version: $VERSION"
        echo "Section: $section"
        echo "Priority: optional"
        echo "Architecture: all"
        echo "Installed-Size: $size"
        echo "Maintainer: $MAINTAINER"
        echo "Depends: $depends"
        [ -z "$recommends" ] || echo "Recommends: $recommends"
        [ -z "$extra" ] || echo "$extra"
        echo "Description: $description"
    } > "$dir/DEBIAN/control"
}

build() {                       # build DIR PACKAGE
    out="dist/${2}_${VERSION}_all.deb"
    dpkg-deb --root-owner-group --build "$1" "$out" >/dev/null
    echo "Built $out"
}

# -- proccoli ------------------------------------------------------------
M="$BUILD/metrics"
stage "$M" metrics
control "$M" proccoli utils \
    "python3 (>= 3.10), python3-gi, gir1.2-glib-2.0" \
    "network-manager" \
    "$COLLECTOR_TAKES_OVER" \
    "system resource history for Proccoli, without a display
 Reads every device Proccoli shows (processors, memory, GPUs, drives,
 network interfaces, batteries), records the readings in a history
 database and serves them to Proccoli's window, from a systemd user
 service that runs without a window, on for every user. Needs no GTK,
 so it suits a machine without a screen."
# Before removing it: stop each logged-in user's collector (their history
# stays). Best effort; a user's systemd may not be reachable.
cat > "$M/DEBIAN/prerm" <<'PRERM'
#!/bin/sh
set -e
if [ "$1" = remove ]; then
    systemctl --global disable proccoli.service >/dev/null 2>&1 || true
fi
if [ "$1" = remove ] && command -v loginctl >/dev/null 2>&1; then
    loginctl list-users --no-legend 2>/dev/null | while read -r _uid user _rest; do
        [ -n "$user" ] || continue
        systemctl --user -M "$user@" stop proccoli.service >/dev/null 2>&1 || true
    done
fi
exit 0
PRERM
chmod 755 "$M/DEBIAN/prerm"
# After installing: on for every user (the window shows what it
# reads), and started now for anyone logged in. Best effort.
cat > "$M/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
if [ "$1" = configure ]; then
    # The unit's name before 0.5.0; its package is gone with it.
    systemctl --global disable proccoli-metrics.service >/dev/null 2>&1 || true
    systemctl --global enable proccoli.service >/dev/null 2>&1 || true
    if command -v loginctl >/dev/null 2>&1; then
        loginctl list-users --no-legend 2>/dev/null | while read -r _uid user _rest; do
            [ -n "$user" ] || continue
            systemctl --user -M "$user@" daemon-reload >/dev/null 2>&1 || true
            systemctl --user -M "$user@" restart proccoli.service >/dev/null 2>&1 || true
        done
    fi
fi
exit 0
POSTINST
chmod 755 "$M/DEBIAN/postinst"
build "$M" proccoli

# -- proccoli-gui: the window's files only ---------------------------------------
G="$BUILD/gui"
mkdir -p "$G"
cp -a "$M/usr" "$G/"
rm -rf "$G/usr/share/doc"
stage "$G" gui
( cd "$M" && find usr -type f ) | while read -r f; do rm -f "$G/$f"; done
find "$G/usr" -depth -type d -empty -delete
control "$G" proccoli-gui utils \
    "proccoli (= $VERSION), python3-gi-cairo, gir1.2-gtk-4.0 (>= 4.10), gir1.2-adw-1 (>= 1.5), pkexec" \
    "intel-gpu-tools, dmidecode" \
    "" \
    "system resource monitor with detailed GPU statistics (the window)
 A GTK 4 / libadwaita system monitor for processors, memory, GPUs,
 drives, network interfaces and batteries, with tables of running apps
 and processes, and per-engine statistics on Intel, NVIDIA and AMD GPUs."
build "$G" proccoli-gui

echo "Install with:  sudo apt install ./dist/proccoli_${VERSION}_all.deb" \
     "./dist/proccoli-gui_${VERSION}_all.deb"
