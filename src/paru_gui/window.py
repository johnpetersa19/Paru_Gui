import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

import os
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

from gi.repository import Gtk, Gio, Adw, GLib, GObject, Pango, Gdk


@Gtk.Template(resource_path='/org/gnome/paru-gui/ui/window.ui')
class ParuGUIWindow(Gtk.ApplicationWindow):
    __gtype_name__ = 'ParuGUIWindow'

    main_stack: Gtk.Stack = Gtk.Template.Child()
    header_bar: Gtk.HeaderBar = Gtk.Template.Child()
    search_entry: Gtk.SearchEntry = Gtk.Template.Child()
    app_menu_button: Gtk.MenuButton = Gtk.Template.Child()
    help_button: Gtk.Button = Gtk.Template.Child()

    welcome_screen: Gtk.Box = Gtk.Template.Child()
    select_file_button: Gtk.Button = Gtk.Template.Child()
    select_folder_button: Gtk.Button = Gtk.Template.Child()
    recent_dirs_flowbox: Gtk.FlowBox = Gtk.Template.Child()
    recent_dirs_label: Gtk.Label = Gtk.Template.Child()

    content_view: Gtk.Box = Gtk.Template.Child()
    content_cards: Gtk.FlowBox = Gtk.Template.Child()
    action_bar: Gtk.Box = Gtk.Template.Child()
    back_button: Gtk.Button = Gtk.Template.Child()
    status_label: Gtk.Label = Gtk.Template.Child()
    action_button: Gtk.Button = Gtk.Template.Child()

    processing_screen: Gtk.Box = Gtk.Template.Child()
    processing_spinner: Gtk.Spinner = Gtk.Template.Child()
    processing_label: Gtk.Label = Gtk.Template.Child()
    processing_progress: Gtk.ProgressBar = Gtk.Template.Child()
    log_textview: Gtk.TextView = Gtk.Template.Child()
    cancel_button: Gtk.Button = Gtk.Template.Child()
    details_button: Gtk.Button = Gtk.Template.Child()

    upstream_updates_view: Gtk.Box = Gtk.Template.Child()
    upstream_update_cards: Gtk.FlowBox = Gtk.Template.Child()
    refresh_updates_button: Gtk.Button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        managers = kwargs.pop('managers', {})
        super().__init__(**kwargs)

        self.logger = logging.getLogger("ParuGUI.Window")

        self.error_handler = managers.get('error_handler')
        self.preferences_manager = managers.get('preferences')
        self.history_manager = managers.get('history')
        self.cache_manager = managers.get('cache')
        self.sandbox_manager = managers.get('sandbox')
        self.security_analyzer = managers.get('security')
        self.terminal_manager = managers.get('terminal')
        self.tour_guide = managers.get('tour_guide')
        self.file_utils = managers.get('file_utils')
        self.pkgbuild_analyzer = managers.get('pkgbuild_analyzer')
        self.thread_pool_executor = managers.get('thread_pool_executor')

        self.ui_manager = None
        self.content_view_manager = None
        self.search_manager = None
        self.file_operations = None
        self.preferences_dialog_manager = None
        self.help_overlay = None
        self.file_chooser = None

        self.current_directory = None
        self.selected_files = []
        self.search_active = False
        self.sidebar_visible = True

        self._init_managers()
        self._setup_window_properties()
        self._connect_signals()
        self._load_recent_directories()
        self._setup_drag_drop()

        self.logger.info("ParuGUIWindow initialized successfully")

    def _init_managers(self):
        try:
            from ui.managers.ui_manager import UIManager
            from ui.managers.content_view_manager import ContentViewManager
            from ui.managers.search_manager import SearchManager
            from ui.managers.file_operations import FileOperationsManager
            from ui.managers.preferences_dialog_manager import PreferencesDialogManager
            from ui.components.help_overlay import HelpOverlay
            from ui.components.file_chooser_dialog import FileChooserDialog

            builder = Gtk.Builder.new_from_resource('/org/gnome/paru-gui/ui/window.ui')

            self.ui_manager = UIManager(
                window=self,
                builder=builder,
                preferences_manager=self.preferences_manager,
                history_manager=self.history_manager
            )

            self.content_view_manager = ContentViewManager(
                window=self,
                content_cards=self.content_cards,
                preferences_manager=self.preferences_manager,
                security_analyzer=self.security_analyzer
            )

            self.search_manager = SearchManager(
                window=self,
                search_entry=self.search_entry,
                content_view_manager=self.content_view_manager
            )

            self.file_operations = FileOperationsManager(
                window=self,
                builder=builder,
                preferences_manager=self.preferences_manager,
                history_manager=self.history_manager,
                file_utils=self.file_utils,
                error_handler=self.error_handler,
                thread_pool_executor=self.thread_pool_executor
            )

            self.preferences_dialog_manager = PreferencesDialogManager(
                window=self,
                builder=builder,
                preferences_manager=self.preferences_manager
            )

            self.help_overlay = HelpOverlay()
            self.file_chooser = FileChooserDialog(parent=self)

        except Exception as e:
            self.logger.error(f"Failed to initialize managers: {e}")
            if self.error_handler:
                self.error_handler.handle_error(e, "Manager Initialization")

    def _setup_window_properties(self):
        if self.preferences_manager:
            width = self.preferences_manager.get_preference('window-width', 1200)
            height = self.preferences_manager.get_preference('window-height', 800)
            self.set_default_size(width, height)

        self.set_title("Paru GUI")
        self.set_icon_name("org.gnome.paru-gui")

        if self.ui_manager:
            self.ui_manager.show_welcome_screen()

    def _connect_signals(self):
        self.select_file_button.connect('clicked', self._on_select_file_clicked)
        self.select_folder_button.connect('clicked', self._on_select_folder_clicked)
        self.back_button.connect('clicked', self._on_back_button_clicked)
        self.action_button.connect('clicked', self._on_action_button_clicked)
        self.cancel_button.connect('clicked', self._on_cancel_button_clicked)
        self.details_button.connect('clicked', self._on_details_button_clicked)
        self.refresh_updates_button.connect('clicked', self._on_refresh_updates_clicked)
        self.help_button.connect('clicked', self._on_help_button_clicked)

        self.search_entry.connect('search-changed', self._on_search_changed)
        self.search_entry.connect('activate', self._on_search_activated)

        self.recent_dirs_flowbox.connect('child-activated', self._on_recent_dir_activated)

        self.connect('close-request', self._on_close_request)

    def _load_recent_directories(self):
        if not self.preferences_manager:
            return

        recent_dirs = self.preferences_manager.get_preference('recent-directories', [])

        if not recent_dirs:
            self.recent_dirs_label.set_visible(False)
            self.recent_dirs_flowbox.set_visible(False)
            return

        for child in self.recent_dirs_flowbox.get_children():
            self.recent_dirs_flowbox.remove(child)

        for dir_path in recent_dirs[:10]:
            if os.path.exists(dir_path):
                self._create_recent_dir_card(dir_path)

    def _create_recent_dir_card(self, dir_path):
        card = Gtk.Button()
        card.set_size_request(200, 80)
        card.add_css_class("card")
        card.add_css_class("flat")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)

        icon = Gtk.Image.new_from_icon_name("folder-symbolic")
        icon.set_icon_size(Gtk.IconSize.LARGE)

        name_label = Gtk.Label()
        name_label.set_text(os.path.basename(dir_path))
        name_label.add_css_class("heading")
        name_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)

        path_label = Gtk.Label()
        path_label.set_text(dir_path)
        path_label.add_css_class("caption")
        path_label.add_css_class("dim-label")
        path_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)

        box.append(icon)
        box.append(name_label)
        box.append(path_label)
        card.set_child(box)

        card.connect('clicked', lambda btn: self._load_directory(dir_path))

        self.recent_dirs_flowbox.append(card)

    def _setup_drag_drop(self):
        drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop_target.connect('drop', self._on_file_dropped)
        self.add_controller(drop_target)

    def _on_select_file_clicked(self, button):
        if self.file_chooser:
            self.file_chooser.show_file_chooser(self._on_file_selected)

    def _on_select_folder_clicked(self, button):
        if self.file_chooser:
            self.file_chooser.show_folder_chooser(self._on_folder_selected)

    def _on_file_selected(self, file_path):
        if file_path and os.path.isfile(file_path):
            self._load_single_file(file_path)

    def _on_folder_selected(self, folder_path):
        if folder_path and os.path.isdir(folder_path):
            self._load_directory(folder_path)

    def _on_file_dropped(self, drop_target, value, x, y):
        if isinstance(value, Gio.File):
            path = value.get_path()
            if path:
                if os.path.isdir(path):
                    self._load_directory(path)
                else:
                    self._load_single_file(path)
                return True
        return False

    def _load_directory(self, directory_path):
        if not os.path.exists(directory_path):
            if self.ui_manager:
                self.ui_manager.show_error_dialog(
                    "Directory Not Found",
                    f"The directory '{directory_path}' no longer exists."
                )
            return

        self.current_directory = directory_path
        self._add_to_recent_directories(directory_path)

        if self.ui_manager:
            self.ui_manager.show_processing_screen(f"Scanning '{os.path.basename(directory_path)}'...")

        if self.content_view_manager:
            self.content_view_manager.load_directory_content(directory_path, self._on_directory_loaded)

    def _load_single_file(self, file_path):
        if not os.path.exists(file_path):
            if self.ui_manager:
                self.ui_manager.show_error_dialog(
                    "File Not Found",
                    f"The file '{file_path}' no longer exists."
                )
            return

        directory_path = os.path.dirname(file_path)
        self._load_directory(directory_path)

    def _on_directory_loaded(self, success, files_data):
        if self.ui_manager:
            self.ui_manager.hide_processing_screen()

        if success and files_data:
            if self.ui_manager:
                self.ui_manager.show_content_view()

            if self.content_view_manager:
                self.content_view_manager.populate_content_cards(files_data)

            self._update_action_bar()
        else:
            if self.ui_manager:
                self.ui_manager.show_welcome_screen()
                self.ui_manager.show_toast("No compatible files found in the selected directory.", 5)

    def _add_to_recent_directories(self, directory_path):
        if not self.preferences_manager:
            return

        recent_dirs = self.preferences_manager.get_preference('recent-directories', [])

        if directory_path in recent_dirs:
            recent_dirs.remove(directory_path)

        recent_dirs.insert(0, directory_path)

        max_recent = self.preferences_manager.get_preference('max-recent-directories', 10)
        recent_dirs = recent_dirs[:max_recent]

        self.preferences_manager.set_preference('recent-directories', recent_dirs)

        self._load_recent_directories()

    def _update_action_bar(self):
        if self.current_directory:
            self.status_label.set_text(f"Loaded: {os.path.basename(self.current_directory)}")
            self.action_button.set_visible(True)
            self.action_button.set_label("Process Selected")
        else:
            self.status_label.set_text("Ready")
            self.action_button.set_visible(False)

    def _on_back_button_clicked(self, button):
        if self.ui_manager:
            if not self.ui_manager.navigate_back():
                self.ui_manager.show_welcome_screen()

        self.current_directory = None
        self.selected_files = []
        self._update_action_bar()

    def _on_action_button_clicked(self, button):
        if self.selected_files:
            self._process_selected_files()
        elif self.current_directory:
            self._process_all_files()

    def _process_selected_files(self):
        if self.file_operations:
            self.file_operations.process_files(self.selected_files, self._on_processing_complete)

    def _process_all_files(self):
        if self.current_directory and self.content_view_manager:
            all_files = self.content_view_manager.get_all_compatible_files()
            if all_files and self.file_operations:
                self.file_operations.process_files(all_files, self._on_processing_complete)

    def _on_processing_complete(self, success, results):
        if self.ui_manager:
            if success:
                self.ui_manager.show_toast("Processing completed successfully.", 3)
            else:
                self.ui_manager.show_toast("Processing completed with errors.", 5)

    def _on_cancel_button_clicked(self, button):
        if self.file_operations:
            self.file_operations.cancel_current_operation()

    def _on_details_button_clicked(self, button):
        pass

    def _on_refresh_updates_clicked(self, button):
        if self.ui_manager:
            self.ui_manager.show_processing_screen("Checking for upstream updates...")

        GLib.timeout_add_seconds(2, lambda: self.ui_manager.hide_processing_screen())

    def _on_help_button_clicked(self, button):
        self.show_help_overlay()

    def _on_search_changed(self, search_entry):
        search_text = search_entry.get_text()
        if self.search_manager:
            self.search_manager.perform_search(search_text)

    def _on_search_activated(self, search_entry):
        search_text = search_entry.get_text()
        if search_text and self.search_manager:
            self.search_manager.execute_search(search_text)

    def _on_recent_dir_activated(self, flowbox, child):
        pass

    def _on_close_request(self, window):
        self._save_window_state()
        return False

    def _save_window_state(self):
        if self.preferences_manager:
            width, height = self.get_default_size()
            self.preferences_manager.set_preference('window-width', width)
            self.preferences_manager.set_preference('window-height', height)

    def show_preferences(self):
        if self.preferences_dialog_manager:
            self.preferences_dialog_manager.show_preferences_dialog()

    def show_help_overlay(self):
        if self.help_overlay:
            self.help_overlay.show_help_overlay(self)

    def show_pkgbuild_review(self, pkgbuild_path):
        from ui.screens.pkgbuild_review_dialog import PKGBUILDReviewDialog

        dialog = PKGBUILDReviewDialog(
            parent=self,
            pkgbuild_path=pkgbuild_path,
            security_analyzer=self.security_analyzer
        )
        dialog.present()

    def show_welcome_screen(self):
        from ui.screens.welcome_screen import WelcomeScreen

        if self.ui_manager:
            self.ui_manager.show_welcome_screen()

    def show_content_view(self, directory_path=None):
        from ui.screens.content_view import ContentView

        if directory_path:
            self._load_directory(directory_path)
        elif self.ui_manager:
            self.ui_manager.show_content_view()

    def refresh_content(self):
        if self.current_directory:
            self._load_directory(self.current_directory)
        elif self.ui_manager:
            self.ui_manager.show_toast("Nothing to refresh", 2)

    def toggle_sidebar(self):
        self.sidebar_visible = not self.sidebar_visible
        if self.ui_manager:
            self.ui_manager.show_toast(
                f"Sidebar {'shown' if self.sidebar_visible else 'hidden'}", 2
            )

    def toggle_search(self):
        self.search_active = not self.search_active
        if self.search_active:
            self.search_entry.grab_focus()
        else:
            self.search_entry.set_text("")
            if self.search_manager:
                self.search_manager.clear_search()

    def select_all(self):
        if self.content_view_manager:
            self.content_view_manager.select_all_items()

    def copy_selection(self):
        if self.selected_files:
            clipboard = Gdk.Display.get_default().get_clipboard()
            file_list = '\n'.join(self.selected_files)
            clipboard.set(file_list)
            if self.ui_manager:
                self.ui_manager.show_toast(f"Copied {len(self.selected_files)} file(s)", 2)

    def paste_content(self):
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.read_text_async(None, self._on_paste_complete)

    def _on_paste_complete(self, clipboard, result):
        try:
            text = clipboard.read_text_finish(result)
            if text and self.ui_manager:
                self.ui_manager.show_toast("Paste operation not implemented", 2)
        except Exception as e:
            self.logger.warning(f"Paste operation failed: {e}")

    def show_upstream_updates(self):
        from ui.screens.upstream_update import UpstreamUpdate
        from ui.managers.ui_manager import ViewType

        if self.ui_manager:
            self.ui_manager.show_view(ViewType.PROCESSING)
            GLib.timeout_add_seconds(1, lambda: self._show_upstream_updates_view())

    def _show_upstream_updates_view(self):
        if self.ui_manager:
            self.ui_manager.main_stack.set_visible_child_name("upstream_updates")
        return False
