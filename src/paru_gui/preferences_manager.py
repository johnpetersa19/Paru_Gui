import os
import logging
from typing import List, Optional, Any
from gi.repository import Gio, Gtk # Gtk is only for _("...") translation

# Basic logging configuration for this module
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("preferences_manager")

class PreferencesManager:
    """
    Manages application preferences using GSettings.
    Provides methods to get and set various user-configurable options,
    including simplified mode, upstream update settings, AUR trust levels,
    and developer options.
    """

    SCHEMA_ID = 'org.gnome.paru-gui'

    def __init__(self):
        try:
            self.settings = Gio.Settings.new(self.SCHEMA_ID)
            logger.info(f"PreferencesManager initialized with GSettings schema: {self.SCHEMA_ID}")
        except Gio.Error as e:
            logger.critical(f"Failed to initialize GSettings for schema '{self.SCHEMA_ID}': {e}")
            logger.critical("Preferences will not be saved or loaded properly. Ensure schema is installed.")
            # Fallback or raise an error depending on criticality
            raise RuntimeError(f"GSettings initialization failed: {e}")

    def _get_setting(self, key: str, default_value: Any = None) -> Any:
        """Helper to get a setting, handling potential GSettings errors."""
        try:
            # GSettings methods depend on the type in the schema
            schema_type = self.settings.get_value(key).get_type().peek_string()
            if schema_type == 's':
                return self.settings.get_string(key)
            elif schema_type == 'b':
                return self.settings.get_boolean(key)
            elif schema_type == 'i':
                return self.settings.get_int(key)
            elif schema_type == 'as': # Array of strings
                return self.settings.get_strv(key)
            else:
                logger.warning(f"Unknown GSettings type '{schema_type}' for key '{key}'. Returning default.")
                return default_value
        except Gio.Error as e:
            logger.error(f"Error getting GSettings key '{key}': {e}. Returning default: {default_value}")
            return default_value
        except AttributeError: # Happens if key is not found
            logger.error(f"GSettings key '{key}' not found in schema. Returning default: {default_value}")
            return default_value

    def _set_setting(self, key: str, value: Any) -> bool:
        """Helper to set a setting, handling potential GSettings errors."""
        try:
            schema_type = self.settings.get_value(key).get_type().peek_string()
            if schema_type == 's':
                self.settings.set_string(key, value)
            elif schema_type == 'b':
                self.settings.set_boolean(key, value)
            elif schema_type == 'i':
                self.settings.set_int(key, value)
            elif schema_type == 'as':
                # GSettings requires a GLib.Variant for array types
                self.settings.set_strv(key, value)
            else:
                logger.warning(f"Cannot set GSettings key '{key}': Unknown type '{schema_type}'.")
                return False
            logger.debug(f"GSettings key '{key}' set to '{value}'")
            return True
        except Gio.Error as e:
            logger.error(f"Error setting GSettings key '{key}' to '{value}': {e}")
            return False
        except AttributeError:
            logger.error(f"GSettings key '{key}' not found in schema. Cannot set value.")
            return False

    # --- General Settings ---
    def get_default_editor(self) -> str:
        """Returns the configured default text editor."""
        return self._get_setting('default-editor', 'gedit')

    def set_default_editor(self, editor: str) -> bool:
        """Sets the default text editor."""
        return self._set_setting('default-editor', editor)

    def get_simplified_mode(self) -> bool:
        """Returns True if simplified mode is enabled."""
        return self._get_setting('simplified-mode', True)

    def set_simplified_mode(self, enabled: bool) -> bool:
        """Enables or disables simplified mode."""
        return self._set_setting('simplified-mode', enabled)

    def get_recent_directories(self) -> List[str]:
        """Returns a list of recently accessed directories."""
        return self._get_setting('recent-directories', [])

    def add_recent_directory(self, path: str):
        """Adds a path to the list of recent directories, managing its size."""
        recent_dirs = self.get_recent_directories()
        if path in recent_dirs:
            recent_dirs.remove(path) # Move to front if already exists
        recent_dirs.insert(0, path)

        max_recent = self.get_max_recent_directories()
        if len(recent_dirs) > max_recent:
            recent_dirs = recent_dirs[:max_recent] # Trim if over limit

        return self._set_setting('recent-directories', recent_dirs)

    def get_max_recent_directories(self) -> int:
        """Returns the maximum number of recent directories to store."""
        return self._get_setting('max-recent-directories', 10)


    # --- Upstream Update Settings ---
    def get_upstream_check_frequency(self) -> int:
        """Returns the frequency (in hours) for checking upstream updates."""
        return self._get_setting('upstream-check-frequency', 24)

    def set_upstream_check_frequency(self, hours: int) -> bool:
        """Sets the frequency (in hours) for checking upstream updates."""
        if hours < 1:
            logger.warning("Upstream check frequency cannot be less than 1 hour. Setting to 1.")
            hours = 1
        return self._set_setting('upstream-check-frequency', hours)

    def get_ignore_prereleases(self) -> bool:
        """Returns True if pre-release versions should be ignored."""
        return self._get_setting('ignore-prereleases', True)

    def set_ignore_prereleases(self, ignore: bool) -> bool:
        """Sets whether pre-release versions should be ignored."""
        return self._set_setting('ignore-prereleases', ignore)

    def get_ignored_upstream_versions(self) -> List[str]:
        """Returns a list of specific upstream versions to ignore."""
        return self._get_setting('ignored-upstream-versions', [])

    def add_ignored_upstream_version(self, pkgname: str, version: str) -> bool:
        """Adds a specific package version to the ignored list."""
        ignored_versions = self.get_ignored_upstream_versions()
        entry = f"{pkgname}:{version}"
        if entry not in ignored_versions:
            ignored_versions.append(entry)
            return self._set_setting('ignored-upstream-versions', ignored_versions)
        return False # Already ignored

    def remove_ignored_upstream_version(self, pkgname: str, version: str) -> bool:
        """Removes a specific package version from the ignored list."""
        ignored_versions = self.get_ignored_upstream_versions()
        entry = f"{pkgname}:{version}"
        if entry in ignored_versions:
            ignored_versions.remove(entry)
            return self._set_setting('ignored-upstream-versions', ignored_versions)
        return False # Not found

    # --- AUR Trust Settings ---
    def get_show_trust_icons(self) -> bool:
        """Returns True if trust level icons should be displayed for AUR packages."""
        return self._get_setting('show-trust-icons', True)

    def set_show_trust_icons(self, show: bool) -> bool:
        """Sets whether trust level icons should be displayed."""
        return self._set_setting('show-trust-icons', show)

    def get_block_unvoted_packages(self) -> bool:
        """Returns True if installation of packages with no AUR votes should be blocked."""
        return self._get_setting('block-unvoted-packages', False)

    def set_block_unvoted_packages(self, block: bool) -> bool:
        """Sets whether installation of unvoted packages should be blocked."""
        return self._set_setting('block-unvoted-packages', block)

    def get_min_votes_medium_trust(self) -> int:
        """Returns the minimum votes required for a medium trust level."""
        return self._get_setting('min-votes-medium-trust', 10)

    def set_min_votes_medium_trust(self, votes: int) -> bool:
        """Sets the minimum votes required for a medium trust level."""
        if votes < 0: votes = 0
        return self._set_setting('min-votes-medium-trust', votes)

    def get_min_votes_high_trust(self) -> int:
        """Returns the minimum votes required for a high trust level."""
        return self._get_setting('min-votes-high-trust', 50)

    def set_min_votes_high_trust(self, votes: int) -> bool:
        """Sets the minimum votes required for a high trust level."""
        if votes < 0: votes = 0
        return self._set_setting('min-votes-high-trust', votes)

    def get_max_days_since_update_medium_trust(self) -> int:
        """Returns the maximum days since last update for medium trust."""
        return self._get_setting('max-days-since-update-medium-trust', 90)

    def set_max_days_since_update_medium_trust(self, days: int) -> bool:
        """Sets the maximum days since last update for medium trust."""
        if days < 0: days = 0
        return self._set_setting('max-days-since-update-medium-trust', days)

    def get_check_recent_comments(self) -> bool:
        """Returns True if recent AUR comments should be factored into the trust score."""
        return self._get_setting('check-recent-comments', True)

    def set_check_recent_comments(self, check: bool) -> bool:
        """Sets whether recent AUR comments should be factored into the trust score."""
        return self._set_setting('check-recent-comments', check)

    # --- Developer Mode Settings ---
    def get_developer_mode(self) -> bool:
        """Returns True if developer mode features are enabled."""
        return self._get_setting('developer-mode', False)

    def set_developer_mode(self, enabled: bool) -> bool:
        """Enables or disables developer mode."""
        return self._set_setting('developer-mode', enabled)

    def get_clean_after_build(self) -> bool:
        """Returns True if build files should be cleaned after successful compilation."""
        return self._get_setting('clean-after-build', True)

    def set_clean_after_build(self, clean: bool) -> bool:
        """Sets whether build files should be cleaned after compilation."""
        return self._set_setting('clean-after-build', clean)

    def get_show_realtime_terminal(self) -> bool:
        """Returns True if real-time terminal output should be displayed."""
        return self._get_setting('show-realtime-terminal', False)

    def set_show_realtime_terminal(self, show: bool) -> bool:
        """Sets whether real-time terminal output should be displayed."""
        return self._set_setting('show-realtime-terminal', show)

    def get_check_devel_updates(self) -> bool:
        """Returns True if updates for -git, -svn, -hg packages should be checked."""
        return self._get_setting('check-devel-updates', False)

    def set_check_devel_updates(self, check: bool) -> bool:
        """Sets whether updates for development packages should be checked."""
        return self._set_setting('check-devel-updates', check)

    def get_install_debug_packages(self) -> bool:
        """Returns True if debug symbols should be automatically installed."""
        return self._get_setting('install-debug-packages', False)

    def set_install_debug_packages(self, install: bool) -> bool:
        """Sets whether debug symbols should be automatically installed."""
        return self._set_setting('install-debug-packages', install)

    def get_show_detailed_warnings(self) -> bool:
        """Returns True if detailed security warnings should be shown."""
        return self._get_setting('show-detailed-warnings', False)

    def set_show_detailed_warnings(self, show: bool) -> bool:
        """Sets whether detailed security warnings should be shown."""
        return self._set_setting('show-detailed-warnings', show)


