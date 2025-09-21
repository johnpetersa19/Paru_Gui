from gi.repository import Gtk, GObject, Adw, Gio
from typing import Optional, List, Dict, Any

@Gtk.Template(resource_path="/org/gnome/paru-gui/ui/components/help-overlay.ui")
class HelpOverlay(Gtk.ShortcutsWindow):
    __gtype_name__ = "HelpOverlay"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_modal(True)
        self.set_resizable(True)
        self.set_default_size(800, 600)
        self._connect_signals()

    def _connect_signals(self):
        self.connect("close-request", self._on_close_request)

    def _on_close_request(self, window):
        return False

    def show_overlay(self, parent_window: Optional[Gtk.Window] = None):
        if parent_window:
            self.set_transient_for(parent_window)
        self.present()

    def add_custom_shortcut(self, section_name: str, group_title: str,
                           shortcut_title: str, accelerator: str, action_name: str):
        pass

    def update_shortcuts_from_actions(self, action_map: Dict[str, str]):
        pass

    def get_shortcut_sections(self) -> List[str]:
        return ["general", "navigation", "file-management", "actions"]

    def get_action_shortcuts(self) -> Dict[str, str]:
        return {
            "win.show-help-overlay": "<Primary>question|F1",
            "app.quit": "<Primary>q",
            "app.preferences": "<Primary>comma",
            "app.about": "",
            "app.system": "<Primary>s",
            "app.statistics": "<Primary>t",
            "app.arch-news": "<Primary>n",
            "app.show-upstream-updates": "<Primary>u",
            "app.refresh-upstream-updates": "F6",
            "app.go-home": "Escape",
            "app.action-history": "<Primary>h",
            "app.go-back": "<Alt>Left",
            "app.go-forward": "<Alt>Right",
            "app.search-packages": "<Primary>f",
            "app.select-file": "<Primary>o",
            "app.select-folder": "<Primary><Shift>o",
            "app.refresh-view": "F5",
            "app.download-sources": "<Primary>l",
            "app.build-package": "<Primary>b",
            "app.edit-pkgbuild": "<Primary>e",
            "app.view-analysis": "<Primary>r",
            "app.install-package": "<Primary>i",
            "app.verify-signature": "<Primary>v",
            "app.apply-patch": "<Primary>a",
            "app.view-diff": "<Primary>d",
            "app.hide-advanced": "<Primary>m",
            "app.execute-custom-command": "<Primary>x",
            "app.dry-run": "<Primary>y",
            "app.consult-docs": "<Primary>slash",
            "app.update-system": "<Primary><Shift>u",
            "app.clean-cache": "<Primary><Shift>c",
        }

    def validate_shortcuts(self) -> List[str]:
        shortcuts = self.get_action_shortcuts()
        missing_actions = []
        for action_name in shortcuts.keys():
            pass
        return missing_actions

    def show_section(self, section_name: str):
        self.present()

    @staticmethod
    def setup_help_action(window: Gtk.ApplicationWindow) -> Gio.SimpleAction:
        def show_help_overlay(action, param):
            help_overlay = HelpOverlay()
            help_overlay.show_overlay(window)

        action = Gio.SimpleAction.new("show-help-overlay", None)
        action.connect("activate", show_help_overlay)
        window.add_action(action)

        window.get_application().set_accels_for_action(
            "win.show-help-overlay",
            ["<Primary>question", "F1"]
        )

        return action
