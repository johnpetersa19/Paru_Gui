from gi.repository import Gtk, GObject, Adw
from typing import Optional, List, Dict, Any

# The .ui file specifies <template class="ParuSearchBar" parent="GtkBox">
@Gtk.Template(resource_path="/org/gnome/paru-gui/ui/components/search_bar.ui")
class ParuSearchBar(Gtk.Box):
    __gtype_name__ = "ParuSearchBar"

    # --- UI Elements from search_bar.ui ---
    search_entry = Gtk.Template.Child()
    clear_button = Gtk.Template.Child()
    search_options_button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_orientation(Gtk.Orientation.HORIZONTAL) # As defined in UI template
        self.set_spacing(12) # As defined in UI template

        # Connect signals
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.search_entry.connect("activate", self._on_search_activated)
        self.clear_button.connect("clicked", self._on_clear_clicked)
        self.search_options_button.connect("clicked", self._on_search_options_clicked)

        print("ParuSearchBar component initialized.")

    def get_search_text(self) -> str:
        """Returns the current text in the search entry."""
        return self.search_entry.get_text()

    def set_search_text(self, text: str):
        """Sets the text in the search entry."""
        self.search_entry.set_text(text)

    # --- Signal Handlers ---
    def _on_search_changed(self, entry: Gtk.SearchEntry):
        """Handler for 'search-changed' signal (text input changes)."""
        search_text = entry.get_text()
        print(f"SearchBar: Search text changed to '{search_text}'.")
        # This would typically emit a signal to the parent window/controller
        # to trigger intelligent assistance (auto-complete, suggestions).
        # Example: self.emit("search-text-changed", search_text)

    def _on_search_activated(self, entry: Gtk.SearchEntry):
        """Handler for 'activate' signal (Enter key pressed)."""
        command_or_query = entry.get_text()
        print(f"SearchBar: Command/Query activated: '{command_or_query}'.")
        # This would typically emit a signal to the parent window/controller
        # to execute the command or perform a package search.
        # Example: self.emit("command-activated", command_or_query)
        entry.set_text("") # Clear after activation

    def _on_clear_clicked(self, button: Gtk.Button):
        """Handler for the 'Clear' button."""
        self.search_entry.set_text("")
        print("SearchBar: Clear button clicked, search entry cleared.")
        # Example: self.emit("search-cleared")

    def _on_search_options_clicked(self, button: Gtk.Button):
        """Handler for the 'Search Options / Command Assistant' button."""
        print("SearchBar: Search Options button clicked.")
        # This would typically emit a signal to the parent window/controller
        # to show a popover or dialog with search options or command assistant help.
        # Example: self.emit("show-search-options")
