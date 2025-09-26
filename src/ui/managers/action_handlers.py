import os
import shlex
import subprocess
import tempfile
import shutil
from typing import Optional, List, Dict, Any, Callable, Tuple
from gi.repository import Gtk, GLib, Gio
from datetime import datetime
from pathlib import Path
from enum import Enum


class ActionResult(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    IN_PROGRESS = "in_progress"


class BuildMode(Enum):
    STANDARD = "standard"
    SANDBOXED = "sandboxed"
    CLEAN = "clean"
    FORCE = "force"


class ActionHandlers:

    def __init__(self, window=None):
        self.window = window
        self.builder = None
        self.preferences_manager = None
        self.history_manager = None
        self.terminal_manager = None
        self.sandbox_manager = None
        self.security_analyzer = None
        self.file_utils = None
        self.error_handler = None

        self._handlers: Dict[str, Callable] = {}
        self._running_processes: Dict[str, subprocess.Popen] = {}
        self._temp_dirs: List[str] = []

        self._initialize_handlers()

    def __del__(self):
        self.cleanup_resources()

    def set_dependencies(self, **dependencies):
        for key, value in dependencies.items():
            setattr(self, key, value)

    def cleanup_resources(self):
        for process in self._running_processes.values():
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                try:
                    process.kill()
                except:
                    pass

        for temp_dir in self._temp_dirs:
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            except:
                pass

        self._running_processes.clear()
        self._temp_dirs.clear()

    def _initialize_handlers(self):
        self._handlers = {
            'refresh': self._handle_refresh,
            'back': self._handle_back,
            'search': self._handle_search,
            'build': self._handle_build,
            'install': self._handle_install,
            'uninstall': self._handle_uninstall,
            'update': self._handle_update,
            'edit_pkgbuild': self._handle_edit_pkgbuild,
            'view_files': self._handle_view_files,
            'view_dependencies': self._handle_view_dependencies,
            'download_sources': self._handle_download_sources,
            'clean_build': self._handle_clean_build,
            'validate_checksums': self._handle_validate_checksums,
            'show_package_info': self._handle_show_package_info,
            'open_terminal': self._handle_open_terminal,
            'open_file_manager': self._handle_open_file_manager,
            'copy_to_clipboard': self._handle_copy_to_clipboard,
            'export_package_list': self._handle_export_package_list,
            'import_package_list': self._handle_import_package_list
        }

    def register_handler(self, action_name: str, handler_func: Callable):
        self._handlers[action_name] = handler_func

    def handle_action(self, action_name: str, *args, **kwargs) -> ActionResult:
        try:
            if action_name in self._handlers:
                result = self._handlers[action_name](*args, **kwargs)
                return result if isinstance(result, ActionResult) else ActionResult.SUCCESS
            else:
                return self._handle_unknown_action(action_name, *args, **kwargs)
        except Exception as e:
            self._log_error(f"Action {action_name} failed: {e}")
            return ActionResult.FAILURE

    def get_available_actions(self) -> List[str]:
        return list(self._handlers.keys())

    def is_action_available(self, action_name: str) -> bool:
        return action_name in self._handlers

    def _handle_refresh(self, *args, **kwargs) -> ActionResult:
        try:
            if self.window and hasattr(self.window, 'refresh_current_view'):
                self.window.refresh_current_view()
            return ActionResult.SUCCESS
        except Exception as e:
            self._log_error(f"Refresh failed: {e}")
            return ActionResult.FAILURE

    def _handle_back(self, *args, **kwargs) -> ActionResult:
        try:
            if self.window and hasattr(self.window, 'navigate_back'):
                self.window.navigate_back()
            return ActionResult.SUCCESS
        except Exception as e:
            self._log_error(f"Back navigation failed: {e}")
            return ActionResult.FAILURE

    def _handle_search(self, query: str = "", search_type: str = "packages", **kwargs) -> ActionResult:
        if not query.strip():
            return ActionResult.CANCELLED

        try:
            search_command = self._build_search_command(query, search_type)
            if self.terminal_manager:
                success = self.terminal_manager.run_command_async(
                    search_command,
                    title=f"Search: {query}",
                    callback=self._on_search_completed
                )
                return ActionResult.IN_PROGRESS if success else ActionResult.FAILURE
            return ActionResult.FAILURE
        except Exception as e:
            self._log_error(f"Search failed: {e}")
            return ActionResult.FAILURE

    def _handle_build(self, pkgbuild_path: str = None, build_mode: BuildMode = BuildMode.STANDARD, **kwargs) -> ActionResult:
        if not pkgbuild_path or not os.path.exists(pkgbuild_path):
            return ActionResult.FAILURE

        try:
            if self.security_analyzer:
                security_result = self.security_analyzer.analyze_pkgbuild(pkgbuild_path)
                if not self._confirm_security_risk(security_result):
                    return ActionResult.CANCELLED

            work_dir = os.path.dirname(pkgbuild_path)

            if self.preferences_manager:
                use_sandbox = self.preferences_manager.get_preference("use_sandbox", True)
                clean_build = self.preferences_manager.get_preference("clean_build", False)
            else:
                use_sandbox = build_mode == BuildMode.SANDBOXED
                clean_build = build_mode == BuildMode.CLEAN

            if clean_build:
                self._clean_build_directory(work_dir)

            success = False
            if use_sandbox and self.sandbox_manager:
                success = self.sandbox_manager.execute_sandboxed_makepkg(work_dir)
            elif self.terminal_manager:
                success = self.terminal_manager.run_makepkg(
                    work_dir,
                    force=build_mode == BuildMode.FORCE
                )

            if success and self.history_manager:
                self.history_manager.add_build_entry(pkgbuild_path, success)

            return ActionResult.SUCCESS if success else ActionResult.FAILURE

        except Exception as e:
            self._log_error(f"Build failed: {e}")
            return ActionResult.FAILURE

    def _handle_install(self, package: str = None, package_path: str = None, **kwargs) -> ActionResult:
        if not package and not package_path:
            return ActionResult.FAILURE

        try:
            if package_path and os.path.exists(package_path):
                install_cmd = ['pacman', '-U', package_path]
            elif package:
                install_cmd = ['paru', '-S', package]
            else:
                return ActionResult.FAILURE

            if self.terminal_manager:
                success = self.terminal_manager.run_command_with_sudo(
                    install_cmd,
                    title=f"Installing: {package or os.path.basename(package_path)}"
                )

                if success and self.history_manager:
                    self.history_manager.add_install_entry(package or package_path, success)

                return ActionResult.SUCCESS if success else ActionResult.FAILURE

            return ActionResult.FAILURE

        except Exception as e:
            self._log_error(f"Install failed: {e}")
            return ActionResult.FAILURE

    def _handle_uninstall(self, package: str = None, **kwargs) -> ActionResult:
        if not package:
            return ActionResult.FAILURE

        try:
            if not self._confirm_uninstall(package):
                return ActionResult.CANCELLED

            uninstall_cmd = ['pacman', '-R', package]

            if self.terminal_manager:
                success = self.terminal_manager.run_command_with_sudo(
                    uninstall_cmd,
                    title=f"Uninstalling: {package}"
                )

                if success and self.history_manager:
                    self.history_manager.add_uninstall_entry(package, success)

                return ActionResult.SUCCESS if success else ActionResult.FAILURE

            return ActionResult.FAILURE

        except Exception as e:
            self._log_error(f"Uninstall failed: {e}")
            return ActionResult.FAILURE

    def _handle_update(self, packages: List[str] = None, **kwargs) -> ActionResult:
        try:
            if packages:
                update_cmd = ['paru', '-S'] + packages
            else:
                update_cmd = ['paru', '-Syu']

            if self.terminal_manager:
                success = self.terminal_manager.run_command_with_sudo(
                    update_cmd,
                    title="System Update"
                )
                return ActionResult.SUCCESS if success else ActionResult.FAILURE

            return ActionResult.FAILURE

        except Exception as e:
            self._log_error(f"Update failed: {e}")
            return ActionResult.FAILURE

    def _handle_edit_pkgbuild(self, pkgbuild_path: str = None, **kwargs) -> ActionResult:
        if not pkgbuild_path or not os.path.exists(pkgbuild_path):
            return ActionResult.FAILURE

        try:
            editor = self._get_preferred_editor()
            edit_cmd = [editor, pkgbuild_path]

            if self.terminal_manager:
                success = self.terminal_manager.run_command(
                    edit_cmd,
                    title=f"Editing: {os.path.basename(pkgbuild_path)}"
                )
                return ActionResult.SUCCESS if success else ActionResult.FAILURE

            return ActionResult.FAILURE

        except Exception as e:
            self._log_error(f"Edit failed: {e}")
            return ActionResult.FAILURE

    def _handle_view_files(self, package_path: str = None, **kwargs) -> ActionResult:
        if not package_path or not os.path.exists(package_path):
            return ActionResult.FAILURE

        try:
            if self.file_utils:
                package_info = self.file_utils.analyze_package(package_path)
                if package_info.is_valid:
                    self._show_file_list_dialog(package_info.files, package_path)
                    return ActionResult.SUCCESS

            return ActionResult.FAILURE

        except Exception as e:
            self._log_error(f"View files failed: {e}")
            return ActionResult.FAILURE

    def _handle_view_dependencies(self, pkgbuild_path: str = None, **kwargs) -> ActionResult:
        if not pkgbuild_path or not os.path.exists(pkgbuild_path):
            return ActionResult.FAILURE

        try:
            if self.file_utils:
                dependencies = self.file_utils.get_package_dependencies(pkgbuild_path)
                self._show_dependencies_dialog(dependencies, pkgbuild_path)
                return ActionResult.SUCCESS

            return ActionResult.FAILURE

        except Exception as e:
            self._log_error(f"View dependencies failed: {e}")
            return ActionResult.FAILURE

    def _handle_download_sources(self, pkgbuild_path: str = None, **kwargs) -> ActionResult:
        if not pkgbuild_path or not os.path.exists(pkgbuild_path):
            return ActionResult.FAILURE

        try:
            work_dir = os.path.dirname(pkgbuild_path)

            if self.terminal_manager:
                success = self.terminal_manager.run_command(
                    ['makepkg', '-o'],
                    working_dir=work_dir,
                    title="Downloading Sources"
                )
                return ActionResult.SUCCESS if success else ActionResult.FAILURE

            return ActionResult.FAILURE

        except Exception as e:
            self._log_error(f"Download sources failed: {e}")
            return ActionResult.FAILURE

    def _handle_clean_build(self, build_dir: str = None, **kwargs) -> ActionResult:
        if not build_dir or not os.path.exists(build_dir):
            return ActionResult.FAILURE

        try:
            if self.terminal_manager:
                success = self.terminal_manager.run_command(
                    ['makepkg', '-c'],
                    working_dir=build_dir,
                    title="Cleaning Build Directory"
                )
                return ActionResult.SUCCESS if success else ActionResult.FAILURE

            return ActionResult.FAILURE

        except Exception as e:
            self._log_error(f"Clean build failed: {e}")
            return ActionResult.FAILURE

    def _handle_validate_checksums(self, pkgbuild_path: str = None, **kwargs) -> ActionResult:
        if not pkgbuild_path or not os.path.exists(pkgbuild_path):
            return ActionResult.FAILURE

        try:
            if self.file_utils:
                is_valid, results = self.file_utils.validate_checksums(pkgbuild_path)
                self._show_checksum_validation_dialog(is_valid, results)
                return ActionResult.SUCCESS

            return ActionResult.FAILURE

        except Exception as e:
            self._log_error(f"Checksum validation failed: {e}")
            return ActionResult.FAILURE

    def _handle_show_package_info(self, package: str = None, **kwargs) -> ActionResult:
        if not package:
            return ActionResult.FAILURE

        try:
            info_cmd = ['paru', '-Si', package]

            if self.terminal_manager:
                success = self.terminal_manager.run_command(
                    info_cmd,
                    title=f"Package Info: {package}"
                )
                return ActionResult.SUCCESS if success else ActionResult.FAILURE

            return ActionResult.FAILURE

        except Exception as e:
            self._log_error(f"Show package info failed: {e}")
            return ActionResult.FAILURE

    def _handle_open_terminal(self, working_dir: str = None, **kwargs) -> ActionResult:
        try:
            if self.terminal_manager:
                success = self.terminal_manager.open_terminal(working_dir)
                return ActionResult.SUCCESS if success else ActionResult.FAILURE

            return ActionResult.FAILURE

        except Exception as e:
            self._log_error(f"Open terminal failed: {e}")
            return ActionResult.FAILURE

    def _handle_open_file_manager(self, path: str = None, **kwargs) -> ActionResult:
        if not path:
            path = os.path.expanduser("~")

        try:
            subprocess.run(['xdg-open', path], check=False)
            return ActionResult.SUCCESS

        except Exception as e:
            self._log_error(f"Open file manager failed: {e}")
            return ActionResult.FAILURE

    def _handle_copy_to_clipboard(self, text: str = None, **kwargs) -> ActionResult:
        if not text:
            return ActionResult.FAILURE

        try:
            clipboard = Gtk.Clipboard.get(Gtk.SELECTION_CLIPBOARD)
            clipboard.set_text(text, -1)
            return ActionResult.SUCCESS

        except Exception as e:
            self._log_error(f"Copy to clipboard failed: {e}")
            return ActionResult.FAILURE

    def _handle_export_package_list(self, file_path: str = None, **kwargs) -> ActionResult:
        try:
            if not file_path:
                file_path = self._get_save_file_path("package_list.txt")

            if not file_path:
                return ActionResult.CANCELLED

            result = subprocess.run(['pacman', '-Q'], capture_output=True, text=True)
            if result.returncode == 0:
                with open(file_path, 'w') as f:
                    f.write(result.stdout)
                return ActionResult.SUCCESS

            return ActionResult.FAILURE

        except Exception as e:
            self._log_error(f"Export package list failed: {e}")
            return ActionResult.FAILURE

    def _handle_import_package_list(self, file_path: str = None, **kwargs) -> ActionResult:
        try:
            if not file_path:
                file_path = self._get_open_file_path()

            if not file_path or not os.path.exists(file_path):
                return ActionResult.CANCELLED

            with open(file_path, 'r') as f:
                packages = [line.split()[0] for line in f if line.strip()]

            if packages and self.terminal_manager:
                success = self.terminal_manager.run_command_with_sudo(
                    ['paru', '-S'] + packages,
                    title="Installing Package List"
                )
                return ActionResult.SUCCESS if success else ActionResult.FAILURE

            return ActionResult.FAILURE

        except Exception as e:
            self._log_error(f"Import package list failed: {e}")
            return ActionResult.FAILURE

    def _handle_unknown_action(self, action_name: str, *args, **kwargs) -> ActionResult:
        self._log_error(f"Unknown action requested: {action_name}")
        return ActionResult.FAILURE

    def _build_search_command(self, query: str, search_type: str) -> List[str]:
        if search_type == "aur":
            return ['paru', '-Ss', query]
        elif search_type == "installed":
            return ['pacman', '-Qs', query]
        else:
            return ['paru', '-Ss', query]

    def _clean_build_directory(self, build_dir: str):
        patterns_to_remove = ['*.pkg.tar.*', 'src/', 'pkg/']

        for pattern in patterns_to_remove:
            try:
                if pattern.endswith('/'):
                    full_path = os.path.join(build_dir, pattern.rstrip('/'))
                    if os.path.exists(full_path):
                        shutil.rmtree(full_path)
                else:
                    import glob
                    files = glob.glob(os.path.join(build_dir, pattern))
                    for file_path in files:
                        os.remove(file_path)
            except:
                pass

    def _get_preferred_editor(self) -> str:
        if self.preferences_manager:
            editor = self.preferences_manager.get_preference("preferred_editor", "")
            if editor and shutil.which(editor):
                return editor

        for editor in ['nano', 'vim', 'gedit', 'code', 'mousepad']:
            if shutil.which(editor):
                return editor

        return 'nano'

    def _confirm_security_risk(self, security_result) -> bool:
        if not security_result or not hasattr(security_result, 'security_level'):
            return True

        from ..file_utils import SecurityLevel

        if security_result.security_level in [SecurityLevel.WARNING, SecurityLevel.DANGER]:
            dialog = Gtk.MessageDialog(
                transient_for=self.window,
                modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.YES_NO,
                text="Security Warning"
            )
            dialog.format_secondary_text(
                f"This PKGBUILD has security concerns. Continue anyway?"
            )
            response = dialog.run()
            dialog.destroy()
            return response == Gtk.ResponseType.YES

        return True

    def _confirm_uninstall(self, package: str) -> bool:
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Uninstall {package}?"
        )
        dialog.format_secondary_text("This action cannot be undone.")
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.YES

    def _show_file_list_dialog(self, files: List[str], package_path: str):
        dialog = Gtk.Dialog(
            title=f"Files in {os.path.basename(package_path)}",
            transient_for=self.window,
            modal=True
        )
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(600, 400)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        listbox = Gtk.ListBox()
        scrolled.add(listbox)

        for file_path in files:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=file_path, halign=Gtk.Align.START)
            label.set_margin_start(12)
            label.set_margin_end(12)
            label.set_margin_top(6)
            label.set_margin_bottom(6)
            row.add(label)
            listbox.add(row)

        dialog.get_content_area().pack_start(scrolled, True, True, 0)
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def _show_dependencies_dialog(self, dependencies: Dict[str, List[str]], pkgbuild_path: str):
        dialog = Gtk.Dialog(
            title=f"Dependencies - {os.path.basename(pkgbuild_path)}",
            transient_for=self.window,
            modal=True
        )
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(500, 400)

        notebook = Gtk.Notebook()

        for dep_type, deps in dependencies.items():
            if deps:
                scrolled = Gtk.ScrolledWindow()
                scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

                listbox = Gtk.ListBox()
                scrolled.add(listbox)

                for dep in deps:
                    row = Gtk.ListBoxRow()
                    label = Gtk.Label(label=dep, halign=Gtk.Align.START)
                    label.set_margin_start(12)
                    label.set_margin_end(12)
                    label.set_margin_top(6)
                    label.set_margin_bottom(6)
                    row.add(label)
                    listbox.add(row)

                notebook.append_page(scrolled, Gtk.Label(label=dep_type.title()))

        dialog.get_content_area().pack_start(notebook, True, True, 0)
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def _show_checksum_validation_dialog(self, is_valid: bool, results: Dict[str, Any]):
        title = "Checksum Validation - " + ("Valid" if is_valid else "Invalid")
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.INFO if is_valid else Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )

        if "error" in results:
            dialog.format_secondary_text(results["error"])
        else:
            details = f"Files checked: {len(results.get('results', {}))}\n"
            details += f"Missing files: {len(results.get('missing_files', []))}\n"
            details += f"Checksum mismatches: {len(results.get('checksum_mismatches', []))}"
            dialog.format_secondary_text(details)

        dialog.run()
        dialog.destroy()

    def _get_save_file_path(self, default_name: str) -> Optional[str]:
        dialog = Gtk.FileChooserDialog(
            title="Save File",
            parent=self.window,
            action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK
        )
        dialog.set_current_name(default_name)

        response = dialog.run()
        file_path = dialog.get_filename() if response == Gtk.ResponseType.OK else None
        dialog.destroy()
        return file_path

    def _get_open_file_path(self) -> Optional[str]:
        dialog = Gtk.FileChooserDialog(
            title="Open File",
            parent=self.window,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )

        response = dialog.run()
        file_path = dialog.get_filename() if response == Gtk.ResponseType.OK else None
        dialog.destroy()
        return file_path

    def _on_search_completed(self, success: bool, output: str = ""):
        if success and self.window:
            if hasattr(self.window, 'show_search_results'):
                self.window.show_search_results(output)

    def _log_error(self, message: str):
        if self.error_handler:
            self.error_handler.log_error(message)
        else:
            print(f"ERROR: {message}")
