from gi.repository import Gtk, GObject, Adw
from typing import Optional, List, Dict, Any

# The .ui file specifies <object class="GtkShortcutsWindow" id="help_overlay">
@Gtk.Template(resource_path="/org/gnome/paru-gui/ui/components/help-overlay.ui")
class HelpOverlay(Gtk.ShortcutsWindow):
    __gtype_name__ = "HelpOverlay"

    # --- UI Elements from help-overlay.ui ---
    # GtkShortcutsWindow automatically manages sections and groups within.
    # No direct @Gtk.Template.Child() is needed for the shortcuts themselves,
    # as they are defined structurally in the XML.

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_modal(True) # As defined in UI template
        # The GtkShortcutsWindow gets its content directly from the .ui file.
        # No need to manually populate sections/shortcuts from Python here
        # unless dynamic content is required.

        # The 'accelerator' properties in the .ui file define the keybindings
        # for showing/hiding this window.
        print("HelpOverlay component initialized.")

    # No specific methods are usually needed here unless you want to dynamically
    # add/remove shortcuts or provide custom logic beyond what GtkShortcutsWindow handles.
    # The main window will simply 'present' this object.
