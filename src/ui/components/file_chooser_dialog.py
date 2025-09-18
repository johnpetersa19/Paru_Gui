from gi.repository import Gtk, GObject, Adw, Pango # Pango for EllipsizeMode
import os
from typing import Optional, List, Dict, Any, Tuple

# We need FileItem (from window.py or file_utils.py) to manage the list of files.
# For standalone component, we can define a minimal version or assume it's imported.
# For now, let's assume it's available (e.g., from file_utils if refactored).
# If running standalone, you'd need to mock/define FileItem here.

# As the .ui file specifies <template class="FileChooserDialog" parent="AdwDialog">,
# the class should inherit from Adw.Dialog.
@Gtk.Template(resource_path="/org/gnome/paru-gui/ui/components/file_chooser_dialog.ui")
class FileChooserDialog(Adw.Dialog):
    __gtype_name__ = "FileChooserDialog"

    # --- UI Elements from file_chooser_dialog.ui ---
    # Top Bar
    up_button = Gtk.Template.Child()
    current_path_label = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()

    # File Grid
    files_grid = Gtk.Template.Child() # GtkFlowBox for file cards
    scrolled_window = Gtk.Template.Child() # GtkScrolledWindow around the FlowBox

    # Status Bar / Filters
    file_count_label = Gtk.Template.Child()
    filter_pkgbuild = Gtk.Template.Child()
    filter_packages = Gtk.Template.Child()
    filter_patches = Gtk.Template.Child()
    filter_advanced = Gtk.Template.Child()

    # Action Area
    cancel_button = Gtk.Template.Child()
    open_button = Gtk.Template.Child()

    # --- Internal State ---
    _current_folder_path: str = os.path.expanduser("~")
    _all_file_items: List[Any] = [] # Store all FileItem objects
    _filtered_file_items: List[Any] = [] # Store currently filtered FileItem objects
    _active_filters: List[str] = ["PKGBUILD", "PACKAGE", "PATCH", "ADVANCED"]
    _search_text: str = ""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(800, 600)
        self.set_modal(True)
        self.set_title("Select Folder with Compatible Files") # As defined in UI template

        # Connect signals from the UI template
        self.up_button.connect("clicked", self._on_up_button_clicked)
        self.search_entry.connect("search-changed", self._on_search_entry_changed)
        self.files_grid.connect("child-activated", self._on_file_activated)

        self.filter_pkgbuild.connect("toggled", self._on_filter_toggled)
        self.filter_packages.connect("toggled", self._on_filter_toggled)
        self.filter_patches.connect("toggled", self._on_filter_toggled)
        self.filter_advanced.connect("toggled", self._on_filter_toggled)

        self.cancel_button.connect("clicked", self._on_cancel_clicked)
        self.open_button.connect("clicked", self._on_open_clicked)

        print("FileChooserDialog component initialized.")

    @property
    def current_folder_path(self) -> str:
        return self._current_folder_path

    @current_folder_path.setter
    def current_folder_path(self, path: str):
        self._current_folder_path = path
        self.current_path_label.set_label(path)
        self.current_path_label.set_tooltip_text(path)
        # Trigger a refresh of the files in the grid
        self.scan_and_display_files(path)

    def scan_and_display_files(self, folder_path: str, file_items: Optional[List[Any]] = None):
        """
        Sets the files to be displayed in the grid.
        This method is expected to be called by window.py after asynchronous scanning.

        Args:
            folder_path: The path of the folder that was scanned.
            file_items: A list of FileItem objects from the scan.
        """
        self._current_folder_path = folder_path
        self._all_file_items = file_items if file_items is not None else []
        self.current_path_label.set_label(folder_path)
        self.current_path_label.set_tooltip_text(folder_path)
        self._apply_filters_and_search()

    def _apply_filters_and_search(self):
        """Applies current filters and search text to the displayed files."""
        self._filtered_file_items = []
        for item in self._all_file_items:
            # Apply type filters
            if item.is_dir: # Directories are always shown unless explicitly filtered out
                self._filtered_file_items.append(item)
                continue

            if item.file_type in self._active_filters:
                # Apply search text filter
                if self._search_text.lower() in item.name.lower() or \
                   self._search_text.lower() in item.path.lower():
                    self._filtered_file_items.append(item)

        self._populate_files_grid()

    def _populate_files_grid(self):
        """Clears and repopulates the GtkFlowBox with filtered files."""
        while self.files_grid.get_first_child() is not None:
            self.files_grid.remove(self.files_grid.get_first_child())

        for item in self._filtered_file_items:
            # This logic is similar to window.py's _update_content_view but simplified
            # for the dialog's purpose. It should ideally re-use card templates.
            card_frame: Optional[Gtk.Frame] = None
            if item.is_dir:
                card_frame = Gtk.Frame()
                card_frame.add_css_class("card")
                card_frame.add_css_class("file-card")
                card_frame.set_size_request(220, 180) # Adjust size for directory card

                card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_start=12, margin_end=12, margin_top=12, margin_bottom=12)
                icon = Gtk.Image.new_from_icon_name("folder-symbolic", Gtk.IconSize.LARGE)
                icon.set_pixel_size(48)
                name_label = Gtk.Label(label=item.name, wrap=True, max_width_chars=20)
                name_label.add_css_class("heading")
                path_label = Gtk.Label(label=f"Folder: {os.path.basename(item.path)}", wrap=True, max_width_chars=25)
                path_label.add_css_class("caption")
                path_label.add_css_class("dim-label")

                card_box.append(icon)
                card_box.append(name_label)
                card_box.append(path_label)
                card_frame.set_child(card_box)
                card_frame.set_tooltip_text(item.path) # Store path in tooltip for later retrieval
            else:
                # For file types, re-use window.py's card creation logic or simplify
                # For now, let's create a generic card
                card_frame = Gtk.Frame()
                card_frame.add_css_class("card")
                card_frame.add_css_class("file-card")
                card_frame.set_size_request(220, 250)

                card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_start=12, margin_end=12, margin_top=12, margin_bottom=12)
                icon = Gtk.Image.new_from_icon_name(item.get_icon_name(), Gtk.IconSize.LARGE)
                icon.set_pixel_size(48)
                name_label = Gtk.Label(label=item.name, wrap=True, max_width_chars=20)
                name_label.add_css_class("heading")
                type_label = Gtk.Label(label=item.file_type, wrap=True, max_width_chars=25)
                type_label.add_css_class("caption")
                type_label.add_css_class("dim-label")

                card_box.append(icon)
                card_box.append(name_label)
                card_box.append(type_label)
                card_frame.set_child(card_box)
                card_frame.set_tooltip_text(item.path)

            if card_frame:
                flowbox_child = Gtk.FlowBoxChild()
                flowbox_child.set_child(card_frame)
                self.files_grid.append(flowbox_child)

        self.file_count_label.set_label(f"{len(self._filtered_file_items)} files found")
        self.files_grid.show_all()

    # --- Signal Handlers ---
    def _on_up_button_clicked(self, button: Gtk.Button):
        """Navigates up one level in the directory structure."""
        parent_path = os.path.dirname(self._current_folder_path)
        if parent_path != self._current_folder_path: # Avoid going up from root
            self.current_folder_path = parent_path
        # No need to re-scan here; current_folder_path.setter will trigger it.

    def _on_search_entry_changed(self, search_entry: Gtk.SearchEntry):
        """Filters files based on search text."""
        self._search_text = search_entry.get_text()
        self._apply_filters_and_search()

    def _on_filter_toggled(self, toggle_button: Gtk.ToggleButton):
        """Handles toggling of file type filter buttons."""
        filter_name = toggle_button.get_name() # e.g., "PKGBUILD"
        if toggle_button.get_active():
            if filter_name not in self._active_filters:
                self._active_filters.append(filter_name)
        else:
            if filter_name in self._active_filters:
                self._active_filters.remove(filter_name)
        self._apply_filters_and_search()

    def _on_file_activated(self, flowbox: Gtk.FlowBox, child: Gtk.FlowBoxChild):
        """Handles activation (click) of a file/directory card."""
        item_path = child.get_child().get_tooltip_text() # Retrieve path from tooltip
        if os.path.isdir(item_path):
            self.current_folder_path = item_path # Navigate into directory
        else:
            # A file was selected. Emit a signal to the parent window.
            print(f"File selected in FileChooserDialog: {item_path}")
            # The parent window (ParuGuiWindow) will connect to this dialog and handle selection.
            # Example: self.emit("file-selected", item_path)
            # For now, let's just close the dialog.
            self.close()

    def _on_cancel_clicked(self, button: Gtk.Button):
        """Closes the dialog without selecting a file."""
        self.close()

    def _on_open_clicked(self, button: Gtk.Button):
        """
        Handles the "Open" button click.
        If a folder is selected, it effectively navigates into it.
        If a file is selected (via activation in grid), this button might be hidden or re-purposed.
        For simplicity, this button will just close the dialog and notify parent of current folder.
        """
        print(f"FileChooserDialog: Open button clicked for folder: {self.current_folder_path}")
        # The parent window (ParuGuiWindow) will connect to this dialog and get the path.
        # Example: self.emit("folder-selected", self.current_folder_path)
        self.close()


    # You might want to add a method like this in window.py to trigger the dialog and get result
    # def show(self, callback: Callable[[Optional[str]], None]):
    #     self._callback = callback
    #     super().show()
    # def _on_cancel_clicked(self, button):
    #     self._callback(None)
    #     self.close()
    # def _on_open_clicked(self, button):
    #     self._callback(self.current_folder_path)
    #     self.close()
