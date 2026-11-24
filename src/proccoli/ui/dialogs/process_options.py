"""Process Options: priority (niceness) and processor affinity."""

from __future__ import annotations

from gi.repository import Adw, Gtk

# Priority names and the niceness each one sets (with *Show Niceness Values*
# off, like Resources).
PRIORITIES = [("Very High", -15), ("High", -5), ("Normal", 0), ("Low", 5), ("Very Low", 15)]


def priority_index(nice: int) -> int:
    """The priority name closest to a niceness value."""
    return min(range(len(PRIORITIES)), key=lambda i: abs(PRIORITIES[i][1] - nice))


class ProcessOptionsDialog(Adw.Dialog):
    def __init__(self, process, system, actions, settings, cpu_count: int,
                 report=lambda text: None) -> None:
        super().__init__(title="Process Options", content_width=420)
        self.process = process
        self.actions = actions
        self.report = report
        self.detailed = settings.get("detailed-priority")
        try:
            self.original_nice = system.get_priority(process.pid)
            self.original_cpus = system.get_affinity(process.pid)
        except OSError:
            self.original_nice = process.nice
            self.original_cpus = set(range(cpu_count))

        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title=process.name,
                                     description=f"Process ID {process.pid}")
        if self.detailed:
            self.nice_row = Adw.SpinRow.new_with_range(-20, 19, 1)
            self.nice_row.set_title("Niceness")
            self.nice_row.set_subtitle("A lower niceness means a higher priority")
            self.nice_row.set_value(self.original_nice)
            group.add(self.nice_row)
            self.priority_row = None
        else:
            self.priority_row = Adw.ComboRow(
                title="Priority", model=Gtk.StringList.new([n for n, _ in PRIORITIES]))
            self.priority_row.set_selected(priority_index(self.original_nice))
            group.add(self.priority_row)
            self.nice_row = None

        self.affinity = Adw.ExpanderRow(
            title="Processor Affinity",
            subtitle="Which logical CPUs the process may run on")
        self.cpu_checks = []
        for cpu in range(cpu_count):
            check = Gtk.CheckButton(active=cpu in self.original_cpus,
                                    valign=Gtk.Align.CENTER)
            check.connect("toggled", lambda *_: self._validate())
            row = Adw.ActionRow(title=f"CPU {cpu}", activatable_widget=check)
            row.add_prefix(check)
            self.affinity.add_row(row)
            self.cpu_checks.append(check)
        group.add(self.affinity)
        page.add(group)

        self.apply_button = Gtk.Button(label="Apply")
        self.apply_button.add_css_class("suggested-action")
        self.apply_button.connect("clicked", lambda *_: self.apply())
        header = Adw.HeaderBar()
        header.pack_end(self.apply_button)
        toolbar = Adw.ToolbarView(content=page)
        toolbar.add_top_bar(header)
        self.set_child(toolbar)

    def selected_nice(self) -> int:
        if self.nice_row is not None:
            return int(self.nice_row.get_value())
        return PRIORITIES[self.priority_row.get_selected()][1]

    def selected_cpus(self) -> set[int]:
        return {i for i, c in enumerate(self.cpu_checks) if c.get_active()}

    def _validate(self) -> None:
        self.apply_button.set_sensitive(bool(self.selected_cpus()))  # never zero CPUs

    def apply(self) -> None:
        pid = self.process.pid
        nice, cpus = self.selected_nice(), self.selected_cpus()
        if nice != self.original_nice:
            self.actions.set_priority(pid, nice, self.report)
        if cpus and cpus != self.original_cpus:
            self.actions.set_affinity(pid, cpus, self.report)
        self.close()
