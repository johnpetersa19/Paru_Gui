# src/window.py
#
# Copyright 2025 Unknown
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import subprocess
import re
import traceback
from enum import Enum
import concurrent.futures
import threading
from typing import Optional, List, Dict, Any, Tuple, Callable
from datetime import datetime

from gi.repository import Gtk, Gio, GLib, Gdk, GObject, Adw, Pango

# Import custom modules
from .upstream_checker import UpstreamChecker
from .security_analyzer import SecurityAnalyzer
from .sandboxing import SandboxManager, SandboxOptions, IsolationLevel
from paru_gui.error_handler import ErrorHandler, ErrorContext, ErrorCategory, ErrorDetail, SuggestedAction
from paru_gui.history_manager import HistoryManager, ActionType, ActionStatus, HistoryEntry
from .preferences_manager import PreferencesManager
from paru_gui.file_utils import FileUtils, FileItem # Import FileItem from file_utils
from .terminal_manager import TerminalManager
from .tour_guide import TourGuide # Ensure TourGuide is imported

# Import UI screen/component classes for direct instantiation
from paru_gui.ui.screens.pkgbuild_review_dialog import PkgbuildReviewDialog
from paru_gui.ui.screens.upstream_update import UpstreamUpdateCard
from paru_gui.ui.components.file_chooser_dialog import FileChooserDialog as CustomFileChooserDialog # Rename to avoid conflict
from paru_gui.ui.components.help_overlay import HelpOverlay


class ParuGuiWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("Paru GUI")
        self.set_default_size(1000, 700) # Adjusted default size

        # Thread pool for I/O-bound tasks (network, disk scanning)
        self.thread_pool_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        # Process pool for CPU-bound or security-sensitive tasks (PKGBUILD analysis, sandboxing)
        self.process_pool_executor = concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count() or 1)

        # Current directory for content view
        self.current_path = os.path.expanduser("~") # Start at home directory

        # Initialize core components
        self.preferences_manager = PreferencesManager() # Initialize PreferencesManager first
        self.file_utils = FileUtils(self.preferences_manager) # Pass PreferencesManager to FileUtils
        self.upstream_checker = UpstreamChecker()
        self.security_analyzer = SecurityAnalyzer()
        # Initialize SandboxManager, it will check for bwrap presence
        try:
            self.sandbox_manager = SandboxManager()
        except RuntimeError as e:
            # Handle bwrap not found as a critical error later if a sandboxed action is attempted.
            self.sandbox_manager = None
            print(f"Warning: SandboxManager could not be fully initialized: {e}")

        self.history_manager = HistoryManager() # Assumes default path or configured via prefs

        # UI Components (loaded from .ui files)
        self.builder = Gtk.Builder()
        # --- CORREÇÃO AQUI: Carregar todos os arquivos UI que contêm templates ou objetos top-level ---
        self.builder.add_from_resource('/org/gnome/paru-gui/window.ui')
        self.builder.add_from_resource('/org/gnome/paru-gui/ui/screens/welcome_screen.ui')
        self.builder.add_from_resource('/org/gnome/paru-gui/ui/screens/content_view.ui')
        self.builder.add_from_resource('/org/gnome/paru-gui/ui/screens/pkgbuild_review.ui')
        self.builder.add_from_resource('/org/gnome/paru-gui/ui/screens/upstream_update.ui')
        self.builder.add_from_resource('/org/gnome/paru-gui/ui/components/empty_state.ui')
        self.builder.add_from_resource('/org/gnome/paru-gui/ui/components/error_dialog.ui')
        self.builder.add_from_resource('/org/gnome/paru-gui/ui/components/file_chooser_dialog.ui')
        self.builder.add_from_resource('/org/gnome/paru-gui/ui/components/help-overlay.ui')
        self.builder.add_from_resource('/org/gnome/paru-gui/ui/components/search_bar.ui')
        # --- FIM DA CORREÇÃO ---


        # Initialize ErrorHandler after builder is ready
        self.error_handler = ErrorHandler(self.builder, self, self.get_application().get_version())

        # Link security_analyzer to upstream_checker (if needed, for shared parsing)
        self.security_analyzer.set_upstream_checker(self.upstream_checker)

        # Get main UI elements
        self.main_stack = self.builder.get_object('main_stack')
        self.header_bar = self.builder.get_object('header_bar')

        # Initialize TerminalManager (requires a Gtk.Box for its panel, which is in content_view.ui)
        # This needs to be done *after* content_view is potentially loaded.
        # We will retrieve the 'terminal_area' from the dynamically created ContentView
        # or from the content_view template itself once it is part of the main_stack.
        # For now, we will create a dummy box and update it later.
        dummy_terminal_area_box = Gtk.Box() # Placeholder
        self.terminal_manager = TerminalManager(dummy_terminal_area_box, self.preferences_manager)

        # Initialize TourGuide
        self.tour_guide = TourGuide(self, self.builder, self.preferences_manager)

        self.setup_main_interface()

        # Connect application actions (defined in main.py)
        # The help button on the header bar should trigger the help overlay.
        help_button = self.builder.get_object('help_button')
        if help_button:
            help_button.connect('clicked', lambda btn: self.tour_guide.show_contextual_help_overlay())


    def setup_main_interface(self):
        """Configures the main interface, attaching UI elements and connecting signals."""
        self.set_titlebar(self.header_bar)

        app_menu_button = self.builder.get_object('app_menu_button')
        if app_menu_button:
            # For menu-model, you get the model from the application
            app_menu_button.set_menu_model(self.get_application().get_menu_by_id('primary_menu'))

        self.search_entry = self.builder.get_object('search_entry')
        if self.search_entry:
            self.search_entry.connect('search-changed', self.on_search_changed)
            self.search_entry.connect('activate', self.on_search_activated)

        self.set_child(self.main_stack)
        self.show_welcome_screen()

        # Connect signals for Welcome Screen (buttons are defined in welcome_screen.ui, loaded by builder)
        # Assuming welcome_screen is a GtkBox within window.ui that gets replaced by the WelcomeScreen template later.
        # The welcome_screen object obtained here is from window.ui, not the @Gtk.Template class.
        # If the template replaces it, these objects might not exist or need to be gotten from the template instance.
        # However, the buttons in window.ui (which is always loaded) are likely the intended targets.
        select_file_button = self.builder.get_object('select_file_button')
        if select_file_button:
            select_file_button.connect("clicked", self.on_select_file_clicked)
        select_folder_button = self.builder.get_object('select_folder_button')
        if select_folder_button:
            select_folder_button.connect("clicked", self.on_select_folder_clicked)

        self.recent_dirs_flowbox = self.builder.get_object('recent_dirs_flowbox')
        self._load_recent_directories() # Load and display recent dirs

        # Connect Tour Guide button on welcome screen (buttons are on the template in welcome_screen.ui)
        # So we need to ensure the welcome_screen template is loaded and then get its children.
        # As the welcome_screen in window.ui acts as a container for the template, this is fine.
        # The actual buttons are found via self.builder.get_object within the scope of the main_window's welcome_screen object.
        welcome_screen_main_box = self.builder.get_object('welcome_screen') # This is the GtkBox container for the template
        if welcome_screen_main_box:
            # We need to get the actual buttons from the template *after* it's loaded/rendered.
            # For now, relying on the 'window.ui' direct buttons or connecting on template instance.
            # The current setup in window.ui has its own select_file_button, select_folder_button, etc.
            # The TourGuide and Docs buttons in welcome_screen.ui are separate from window.ui's buttons.
            # This needs to be handled by creating an instance of WelcomeScreen class and connecting its signals.
            # For simplicity, if the window.ui has its own buttons, connect them.
            # If the actual WelcomeScreen *template class* is used as the child of the stack,
            # then its buttons should connect in its __init__ (as already coded).

            # To avoid confusion, ensure the button IDs are unique or the intent is clear.
            # Since the window.ui defines its own `select_file_button` and `select_folder_button`,
            # and the welcome_screen.ui also defines them, this is a potential conflict.
            # Let's assume the window.ui's direct buttons are the primary ones for the main window.
            # The TourGuide and Documentation buttons are inside the welcome_screen.ui *template*,
            # so they should be connected after the template is fully setup/replaces the placeholder.
            pass # Already connected global select_file/folder buttons.

        # Connect Tour Guide button (from welcome_screen.ui, dynamically instantiated)
        # This part should be handled when the WelcomeScreen *class* is instantiated and set as child.
        # For now, the example in welcome_screen.py assumes self.builder.get_object('tour_guide_button')
        # is called from *within* the WelcomeScreen class, which is correct.


        # Connect main window application actions
        app = self.get_application()
        if app:
            # Actions defined in main.py, accels linked here
            app.set_accels_for_action("app.preferences", ["<primary>comma"])
            app.set_accels_for_action("app.about", []) # No default accel for About
            # app.set_accels_for_action("app.initial-tour", []) # Tour is often menu/button driven
            app.set_accels_for_action("app.action-history", ["<primary>h"])
            app.set_accels_for_action("app.go-home", ["Escape"]) # Added from help-overlay.ui
            app.set_accels_for_action("app.show-help-overlay", ["<primary>question", "F1"]) # Added from help-overlay.ui

            # Connect other menu actions (placeholders, will be linked to self methods)
            self.create_action('system', self.on_system_action)
            self.create_action('statistics', self.on_statistics_action)
            self.create_action('arch-news', self.on_arch_news_action)
            self.create_action('clean-cache', self.on_clean_cache_action)
            self.create_action('update-system', self.on_update_system_action)
            self.create_action('action-history', self.on_action_history_action, ["<primary>h"])
            self.create_action('initial-tour', lambda *args: self.tour_guide.show_initial_tour())
            self.create_action('show-upstream-updates', self.on_show_upstream_updates)
            self.create_action('refresh-upstream-updates', self.on_refresh_upstream_updates_action, ["F6"]) # New action
            self.create_action('hide-advanced', self.on_hide_advanced_action, ["<primary>m"]) # Toggle simplified mode
            self.create_action('check-devel', self.on_check_devel_action, ["<primary><shift>e"])
            self.create_action('install-debug', self.on_install_debug_action, ["<primary><shift>p"])
            self.create_action('show-warnings', self.on_show_warnings_action, ["<primary><shift>w"])
            self.create_action('show-terminal', self.on_show_terminal_panel_action, ["<primary><shift>t"])
            self.create_action('review-pkgbuild', self.on_review_pkgbuild_action) # Placeholder for direct PKGBUILD review from menu
            self.create_action('select-file', self.on_select_file_clicked, ["<primary>o"]) # New action
            self.create_action('select-folder', self.on_select_folder_clicked, ["<primary><shift>o"]) # New action
            self.create_action('refresh-view', lambda *args: self._start_scan_compatible_files_async(self.current_path), ["F5"]) # New action
            self.create_action('download-sources', self.on_download_sources) # New action
            self.create_action('build-package', self.on_build_package) # Global shortcut can be ambiguous, maybe better on card
            self.create_action('edit-pkgbuild', self.on_edit_pkgbuild) # Global shortcut can be ambiguous, maybe better on card
            self.create_action('view-analysis', self.on_review_pkgbuild_action, ["<primary>r"]) # Global shortcut
            self.create_action('install-package', self.on_install_package) # Global shortcut can be ambiguous
            self.create_action('verify-signature', self.on_verify_signature) # Global shortcut can be ambiguous
            self.create_action('apply-patch', self.on_apply_patch) # Global shortcut can be ambiguous
            self.create_action('view-diff', self.on_view_diff) # Global shortcut can be ambiguous
            self.create_action('execute-custom-command', self.on_execute_custom_command, ["<primary>x"]) # Global shortcut
            self.create_action('dry-run', self.on_dry_run_command, ["<primary>y"]) # Global shortcut
            self.create_action('consult-docs', self.on_consult_documentation, ["<primary>slash"]) # Global shortcut

        # Connect preferences switches/combos (assuming the dialog is instantiated)
        # The preferences dialog is created on-demand in on_preferences_action
        # We need to ensure preference callbacks are connected to the *dialog instance* when it's created.
        # This will be handled in on_preferences_action.

    def create_action(self, name, callback, shortcuts=None):
        """Helper to create and add application actions."""
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.get_application().add_action(action)
        if shortcuts:
            self.get_application().set_accels_for_action(f"app.{name}", shortcuts)

    def on_preferences_action(self, *args):
        """Callback for the app.preferences action."""
        print('app.preferences action activated')
        prefs_dialog = self.builder.get_object('preferences_dialog')
        if not prefs_dialog:
            prefs_dialog = Gtk.Builder.get_template(self.__class__, 'preferences_dialog').new_with_values([('transient-for', self), ('modal', True)])
            # Attach to builder to allow getting children with scope
            self.builder.expose_widget(prefs_dialog, 'preferences_dialog')
            print("Created new preferences_dialog instance.")

        prefs_dialog.set_transient_for(self)
        prefs_dialog.set_modal(True)

        # Connect controls on the *instance* of the dialog
        editor_combo = self.builder.get_object('editor_combo', prefs_dialog)
        if editor_combo and not hasattr(editor_combo, '_connected'):
            editor_combo.connect('changed', self._on_editor_combo_changed)
            editor_combo._connected = True

        simplified_mode_switch = self.builder.get_object('simplified_mode_switch', prefs_dialog)
        if simplified_mode_switch and not hasattr(simplified_mode_switch, '_connected'):
            simplified_mode_switch.connect('notify::active', self._on_simplified_mode_toggled)
            simplified_mode_switch._connected = True

        trust_icons_switch = self.builder.get_object('trust_icons_switch', prefs_dialog)
        if trust_icons_switch and not hasattr(trust_icons_switch, '_connected'):
            trust_icons_switch.connect('notify::active', self._on_trust_icons_toggled)
            trust_icons_switch._connected = True

        block_unvoted_switch = self.builder.get_object('block_unvoted_switch', prefs_dialog)
        if block_unvoted_switch and not hasattr(block_unvoted_switch, '_connected'):
            block_unvoted_switch.connect('notify::active', self._on_block_unvoted_toggled)
            block_unvoted_switch._connected = True

        clean_after_build_switch = self.builder.get_object('clean_after_build_switch', prefs_dialog)
        if clean_after_build_switch and not hasattr(clean_after_build_switch, '_connected'):
            clean_after_build_switch.connect('notify::active', self._on_clean_after_build_toggled)
            clean_after_build_switch._connected = True

        terminal_switch = self.builder.get_object('terminal_switch', prefs_dialog)
        if terminal_switch and not hasattr(terminal_switch, '_connected'):
            terminal_switch.connect('notify::active', self._on_show_realtime_terminal_toggled)
            terminal_switch._connected = True

        prefs_close_button = self.builder.get_object('prefs_close_button', prefs_dialog)
        if prefs_close_button and not hasattr(prefs_close_button, '_connected'):
            prefs_close_button.connect('clicked', lambda btn: prefs_dialog.close())
            prefs_close_button._connected = True

        self._load_preferences_to_dialog(prefs_dialog)
        prefs_dialog.present()


    def _load_preferences_to_dialog(self, dialog: Gtk.Dialog):
        """Populates the preferences dialog with current settings."""
        if not self.preferences_manager: return

        editor_combo = self.builder.get_object('editor_combo', dialog)
        if editor_combo: editor_combo.set_active_id(self.preferences_manager.get_default_editor())

        simplified_mode_switch = self.builder.get_object('simplified_mode_switch', dialog)
        if simplified_mode_switch: simplified_mode_switch.set_active(self.preferences_manager.get_simplified_mode())

        trust_icons_switch = self.builder.get_object('trust_icons_switch', dialog)
        if trust_icons_switch: trust_icons_switch.set_active(self.preferences_manager.get_show_trust_icons())

        block_unvoted_switch = self.builder.get_object('block_unvoted_switch', dialog)
        if block_unvoted_switch: block_unvoted_switch.set_active(self.preferences_manager.get_block_unvoted_packages())

        clean_after_build_switch = self.builder.get_object('clean_after_build_switch', dialog)
        if clean_after_build_switch: clean_after_build_switch.set_active(self.preferences_manager.get_clean_after_build())

        terminal_switch = self.builder.get_object('terminal_switch', dialog)
        if terminal_switch: terminal_switch.set_active(self.preferences_manager.get_show_realtime_terminal())


    # --- Preferences Callbacks ---
    def _on_editor_combo_changed(self, combo: Gtk.ComboBoxText):
        if self.preferences_manager:
            self.preferences_manager.set_default_editor(combo.get_active_id())
            logger.info(f"Default editor set to: {combo.get_active_id()}")

    def _on_simplified_mode_toggled(self, switch: Gtk.Switch, gparam):
        if self.preferences_manager:
            self.preferences_manager.set_simplified_mode(switch.get_active())
            logger.info(f"Simplified mode toggled: {switch.get_active()}")
            # Re-scan/update view to reflect changes in UI elements (e.g., hiding advanced cards)
            self._start_scan_compatible_files_async(self.current_path)

    def _on_trust_icons_toggled(self, switch: Gtk.Switch, gparam):
        if self.preferences_manager:
            self.preferences_manager.set_show_trust_icons(switch.get_active())
            logger.info(f"Show trust icons toggled: {switch.get_active()}")
            self._start_scan_compatible_files_async(self.current_path)

    def _on_block_unvoted_toggled(self, switch: Gtk.Switch, gparam):
        if self.preferences_manager:
            self.preferences_manager.set_block_unvoted_packages(switch.get_active())
            logger.info(f"Block unvoted packages toggled: {switch.get_active()}")

    def _on_clean_after_build_toggled(self, switch: Gtk.Switch, gparam):
        if self.preferences_manager:
            self.preferences_manager.set_clean_after_build(switch.get_active())
            logger.info(f"Clean after build toggled: {switch.get_active()}")

    def _on_show_realtime_terminal_toggled(self, switch: Gtk.Switch, gparam):
        if self.preferences_manager:
            active = switch.get_active()
            self.preferences_manager.set_show_realtime_terminal(active)
            logger.info(f"Show real-time terminal toggled: {active}")
            # TerminalManager manages its own visibility based on this preference
            if active:
                self.terminal_manager.show_terminal_panel()
            else:
                self.terminal_manager.hide_terminal_panel()


    def _load_recent_directories(self):
        """Loads recent directories from preferences and displays them."""
        self.recent_dirs_flowbox = self.builder.get_object('recent_dirs_flowbox')
        if not self.recent_dirs_flowbox:
            logger.warning("Recent directories flowbox not found in UI, skipping loading.")
            return

        recent_dirs = self.preferences_manager.get_recent_directories()

        while self.recent_dirs_flowbox.get_first_child() is not None:
            self.recent_dirs_flowbox.remove(self.recent_dirs_flowbox.get_first_child())

        for path in recent_dirs:
            button = Gtk.Button(label=os.path.basename(path))
            button.set_tooltip_text(path)
            button.add_css_class('pill')
            # Connect using lambda to pass path correctly
            button.connect('clicked', self._on_recent_dir_clicked, path)
            self.recent_dirs_flowbox.append(button)
        self.recent_dirs_flowbox.show_all() # Ensure new children are shown

    def _on_recent_dir_clicked(self, button: Gtk.Button, path: str):
        """Callback for clicking a recent directory button."""
        self.current_path = path
        self.main_stack.set_visible_child_name("content")
        self._start_scan_compatible_files_async(path)
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.UI_INTERACTION,
            summary=f"Opened recent directory: {os.path.basename(path)}",
            status=ActionStatus.INFO,
            details={"path": path}
        ))
        self.preferences_manager.add_recent_directory(path)


    def show_welcome_screen(self):
        """Displays the welcome screen."""
        self.main_stack.set_visible_child_name("welcome")
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.UI_INTERACTION,
            summary="Displayed welcome screen",
            status=ActionStatus.INFO
        ))


    def on_select_file_clicked(self, *args):
        """Opens dialog to select a specific file."""
        dialog = Gtk.FileChooserNative(
            title="Select PKGBUILD File",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )

        filter_pkgbuild = Gtk.FileFilter()
        filter_pkgbuild.set_name("PKGBUILD Files")
        filter_pkgbuild.add_pattern("PKGBUILD")
        filter_pkgbuild.add_mime_type("text/x-pkgbuild")
        dialog.add_filter(filter_pkgbuild)

        filter_package = Gtk.FileFilter()
        filter_package.set_name("Arch Packages (.pkg.tar.zst)")
        filter_package.add_pattern("*.pkg.tar.zst")
        filter_package.add_mime_type("application/x-arch-package")
        dialog.add_filter(filter_package)

        filter_patch = Gtk.FileFilter()
        filter_patch.set_name("Patch Files (.patch, .diff)")
        filter_patch.add_pattern("*.patch")
        filter_patch.add_pattern("*.diff")
        filter_patch.add_mime_type("text/x-diff")
        dialog.add_filter(filter_patch)

        filter_all = Gtk.FileFilter()
        filter_all.set_name("All Files")
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)

        dialog.connect("response", self._on_single_file_response)
        dialog.show()
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.UI_INTERACTION,
            summary="Opened file selection dialog",
            status=ActionStatus.INFO
        ))

    def _on_single_file_response(self, dialog: Gtk.FileChooserNative, response: Gtk.ResponseType):
        """Processes selection of a single file."""
        if response == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_file().get_path()
            if file_path:
                self.current_path = os.path.dirname(file_path)
                self.main_stack.set_visible_child_name("content")
                self._start_scan_compatible_files_async(self.current_path, initial_selection_path=file_path)
                self.preferences_manager.add_recent_directory(self.current_path)
        dialog.destroy()


    def on_select_folder_clicked(self, *args):
        """Opens dialog to select folder with smart file visualization."""
        dialog = Gtk.FileChooserNative(
            title="Select Folder",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        dialog.connect("response", self._on_folder_selection_response)
        dialog.show()
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.UI_INTERACTION,
            summary="Opened folder selection dialog",
            status=ActionStatus.INFO
        ))

    def _on_folder_selection_response(self, dialog: Gtk.FileChooserNative, response: Gtk.ResponseType):
        """Processes folder selection from the native dialog."""
        if response == Gtk.ResponseType.ACCEPT:
            folder_path = dialog.get_file().get_path()
            if folder_path:
                self.current_path = folder_path
                self.main_stack.set_visible_child_name("content")
                self._start_scan_compatible_files_async(self.current_path)
                self.preferences_manager.add_recent_directory(self.current_path)
        dialog.destroy()


    def _start_scan_compatible_files_async(self, folder_path: str, initial_selection_path: Optional[str] = None):
        """Starts scanning compatible files in a separate thread."""
        self._show_processing_screen(f"Scanning '{os.path.basename(folder_path)}'...")
        future = self.thread_pool_executor.submit(self.file_utils.scan_compatible_files_worker, folder_path)
        future.add_done_callback(
            lambda f: GLib.idle_add(
                self._on_scan_completed, f, folder_path, initial_selection_path
            )
        )
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.UI_INTERACTION,
            summary=f"Initiated file scan for: {os.path.basename(folder_path)}",
            status=ActionStatus.INFO,
            details={"path": folder_path}
        ))


    def _on_scan_completed(self, future: concurrent.futures.Future, folder_path: str, initial_selection_path: Optional[str] = None):
        """Callback executed on the UI thread when file scan is complete."""
        try:
            file_items = future.result()
            self._update_content_view(file_items, folder_path)

            if initial_selection_path:
                content_cards = self.builder.get_object('content_cards')
                if content_cards: # Ensure content_cards exists
                    for child in content_cards:
                        # Access the GtkFrame directly from the FlowBoxChild, then its tooltip
                        child_frame = child.get_child()
                        if isinstance(child_frame, Gtk.Frame) and child_frame.get_tooltip_text() == initial_selection_path:
                            # Select and scroll to the selected child
                            content_cards.select_child(child)
                            # The scroll_to_child needs an iter or mark if it's a TextView.
                            # For FlowBox, `scroll_to_child` might be a conceptual operation or need custom implementation.
                            # For now, simply selecting.
                            break
            self._hide_processing_screen()
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Completed file scan for: {os.path.basename(folder_path)}",
                status=ActionStatus.SUCCESS,
                details={"path": folder_path, "files_found": len(file_items)}
            ))
        except Exception as e:
            error_ctx = ErrorContext(
                category=ErrorCategory.INTERNAL,
                summary="File scan callback failed",
                details=f"An unexpected error occurred after scanning: {e}",
                file_path=folder_path,
                traceback=traceback.format_exc(),
                original_exception=e
            )
            self.error_handler.show_error_dialog(error_ctx)
            self._hide_processing_screen()
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Failed file scan for: {os.path.basename(folder_path)}",
                status=ActionStatus.FAILED,
                details={"path": folder_path, "error": str(e)}
            ))


    def _update_content_view(self, file_items: List[FileItem], folder_path: str):
        """Populates the content view with scanned file items."""
        # Ensure content_view is the visible child or get it from the builder
        content_view_widget = self.builder.get_object('content_view') # This is the GtkBox in window.ui

        # Update TerminalManager's actual terminal_area_box
        terminal_area_box = self.builder.get_object('terminal_area', content_view_widget)
        if terminal_area_box:
            self.terminal_manager.terminal_area_box = terminal_area_box
            self.terminal_manager._load_preferences() # Re-apply visibility based on preferences

        content_cards = self.builder.get_object('content_cards', content_view_widget) # Get from content_view scope
        current_path_label = self.builder.get_object('current_path_label', content_view_widget)
        file_count_label = self.builder.get_object('file_count_label', content_view_widget)
        up_button = self.builder.get_object('up_button', content_view_widget)

        if current_path_label:
            current_path_label.set_label(folder_path)
            current_path_label.set_tooltip_text(folder_path)
        if file_count_label:
            file_count_label.set_label(f"{len(file_items)} files found")

        if up_button and not hasattr(up_button, '_connected_up_button'):
            up_button.connect('clicked', self._on_up_button_clicked)
            up_button._connected_up_button = True

        if not content_cards:
            logger.error("Content cards FlowBox not found in UI.")
            return

        while content_cards.get_first_child() is not None:
            content_cards.remove(content_cards.get_first_child())

        # Filter out directories for displaying the empty state condition
        displayable_file_items = [item for item in file_items if not item.is_dir]

        # If no files found, display empty state
        if not displayable_file_items:
            empty_state_instance = Gtk.Builder.get_template(self.__class__, 'empty_card_template').new_with_values([]) # Instantiate template
            if not empty_state_instance:
                logger.error("Empty state box template not found in UI. Cannot display empty state.")
                return

            # Note: The empty_card_template is defined within window.ui, not src/ui/components/empty_state.ui
            # The empty_state.py class is for the standalone component, if you were to use it.
            # Here, we're using the simple empty_card_template from window.ui.
            empty_state_box = empty_state_instance # Already an instance
            empty_state_box.set_visible(True)

            # Get objects within this specific empty_state_box instance
            # These IDs are from the 'empty_card_template' within window.ui, not empty_state.ui
            # Make sure these IDs match the template.
            title_label = self.builder.get_object('heading', empty_state_box)
            desc_label = self.builder.get_object('label', empty_state_box)
            download_button = self.builder.get_object('download_button', empty_state_box)

            if title_label: title_label.set_label("Empty Directory")
            if desc_label: desc_label.set_label(f"No compatible files found in '{os.path.basename(folder_path)}'.")
            if download_button: # Re-connect button if template is re-used
                if hasattr(download_button, '_connected_empty_state_download'):
                    download_button.disconnect_by_func(self._on_empty_state_download_pkgbuild_clicked)
                download_button.connect('clicked', self._on_empty_state_download_pkgbuild_clicked)
                download_button._connected_empty_state_download = True

            flowbox_child = Gtk.FlowBoxChild()
            flowbox_child.set_child(empty_state_box)
            content_cards.append(flowbox_child)
            self.main_stack.set_visible_child_name("content")
            return


        for item in file_items:
            # First add directories, then files.
            if item.is_dir:
                card_frame = Gtk.Frame()
                card_frame.add_css_class("card")
                card_frame.add_css_class("file-card")
                card_frame.set_size_request(220, 180) # Fixed size for directory card

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
                card_frame.set_tooltip_text(item.path)
                card_frame.set_cursor(Gdk.Cursor.new_from_name(self.get_display(), "pointer")) # Set pointer cursor
                card_frame.add_css_class('interactive') # Add class for hover effects

                # Use Gtk.GestureClick for GTK4 compliant click handling
                gesture = Gtk.GestureClick.new()
                gesture.set_button(0) # Any button
                gesture.connect("released", self._on_card_activated_gesture, item)
                card_frame.add_controller(gesture)

                flowbox_child = Gtk.FlowBoxChild()
                flowbox_child.set_child(card_frame)
                content_cards.append(flowbox_child)

        # Now add file items (PKGBUILD, PACKAGE, PATCH, ADVANCED)
        for item in file_items:
            if not item.is_dir:
                # Check for simplified mode before showing advanced card
                if item.file_type == 'ADVANCED' and self.preferences_manager.get_simplified_mode():
                    continue # Skip advanced card in simplified mode

                # Get template from builder, ensure it's a fresh instance
                # Gtk.Builder.get_template returns the GtkTemplate object, need to instantiate.
                # The template is defined as a GtkBox, so we'll get the box.
                template_box = Gtk.Builder.get_template(self.__class__, f"{item.file_type.lower()}_card_template").new_with_values([])

                if not template_box:
                    logger.warning(f"No card template found for {item.file_type.lower()}_card_template. Skipping.")
                    continue

                # The card template from window.ui is a GtkBox, not GtkFrame.
                # To make it a "card" visual, we apply CSS classes to the top-level box or a wrapper.
                card_wrapper_frame = Gtk.Frame()
                card_wrapper_frame.add_css_class("card")
                card_wrapper_frame.add_css_class(f"{item.file_type.lower()}-card")
                card_wrapper_frame.set_size_request(220, 300) # Ensure consistent size
                card_wrapper_frame.set_child(template_box) # Set the template box as child
                card_wrapper_frame.set_visible(True)
                card_wrapper_frame.set_tooltip_text(item.path)
                card_wrapper_frame.set_cursor(Gdk.Cursor.new_from_name(self.get_display(), "pointer"))
                card_wrapper_frame.add_css_class('interactive') # Add class for hover effects

                # Use Gtk.GestureClick for GTK4 compliant click handling
                gesture = Gtk.GestureClick.new()
                gesture.set_button(0) # Any button
                gesture.connect("released", self._on_card_activated_gesture, item)
                card_wrapper_frame.add_controller(gesture)


                # Populate labels and icons for specific card types (on the template's children)
                self._populate_card_specific_info(template_box, item)

                # Connect buttons for specific card types (on the template's children)
                self._connect_card_actions(template_box, item)

                flowbox_child = Gtk.FlowBoxChild()
                flowbox_child.set_child(card_wrapper_frame) # Add the wrapper frame
                content_cards.append(flowbox_child)

        self.main_stack.set_visible_child_name("content")
        content_cards.show_all() # Ensure all new children are shown


    def _on_empty_state_download_pkgbuild_clicked(self, button: Gtk.Button):
        """Handler for 'Download PKGBUILD' button on empty state card."""
        logger.info("Empty State: Download PKGBUILD button clicked.")
        # Trigger the download PKGBUILD flow, perhaps by showing a search dialog
        # or directly calling a method to ask for package name.
        self._show_info_dialog("Download PKGBUILD", "Enter the AUR package name to download its PKGBUILD.", "system-search-symbolic")
        # For a full implementation, you'd likely pop up a small dialog with an entry field.
        # For now, let's assume the user will type into the main search bar.


    def _on_up_button_clicked(self, button: Gtk.Button):
        """Navigates up one level in the directory structure."""
        parent_path = os.path.dirname(self.current_path)
        if parent_path != self.current_path:
            self.current_path = parent_path
            self._start_scan_compatible_files_async(self.current_path)
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Navigated up to: {os.path.basename(self.current_path)}",
                status=ActionStatus.INFO,
                details={"path": self.current_path}
            ))
        else:
            self.show_welcome_screen()
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary="Navigated to welcome screen (from root)",
                status=ActionStatus.INFO
            ))

    def _on_card_activated_gesture(self, gesture: Gtk.GestureClick, n_press: int, x: float, y: float, item: FileItem):
        """Processes item activation in flowbox (click event from Gtk.GestureClick)."""
        if n_press == 1: # Single click
            if item.is_dir:
                self.current_path = item.path
                self._start_scan_compatible_files_async(self.current_path)
                self.history_manager.add_action(HistoryEntry(
                    id=None, timestamp=datetime.utcnow(),
                    action_type=ActionType.UI_INTERACTION,
                    summary=f"Opened directory: {item.name}",
                    status=ActionStatus.INFO,
                    details={"path": item.path}
                ))
                self.preferences_manager.add_recent_directory(item.path)
            else:
                self._process_selected_item(item)

    def _populate_card_specific_info(self, card_box: Gtk.Box, item: FileItem):
        """Populates labels and icons for specific card types (PKGBUILD, PACKAGE, PATCH, ADVANCED).
           card_box here is the GtkBox loaded from the template, not the wrapper frame.
        """
        if item.file_type == 'PKGBUILD':
            icon_widget = self.builder.get_object('pkgbuild_icon', card_box)
            name_label = self.builder.get_object('pkgbuild_name', card_box)
            version_label = self.builder.get_object('pkgbuild_version', card_box)
            dl_size_label = self.builder.get_object('pkgbuild_download_size', card_box)
            trust_icon = self.builder.get_object('trust_icon', card_box)
            trust_label = self.builder.get_object('trust_label', card_box)
            pkgbuild_votes_label = self.builder.get_object('pkgbuild_votes_label', card_box)
            pkgbuild_update_time_label = self.builder.get_object('pkgbuild_update_time_label', card_box)
            pkgbuild_pgp_status_label = self.builder.get_object('pkgbuild_pgp_status_label', card_box)

            if icon_widget: icon_widget.set_from_icon_name(item.get_icon_name())
            if name_label: name_label.set_label(item.name)
            if version_label: version_label.set_label(f"Version: {item.version}")
            if dl_size_label: dl_size_label.set_label(f"Download Size: N/A") # This needs dynamic fetching

            show_trust_icons = self.preferences_manager.get_show_trust_icons()
            if show_trust_icons and item.trust_level and trust_icon and trust_label:
                trust_icon.set_from_icon_name(item.get_trust_icon())
                trust_icon.set_visible(True)
                trust_label.set_label(item.trust_level.value)
                trust_label.get_style_context().remove_class("success-color")
                trust_label.get_style_context().remove_class("warning-color")
                trust_label.get_style_context().remove_class("error-color")
                if item.trust_level == TrustLevel.HIGH: trust_label.get_style_context().add_class("success-color")
                elif item.trust_level == TrustLevel.MEDIUM: trust_label.get_style_context().add_class("warning-color")
                else: trust_label.get_style_context().add_class("error-color")
            else:
                if trust_icon: trust_icon.set_visible(False)
                if trust_label: trust_label.set_visible(False)

            # Detailed trust box (initial values, to be updated by security_analyzer)
            if pkgbuild_votes_label: pkgbuild_votes_label.set_label(f"Votes: {item.votes}") # Use FileItem's votes
            if pkgbuild_update_time_label: pkgbuild_update_time_label.set_label(f"Last Update: {item.last_update_str}") # Use FileItem's
            if pkgbuild_pgp_status_label: pkgbuild_pgp_status_label.set_label(f"PGP: {item.pgp_status}") # Use FileItem's


        elif item.file_type == 'PACKAGE':
            icon_widget = self.builder.get_object('package_icon', card_box)
            name_label = self.builder.get_object('package_name', card_box)
            version_label = self.builder.get_object('package_version', card_box)
            details_label = self.builder.get_object('details_label', card_box)
            signature_icon = self.builder.get_object('signature_icon', card_box)
            signature_label = self.builder.get_object('signature_label', card_box)

            if icon_widget: icon_widget.set_from_icon_name(item.get_icon_name())
            if name_label: name_label.set_label(item.name)
            if version_label: version_label.set_label(f"Version: {item.version}")
            if details_label: details_label.set_label(item.extra_info or "Pre-compiled package file.")

            if signature_icon and signature_label:
                if item.signature_status == "Verified":
                    signature_icon.set_from_icon_name("security-high-symbolic")
                    signature_label.set_label("Verified")
                    signature_label.get_style_context().add_class("success-color")
                    signature_label.get_style_context().remove_class("error-color")
                else:
                    signature_icon.set_from_icon_name("security-low-symbolic")
                    signature_label.set_label("Not signed")
                    signature_label.get_style_context().add_class("error-color")
                    signature_label.get_style_context().remove_class("success-color")
                signature_icon.set_visible(True)
                signature_label.set_visible(True)

        elif item.file_type == 'PATCH':
            icon_widget = self.builder.get_object('patch_icon', card_box)
            name_label = self.builder.get_object('patch_name', card_box)
            description_label = self.builder.get_object('patch_description', card_box)

            if icon_widget: icon_widget.set_from_icon_name(item.get_icon_name())
            if name_label: name_label.set_label(item.name)
            if description_label: description_label.set_label(item.extra_info or "Patch file with changes.")

        elif item.file_type == 'ADVANCED':
            # No dynamic info needed beyond what's in the UI file for Advanced card,
            # as it's static informational text.
            pass


    def _connect_card_actions(self, card_box: Gtk.Box, item: FileItem):
        """Connects action buttons on a card to their respective handlers.
           card_box here is the GtkBox loaded from the template, not the wrapper frame.
        """
        if item.file_type == 'PKGBUILD':
            build_button = self.builder.get_object('build_button', card_box)
            edit_button = self.builder.get_object('edit_button', card_box)
            dependencies_button = self.builder.get_object('dependencies_button', card_box)
            sources_button = self.builder.get_object('sources_button', card_box)
            build_sandbox_button = self.builder.get_object('build_sandbox_button', card_box)
            confirm_sandbox_build_button = self.builder.get_object('confirm_pkgbuild_sandbox_build', card_box)

            if build_button: build_button.connect('clicked', self.on_build_package, item.path)
            if edit_button: edit_button.connect('clicked', self.on_edit_pkgbuild, item.path)
            if dependencies_button: dependencies_button.connect('clicked', self.on_view_dependencies, item.path)
            if sources_button: sources_button.connect('clicked', self.on_download_sources, item.path)

            if build_sandbox_button and confirm_sandbox_build_button:
                 # The popover content is a GtkBox, get its parent (GtkPopover) then its child (GtkBox)
                 popover_content_box = confirm_sandbox_build_button.get_parent()
                 sandbox_level_combo = self.builder.get_object('pkgbuild_sandbox_level_combo', popover_content_box)
                 sandbox_network_check = self.builder.get_object('pkgbuild_sandbox_network_check', popover_content_box)
                 sandbox_filesystem_check = self.builder.get_object('pkgbuild_sandbox_filesystem_check', popover_content_box)
                 confirm_sandbox_build_button.connect('clicked',
                     lambda btn, path=item.path, level_combo=sandbox_level_combo, net_check=sandbox_network_check, fs_check=sandbox_filesystem_check:
                         self.on_build_package_sandboxed(btn, path, level_combo.get_active_id(), net_check.get_active(), fs_check.get_active())
                 )

        elif item.file_type == 'PACKAGE':
            install_button = self.builder.get_object('install_button', card_box)
            info_button = self.builder.get_object('info_button', card_box)
            verify_button = self.builder.get_object('verify_button', card_box)
            install_sandbox_button = self.builder.get_object('install_sandbox_button', card_box)
            confirm_sandbox_install_button = self.builder.get_object('confirm_package_sandbox_install', card_box)

            if install_button: install_button.connect('clicked', self.on_install_package, item.path)
            if info_button: info_button.connect('clicked', self.on_view_package_info, item.path)
            if verify_button: verify_button.connect('clicked', self.on_verify_signature, item.path)

            if install_sandbox_button and confirm_sandbox_install_button:
                popover_content_box = confirm_sandbox_install_button.get_parent()
                sandbox_level_combo = self.builder.get_object('package_sandbox_level_combo', popover_content_box)
                sandbox_network_check = self.builder.get_object('package_sandbox_network_check', popover_content_box)
                sandbox_filesystem_check = self.builder.get_object('package_sandbox_filesystem_check', popover_content_box)
                confirm_sandbox_install_button.connect('clicked',
                    lambda btn, path=item.path, level_combo=sandbox_level_combo, net_check=sandbox_network_check, fs_check=sandbox_filesystem_check:
                        self.on_install_package_sandboxed(btn, path, level_combo.get_active_id(), net_check.get_active(), fs_check.get_active())
                )

        elif item.file_type == 'PATCH':
            apply_patch_button = self.builder.get_object('apply_patch_button', card_box)
            diff_button = self.builder.get_object('diff_button', card_box)
            apply_patch_sandbox_button = self.builder.get_object('apply_patch_sandbox_button', card_box)
            confirm_sandbox_apply_button = self.builder.get_object('confirm_patch_sandbox_apply', card_box)

            if apply_patch_button: apply_patch_button.connect('clicked', self.on_apply_patch, item.path)
            if diff_button: diff_button.connect('clicked', self.on_view_diff, item.path)

            if apply_patch_sandbox_button and confirm_sandbox_apply_button:
                popover_content_box = confirm_sandbox_apply_button.get_parent()
                sandbox_level_combo = self.builder.get_object('patch_sandbox_level_combo', popover_content_box)
                sandbox_network_check = self.builder.get_object('patch_sandbox_network_check', popover_content_box)
                sandbox_filesystem_check = self.builder.get_object('patch_sandbox_filesystem_check', popover_content_box)
                confirm_sandbox_apply_button.connect('clicked',
                    lambda btn, path=item.path, level_combo=sandbox_level_combo, net_check=sandbox_network_check, fs_check=sandbox_filesystem_check:
                        self.on_apply_patch_sandboxed(btn, path, level_combo.get_active_id(), net_check.get_active(), fs_check.get_active())
                )

        elif item.file_type == 'ADVANCED':
            custom_command_button = self.builder.get_object('custom_command_button', card_box)
            dry_run_button = self.builder.get_object('dry_run_button', card_box)
            docs_button = self.builder.get_object('docs_button', card_box)
            advanced_sandbox_command_button = self.builder.get_object('advanced_sandbox_command_button', card_box)
            confirm_advanced_sandbox_command = self.builder.get_object('confirm_advanced_sandbox_command', card_box)

            if custom_command_button: custom_command_button.connect('clicked', self.on_execute_custom_command)
            if dry_run_button: dry_run_button.connect('clicked', self.on_dry_run_command)
            if docs_button: docs_button.connect('clicked', self.on_consult_documentation)

            if advanced_sandbox_command_button and confirm_advanced_sandbox_command:
                popover_content_box = confirm_advanced_sandbox_command.get_parent()
                sandbox_level_combo = self.builder.get_object('advanced_sandbox_level_combo', popover_content_box)
                sandbox_network_check = self.builder.get_object('advanced_sandbox_network_check', popover_content_box)
                sandbox_filesystem_check = self.builder.get_object('advanced_sandbox_filesystem_check', popover_content_box)
                confirm_advanced_sandbox_command.connect('clicked',
                    lambda btn, level_combo=sandbox_level_combo, net_check=sandbox_network_check, fs_check=sandbox_filesystem_check:
                        self.on_execute_sandboxed_command(btn, level_combo.get_active_id(), net_check.get_active(), fs_check.get_active())
                )


    def _process_selected_item(self, item: FileItem):
        """Processes selected item and displays contextual interface."""
        if item.file_type == 'PKGBUILD':
            # Create a new instance from the PkgbuildReviewDialog class
            pkgbuild_review_dialog_instance = PkgbuildReviewDialog(transient_for=self, modal=True)
            # The builder.get_object('ID', scope) is primarily for widgets *within* an already loaded UI.
            # When using @Gtk.Template, the class itself becomes the primary way to access its UI.

            # Populate PKGBUILD review details
            pkgbuild_review_dialog_instance.update_package_info(
                name=item.name,
                version=item.version,
                path=item.path, # Pass direct path as this is the source
                trust_level_str=item.trust_level.value if item.trust_level else "N/A",
                votes=item.votes,
                last_update=item.last_update_str
            )

            # Connect build action from the dialog to window's handler
            pkgbuild_review_dialog_instance.build_button.connect('clicked', self._on_pkgbuild_review_build_clicked)
            pkgbuild_review_dialog_instance.connect("close-request", lambda d: d.close()) # Connect default close

            # Start asynchronous security analysis for heatmap and checklist
            self._start_pkgbuild_security_analysis(item.path, pkgbuild_review_dialog_instance, item.name, item.version)

            pkgbuild_review_dialog_instance.present()
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Opened PKGBUILD review for {item.name}",
                status=ActionStatus.INFO,
                related_pkg=item.name,
                details={"path": item.path}
            ))

        elif item.file_type == 'PACKAGE':
            self._show_info_dialog(item.name, f"Version: {item.version}\nSignature: {item.signature_status}", "package-x-generic-symbolic")
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Viewed package info for {item.name}",
                status=ActionStatus.INFO,
                related_pkg=item.name,
                details={"path": item.path}
            ))

        elif item.file_type == 'PATCH':
            self._show_info_dialog(item.name, f"Description: {item.extra_info}\nPath: {item.path}", "text-x-patch-symbolic")
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Viewed patch info for {item.name}",
                status=ActionStatus.INFO,
                related_pkg=item.name,
                details={"path": item.path}
            ))


    def _start_pkgbuild_security_analysis(self, pkgbuild_path: str, review_dialog_instance: PkgbuildReviewDialog, pkgname: str, pkgver: str):
        """
        Starts asynchronous security analysis for a PKGBUILD in a separate process.
        """
        self._show_processing_screen(f"Analyzing {pkgname} for risks...", dialog=review_dialog_instance)
        # Ensure SecurityAnalyzer has the UpstreamChecker if it needs AUR data
        if self.security_analyzer:
            self.security_analyzer.set_upstream_checker(self.upstream_checker)
            future = self.process_pool_executor.submit(self.security_analyzer.analyze_pkgbuild, pkgbuild_path)
            future.add_done_callback(
                lambda f: GLib.idle_add(self._on_pkgbuild_analysis_completed, f, review_dialog_instance, pkgname, pkgver, pkgbuild_path)
            )
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.PKGBUILD_BUILD,
                summary=f"Started security analysis for {pkgname}",
                status=ActionStatus.INFO,
                related_pkg=pkgname,
                details={"path": pkgbuild_path}
            ))
        else:
            error_ctx = ErrorContext(
                category=ErrorCategory.INTERNAL,
                summary="Security Analyzer Unavailable",
                details="Security analysis cannot be performed because the SecurityAnalyzer failed to initialize.",
                pkgname=pkgname,
                file_path=pkgbuild_path,
                suggested_actions=[SuggestedAction.CHECK_LOG]
            )
            self.error_handler.show_error_dialog(error_ctx)
            self._hide_processing_screen(dialog=review_dialog_instance)

    def _on_pkgbuild_analysis_completed(self, future: concurrent.futures.Future, review_dialog_instance: PkgbuildReviewDialog, pkgname: str, pkgver: str, pkgbuild_path: str):
        """Callback for PKGBUILD security analysis completion (on UI thread)."""
        try:
            analysis_results = future.result()
            # Assuming update_package_info, update_critical_changes_view, update_risk_checklist, update_heatmap_view
            # are methods on review_dialog_instance.
            review_dialog_instance.update_package_info(
                name=pkgname,
                version=pkgver,
                path=pkgbuild_path, # Use actual path
                trust_level_str=analysis_results.overall_trust_level.value,
                votes=analysis_results.aur_info.get("Votes", 0),
                last_update=analysis_results.aur_info.get("Last_Update", "N/A")
            )

            # Get specific section content using PkgbuildAnalyzer for better diff
            # PkgbuildAnalyzer requires explicit import and instantiation.
            # It's already available as self.file_utils.pkgbuild_analyzer
            pkgbuild_metadata = self.file_utils.pkgbuild_analyzer.parse_pkgbuild_detailed(pkgbuild_path)
            source_content = "\n".join(pkgbuild_metadata.source) if pkgbuild_metadata and pkgbuild_metadata.source else ""
            # Ensure PkgbuildFunction is imported or defined
            from paru_gui.pkgbuild_analyzer import PkgbuildFunction
            prepare_content = pkgbuild_metadata.functions.get("prepare", PkgbuildFunction("", "", -1, -1)).content if pkgbuild_metadata else ""
            package_content = pkgbuild_metadata.functions.get("package", PkgbuildFunction("", "", -1, -1)).content if pkgbuild_metadata else ""


            review_dialog_instance.update_critical_changes_view(
                source_content=source_content,
                prepare_content=prepare_content,
                package_content=package_content
            )
            review_dialog_instance.update_risk_checklist(
                risks=analysis_results.detected_risks,
                overall_risk_summary=f"Overall risk: {analysis_results.overall_trust_level.value}"
            )
            review_dialog_instance.update_heatmap_view(
                pkgbuild_content=analysis_results.raw_pkgbuild_content,
                heatmap_annotations=analysis_results.heatmap_lines
            )

            self._hide_processing_screen(dialog=review_dialog_instance)
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.PKGBUILD_BUILD, # Or a more specific 'PKGBUILD_ANALYSIS' type
                summary=f"Completed security analysis for {pkgname}",
                status=ActionStatus.SUCCESS if analysis_results.overall_trust_level == SecurityAnalyzer.RiskLevel.NONE else ActionStatus.WARNING,
                related_pkg=pkgname,
                details={"trust_level": analysis_results.overall_trust_level.value}
            ))
        except Exception as e:
            error_ctx = ErrorContext(
                category=ErrorCategory.PKGBUILD_ANALYSIS,
                summary="PKGBUILD Analysis Failed",
                details=f"Failed to perform security analysis for '{pkgname}' (v{pkgver}): {e}",
                pkgname=pkgname,
                pkgver=pkgver,
                file_path=pkgbuild_path,
                traceback=traceback.format_exc(),
                original_exception=e
            )
            self.error_handler.show_error_dialog(error_ctx)
            self._hide_processing_screen(dialog=review_dialog_instance)
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.PKGBUILD_BUILD,
                summary=f"Failed security analysis for {pkgname}",
                status=ActionStatus.FAILED,
                related_pkg=pkgname,
                details={"path": pkgbuild_path, "error": str(e)}
            ))


    # These methods are now handled by PkgbuildReviewDialog directly due to @Gtk.Template
    # def _on_pkgbuild_review_step_toggled(self, button: Gtk.ToggleButton): pass
    # def _on_pkgbuild_review_next_clicked(self, button: Gtk.Button): pass
    # def _on_pkgbuild_review_previous_clicked(self, button: Gtk.Button): pass
    # def _on_pkgbuild_review_sandbox_toggled(self, checkbutton: Gtk.CheckButton): pass


    def _on_pkgbuild_review_build_clicked(self, button: Gtk.Button):
        """Initiates the build process from the PKGBUILD review dialog."""
        # Find the PkgbuildReviewDialog instance from the button's parentage
        review_dialog_instance = button.get_ancestor(PkgbuildReviewDialog)
        if not review_dialog_instance:
            logger.error("Could not find parent PkgbuildReviewDialog for build action.")
            return

        # Access properties/children of the PkgbuildReviewDialog instance
        pkgbuild_path = review_dialog_instance.package_path.get_label().replace("Path: ", "")
        if not pkgbuild_path:
            self.error_handler.show_error_dialog(ErrorContext(
                category=ErrorCategory.UI_ERROR,
                summary="Missing PKGBUILD path",
                details="Could not retrieve PKGBUILD path from dialog UI.",
                suggested_actions=[SuggestedAction.CHECK_LOG]
            ))
            return

        if review_dialog_instance.enable_sandbox_check.get_active():
            sandbox_level_id = review_dialog_instance.sandbox_level_combo.get_active_id()
            allow_network = review_dialog_instance.sandbox_network_check.get_active()
            allow_home = review_dialog_instance.sandbox_home_check.get_active()

            self.on_build_package_sandboxed(button, pkgbuild_path, sandbox_level_id, allow_network, allow_home)
        else:
            self.on_build_package(button, pkgbuild_path)

        review_dialog_instance.close()

    def on_search_changed(self, entry: Gtk.SearchEntry):
        """Handles changes in the search entry for intelligent assistance."""
        text = entry.get_text().strip()
        # TODO: [~] Implement intelligent assistant logic here.
        # - Auto-complete for 'paru' commands
        # - Suggest packages
        # - Provide command help for prefixes like '-c'
        print(f"Search text changed: {text}")
        # Placeholder: If text starts with '-', offer command completion
        # If it looks like a package name, offer package search/info

    def on_search_activated(self, entry: Gtk.SearchEntry):
        """Handles activation (Enter key) in the search entry."""
        command_or_query = entry.get_text().strip()
        if command_or_query:
            logger.info(f"Executing search/command from search bar: {command_or_query}")
            # Determine if it's a command or package query
            if command_or_query.startswith("paru") or command_or_query.startswith("pacman") or command_or_query.startswith("sudo"):
                # Treat as a direct command to be executed in an external terminal
                self.terminal_manager.execute_command_in_system_terminal(shlex.split(command_or_query), cwd=self.current_path)
                self.history_manager.add_action(HistoryEntry(
                    id=None, timestamp=datetime.utcnow(),
                    action_type=ActionType.COMMAND_EXECUTION,
                    summary=f"Executed command from search bar: {command_or_query}",
                    status=ActionStatus.INFO,
                    details={"command": command_or_query}
                ))
            else:
                # Treat as a package search query (example: paru -Ss <query>)
                full_command = ['paru', '-Ss', command_or_query]
                self._run_shell_command_async(full_command, self.current_path, f"Search for: {command_or_query}",
                                              ActionType.COMMAND_EXECUTION, related_pkg=command_or_query,
                                              callback=lambda s, out, err: self._display_search_results(s, out, err, command_or_query))
            entry.set_text("") # Clear search after activation

    def _display_search_results(self, success: bool, stdout: str, stderr: str, query: str):
        if success:
            self._show_info_dialog(f"Search Results for '{query}'", stdout, "system-search-symbolic")
        else:
            error_ctx = ErrorContext(
                category=ErrorCategory.COMMAND_EXECUTION,
                summary=f"Search for '{query}' Failed",
                details=f"Paru search command returned an error. STDERR:\n{stderr}",
                command_executed=f"paru -Ss {query}",
                stdout=stdout,
                stderr=stderr,
                suggested_actions=[SuggestedAction.RETRY, SuggestedAction.CHECK_LOG]
            )
            self.error_handler.show_error_dialog(error_ctx)


    def _show_info_dialog(self, title: str, message: str, icon_name: str = "dialog-information-symbolic"):
        """Shows a generic information dialog."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=title,
            body=message,
            extra_button_label="OK"
        )
        dialog.set_icon_name(icon_name)
        dialog.connect("response", lambda d, r: d.close())
        dialog.present()


    def _show_processing_screen(self, message: str, progress_value: float = -1.0, dialog: Optional[Adw.Dialog] = None):
        """Displays the processing screen, optionally within a dialog."""
        spinner: Optional[Gtk.Spinner] = None
        label: Optional[Gtk.Label] = None
        progress_bar: Optional[Gtk.ProgressBar] = None
        cancel_button: Optional[Gtk.Button] = None
        details_button: Optional[Gtk.Button] = None

        if dialog: # For dialog-specific processing
            spinner = self.builder.get_object('processing_spinner', dialog)
            label = self.builder.get_object('processing_label', dialog)
            progress_bar = self.builder.get_object('processing_progress', dialog)
            cancel_button = self.builder.get_object('cancel_button', dialog)
            details_button = self.builder.get_object('details_button', dialog)
            # The processing_screen_box needs to be a direct child of the dialog's content area
            # Or at least in the dialog's direct scope.
            # For PkgbuildReviewDialog, the processing screen is a separate stack page.
            dialog_main_stack = self.builder.get_object('main_stack', dialog) # Assumes PkgbuildReviewDialog might have a stack
            if dialog_main_stack and dialog_main_stack.get_child_by_name('processing'):
                dialog_main_stack.set_visible_child_name('processing')
            else:
                # Fallback if dialog doesn't have a 'processing' stack page
                logger.warning(f"Dialog '{dialog.__gtype_name__}' does not have a 'processing' stack page. Cannot show processing screen within it.")
                # Show main window processing screen as a fallback
                self.main_stack.set_visible_child_name("processing")
                spinner = self.builder.get_object('processing_spinner')
                label = self.builder.get_object('processing_label')
                progress_bar = self.builder.get_object('processing_progress')
                cancel_button = self.builder.get_object('cancel_button')
                details_button = self.builder.get_object('details_button')

        else: # For main window processing
            self.main_stack.set_visible_child_name("processing")
            spinner = self.builder.get_object('processing_spinner')
            label = self.builder.get_object('processing_label')
            progress_bar = self.builder.get_object('processing_progress')
            cancel_button = self.builder.get_object('cancel_button')
            details_button = self.builder.get_object('details_button')

        if spinner: spinner.start()
        if label: label.set_label(message)
        if progress_bar:
            if progress_value >= 0:
                progress_bar.set_fraction(progress_value)
                progress_bar.set_text(f"{int(progress_value * 100)}%")
            else:
                progress_bar.set_fraction(0) # Indeterminate progress
                progress_bar.set_text("Working...")

        if cancel_button and not hasattr(cancel_button, '_connected_processing'):
            cancel_button.connect('clicked', self._on_processing_cancel_clicked)
            cancel_button._connected_processing = True
        if details_button and not hasattr(details_button, '_connected_processing'):
            details_button.connect('clicked', self._on_processing_details_clicked)
            details_button._connected_processing = True


    def _hide_processing_screen(self, dialog: Optional[Adw.Dialog] = None):
        """Hides the processing screen, optionally within a dialog."""
        if dialog:
            spinner = self.builder.get_object('processing_spinner', dialog)
            if spinner: spinner.stop()
            # Try to hide the processing_screen_box or switch stack child
            dialog_main_stack = self.builder.get_object('main_stack', dialog) # Assumes PkgbuildReviewDialog might have a stack
            if dialog_main_stack and dialog_main_stack.get_child_by_name('processing'):
                # After processing, return to the previously active step (step1 or step2)
                if dialog_main_stack.get_child_by_name('step1_content') and dialog_main_stack.get_child_by_name('step1_content').get_visible():
                    dialog_main_stack.set_visible_child_name('step1_content')
                elif dialog_main_stack.get_child_by_name('step2_content') and dialog_main_stack.get_child_by_name('step2_content').get_visible():
                    dialog_main_stack.set_visible_child_name('step2_content')
                else: # Fallback, hide the entire dialog or revert to a default view
                    logger.warning(f"Could not determine previous step in dialog '{dialog.__gtype_name__}'. Hiding processing screen directly.")
                    dialog_main_stack.set_visible_child_name('main_box') # Assume main_box is default content
        else:
            spinner = self.builder.get_object('processing_spinner')
            if spinner: spinner.stop()
            if self.main_stack.get_visible_child_name() == "processing":
                self.main_stack.set_visible_child_name("content") # Default to content


    def _on_processing_cancel_clicked(self, button: Gtk.Button):
        """Handles cancellation of a processing task."""
        # TODO: [ ] Implement actual cancellation logic for running futures/subprocesses
        logger.warning("Processing cancelled (cancellation logic TBD)!")
        self._hide_processing_screen(dialog=button.get_ancestor(Adw.Dialog))
        # Record cancellation in history
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.OTHER, # Or a more specific cancellation type
            summary="Processing task cancelled by user",
            status=ActionStatus.CANCELED,
            details={}
        ))


    def _on_processing_details_clicked(self, button: Gtk.Button):
        """Shows detailed logs/progress for a processing task."""
        # For now, append to the log_textview, in future, maybe a separate dialog/window
        # Need to find the log_textview in the correct scope (either main window or dialog)
        dialog_ancestor = button.get_ancestor(Adw.Dialog)
        if dialog_ancestor:
            log_textview = self.builder.get_object('log_textview', dialog_ancestor)
        else:
            log_textview = self.builder.get_object('log_textview')

        if log_textview:
            buffer = log_textview.get_buffer()
            # For demonstration, just append a message. Real output would be streamed.
            buffer.insert_at_cursor(f"\n[{datetime.now().isoformat()}] [INFO] Details button clicked. Log streaming from current process is internal.\n")
            log_textview.scroll_to_mark(buffer.get_end_iter(), 0.0, False, 0.0, 0.0)


    # --- Action handlers ---
    def _run_shell_command_async(self, command: List[str], cwd: str, description: str,
                                 action_type: ActionType, related_pkg: Optional[str] = None,
                                 is_undoable: bool = False,
                                 callback: Optional[Callable[[bool, str, str], None]] = None):
        """
        Executes a shell command in a separate thread/process and captures its output.
        This is suitable for non-interactive commands whose output needs to be processed by the GUI.
        For interactive commands, `terminal_manager.execute_command_in_system_terminal` should be used.
        """
        logger.info(f"Executing '{description}' asynchronously: {' '.join(command)}")
        self._show_processing_screen(f"{description}...", dialog=None)

        future = self.thread_pool_executor.submit(self._run_direct_command_worker, command, cwd)
        future.add_done_callback(
            lambda f: GLib.idle_add(self._on_command_completed, f, description, action_type, related_pkg, is_undoable, command, cwd, callback)
        )
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=action_type,
            summary=f"Initiated: {description}",
            status=ActionStatus.INFO,
            related_pkg=related_pkg,
            details={"command": " ".join(command), "cwd": cwd}
        ))


    def _run_direct_command_worker(self, command: List[str], cwd: str) -> Tuple[int, str, str]:
        """
        Worker function to execute a shell command directly (not in external terminal)
        and capture its output. Runs in a separate thread/process.
        """
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            stdout_lines = []
            stderr_lines = []

            # Read all output. For real-time streaming to internal GUI TextView,
            # this would use threads and GLib.idle_add, but that's not the current scope
            # of `TerminalManager` anymore.
            for line in process.stdout:
                stdout_lines.append(line)
            for line in process.stderr:
                stderr_lines.append(line)

            process.wait()
            return process.returncode, "".join(stdout_lines), "".join(stderr_lines)

        except FileNotFoundError:
            return 127, "", f"Error: Command '{command[0]}' not found in PATH."
        except Exception as e:
            return 1, "", f"Error executing command: {traceback.format_exc()}"


    def _on_command_completed(self, future: concurrent.futures.Future, description: str,
                             action_type: ActionType, related_pkg: Optional[str],
                             is_undoable: bool, original_command: List[str], cwd: str,
                             callback: Optional[Callable[[bool, str, str], None]]):
        """Callback for shell command completion (on UI thread)."""
        self._hide_processing_screen()
        status = ActionStatus.FAILED
        stdout_str = ""
        stderr_str = ""
        try:
            return_code, stdout_str, stderr_str = future.result()

            if return_code == 0:
                logger.info(f"'{description}' completed successfully. Output: {stdout_str}")
                status = ActionStatus.SUCCESS
                if callback: callback(True, stdout_str, stderr_str)
            else:
                logger.error(f"'{description}' failed with exit code {return_code}. STDERR: {stderr_str.strip()}")
                status = ActionStatus.FAILED

                error_ctx = ErrorContext(
                    category=ErrorCategory.COMMAND_EXECUTION,
                    summary=f"Command '{description}' Failed",
                    details=f"The command exited with code {return_code}. See output for details.",
                    pkgname=related_pkg,
                    command_executed=" ".join(original_command),
                    working_directory=cwd,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    suggested_actions=[SuggestedAction.RETRY, SuggestedAction.CHECK_LOG]
                )
                self.error_handler.show_error_dialog(error_ctx)
                if callback: callback(False, stdout_str, stderr_str)

        except concurrent.futures.CancelledError:
            logger.warning(f"'{description}' was cancelled.")
            status = ActionStatus.CANCELED
        except Exception as e:
            logger.critical(f"Internal error processing command completion for '{description}': {e}")
            status = ActionStatus.FAILED
            error_ctx = ErrorContext(
                category=ErrorCategory.INTERNAL,
                summary=f"Internal Error in '{description}' callback",
                details=f"An unexpected error occurred: {e}",
                pkgname=related_pkg,
                command_executed=" ".join(original_command),
                traceback=traceback.format_exc(),
                original_exception=e
            )
            self.error_handler.show_error_dialog(error_ctx)
        finally:
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=action_type,
                summary=description,
                status=status,
                related_pkg=related_pkg,
                details={"command": " ".join(original_command), "cwd": cwd, "stdout": stdout_str, "stderr": stderr_str},
                is_undoable=is_undoable
            ))


    def on_build_package(self, button: Gtk.Button, pkgbuild_path: str):
        """Starts the package building process without sandboxing."""
        pkgname, _, _ = self.file_utils.extract_pkgbuild_info(pkgbuild_path)
        build_dir = os.path.dirname(pkgbuild_path)
        # makepkg -s installs dependencies and builds
        command = ['makepkg', '-s', '--noconfirm'] # --noconfirm for non-interactive
        self._show_info_dialog("Build Initiated", f"Building {pkgname}. This will open in your system terminal.")
        self.terminal_manager.execute_command_in_system_terminal(command, cwd=build_dir)
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.PKGBUILD_BUILD,
            summary=f"Initiated build for: {pkgname} (non-sandboxed)",
            status=ActionStatus.INFO,
            related_pkg=pkgname,
            details={"command": " ".join(command), "cwd": build_dir, "sandboxed": False}
        ))
        # No direct callback for system terminal. User monitors there.

    def on_build_package_sandboxed(self, button: Gtk.Button, pkgbuild_path: str,
                                   sandbox_level_id: str, allow_network: bool, allow_home: bool):
        """
        Starts the package building process with sandboxing.
        """
        if not self.sandbox_manager:
            self.error_handler.show_error_dialog(ErrorContext(
                category=ErrorCategory.SYSTEM,
                summary="Sandboxing Unavailable",
                details="Bubblewrap (bwrap) is not installed or could not be initialized. Cannot run sandboxed command.",
                suggested_actions=[SuggestedAction.CONSULT_DOCS]
            ))
            return

        pkgname, _, _ = self.file_utils.extract_pkgbuild_info(pkgbuild_path)
        build_dir = os.path.dirname(pkgbuild_path)

        sandbox_options = SandboxOptions(
            isolation_level=IsolationLevel(sandbox_level_id),
            allow_network=allow_network,
            allow_home=allow_home,
            working_dir=build_dir,
            bind_paths=[(pkgbuild_path, os.path.join(build_dir, "PKGBUILD"), None)] # Default is --bind
        )
        command_to_sandbox = ['makepkg', '-s', '--noconfirm']

        self._show_info_dialog("Sandboxed Build Initiated", f"Building {pkgname} in a sandboxed environment. This will open in your system terminal.")
        self.terminal_manager.execute_command_in_system_terminal(command_to_sandbox, cwd=build_dir, is_sandboxed=True, sandbox_options=sandbox_options)
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.PKGBUILD_BUILD,
            summary=f"Initiated sandboxed build for: {pkgname}",
            status=ActionStatus.INFO,
            related_pkg=pkgname,
            details={"command": " ".join(command_to_sandbox), "cwd": build_dir, "sandbox_level": sandbox_level_id, "sandboxed": True}
        ))


    def on_edit_pkgbuild(self, button: Gtk.Button, pkgbuild_path: str):
        """Opens PKGBUILD in default editor."""
        editor = self.preferences_manager.get_default_editor()
        pkgname, _, _ = self.file_utils.extract_pkgbuild_info(pkgbuild_path)
        try:
            subprocess.Popen([editor, pkgbuild_path])
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Opened PKGBUILD for editing: {os.path.basename(pkgbuild_path)}",
                status=ActionStatus.INFO,
                related_pkg=pkgname,
                details={"path": pkgbuild_path, "editor": editor}
            ))
        except FileNotFoundError:
            error_ctx = ErrorContext(
                category=ErrorCategory.SYSTEM,
                summary="Editor Not Found",
                details=f"Could not find default editor '{editor}'. Please configure it in preferences.",
                file_path=pkgbuild_path,
                command_executed=editor,
                suggested_actions=[SuggestedAction.ADJUST_SETTINGS]
            )
            self.error_handler.show_error_dialog(error_ctx)
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Failed to open PKGBUILD for editing: {os.path.basename(pkgbuild_path)}",
                status=ActionStatus.FAILED,
                related_pkg=pkgname,
                details={"path": pkgbuild_path, "editor": editor, "error": "Editor not found"}
            ))
        except Exception as e:
            error_ctx = ErrorContext(
                category=ErrorCategory.INTERNAL,
                summary="Editor Error",
                details=f"Failed to open PKGBUILD: {e}",
                file_path=pkgbuild_path,
                traceback=traceback.format_exc(),
                original_exception=e
            )
            self.error_handler.show_error_dialog(error_ctx)
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Failed to open PKGBUILD for editing: {os.path.basename(pkgbuild_path)}",
                status=ActionStatus.FAILED,
                related_pkg=pkgname,
                details={"path": pkgbuild_path, "error": str(e)}
            ))


    def on_view_dependencies(self, button: Gtk.Button, pkgbuild_path: str):
        """Views package dependencies (for PKGBUILD)."""
        pkgname, _, _ = self.file_utils.extract_pkgbuild_info(pkgbuild_path)
        if pkgname != "unknown":
            command = ['paru', '-Si', pkgname]
            self._run_shell_command_async(command, os.path.dirname(pkgbuild_path), f"View Dependencies for {pkgname}",
                ActionType.UI_INTERACTION, pkgname, is_undoable=False,
                callback=lambda success, stdout, stderr: self._display_dependencies_info(success, stdout, stderr, pkgname)
            )
        else:
            error_ctx = ErrorContext(
                category=ErrorCategory.PKGBUILD_ANALYSIS,
                summary="Cannot view dependencies",
                details="Could not extract package name from PKGBUILD. Ensure 'pkgname' is defined.",
                file_path=pkgbuild_path,
                suggested_actions=[SuggestedAction.CHECK_LOG, SuggestedAction.OPEN_PKGBUILD]
            )
            self.error_handler.show_error_dialog(error_ctx)
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Failed to view dependencies (pkgname unknown) for {os.path.basename(pkgbuild_path)}",
                status=ActionStatus.FAILED,
                details={"path": pkgbuild_path}
            ))

    def _display_dependencies_info(self, success: bool, stdout: str, stderr: str, pkgname: str):
        if success:
            deps_match = re.search(r'Depends On\s*:\s*(.*)', stdout)
            make_deps_match = re.search(r'Make Depends On\s*:\s*(.*)', stdout)
            check_deps_match = re.search(r'Check Depends On\s*:\s*(.*)', stdout)
            opt_deps_match = re.search(r'Optional Deps\s*:\s*(.*)', stdout)

            dependencies = deps_match.group(1).strip() if deps_match else "None"
            make_dependencies = make_deps_match.group(1).strip() if make_deps_match else "None"
            check_dependencies = check_deps_match.group(1).strip() if check_deps_match else "None"
            optional_dependencies = opt_deps_match.group(1).strip() if opt_deps_match else "None"

            message = (
                f"Dependencies: {dependencies}\n"
                f"Make Dependencies: {make_dependencies}\n"
                f"Check Dependencies: {check_dependencies}\n"
                f"Optional Dependencies: {optional_dependencies}"
            )
            self._show_info_dialog(f"Dependencies for {pkgname}", message)
        else:
            error_ctx = ErrorContext(
                category=ErrorCategory.COMMAND_EXECUTION,
                summary=f"Failed to get dependencies for {pkgname}",
                details=f"Paru command returned an error. STDERR:\n{stderr}",
                pkgname=pkgname,
                command_executed=f"paru -Si {pkgname}",
                stdout=stdout,
                stderr=stderr,
                suggested_actions=[SuggestedAction.RETRY, SuggestedAction.CHECK_LOG]
            )
            self.error_handler.show_error_dialog(error_ctx)


    def on_download_sources(self, button: Gtk.Button, pkgbuild_path: str):
        """Downloads source files for building a PKGBUILD."""
        pkgname, _, _ = self.file_utils.extract_pkgbuild_info(pkgbuild_path)
        build_dir = os.path.dirname(pkgbuild_path)
        # paru -G <package> downloads the PKGBUILD and related files
        # into a subdirectory named <package> in the current working directory.
        command = ['paru', '-G', pkgname]
        self._show_info_dialog("Download Sources Initiated", f"Downloading sources for {pkgname}. This will open in your system terminal.")
        self.terminal_manager.execute_command_in_system_terminal(command, cwd=build_dir)
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.PKGBUILD_BUILD,
            summary=f"Initiated source download for: {pkgname}",
            status=ActionStatus.INFO,
            related_pkg=pkgname,
            details={"command": " ".join(command), "cwd": build_dir}
        ))


    def on_install_package(self, button: Gtk.Button, package_path: str):
        """Installs the selected package without sandboxing."""
        pkgname = self.file_utils.get_pkg_name_from_zst(package_path)
        install_dir = os.path.dirname(package_path)
        command = ['sudo', 'pacman', '-U', '--noconfirm', package_path]
        self._show_info_dialog("Installation Initiated", f"Installing {os.path.basename(package_path)}. This may require your `sudo` password in the terminal.")
        self.terminal_manager.execute_command_in_system_terminal(command, cwd=install_dir)
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.PACKAGE_INSTALL,
            summary=f"Initiated install for: {pkgname} (non-sandboxed)",
            status=ActionStatus.INFO,
            related_pkg=pkgname,
            details={"command": " ".join(command), "cwd": install_dir, "sandboxed": False},
            is_undoable=True
        ))


    def on_install_package_sandboxed(self, button: Gtk.Button, package_path: str,
                                     sandbox_level_id: str, allow_network: bool, allow_home: bool):
        """
        Installs the selected package with sandboxing.
        """
        if not self.sandbox_manager:
            self.error_handler.show_error_dialog(ErrorContext(
                category=ErrorCategory.SYSTEM,
                summary="Sandboxing Unavailable",
                details="Bubblewrap (bwrap) is not installed or could not be initialized. Cannot run sandboxed command.",
                suggested_actions=[SuggestedAction.CONSULT_DOCS]
            ))
            return

        pkgname = self.file_utils.get_pkg_name_from_zst(package_path)
        install_dir = os.path.dirname(package_path)

        sandbox_options = SandboxOptions(
            isolation_level=IsolationLevel(sandbox_level_id),
            allow_network=allow_network,
            allow_home=allow_home,
            working_dir=install_dir,
            bind_paths=[(package_path, package_path, None)]
        )
        command_to_sandbox = ['sudo', 'pacman', '-U', '--noconfirm', package_path]

        self._show_info_dialog("Sandboxed Installation Initiated", f"Installing {pkgname} in a sandboxed environment. This will open in your system terminal.")
        self.terminal_manager.execute_command_in_system_terminal(command_to_sandbox, cwd=install_dir, is_sandboxed=True, sandbox_options=sandbox_options)
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.PACKAGE_INSTALL,
            summary=f"Initiated sandboxed install for: {pkgname}",
            status=ActionStatus.INFO,
            related_pkg=pkgname,
            details={"command": " ".join(command_to_sandbox), "cwd": install_dir, "sandbox_level": sandbox_level_id, "sandboxed": True},
            is_undoable=True
        ))


    def on_view_package_info(self, button: Gtk.Button, package_path: str):
        """Displays detailed information about the .zst package."""
        pkgname = self.file_utils.get_pkg_name_from_zst(package_path)
        command = ['pacman', '-Qip', package_path]
        self._run_shell_command_async(command, os.path.dirname(package_path), f"View Package Info for {pkgname}",
            ActionType.UI_INTERACTION, pkgname, is_undoable=False,
            callback=lambda success, stdout, stderr: self._display_pacman_info(success, stdout, stderr, pkgname)
        )

    def _display_pacman_info(self, success: bool, stdout: str, stderr: str, pkgname: str):
        if success:
            self._show_info_dialog(f"Package Info: {pkgname}", stdout)
        else:
            error_ctx = ErrorContext(
                category=ErrorCategory.COMMAND_EXECUTION,
                summary=f"Failed to get info for {pkgname}",
                details=f"Pacman command returned an error. STDERR:\n{stderr}",
                pkgname=pkgname,
                command_executed=f"pacman -Qip {pkgname}",
                stdout=stdout,
                stderr=stderr,
                suggested_actions=[SuggestedAction.RETRY, SuggestedAction.CHECK_LOG]
            )
            self.error_handler.show_error_dialog(error_ctx)


    def on_verify_signature(self, button: Gtk.Button, package_path: str):
        """Verifies package signature."""
        pkgname = self.file_utils.get_pkg_name_from_zst(package_path)
        sig_path = package_path + '.sig'
        if not os.path.exists(sig_path):
            error_ctx = ErrorContext(
                category=ErrorCategory.FILE_OPERATION,
                summary="Signature File Missing",
                details=f"No .sig file found for package '{pkgname}' at '{sig_path}'. Cannot verify signature.",
                file_path=package_path,
                suggested_actions=[SuggestedAction.CHECK_LOG]
            )
            self.error_handler.show_error_dialog(error_ctx)
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Failed to verify signature (no .sig) for {pkgname}",
                status=ActionStatus.FAILED,
                related_pkg=pkgname,
                details={"path": package_path}
            ))
            return

        command = ['gpg', '--verify', sig_path, package_path]
        self._run_shell_command_async(command, os.path.dirname(package_path), f"Verify Signature for {pkgname}",
            ActionType.UI_INTERACTION, pkgname, is_undoable=False,
            callback=lambda success, stdout, stderr: self._display_signature_verification_result(success, stdout, stderr, pkgname)
        )

    def _display_signature_verification_result(self, success: bool, stdout: str, stderr: str, pkgname: str):
        if success:
            self._show_info_dialog("Signature Verified", f"The package signature for '{pkgname}' is valid.", "security-high-symbolic")
        else:
            error_ctx = ErrorContext(
                category=ErrorCategory.SECURITY_RISK,
                summary=f"Signature Verification Failed for {pkgname}",
                details=f"The package signature could not be verified. This package might be tampered with. STDERR:\n{stderr}",
                pkgname=pkgname,
                command_executed=f"gpg --verify {pkgname}.sig {pkgname}", # Simplified command display
                stdout=stdout,
                stderr=stderr,
                suggested_actions=[SuggestedAction.CHECK_LOG, SuggestedAction.REPORT_AUR]
            )
            self.error_handler.show_error_dialog(error_ctx)


    def on_apply_patch(self, button: Gtk.Button, patch_path: str):
        """Applies the selected patch without sandboxing."""
        patch_name = os.path.basename(patch_path)
        patch_dir = os.path.dirname(patch_path)
        # TODO: Ask user for target directory/files to patch
        # For demo, assume applying to some generic source in the same dir
        command = ['patch', '-p1', '-i', os.path.basename(patch_path)]
        self._show_info_dialog("Apply Patch Initiated", f"Applying '{patch_name}'. This may require user interaction in the terminal.")
        self.terminal_manager.execute_command_in_system_terminal(command, cwd=patch_dir)
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.PATCH_APPLY,
            summary=f"Initiated patch apply for: {patch_name} (non-sandboxed)",
            status=ActionStatus.INFO,
            related_pkg=patch_name,
            details={"command": " ".join(command), "cwd": patch_dir, "sandboxed": False},
            is_undoable=False
        ))


    def on_apply_patch_sandboxed(self, button: Gtk.Button, patch_path: str,
                                 sandbox_level_id: str, allow_network: bool, allow_home: bool):
        """
        Applies the selected patch with sandboxing.
        """
        if not self.sandbox_manager:
            self.error_handler.show_error_dialog(ErrorContext(
                category=ErrorCategory.SYSTEM,
                summary="Sandboxing Unavailable",
                details="Bubblewrap (bwrap) is not installed or could not be initialized. Cannot run sandboxed command.",
                suggested_actions=[SuggestedAction.CONSULT_DOCS]
            ))
            return

        patch_name = os.path.basename(patch_path)
        patch_dir = os.path.dirname(patch_path)

        sandbox_options = SandboxOptions(
            isolation_level=IsolationLevel(sandbox_level_id),
            allow_network=allow_network,
            allow_home=allow_home,
            working_dir=patch_dir,
            bind_paths=[(patch_path, os.path.join(patch_dir, patch_name), None)]
        )
        command_to_sandbox = ['patch', '-p1', '-i', patch_name]

        self._show_info_dialog("Sandboxed Patch Apply Initiated", f"Applying '{patch_name}' in a sandboxed environment. This will open in your system terminal.")
        self.terminal_manager.execute_command_in_system_terminal(command_to_sandbox, cwd=patch_dir, is_sandboxed=True, sandbox_options=sandbox_options)
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.PATCH_APPLY,
            summary=f"Initiated sandboxed patch apply for: {patch_name}",
            status=ActionStatus.INFO,
            related_pkg=patch_name,
            details={"command": " ".join(command_to_sandbox), "cwd": patch_dir, "sandbox_level": sandbox_level_id, "sandboxed": True},
            is_undoable=False
        ))


    def on_view_diff(self, button: Gtk.Button, patch_path: str):
        """Views patch diff."""
        patch_name = os.path.basename(patch_path)
        # For simplicity, always show raw content, as finding the 'original_filepath' is contextual.
        success, content, err_msg = self.file_utils.preview_patch_diff(patch_path)

        if success:
            self._show_info_dialog(f"Diff for {patch_name}", content, "text-x-patch-symbolic")
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Viewed diff for {patch_name}",
                status=ActionStatus.INFO,
                related_pkg=patch_name,
                details={"path": patch_path}
            ))
        else:
            error_ctx = ErrorContext(
                category=ErrorCategory.FILE_OPERATION,
                summary=f"Could not read patch file '{patch_name}'",
                details=f"Failed to read file for diff view: {err_msg}",
                file_path=patch_path,
                traceback=traceback.format_exc(),
                original_exception=Exception(err_msg)
            )
            self.error_handler.show_error_dialog(error_ctx)
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Failed to view diff for {patch_name}",
                status=ActionStatus.FAILED,
                related_pkg=patch_name,
                details={"path": patch_path, "error": err_msg}
            ))


    def on_execute_custom_command(self, *args):
        """Placeholder for executing a custom command (non-sandboxed)."""
        # This button typically launches a dialog to ask for the command.
        # For now, it could launch an external terminal with a generic shell.
        self._show_info_dialog("Custom Command", "Please enter your custom command in the search bar or use the terminal panel.", "utilities-terminal-symbolic")
        self.terminal_manager.show_terminal_panel()
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.UI_INTERACTION,
            summary="Attempted to execute custom command (prompt user)",
            status=ActionStatus.INFO
        ))

    def on_dry_run_command(self, *args):
        """Placeholder for simulating an action (dry run)."""
        self._show_info_dialog("Dry Run", "Dry run functionality is currently simulated. Commands will be displayed but not executed.", "system-run-symbolic")
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.COMMAND_EXECUTION,
            summary="Executed dry run (simulated)",
            status=ActionStatus.INFO
        ))

    def on_consult_documentation(self, *args):
        """Placeholder for consulting documentation."""
        Gtk.show_uri(self, "https://wiki.archlinux.org/title/Arch_User_Repository", Gdk.CURRENT_TIME)
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.UI_INTERACTION,
            summary="Consulted documentation (AUR Wiki)",
            status=ActionStatus.INFO
        ))

    def on_execute_sandboxed_command(self, *args):
        """Placeholder for executing a custom command in a sandbox."""
        self._show_info_dialog("Sandboxed Custom Command", "Please enter your custom command in the search bar for sandboxed execution.", "security-high-symbolic")
        self.terminal_manager.show_terminal_panel() # Still show panel for general context
        # The command itself would be input via the search bar after this, then executed sandboxed.
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.COMMAND_EXECUTION,
            summary=f"Attempted sandboxed custom command (prompt user)",
            status=ActionStatus.INFO,
            details={"sandbox_level": args[0], "network": args[1], "home": args[2]} if len(args) > 2 else {}
        ))


    # --- Upstream Updates specific actions (from window.ui primary_menu and upstream_update_cards) ---
    def on_show_upstream_updates(self, *args):
        """Action handler for showing upstream updates screen."""
        self.main_stack.set_visible_child_name("upstream_updates")
        self._start_check_all_upstream_updates_async()
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.UI_INTERACTION,
            summary="Opened Upstream Updates screen",
            status=ActionStatus.INFO
        ))

    def on_refresh_upstream_updates_action(self, *args):
        """Action handler for refreshing upstream updates."""
        self.upstream_checker.invalidate_cache() # Clear cache for a fresh check
        self._start_check_all_upstream_updates_async()
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.UPSTREAM_CHECK,
            summary="Refreshed upstream updates (cleared cache)",
            status=ActionStatus.INFO
        ))

    def _start_check_all_upstream_updates_async(self):
        """
        Initiates checking for all upstream updates in the current directory.
        """
        self._show_processing_screen("Checking for upstream updates...", dialog=None)

        # In a real implementation, you would scan known PKGBUILDs in configured AUR dirs.
        # For this example, we'll scan the current_path for PKGBUILDs.
        pkgbuild_paths = []
        for root, _, files in os.walk(self.current_path):
            if "PKGBUILD" in files:
                pkgbuild_paths.append(os.path.join(root, "PKGBUILD"))

        if not pkgbuild_paths:
            GLib.idle_add(self._on_all_upstream_checks_completed, ([], []), []) # No PKGBUILDs to check
            return

        futures = [
            self.thread_pool_executor.submit(self.upstream_checker.check_for_updates, path)
            for path in pkgbuild_paths
        ]

        # Use another future to wait for all upstream checks to complete
        # Wait up to 60 seconds for all checks to complete, but don't block indefinitely
        all_checks_future = concurrent.futures.wait(futures, timeout=60)

        # Then process results in the UI thread
        GLib.idle_add(self._on_all_upstream_checks_completed, all_checks_future, pkgbuild_paths)

        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.UPSTREAM_CHECK,
            summary="Initiated upstream check for all PKGBUILDs",
            status=ActionStatus.INFO,
            details={"path": self.current_path, "pkgbuilds_found": len(pkgbuild_paths)}
        ))

    def _on_all_upstream_checks_completed(self, all_checks_future: Tuple[List[concurrent.futures.Future], List[concurrent.futures.Future]], pkgbuild_paths: List[str]):
        """Callback for when all upstream checks for multiple PKGBUILDs are complete."""
        self._hide_processing_screen()
        # Get the flowbox from the upstream_updates_view
        upstream_update_cards_flowbox = self.builder.get_object('upstream_update_cards')
        if not upstream_update_cards_flowbox:
            logger.error("Upstream update cards FlowBox not found.")
            return

        while upstream_update_cards_flowbox.get_first_child() is not None:
            upstream_update_cards_flowbox.remove(upstream_update_cards_flowbox.get_first_child())

        updates_found = []
        for future in all_checks_future[0]: # Iterate over completed futures
            try:
                update_info = future.result()
                if update_info:
                    updates_found.append(update_info)
                    # Create an instance of UpstreamUpdateCard
                    update_card = UpstreamUpdateCard()

                    # Extract actual pkgname from path (update_info.pkgname is initially the path)
                    pkgname_from_path, _, _ = self.file_utils.extract_pkgbuild_info(update_info.pkgname)
                    current_aur_version = self.file_utils.extract_pkgbuild_info(update_info.pkgname)[1]

                    update_card.update_card_data(pkgname_from_path, current_aur_version, {
                        "version": update_info.version,
                        "release_date": update_info.release_date,
                        "changelog_url": update_info.changelog_url,
                        "cve_fix_info": update_info.cve_fix_info
                    })
                    # Connect the sandboxed update button for this specific card
                    # update_card.confirm_sandbox_update.connect('clicked',
                    #     lambda btn, card_info=update_info: self._on_confirm_upstream_sandbox_update(btn, card_info)
                    # )
                    # Connect other buttons if needed

                    flowbox_child = Gtk.FlowBoxChild()
                    flowbox_child.set_child(update_card)
                    upstream_update_cards_flowbox.append(flowbox_child)
            except Exception as e:
                logger.error(f"Error processing individual upstream check result: {e}")
                # Individual errors are logged, but the overall UI still attempts to display others.

        if not updates_found:
            # Display the empty state for upstream updates.
            # Use the generic empty card template from window.ui
            empty_state_instance = self.builder.get_object('empty_card_template')
            if empty_state_instance:
                empty_state_box = empty_state_instance.unparent() # Detach from builder scope
                # Correctly target labels within the empty_card_template in window.ui
                title_label = self.builder.get_object('heading', empty_state_box)
                description_label = self.builder.get_object('label', empty_state_box)
                download_button = self.builder.get_object('download_button', empty_state_box)

                if title_label: title_label.set_label("No Upstream Updates Found")
                if description_label: description_label.set_label("All packages appear to be up-to-date or no upstream source was detected.")
                # Hide any buttons if present in this generic empty card
                if download_button: download_button.set_visible(False)
                empty_state_box.set_visible(True)

                flowbox_child = Gtk.FlowBoxChild()
                flowbox_child.set_child(empty_state_box)
                upstream_update_cards_flowbox.append(flowbox_child)
            else:
                logger.error("Empty card template not found for upstream updates.")


        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.UPSTREAM_CHECK,
            summary="Completed upstream check for all PKGBUILDs",
            status=ActionStatus.SUCCESS if updates_found else ActionStatus.INFO,
            details={"pkgbuilds_scanned": len(pkgbuild_paths), "updates_found": len(updates_found)}
        ))


    # --- Application-wide actions (from main.py primary_menu) ---
    def on_system_action(self, *args):
        self._show_info_dialog("System Information", "Display system and Arch Linux related details here.")
        self.history_manager.add_action(HistoryEntry(id=None, timestamp=datetime.utcnow(), action_type=ActionType.UI_INTERACTION, summary="Viewed System Info", status=ActionStatus.INFO))

    def on_statistics_action(self, *args):
        self._show_info_dialog("Statistics", "Display package manager statistics here (e.g., package count, disk usage).")
        self.history_manager.add_action(HistoryEntry(id=None, timestamp=datetime.utcnow(), action_type=ActionType.UI_INTERACTION, summary="Viewed Statistics", status=ActionStatus.INFO))

    def on_arch_news_action(self, *args):
        self._show_info_dialog("Arch News", "Display official Arch Linux news feed here.")
        self.history_manager.add_action(HistoryEntry(id=None, timestamp=datetime.utcnow(), action_type=ActionType.UI_INTERACTION, summary="Viewed Arch News", status=ActionStatus.INFO))

    def on_clean_cache_action(self, *args):
        self._show_info_dialog("Clean Cache", "Initiate cleaning of pacman and paru caches. This will open in your system terminal.")
        command = ['sudo', 'paru', '-Scc', '--noconfirm']
        self.terminal_manager.execute_command_in_system_terminal(command, cwd=os.path.expanduser("~"))
        self.history_manager.add_action(HistoryEntry(id=None, timestamp=datetime.utcnow(), action_type=ActionType.CACHE_CLEAN, summary="Initiated cache clean", status=ActionStatus.INFO, is_undoable=False))

    def on_update_system_action(self, *args):
        self._show_info_dialog("System Update", "Initiate a full system update. This will open in your system terminal.")
        command = ['sudo', 'paru', '-Syu', '--noconfirm']
        self.terminal_manager.execute_command_in_system_terminal(command, cwd=os.path.expanduser("~"))
        self.history_manager.add_action(HistoryEntry(id=None, timestamp=datetime.utcnow(), action_type=ActionType.SYSTEM_UPDATE, summary="Initiated system update", status=ActionStatus.INFO, is_undoable=False))

    def on_action_history_action(self, *args):
        # TODO: Implement a proper history viewer dialog/screen
        history_str = self.history_manager.export_history_to_string(limit=20)
        self._show_info_dialog("Action History", history_str, "document-history-symbolic")
        self.history_manager.add_action(HistoryEntry(id=None, timestamp=datetime.utcnow(), action_type=ActionType.UI_INTERACTION, summary="Viewed Action History", status=ActionStatus.INFO))

    def on_hide_advanced_action(self, action: Gio.SimpleAction, parameter: Optional[GLib.Variant]):
        # This action would toggle the 'simplified-mode' preference
        current_state = self.preferences_manager.get_simplified_mode()
        self.preferences_manager.set_simplified_mode(not current_state)
        # Update UI if needed, e.g., re-scan current directory
        self._start_scan_compatible_files_async(self.current_path)
        logger.info(f"Toggled Simplified Mode to: {not current_state}")
        self.history_manager.add_action(HistoryEntry(id=None, timestamp=datetime.utcnow(), action_type=ActionType.UI_INTERACTION, summary=f"Toggled Simplified Mode to {not current_state}", status=ActionStatus.INFO))

    def on_check_devel_action(self, *args):
        # This action would toggle the 'check-devel-updates' preference
        current_state = self.preferences_manager.get_check_devel_updates()
        self.preferences_manager.set_check_devel_updates(not current_state)
        logger.info(f"Toggled Check Devel Updates to: {not current_state}")
        self.history_manager.add_action(HistoryEntry(id=None, timestamp=datetime.utcnow(), action_type=ActionType.UI_INTERACTION, summary=f"Toggled Check Devel Updates to {not current_state}", status=ActionStatus.INFO))

    def on_install_debug_action(self, *args):
        # This action would toggle the 'install-debug-packages' preference
        current_state = self.preferences_manager.get_install_debug_packages()
        self.preferences_manager.set_install_debug_packages(not current_state)
        logger.info(f"Toggled Install Debug Packages to: {not current_state}")
        self.history_manager.add_action(HistoryEntry(id=None, timestamp=datetime.utcnow(), action_type=ActionType.UI_INTERACTION, summary=f"Toggled Install Debug Packages to {not current_state}", status=ActionStatus.INFO))

    def on_show_warnings_action(self, *args):
        # This action would toggle the 'show-detailed-warnings' preference
        current_state = self.preferences_manager.get_show_detailed_warnings()
        self.preferences_manager.set_show_detailed_warnings(not current_state)
        logger.info(f"Toggled Show Detailed Warnings to: {not current_state}")
        self.history_manager.add_action(HistoryEntry(id=None, timestamp=datetime.utcnow(), action_type=ActionType.UI_INTERACTION, summary=f"Toggled Show Detailed Warnings to {not current_state}", status=ActionStatus.INFO))

    def on_show_terminal_panel_action(self, *args):
        # This action would toggle the 'show-realtime-terminal' preference
        current_state = self.preferences_manager.get_show_realtime_terminal()
        if current_state:
            self.terminal_manager.hide_terminal_panel()
        else:
            self.terminal_manager.show_terminal_panel()
        # The preference manager callback will update the preference.
        self.history_manager.add_action(HistoryEntry(id=None, timestamp=datetime.utcnow(), action_type=ActionType.UI_INTERACTION, summary=f"Toggled Terminal Panel visibility to {not current_state}", status=ActionStatus.INFO))

    def on_review_pkgbuild_action(self, *args):
        # This action might trigger a file chooser to select a PKGBUILD for review
        self._show_info_dialog("Review PKGBUILD", "Select a PKGBUILD file to open its security review dialog.", "text-x-generic-symbolic")
        self.on_select_file_clicked() # Re-use file selection logic.
        self.history_manager.add_action(HistoryEntry(id=None, timestamp=datetime.utcnow(), action_type=ActionType.UI_INTERACTION, summary="Initiated PKGBUILD review from menu", status=ActionStatus.INFO))

    def on_go_home_action(self, *args):
        """Action to go back to the home/welcome screen."""
        self.show_welcome_screen()
        self.history_manager.add_action(HistoryEntry(id=None, timestamp=datetime.utcnow(), action_type=ActionType.UI_INTERACTION, summary="Navigated to Home Screen", status=ActionStatus.INFO))

    def on_go_back_action(self, *args):
        """Action to go back in navigation history (conceptual)."""
        self._show_info_dialog("Navigation", "Back action (conceptual) - not fully implemented.", "go-previous-symbolic")
        self.history_manager.add_action(HistoryEntry(id=None, timestamp=datetime.utcnow(), action_type=ActionType.UI_INTERACTION, summary="Attempted Back Navigation", status=ActionStatus.INFO))

    def on_go_forward_action(self, *args):
        """Action to go forward in navigation history (conceptual)."""
        self._show_info_dialog("Navigation", "Forward action (conceptual) - not fully implemented.", "go-next-symbolic")
        self.history_manager.add_action(HistoryEntry(id=None, timestamp=datetime.utcnow(), action_type=ActionType.UI_INTERACTION, summary="Attempted Forward Navigation", status=ActionStatus.INFO))

    def on_search_packages_action(self, *args):
        """Action to focus the search bar for package search."""
        if self.search_entry:
            self.search_entry.grab_focus()
            self.search_entry.set_text("paru -Ss ") # Pre-fill for common search
        self.history_manager.add_action(HistoryEntry(id=None, timestamp=datetime.utcnow(), action_type=ActionType.UI_INTERACTION, summary="Focused search for packages", status=ActionStatus.INFO))

```
