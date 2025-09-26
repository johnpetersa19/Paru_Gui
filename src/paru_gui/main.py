#!/usr/bin/env python3

import sys
import os
import logging
import signal
from typing import Optional, List

def check_dependencies():
    missing_deps = []

    try:
        import requests
    except ImportError:
        missing_deps.append('requests')

    try:
        import gi
    except ImportError:
        missing_deps.append('PyGObject')

    if missing_deps:
        print("Missing required Python dependencies:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\nTo install:")
        print(f"  pip install {' '.join(missing_deps)}")
        print("  or")
        print(f"  sudo pacman -S {' '.join(f'python-{dep.lower()}' for dep in missing_deps)}")
        sys.exit(1)

check_dependencies()

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Gio, Adw, GLib
from pathlib import Path

from .error_handler import ErrorHandler
from .preferences_manager import PreferencesManager
from .history_manager import HistoryManager
from .lazy_cache_manager import LazyCacheManager
from .sandboxing import SandboxManager
from .security_analyzer import SecurityAnalyzer
from .terminal_manager import TerminalManager
from .tour_guide import TourGuide


class ParuGUIApplication(Adw.Application):

    def __init__(self):
        super().__init__(
            application_id="org.gnome.paru-gui",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS
        )

        self.window = None
        self.error_handler = None
        self.preferences_manager = None
        self.history_manager = None
        self.cache_manager = None
        self.sandbox_manager = None
        self.security_analyzer = None
        self.terminal_manager = None
        self.tour_guide = None

        self._setup_logging()
        self._setup_signal_handlers()
        self._setup_actions()
        self._initialize_managers()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger("ParuGUI")

    def _setup_signal_handlers(self):
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, shutting down gracefully")
            self.quit()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _initialize_managers(self):
        try:
            self.error_handler = ErrorHandler()
            self.preferences_manager = PreferencesManager()
            self.history_manager = HistoryManager()
            self.cache_manager = LazyCacheManager()
            self.sandbox_manager = SandboxManager()
            self.security_analyzer = SecurityAnalyzer()
            self.terminal_manager = TerminalManager()
            self.tour_guide = TourGuide()

            self.logger.info("All managers initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize managers: {e}")
            if self.error_handler:
                self.error_handler.handle_error(e, "Manager Initialization")

    def _setup_actions(self):
        actions = [
            ("quit", self._on_quit_action, ["<primary>q"]),
            ("about", self._on_about_action, ["<primary>question"]),
            ("preferences", self._on_preferences_action, ["<primary>comma"]),
            ("new-window", self._on_new_window_action, ["<primary>n"]),
            ("close-window", self._on_close_window_action, ["<primary>w"]),
            ("refresh", self._on_refresh_action, ["<primary>r", "F5"]),
            ("show-help-overlay", self._on_show_help_overlay, ["<primary>question"]),
            ("toggle-sidebar", self._on_toggle_sidebar, ["F9"]),
            ("search", self._on_search_action, ["<primary>f"]),
            ("select-all", self._on_select_all_action, ["<primary>a"]),
            ("copy", self._on_copy_action, ["<primary>c"]),
            ("paste", self._on_paste_action, ["<primary>v"]),
            ("undo", self._on_undo_action, ["<primary>z"]),
            ("redo", self._on_redo_action, ["<primary><shift>z"]),
        ]

        for name, callback, accelerators in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
            if accelerators:
                self.set_accels_for_action(f"app.{name}", accelerators)

    def _setup_css_provider(self):
        css_provider = Gtk.CssProvider()
        try:
            css_provider.load_from_resource("/org/gnome/paru-gui/ui/style.css")
            Gtk.StyleContext.add_provider_for_display(
                self.window.get_display(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            image_fixes_provider = Gtk.CssProvider()
            image_fixes_provider.load_from_resource("/org/gnome/paru-gui/ui/image_fixes.css")
            Gtk.StyleContext.add_provider_for_display(
                self.window.get_display(),
                image_fixes_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        except Exception as e:
            self.logger.warning(f"Could not load CSS: {e}")

    def do_activate(self):
        if self.window is None:
            self._create_main_window()

        self.window.present()

    def do_startup(self):
        Adw.Application.do_startup(self)
        self.logger.info("Application startup")

    def do_shutdown(self):
        self.logger.info("Application shutdown")

        if self.history_manager:
            try:
                self.history_manager.cleanup()
            except Exception as e:
                self.logger.error(f"Error during history manager cleanup: {e}")

        if self.cache_manager:
            try:
                self.cache_manager.cleanup()
            except Exception as e:
                self.logger.error(f"Error during cache manager cleanup: {e}")

        if self.terminal_manager:
            try:
                self.terminal_manager.cleanup()
            except Exception as e:
                self.logger.error(f"Error during terminal manager cleanup: {e}")

        Adw.Application.do_shutdown(self)

    def _create_main_window(self):
        from .window import ParuGUIWindow

        try:
            self.window = ParuGUIWindow(
                application=self,
                managers={
                    'error_handler': self.error_handler,
                    'preferences': self.preferences_manager,
                    'history': self.history_manager,
                    'cache': self.cache_manager,
                    'sandbox': self.sandbox_manager,
                    'security': self.security_analyzer,
                    'terminal': self.terminal_manager,
                    'tour_guide': self.tour_guide,
                }
            )

            self._setup_css_provider()
            self._connect_window_signals()

            if self.preferences_manager.get_preference('show_tour_on_startup', True):
                self.tour_guide.start_tour(self.window)

            self.logger.info("Main window created successfully")

        except Exception as e:
            self.logger.error(f"Failed to create main window: {e}")
            if self.error_handler:
                self.error_handler.handle_critical_error(e, "Window Creation")
            else:
                sys.exit(1)

    def _connect_window_signals(self):
        if self.window:
            self.window.connect('close-request', self._on_window_close_request)

    def _on_window_close_request(self, window):
        if self.preferences_manager.get_preference('confirm_on_quit', False):
            dialog = Adw.MessageDialog.new(
                self.window,
                "Quit Paru GUI?",
                "Are you sure you want to quit?"
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("quit", "Quit")
            dialog.set_response_appearance("quit", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")

            dialog.connect("response", self._on_quit_dialog_response)
            dialog.present()
            return True

        return False

    def _on_quit_dialog_response(self, dialog, response):
        if response == "quit":
            self.quit()
        dialog.close()

    def _on_quit_action(self, action, param):
        if self.window:
            self.window.close()
        else:
            self.quit()

    def _on_about_action(self, action, param):
        about_window = Adw.AboutWindow(
            transient_for=self.window,
            application_name="Paru GUI",
            application_icon="org.gnome.paru-gui",
            developer_name="Paru GUI Team",
            version="2.7.0",
            developers=["Paru GUI Team"],
            copyright="© 2025 Paru GUI Team",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/paru-gui-project",
            issue_url="https://github.com/paru-gui-project/paru-gui/issues",
            support_url="https://github.com/paru-gui-project/paru-gui/discussions",
        )

        about_window.set_comments("Manage AUR packages with ease and security")
        about_window.present()

    def _on_preferences_action(self, action, param):
        if self.window:
            self.window.show_preferences()

    def _on_new_window_action(self, action, param):
        new_window = ParuGUIWindow(application=self)
        new_window.present()

    def _on_close_window_action(self, action, param):
        if self.window:
            self.window.close()

    def _on_refresh_action(self, action, param):
        if self.window:
            self.window.refresh_content()

    def _on_show_help_overlay(self, action, param):
        if self.window:
            self.window.show_help_overlay()

    def _on_toggle_sidebar(self, action, param):
        if self.window:
            self.window.toggle_sidebar()

    def _on_search_action(self, action, param):
        if self.window:
            self.window.toggle_search()

    def _on_select_all_action(self, action, param):
        if self.window:
            self.window.select_all()

    def _on_copy_action(self, action, param):
        if self.window:
            self.window.copy_selection()

    def _on_paste_action(self, action, param):
        if self.window:
            self.window.paste_content()

    def _on_undo_action(self, action, param):
        if self.history_manager:
            try:
                self.history_manager.undo_last_action()
            except Exception as e:
                self.logger.error(f"Undo failed: {e}")
                if self.error_handler:
                    self.error_handler.handle_error(e, "Undo Operation")

    def _on_redo_action(self, action, param):
        if self.history_manager:
            try:
                self.history_manager.redo_last_action()
            except Exception as e:
                self.logger.error(f"Redo failed: {e}")
                if self.error_handler:
                    self.error_handler.handle_error(e, "Redo Operation")

    def get_manager(self, manager_name: str):
        managers = {
            'error_handler': self.error_handler,
            'preferences': self.preferences_manager,
            'history': self.history_manager,
            'cache': self.cache_manager,
            'sandbox': self.sandbox_manager,
            'security': self.security_analyzer,
            'terminal': self.terminal_manager,
            'tour_guide': self.tour_guide,
        }
        return managers.get(manager_name)

    def handle_command_line_args(self, args: List[str]):
        if '--verbose' in args or '-v' in args:
            logging.getLogger().setLevel(logging.DEBUG)
            self.logger.debug("Verbose logging enabled")

        if '--no-tour' in args:
            self.preferences_manager.set_preference('show_tour_on_startup', False)

        if '--reset-preferences' in args:
            self.preferences_manager.reset_to_defaults()
            self.logger.info("Preferences reset to defaults")

        if '--safe-mode' in args:
            self.sandbox_manager.enable_safe_mode()
            self.logger.info("Safe mode enabled")


def main():
    app = ParuGUIApplication()

    if len(sys.argv) > 1:
        app.handle_command_line_args(sys.argv[1:])

    try:
        return app.run(sys.argv)
    except KeyboardInterrupt:
        app.logger.info("Application interrupted by user")
        return 0
    except Exception as e:
        if app.error_handler:
            app.error_handler.handle_critical_error(e, "Application Runtime")
        else:
            print(f"Critical error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

