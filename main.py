import sys
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw

# Attempt import using the structure defined by the application's resource path and GResource
# The window module is expected to be at the same level as the gear package within the paru_gui namespace
try:
    # Standard absolute import assuming correct package structure and sys.path setup by launcher
    from paru_gui.window import ParuGUIWindow
except ImportError:
    # Fallback if direct absolute import fails
    # Attempt relative import from parent (src directory) if launched from there
    try:
        from ..window import ParuGUIWindow
    except (ImportError, ValueError):
        # Final fallback: add parent directory to path and import
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from window import ParuGUIWindow


class ParuGUIApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="org.gnome.paru-gui",
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        self.window = None

    def do_activate(self):
        self.window = ParuGUIWindow(application=self)
        self.window.present()


def main():
    app = ParuGUIApplication()
    return app.run(sys.argv)

