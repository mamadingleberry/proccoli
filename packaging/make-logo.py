#!/usr/bin/python3
"""Draw Proccoli's app icon as SVG.

A gauge whose needle is a broccoli: the stalk is the needle's shaft and
pivot, the crown its head, so the vegetable's awkward shape (thin stem,
big lumpy top) becomes the most natural part of the gauge. The dial is
flat (dark face, colored scale, a sparkline of recent usage under the
pivot); the broccoli sits on top, drawn with some depth.

The florets' buds are placed by a seeded random generator, so the output
is the same on every run. Run ``make icons`` after changing this file; it
writes the scalable SVG and renders the PNGs.

    python3 packaging/make-logo.py [OUT.svg()]
"""

from __future__ import annotations

import math
import os
import random
import sys
from typing import Iterable

SIZE = 128
CENTER = (64.0, 64.0)          # dial centre
DIAL_R = 58.0                  # outer bezel
FACE_R = 51.0
SCALE_R = 43.0                 # colored scale (arc)
SCALE_W = 6.0
SWEEP = 240.0                  # degrees, centred on 12 o'clock
PIVOT = (64.0, 75.0)           # the broccoli turns about its stalk's base
READING = 0.58                 # where the broccoli points, 0..1 along the scale
BROCCOLI_SCALE = 0.9
SEED = 26

# Scale colors (GNOME palette): green most of the way, then yellow, red.
ZONES = ((0.0, 0.66, "#57e389"), (0.66, 0.84, "#f6d32d"), (0.84, 1.0, "#ed333b"))

GREENS_DARK = ("#1f4d1c", "#24581f", "#2a6324")
GREENS_MID = ("#2f6f27", "#37802d", "#3f8c33")
GREENS_LIGHT = ("#5aa845", "#6cb851", "#7fc65e")


def f(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".")