# Example Usage (for testing this module directly)
if __name__ == "__main__":
    # Ensure gi is initialized for Gtk/Gio before PreferencesManager
    # In a real app, this is done in main.py
    try:
        import gi
        gi.require_version('Gtk', '4.0')
        gi.require_version('Adw', '1') # Adw is often pulled by Gtk, but good to ensure
    except ValueError as e:
        print(f"GI requirements not met for testing: {e}")
        print("Please ensure you have pygobject installed and GTK/Adwaita libraries are available.")
        print("Skipping direct test of PreferencesManager due to GI environment.")
        exit(1)

    # For direct testing, you might need to compile and install the GSettings schema
    # e.g., `glib-compile-schemas /usr/share/glib-2.0/schemas/`
    # Or mock it. For this test, we assume it's available or GSettings will log an error.

    print("--- Testing PreferencesManager ---")
    prefs = PreferencesManager()

    # Test General Settings
    print(f"\nDefault Editor: {prefs.get_default_editor()}")
    prefs.set_default_editor('code')
    print(f"New Default Editor: {prefs.get_default_editor()}")

    print(f"Simplified Mode: {prefs.get_simplified_mode()}")
    prefs.set_simplified_mode(False)
    print(f"Simplified Mode (set False): {prefs.get_simplified_mode()}")

    print(f"Max Recent Dirs: {prefs.get_max_recent_directories()}")
    prefs.add_recent_directory("/home/user/Projects/Paru_Gui")
    prefs.add_recent_directory("/tmp/aur-builds")
    prefs.add_recent_directory("/home/user/Documents") # This will be at the front
    print(f"Recent Directories: {prefs.get_recent_directories()}")
    prefs.add_recent_directory("/home/user/Projects/Paru_Gui") # Should move to front
    print(f"Recent Directories (moved): {prefs.get_recent_directories()}")


    # Test Upstream Update Settings
    print(f"\nUpstream Check Frequency: {prefs.get_upstream_check_frequency()} hours")
    prefs.set_upstream_check_frequency(12)
    print(f"New Upstream Check Frequency: {prefs.get_upstream_check_frequency()} hours")

    print(f"Ignore Pre-releases: {prefs.get_ignore_prereleases()}")
    prefs.set_ignore_prereleases(False)
    print(f"Ignore Pre-releases (set False): {prefs.get_ignore_prereleases()}")

    prefs.add_ignored_upstream_version("firefox-git", "v1.0.0-rc1")
    prefs.add_ignored_upstream_version("vlc", "3.0.19")
    print(f"Ignored Upstream Versions: {prefs.get_ignored_upstream_versions()}")
    prefs.remove_ignored_upstream_version("firefox-git", "v1.0.0-rc1")
    print(f"Ignored Upstream Versions (after removal): {prefs.get_ignored_upstream_versions()}")


    # Test AUR Trust Settings
    print(f"\nShow Trust Icons: {prefs.get_show_trust_icons()}")
    prefs.set_show_trust_icons(False)
    print(f"Show Trust Icons (set False): {prefs.get_show_trust_icons()}")

    print(f"Min Votes Medium Trust: {prefs.get_min_votes_medium_trust()}")
    prefs.set_min_votes_medium_trust(5)
    print(f"New Min Votes Medium Trust: {prefs.get_min_votes_medium_trust()}")

    print(f"Block Unvoted Packages: {prefs.get_block_unvoted_packages()}")
    prefs.set_block_unvoted_packages(True)
    print(f"Block Unvoted Packages (set True): {prefs.get_block_unvoted_packages()}")


    # Test Developer Mode Settings
    print(f"\nDeveloper Mode: {prefs.get_developer_mode()}")
    prefs.set_developer_mode(True)
    print(f"Developer Mode (set True): {prefs.get_developer_mode()}")

    print(f"Show Real-time Terminal: {prefs.get_show_realtime_terminal()}")
    prefs.set_show_realtime_terminal(True)
    print(f"Show Real-time Terminal (set True): {prefs.get_show_realtime_terminal()}")

    print("\n--- PreferencesManager Test Complete ---")
