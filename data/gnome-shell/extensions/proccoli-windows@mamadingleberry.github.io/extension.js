// Proccoli Window Switching: lets Proccoli (a system monitor) bring any
// running app's window to the front. GNOME on Wayland lets an app focus
// only its own windows; code inside the Shell may focus any. This
// extension can do two things, on the user's own session bus only:
//
//   List()        -> a(tussu): window id, process id, app id (the
//                    .desktop name without ".desktop"), title, and when
//                    the user last used it (for "the most recent")
//   Activate(id)  -> b: bring that window to the front
//
// Object path /io/github/mamadingleberry/Proccoli/Windows on the Shell's
// connection (destination org.gnome.Shell). Proccoli's core/windows.py
// is the other side; tests/test_windows.py checks the two agree.

import Gio from 'gi://Gio';
import Shell from 'gi://Shell';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const OBJECT_PATH = '/io/github/mamadingleberry/Proccoli/Windows';
const INTERFACE = `
<node>
  <interface name="io.github.mamadingleberry.Proccoli.Windows">
    <method name="List">
      <arg type="a(tussu)" direction="out" name="windows"/>
    </method>
    <method name="Activate">
      <arg type="t" direction="in" name="id"/>
      <arg type="b" direction="out" name="ok"/>
    </method>
  </interface>
</node>`;

function windows() {
    return global.get_window_actors()
        .map(actor => actor.get_meta_window())
        .filter(win => win && !win.is_skip_taskbar());
}

class Windows {
    List() {
        const tracker = Shell.WindowTracker.get_default();
        return windows().map(win => {
            const app = tracker.get_window_app(win);
            const appId = app ? (app.get_id() || '').replace(/\.desktop$/, '') : '';
            return [win.get_id(), win.get_pid() || 0, appId, win.get_title() || '',
                win.get_user_time() || 0];
        });
    }

    Activate(id) {
        const win = windows().find(w => w.get_id() === id);
        if (!win)
            return false;
        Main.activateWindow(win);
        return true;
    }
}

export default class ProccoliWindowsExtension extends Extension {
    enable() {
        this._dbus = Gio.DBusExportedObject.wrapJSObject(INTERFACE, new Windows());
        this._dbus.export(Gio.DBus.session, OBJECT_PATH);
    }

    disable() {
        this._dbus?.unexport();
        this._dbus = null;
    }
}
