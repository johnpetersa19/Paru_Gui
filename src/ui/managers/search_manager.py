# src/ui/search_manager.py
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

import shlex
from typing import Callable
from gi.repository import Gtk
from datetime import datetime

from ...history_manager import HistoryManager, ActionType, ActionStatus, HistoryEntry
from ...terminal_manager import TerminalManager
from ...error_handler import ErrorHandler, ErrorContext, ErrorCategory, SuggestedAction


class SearchManager:
    """Manages search functionality and command execution from search bar."""

    def __init__(self, window, builder, history_manager, terminal_manager, error_handler):
        self.window = window
        self.builder = builder
        self.history_manager = history_manager
        self.terminal_manager = terminal_manager
        self.error_handler = error_handler

    def on_search_changed(self, entry: Gtk.SearchEntry):
        """Handles changes in the search entry for intelligent assistance."""
        text = entry.get_text().strip()
        # TODO: Implement intelligent assistant logic here
        # - Auto-complete for 'paru' commands
        # - Suggest packages
        # - Provide command help for prefixes like '-c'
        print(f"Search text changed: {text}")

    def on_search_activated(self, entry: Gtk.SearchEntry):
        """Handles activation (Enter key) in the search entry."""
        command_or_query = entry.get_text().strip()
        if command_or_query:
            print(f"Executing search/command from search bar: {command_or_query}")

            # Determine if it's a command or package query
            if self._is_direct_command(command_or_query):
                self._execute_direct_command(command_or_query)
            else:
                self._execute_package_search(command_or_query)

            entry.set_text("")  # Clear search after activation

    def _is_direct_command(self, text: str) -> bool:
        """Determines if the text is a direct command."""
        return (text.startswith("paru") or
                text.startswith("pacman") or
                text.startswith("sudo"))

    def _execute_direct_command(self, command_text: str):
        """Executes a direct command in the system terminal."""
        try:
            command_args = shlex.split(command_text)
            self.terminal_manager.execute_command_in_system_terminal(
                command_args, cwd=self.window.current_path
            )

            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.COMMAND_EXECUTION,
                summary=f"Executed command from search bar: {command_text}",
                status=ActionStatus.INFO,
                details={"command": command_text}
            ))
        except Exception as e:
            self.error_handler.show_error_dialog(ErrorContext(
                category=ErrorCategory.COMMAND_EXECUTION,
                summary="Command execution failed",
                details=f"Failed to execute command: {command_text}\nError: {str(e)}",
                command_executed=command_text
            ))

    def _execute_package_search(self, query: str):
        """Executes a package search query."""
        # For now, execute search in terminal
        command = ['paru', '-Ss', query]
        self.terminal_manager.execute_command_in_system_terminal(command)

        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.COMMAND_EXECUTION,
            summary=f"Searched for package: {query}",
            status=ActionStatus.INFO,
            details={"query": query, "command": " ".join(command)}
        ))

    def get_search_callbacks(self) -> dict:
        """Returns dictionary of search-related callbacks."""
        return {
            'changed': self.on_search_changed,
            'activated': self.on_search_activated
        }
