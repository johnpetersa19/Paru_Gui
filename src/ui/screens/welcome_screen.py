from gi.repository import Gtk, GObject, Adw, Gio, Pango
from typing import Optional, List, Dict, Any, Callable
import os
import json

@Gtk.Template(resource_path="/org/gnome/paru-gui/ui/screens/welcome_screen.ui")
class WelcomeScreen(Gtk.Box):
    __gtype_name__ = "WelcomeScreen"

    welcome_icon = Gtk.Template.Child()
    welcome_title = Gtk.Template.Child()
    welcome_subtitle = Gtk.Template.Child()
    select_file_button = Gtk.Template.Child()
    select_folder_button = Gtk.Template.Child()
    recent_dirs_label = Gtk.Template.Child()
    recent_dirs_flowbox = Gtk.Template.Child()
    tour_button = Gtk.Template.Child()
    docs_button = Gtk.Template.Child()

    __gsignals__ = {
        'file-selection-requested': (GObject.SignalFlags.RUN_LAST, None, ()),
        'folder-selection-requested': (GObject.SignalFlags.RUN_LAST, None, ()),
        'recent-directory-selected': (GObject.SignalFlags.RUN_LAST, None, (str,)),
        'tour-requested': (GObject.SignalFlags.RUN_LAST, None, ()),
        'documentation-requested': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._recent_directories = []
        self._max_recent_dirs = 6
        self._recent_dirs_file = os.path.expanduser("~/.config/paru-gui/recent_dirs.json")

        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(24)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)

        self._connect_signals()
        self._load_recent_directories()
        self._setup_initial_content()

    def _connect_signals(self):
        self.select_file_button.connect("clicked", self._on_select_file_clicked)
        self.select_folder_button.connect("clicked", self._on_select_folder_clicked)
        self.tour_button.connect("clicked", self._on_tour_clicked)
        self.docs_button.connect("clicked", self._on_docs_clicked)
        self.recent_dirs_flowbox.connect("child-activated", self._on_recent_dir_activated)

    def _setup_initial_content(self):
        self.welcome_title.set_label("Welcome to Paru GUI")
        self.welcome_subtitle.set_label(
            "A modern and secure interface for managing AUR packages on Arch Linux"
        )

        self.welcome_icon.set_from_icon_name("system-software-install-symbolic")
        self.welcome_icon.set_pixel_size(128)

        self.recent_dirs_flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.recent_dirs_flowbox.set_activate_on_single_click(True)
        self.recent_dirs_flowbox.set_max_children_per_line(3)
        self.recent_dirs_flowbox.set_min_children_per_line(1)

        self._update_recent_dirs_display()

    def _load_recent_directories(self):
        try:
            if os.path.exists(self._recent_dirs_file):
                with open(self._recent_dirs_file, 'r') as f:
                    data = json.load(f)
                    self._recent_directories = data.get('recent_dirs', [])
                    self._recent_directories = [
                        path for path in self._recent_directories
                        if os.path.exists(path) and os.path.isdir(path)
                    ]
        except (json.JSONDecodeError, IOError):
            self._recent_directories = []

    def _save_recent_directories(self):
        try:
            os.makedirs(os.path.dirname(self._recent_dirs_file), exist_ok=True)
            with open(self._recent_dirs_file, 'w') as f:
                json.dump({'recent_dirs': self._recent_directories}, f, indent=2)
        except IOError:
            pass

    def add_recent_directory(self, path: str):
        if not os.path.exists(path) or not os.path.isdir(path):
            return

        if path in self._recent_directories:
            self._recent_directories.remove(path)

        self._recent_directories.insert(0, path)
        self._recent_directories = self._recent_directories[:self._max_recent_dirs]

        self._save_recent_directories()
        self._update_recent_dirs_display()

    def remove_recent_directory(self, path: str):
        if path in self._recent_directories:
            self._recent_directories.remove(path)
            self._save_recent_directories()
            self._update_recent_dirs_display()

    def clear_recent_directories(self):
        self._recent_directories.clear()
        self._save_recent_directories()
        self._update_recent_dirs_display()

    def _update_recent_dirs_display(self):
        while self.recent_dirs_flowbox.get_first_child() is not None:
            self.recent_dirs_flowbox.remove(self.recent_dirs_flowbox.get_first_child())

        has_recent = len(self._recent_directories) > 0
        self.recent_dirs_label.set_visible(has_recent)
        self.recent_dirs_flowbox.set_visible(has_recent)

        if has_recent:
            self.recent_dirs_label.set_label(f"Recent Directories ({len(self._recent_directories)})")

            for directory in self._recent_directories:
                card = self._create_recent_dir_card(directory)
                if card:
                    self.recent_dirs_flowbox.append(card)

    def _create_recent_dir_card(self, directory: str) -> Optional[Gtk.FlowBoxChild]:
        if not os.path.exists(directory):
            return None

        child = Gtk.FlowBoxChild()

        frame = Gtk.Frame()
        frame.add_css_class("card")
        frame.add_css_class("recent-dir-card")
        frame.set_size_request(200, 120)

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_start=12, margin_end=12,
            margin_top=12, margin_bottom=12
        )

        icon = Gtk.Image.new_from_icon_name("folder-symbolic")
        icon.set_pixel_size(32)

        name_label = Gtk.Label(
            label=os.path.basename(directory),
            wrap=True,
            max_width_chars=20,
            ellipsize=Pango.EllipsizeMode.MIDDLE
        )
        name_label.add_css_class("heading")

        path_label = Gtk.Label(
            label=directory,
            wrap=True,
            max_width_chars=25,
            ellipsize=Pango.EllipsizeMode.MIDDLE
        )
        path_label.add_css_class("caption")
        path_label.add_css_class("dim-label")

        remove_button = Gtk.Button()
        remove_button.set_icon_name("edit-delete-symbolic")
        remove_button.add_css_class("flat")
        remove_button.add_css_class("circular")
        remove_button.set_size_request(24, 24)
        remove_button.set_halign(Gtk.Align.END)
        remove_button.set_valign(Gtk.Align.START)
        remove_button.connect("clicked", lambda btn: self.remove_recent_directory(directory))

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header_box.append(icon)
        header_box.append(Gtk.Box())
        header_box.append(remove_button)

        box.append(header_box)
        box.append(name_label)
        box.append(path_label)

        frame.set_child(box)
        frame.set_tooltip_text(directory)

        child.set_child(frame)
        return child

    def _on_select_file_clicked(self, button: Gtk.Button):
        self.emit("file-selection-requested")

    def _on_select_folder_clicked(self, button: Gtk.Button):
        self.emit("folder-selection-requested")

    def _on_recent_dir_activated(self, flowbox: Gtk.FlowBox, child: Gtk.FlowBoxChild):
        directory = child.get_child().get_tooltip_text()
        if directory and os.path.exists(directory):
            self.emit("recent-directory-selected", directory)
        else:
            if directory:
                self.remove_recent_directory(directory)

    def _on_tour_clicked(self, button: Gtk.Button):
        self.emit("tour-requested")

    def _on_docs_clicked(self, button: Gtk.Button):
        self.emit("documentation-requested")

    def refresh_recent_directories(self):
        self._load_recent_directories()
        self._update_recent_dirs_display()

    def set_welcome_message(self, title: str, subtitle: str):
        self.welcome_title.set_label(title)
        self.welcome_subtitle.set_label(subtitle)

    def set_action_buttons_visible(self, visible: bool):
        self.select_file_button.set_visible(visible)
        self.select_folder_button.set_visible(visible)

    def set_secondary_buttons_visible(self, visible: bool):
        self.tour_button.set_visible(visible)
        self.docs_button.set_visible(visible)

    def get_recent_directories(self) -> List[str]:
        return self._recent_directories.copy()

    def set_max_recent_directories(self, max_dirs: int):
        self._max_recent_dirs = max(1, max_dirs)
        if len(self._recent_directories) > self._max_recent_dirs:
            self._recent_directories = self._recent_directories[:self._max_recent_dirs]
            self._save_recent_directories()
            self._update_recent_dirs_display()

    def connect_to_window(self, window):
        self.connect("file-selection-requested", lambda w: window._on_select_file_clicked(None))
        self.connect("folder-selection-requested", lambda w: window._on_select_folder_clicked(None))
        self.connect("recent-directory-selected", lambda w, path: window.show_content_view(path))
        self.connect("tour-requested", lambda w: window._on_initial_tour_action(None, None))
        self.connect("documentation-requested", lambda w: window._on_consult_docs_action(None, None))
