import shlex
from typing import Callable
from gi.repository import Gtk
from datetime import datetime

from ...history_manager import HistoryManager, ActionType, ActionStatus, HistoryEntry
from ...terminal_manager import TerminalManager
from ...error_handler import ErrorHandler, ErrorCategory, ErrorReport
from ..components.error_dialog import SuggestedAction

class SearchManager:
    def __init__(self, window, search_entry, content_view_manager):
        self.window = window
        self.search_entry = search_entry
        self.content_view_manager = content_view_manager

        self.history_manager = getattr(window, 'history_manager', None)
        self.terminal_manager = getattr(window, 'terminal_manager', None)
        self.error_handler = getattr(window, 'error_handler', None)

        self._setup_search_entry()

    def _setup_search_entry(self):
        if self.search_entry:
            self.search_entry.connect('search-changed', self.on_search_changed)
            self.search_entry.connect('activate', self.on_search_activated)

    def on_search_changed(self, entry: Gtk.SearchEntry):
        text = entry.get_text().strip()
        if not text:
            return

        self._update_search_suggestions(text)

    def on_search_activated(self, entry: Gtk.SearchEntry):
        command_or_query = entry.get_text().strip()
        if command_or_query:
            print(f"Executing search/command from search bar: {command_or_query}")

            if self._is_direct_command(command_or_query):
                self._execute_direct_command(command_or_query)
            else:
                self._execute_package_search(command_or_query)

            entry.set_text("")

    def _update_search_suggestions(self, text: str):
        if text.startswith('paru'):
            self._show_command_suggestions(text)
        else:
            self._show_package_suggestions(text)

    def _show_command_suggestions(self, text: str):
        suggestions = [
            'paru -S <package>',
            'paru -R <package>',
            'paru -Syu',
            'paru -Ss <query>',
            'paru -Si <package>',
            'paru -Ql <package>',
            'paru -Qo <file>',
            'paru -Sc',
            'paru --stats'
        ]

        matching_suggestions = [cmd for cmd in suggestions if cmd.startswith(text)]
        if matching_suggestions:
            self._display_suggestions(matching_suggestions)

    def _show_package_suggestions(self, query: str):
        pass

    def _display_suggestions(self, suggestions: list):
        pass

    def _is_direct_command(self, text: str) -> bool:
        return (text.startswith("paru") or
                text.startswith("pacman") or
                text.startswith("sudo"))

    def _execute_direct_command(self, command_text: str):
        if not self.terminal_manager:
            print(f"Terminal manager not available. Command: {command_text}")
            return

        try:
            command_args = shlex.split(command_text)
            current_path = getattr(self.window, 'current_path', None)

            self.terminal_manager.execute_command_in_system_terminal(
                command_args, cwd=current_path
            )

            if self.history_manager:
                self.history_manager.add_action(HistoryEntry(
                    id=None,
                    timestamp=datetime.utcnow(),
                    action_type=ActionType.COMMAND_EXECUTION,
                    summary=f"Executed command from search bar: {command_text}",
                    status=ActionStatus.INFO,
                    details={"command": command_text}
                ))
        except Exception as e:
            if self.error_handler:
                self.error_handler.handle_error(
                    e,
                    context="Command execution failed",
                    user_action=command_text
                )
            else:
                print(f"Error executing command: {e}")

    def _execute_package_search(self, query: str):
        if not self.terminal_manager:
            print(f"Terminal manager not available. Search query: {query}")
            return

        command = ['paru', '-Ss', query]
        self.terminal_manager.execute_command_in_system_terminal(command)

        if self.history_manager:
            self.history_manager.add_action(HistoryEntry(
                id=None,
                timestamp=datetime.utcnow(),
                action_type=ActionType.COMMAND_EXECUTION,
                summary=f"Searched for package: {query}",
                status=ActionStatus.INFO,
                details={"query": query, "command": " ".join(command)}
            ))

    def get_search_callbacks(self) -> dict:
        return {
            'changed': self.on_search_changed,
            'activated': self.on_search_activated
        }

    def clear_search(self):
        if self.search_entry:
            self.search_entry.set_text("")

    def focus_search(self):
        if self.search_entry:
            self.search_entry.grab_focus()

    def set_search_text(self, text: str):
        if self.search_entry:
            self.search_entry.set_text(text)

    def get_search_text(self) -> str:
        if self.search_entry:
            return self.search_entry.get_text()
        return ""

    def execute_quick_command(self, command: str):
        if self.search_entry:
            self.search_entry.set_text(command)
            self.on_search_activated(self.search_entry)

    def search_packages(self, query: str):
        self._execute_package_search(query)

    def get_command_history(self) -> list:
        if self.history_manager:
            return self.history_manager.get_recent_commands()
        return []

    def suggest_command_completion(self, partial_command: str) -> list:
        common_commands = [
            'paru -S', 'paru -R', 'paru -Syu', 'paru -Ss',
            'paru -Si', 'paru -Ql', 'paru -Qo', 'paru -Sc',
            'paru --stats', 'pacman -Q', 'pacman -Qi'
        ]

        return [cmd for cmd in common_commands if cmd.startswith(partial_command)]

    def validate_command(self, command: str) -> bool:
        try:
            shlex.split(command)
            return True
        except ValueError:
            return False

    def get_package_suggestions(self, query: str) -> list:
        return []

    def execute_search_filter(self, filter_text: str):
        if self.content_view_manager:
            pass
