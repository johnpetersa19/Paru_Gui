import os
import logging
from typing import List, Optional, Any, Dict
from gi.repository import Gio, Gtk

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("preferences_manager")

class PreferencesManager:
    SCHEMA_ID = 'org.gnome.paru-gui'

    def __init__(self):
        try:
            self.settings = Gio.Settings.new(self.SCHEMA_ID)
            logger.info(f"PreferencesManager initialized with GSettings schema: {self.SCHEMA_ID}")
        except Gio.Error as e:
            logger.critical(f"Failed to initialize GSettings for schema '{self.SCHEMA_ID}': {e}")
            logger.critical("Preferences will not be saved or loaded properly. Ensure schema is installed.")
            raise RuntimeError(f"GSettings initialization failed: {e}")

    def _get_setting(self, key: str, default_value: Any = None) -> Any:
        try:
            schema_type = self.settings.get_value(key).get_type().peek_string()
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
        except Gio.Error as e:
            logger.error(f"Error getting GSettings key '{key}': {e}. Returning default: {default_value}")
            return default_value
        except AttributeError:
            logger.error(f"GSettings key '{key}' not found in schema. Returning default: {default_value}")
            return default_value

    def _set_setting(self, key: str, value: Any) -> bool:
        try:
            schema_type = self.settings.get_value(key).get_type().peek_string()
            if schema_type == 's':
                self.settings.set_string(key, value)
            elif schema_type == 'b':
                self.settings.set_boolean(key, value)
            elif schema_type == 'i':
                self.settings.set_int(key, value)
            elif schema_type == 'as':
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

    def get_default_editor(self) -> str:
        return self._get_setting('default-editor', 'gedit')

    def set_default_editor(self, editor: str) -> bool:
        return self._set_setting('default-editor', editor)

    def get_simplified_mode(self) -> bool:
        return self._get_setting('simplified-mode', True)

    def set_simplified_mode(self, enabled: bool) -> bool:
        return self._set_setting('simplified-mode', enabled)

    def get_recent_directories(self) -> List[str]:
        return self._get_setting('recent-directories', [])

    def add_recent_directory(self, path: str):
        recent_dirs = self.get_recent_directories()
        if path in recent_dirs:
            recent_dirs.remove(path)
        recent_dirs.insert(0, path)

        max_recent = self.get_max_recent_directories()
        if len(recent_dirs) > max_recent:
            recent_dirs = recent_dirs[:max_recent]

        return self._set_setting('recent-directories', recent_dirs)

    def get_max_recent_directories(self) -> int:
        return self._get_setting('max-recent-directories', 10)

    def set_max_recent_directories(self, max_dirs: int) -> bool:
        if max_dirs < 1: max_dirs = 1
        return self._set_setting('max-recent-directories', max_dirs)

    def get_upstream_check_frequency(self) -> int:
        return self._get_setting('upstream-check-frequency', 24)

    def set_upstream_check_frequency(self, hours: int) -> bool:
        if hours < 1:
            logger.warning("Upstream check frequency cannot be less than 1 hour. Setting to 1.")
            hours = 1
        return self._set_setting('upstream-check-frequency', hours)

    def get_ignore_prereleases(self) -> bool:
        return self._get_setting('ignore-prereleases', True)

    def set_ignore_prereleases(self, ignore: bool) -> bool:
        return self._set_setting('ignore-prereleases', ignore)

    def get_ignored_upstream_versions(self) -> List[str]:
        return self._get_setting('ignored-upstream-versions', [])

    def add_ignored_upstream_version(self, pkgname: str, version: str) -> bool:
        ignored_versions = self.get_ignored_upstream_versions()
        entry = f"{pkgname}:{version}"
        if entry not in ignored_versions:
            ignored_versions.append(entry)
            return self._set_setting('ignored-upstream-versions', ignored_versions)
        return False

    def remove_ignored_upstream_version(self, pkgname: str, version: str) -> bool:
        ignored_versions = self.get_ignored_upstream_versions()
        entry = f"{pkgname}:{version}"
        if entry in ignored_versions:
            ignored_versions.remove(entry)
            return self._set_setting('ignored-upstream-versions', ignored_versions)
        return False

    def get_upstream_check_sources(self) -> List[str]:
        return self._get_setting('upstream-check-sources', ['github', 'pypi', 'npmjs', 'gitlab'])

    def set_upstream_check_sources(self, sources: List[str]) -> bool:
        valid_sources = ['github', 'pypi', 'npmjs', 'gitlab', 'aur', 'archlinux', 'custom']
        filtered_sources = [s for s in sources if s in valid_sources]
        return self._set_setting('upstream-check-sources', filtered_sources)

    def get_upstream_timeout(self) -> int:
        return self._get_setting('upstream-timeout', 30)

    def set_upstream_timeout(self, timeout: int) -> bool:
        if timeout < 5: timeout = 5
        if timeout > 300: timeout = 300
        return self._set_setting('upstream-timeout', timeout)

    def get_enable_upstream_notifications(self) -> bool:
        return self._get_setting('enable-upstream-notifications', True)

    def set_enable_upstream_notifications(self, enabled: bool) -> bool:
        return self._set_setting('enable-upstream-notifications', enabled)

    def get_upstream_parallel_checks(self) -> int:
        return self._get_setting('upstream-parallel-checks', 5)

    def set_upstream_parallel_checks(self, parallel: int) -> bool:
        if parallel < 1: parallel = 1
        if parallel > 20: parallel = 20
        return self._set_setting('upstream-parallel-checks', parallel)

    def get_show_trust_icons(self) -> bool:
        return self._get_setting('show-trust-icons', True)

    def set_show_trust_icons(self, show: bool) -> bool:
        return self._set_setting('show-trust-icons', show)

    def get_block_unvoted_packages(self) -> bool:
        return self._get_setting('block-unvoted-packages', False)

    def set_block_unvoted_packages(self, block: bool) -> bool:
        return self._set_setting('block-unvoted-packages', block)

    def get_min_votes_medium_trust(self) -> int:
        return self._get_setting('min-votes-medium-trust', 10)

    def set_min_votes_medium_trust(self, votes: int) -> bool:
        if votes < 0: votes = 0
        return self._set_setting('min-votes-medium-trust', votes)

    def get_min_votes_high_trust(self) -> int:
        return self._get_setting('min-votes-high-trust', 50)

    def set_min_votes_high_trust(self, votes: int) -> bool:
        if votes < 0: votes = 0
        return self._set_setting('min-votes-high-trust', votes)

    def get_max_days_since_update_medium_trust(self) -> int:
        return self._get_setting('max-days-since-update-medium-trust', 90)

    def set_max_days_since_update_medium_trust(self, days: int) -> bool:
        if days < 0: days = 0
        return self._set_setting('max-days-since-update-medium-trust', days)

    def get_check_recent_comments(self) -> bool:
        return self._get_setting('check-recent-comments', True)

    def set_check_recent_comments(self, check: bool) -> bool:
        return self._set_setting('check-recent-comments', check)

    def get_trusted_maintainers(self) -> List[str]:
        return self._get_setting('trusted-maintainers', [])

    def add_trusted_maintainer(self, maintainer: str) -> bool:
        trusted = self.get_trusted_maintainers()
        if maintainer not in trusted:
            trusted.append(maintainer)
            return self._set_setting('trusted-maintainers', trusted)
        return False

    def remove_trusted_maintainer(self, maintainer: str) -> bool:
        trusted = self.get_trusted_maintainers()
        if maintainer in trusted:
            trusted.remove(maintainer)
            return self._set_setting('trusted-maintainers', trusted)
        return False

    def get_developer_mode(self) -> bool:
        return self._get_setting('developer-mode', False)

    def set_developer_mode(self, enabled: bool) -> bool:
        return self._set_setting('developer-mode', enabled)

    def get_clean_after_build(self) -> bool:
        return self._get_setting('clean-after-build', True)

    def set_clean_after_build(self, clean: bool) -> bool:
        return self._set_setting('clean-after-build', clean)

    def get_show_realtime_terminal(self) -> bool:
        return self._get_setting('show-realtime-terminal', False)

    def set_show_realtime_terminal(self, show: bool) -> bool:
        return self._set_setting('show-realtime-terminal', show)

    def get_check_devel_updates(self) -> bool:
        return self._get_setting('check-devel-updates', False)

    def set_check_devel_updates(self, check: bool) -> bool:
        return self._set_setting('check-devel-updates', check)

    def get_install_debug_packages(self) -> bool:
        return self._get_setting('install-debug-packages', False)

    def set_install_debug_packages(self, install: bool) -> bool:
        return self._set_setting('install-debug-packages', install)

    def get_show_detailed_warnings(self) -> bool:
        return self._get_setting('show-detailed-warnings', False)

    def set_show_detailed_warnings(self, show: bool) -> bool:
        return self._set_setting('show-detailed-warnings', show)

    def get_enable_debug_logging(self) -> bool:
        return self._get_setting('enable-debug-logging', False)

    def set_enable_debug_logging(self, enabled: bool) -> bool:
        return self._set_setting('enable-debug-logging', enabled)

    def get_save_build_logs(self) -> bool:
        return self._get_setting('save-build-logs', True)

    def set_save_build_logs(self, save: bool) -> bool:
        return self._set_setting('save-build-logs', save)

    def get_build_logs_directory(self) -> str:
        return self._get_setting('build-logs-directory', '~/.cache/paru-gui/logs')

    def set_build_logs_directory(self, directory: str) -> bool:
        return self._set_setting('build-logs-directory', directory)

    def get_window_width(self) -> int:
        return self._get_setting('window-width', 1000)

    def set_window_width(self, width: int) -> bool:
        if width < 600: width = 600
        return self._set_setting('window-width', width)

    def get_window_height(self) -> int:
        return self._get_setting('window-height', 700)

    def set_window_height(self, height: int) -> bool:
        if height < 400: height = 400
        return self._set_setting('window-height', height)

    def get_window_maximized(self) -> bool:
        return self._get_setting('window-maximized', False)

    def set_window_maximized(self, maximized: bool) -> bool:
        return self._set_setting('window-maximized', maximized)

    def get_theme_variant(self) -> str:
        return self._get_setting('theme-variant', 'default')

    def set_theme_variant(self, variant: str) -> bool:
        valid_variants = ['default', 'light', 'dark']
        if variant not in valid_variants:
            variant = 'default'
        return self._set_setting('theme-variant', variant)

    def is_first_run(self) -> bool:
        return self._get_setting('first-run', True)

    def set_first_run(self, is_first: bool) -> bool:
        success = self._set_setting('first-run', is_first)
        if success:
            logger.info(f"First run set to: {is_first}")
        return success

    def get_all_preferences(self) -> Dict[str, Any]:
        try:
            return {
                'simplified_mode': self.get_simplified_mode(),
                'default_editor': self.get_default_editor(),
                'recent_directories': self.get_recent_directories(),
                'max_recent_directories': self.get_max_recent_directories(),
                'upstream_check_frequency': self.get_upstream_check_frequency(),
                'ignore_prereleases': self.get_ignore_prereleases(),
                'upstream_check_sources': self.get_upstream_check_sources(),
                'upstream_timeout': self.get_upstream_timeout(),
                'enable_upstream_notifications': self.get_enable_upstream_notifications(),
                'upstream_parallel_checks': self.get_upstream_parallel_checks(),
                'show_trust_icons': self.get_show_trust_icons(),
                'block_unvoted_packages': self.get_block_unvoted_packages(),
                'min_votes_medium_trust': self.get_min_votes_medium_trust(),
                'min_votes_high_trust': self.get_min_votes_high_trust(),
                'max_days_since_update_medium_trust': self.get_max_days_since_update_medium_trust(),
                'check_recent_comments': self.get_check_recent_comments(),
                'trusted_maintainers': self.get_trusted_maintainers(),
                'developer_mode': self.get_developer_mode(),
                'clean_after_build': self.get_clean_after_build(),
                'show_realtime_terminal': self.get_show_realtime_terminal(),
                'check_devel_updates': self.get_check_devel_updates(),
                'install_debug_packages': self.get_install_debug_packages(),
                'show_detailed_warnings': self.get_show_detailed_warnings(),
                'enable_debug_logging': self.get_enable_debug_logging(),
                'save_build_logs': self.get_save_build_logs(),
                'build_logs_directory': self.get_build_logs_directory(),
                'window_width': self.get_window_width(),
                'window_height': self.get_window_height(),
                'window_maximized': self.get_window_maximized(),
                'theme_variant': self.get_theme_variant(),
                'first_run': self.is_first_run()
            }
        except Exception as e:
            logger.error(f"Error getting all preferences: {e}")
            return {}

    def set_preference(self, key: str, value: Any) -> bool:
        try:
            method_map = {
                'simplified_mode': self.set_simplified_mode,
                'default_editor': self.set_default_editor,
                'max_recent_directories': self.set_max_recent_directories,
                'upstream_check_frequency': self.set_upstream_check_frequency,
                'ignore_prereleases': self.set_ignore_prereleases,
                'upstream_check_sources': self.set_upstream_check_sources,
                'upstream_timeout': self.set_upstream_timeout,
                'enable_upstream_notifications': self.set_enable_upstream_notifications,
                'upstream_parallel_checks': self.set_upstream_parallel_checks,
                'show_trust_icons': self.set_show_trust_icons,
                'block_unvoted_packages': self.set_block_unvoted_packages,
                'min_votes_medium_trust': self.set_min_votes_medium_trust,
                'min_votes_high_trust': self.set_min_votes_high_trust,
                'max_days_since_update_medium_trust': self.set_max_days_since_update_medium_trust,
                'check_recent_comments': self.set_check_recent_comments,
                'developer_mode': self.set_developer_mode,
                'clean_after_build': self.set_clean_after_build,
                'show_realtime_terminal': self.set_show_realtime_terminal,
                'check_devel_updates': self.set_check_devel_updates,
                'install_debug_packages': self.set_install_debug_packages,
                'show_detailed_warnings': self.set_show_detailed_warnings,
                'enable_debug_logging': self.set_enable_debug_logging,
                'save_build_logs': self.set_save_build_logs,
                'build_logs_directory': self.set_build_logs_directory,
                'window_width': self.set_window_width,
                'window_height': self.set_window_height,
                'window_maximized': self.set_window_maximized,
                'theme_variant': self.set_theme_variant,
                'first_run': self.set_first_run
            }

            if key in method_map:
                return method_map[key](value)

            if key == 'recent_directories':
                return self._set_recent_directories(value)
            elif key == 'trusted_maintainers':
                return self._set_setting('trusted-maintainers', value)
            else:
                return self._set_setting(key.replace('_', '-'), value)

        except Exception as e:
            logger.error(f"Error setting preference {key}: {e}")
            return False

    def _set_recent_directories(self, directories: List[str]) -> bool:
        try:
            max_dirs = self.get_max_recent_directories()
            unique_dirs = []
            seen = set()

            for directory in directories:
                if directory not in seen and os.path.exists(directory):
                    unique_dirs.append(directory)
                    seen.add(directory)
                    if len(unique_dirs) >= max_dirs:
                        break

            return self._set_setting('recent-directories', unique_dirs)
        except Exception as e:
            logger.error(f"Error setting recent directories: {e}")
            return False

    def reset_to_defaults(self) -> bool:
        try:
            defaults = {
                'simplified-mode': True,
                'default-editor': 'gedit',
                'recent-directories': [],
                'max-recent-directories': 10,
                'upstream-check-frequency': 24,
                'ignore-prereleases': True,
                'upstream-check-sources': ['github', 'pypi', 'npmjs', 'gitlab'],
                'upstream-timeout': 30,
                'enable-upstream-notifications': True,
                'upstream-parallel-checks': 5,
                'show-trust-icons': True,
                'block-unvoted-packages': False,
                'min-votes-medium-trust': 10,
                'min-votes-high-trust': 50,
                'max-days-since-update-medium-trust': 90,
                'check-recent-comments': True,
                'trusted-maintainers': [],
                'developer-mode': False,
                'clean-after-build': True,
                'show-realtime-terminal': False,
                'check-devel-updates': False,
                'install-debug-packages': False,
                'show-detailed-warnings': False,
                'enable-debug-logging': False,
                'save-build-logs': True,
                'build-logs-directory': '~/.cache/paru-gui/logs',
                'window-width': 1000,
                'window-height': 700,
                'window-maximized': False,
                'theme-variant': 'default',
                'first-run': True
            }

            for key, value in defaults.items():
                self._set_setting(key, value)

            logger.info("All preferences reset to defaults")
            return True
        except Exception as e:
            logger.error(f"Error resetting preferences to defaults: {e}")
            return False

    def export_preferences(self, file_path: str) -> bool:
        try:
            import json
            prefs = self.get_all_preferences()
            with open(file_path, 'w') as f:
                json.dump(prefs, f, indent=2)
            logger.info(f"Preferences exported to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error exporting preferences: {e}")
            return False

    def import_preferences(self, file_path: str) -> bool:
        try:
            import json
            with open(file_path, 'r') as f:
                prefs = json.load(f)
            
            for key, value in prefs.items():
                self.set_preference(key, value)
            
            logger.info(f"Preferences imported from {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error importing preferences: {e}")
            return False

