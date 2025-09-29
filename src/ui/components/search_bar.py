from gi.repository import Gtk, GObject, Adw
from typing import Optional, List, Dict, Any
from .command_assistant import CommandAssistant

@Gtk.Template(resource_path="/org/gnome/paru-gui/ui/components/search_bar.ui")
class ParuSearchBar(Gtk.Box):
    __gtype_name__ = "ParuSearchBar"

    search_entry = Gtk.Template.Child()
    clear_button = Gtk.Template.Child()
    search_options_button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_spacing(12)

        self.search_entry.connect("search-changed", self._on_search_changed)
        self.search_entry.connect("activate", self._on_search_activated)
        self.clear_button.connect("clicked", self._on_clear_clicked)
        self.search_options_button.connect("clicked", self._on_search_options_clicked)

    def get_search_text(self) -> str:
        return self.search_entry.get_text()

    def set_search_text(self, text: str):
        self.search_entry.set_text(text)

    def _on_search_changed(self, entry: Gtk.SearchEntry):
        search_text = entry.get_text()

    def _on_search_activated(self, entry: Gtk.SearchEntry):
        command_or_query = entry.get_text()
        entry.set_text("")

    def _on_clear_clicked(self, button: Gtk.Button):
        self.search_entry.set_text("")

    def _on_search_options_clicked(self, button: Gtk.Button):
        try:
            command_assistant = CommandAssistant()

            parent_window = self.get_root()
            if parent_window and isinstance(parent_window, Gtk.Window):
                command_assistant.set_transient_for(parent_window)
                command_assistant.set_modal(True)

            command_assistant.present()
        except Exception:
            pass
