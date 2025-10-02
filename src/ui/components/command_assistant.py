import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import GObject, Gio, GLib, Gtk, Adw, Gdk
import json
import os
from typing import Dict, List, Any, Optional, Tuple, Union
from enum import Enum
from dataclasses import dataclass, field

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

@dataclass
class PreferenceCategory:
    name: str
    title: str
    description: str
    preferences: List[str] = field(default_factory=list)

@dataclass
class PreferenceDefinition:
    key: str
    title: str
    description: str
    default_value: Any
    value_type: type
    category: str
    requires_restart: bool = False
    validator: Optional[callable] = None
    constraints: Optional[Dict[str, Any]] = None

class CommandAssistant(Adw.Window):
    __gtype_name__ = "CommandAssistant"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Command Assistant")
        self.set_default_size(600, 500)
        self._setup_ui()

    def _setup_ui(self):
        header_bar = Adw.HeaderBar()
        self.set_titlebar(header_bar)

        toast_overlay = Adw.ToastOverlay()
        self.set_content(toast_overlay)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        toast_overlay.set_child(scrolled_window)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.set_spacing(24)
        main_box.set_margin_top(24)
        main_box.set_margin_bottom(24)
        main_box.set_margin_start(24)
        main_box.set_margin_end(24)
        scrolled_window.set_child(main_box)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title_box.set_spacing(6)
        main_box.append(title_box)

        title_label = Gtk.Label()
        title_label.set_markup("<big><b>Command Assistant</b></big>")
        title_label.set_halign(Gtk.Align.START)
        title_box.append(title_label)

        subtitle_label = Gtk.Label()
        subtitle_label.set_text("Get help with paru commands and manage application preferences")
        subtitle_label.set_halign(Gtk.Align.START)
        subtitle_label.add_css_class("dim-label")
        title_box.append(subtitle_label)

        commands_group = Adw.PreferencesGroup()
        commands_group.set_title("Common Commands")
        commands_group.set_description("Frequently used paru and AUR commands")
        main_box.append(commands_group)

        commands = [
            ("paru -S <package>", "Install a package from repositories or AUR"),
            ("paru -R <package>", "Remove an installed package"),
            ("paru -Syu", "Update all installed packages"),
            ("paru -Ss <query>", "Search for packages by name or description"),
            ("paru -Si <package>", "Show detailed package information"),
            ("paru -Ql <package>", "List files installed by a package"),
            ("paru -Qo <file>", "Find which package owns a file"),
            ("paru -Sc", "Clean package cache"),
            ("paru --stats", "Show statistics about installed packages")
        ]

        for command, description in commands:
            row = Adw.ActionRow()
            row.set_title(command)
            row.set_subtitle(description)

            copy_button = Gtk.Button()
            copy_button.set_icon_name("edit-copy-symbolic")
            copy_button.set_valign(Gtk.Align.CENTER)
            copy_button.add_css_class("flat")
            copy_button.set_tooltip_text("Copy command")
            copy_button.connect("clicked", self._on_copy_command, command)
            row.add_suffix(copy_button)

            commands_group.add(row)

        options_group = Adw.PreferencesGroup()
        options_group.set_title("Application Settings")
        options_group.set_description("Configure application behavior and preferences")
        main_box.append(options_group)

        preferences_row = Adw.ActionRow()
        preferences_row.set_title("Open Preferences")
        preferences_row.set_subtitle("Configure general settings, security options, and more")

        preferences_button = Gtk.Button()
        preferences_button.set_icon_name("preferences-system-symbolic")
        preferences_button.set_valign(Gtk.Align.CENTER)
        preferences_button.add_css_class("flat")
        preferences_button.connect("clicked", self._on_preferences_clicked)
        preferences_row.add_suffix(preferences_button)

        options_group.add(preferences_row)

        shortcuts_row = Adw.ActionRow()
        shortcuts_row.set_title("Keyboard Shortcuts")
        shortcuts_row.set_subtitle("View available keyboard shortcuts")

        shortcuts_button = Gtk.Button()
        shortcuts_button.set_icon_name("preferences-desktop-keyboard-symbolic")
        shortcuts_button.set_valign(Gtk.Align.CENTER)
        shortcuts_button.add_css_class("flat")
        shortcuts_button.connect("clicked", self._on_shortcuts_clicked)
        shortcuts_row.add_suffix(shortcuts_button)

        options_group.add(shortcuts_row)

        help_group = Adw.PreferencesGroup()
        help_group.set_title("Help Resources")
        help_group.set_description("External documentation and support")
        main_box.append(help_group)

        help_items = [
            ("Paru Documentation", "View official paru documentation", "text-x-generic-symbolic"),
            ("Arch Wiki", "Browse Arch Linux Wiki for AUR information", "applications-internet-symbolic"),
            ("AUR Guidelines", "Read AUR package guidelines", "text-x-generic-symbolic")
        ]

        for title, subtitle, icon in help_items:
            row = Adw.ActionRow()
            row.set_title(title)
            row.set_subtitle(subtitle)

            help_button = Gtk.Button()
            help_button.set_icon_name(icon)
            help_button.set_valign(Gtk.Align.CENTER)
            help_button.add_css_class("flat")
            help_button.connect("clicked", self._on_help_clicked, title)
            row.add_suffix(help_button)

            help_group.add(row)

    def _on_copy_command(self, button, command):
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set_text(command)

        toast = Adw.Toast()
        toast.set_title(f"Copied: {command}")
        toast.set_timeout(2)

        overlay = self.get_content()
        if isinstance(overlay, Adw.ToastOverlay):
            overlay.add_toast(toast)

    def _on_preferences_clicked(self, button):
        pass

    def _on_shortcuts_clicked(self, button):
        pass

    def _on_help_clicked(self, button, resource):
        pass

