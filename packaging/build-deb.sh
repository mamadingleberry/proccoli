#!/bin/sh
# Build a .deb with nothing but dpkg-deb.
set -eu

cd "$(dirname "$0")/.."
NAME=proccoli
VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/proccoli/__init__.py)
ROOT=build/deb-root
OUT=dist/${NAME}_${VERSION}_all.deb
# Runtime dependencies (libadwaita >= 1.5 for Adw.Dialog).
DEPENDS="python3 (>= 3.10), python3-gi, python3-gi-cairo, gir1.2-gtk-4.0 (>= 4.10), gir1.2-adw-1 (>= 1.5), pkexec"
RECOMMENDS="intel-gpu-tools, dmidecode, network-manager"

rm -rf "$ROOT"
DESTDIR="$PWD/$ROOT" PREFIX=/usr packaging/install.sh >/dev/null

install -Dm 644 LICENSE "$ROOT/usr/share/doc/$NAME/copyright"

SIZE=$(du -sk "$ROOT/usr" | cut -f1)
mkdir -p "$ROOT/DEBIAN"
cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: $NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Installed-Size: $SIZE
Maintainer: The Proccoli contributors <maintainers@example.invalid>
Depends: $DEPENDS
Recommends: $RECOMMENDS
Description: system resource monitor with detailed GPU statistics
 A GTK 4 / libadwaita system monitor for processors, memory, GPUs,
 drives, network interfaces and batteries, with tables of running apps
 and processes. On Intel GPUs it can show per-engine statistics from
 intel_gpu_top.
CONTROL

mkdir -p dist
dpkg-deb --root-owner-group --build "$ROOT" "$OUT" >/dev/null
echo "Built $OUT"
echo "Install with:  sudo apt install ./$OUT"
