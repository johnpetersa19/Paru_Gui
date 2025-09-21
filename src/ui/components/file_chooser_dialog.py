from gi.repository import Gtk, GObject, Adw, Pango
import os
from typing import Optional, List, Dict, Any, Tuple, Callable

class FileItem:
    def __init__(self, name: str, path: str, is_dir: bool = False, file_type: str = "UNKNOWN"):
        self.name = name
        self.path = path
        self.is_dir = is_dir
        self.file_type = file_type

    def get_icon_name(self) -> str:
        if self.is_dir:
            return "folder-symbolic"
        return {
            "PKGBUILD": "text-x-script-symbolic",
            "PACKAGE": "package-x-generic-symbolic",
            "PATCH": "text-x-patch-symbolic",
            "ADVANCED": "text-x-generic-symbolic"
        }.get(self.file_type, "text-x-generic-symbolic")

@Gtk.Template(resource_path="/org/gnome/paru-gui/ui/components/file_chooser_dialog.ui")
class FileChooserDialog(Adw.Dialog):
    __gtype_name__ = "FileChooserDialog"

    up_button = Gtk.Template.Child()
    current_path_label = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()
    files_grid = Gtk.Template.Child()
    scrolled_window = Gtk.Template.Child()
    file_count_label = Gtk.Template.Child()
    filter_pkgbuild = Gtk.Template.Child()
    filter_packages = Gtk.Template.Child()
    filter_patches = Gtk.Template.Child()
    filter_advanced = Gtk.Template.Child()
    cancel_button = Gtk.Template.Child()
    open_button = Gtk.Template.Child()

    __gsignals__ = {
        'file-selected': (GObject.SignalFlags.RUN_LAST, None, (str,)),
        'folder-selected': (GObject.SignalFlags.RUN_LAST, None, (str,)),
        'dialog-cancelled': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_folder_path: str = os.path.expanduser("~")
        self._all_file_items: List[FileItem] = []
        self._filtered_file_items: List[FileItem] = []
        self._active_filters: List[str] = ["PKGBUILD", "PACKAGE", "PATCH", "ADVANCED"]
        self._search_text: str = ""
        self._callback: Optional[Callable] = None

        self.set_default_size(800, 600)
        self.set_modal(True)
        self.set_title("Select Folder with Compatible Files")
        self._connect_ui_signals()
        self._initialize_dialog()

    def _connect_ui_signals(self):
        self.up_button.connect("clicked", self.on_up_button_clicked)
        self.search_entry.connect("search-changed", self.on_search_entry_changed)
        self.files_grid.connect("child-activated", self.on_file_activated)
        self.filter_pkgbuild.connect("toggled", self.on_filter_toggled)
        self.filter_packages.connect("toggled", self.on_filter_toggled)
        self.filter_patches.connect("toggled", self.on_filter_toggled)
        self.filter_advanced.connect("toggled", self.on_filter_toggled)
        self.cancel_button.connect("clicked", self.on_cancel_clicked)
        self.open_button.connect("clicked", self.on_open_clicked)

    def _initialize_dialog(self):
        self.filter_pkgbuild.set_active(True)
        self.filter_packages.set_active(True)
        self.filter_patches.set_active(True)
        self.filter_advanced.set_active(True)
        self.current_folder_path = self._current_folder_path
        self.files_grid.set_selection_mode(Gtk.SelectionMode.NONE)
        self.files_grid.set_activate_on_single_click(True)

    @property
    def current_folder_path(self) -> str:
        return self._current_folder_path

    @current_folder_path.setter
    def current_folder_path(self, path: str):
        self._current_folder_path = path
        self.current_path_label.set_label(path)
        self.current_path_label.set_tooltip_text(path)
        self._mock_scan_folder(path)

    def show_for_selection(self, callback: Callable[[Optional[str]], None]):
        self._callback = callback
        self.present()

    def scan_and_display_files(self, folder_path: str, file_items: Optional[List[FileItem]] = None):
        self._current_folder_path = folder_path
        self._all_file_items = file_items if file_items is not None else []
        self.current_path_label.set_label(folder_path)
        self.current_path_label.set_tooltip_text(folder_path)
        self._apply_filters_and_search()

    def on_up_button_clicked(self, button: Gtk.Button):
        parent_path = os.path.dirname(self._current_folder_path)
        if parent_path != self._current_folder_path:
            self.current_folder_path = parent_path

    def on_search_entry_changed(self, search_entry: Gtk.SearchEntry):
        self._search_text = search_entry.get_text()
        self._apply_filters_and_search()

    def on_filter_toggled(self, toggle_button: Gtk.ToggleButton):
        filter_name = toggle_button.get_name()
        if toggle_button.get_active():
            if filter_name not in self._active_filters:
                self._active_filters.append(filter_name)
        else:
            if filter_name in self._active_filters:
                self._active_filters.remove(filter_name)
        self._apply_filters_and_search()

    def on_file_activated(self, flowbox: Gtk.FlowBox, child: Gtk.FlowBoxChild):
        item_path = child.get_child().get_tooltip_text()
        if os.path.isdir(item_path):
            self.current_folder_path = item_path
        else:
            self.emit("file-selected", item_path)
            if self._callback:
                self._callback(item_path)
            self.close()

    def on_cancel_clicked(self, button: Gtk.Button):
        self.emit("dialog-cancelled")
        if self._callback:
            self._callback(None)
        self.close()

    def on_open_clicked(self, button: Gtk.Button):
        self.emit("folder-selected", self.current_folder_path)
        if self._callback:
            self._callback(self.current_folder_path)
        self.close()

    def _apply_filters_and_search(self):
        self._filtered_file_items = []
        for item in self._all_file_items:
            if item.is_dir:
                if self._matches_search(item):
                    self._filtered_file_items.append(item)
                continue

            if item.file_type in self._active_filters:
                if self._matches_search(item):
                    self._filtered_file_items.append(item)

        self._populate_files_grid()

    def _matches_search(self, item: FileItem) -> bool:
        if not self._search_text:
            return True
        search_lower = self._search_text.lower()
        return (search_lower in item.name.lower() or
                search_lower in item.path.lower())

    def _populate_files_grid(self):
        while self.files_grid.get_first_child() is not None:
            self.files_grid.remove(self.files_grid.get_first_child())

        for item in self._filtered_file_items:
            card_frame = self._create_file_card(item)
            if card_frame:
                flowbox_child = Gtk.FlowBoxChild()
                flowbox_child.set_child(card_frame)
                self.files_grid.append(flowbox_child)

        count = len(self._filtered_file_items)
        self.file_count_label.set_label(f"{count} file{'s' if count != 1 else ''} found")

    def _create_file_card(self, item: FileItem) -> Optional[Gtk.Frame]:
        card_frame = Gtk.Frame()
        card_frame.add_css_class("card")
        card_frame.add_css_class("file-card")

        if item.is_dir:
            card_frame.set_size_request(220, 180)
            card_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=8,
                margin_start=12, margin_end=12,
                margin_top=12, margin_bottom=12
            )

            icon = Gtk.Image.new_from_icon_name("folder-symbolic")
            icon.set_pixel_size(48)

            name_label = Gtk.Label(label=item.name, wrap=True, max_width_chars=20)
            name_label.add_css_class("heading")

            path_label = Gtk.Label(
                label=f"Folder: {os.path.basename(item.path)}",
                wrap=True, max_width_chars=25
            )
            path_label.add_css_class("caption")
            path_label.add_css_class("dim-label")

            card_box.append(icon)
            card_box.append(name_label)
            card_box.append(path_label)

        else:
            card_frame.set_size_request(220, 250)
            card_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=8,
                margin_start=12, margin_end=12,
                margin_top=12, margin_bottom=12
            )

            icon = Gtk.Image.new_from_icon_name(item.get_icon_name())
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
        return card_frame

    def _mock_scan_folder(self, folder_path: str):
        mock_items = [
            FileItem("parent", os.path.dirname(folder_path), is_dir=True),
            FileItem("PKGBUILD", os.path.join(folder_path, "PKGBUILD"), file_type="PKGBUILD"),
            FileItem("package.pkg.tar.zst", os.path.join(folder_path, "package.pkg.tar.zst"), file_type="PACKAGE"),
            FileItem("fix.patch", os.path.join(folder_path, "fix.patch"), file_type="PATCH"),
            FileItem("config.conf", os.path.join(folder_path, "config.conf"), file_type="ADVANCED"),
        ]

        if os.path.exists(folder_path):
            try:
                real_items = []
                for entry in os.listdir(folder_path):
                    entry_path = os.path.join(folder_path, entry)
                    is_dir = os.path.isdir(entry_path)
                    file_type = "UNKNOWN"

                    if not is_dir:
                        if entry == "PKGBUILD":
                            file_type = "PKGBUILD"
                        elif entry.endswith(".pkg.tar.zst"):
                            file_type = "PACKAGE"
                        elif entry.endswith((".patch", ".diff")):
                            file_type = "PATCH"
                        else:
                            file_type = "ADVANCED"

                    real_items.append(FileItem(entry, entry_path, is_dir, file_type))

                self.scan_and_display_files(folder_path, real_items)
            except PermissionError:
                self.scan_and_display_files(folder_path, [])
        else:
            self.scan_and_display_files(folder_path, mock_items)
