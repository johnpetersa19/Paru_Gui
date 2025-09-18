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
from enum import Enum
import concurrent.futures
import threading # Explicitly import threading for ThreadPoolExecutor
from typing import Optional, List, Dict, Any, Tuple, Callable

from gi.repository import Gtk, Gio, GLib, Gdk, GObject, Adw, Pango

# Import proposed new modules
from .upstream_checker import UpstreamChecker
from .security_analyzer import SecurityAnalyzer
from .sandboxing import SandboxManager, SandboxOptions, IsolationLevel
from .error_handler import ErrorHandler, ErrorContext, ErrorCategory, ErrorDetail, SuggestedAction
from .history_manager import HistoryManager, ActionType, ActionStatus, HistoryEntry
# from .preferences_manager import PreferencesManager # Assuming this will be a new module
# from .file_utils import FileUtils # Assuming file helper functions move here
# from .terminal_manager import TerminalManager # Assuming real-time terminal logic moves here

# Enums and Data Classes (currently in window.py, to be refactored to file_utils.py)
class TrustLevel(Enum):
    HIGH = "HIGH"    # 50+ votes
    MEDIUM = "MEDIUM" # 10-50 votes
    LOW = "LOW"      # <10 votes

class FileItem(GObject.Object):
    """Represents a compatible file or directory with its metadata."""
    __gtype_name__ = "FileItem" # Needed if GObject properties are used for ListView/FlowBox

    # Example GObject properties - uncomment and use if binding directly to Gtk.ListItem
    # __gproperties__ = {
    #     "file_type": (GObject.TYPE_STRING, "File Type", "Type of the file (PKGBUILD, PACKAGE, PATCH, DIR)", None, GObject.ParamFlags.READWRITE),
    #     "name": (GObject.TYPE_STRING, "Name", "File or package name", None, GObject.ParamFlags.READWRITE),
    #     "version": (GObject.TYPE_STRING, "Version", "Package version", None, GObject.ParamFlags.READWRITE),
    #     "path": (GObject.TYPE_STRING, "Path", "Full path to the file/directory", None, GObject.ParamFlags.READWRITE),
    #     "is_dir": (GObject.TYPE_BOOLEAN, "Is Directory", "True if it's a directory", False, GObject.ParamFlags.READWRITE),
    #     # Add other properties as needed
    # }

    def __init__(self, file_type: str, name: str, version: str, path: str,
                 trust_level: Optional[TrustLevel] = None,
                 signature_status: str = "N/A", extra_info: str = ""):
        super().__init__()
        self.file_type = file_type  # 'PKGBUILD', 'PACKAGE', 'PATCH', 'DIR'
        self.name = name
        self.version = version
        self.path = path
        self.trust_level = trust_level
        self.signature_status = signature_status
        self.extra_info = extra_info
        self.is_dir = os.path.isdir(path)

    def get_icon_name(self) -> str:
        """Returns the appropriate GNOME icon for the file type."""
        if self.is_dir:
            return "folder-symbolic"
        elif self.file_type == 'PKGBUILD':
            return "text-x-generic-symbolic"
        elif self.file_type == 'PACKAGE':
            return "package-x-generic-symbolic"
        elif self.file_type == 'PATCH':
            return "text-x-patch-symbolic"
        return "unknown-symbolic"

    def get_trust_icon(self) -> Optional[str]:
        """Returns the appropriate trust icon (for PKGBUILDs)."""
        if self.file_type != 'PKGBUILD' or not self.trust_level:
            return None
        if self.trust_level == TrustLevel.HIGH:
            return "security-high-symbolic"
        elif self.trust_level == TrustLevel.MEDIUM:
            return "security-medium-symbolic"
        return "security-low-symbolic"


class ParuGuiWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("Paru GUI")
        self.set_default_size(900, 650)

        # Thread pool for I/O-bound tasks (network, disk scanning)
        self.thread_pool_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        # Process pool for CPU-bound or security-sensitive tasks (PKGBUILD analysis, sandboxing)
        self.process_pool_executor = concurrent.futures.ProcessPoolExecutor(max_workers=threading.cpu_count())

        # Current directory for content view
        self.current_path = os.path.expanduser("~") # Start at home directory

        # Initialize core components
        self.upstream_checker = UpstreamChecker()
        self.security_analyzer = SecurityAnalyzer()
        self.sandbox_manager = SandboxManager()
        self.history_manager = HistoryManager()
        # self.preferences_manager = PreferencesManager() # Placeholder for new module
        # self.file_utils = FileUtils() # Placeholder for new module
        # self.terminal_manager = TerminalManager() # Placeholder for new module

        # UI Components (loaded from .ui files)
        self.builder = Gtk.Builder()
        self.builder.add_from_resource('/org/gnome/paru-gui/window.ui') # Main window layout
        self.builder.add_from_resource('/org/gnome/paru-gui/ui/screens/welcome_screen.ui')
        self.builder.add_from_resource('/org/gnome/paru-gui/ui/screens/content_view.ui')
        self.builder.add_from_resource('/org/gnome/paru-gui/ui/screens/pkgbuild_review.ui')
        self.builder.add_from_resource('/org/gnome/paru-gui/ui/screens/upstream_update.ui')
        self.builder.add_from_resource('/org/gnome/paru-gui/ui/components/file_chooser_dialog.ui') # Re-use for folder browser
        self.builder.add_from_resource('/org/gnome/paru-gui/ui/components/error_dialog.ui')
        self.builder.add_from_resource('/org/gnome/paru-gui/ui/components/help-overlay.ui')
        self.builder.add_from_resource('/org/gnome/paru-gui/ui/components/search_bar.ui')
        self.builder.add_from_resource('/org/gnome/paru-gui/ui/components/empty_state.ui') # Empty state for flowboxes

        # Initialize ErrorHandler after builder is ready
        self.error_handler = ErrorHandler(self.builder, self, self.get_application().get_version())

        # Get main UI elements
        self.main_stack = self.builder.get_object('main_stack')
        self.header_bar = self.builder.get_object('header_bar') # Will be attached to Adw.ApplicationWindow titlebar

        self.setup_main_interface()

        # Connect application actions (defined in main.py)
        self.builder.get_object('help_button').connect('clicked', lambda btn: self.get_application().lookup_action('shortcuts').activate(None))

        # Link security_analyzer to upstream_checker (if needed, for shared parsing)
        self.security_analyzer.set_upstream_checker(self.upstream_checker)


    def setup_main_interface(self):
        """Configures the main interface, attaching UI elements and connecting signals."""
        self.set_titlebar(self.header_bar)

        app_menu_button = self.builder.get_object('app_menu_button')
        app_menu_button.set_menu_model(self.get_application().get_menu_by_id('primary_menu'))

        self.search_entry = self.builder.get_object('search_entry')
        self.search_entry.connect('search-changed', self.on_search_changed)
        self.search_entry.connect('activate', self.on_search_activated)

        self.set_child(self.main_stack)
        self.show_welcome_screen()

        # Connect signals for Welcome Screen
        self.builder.get_object('select_file_button').connect("clicked", self.on_select_file_clicked)
        self.builder.get_object('select_folder_button').connect("clicked", self.on_select_folder_clicked)

        self.recent_dirs_flowbox = self.builder.get_object('recent_dirs_flowbox')
        self._load_recent_directories() # Load and display recent dirs


    def _load_recent_directories(self):
        """Loads recent directories from preferences (or dummy) and displays them."""
        # TODO: Integrate with PreferencesManager.get_recent_directories()
        recent_dirs = ["/home/john/Projects/Paru_Gui", "/tmp/aur-builds", "/var/cache/pacman/pkg"] # Dummy data

        while self.recent_dirs_flowbox.get_first_child() is not None:
            self.recent_dirs_flowbox.remove(self.recent_dirs_flowbox.get_first_child())

        for path in recent_dirs:
            button = Gtk.Button(label=os.path.basename(path))
            button.set_tooltip_text(path)
            button.add_css_class('pill')
            button.connect('clicked', self._on_recent_dir_clicked, path)
            self.recent_dirs_flowbox.append(button)

    def _on_recent_dir_clicked(self, button: Gtk.Button, path: str):
        """Callback for clicking a recent directory button."""
        self.current_path = path
        self.main_stack.set_visible_child_name("content")
        self._start_scan_compatible_files_async(path)
        # TODO: Record UI interaction in history_manager

    def show_welcome_screen(self):
        """Displays the welcome screen."""
        self.main_stack.set_visible_child_name("welcome")
        # TODO: Record UI interaction in history_manager

    def on_select_file_clicked(self, button: Gtk.Button):
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
        # TODO: Record UI interaction in history_manager

    def _on_single_file_response(self, dialog: Gtk.FileChooserNative, response: Gtk.ResponseType):
        """Processes selection of a single file."""
        if response == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_file().get_path()
            if file_path:
                self.current_path = os.path.dirname(file_path)
                self.main_stack.set_visible_child_name("content")
                self._start_scan_compatible_files_async(self.current_path, initial_selection_path=file_path)
            # TODO: Add to recent directories via PreferencesManager
        dialog.destroy()

    def on_select_folder_clicked(self, button: Gtk.Button):
        """Opens dialog to select folder with smart file visualization."""
        dialog = Gtk.FileChooserNative(
            title="Select Folder",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        dialog.connect("response", self._on_folder_selection_response)
        dialog.show()
        # TODO: Record UI interaction in history_manager

    def _on_folder_selection_response(self, dialog: Gtk.FileChooserNative, response: Gtk.ResponseType):
        """Processes folder selection from the native dialog."""
        if response == Gtk.ResponseType.ACCEPT:
            folder_path = dialog.get_file().get_path()
            if folder_path:
                self.current_path = folder_path
                self.main_stack.set_visible_child_name("content")
                self._start_scan_compatible_files_async(self.current_path)
            # TODO: Add to recent directories via PreferencesManager
        dialog.destroy()

    def _start_scan_compatible_files_async(self, folder_path: str, initial_selection_path: Optional[str] = None):
        """Starts scanning compatible files in a separate thread."""
        self._show_processing_screen(f"Scanning '{os.path.basename(folder_path)}'...")
        future = self.thread_pool_executor.submit(self._scan_compatible_files_worker, folder_path)
        future.add_done_callback(
            lambda f: GLib.idle_add(
                self._on_scan_completed, f, folder_path, initial_selection_path
            )
        )
        # TODO: Record action in history_manager

    def _scan_compatible_files_worker(self, folder_path: str) -> List[FileItem]:
        """
        Worker function for scanning files (runs in a separate thread).
        [~] Partially Implemented: Basic async scan in place.
        """
        file_items: List[FileItem] = []
        scan_limit = 100 # Example limit for initial lazy load

        # TODO: [ ] Implement full lazy loading:
        # Instead of `os.listdir`, this would involve iterating a limited number of items,
        # and then handling scroll events to load more. For now, it's a simple list dir.

        try:
            entries = sorted(os.listdir(folder_path)) # Sort for consistent display
            for i, filename in enumerate(entries):
                if i >= scan_limit: # Basic limit for initial scan
                    break

                filepath = os.path.join(folder_path, filename)

                if os.path.islink(filepath): # Skip symlinks for simplicity
                    continue

                if os.path.isdir(filepath):
                    file_items.append(FileItem(file_type='DIR', name=filename, version="", path=filepath, extra_info="Directory"))
                    continue

                # PKGBUILD detection
                if filename == "PKGBUILD":
                    # TODO: Refactor _extract_pkgbuild_info to FileUtils
                    pkgname, pkgver, pkgrel = self._extract_pkgbuild_info(filepath)
                    # TODO: Refactor _get_aur_votes to FileUtils/AURClient
                    votes = self._get_aur_votes(pkgname) if pkgname != "unknown" else 0
                    # TODO: Refactor _get_trust_level to FileUtils/TrustManager
                    trust_level = self._get_trust_level(votes) if votes > 0 else None

                    item = FileItem(
                        file_type='PKGBUILD',
                        name=pkgname if pkgname != "unknown" else "PKGBUILD",
                        version=f"{pkgver}-{pkgrel}" if pkgver != "unknown" else "N/A",
                        path=filepath,
                        trust_level=trust_level
                    )
                    file_items.append(item)

                # .zst package detection
                elif filename.endswith('.pkg.tar.zst') and not filename.endswith('.sig'):
                    # TODO: Refactor _get_pkg_name_from_zst to FileUtils
                    pkg_name = self._get_pkg_name_from_zst(filepath)
                    # TODO: Refactor _check_signature to FileUtils
                    signature = self._check_signature(filepath)

                    item = FileItem(
                        file_type='PACKAGE',
                        name=pkg_name,
                        # TODO: Refactor _get_pkg_version to FileUtils
                        version=self._get_pkg_version(filepath),
                        path=filepath,
                        signature_status=signature
                    )
                    file_items.append(item)

                # Patch detection
                elif filename.endswith(('.patch', '.diff')):
                    # TODO: Refactor _get_patch_description to FileUtils
                    patch_desc = self._get_patch_description(filepath)

                    item = FileItem(
                        file_type='PATCH',
                        name=os.path.splitext(filename)[0],
                        version="",
                        path=filepath,
                        extra_info=patch_desc
                    )
                    file_items.append(item)
        except Exception as e:
            # Use ErrorHandler for errors
            error_ctx = ErrorContext(
                category=ErrorCategory.FILE_OPERATION,
                summary="File scanning failed",
                details=f"Could not scan directory '{folder_path}': {e}",
                file_path=folder_path,
                traceback=str(e), # For simple cases, just the exception message
                original_exception=e
            )
            GLib.idle_add(self.error_handler.show_error_dialog, error_ctx)
            return []
        return file_items

    def _on_scan_completed(self, future: concurrent.futures.Future, folder_path: str, initial_selection_path: Optional[str] = None):
        """Callback executed on the UI thread when file scan is complete."""
        try:
            file_items = future.result()
            self._update_content_view(file_items, folder_path)

            if initial_selection_path:
                content_cards = self.builder.get_object('content_cards')
                for child in content_cards: # Iterate over GtkFlowBoxChildren
                    if hasattr(child.get_child(), 'get_tooltip_text') and child.get_child().get_tooltip_text() == initial_selection_path:
                        content_cards.select_child(child)
                        content_cards.scroll_to_child(child) # Scroll to selected item
                        # content_cards.activate_child(child) # Potentially activate it
                        break
            self._hide_processing_screen()
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Scanned directory: {os.path.basename(folder_path)}",
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

    def _update_content_view(self, file_items: List[FileItem], folder_path: str):
        """Populates the content view with scanned file items."""
        content_cards = self.builder.get_object('content_cards')
        current_path_label = self.builder.get_object('current_path_label')
        file_count_label = self.builder.get_object('file_count_label')
        up_button = self.builder.get_object('up_button')

        current_path_label.set_label(folder_path)
        file_count_label.set_label(f"{len(file_items)} files found")
        # Ensure only one connection to prevent multiple triggers
        if not hasattr(up_button, '_connected'):
            up_button.connect('clicked', self._on_up_button_clicked)
            up_button._connected = True

        while content_cards.get_first_child() is not None:
            content_cards.remove(content_cards.get_first_child())

        # If no files found, display empty state
        if not file_items:
            empty_state_box = self.builder.get_object('empty_state_box').unparent() # Detach from builder template
            empty_state_box.set_visible(True)
            self.builder.get_object('empty_title_label', empty_state_box).set_label("Empty Directory")
            self.builder.get_object('empty_description_label', empty_state_box).set_label(f"No compatible files found in '{os.path.basename(folder_path)}'.")
            self.builder.get_object('empty_options_box', empty_state_box).set_visible(True) # Re-show options

            # Connect buttons on empty state if needed
            self.builder.get_object('download_pkgbuild_button', empty_state_box).connect('clicked', lambda btn: print("Download PKGBUILD clicked (empty state)"))
            self.builder.get_object('builder_mode_button', empty_state_box).connect('clicked', lambda btn: print("Builder Mode clicked (empty state)"))

            flowbox_child = Gtk.FlowBoxChild()
            flowbox_child.set_child(empty_state_box)
            content_cards.append(flowbox_child)
            self.main_stack.set_visible_child_name("content")
            return


        for item in file_items:
            card_frame: Optional[Gtk.Frame] = None
            if item.is_dir:
                # Create a generic directory card
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
                card_frame.set_tooltip_text(item.path)
                card_frame.connect('button-release-event', lambda w, e, i=item: self._on_card_activated(w, e, i)) # Connect with item


            else: # For PKGBUILD, PACKAGE, PATCH, ADVANCED
                card_template_id = f"{item.file_type.lower()}_card_template"
                template_widget = self.builder.get_object(card_template_id)
                if not template_widget:
                    logger.warning(f"No card template found for {item.file_type} (ID: {card_template_id}). Skipping.")
                    continue

                # Detach the card from the builder (it's a template)
                card_frame = template_widget.unparent()
                card_frame.set_visible(True)
                card_frame.set_tooltip_text(item.path) # Set tooltip for easy path access
                card_frame.connect('button-release-event', lambda w, e, i=item: self._on_card_activated(w, e, i)) # Connect with item

                # Populate labels and icons for specific card types
                self._populate_card_specific_info(card_frame, item)

                # Connect buttons for specific card types
                self._connect_card_actions(card_frame, item)

            if card_frame:
                flowbox_child = Gtk.FlowBoxChild()
                flowbox_child.set_child(card_frame)
                content_cards.append(flowbox_child)

        self.main_stack.set_visible_child_name("content")


    def _on_up_button_clicked(self, button: Gtk.Button):
        """Navigates up one level in the directory structure."""
        parent_path = os.path.dirname(self.current_path)
        if parent_path != self.current_path: # Avoid going up from root
            self.current_path = parent_path
            self._start_scan_compatible_files_async(self.current_path)
            # TODO: Record UI interaction in history_manager
        else:
            self.show_welcome_screen() # Go back to welcome if at file system root

    def _on_card_activated(self, widget: Gtk.Widget, event: Gdk.EventButton, item: FileItem):
        """Processes item activation in flowbox (click event)."""
        if event.type == Gdk.EventType.BUTTON_RELEASE and event.button == 1: # Left click
            if item.is_dir:
                self.current_path = item.path
                self._start_scan_compatible_files_async(self.current_path)
                # TODO: Record UI interaction in history_manager
            else:
                self._process_selected_item(item)

    def _populate_card_specific_info(self, card_frame: Gtk.Frame, item: FileItem):
        """Populates labels and icons for specific card types (PKGBUILD, PACKAGE, PATCH)."""
        # This function assumes specific IDs within each card's hierarchy.
        # This is a bit fragile if UI template IDs change, better to pass widget references or
        # have specific classes for each card type with their own template children.

        # Example for PKGBUILD Card (assuming IDs in pkgbuild_card_template)
        if item.file_type == 'PKGBUILD':
            icon_widget = self.builder.get_object('pkgbuild_icon', card_frame)
            name_label = self.builder.get_object('pkgbuild_name', card_frame)
            version_label = self.builder.get_object('pkgbuild_version', card_frame)
            dl_size_label = self.builder.get_object('pkgbuild_download_size', card_frame)
            trust_icon = self.builder.get_object('trust_icon', card_frame)
            trust_label = self.builder.get_object('trust_label', card_frame)

            if icon_widget: icon_widget.set_from_icon_name(item.get_icon_name())
            if name_label: name_label.set_label(item.name)
            if version_label: version_label.set_label(f"Version: {item.version}")
            if dl_size_label: dl_size_label.set_label(f"Download Size: N/A") # Needs actual fetch

            if item.trust_level and trust_icon and trust_label:
                trust_icon.set_from_icon_name(item.get_trust_icon())
                trust_icon.set_visible(True)
                trust_label.set_label(item.trust_level.value)
                trust_label.remove_css_class("success-color")
                trust_label.remove_css_class("warning-color")
                trust_label.remove_css_class("error-color")
                if item.trust_level == TrustLevel.HIGH: trust_label.add_css_class("success-color")
                elif item.trust_level == TrustLevel.MEDIUM: trust_label.add_css_class("warning-color")
                else: trust_label.add_css_class("error-color")

            # Detailed trust box (if present in template and populated)
            pkgbuild_votes_label = self.builder.get_object('pkgbuild_votes_label', card_frame)
            pkgbuild_update_time_label = self.builder.get_object('pkgbuild_update_time_label', card_frame)
            pkgbuild_pgp_status_label = self.builder.get_object('pkgbuild_pgp_status_label', card_frame)
            if pkgbuild_votes_label: pkgbuild_votes_label.set_label(f"Votes: (fetching...)")
            if pkgbuild_update_time_label: pkgbuild_update_time_label.set_label(f"Last Update: (fetching...)")
            if pkgbuild_pgp_status_label: pkgbuild_pgp_status_label.set_label(f"PGP: (fetching...)")


        # Example for Package Card (assuming IDs in package_card_template)
        elif item.file_type == 'PACKAGE':
            icon_widget = self.builder.get_object('package_icon', card_frame)
            name_label = self.builder.get_object('package_name', card_frame)
            version_label = self.builder.get_object('package_version', card_frame)
            details_label = self.builder.get_object('details_label', card_frame)
            signature_icon = self.builder.get_object('signature_icon', card_frame)
            signature_label = self.builder.get_object('signature_label', card_frame)

            if icon_widget: icon_widget.set_from_icon_name(item.get_icon_name())
            if name_label: name_label.set_label(item.name)
            if version_label: version_label.set_label(f"Version: {item.version}")
            if details_label: details_label.set_label(item.extra_info or "Pre-compiled package file.")

            if signature_icon and signature_label:
                if item.signature_status == "Verified":
                    signature_icon.set_from_icon_name("security-high-symbolic")
                    signature_label.set_label("Verified")
                    signature_label.add_css_class("success-color")
                else:
                    signature_icon.set_from_icon_name("security-low-symbolic")
                    signature_label.set_label("Not signed")
                    signature_label.add_css_class("error-color")

        # Example for Patch Card (assuming IDs in patch_card_template)
        elif item.file_type == 'PATCH':
            icon_widget = self.builder.get_object('patch_icon', card_frame)
            name_label = self.builder.get_object('patch_name', card_frame)
            description_label = self.builder.get_object('patch_description', card_frame)

            if icon_widget: icon_widget.set_from_icon_name(item.get_icon_name())
            if name_label: name_label.set_label(item.name)
            if description_label: description_label.set_label(item.extra_info or "Patch file with changes.")


    def _connect_card_actions(self, card_frame: Gtk.Frame, item: FileItem):
        """Connects action buttons on a card to their respective handlers."""
        # Retrieve buttons using card_frame as the scope
        if item.file_type == 'PKGBUILD':
            build_button = self.builder.get_object('build_button', card_frame)
            edit_button = self.builder.get_object('edit_button', card_frame)
            dependencies_button = self.builder.get_object('dependencies_button', card_frame)
            sources_button = self.builder.get_object('sources_button', card_frame)
            confirm_sandbox_build_button = self.builder.get_object('confirm_pkgbuild_sandbox_build', card_frame)

            if build_button: build_button.connect('clicked', self.on_build_package, item.path)
            if edit_button: edit_button.connect('clicked', self.on_edit_pkgbuild, item.path)
            if dependencies_button: dependencies_button.connect('clicked', self.on_view_dependencies, item.path)
            if sources_button: sources_button.connect('clicked', self.on_download_sources, item.path)
            if confirm_sandbox_build_button:
                 # Pass current sandbox settings from the popover's widgets on click
                 popover = confirm_sandbox_build_button.get_parent_visible().get_parent_visible()
                 sandbox_level_combo = self.builder.get_object('pkgbuild_sandbox_level_combo', popover)
                 sandbox_network_check = self.builder.get_object('pkgbuild_sandbox_network_check', popover)
                 sandbox_filesystem_check = self.builder.get_object('pkgbuild_sandbox_filesystem_check', popover)
                 confirm_sandbox_build_button.connect('clicked',
                     lambda btn, path=item.path, level_combo=sandbox_level_combo, net_check=sandbox_network_check, fs_check=sandbox_filesystem_check:
                         self.on_build_package_sandboxed(btn, path, level_combo.get_active_id(), net_check.get_active(), fs_check.get_active())
                 )

        elif item.file_type == 'PACKAGE':
            install_button = self.builder.get_object('install_button', card_frame)
            info_button = self.builder.get_object('info_button', card_frame)
            verify_button = self.builder.get_object('verify_button', card_frame)
            confirm_sandbox_install_button = self.builder.get_object('confirm_package_sandbox_install', card_frame)

            if install_button: install_button.connect('clicked', self.on_install_package, item.path)
            if info_button: info_button.connect('clicked', self.on_view_package_info, item.path)
            if verify_button: verify_button.connect('clicked', self.on_verify_signature, item.path)
            if confirm_sandbox_install_button:
                popover = confirm_sandbox_install_button.get_parent_visible().get_parent_visible()
                sandbox_level_combo = self.builder.get_object('package_sandbox_level_combo', popover)
                sandbox_network_check = self.builder.get_object('package_sandbox_network_check', popover)
                sandbox_filesystem_check = self.builder.get_object('package_sandbox_filesystem_check', popover)
                confirm_sandbox_install_button.connect('clicked',
                    lambda btn, path=item.path, level_combo=sandbox_level_combo, net_check=sandbox_network_check, fs_check=sandbox_filesystem_check:
                        self.on_install_package_sandboxed(btn, path, level_combo.get_active_id(), net_check.get_active(), fs_check.get_active())
                )

        elif item.file_type == 'PATCH':
            apply_patch_button = self.builder.get_object('apply_patch_button', card_frame)
            diff_button = self.builder.get_object('diff_button', card_frame)
            confirm_sandbox_apply_button = self.builder.get_object('confirm_patch_sandbox_apply', card_frame)

            if apply_patch_button: apply_patch_button.connect('clicked', self.on_apply_patch, item.path)
            if diff_button: diff_button.connect('clicked', self.on_view_diff, item.path)
            if confirm_sandbox_apply_button:
                popover = confirm_sandbox_apply_button.get_parent_visible().get_parent_visible()
                sandbox_level_combo = self.builder.get_object('patch_sandbox_level_combo', popover)
                sandbox_network_check = self.builder.get_object('patch_sandbox_network_check', popover)
                sandbox_filesystem_check = self.builder.get_object('patch_sandbox_filesystem_check', popover)
                confirm_sandbox_apply_button.connect('clicked',
                    lambda btn, path=item.path, level_combo=sandbox_level_combo, net_check=sandbox_network_check, fs_check=sandbox_filesystem_check:
                        self.on_apply_patch_sandboxed(btn, path, level_combo.get_active_id(), net_check.get_active(), fs_check.get_active())
                )

        # TODO: Connect Advanced Card buttons (if dynamically created)
        # self.builder.get_object('custom_command_button', card_frame).connect('clicked', self.on_execute_custom_command, item.path)
        # self.builder.get_object('confirm_advanced_sandbox_command', card_frame).connect('clicked', self.on_execute_sandboxed_command, item.path)
        # self.builder.get_object('dry_run_button', card_frame).connect('clicked', self.on_dry_run_command, item.path)
        # self.builder.get_object('docs_button', card_frame).connect('clicked', self.on_consult_documentation, item.path)


    def _process_selected_item(self, item: FileItem):
        """Processes selected item and displays contextual interface."""
        # For simplicity, we'll replace the content in the main_stack for PKGBUILD review
        if item.file_type == 'PKGBUILD':
            # Load the PKGBUILD review dialog
            # This dialog is a <template class="PkgbuildReviewDialog" parent="AdwDialog">
            pkgbuild_review_dialog = self.builder.get_object('PkgbuildReviewDialog')

            # Connect signals for the dialog's UI elements
            self.builder.connect_signals_for_object(pkgbuild_review_dialog, {
                'on_step_toggled': self._on_pkgbuild_review_step_toggled,
                'on_cancel_clicked': lambda w: pkgbuild_review_dialog.close(),
                'on_next_clicked': self._on_pkgbuild_review_next_clicked,
                'on_previous_clicked': self._on_pkgbuild_review_previous_clicked,
                'on_build_clicked': self._on_pkgbuild_review_build_clicked,
                'on_sandbox_toggled': self._on_pkgbuild_review_sandbox_toggled # For the expander
            })

            pkgbuild_review_dialog.set_transient_for(self)
            pkgbuild_review_dialog.set_modal(True)

            # Populate PKGBUILD review details
            self.builder.get_object('package_name', pkgbuild_review_dialog).set_label(item.name)
            self.builder.get_object('version_label', pkgbuild_review_dialog).set_label(f"Version: {item.version}")
            self.builder.get_object('package_path', pkgbuild_review_dialog).set_label(f"Path: {item.path}")
            # Other labels (votes, trust, etc.) should also be populated dynamically

            # Start asynchronous security analysis for heatmap and checklist
            self._start_pkgbuild_security_analysis(item.path, pkgbuild_review_dialog, item.name, item.version)

            pkgbuild_review_dialog.present()
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

    def _start_pkgbuild_security_analysis(self, pkgbuild_path: str, review_dialog: Adw.Dialog, pkgname: str, pkgver: str):
        """
        [ ] Asynchronous security checklist integration:
        Starts asynchronous security analysis for a PKGBUILD in a separate process.
        """
        self._show_processing_screen(f"Analyzing {pkgname} for risks...", dialog=review_dialog)
        future = self.process_pool_executor.submit(self.security_analyzer.analyze_pkgbuild, pkgbuild_path)
        future.add_done_callback(
            lambda f: GLib.idle_add(self._on_pkgbuild_analysis_completed, f, review_dialog, pkgname, pkgver)
        )
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.PKGBUILD_BUILD,
            summary=f"Started security analysis for {pkgname}",
            status=ActionStatus.INFO,
            related_pkg=pkgname,
            details={"path": pkgbuild_path}
        ))

    def _on_pkgbuild_analysis_completed(self, future: concurrent.futures.Future, review_dialog: Adw.Dialog, pkgname: str, pkgver: str):
        """Callback for PKGBUILD security analysis completion (on UI thread)."""
        try:
            analysis_results = future.result()
            self._update_pkgbuild_review_ui(analysis_results, review_dialog)
            self._hide_processing_screen(dialog=review_dialog)
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.PKGBUILD_BUILD,
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
                file_path=self.builder.get_object('package_path', review_dialog).get_label().replace("Path: ", ""),
                traceback=traceback.format_exc(),
                original_exception=e
            )
            self.error_handler.show_error_dialog(error_ctx)
            self._hide_processing_screen(dialog=review_dialog)
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.PKGBUILD_BUILD,
                summary=f"Failed security analysis for {pkgname}",
                status=ActionStatus.FAILED,
                related_pkg=pkgname,
                details={"error": str(e)}
            ))


    def _update_pkgbuild_review_ui(self, results: SecurityAnalyzer.PkgbuildSecurityAnalysisResult, review_dialog: Adw.Dialog):
        """Updates the PKGBUILD review dialog with analysis results."""
        trust_label = self.builder.get_object('package_trust_label', review_dialog)
        if trust_label:
            overall_trust = results.overall_trust_level
            trust_label.set_label(f"Trust: {overall_trust.value}")
            # Reset and apply CSS classes for color based on trust_level
            trust_label.get_style_context().remove_class("success-color")
            trust_label.get_style_context().remove_class("warning-color")
            trust_label.get_style_context().remove_class("error-color")
            if overall_trust == SecurityAnalyzer.RiskLevel.NONE: trust_label.get_style_context().add_class("success-color")
            elif overall_trust == SecurityAnalyzer.RiskLevel.LOW: trust_label.get_style_context().add_class("success-color") # Low risk is still "good"
            elif overall_trust == SecurityAnalyzer.RiskLevel.MEDIUM: trust_label.get_style_context().add_class("warning-color")
            else: trust_label.get_style_context().add_class("error-color")

        # Update critical changes section (step 1)
        source_diff_view = self.builder.get_object('source_diff_view', review_dialog)
        prepare_diff_view = self.builder.get_object('prepare_diff_view', review_dialog)
        package_diff_view = self.builder.get_object('package_diff_view', review_dialog)

        # Populate these from results.critical_changes or similar structured data
        if source_diff_view: source_diff_view.get_buffer().set_text(results.raw_pkgbuild_content) # For now, full content
        if prepare_diff_view: prepare_diff_view.get_buffer().set_text(results.raw_pkgbuild_content) # For now, full content
        if package_diff_view: package_diff_view.get_buffer().set_text(results.raw_pkgbuild_content) # For now, full content
        # TODO: Apply CSS classes for risk heatmap to TextView content by identifying relevant lines

        # Update risk checklist (step 2)
        problems_list_box = self.builder.get_object('risk_checklist_box', review_dialog)
        if problems_list_box:
            while problems_list_box.get_first_child() is not None:
                problems_list_box.remove(problems_list_box.get_first_child())

            for risk_item in results.detected_risks:
                # Dynamically create risk checkboxes or labels
                # For demo, use a simple label:
                label = Gtk.Label(label=f"• {risk_item.description}")
                label.set_halign(Gtk.Align.START)
                label.set_wrap(True)
                if risk_item.level == SecurityAnalyzer.RiskLevel.CRITICAL: label.get_style_context().add_class('error-color')
                elif risk_item.level == SecurityAnalyzer.RiskLevel.HIGH: label.get_style_context().add_class('warning-color')
                problems_list_box.append(label)

        # Update heatmap view
        heatmap_view = self.builder.get_object('heatmap_view', review_dialog)
        if heatmap_view:
            buffer = heatmap_view.get_buffer()
            buffer.set_text(results.raw_pkgbuild_content) # Show full PKGBUILD content
            # Apply tags based on results.heatmap_lines
            for line_num, level, description in results.heatmap_lines:
                start_iter = buffer.get_iter_at_line(line_num - 1)
                end_iter = buffer.get_iter_at_line(line_num)
                tag_name = f"risk-{level.value.lower()}"
                # Ensure tag exists or create it
                if not buffer.get_tag_table().lookup(tag_name):
                    buffer.create_tag(tag_name, background_set=True, background_color="red" if level == SecurityAnalyzer.RiskLevel.CRITICAL else "orange") # Placeholder colors
                buffer.apply_tag_by_name(tag_name, start_iter, end_iter)


        # Ensure action buttons are correctly set for the initial step
        next_button = self.builder.get_object('next_button', review_dialog)
        build_button = self.builder.get_object('build_button', review_dialog)
        previous_button = self.builder.get_object('previous_button', review_dialog)
        if next_button and build_button and previous_button:
            next_button.set_visible(True)
            build_button.set_visible(False)
            previous_button.set_visible(False)

        # Ensure correct step content is visible
        step1_content = self.builder.get_object('step1_content', review_dialog)
        step2_content = self.builder.get_object('step2_content', review_dialog)
        step1_button = self.builder.get_object('step1_button', review_dialog)
        step2_button = self.builder.get_object('step2_button', review_dialog)

        if step1_content and step2_content and step1_button and step2_button:
            step1_content.set_visible(True)
            step2_content.set_visible(False)
            step1_button.set_active(True)
            step2_button.set_active(False)
            step1_button.add_css_class('active-step')
            step2_button.remove_css_class('active-step')


    def _on_pkgbuild_review_step_toggled(self, button: Gtk.ToggleButton):
        """Handles toggling between review steps."""
        # Get widgets from the context of the dialog
        review_dialog = button.get_ancestor(Adw.Dialog)
        if not review_dialog: return

        step1_button = self.builder.get_object('step1_button', review_dialog)
        step2_button = self.builder.get_object('step2_button', review_dialog)
        step1_content = self.builder.get_object('step1_content', review_dialog)
        step2_content = self.builder.get_object('step2_content', review_dialog)
        previous_button = self.builder.get_object('previous_button', review_dialog)
        next_button = self.builder.get_object('next_button', review_dialog)
        build_button = self.builder.get_object('build_button', review_dialog)

        if button.get_name() == 'step1' and button.get_active():
            step2_button.set_active(False)
            step1_content.set_visible(True)
            step2_content.set_visible(False)
            previous_button.set_visible(False)
            next_button.set_visible(True)
            build_button.set_visible(False)
            step1_button.add_css_class('active-step')
            step2_button.remove_css_class('active-step')
        elif button.get_name() == 'step2' and button.get_active():
            step1_button.set_active(False)
            step1_content.set_visible(False)
            step2_content.set_visible(True)
            previous_button.set_visible(True)
            next_button.set_visible(False)
            build_button.set_visible(True)
            step2_button.add_css_class('active-step')
            step1_button.remove_css_class('active-step')

    def _on_pkgbuild_review_next_clicked(self, button: Gtk.Button):
        """Moves to the next step in the PKGBUILD review."""
        review_dialog = button.get_ancestor(Adw.Dialog)
        if not review_dialog: return
        step2_button = self.builder.get_object('step2_button', review_dialog)
        if step2_button and not step2_button.get_active():
            step2_button.set_active(True)

    def _on_pkgbuild_review_previous_clicked(self, button: Gtk.Button):
        """Moves to the previous step in the PKGBUILD review."""
        review_dialog = button.get_ancestor(Adw.Dialog)
        if not review_dialog: return
        step1_button = self.builder.get_object('step1_button', review_dialog)
        if step1_button and not step1_button.get_active():
            step1_button.set_active(True)

    def _on_pkgbuild_review_build_clicked(self, button: Gtk.Button):
        """Initiates the build process from the PKGBUILD review dialog."""
        # This button is only visible on the last step (Step 2: Risk Checklist)
        review_dialog = button.get_ancestor(Adw.Dialog)
        if not review_dialog: return

        pkgbuild_path_label = self.builder.get_object('package_path', review_dialog)
        if not pkgbuild_path_label:
            self.error_handler.show_error_dialog(ErrorContext(
                category=ErrorCategory.UI_ERROR,
                summary="Missing PKGBUILD path",
                details="Could not retrieve PKGBUILD path from dialog UI.",
                suggested_actions=[SuggestedAction.CHECK_LOG]
            ))
            return

        pkgbuild_path = pkgbuild_path_label.get_label().replace("Path: ", "")

        enable_sandbox_check = self.builder.get_object('enable_sandbox_check', review_dialog)
        if enable_sandbox_check and enable_sandbox_check.get_active():
            sandbox_level_combo = self.builder.get_object('sandbox_level_combo', review_dialog)
            sandbox_network_check = self.builder.get_object('sandbox_network_check', review_dialog)
            sandbox_home_check = self.builder.get_object('sandbox_home_check', review_dialog)

            sandbox_level_id = sandbox_level_combo.get_active_id() if sandbox_level_combo else IsolationLevel.MEDIUM.value
            allow_network = sandbox_network_check.get_active() if sandbox_network_check else False
            allow_home = sandbox_home_check.get_active() if sandbox_home_check else False

            self.on_build_package_sandboxed(button, pkgbuild_path, sandbox_level_id, allow_network, allow_home)
        else:
            self.on_build_package(button, pkgbuild_path)

        review_dialog.close()

    def _on_pkgbuild_review_sandbox_toggled(self, checkbutton: Gtk.CheckButton):
        """Handles toggling the sandboxing options in the PKGBUILD review dialog."""
        review_dialog = checkbutton.get_ancestor(Adw.Dialog)
        if not review_dialog: return
        sandbox_options_box = self.builder.get_object('sandbox_options_box', review_dialog)
        if sandbox_options_box:
            sandbox_options_box.set_visible(checkbutton.get_active())


    def on_search_changed(self, entry: Gtk.SearchEntry):
        """Handles changes in the search entry for intelligent assistance."""
        text = entry.get_text().strip()
        # TODO: [ ] Implement intelligent assistant logic here.
        # - Auto-complete for 'paru' commands
        # - Suggest packages
        # - Provide command help for prefixes like '-c'
        # This should be very fast, possibly using a debounce timer.
        print(f"Search text changed: {text}")

    def on_search_activated(self, entry: Gtk.SearchEntry):
        """Handles activation (Enter key) in the search entry."""
        command = entry.get_text().strip()
        if command:
            print(f"Executing search/command: {command}")
            # TODO: [ ] Integrate with TerminalManager to run the command
            # self.terminal_manager.execute_command_async(command)
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.COMMAND_EXECUTION,
                summary=f"Executed command: {command}",
                status=ActionStatus.INFO,
                details={"command": command}
            ))
        entry.set_text("") # Clear search after activation

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

        if dialog:
            # Try to get widgets from the specific dialog's scope
            spinner = self.builder.get_object('processing_spinner', dialog)
            label = self.builder.get_object('processing_label', dialog)
            progress_bar = self.builder.get_object('processing_progress', dialog)
            cancel_button = self.builder.get_object('cancel_button', dialog)
            details_button = self.builder.get_object('details_button', dialog)
            # If the dialog has its own processing screen, make it visible
            processing_screen_box = self.builder.get_object('processing_screen', dialog)
            if processing_screen_box: processing_screen_box.set_visible(True)
        else:
            # Otherwise, use the main application processing screen
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

        if cancel_button and not hasattr(cancel_button, '_connected_processing'): # Avoid duplicate connections
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
            processing_screen_box = self.builder.get_object('processing_screen', dialog)
            if processing_screen_box: processing_screen_box.set_visible(False)
        else:
            spinner = self.builder.get_object('processing_spinner')
            if spinner: spinner.stop()
            if self.main_stack.get_visible_child_name() == "processing":
                # Determine what screen to go back to (e.g., content, or previous)
                self.main_stack.set_visible_child_name("content") # Default to content


    def _on_processing_cancel_clicked(self, button: Gtk.Button):
        """Handles cancellation of a processing task."""
        print("Processing cancelled!")
        # TODO: [ ] Implement actual cancellation logic for running futures/subprocesses
        self._hide_processing_screen(dialog=button.get_ancestor(Adw.Dialog))
        # TODO: Record action in history_manager

    def _on_processing_details_clicked(self, button: Gtk.Button):
        """Shows detailed logs/progress for a processing task."""
        print("Showing processing details (log_textview)...")
        # TODO: [ ] Implement showing the log_textview content for current task
        # This would typically involve making the log_textview visible and populating its buffer.

    # --- Helper methods for metadata extraction (should be moved to FileUtils.py) ---
    # These are kept here for now as FileUtils is a pending refactor.

    def _extract_pkgbuild_info(self, path: str) -> Tuple[str, str, str]:
        """Safely extracts information from PKGBUILD without execution."""
        pkgname = "unknown"
        pkgver = "unknown"
        pkgrel = "1"

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            name_match = re.search(r'^\s*pkgname\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content, re.MULTILINE)
            ver_match = re.search(r'^\s*pkgver\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content, re.MULTILINE)
            rel_match = re.search(r'^\s*pkgrel\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content, re.MULTILINE)

            if name_match: pkgname = name_match.group(1)
            if ver_match: pkgver = ver_match.group(1)
            if rel_match: pkgrel = rel_match.group(1)

        except Exception as e:
            logger.error(f"Error reading PKGBUILD {path} for info extraction: {e}")
            # Do not use ErrorHandler here to avoid infinite recursion if _extract_pkgbuild_info is used by it
        return (pkgname, pkgver, pkgrel)

    def _get_aur_votes(self, pkgname: str) -> int:
        """Gets votes from AUR to determine trust level (async operation)."""
        logger.info(f"Fetching AUR votes for {pkgname}...")
        try:
            # TODO: Add cache mechanism for AUR votes (if not handled by UpstreamChecker already)
            # This call should ideally be part of a Future that runs in self.thread_pool_executor
            result = subprocess.run(
                ['paru', '-Si', pkgname],
                capture_output=True,
                text=True,
                timeout=10, # Increased timeout for network call
                check=False
            )
            if result.returncode == 0:
                votes_match = re.search(r'Votes\s*:\s*(\d+)', result.stdout)
                return int(votes_match.group(1)) if votes_match else 0
            else:
                logger.warning(f"Paru command failed for {pkgname} (AUR votes): {result.stderr.strip()}")
                return 0
        except FileNotFoundError:
            logger.error("Error: 'paru' command not found. Is paru installed?")
            return 0
        except subprocess.TimeoutExpired:
            logger.warning(f"Paru command timed out for {pkgname} (AUR votes).")
            return 0
        except Exception as e:
            logger.error(f"Error getting AUR votes for {pkgname}: {e}")
            return 0

    def _get_trust_level(self, votes: int) -> TrustLevel:
        """Determines trust level based on votes."""
        # TODO: Integrate with PreferencesManager for configurable thresholds
        if votes >= 50:
            return TrustLevel.HIGH
        elif votes >= 10:
            return TrustLevel.MEDIUM
        return TrustLevel.LOW

    def _get_pkg_name_from_zst(self, filepath: str) -> str:
        """Extracts package name from .zst file."""
        try:
            result = subprocess.run(
                ['tar', '--zstd', '-tvf', filepath], # Inspect .zst file
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if '.PKGINFO' in line:
                        return os.path.basename(filepath).split('-')[0]
                return os.path.basename(filepath).replace('.pkg.tar.zst', '')
            else:
                logger.warning(f"Tar command failed for {filepath} (pkg name): {result.stderr.strip()}")
                return os.path.basename(filepath).replace('.pkg.tar.zst', '')
        except FileNotFoundError:
            logger.error("Error: 'tar' command not found.")
            return os.path.basename(filepath).replace('.pkg.tar.zst', '')
        except subprocess.TimeoutExpired:
            logger.warning(f"Tar command timed out for {filepath} (pkg name).")
            return os.path.basename(filepath).replace('.pkg.tar.zst', '')
        except Exception as e:
            logger.error(f"Error extracting package name from {filepath}: {e}")
            return os.path.basename(filepath).replace('.pkg.tar.zst', '')

    def _get_pkg_version(self, filepath: str) -> str:
        """Extracts package version from .zst file."""
        try:
            result = subprocess.run(
                ['tar', '--zstd', '-xOf', filepath, '.PKGINFO'], # Extract .PKGINFO content
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
            if result.returncode == 0:
                pkgver_match = re.search(r'pkgver\s*=\s*(\S+)', result.stdout)
                pkgrel_match = re.search(r'pkgrel\s*=\s*(\S+)', result.stdout)

                pkgver = pkgver_match.group(1) if pkgver_match else "unknown"
                pkgrel = pkgrel_match.group(1) if pkgrel_match else "1"

                return f"{pkgver}-{pkgrel}"
            else:
                logger.warning(f"Tar command (PKGINFO) failed for {filepath} (pkg version): {result.stderr.strip()}")
                return "unknown"
        except FileNotFoundError:
            logger.error("Error: 'tar' command not found.")
            return "unknown"
        except subprocess.TimeoutExpired:
            logger.warning(f"Tar command (PKGINFO) timed out for {filepath} (pkg version).")
            return "unknown"
        except Exception as e:
            logger.error(f"Error extracting package version from {filepath}: {e}")
            return "unknown"

    def _check_signature(self, filepath: str) -> str:
        """Checks package signature status."""
        try:
            sig_path = filepath + '.sig'
            if not os.path.exists(sig_path):
                return "Not signed"

            # TODO: [~] Implement actual signature verification via `gpg` or `pacman-key --verify`
            # This should be an asynchronous operation in a thread pool.
            logger.info(f"Performing signature verification for {filepath} (placeholder)...")
            # Simulate a check
            import time
            time.sleep(0.5)
            # Example for success/failure
            if "badpackage" in os.path.basename(filepath): # Simulate a bad signature
                raise Exception("Simulated bad signature")
            return "Verified"
        except Exception as e:
            logger.error(f"Error checking signature for {filepath}: {e}")
            return "Verification failed"

    def _get_patch_description(self, filepath: str) -> str:
        """Gets patch description."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if first_line.startswith('#'):
                    return first_line[1:].strip()
                return "Generic patch file"
        except Exception as e:
            logger.error(f"Error reading patch description from {filepath}: {e}")
            return "Unknown patch"

    # --- Action handlers ---
    def _run_shell_command_async(self, command: List[str], cwd: str, description: str,
                                 action_type: ActionType, related_pkg: Optional[str] = None,
                                 is_undoable: bool = False,
                                 callback: Optional[Callable[[bool, str, str], None]] = None):
        """
        [~] Asynchronous logic for real-time terminal display:
        Executes a shell command in a separate thread/process and updates terminal.
        """
        logger.info(f"Executing '{description}' asynchronously: {' '.join(command)}")
        self._show_processing_screen(f"{description}...", dialog=None) # Use main processing screen

        # TODO: [ ] Integrate with TerminalManager for real-time output streaming
        # The _execute_command_worker currently collects all output then returns.
        # For real-time, it needs to stream lines via GLib.idle_add.

        future = self.thread_pool_executor.submit(self._execute_command_worker, command, cwd)
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


    def _execute_command_worker(self, command: List[str], cwd: str) -> Tuple[int, str, str]:
        """
        Worker function to execute a shell command (runs in separate thread/process).
        Currently collects all output before returning.
        """
        # TODO: [ ] Refactor this worker to stream output via output_callback to TerminalManager
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1, # Line-buffered output
                universal_newlines=True # Ensure correct encoding
            )

            stdout_lines = []
            stderr_lines = []

            # Simulate real-time output reading
            for line in process.stdout:
                stdout_lines.append(line)
                # GLib.idle_add(lambda l=line: self.terminal_manager.append_stdout(l.strip())) # Example streaming

            for line in process.stderr:
                stderr_lines.append(line)
                # GLib.idle_add(lambda l=line: self.terminal_manager.append_stderr(l.strip())) # Example streaming

            process.wait()
            return process.returncode, "".join(stdout_lines), "".join(stderr_lines)

        except FileNotFoundError:
            return 127, "", f"Error: Command '{command[0]}' not found."
        except Exception as e:
            return 1, "", f"Error executing command: {traceback.format_exc()}"


    def _on_command_completed(self, future: concurrent.futures.Future, description: str,
                             action_type: ActionType, related_pkg: Optional[str],
                             is_undoable: bool, original_command: List[str], cwd: str,
                             callback: Optional[Callable[[bool, str, str], None]]):
        """Callback for shell command completion (on UI thread)."""
        self._hide_processing_screen()
        status = ActionStatus.FAILED
        try:
            return_code, stdout, stderr = future.result()

            if return_code == 0:
                logger.info(f"'{description}' completed successfully. Output: {stdout}")
                status = ActionStatus.SUCCESS
                if callback: callback(True, stdout, stderr)
            else:
                logger.error(f"'{description}' failed with exit code {return_code}. STDERR: {stderr.strip()}")
                status = ActionStatus.FAILED

                error_ctx = ErrorContext(
                    category=ErrorCategory.COMMAND_EXECUTION,
                    summary=f"Command '{description}' Failed",
                    details=f"The command exited with code {return_code}. See output for details.",
                    pkgname=related_pkg,
                    command_executed=" ".join(original_command),
                    working_directory=cwd,
                    stdout=stdout,
                    stderr=stderr,
                    suggested_actions=[SuggestedAction.RETRY, SuggestedAction.CHECK_LOG]
                )
                self.error_handler.show_error_dialog(error_ctx)
                if callback: callback(False, stdout, stderr)

        except concurrent.futures.CancelledError:
            logger.warning(f"'{description}' was cancelled.")
            status = ActionStatus.CANCELED
            # Show specific error or info for cancellation
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
                details={"command": " ".join(original_command), "cwd": cwd, "stdout": stdout, "stderr": stderr},
                is_undoable=is_undoable
            ))


    def on_build_package(self, button: Gtk.Button, pkgbuild_path: str):
        """Starts the package building process without sandboxing."""
        pkgname, _, _ = self._extract_pkgbuild_info(pkgbuild_path)
        build_dir = os.path.dirname(pkgbuild_path)
        command = ['paru', '-U', '--noconfirm'] # Example: build and install
        self._run_shell_command_async(command, build_dir, f"Build PKGBUILD: {pkgname}", ActionType.PKGBUILD_BUILD, pkgname, is_undoable=True)


    def on_build_package_sandboxed(self, button: Gtk.Button, pkgbuild_path: str,
                                   sandbox_level_id: str, allow_network: bool, allow_home: bool):
        """
        [ ] Asynchronous sandboxed compilation:
        Starts the package building process with sandboxing.
        """
        pkgname, _, _ = self._extract_pkgbuild_info(pkgbuild_path)
        build_dir = os.path.dirname(pkgbuild_path)

        sandbox_options = SandboxOptions(
            isolation_level=IsolationLevel(sandbox_level_id),
            allow_network=allow_network,
            allow_home=allow_home,
            working_dir=build_dir,
            bind_paths=[(pkgbuild_path, os.path.join(build_dir, "PKGBUILD"), "--bind")] # Ensure PKGBUILD is accessible
        )
        command_to_sandbox = ['paru', '-U', '--noconfirm'] # Actual command inside sandbox

        self._show_processing_screen(f"Sandboxed build for {pkgname}...", dialog=button.get_ancestor(Adw.Dialog))
        future = self.process_pool_executor.submit(self.sandbox_manager.run_sandboxed_command, command_to_sandbox, sandbox_options)
        future.add_done_callback(
            lambda f: GLib.idle_add(self._on_sandboxed_command_completed, f, f"Sandboxed Build PKGBUILD: {pkgname}", ActionType.PKGBUILD_BUILD, pkgname, True, command_to_sandbox, build_dir)
        )
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.PKGBUILD_BUILD,
            summary=f"Initiated sandboxed build for {pkgname}",
            status=ActionStatus.INFO,
            related_pkg=pkgname,
            details={"command": " ".join(command_to_sandbox), "cwd": build_dir, "sandbox_level": sandbox_level_id}
        ))


    def _on_sandboxed_command_completed(self, future: concurrent.futures.Future, description: str,
                                        action_type: ActionType, related_pkg: Optional[str],
                                        is_undoable: bool, original_command: List[str], cwd: str):
        """Callback for sandboxed command completion (on UI thread)."""
        self._hide_processing_screen()
        status = ActionStatus.FAILED
        try:
            return_code, stdout, stderr = future.result()
            if return_code == 0:
                logger.info(f"'{description}' completed successfully. Output: {stdout}")
                status = ActionStatus.SUCCESS
            else:
                logger.error(f"'{description}' failed with exit code {return_code}. STDERR: {stderr.strip()}")
                status = ActionStatus.FAILED

                error_ctx = ErrorContext(
                    category=ErrorCategory.COMMAND_EXECUTION,
                    summary=f"Sandboxed Command '{description}' Failed",
                    details=f"The sandboxed command exited with code {return_code}. See output for details. Review sandbox logs for security events.",
                    pkgname=related_pkg,
                    command_executed=" ".join(original_command),
                    working_directory=cwd,
                    stdout=stdout,
                    stderr=stderr,
                    additional_context=[
                        ErrorDetail(f"Sandbox Activity Log (heuristic): {log}" , level="warning")
                        for log in self.sandbox_manager.get_sandbox_activity_log(stdout + stderr)
                    ],
                    suggested_actions=[SuggestedAction.RETRY, SuggestedAction.CHECK_LOG]
                )
                self.error_handler.show_error_dialog(error_ctx)
        except concurrent.futures.CancelledError:
            logger.warning(f"'{description}' was cancelled.")
            status = ActionStatus.CANCELED
        except Exception as e:
            logger.critical(f"Internal error processing sandboxed command completion for '{description}': {e}")
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
                details={"command": " ".join(original_command), "cwd": cwd, "stdout": stdout, "stderr": stderr, "sandboxed": True},
                is_undoable=is_undoable
            ))


    def on_edit_pkgbuild(self, button: Gtk.Button, pkgbuild_path: str):
        """Opens PKGBUILD in default editor."""
        try:
            # TODO: Get default editor from PreferencesManager
            editor = "gedit" # Example default
            subprocess.Popen([editor, pkgbuild_path])
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Opened PKGBUILD for editing: {os.path.basename(pkgbuild_path)}",
                status=ActionStatus.INFO,
                related_pkg=self._extract_pkgbuild_info(pkgbuild_path)[0],
                details={"path": pkgbuild_path, "editor": editor}
            ))
        except FileNotFoundError:
            error_ctx = ErrorContext(
                category=ErrorCategory.SYSTEM,
                summary="Editor Not Found",
                details=f"Could not find default editor '{editor}'. Please configure it in preferences.",
                file_path=pkgbuild_path,
                command_executed=editor,
                suggested_actions=[SuggestedAction.CONSULT_DOCS]
            )
            self.error_handler.show_error_dialog(error_ctx)
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Failed to open PKGBUILD for editing: {os.path.basename(pkgbuild_path)}",
                status=ActionStatus.FAILED,
                related_pkg=self._extract_pkgbuild_info(pkgbuild_path)[0],
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
                related_pkg=self._extract_pkgbuild_info(pkgbuild_path)[0],
                details={"path": pkgbuild_path, "error": str(e)}
            ))


    def on_view_dependencies(self, button: Gtk.Button, pkgbuild_path: str):
        """Views package dependencies (for PKGBUILD)."""
        pkgname, _, _ = self._extract_pkgbuild_info(pkgbuild_path)
        if pkgname != "unknown":
            command = ['paru', '-Si', pkgname]
            self._run_shell_command_async(command, os.path.dirname(pkgbuild_path), f"View Dependencies for {pkgname}",
                ActionType.UI_INTERACTION, pkgname, is_undoable=False,
                callback=lambda success, stdout, stderr: self._display_dependencies_info(success, stdout, stderr, pkgname)
            )
        else:
            self.error_handler.show_error_dialog(ErrorContext(
                category=ErrorCategory.PKGBUILD_ANALYSIS,
                summary="Cannot view dependencies",
                details="Could not extract package name from PKGBUILD. Ensure 'pkgname' is defined.",
                file_path=pkgbuild_path,
                suggested_actions=[SuggestedAction.CHECK_LOG]
            ))
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
            dependencies = deps_match.group(1).strip() if deps_match else "None"
            make_dependencies = make_deps_match.group(1).strip() if make_deps_match else "None"
            self._show_info_dialog(f"Dependencies for {pkgname}", f"Dependencies: {dependencies}\nMake Dependencies: {make_dependencies}")
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
        pkgname, _, _ = self._extract_pkgbuild_info(pkgbuild_path)
        build_dir = os.path.dirname(pkgbuild_path)
        command = ['paru', '-G', os.path.basename(build_dir)] # `paru -G` downloads PKGBUILD and sources
        self._run_shell_command_async(command, build_dir, f"Download Sources for {pkgname}", ActionType.PKGBUILD_BUILD, pkgname, is_undoable=False) # Not easily undoable


    def on_install_package(self, button: Gtk.Button, package_path: str):
        """Installs the selected package without sandboxing."""
        pkgname = self._get_pkg_name_from_zst(package_path)
        install_dir = os.path.dirname(package_path)
        command = ['sudo', 'pacman', '-U', '--noconfirm', package_path]
        # Sudo requires password. For graphical integration, use pkexec or handle password via Polkit agent.
        # Direct `sudo` in subprocess often requires user to type password in terminal where app was launched.
        self._show_info_dialog("Installation Initiated", f"Installing {os.path.basename(package_path)}. This may require your `sudo` password.")
        self._run_shell_command_async(command, install_dir, f"Install Package: {pkgname}", ActionType.PACKAGE_INSTALL, pkgname, is_undoable=True)


    def on_install_package_sandboxed(self, button: Gtk.Button, package_path: str,
                                     sandbox_level_id: str, allow_network: bool, allow_home: bool):
        """
        [ ] Asynchronous sandboxed installation:
        Installs the selected package with sandboxing.
        """
        pkgname = self._get_pkg_name_from_zst(package_path)
        install_dir = os.path.dirname(package_path)

        sandbox_options = SandboxOptions(
            isolation_level=IsolationLevel(sandbox_level_id),
            allow_network=allow_network,
            allow_home=allow_home,
            working_dir=install_dir,
            bind_paths=[(package_path, package_path, "--bind")] # Ensure package file is accessible
        )
        # Note: pacman -U requires root privileges, even in sandbox.
        # This means bwrap itself might need to be run as root, or pacman configured
        # to use a non-root mechanism. This is a complex security model.
        command_to_sandbox = ['sudo', 'pacman', '-U', '--noconfirm', package_path]

        self._show_processing_screen(f"Sandboxed install for {pkgname}...", dialog=button.get_ancestor(Adw.Dialog))
        future = self.process_pool_executor.submit(self.sandbox_manager.run_sandboxed_command, command_to_sandbox, sandbox_options)
        future.add_done_callback(
            lambda f: GLib.idle_add(self._on_sandboxed_command_completed, f, f"Sandboxed Install Package: {pkgname}", ActionType.PACKAGE_INSTALL, pkgname, True, command_to_sandbox, install_dir)
        )


    def on_view_package_info(self, button: Gtk.Button, package_path: str):
        """Displays detailed information about the .zst package."""
        pkgname = self._get_pkg_name_from_zst(package_path)
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
                suggested_actions=[SuggestedAction.CHECK_LOG]
            )
            self.error_handler.show_error_dialog(error_ctx)


    def on_verify_signature(self, button: Gtk.Button, package_path: str):
        """Verifies package signature."""
        pkgname = self._get_pkg_name_from_zst(package_path)
        sig_path = package_path + '.sig'
        if not os.path.exists(sig_path):
            self.error_handler.show_error_dialog(ErrorContext(
                category=ErrorCategory.FILE_OPERATION,
                summary="Signature File Missing",
                details=f"No .sig file found for package '{pkgname}' at '{sig_path}'. Cannot verify signature.",
                file_path=package_path,
                suggested_actions=[SuggestedAction.CHECK_LOG]
            ))
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
                command_executed=f"gpg --verify ...",
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
        command = ['patch', '-p1', '-i', os.path.basename(patch_path)] # Example command, requires context
        self._show_info_dialog("Apply Patch Initiated", f"Applying '{patch_name}'. You may need to manually specify the target directory if this is not a build folder.")
        self._run_shell_command_async(command, patch_dir, f"Apply Patch: {patch_name}", ActionType.PATCH_APPLY, patch_name, is_undoable=False) # Patches are hard to undo


    def on_apply_patch_sandboxed(self, button: Gtk.Button, patch_path: str,
                                 sandbox_level_id: str, allow_network: bool, allow_home: bool):
        """
        [ ] Asynchronous sandboxed patch application:
        Applies the selected patch with sandboxing.
        """
        patch_name = os.path.basename(patch_path)
        patch_dir = os.path.dirname(patch_path)

        sandbox_options = SandboxOptions(
            isolation_level=IsolationLevel(sandbox_level_id),
            allow_network=allow_network,
            allow_home=allow_home,
            working_dir=patch_dir,
            bind_paths=[(patch_path, os.path.join(patch_dir, patch_name), "--bind")] # Ensure patch file is accessible
        )
        command_to_sandbox = ['patch', '-p1', '-i', patch_name]

        self._show_processing_screen(f"Sandboxed patch apply for {patch_name}...", dialog=button.get_ancestor(Adw.Dialog))
        future = self.process_pool_executor.submit(self.sandbox_manager.run_sandboxed_command, command_to_sandbox, sandbox_options)
        future.add_done_callback(
            lambda f: GLib.idle_add(self._on_sandboxed_command_completed, f, f"Sandboxed Apply Patch: {patch_name}", ActionType.PATCH_APPLY, patch_name, False, command_to_sandbox, patch_dir)
        )


    def on_view_diff(self, button: Gtk.Button, patch_path: str):
        """Views patch diff."""
        patch_name = os.path.basename(patch_path)
        try:
            with open(patch_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self._show_info_dialog(f"Diff for {patch_name}", content, "text-x-patch-symbolic")
                self.history_manager.add_action(HistoryEntry(
                    id=None, timestamp=datetime.utcnow(),
                    action_type=ActionType.UI_INTERACTION,
                    summary=f"Viewed diff for {patch_name}",
                    status=ActionStatus.INFO,
                    related_pkg=patch_name,
                    details={"path": patch_path}
                ))
        except Exception as e:
            error_ctx = ErrorContext(
                category=ErrorCategory.FILE_OPERATION,
                summary=f"Could not read patch file '{patch_name}'",
                details=f"Failed to read file for diff view: {e}",
                file_path=patch_path,
                traceback=traceback.format_exc(),
                original_exception=e
            )
            self.error_handler.show_error_dialog(error_ctx)
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Failed to view diff for {patch_name}",
                status=ActionStatus.FAILED,
                related_pkg=patch_name,
                details={"path": patch_path, "error": str(e)}
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

    def _start_check_all_upstream_updates_async(self):
        """
        [ ] Asynchronous UpstreamChecker integration:
        Initiates checking for all upstream updates in the current directory.
        """
        self._show_processing_screen("Checking for upstream updates...", dialog=None) # Main window processing

        # For a full implementation, you would:
        # 1. Get a list of all PKGBUILD paths currently known or in configured AUR directories.
        # 2. Submit self.upstream_checker.check_for_updates for EACH PKGBUILD to self.thread_pool_executor.
        # 3. Collect results.

        # For demo, simulate a check for a dummy PKGBUILD
        dummy_pkgbuild_path = os.path.join(self.current_path, "PKGBUILD")
        if not os.path.exists(dummy_pkgbuild_path):
            with open(dummy_pkgbuild_path, "w") as f:
                f.write("""pkgname=testpackage\npkgver=1.0.0\nsource=("https://github.com/dummy/testrepo/archive/v1.0.0.tar.gz")\nurl="https://github.com/dummy/testrepo" """)

        future = self.thread_pool_executor.submit(self.upstream_checker.check_for_updates, dummy_pkgbuild_path)
        future.add_done_callback(
            lambda f: GLib.idle_add(self._on_upstream_check_completed, f, dummy_pkgbuild_path)
        )
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.UPSTREAM_CHECK,
            summary="Initiated upstream check",
            status=ActionStatus.INFO,
            details={"path": self.current_path}
        ))


    def _on_upstream_check_completed(self, future: concurrent.futures.Future, pkgbuild_path: str):
        """Callback for upstream check completion (on UI thread)."""
        self._hide_processing_screen()
        status = ActionStatus.FAILED
        try:
            update_info = future.result()
            upstream_update_cards_flowbox = self.builder.get_object('upstream_update_cards')
            if not upstream_update_cards_flowbox: return # Should not happen if UI is loaded

            while upstream_update_cards_flowbox.get_first_child() is not None:
                upstream_update_cards_flowbox.remove(upstream_update_cards_flowbox.get_first_child())

            if update_info:
                logger.info(f"Upstream update found: {update_info.version}")
                status = ActionStatus.SUCCESS
                # Create and populate an UpstreamUpdateCard (using its template)
                # Adw.Application.get_default().get_builder().get_object() is another way
                from .ui.screens.upstream_update import UpstreamUpdateCard
                update_card = UpstreamUpdateCard() # The template is already loaded by main builder

                pkgname, pkgver, _ = self._extract_pkgbuild_info(pkgbuild_path)
                update_card.update_card_data(pkgname, pkgver, {
                    "version": update_info.version,
                    "release_date": update_info.release_date,
                    "changelog_url": update_info.changelog_url,
                    "cve_fix_info": update_info.cve_fix_info
                })
                # Connect the card's buttons to window's handlers or let card handle internally
                # (Card handlers are already defined in UpstreamUpdateCard class, so just ensure they work)

                flowbox_child = Gtk.FlowBoxChild()
                flowbox_child.set_child(update_card)
                upstream_update_cards_flowbox.append(flowbox_child)
            else:
                logger.info("No upstream updates found.")
                status = ActionStatus.INFO
                empty_state_box = self.builder.get_object('empty_state_box').unparent()
                empty_state_box.set_visible(True)
                self.builder.get_object('empty_title_label', empty_state_box).set_label("No Upstream Updates Found")
                self.builder.get_object('empty_description_label', empty_state_box).set_label("All packages appear to be up-to-date or no upstream source was detected.")
                self.builder.get_object('empty_options_box', empty_state_box).set_visible(False)

                flowbox_child = Gtk.FlowBoxChild()
                flowbox_child.set_child(empty_state_box)
                upstream_update_cards_flowbox.append(flowbox_child)

        except Exception as e:
            error_ctx = ErrorContext(
                category=ErrorCategory.NETWORK,
                summary="Upstream Check Failed",
                details=f"Failed to check for upstream updates: {e}",
                file_path=pkgbuild_path,
                traceback=traceback.format_exc(),
                original_exception=e
            )
            self.error_handler.show_error_dialog(error_ctx)
            status = ActionStatus.FAILED
        finally:
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UPSTREAM_CHECK,
                summary="Completed upstream check",
                status=status,
                details={"path": pkgbuild_path, "update_found": bool(update_info)}
            ))
