from gi.repository import Gtk, GObject, Adw, Pango # Pango for EllipsizeMode
import os
from typing import Optional, List, Dict, Any, Tuple

# Ensure parent class Adw.Bin or Gtk.Box is imported if parent is Adw.Bin/Gtk.Box
# The .ui file specifies <template class="ContentView" parent="GtkBox">
# So, Gtk.Box is the correct parent.
@Gtk.Template(resource_path="/org/gnome/paru-gui/ui/screens/content_view.ui")
class ContentView(Gtk.Box):
    __gtype_name__ = "ContentView"

    # --- UI Elements from content_view.ui ---
    # Path Bar
    up_button = Gtk.Template.Child()
    current_path_label = Gtk.Template.Child()
    filter_pkgbuild = Gtk.Template.Child()
    filter_packages = Gtk.Template.Child()
    filter_patches = Gtk.Template.Child()
    filter_advanced = Gtk.Template.Child()

    # Main Content Area
    content_cards = Gtk.Template.Child() # This is the GtkFlowBox
    scrolled_content = Gtk.Template.Child() # The GtkScrolledWindow around the FlowBox

    # Terminal Area (managed by TerminalManager, but we need to pass its container)
    terminal_area = Gtk.Template.Child() # The main GtkBox for the terminal panel

    # Status Bar
    file_count_label = Gtk.Template.Child()

    # --- Internal State ---
    _current_folder_path: str = os.path.expanduser("~") # Default to home
    _active_filters: List[str] = ["PKGBUILD", "PACKAGE", "PATCH", "ADVANCED"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_orientation(Gtk.Orientation.VERTICAL) # As defined in UI template
        self.set_spacing(16) # As defined in UI template

        # Connect filter buttons
        self.filter_pkgbuild.connect("toggled", self._on_filter_toggled)
        self.filter_packages.connect("toggled", self._on_filter_toggled)
        self.filter_patches.connect("toggled", self._on_filter_toggled)
        self.filter_advanced.connect("toggled", self._on_filter_toggled)

        # Connect up button (handled by window.py, but for internal cohesion if needed)
        # self.up_button.connect("clicked", self._on_up_button_clicked)

        # This class will primarily be responsible for updating its own UI elements
        # based on data provided by window.py (which fetches data asynchronously).
        print("ContentView initialized.")

    @property
    def current_folder_path(self) -> str:
        return self._current_folder_path

    @current_folder_path.setter
    def current_folder_path(self, path: str):
        self._current_folder_path = path
        self.current_path_label.set_label(path)
        self.current_path_label.set_tooltip_text(path)

    def update_file_count(self, count: int):
        """Updates the label showing the number of files found."""
        self.file_count_label.set_label(f"{count} files found")

    def _on_filter_toggled(self, toggle_button: Gtk.ToggleButton):
        """Handles toggling of file type filter buttons."""
        filter_name = toggle_button.get_name() # e.g., "PKGBUILD"
        if toggle_button.get_active():
            if filter_name not in self._active_filters:
                self._active_filters.append(filter_name)
        else:
            if filter_name in self._active_filters:
                self._active_filters.remove(filter_name)

        # Trigger a refresh of the content cards based on new filters
        # This would typically notify the parent window or a controller
        # to re-scan/re-display with updated filters.
        print(f"Filters changed: {self._active_filters}. Needs content refresh.")
        # self.emit("filters-changed", self._active_filters) # Example of custom signal

    # You might add methods here to dynamically create/remove/update the cards
    # in the self.content_cards (GtkFlowBox) when data is provided.
    # The current window.py already has a version of this logic; it can be moved here.

    def add_card_to_flowbox(self, card_widget: Gtk.Widget):
        """Adds a new card widget to the content flowbox."""
        flowbox_child = Gtk.FlowBoxChild()
        flowbox_child.set_child(card_widget)
        self.content_cards.append(flowbox_child)
        self.content_cards.show_all() # Ensure new children are shown

    def clear_cards(self):
        """Clears all cards from the content flowbox."""
        while self.content_cards.get_first_child() is not None:
            self.content_cards.remove(self.content_cards.get_first_child())

    # Placeholder for lazy loading - to be implemented with scroll events
    # def _on_scroll_event(self, scrolled_window, event):
    #     adj = scrolled_window.get_vadjustment()
    #     if adj.get_value() >= adj.get_upper() - adj.get_page_size() * 1.5:
    #         print("Near bottom, trigger lazy load!")
    #         # self.emit("lazy-load-request")

    # Connect to scroll adjustment for lazy loading (conceptual)
    # def do_realize(self):
    #     Gtk.Box.do_realize(self)
    #     self.scrolled_content.get_vadjustment().connect("changed", self._on_scroll_event)
