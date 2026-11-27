# Milestone 26: Optional authentication at launch

*✅ Done.* Plus a main-menu entry to bring it back; real password prompts untested (need a password)

Proccoli offers, once at start-up, to authenticate for everything that needs
administrator rights. Declining changes nothing: the existing buttons
(Memory's *Authenticate*, the GPU's *Show Detailed Statistics*, Processes'
*Show Drive I/O of All Processes*) stay.

| Step | Create / change | Test |
|---|---|---|
| 26.1 | `ui/elevation.py` (no widgets): `ElevationOffer(id, title, run(done))`; `ResourcePage.elevation_offer()` (None by default) on Memory (no module data), GPU (details need rights) and Processes (helper available, I/O not elevated) | Unit per page |
| 26.2 | `ElevationRunner`: runs the chosen offers **one after another** (each may show a polkit prompt; never two at once), reports each result | Unit with fake offers: order, a failure or cancel doesn't stop the rest |
| 26.3 | Schema `auth-at-launch` (default true); `LaunchAuthDialog` (`Adw.AlertDialog`): what would be unlocked, *Authenticate* / *Not Now*, "Don't ask at start-up" | Dialog test |
| 26.4 | `MainWindow` presents it after the first frame when there are offers and the setting is on; Preferences → General gets *Ask for Administrator Rights at Start-Up* | UI test: no offers, no dialog; Not Now leaves the buttons |
