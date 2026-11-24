#!/usr/bin/python3
"""Render the scalable app icon to PNGs, for docks and launchers without SVG
support. ``make icons`` runs it after ``make-logo.py`` (which writes the
SVG); the PNGs are committed."""

import os
import sys

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from proccoli import APP_ID  # noqa: E402

ICONS = os.path.join(ROOT, "data", "icons", "hicolor")
SVG = os.path.join(ICONS, "scalable", "apps", f"{APP_ID}.svg")
SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

for size in SIZES:
    out_dir = os.path.join(ICONS, f"{size}x{size}", "apps")
    os.makedirs(out_dir, exist_ok=True)
    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(SVG, size, size)
    pixbuf.savev(os.path.join(out_dir, f"{APP_ID}.png"), "png", [], [])
    print(f"{size}x{size}")
