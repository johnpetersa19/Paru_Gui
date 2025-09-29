import os
import concurrent.futures
from typing import Optional, List, Callable
from gi.repository import Gtk, GLib
from datetime import datetime

from ...file_utils import FileUtils, FileItem
from ...history_manager import HistoryManager, ActionType, ActionStatus, HistoryEntry
from ...error_handler import ErrorHandler, ErrorCategory, ErrorReport # Mantendo a importação correta


class FileOperationsManager: # <--- CLASSE RENOMEADA AQUI
    """Handles file and directory operations, scanning and selection."""

    def __init__(self, window, builder, preferences_manager, history_manager,
                 file_utils, error_handler, thread_pool_executor):
        self.window = window
        self.builder = builder
        self.preferences_manager = preferences_manager
        self.history_manager = history_manager
        self.file_utils = file_utils
        self.error_handler = error_handler
        self.thread_pool_executor = thread_pool_executor

    def on_select_file_clicked(self, *args):
        """Opens dialog to select a specific file."""
        dialog = Gtk.FileChooserNative(
            title="Select PKGBUILD File",
            parent=self.window,
            action=Gtk.FileChooserAction.OPEN
        )

        self._add_file_filters(dialog)

        dialog.connect("response", self._on_single_file_response)
        dialog.show()

        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.UI_INTERACTION,
            summary="Opened file selection dialog",
            status=ActionStatus.INFO
        ))

    def on_select_folder_clicked(self, *args):
        """Opens dialog to select folder with smart file visualization."""
        dialog = Gtk.FileChooserNative(
            title="Select Folder",
            parent=self.window,
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

    def _add_file_filters(self, dialog):
        """Adds file type filters to the file chooser dialog."""
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

    def _on_single_file_response(self, dialog: Gtk.FileChooserNative, response: Gtk.ResponseType):
        """Processes selection of a single file."""
        if response == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_file().get_path()
            if file_path:
                self.window.current_path = os.path.dirname(file_path)
                self.window.ui_manager.show_content_view()
                self.start_scan_compatible_files_async(
                    self.window.current_path, initial_selection_path=file_path
                )
                self.preferences_manager.add_recent_directory(self.window.current_path)
        dialog.destroy()

    def _on_folder_selection_response(self, dialog: Gtk.FileChooserNative, response: Gtk.ResponseType):
        """Processes folder selection from the native dialog."""
        if response == Gtk.ResponseType.ACCEPT:
            folder_path = dialog.get_file().get_path()
            if folder_path:
                self.window.current_path = folder_path
                self.window.ui_manager.show_content_view()
                self.start_scan_compatible_files_async(self.window.current_path)
                self.preferences_manager.add_recent_directory(self.window.current_path)
        dialog.destroy()

    def start_scan_compatible_files_async(self, folder_path: str, initial_selection_path: Optional[str] = None):
        """Starts scanning compatible files in a separate thread."""
        self.window.ui_manager.show_processing_screen(f"Scanning '{os.path.basename(folder_path)}'...")

        future = self.thread_pool_executor.submit(
            self.file_utils.scan_compatible_files_worker, folder_path
        )
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

    def _on_scan_completed(self, future: concurrent.futures.Future, folder_path: str,
                          initial_selection_path: Optional[str] = None):
        """Callback executed on the UI thread when file scan is complete."""
        try:
            file_items = future.result()

            if hasattr(self.window, 'content_view_manager'):
                self.window.content_view_manager.update_content_view(
                    file_items, folder_path, initial_selection_path
                )

            self.window.ui_manager.hide_processing_screen()

            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Completed file scan for: {os.path.basename(folder_path)}",
                status=ActionStatus.SUCCESS,
                details={"path": folder_path, "files_found": len(file_items)}
            ))

        except Exception as e:
            self.error_handler.handle_error(e, context="File Scan Failed", user_action=f"Scanning folder: {folder_path}")

            self.window.ui_manager.hide_processing_screen()

            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Failed file scan for: {os.path.basename(folder_path)}",
                status=ActionStatus.FAILED,
                details={"path": folder_path, "error": str(e)}
            ))

    def on_recent_dir_clicked(self, button: Gtk.Button, path: str):
        """Callback for clicking a recent directory button."""
        self.window.current_path = path
        self.window.ui_manager.show_content_view()
        self.start_scan_compatible_files_async(path)

        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.UI_INTERACTION,
            summary=f"Opened recent directory: {os.path.basename(path)}",
            status=ActionStatus.INFO,
            details={"path": path}
        ))
        self.preferences_manager.add_recent_directory(path)

    def on_up_button_clicked(self, button: Gtk.Button):
        """Navigates up one level in the directory structure."""
        parent_path = os.path.dirname(self.window.current_path)
        if parent_path != self.window.current_path:
            self.window.current_path = parent_path
            self.start_scan_compatible_files_async(self.window.current_path)

            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Navigated up to: {os.path.basename(self.window.current_path)}",
                status=ActionStatus.INFO,
                details={"path": self.window.current_path}
            ))
        else:
            self.window.ui_manager.show_welcome_screen()

            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary="Navigated to welcome screen (from root)",
                status=ActionStatus.INFO
            ))