class PreferencesManager(GObject.Object):
    __gsignals__ = {
        'preference-changed': (GObject.SignalFlags.RUN_LAST, None, (str, object)),
        'category-changed': (GObject.SignalFlags.RUN_LAST, None, (str,)),
        'preferences-reset': (GObject.SignalFlags.RUN_LAST, None, ()),
        'preferences-imported': (GObject.SignalFlags.RUN_LAST, None, ()),
        'preferences-exported': (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(self):
        super().__init__()
        self.settings = None
        self.fallback_storage = {}
        self.preference_definitions = {}
        self.categories = {}
        self.change_callbacks = {}
        self.validation_errors = {}

        self._initialize_schema()
        self._setup_categories()
        self._setup_preference_definitions()
        self._setup_settings()
        self._load_fallback_preferences()

    def _initialize_schema(self):
        try:
            self.settings = Gio.Settings.new("org.gnome.paru-gui")
            self.settings.connect("changed", self._on_settings_changed)
        except Exception:
            self.settings = None

    def _setup_categories(self):
        self.categories = {
            'general': PreferenceCategory(
                name='general',
                title='General',
                description='General application settings'
            ),
            'interface': PreferenceCategory(
                name='interface',
                title='Interface',
                description='User interface preferences'
            ),
            'editor': PreferenceCategory(
                name='editor',
                title='Editor',
                description='Text editor configuration'
            ),
            'updates': PreferenceCategory(
                name='updates',
                title='Updates',
                description='Package update settings'
            ),
            'security': PreferenceCategory(
                name='security',
                title='Security',
                description='Security and verification settings'
            ),
            'aur': PreferenceCategory(
                name='aur',
                title='AUR',
                description='Arch User Repository settings'
            ),
            'advanced': PreferenceCategory(
                name='advanced',
                title='Advanced',
                description='Advanced configuration options'
            ),
            'developer': PreferenceCategory(
                name='developer',
                title='Developer',
                description='Developer mode and debugging options'
            )
        }

    def _setup_preference_definitions(self):
        definitions = [
            PreferenceDefinition(
                key='general.startup_check_updates',
                title='Check for updates on startup',
                description='Automatically check for package updates when the application starts',
                default_value=True,
                value_type=bool,
                category='general'
            ),
            PreferenceDefinition(
                key='general.simplified_mode',
                title='Simplified mode',
                description='Enable simplified interface for basic users',
                default_value=True,
                value_type=bool,
                category='general'
            ),
            PreferenceDefinition(
                key='interface.theme_mode',
                title='Theme mode',
                description='Application color theme preference',
                default_value=ThemeMode.SYSTEM.value,
                value_type=str,
                category='interface'
            ),
            PreferenceDefinition(
                key='editor.default_editor',
                title='Default editor',
                description='Default text editor for editing files',
                default_value=EditorChoice.GEDIT.value,
                value_type=str,
                category='editor'
            ),
            PreferenceDefinition(
                key='security.aur_confidence_level',
                title='AUR confidence level',
                description='Security level for AUR package installation',
                default_value=AURConfidenceLevel.BALANCED.value,
                value_type=str,
                category='security'
            ),
            PreferenceDefinition(
                key='updates.upstream_frequency',
                title='Upstream check frequency',
                description='How often to check for upstream updates',
                default_value=UpstreamFrequency.WEEKLY.value,
                value_type=str,
                category='updates'
            )
        ]

        for definition in definitions:
            self.preference_definitions[definition.key] = definition
            if definition.category in self.categories:
                self.categories[definition.category].preferences.append(definition.key)

    def _setup_settings(self):
        if self.settings:
            self.settings.connect("changed", self._on_settings_changed)

    def _load_fallback_preferences(self):
        fallback_path = os.path.expanduser("~/.config/paru-gui/preferences.json")
        if os.path.exists(fallback_path):
            try:
                with open(fallback_path, 'r') as f:
                    self.fallback_storage = json.load(f)
            except Exception:
                self.fallback_storage = {}

    def _save_fallback_preferences(self):
        os.makedirs(os.path.expanduser("~/.config/paru-gui"), exist_ok=True)
        fallback_path = os.path.expanduser("~/.config/paru-gui/preferences.json")
        try:
            with open(fallback_path, 'w') as f:
                json.dump(self.fallback_storage, f, indent=2)
        except Exception:
            pass

    def _on_settings_changed(self, settings, key):
        self.emit('preference-changed', key, self.get_preference(key))

    def get_bool(self, key: str) -> bool:
        try:
            if self.settings and self.settings.list_keys() and key.replace('.', '-') in self.settings.list_keys():
                return self.settings.get_boolean(key.replace('.', '-'))
        except Exception:
            pass
        
        return self.fallback_storage.get(key, self._get_default_value(key))

    def set_bool(self, key: str, value: bool) -> bool:
        try:
            if self.settings and self.settings.list_keys() and key.replace('.', '-') in self.settings.list_keys():
                return self.settings.set_boolean(key.replace('.', '-'), value)
        except Exception:
            pass
        
        self.fallback_storage[key] = value
        self._save_fallback_preferences()
        self.emit('preference-changed', key, value)
        return True

    def get_string(self, key: str) -> str:
        try:
            if self.settings and self.settings.list_keys() and key.replace('.', '-') in self.settings.list_keys():
                return self.settings.get_string(key.replace('.', '-'))
        except Exception:
            pass
        
        return self.fallback_storage.get(key, self._get_default_value(key))

    def set_string(self, key: str, value: str) -> bool:
        try:
            if self.settings and self.settings.list_keys() and key.replace('.', '-') in self.settings.list_keys():
                return self.settings.set_string(key.replace('.', '-'), value)
        except Exception:
            pass
        
        self.fallback_storage[key] = value
        self._save_fallback_preferences()
        self.emit('preference-changed', key, value)
        return True

    def get_int(self, key: str) -> int:
        try:
            if self.settings and self.settings.list_keys() and key.replace('.', '-') in self.settings.list_keys():
                return self.settings.get_int(key.replace('.', '-'))
        except Exception:
            pass
        
        return self.fallback_storage.get(key, self._get_default_value(key))

    def set_int(self, key: str, value: int) -> bool:
        try:
            if self.settings and self.settings.list_keys() and key.replace('.', '-') in self.settings.list_keys():
                return self.settings.set_int(key.replace('.', '-'), value)
        except Exception:
            pass
        
        self.fallback_storage[key] = value
        self._save_fallback_preferences()
        self.emit('preference-changed', key, value)
        return True

    def get_float(self, key: str) -> float:
        try:
            if self.settings and self.settings.list_keys() and key.replace('.', '-') in self.settings.list_keys():
                return self.settings.get_double(key.replace('.', '-'))
        except Exception:
            pass
        
        return self.fallback_storage.get(key, self._get_default_value(key))

    def set_float(self, key: str, value: float) -> bool:
        try:
            if self.settings and self.settings.list_keys() and key.replace('.', '-') in self.settings.list_keys():
                return self.settings.set_double(key.replace('.', '-'), value)
        except Exception:
            pass
        
        self.fallback_storage[key] = value
        self._save_fallback_preferences()
        self.emit('preference-changed', key, value)
        return True

    def get_list(self, key: str) -> List[str]:
        try:
            if self.settings and self.settings.list_keys() and key.replace('.', '-') in self.settings.list_keys():
                return self.settings.get_strv(key.replace('.', '-'))
        except Exception:
            pass
        
        return self.fallback_storage.get(key, self._get_default_value(key))

    def set_list(self, key: str, value: List[str]) -> bool:
        try:
            if self.settings and self.settings.list_keys() and key.replace('.', '-') in self.settings.list_keys():
                return self.settings.set_strv(key.replace('.', '-'), value)
        except Exception:
            pass
        
        self.fallback_storage[key] = value
        self._save_fallback_preferences()
        self.emit('preference-changed', key, value)
        return True

    def get_preference(self, key: str, default_value: Any = None) -> Any:
        definition = self.preference_definitions.get(key)
        if not definition:
            return default_value

        if definition.value_type == bool:
            return self.get_bool(key)
        elif definition.value_type == int:
            return self.get_int(key)
        elif definition.value_type == float:
            return self.get_float(key)
        elif definition.value_type == list:
            return self.get_list(key)
        else:
            return self.get_string(key)

    def set_preference(self, key: str, value: Any) -> bool:
        definition = self.preference_definitions.get(key)
        if not definition:
            return False

        if definition.value_type == bool:
            return self.set_bool(key, bool(value))
        elif definition.value_type == int:
            return self.set_int(key, int(value))
        elif definition.value_type == float:
            return self.set_float(key, float(value))
        elif definition.value_type == list:
            return self.set_list(key, list(value))
        else:
            return self.set_string(key, str(value))

    def get_simplified_mode(self) -> bool:
        return self.get_preference('general.simplified_mode', True)

    def set_simplified_mode(self, value: bool) -> bool:
        return self.set_preference('general.simplified_mode', value)

    def _get_default_value(self, key: str) -> Any:
        definition = self.preference_definitions.get(key)
        return definition.default_value if definition else None

    def _validate_preference(self, key: str, value: Any) -> bool:
        definition = self.preference_definitions.get(key)
        if not definition:
            return False

        if definition.validator:
            try:
                if not definition.validator(value):
                    return False
            except Exception:
                return False

        if definition.constraints:
            try:
                if 'min' in definition.constraints and value < definition.constraints['min']:
                    return False
                if 'max' in definition.constraints and value > definition.constraints['max']:
                    return False
                if 'choices' in definition.constraints and value not in definition.constraints['choices']:
                    return False
            except Exception:
                return False

        return True

    def get_categories(self) -> Dict[str, PreferenceCategory]:
        return self.categories.copy()

    def get_preferences_for_category(self, category: str) -> List[str]:
        if category in self.categories:
            return self.categories[category].preferences.copy()
        return []

    def get_preference_definition(self, key: str) -> Optional[PreferenceDefinition]:
        return self.preference_definitions.get(key)

    def has_preference(self, key: str) -> bool:
        return key in self.preference_definitions

    def reset_preference(self, key: str) -> bool:
        definition = self.preference_definitions.get(key)
        if not definition:
            return False
        
        return self.set_preference(key, definition.default_value)

    def reset_category(self, category: str) -> bool:
        if category not in self.categories:
            return False
        
        success = True
        for key in self.categories[category].preferences:
            if not self.reset_preference(key):
                success = False
        
        if success:
            self.emit('category-changed', category)
        
        return success

    def reset_all_preferences(self) -> bool:
        success = True
        for key in self.preference_definitions.keys():
            if not self.reset_preference(key):
                success = False

        if success:
            self.emit('preferences-reset')

        return success

    def export_preferences(self, file_path: str) -> bool:
        try:
            export_data = {
                'version': '1.0',
                'preferences': {}
            }

            for key in self.preference_definitions.keys():
                export_data['preferences'][key] = self.get_preference(key)

            with open(file_path, 'w') as f:
                json.dump(export_data, f, indent=2)

            self.emit('preferences-exported', file_path)
            return True
        except Exception:
            return False

    def import_preferences(self, file_path: str) -> bool:
        try:
            with open(file_path, 'r') as f:
                import_data = json.load(f)

            if 'preferences' not in import_data:
                return False

            for key, value in import_data['preferences'].items():
                if self.has_preference(key):
                    self.set_preference(key, value)

            self.emit('preferences-imported')
            return True
        except Exception:
            return False

    def get_preference_summary(self) -> Dict[str, Dict[str, Any]]:
        summary = {}
        for category_name, category in self.categories.items():
            summary[category_name] = {
                'title': category.title,
                'description': category.description,
                'preferences': {}
            }

            for key in category.preferences:
                definition = self.preference_definitions.get(key)
                if definition:
                    summary[category_name]['preferences'][key] = {
                        'title': definition.title,
                        'description': definition.description,
                        'value': self.get_preference(key),
                        'default': definition.default_value,
                        'type': definition.value_type.__name__
                    }

        return summary
