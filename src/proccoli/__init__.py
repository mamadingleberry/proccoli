"""Proccoli: a GTK 4 / libadwaita system monitor (prototype name).

The app's identity lives only here. To rename the app, edit these constants,
then rename this package directory and the files in data/.
"""

APP_ID = "io.github.mamadingleberry.Proccoli"
APP_NAME = "Proccoli"
# The two programs: the recorder (no display) and the window.
COLLECTOR = "proccoli"
WINDOW = "proccoli-gui"
__version__ = "0.6.0"

# Our own symbolic icons (data/icons): Adwaita has none for these.
PROCESSOR_ICON = f"{APP_ID}-processor-symbolic"
MEMORY_ICON = f"{APP_ID}-memory-symbolic"
GPU_ICON = f"{APP_ID}-gpu-symbolic"
OVERVIEW_ICON = f"{APP_ID}-overview-symbolic"

# Apps and processes without an icon of their own: a solid puzzle piece
# (white in the dark style; Adwaita's own is an outline).
MISSING_APP_ICON = f"{APP_ID}-missing-app-symbolic"
