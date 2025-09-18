from gi.repository import Gtk, GObject, Adw
from typing import List, Dict, Any, Optional

# The .ui file specifies <template class="WelcomeScreen" parent="GtkBox">
@Gtk.Template(resource_path="/org/gnome/paru-gui/ui/screens/welcome_screen.ui")
class WelcomeScreen(Gtk.Box):
    __gtype_name__ = "WelcomeScreen"

    # --- UI Elements from welcome_screen.ui ---
    select_file_button = Gtk.Template.Child()
    select_folder_button = Gtk.Template.Child()
    recent_files_list = Gtk.Template.Child() # This is a GtkListBox
    # The actual GtkFlowBox for recent dirs is part of window.ui (recent_dirs_flowbox)

    # Buttons at the bottom
    # Assuming direct template connection via signals or parent will connect
    # on_tour_guide_clicked
    # on_documentation_clicked

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_orientation(Gtk.Orientation.VERTICAL) # As defined in UI template
        self.set_spacing(24) # As defined in UI template

        # Connect internal signals (parent window will connect main action buttons)
        # self.select_file_button.connect("clicked", self._on_select_file_clicked) # Handled by window.py
        # self.select_folder_button.connect("clicked", self._on_select_folder_clicked) # Handled by window.py

        # Connect other buttons if this class manages their logic directly
        tour_guide_button = self.builder.get_object('tour_guide_button') # Assuming an ID for it
        if tour_guide_button:
            tour_guide_button.connect("clicked", self._on_tour_guide_clicked)

        documentation_button = self.builder.get_object('documentation_button') # Assuming an ID for it
        if documentation_button:
            documentation_button.connect("clicked", self._on_documentation_clicked)

        print("WelcomeScreen initialized.")

    # Methods to populate recent files list (if needed)
    def add_recent_file_entry(self, filename: str, filepath: str):
        """Adds an entry to the recent files list."""
        row = Gtk.ListBoxRow()
        label = Gtk.Label(label=os.path.basename(filename), halign=Gtk.Align.START)
        row.set_child(label)
        row.set_tooltip_text(filepath)
        self.recent_files_list.append(row)
        self.recent_files_list.show_all()

    def clear_recent_files_list(self):
        """Clears all entries from the recent files list."""
        while self.recent_files_list.get_first_child() is not None:
            self.recent_files_list.remove(self.recent_files_list.get_first_child())

    def _on_tour_guide_clicked(self, button: Gtk.Button):
        """Handler for the Tour Guide button."""
        print("Tour Guide button clicked on Welcome Screen.")
        # This signal should be handled by window.py to trigger TourGuide.show_initial_tour()
        # self.get_root().tour_guide.show_initial_tour() # Conceptual call

    def _on_documentation_clicked(self, button: Gtk.Button):
        """Handler for the Documentation button."""
        print("Documentation button clicked on Welcome Screen.")
        # This signal should be handled by window.py to open documentation URL
        # Gtk.show_uri(self.get_root(), "https://paru-gui.org/docs", Gdk.CURRENT_TIME) # Conceptual call
