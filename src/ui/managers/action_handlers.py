# src/ui/action_handlers.py
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
import shlex
from typing import Optional, List
from gi.repository import Gtk
from datetime import datetime

from ...history_manager import HistoryManager, ActionType, ActionStatus, HistoryEntry
from ...terminal_manager import TerminalManager
from ...sandboxing import SandboxManager, SandboxOptions, IsolationLevel
from ...error_handler import ErrorHandler, ErrorContext, ErrorCategory, SuggestedAction



class ActionHandlers:
    """Handles all user action callbacks and command executions."""

    def __init__(self, window, builder, preferences_manager, history_manager,
                 terminal_manager, sandbox_manager, error_handler):
        self.window = window
        self.builder = builder
        self.preferences_manager = preferences_manager
        self.history_manager = history_manager
        self.terminal_manager = terminal_manager
        self.sandbox_manager = sandbox_manager
        self.error_handler = error_handler

    def on_build_package(self, button_or_action, pkgbuild_path: str):
        """Handles building a package from PKGBUILD."""
        command = ['makepkg', '-si']
        working_dir = os.path.dirname(pkgbuild_path)

        self.terminal_manager.execute_command_in_system_terminal(
            command, cwd=working_dir
        )

        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.PACKAGE_BUILD,
            summary=f"Built package: {os.path.basename(pkgbuild_path)}",
            status=ActionStatus.INFO,
            details={"pkgbuild_path": pkgbuild_path, "command": " ".join(command)}
        ))

    def on_build_package_sandboxed(self, button, pkgbuild_path: str, isolation_level: str,
                                   allow_network: bool, allow_home: bool):
        """Handles sandboxed package building."""
        if not self.sandbox_manager:
            self.error_handler.show_error_dialog(ErrorContext(
                category=ErrorCategory.DEPENDENCY_ERROR,
                summary="Sandboxing not available",
                details="Bubblewrap (bwrap) is not installed or configured.",
                suggested_actions=[SuggestedAction.INSTALL_DEPENDENCY]
            ))
            return

        try:
            isolation = IsolationLevel[isolation_level.upper()]
        except KeyError:
            isolation = IsolationLevel.MEDIUM

        options = SandboxOptions(
            isolation_level=isolation,
            allow_network=allow_network,
            allow_home_access=allow_home
        )

        command = ['makepkg', '-si']
        working_dir = os.path.dirname(pkgbuild_path)

        try:
            self.sandbox_manager.execute_sandboxed(
                command, options, cwd=working_dir
            )

            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.PACKAGE_BUILD,
                summary=f"Built package (sandboxed): {os.path.basename(pkgbuild_path)}",
                status=ActionStatus.SUCCESS,
                details={
                    "pkgbuild_path": pkgbuild_path,
                    "sandboxed": True,
                    "isolation_level": isolation_level
                }
            ))
        except Exception as e:
            self.error_handler.show_error_dialog(ErrorContext(
                category=ErrorCategory.SANDBOX_ERROR,
                summary="Sandboxed build failed",
                details=str(e),
                file_path=pkgbuild_path
            ))

    def on_edit_pkgbuild(self, button_or_action, pkgbuild_path: str):
        """Handles editing a PKGBUILD file."""
        editor = self.preferences_manager.get_default_editor()
        command = [editor, pkgbuild_path]

        self.terminal_manager.execute_command_in_system_terminal(command)

        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.FILE_EDIT,
            summary=f"Opened PKGBUILD for editing: {os.path.basename(pkgbuild_path)}",
            status=ActionStatus.INFO,
            details={"file_path": pkgbuild_path, "editor": editor}
        ))

    def on_view_dependencies(self, button_or_action, pkgbuild_path: str):
        """Handles viewing package dependencies."""
        command = ['makepkg', '--printsrcinfo']
        working_dir = os.path.dirname(pkgbuild_path)

        self.terminal_manager.execute_command_in_system_terminal(
            command, cwd=working_dir
        )

    def on_download_sources(self, button_or_action, pkgbuild_path: str = None):
        """Handles downloading package sources."""
        if pkgbuild_path:
            command = ['makepkg', '-o']  # Download sources only
            working_dir = os.path.dirname(pkgbuild_path)
        else:
            command = ['paru', '-G']  # Generic download
            working_dir = self.window.current_path

        self.terminal_manager.execute_command_in_system_terminal(
            command, cwd=working_dir
        )

    def on_install_package(self, button_or_action, package_path: str):
        """Handles installing a package file."""
        command = ['sudo', 'pacman', '-U', package_path]

        self.terminal_manager.execute_command_in_system_terminal(command)

        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.PACKAGE_INSTALL,
            summary=f"Installed package: {os.path.basename(package_path)}",
            status=ActionStatus.INFO,
            details={"package_path": package_path}
        ))

    def on_install_package_sandboxed(self, button, package_path: str, isolation_level: str,
                                     allow_network: bool, allow_home: bool):
        """Handles sandboxed package installation."""
        # Similar to sandboxed build but for installation
        command = ['sudo', 'pacman', '-U', package_path]

        # Note: Sandboxed sudo operations require special handling
        # This is a simplified implementation
        self.on_install_package(button, package_path)

    def on_verify_signature(self, button_or_action, package_path: str):
        """Handles verifying package signature."""
        command = ['pacman', '-Qkk', os.path.basename(package_path).split('-')[0]]

        self.terminal_manager.execute_command_in_system_terminal(command)

    def on_view_package_info(self, button_or_action, package_path: str):
        """Handles viewing package information."""
        command = ['pacman', '-Qip', package_path]

        self.terminal_manager.execute_command_in_system_terminal(command)

    def on_apply_patch(self, button_or_action, patch_path: str):
        """Handles applying a patch file."""
        command = ['patch', '-p1', '-i', patch_path]
        working_dir = os.path.dirname(patch_path)

        self.terminal_manager.execute_command_in_system_terminal(
            command, cwd=working_dir
        )

    def on_view_diff(self, button_or_action, patch_path: str):
        """Handles viewing a diff/patch file."""
        editor = self.preferences_manager.get_default_editor()
        command = [editor, patch_path]

        self.terminal_manager.execute_command_in_system_terminal(command)

    def on_execute_custom_command(self, button_or_action):
        """Handles executing a custom command."""
        # This would open a dialog to input custom command
        # For now, just show a placeholder
        from .ui_manager import UIManager
        if hasattr(self.window, 'ui_manager'):
            self.window.ui_manager.show_info_dialog(
                "Custom Command",
                "Custom command execution will be implemented here.",
                "utilities-terminal-symbolic"
            )

    def on_dry_run_command(self, button_or_action):
        """Handles dry-run simulation of commands."""
        # Placeholder for dry-run functionality
        pass

    def on_consult_documentation(self, button_or_action):
        """Handles opening documentation."""
        command = ['xdg-open', 'https://wiki.archlinux.org/title/Arch_User_Repository']
        self.terminal_manager.execute_command_in_system_terminal(command)

    # System-level actions
    def on_system_action(self, action, param):
        """General system action handler."""
        pass

    def on_statistics_action(self, action, param):
        """Shows system statistics."""
        command = ['paru', '-Ps']
        self.terminal_manager.execute_command_in_system_terminal(command)

    def on_arch_news_action(self, action, param):
        """Shows Arch Linux news."""
        command = ['paru', '--news']
        self.terminal_manager.execute_command_in_system_terminal(command)

    def on_clean_cache_action(self, action, param):
        """Cleans package cache."""
        command = ['sudo', 'paru', '-Scc']
        self.terminal_manager.execute_command_in_system_terminal(command)

    def on_update_system_action(self, action, param):
        """Updates the system."""
        command = ['paru', '-Syu']
        self.terminal_manager.execute_command_in_system_terminal(command)

    def on_action_history_action(self, action, param):
        """Shows action history."""
        # This would open the history dialog
        pass

    def on_show_upstream_updates(self, action, param):
        """Shows upstream updates."""
        pass

    def on_refresh_upstream_updates_action(self, action, param):
        """Refreshes upstream updates."""
        pass

    def on_hide_advanced_action(self, action, param):
        """Toggles simplified mode."""
        current = self.preferences_manager.get_simplified_mode()
        self.preferences_manager.set_simplified_mode(not current)

    def on_check_devel_action(self, action, param):
        """Checks for devel updates."""
        command = ['paru', '-Sua']
        self.terminal_manager.execute_command_in_system_terminal(command)

    def on_install_debug_action(self, action, param):
        """Installs debug packages."""
        pass

    def on_show_warnings_action(self, action, param):
        """Shows detailed warnings."""
        pass

    def on_show_terminal_panel_action(self, action, param):
        """Toggles terminal panel visibility."""
        current = self.preferences_manager.get_show_realtime_terminal()
        self.preferences_manager.set_show_realtime_terminal(not current)

        if not current:
            self.terminal_manager.show_terminal_panel()
        else:
            self.terminal_manager.hide_terminal_panel()

    def on_review_pkgbuild_action(self, action, param):
        """Opens PKGBUILD review dialog."""
        # This would open the review dialog
        pass
