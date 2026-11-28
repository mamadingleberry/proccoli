"""Preferences' Style and Palette rows, each choice drawn as a swatch."""

from __future__ import annotations

from gi.repository import Adw, Gtk
from ...core.palette import PALETTES, hex_to_rgb
from ...core.styles import STYLES


class AppearanceRows:
    """The style and palette choosers (a part of ``PreferencesDialog``)."""

    def _style_row(self, group) -> Adw.ComboRow:
        """The *Style* combo: each entry shows its window and text colors."""
        row = self._combo(group, "color-scheme", "Style", [(s.id, s.name) for s in STYLES],
                          "Follow System uses the desktop's light or dark style")
        factory = Gtk.SignalListItemFactory()

        def setup(_f, item):
            box = Gtk.Box(spacing=12)
            box.append(Gtk.Label(xalign=0, hexpand=True))
            box.append(Gtk.DrawingArea(content_width=28, content_height=16,
                                       valign=Gtk.Align.CENTER))
            item.set_child(box)

        def bind(_f, item):
            box = item.get_child()
            name = item.get_item().get_string()
            style = next(s for s in STYLES if s.name == name)
            box.get_first_child().set_label(style.name)
            box.get_last_child().set_draw_func(self._draw_style_swatch, style)
        factory.connect("setup", setup)
        factory.connect("bind", bind)
        row.set_factory(factory)
        return row

    @staticmethod
    def style_swatch_colors(style) -> tuple[str, str]:
        """(background, text) for a style's swatch."""
        if style.tinted:
            return style.colors["window-bg-color"], style.colors["window-fg-color"]
        return {"light": ("#fafafb", "#323232"), "dark": ("#222226", "#ffffff"),
                "system": ("#fafafb", "#222226")}[style.base]

    def _draw_style_swatch(self, _area, cr, width, height, style) -> None:
        bg, fg = self.style_swatch_colors(style)
        cr.set_source_rgb(*hex_to_rgb(bg))
        cr.rectangle(0, 0, width, height)
        cr.fill()
        if style.base == "system":           # half light, half dark
            cr.set_source_rgb(*hex_to_rgb(fg))
            cr.rectangle(width / 2, 0, width / 2, height)
            cr.fill()
            return
        cr.set_source_rgb(*hex_to_rgb(fg))
        cr.arc(width / 2, height / 2, height / 4, 0, 6.2832)
        cr.fill()

    def _palette_row(self, group) -> Adw.ComboRow:
        """The *Color Palette* combo: each entry shows its colors."""
        row = self._combo(group, "palette", "Color Palette",
                          [(p.id, p.name) for p in PALETTES],
                          "Colors of graphs, meters and the accent")
        factory = Gtk.SignalListItemFactory()

        def setup(_f, item):
            box = Gtk.Box(spacing=12)
            box.append(Gtk.Label(xalign=0, hexpand=True))
            swatch = Gtk.DrawingArea(content_width=6 * 14, content_height=12,
                                     valign=Gtk.Align.CENTER)
            box.append(swatch)
            item.set_child(box)

        def bind(_f, item):
            box = item.get_child()
            label, swatch = box.get_first_child(), box.get_last_child()
            # Look the palette up by name: the row's own button binds the
            # selected item without a list position.
            name = item.get_item().get_string()
            palette = next(p for p in PALETTES if p.name == name)
            label.set_label(palette.name)
            swatch.set_draw_func(self._draw_swatch, palette)
            swatch.update_property([Gtk.AccessibleProperty.LABEL],
                                   [f"{palette.name} colors"])
        factory.connect("setup", setup)
        factory.connect("bind", bind)
        row.set_factory(factory)
        return row

    def _draw_swatch(self, _area, cr, width, height, palette) -> None:
        dark = self.theme.dark if self.theme is not None else False
        colors = palette.colors(dark)[:6]
        if palette.follows_accent and self.theme is not None:
            colors = [None] + list(colors[:5])        # the desktop's accent first
        r = height / 2
        for i, color in enumerate(colors):
            rgb = self.theme.system_accent() if color is None else hex_to_rgb(color)
            cr.set_source_rgb(*rgb)
            cr.arc(r + i * 14, height / 2, r, 0, 6.2832)
            cr.fill()
