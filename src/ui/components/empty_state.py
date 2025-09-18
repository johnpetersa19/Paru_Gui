from gi.repository import Gtk, GObject, Adw
from typing import Optional, List, Dict, Any

# The .ui file specifies <object class="GtkBox" id="empty_state_box">
# We'll make the template class inherit from Gtk.Box as per the UI file's structure.
@Gtk.Template(resource_path="/org/gnome/paru-gui/ui/components/empty_state.ui")
class EmptyState(Gtk.Box):
    __gtype_name__ = "EmptyState"

    # --- UI Elements from empty_state.ui ---
    empty_icon = Gtk.Template.Child()
    empty_title_label = Gtk.Template.Child()
    empty_description_label = Gtk.Template.Child()
    empty_options_box = Gtk.Template.Child() # Container for action buttons
    download_pkgbuild_button = Gtk.Template.Child()
    builder_mode_button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_orientation(Gtk.Orientation.VERTICAL) # As defined in UI template
        self.set_spacing(24) # As defined in UI template

        # Connect buttons (these would typically emit signals to the parent window/controller)
        self.download_pkgbuild_button.connect("clicked", self._on_download_pkgbuild_clicked)
        self.builder_mode_button.connect("clicked", self._on_builder_mode_clicked)

        print("EmptyState component initialized.")

    def set_message(self, title: str, description: str, icon_name: str = "folder-symbolic", show_options: bool = True):
        """
        Sets the message and icon for the empty state.

        Args:
            title: The main title for the empty state.
            description: A more detailed description.
            icon_name: The Gtk icon name to display.
            show_options: If True, shows the download/builder buttons.
        """
        self.empty_title_label.set_label(title)
        self.empty_description_label.set_label(description)
        self.empty_icon.set_from_icon_name(icon_name)
        self.empty_options_box.set_visible(show_options)
        self.set_visible(True) # Ensure the empty state itself is visible

    def _on_download_pkgbuild_clicked(self, button: Gtk.Button):
        """Handler for the 'Download PKGBUILD' button."""
        print("EmptyState: Download PKGBUILD button clicked.")
        # This should emit a signal or call a method on the parent window/controller
        # Example: self.get_root().emit("download-pkgbuild-request")

    def _on_builder_mode_clicked(self, button: Gtk.Button):
        """Handler for the 'Builder Mode (Wizard)' button."""
        print("EmptyState: Builder Mode button clicked.")
        # This should emit a signal or call a method on the parent window/controller
        # Example: self.get_root().emit("builder-mode-request")
