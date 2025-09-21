from gi.repository import Gtk, GObject, Adw
from typing import Optional, List, Dict, Any, Callable

@Gtk.Template(resource_path="/org/gnome/paru-gui/ui/components/empty_state.ui")
class EmptyState(Gtk.Box):
    __gtype_name__ = "EmptyState"

    empty_icon = Gtk.Template.Child()
    empty_title_label = Gtk.Template.Child()
    empty_description_label = Gtk.Template.Child()
    empty_options_box = Gtk.Template.Child()
    download_pkgbuild_button = Gtk.Template.Child()
    builder_mode_button = Gtk.Template.Child()

    __gsignals__ = {
        'download-pkgbuild-requested': (GObject.SignalFlags.RUN_LAST, None, ()),
        'builder-mode-requested': (GObject.SignalFlags.RUN_LAST, None, ()),
        'action-requested': (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(24)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)

        self._current_message_type = "default"
        self._custom_actions = []

        self._connect_signals()
        self._setup_initial_state()

    def _connect_signals(self):
        self.download_pkgbuild_button.connect("clicked", self._on_download_pkgbuild_clicked)
        self.builder_mode_button.connect("clicked", self._on_builder_mode_clicked)

    def _setup_initial_state(self):
        self.set_message(
            title="No Content Selected",
            description="Select a PKGBUILD file or directory to get started with package management.",
            icon_name="folder-symbolic",
            show_options=True
        )

    def set_message(self, title: str, description: str,
                   icon_name: str = "folder-symbolic",
                   show_options: bool = True,
                   message_type: str = "default"):
        self.empty_title_label.set_label(title)
        self.empty_description_label.set_label(description)
        self.empty_icon.set_from_icon_name(icon_name)
        self.empty_options_box.set_visible(show_options)

        self._apply_message_style(message_type)
        self.set_visible(True)
        self._current_message_type = message_type

    def set_error_state(self, error_message: str, details: str = ""):
        full_description = f"{error_message}\n{details}" if details else error_message
        self.set_message(
            title="Error Occurred",
            description=full_description,
            icon_name="dialog-error-symbolic",
            show_options=False,
            message_type="error"
        )

    def set_loading_state(self, message: str = "Loading..."):
        self.set_message(
            title=message,
            description="Please wait while content is being loaded.",
            icon_name="content-loading-symbolic",
            show_options=False,
            message_type="loading"
        )

    def set_no_results_state(self, search_term: str = ""):
        if search_term:
            description = f"No results found for '{search_term}'. Try adjusting your search terms."
        else:
            description = "No compatible files found in the selected directory."

        self.set_message(
            title="No Results Found",
            description=description,
            icon_name="edit-find-symbolic",
            show_options=True,
            message_type="info"
        )

    def add_custom_action(self, label: str, action_name: str,
                         icon_name: Optional[str] = None,
                         callback: Optional[Callable] = None):
        button = Gtk.Button(label=label)
        if icon_name:
            button.set_icon_name(icon_name)

        button.add_css_class("pill")

        if callback:
            button.connect("clicked", lambda btn: callback())
        else:
            button.connect("clicked", lambda btn: self.emit("action-requested", action_name))

        self.empty_options_box.append(button)

        self._custom_actions.append({
            'button': button,
            'action_name': action_name,
            'callback': callback
        })

    def clear_custom_actions(self):
        for action in self._custom_actions:
            self.empty_options_box.remove(action['button'])
        self._custom_actions.clear()

    def set_options_visible(self, visible: bool):
        self.empty_options_box.set_visible(visible)

    def update_icon_size(self, size: int = 64):
        self.empty_icon.set_pixel_size(size)

    def _on_download_pkgbuild_clicked(self, button: Gtk.Button):
        self.emit("download-pkgbuild-requested")
        self.emit("action-requested", "download-pkgbuild")

    def _on_builder_mode_clicked(self, button: Gtk.Button):
        self.emit("builder-mode-requested")
        self.emit("action-requested", "builder-mode")

    def _apply_message_style(self, message_type: str):
        style_classes = ["error-state", "warning-state", "info-state", "loading-state"]
        for css_class in style_classes:
            self.remove_css_class(css_class)

        if message_type == "error":
            self.add_css_class("error-state")
            self.empty_title_label.add_css_class("error")
        elif message_type == "warning":
            self.add_css_class("warning-state")
            self.empty_title_label.add_css_class("warning")
        elif message_type == "info":
            self.add_css_class("info-state")
            self.empty_title_label.add_css_class("accent")
        elif message_type == "loading":
            self.add_css_class("loading-state")

    def get_current_state(self) -> Dict[str, Any]:
        return {
            'title': self.empty_title_label.get_label(),
            'description': self.empty_description_label.get_label(),
            'message_type': self._current_message_type,
            'options_visible': self.empty_options_box.get_visible(),
            'custom_actions_count': len(self._custom_actions)
        }

    @staticmethod
    def create_welcome_state() -> 'EmptyState':
        empty_state = EmptyState()
        empty_state.set_message(
            title="Welcome to Paru GUI",
            description="A modern interface for managing AUR packages safely and efficiently.",
            icon_name="system-software-install-symbolic",
            show_options=True
        )
        return empty_state

    @staticmethod
    def create_folder_selection_state() -> 'EmptyState':
        empty_state = EmptyState()
        empty_state.set_message(
            title="Select a Directory",
            description="Choose a folder containing PKGBUILD files or related package sources.",
            icon_name="folder-open-symbolic",
            show_options=True
        )
        return empty_state