def polar(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    """Point at ``deg`` degrees clockwise from 12 o'clock."""
    a = math.radians(deg)
    return cx + r * math.sin(a), cy - r * math.cos(a)


def arc_path(cx: float, cy: float, r: float, start: float, end: float) -> str:
    x0, y0 = polar(cx, cy, r, start)
    x1, y1 = polar(cx, cy, r, end)
    large = 1 if end - start > 180 else 0
    return f"M{f(x0)} {f(y0)} A{f(r)} {f(r)} 0 {large} 1 {f(x1)} {f(y1)}"


def scale_angle(t: float) -> float:
    return -SWEEP / 2 + SWEEP * t


# -- the dial ------------------------------------------------------------------------

def dial() -> list[str]:
    cx, cy = CENTER
    out = [
        # Base with a flat bottom edge, as GNOME app icons have.
        f'<circle cx="{f(cx)}" cy="{f(cy + 3)}" r="{f(DIAL_R)}" fill="#1b1f27"/>',
        f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(DIAL_R)}" fill="url(#bezel)"/>',
        f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(FACE_R)}" fill="url(#face)"/>',
    ]
    # Colored scale, then ticks across it.
    for t0, t1, color in ZONES:
        out.append(f'<path d="{arc_path(cx, cy, SCALE_R, scale_angle(t0), scale_angle(t1))}" '
                   f'fill="none" stroke="{color}" stroke-width="{f(SCALE_W)}"/>')
    for i in range(11):
        a = scale_angle(i / 10)
        major = i % 5 == 0
        x0, y0 = polar(cx, cy, SCALE_R - SCALE_W / 2 - (5 if major else 3), a)
        x1, y1 = polar(cx, cy, SCALE_R - SCALE_W / 2 - 1, a)
        out.append(f'<line x1="{f(x0)}" y1="{f(y0)}" x2="{f(x1)}" y2="{f(y1)}" '
                   f'stroke="#e8edf3" stroke-opacity="{0.9 if major else 0.55}" '
                   f'stroke-width="{2 if major else 1.4}" stroke-linecap="round"/>')
    # A sparkline of recent usage under the pivot.
    pts = [(40, 100), (46, 96), (51, 98), (56, 92), (61, 94), (66, 89), (71, 91),
           (76, 86), (81, 88), (88, 83)]
    line = " ".join(f"{x} {y}" for x, y in pts)
    left, right = pts[0][0], pts[-1][0]
    out.append(f'<path d="M{line} L{right} 104 L{left} 104 Z" fill="url(#spark)"/>')
    out.append(f'<path d="M{line}" fill="none" stroke="#57e389" stroke-width="2.2" '
               f'stroke-linecap="round" stroke-linejoin="round"/>')
    return out


# -- the broccoli (drawn pointing straight up from the origin) ------------------------------

CLUSTERS = [  # (x, y, r): the crown's florets, back to front
    (-17, -47, 10.5), (17, -47, 10.5), (-8, -55, 11), (8, -55, 11),
    (0, -60, 10), (-21, -37, 8.5), (21, -37, 8.5), (-11, -42, 11.5),
    (11, -42, 11.5), (0, -46, 12),
]


def stalk() -> list[str]:
    # Main stalk: wide where it branches, narrower at the cut end, with a
    # pale cut face at the bottom.
    body = ("M-6 0 C-6.5 -8 -7 -16 -9 -24 C-12 -28 -17 -31 -21 -33 "
            "L-15 -36 C-10 -33 -6 -31 -3 -30 L-2 -36 L2 -36 L3 -30 "
            "C6 -31 10 -33 15 -36 L21 -33 C17 -31 12 -28 9 -24 "
            "C7 -16 6.5 -8 6 0 Z")
    return [
        f'<path d="{body}" fill="url(#stalk)"/>',
        # Fibres.
        '<path d="M-2 -2 C-2.5 -12 -3 -20 -5 -27 M2.5 -2 C3 -12 3.5 -20 5.5 -27" '
        'fill="none" stroke="#8fae5f" stroke-width="1" stroke-linecap="round" '
        'stroke-opacity="0.7"/>',
        '<ellipse cx="0" cy="0" rx="6" ry="2" fill="#dfe8b8"/>',
        '<ellipse cx="0" cy="0" rx="4.2" ry="1.2" fill="#c8d99a"/>',
    ]


def buds(rng: random.Random, x: float, y: float, r: float) -> Iterable[str]:
    """Bud texture inside one floret: lighter on the upper left."""
    for _ in range(int(r * r * 0.55)):
        a = rng.uniform(0, 2 * math.pi)
        d = r * math.sqrt(rng.uniform(0, 0.92))
        bx, by = x + d * math.cos(a), y + d * math.sin(a)
        light = (bx - x) * -0.6 + (by - y) * -0.8      # towards the upper left
        if light > r * 0.35:
            palette = GREENS_LIGHT
        elif light < -r * 0.35:
            palette = GREENS_DARK
        else:
            palette = GREENS_MID
        yield (f'<circle cx="{f(bx)}" cy="{f(by)}" r="{f(rng.uniform(1.1, 1.9))}" '
               f'fill="{rng.choice(palette)}"/>')


def crown(rng: random.Random) -> list[str]:
    out = []
    # Shadow under the crown where it meets the stems.
    out.append('<ellipse cx="0" cy="-33" rx="22" ry="5" fill="#16361a" fill-opacity="0.55"/>')
    for x, y, r in CLUSTERS:
        out.append(f'<circle cx="{f(x)}" cy="{f(y + 1)}" r="{f(r)}" fill="#163a17"/>')
        out.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r)}" fill="url(#floret)"/>')
        out.extend(buds(rng, x, y, r))
    return out


def broccoli() -> list[str]:
    rng = random.Random(SEED)
    angle = scale_angle(READING)
    px, py = PIVOT
    parts = stalk() + crown(rng)
    inner = "\n    ".join(parts)
    k = f(BROCCOLI_SCALE)
    shadow = (f'<g transform="translate({f(px + 2.5)} {f(py + 3)}) rotate({f(angle)}) scale({k})" '
              f'fill="#000" fill-opacity="0.28">'
              + "".join(f'<circle cx="{x}" cy="{y}" r="{r}"/>' for x, y, r in CLUSTERS)
              + '<path d="M-6 0 L-9 -24 L9 -24 L6 0 Z"/></g>')
    return [shadow,
            f'<g transform="translate({f(px)} {f(py)}) rotate({f(angle)}) scale({k})">'
            f'\n    {inner}\n  </g>',
            # The pivot cap over the cut end.
            f'<circle cx="{f(px)}" cy="{f(py)}" r="4.5" fill="#2b313c"/>',
            f'<circle cx="{f(px)}" cy="{f(py)}" r="2.4" fill="#9aa5b4"/>']


DEFS = """<defs>
    <linearGradient id="bezel" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#4a5261"/>
      <stop offset="1" stop-color="#2b313c"/>
    </linearGradient>
    <radialGradient id="face" cx="0.5" cy="0.4" r="0.6">
      <stop offset="0" stop-color="#26303d"/>
      <stop offset="1" stop-color="#151b24"/>
    </radialGradient>
    <linearGradient id="spark" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#57e389" stop-opacity="0.35"/>
      <stop offset="1" stop-color="#57e389" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="stalk" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#9dbb6a"/>
      <stop offset="0.45" stop-color="#c9dc95"/>
      <stop offset="1" stop-color="#86a656"/>
    </linearGradient>
    <radialGradient id="floret" cx="0.35" cy="0.3" r="0.75">
      <stop offset="0" stop-color="#4f9a3c"/>
      <stop offset="0.7" stop-color="#2f6f27"/>
      <stop offset="1" stop-color="#1f4d1c"/>
    </radialGradient>
  </defs>"""


def svg() -> str:
    body = "\n  ".join(dial() + broccoli())
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{SIZE}" height="{SIZE}" '
            f'viewBox="0 0 {SIZE} {SIZE}">\n  <title>Proccoli</title>\n  {DEFS}\n  {body}\n</svg>\n')


def main() -> int:
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    sys.path.insert(0, os.path.join(root, "src"))
    from proccoli import APP_ID
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        root, "data", "icons", "hicolor", "scalable", "apps", f"{APP_ID}.svg")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(svg())
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