if __name__ == "__main__":
    try:
        import gi
        gi.require_version('Gtk', '4.0')
        gi.require_version('Adw', '1')
    except ValueError as e:
        print(f"GI requirements not met for testing: {e}")
        print("Please ensure you have pygobject installed and GTK/Adwaita libraries are available.")
        print("Skipping direct test of PreferencesManager due to GI environment.")
        exit(1)

    print("--- Testing PreferencesManager ---")
    prefs = PreferencesManager()

    print(f"\nDefault Editor: {prefs.get_default_editor()}")
    prefs.set_default_editor('code')
    print(f"New Default Editor: {prefs.get_default_editor()}")

    print(f"Simplified Mode: {prefs.get_simplified_mode()}")
    prefs.set_simplified_mode(False)
    print(f"Simplified Mode (set False): {prefs.get_simplified_mode()}")

    print(f"Max Recent Dirs: {prefs.get_max_recent_directories()}")
    prefs.add_recent_directory("/home/user/Projects/Paru_Gui")
    prefs.add_recent_directory("/tmp/aur-builds")
    prefs.add_recent_directory("/home/user/Documents")
    print(f"Recent Directories: {prefs.get_recent_directories()}")

    print(f"\nUpstream Check Frequency: {prefs.get_upstream_check_frequency()} hours")
    prefs.set_upstream_check_frequency(12)
    print(f"New Upstream Check Frequency: {prefs.get_upstream_check_frequency()} hours")

    print(f"Ignore Pre-releases: {prefs.get_ignore_prereleases()}")
    prefs.set_ignore_prereleases(False)
    print(f"Ignore Pre-releases (set False): {prefs.get_ignore_prereleases()}")

    prefs.add_ignored_upstream_version("firefox-git", "v1.0.0-rc1")
    prefs.add_ignored_upstream_version("vlc", "3.0.19")
    print(f"Ignored Upstream Versions: {prefs.get_ignored_upstream_versions()}")

    print(f"\nShow Trust Icons: {prefs.get_show_trust_icons()}")
    prefs.set_show_trust_icons(False)
    print(f"Show Trust Icons (set False): {prefs.get_show_trust_icons()}")

    print(f"Min Votes Medium Trust: {prefs.get_min_votes_medium_trust()}")
    prefs.set_min_votes_medium_trust(5)
    print(f"New Min Votes Medium Trust: {prefs.get_min_votes_medium_trust()}")

    print(f"\nDeveloper Mode: {prefs.get_developer_mode()}")
    prefs.set_developer_mode(True)
    print(f"Developer Mode (set True): {prefs.get_developer_mode()}")

    print(f"\nFirst Run: {prefs.is_first_run()}")
    prefs.set_preference('first_run', False)
    print(f"First Run (after set_preference): {prefs.is_first_run()}")

    print(f"\nAll preferences: {len(prefs.get_all_preferences())} settings loaded")

    print("\n--- PreferencesManager Test Complete ---")
