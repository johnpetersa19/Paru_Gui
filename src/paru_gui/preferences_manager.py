import os
import logging
import json
from typing import List, Optional, Any, Dict, Union
from enum import Enum
from gi.repository import Gio, Gtk, GObject, Adw, GLib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("preferences_manager")

class EditorChoice(Enum):
    SYSTEM_DEFAULT = "system_default"
    GEDIT = "gedit"
    NANO = "nano"
    VIM = "vim"
    EMACS = "emacs"
    VSCODE = "code"
    ATOM = "atom"
    SUBLIME = "subl"
    CUSTOM = "custom"

class UpstreamFrequency(Enum):
    NEVER = "never"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ON_STARTUP = "on_startup"
    MANUAL = "manual"

class AURConfidenceLevel(Enum):
    PARANOID = "paranoid"
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    TRUSTING = "trusting"
    PERMISSIVE = "permissive"

class ThemeMode(Enum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"

class UpdateNotificationLevel(Enum):
    NONE = "none"
    CRITICAL = "critical"
    IMPORTANT = "important"
    ALL = "all"

class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class PreferencesManager(GObject.Object):
    SCHEMA_ID = 'org.gnome.paru-gui'

    __gsignals__ = {
        'preference-changed': (GObject.SignalFlags.RUN_LAST, None, (str, object)),
        'preferences-reset': (GObject.SignalFlags.RUN_LAST, None, ()),
        'preferences-exported': (GObject.SignalFlags.RUN_LAST, None, (str,)),
        'preferences-imported': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self):
        super().__init__()
        try:
            self.settings = Gio.Settings.new(self.SCHEMA_ID)
            logger.info(f"PreferencesManager initialized with GSettings schema: {self.SCHEMA_ID}")
        except GLib.Error as e:
            logger.critical(f"Failed to initialize GSettings for schema '{self.SCHEMA_ID}': {e}")
            logger.critical("Preferences will not be saved or loaded properly. Ensure schema is installed.")
            self.settings = None

    def _get_setting(self, key: str, default_value: Any = None) -> Any:
        if not self.settings:
            return default_value

        try:
            schema_type = self.settings.get_value(key).get_type().get_type_string()
            if schema_type == 's':
                return self.settings.get_string(key)
            elif schema_type == 'b':
                return self.settings.get_boolean(key)
            elif schema_type == 'i':
                return self.settings.get_int(key)
            elif schema_type == 'as':
                return self.settings.get_strv(key)
            else:
                logger.warning(f"Unknown GSettings type '{schema_type}' for key '{key}'. Returning default.")
                return default_value
        except (GLib.Error, AttributeError) as e:
            logger.error(f"Error getting GSettings key '{key}': {e}. Returning default: {default_value}")
            return default_value

    def _set_setting(self, key: str, value: Any) -> bool:
        if not self.settings:
            return False

        try:
            if isinstance(value, bool):
                self.settings.set_boolean(key, value)
            elif isinstance(value, int):
                self.settings.set_int(key, value)
            elif isinstance(value, str):
                self.settings.set_string(key, value)
            elif isinstance(value, list):
                self.settings.set_strv(key, value)
            else:
                logger.error(f"Unsupported value type for key '{key}': {type(value)}")
                return False

            self.emit('preference-changed', key, value)
            return True
        except GLib.Error as e:
            logger.error(f"Error setting GSettings key '{key}' to '{value}': {e}")
            return False

    def get_preference(self, key: str, default_value: Any = None) -> Any:
        return self._get_setting(key, default_value)

    def set_preference(self, key: str, value: Any) -> bool:
        return self._set_setting(key, value)

    def get_simplified_mode(self) -> bool:
        return self.simplified_mode

    def set_simplified_mode(self, value: bool) -> bool:
        self.simplified_mode = value
        return True

    @property
    def first_run(self) -> bool:
        return self._get_setting('first-run', True)

    @first_run.setter
    def first_run(self, value: bool):
        self._set_setting('first-run', value)

    @property
    def simplified_mode(self) -> bool:
        return self._get_setting('simplified-mode', True)

    @simplified_mode.setter
    def simplified_mode(self, value: bool):
        self._set_setting('simplified-mode', value)

    @property
    def default_editor(self) -> str:
        return self._get_setting('default-editor', 'gedit')

    @default_editor.setter
    def default_editor(self, value: str):
        self._set_setting('default-editor', value)

    @property
    def window_width(self) -> int:
        return self._get_setting('window-width', 1200)

    @window_width.setter
    def window_width(self, value: int):
        self._set_setting('window-width', value)

    @property
    def window_height(self) -> int:
        return self._get_setting('window-height', 800)

    @window_height.setter
    def window_height(self, value: int):
        self._set_setting('window-height', value)

    @property
    def recent_directories(self) -> List[str]:
        return self._get_setting('recent-directories', [])

    @recent_directories.setter
    def recent_directories(self, value: List[str]):
        self._set_setting('recent-directories', value)

    @property
    def max_recent_directories(self) -> int:
        return self._get_setting('max-recent-directories', 10)

    @max_recent_directories.setter
    def max_recent_directories(self, value: int):
        self._set_setting('max-recent-directories', value)

    @property
    def upstream_check_frequency(self) -> int:
        return self._get_setting('upstream-check-frequency', 24)

    @upstream_check_frequency.setter
    def upstream_check_frequency(self, value: int):
        self._set_setting('upstream-check-frequency', value)

    @property
    def upstream_ignore_prerelease(self) -> bool:
        return self._get_setting('upstream-ignore-prerelease', True)

    @upstream_ignore_prerelease.setter
    def upstream_ignore_prerelease(self, value: bool):
        self._set_setting('upstream-ignore-prerelease', value)

    @property
    def upstream_notify_security_only(self) -> bool:
        return self._get_setting('upstream-notify-security-only', False)

    @upstream_notify_security_only.setter
    def upstream_notify_security_only(self, value: bool):
        self._set_setting('upstream-notify-security-only', value)

    @property
    def upstream_priority_platforms(self) -> List[str]:
        return self._get_setting('upstream-priority-platforms', ['github', 'gitlab'])

    @upstream_priority_platforms.setter
    def upstream_priority_platforms(self, value: List[str]):
        self._set_setting('upstream-priority-platforms', value)

    @property
    def aur_show_trust_icons(self) -> bool:
        return self._get_setting('aur-show-trust-icons', True)

    @aur_show_trust_icons.setter
    def aur_show_trust_icons(self, value: bool):
        self._set_setting('aur-show-trust-icons', value)

    @property
    def aur_block_no_votes(self) -> bool:
        return self._get_setting('aur-block-no-votes', False)

    @aur_block_no_votes.setter
    def aur_block_no_votes(self, value: bool):
        self._set_setting('aur-block-no-votes', value)

    @property
    def aur_consider_last_update(self) -> bool:
        return self._get_setting('aur-consider-last-update', True)

    @aur_consider_last_update.setter
    def aur_consider_last_update(self, value: bool):
        self._set_setting('aur-consider-last-update', value)

    @property
    def aur_check_negative_comments(self) -> bool:
        return self._get_setting('aur-check-negative-comments', True)

    @aur_check_negative_comments.setter
    def aur_check_negative_comments(self, value: bool):
        self._set_setting('aur-check-negative-comments', value)

    @property
    def aur_confidence_level(self) -> str:
        return self._get_setting('aur-confidence-level', 'balanced')

    @aur_confidence_level.setter
    def aur_confidence_level(self, value: str):
        self._set_setting('aur-confidence-level', value)

    @property
    def developer_mode(self) -> bool:
        return self._get_setting('developer-mode', False)

    @developer_mode.setter
    def developer_mode(self, value: bool):
        self._set_setting('developer-mode', value)

    @property
    def check_devel_updates(self) -> bool:
        return self._get_setting('check-devel-updates', False)

    @check_devel_updates.setter
    def check_devel_updates(self, value: bool):
        self._set_setting('check-devel-updates', value)

    @property
    def clean_after_build(self) -> bool:
        return self._get_setting('clean-after-build', True)

    @clean_after_build.setter
    def clean_after_build(self, value: bool):
        self._set_setting('clean-after-build', value)

    @property
    def install_debug_packages(self) -> bool:
        return self._get_setting('install-debug-packages', False)

    @install_debug_packages.setter
    def install_debug_packages(self, value: bool):
        self._set_setting('install-debug-packages', value)

    @property
    def show_detailed_warnings(self) -> bool:
        return self._get_setting('show-detailed-warnings', False)

    @show_detailed_warnings.setter
    def show_detailed_warnings(self, value: bool):
        self._set_setting('show-detailed-warnings', value)

    @property
    def show_terminal_panel(self) -> bool:
        return self._get_setting('show-terminal-panel', False)

    @show_terminal_panel.setter
    def show_terminal_panel(self, value: bool):
        self._set_setting('show-terminal-panel', value)

    @property
    def enable_sandboxing(self) -> bool:
        return self._get_setting('enable-sandboxing', True)

    @enable_sandboxing.setter
    def enable_sandboxing(self, value: bool):
        self._set_setting('enable-sandboxing', value)

    @property
    def auto_pgp_fetch(self) -> bool:
        return self._get_setting('auto-pgp-fetch', True)

    @auto_pgp_fetch.setter
    def auto_pgp_fetch(self, value: bool):
        self._set_setting('auto-pgp-fetch', value)

    @property
    def theme_mode(self) -> str:
        return self._get_setting('theme-mode', 'system')

    @theme_mode.setter
    def theme_mode(self, value: str):
        self._set_setting('theme-mode', value)

    @property
    def update_notification_level(self) -> str:
        return self._get_setting('update-notification-level', 'important')

    @update_notification_level.setter
    def update_notification_level(self, value: str):
        self._set_setting('update-notification-level', value)

    @property
    def log_level(self) -> str:
        return self._get_setting('log-level', 'info')

    @log_level.setter
    def log_level(self, value: str):
        self._set_setting('log-level', value)

    @property
    def enable_history_tracking(self) -> bool:
        return self._get_setting('enable-history-tracking', True)

    @enable_history_tracking.setter
    def enable_history_tracking(self, value: bool):
        self._set_setting('enable-history-tracking', value)

    @property
    def history_retention_days(self) -> int:
        return self._get_setting('history-retention-days', 30)

    @history_retention_days.setter
    def history_retention_days(self, value: int):
        self._set_setting('history-retention-days', value)

    def add_recent_directory(self, directory: str):
        recent = self.recent_directories
        if directory in recent:
            recent.remove(directory)
        recent.insert(0, directory)
        recent = recent[:self.max_recent_directories]
        self.recent_directories = recent

    def clear_recent_directories(self):
        self.recent_directories = []

    def get_editor_command(self) -> str:
        editor = self.default_editor
        if editor == "system_default":
            return os.environ.get('EDITOR', 'gedit')
        elif editor == "custom":
            return self._get_setting('custom-editor-command', 'gedit')
        else:
            return editor

    def set_custom_editor(self, command: str):
        self._set_setting('custom-editor-command', command)
        self.default_editor = "custom"

    def reset_to_defaults(self):
        if not self.settings:
            return False

        try:
            for key in self.settings.list_keys():
                self.settings.reset(key)
            self.emit('preferences-reset')
            logger.info("All preferences reset to defaults")
            return True
        except Exception as e:
            logger.error(f"Failed to reset preferences: {e}")
            return False

    def export_preferences(self, file_path: str) -> bool:
        if not self.settings:
            return False

        try:
            preferences = {}
            for key in self.settings.list_keys():
                preferences[key] = self._get_setting(key)

            with open(file_path, 'w') as f:
                json.dump(preferences, f, indent=2)

            self.emit('preferences-exported', file_path)
            logger.info(f"Preferences exported to: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export preferences: {e}")
            return False

    def import_preferences(self, file_path: str) -> bool:
        if not self.settings:
            return False

        try:
            with open(file_path, 'r') as f:
                preferences = json.load(f)
            
            for key, value in preferences.items():
                if key in self.settings.list_keys():
                    self._set_setting(key, value)
            
            self.emit('preferences-imported')
            logger.info(f"Preferences imported from: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to import preferences: {e}")
            return False

    def validate_preferences(self) -> Dict[str, List[str]]:
        errors = {}

        if self.window_width < 800:
            errors.setdefault('window', []).append("Window width must be at least 800 pixels")

        if self.window_height < 600:
            errors.setdefault('window', []).append("Window height must be at least 600 pixels")

        if self.upstream_check_frequency < 0:
            errors.setdefault('upstream', []).append("Check frequency cannot be negative")

        if self.max_recent_directories < 1:
            errors.setdefault('recent', []).append("Must keep at least 1 recent directory")

        if self.history_retention_days < 1:
            errors.setdefault('history', []).append("History retention must be at least 1 day")

        return errors

    def apply_theme(self):
        theme = self.theme_mode
        if theme == "system":
            return

        style_manager = Adw.StyleManager.get_default() if hasattr(Adw, 'StyleManager') else None
        if style_manager:
            if theme == "dark":
                style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            elif theme == "light":
                style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
            else:
                style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

    def get_all_preferences(self) -> Dict[str, Any]:
        if not self.settings:
            return {}

        preferences = {}
        for key in self.settings.list_keys():
            preferences[key.replace('-', '_')] = self._get_setting(key)
        return preferences

    def update_preferences(self, preferences: Dict[str, Any]):
        if not self.settings:
            return

        for key, value in preferences.items():
            gsettings_key = key.replace('_', '-')
            if gsettings_key in self.settings.list_keys():
                self._set_setting(gsettings_key, value)
