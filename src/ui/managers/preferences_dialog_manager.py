# src/ui/preferences_manager.py
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

from gi.repository import Gtk, Adw


class PreferencesDialogManager:
    """Manages the preferences dialog and its callbacks."""
    
    def __init__(self, window, builder, preferences_manager):
        self.window = window
        self.builder = builder
        self.preferences_manager = preferences_manager
        
    def show_preferences_dialog(self):
        """Shows the preferences dialog."""
        prefs_dialog = self.builder.get_object('preferences_dialog')
        if not prefs_dialog:
            # Create new instance if not exists
            prefs_dialog = Gtk.Builder.get_template(
                self.window.__class__, 'preferences_dialog'
            ).new_with_values([('transient-for', self.window), ('modal', True)])
            self.builder.expose_widget(prefs_dialog, 'preferences_dialog')
            
        prefs_dialog.set_transient_for(self.window)
        prefs_dialog.set_modal(True)
        
        # Connect controls on the dialog instance
        self._connect_preference_controls(prefs_dialog)
        
        # Load current settings
        self._load_preferences_to_dialog(prefs_dialog)
        
        prefs_dialog.present()
        
    def _connect_preference_controls(self, dialog):
        """Connects preference control callbacks."""
        # Editor combo
        editor_combo = self.builder.get_object('editor_combo', dialog)
        if editor_combo and not hasattr(editor_combo, '_connected'):
            editor_combo.connect('changed', self._on_editor_combo_changed)
            editor_combo._connected = True
            
        # Simplified mode switch
        simplified_mode_switch = self.builder.get_object('simplified_mode_switch', dialog)
        if simplified_mode_switch and not hasattr(simplified_mode_switch, '_connected'):
            simplified_mode_switch.connect('notify::active', self._on_simplified_mode_toggled)
            simplified_mode_switch._connected = True
            
        # Trust icons switch
        trust_icons_switch = self.builder.get_object('trust_icons_switch', dialog)
        if trust_icons_switch and not hasattr(trust_icons_switch, '_connected'):
            trust_icons_switch.connect('notify::active', self._on_trust_icons_toggled)
            trust_icons_switch._connected = True
            
        # Block unvoted switch
        block_unvoted_switch = self.builder.get_object('block_unvoted_switch', dialog)
        if block_unvoted_switch and not hasattr(block_unvoted_switch, '_connected'):
            block_unvoted_switch.connect('notify::active', self._on_block_unvoted_toggled)
            block_unvoted_switch._connected = True
            
        # Clean after build switch
        clean_after_build_switch = self.builder.get_object('clean_after_build_switch', dialog)
        if clean_after_build_switch and not hasattr(clean_after_build_switch, '_connected'):
            clean_after_build_switch.connect('notify::active', self._on_clean_after_build_toggled)
            clean_after_build_switch._connected = True
            
        # Terminal switch
        terminal_switch = self.builder.get_object('terminal_switch', dialog)
        if terminal_switch and not hasattr(terminal_switch, '_connected'):
            terminal_switch.connect('notify::active', self._on_show_realtime_terminal_toggled)
            terminal_switch._connected = True
            
        # Close button
        prefs_close_button = self.builder.get_object('prefs_close_button', dialog)
        if prefs_close_button and not hasattr(prefs_close_button, '_connected'):
            prefs_close_button.connect('clicked', lambda btn: dialog.close())
            prefs_close_button._connected = True
            
    def _load_preferences_to_dialog(self, dialog: Gtk.Dialog):
        """Populates the preferences dialog with current settings."""
        if not self.preferences_manager:
            return
            
        # Load editor setting
        editor_combo = self.builder.get_object('editor_combo', dialog)
        if editor_combo:
            editor_combo.set_active_id(self.preferences_manager.get_default_editor())
            
        # Load simplified mode setting
        simplified_mode_switch = self.builder.get_object('simplified_mode_switch', dialog)
        if simplified_mode_switch:
            simplified_mode_switch.set_active(self.preferences_manager.get_simplified_mode())
            
        # Load trust icons setting
        trust_icons_switch = self.builder.get_object('trust_icons_switch', dialog)
        if trust_icons_switch:
            trust_icons_switch.set_active(self.preferences_manager.get_show_trust_icons())
            
        # Load block unvoted setting
        block_unvoted_switch = self.builder.get_object('block_unvoted_switch', dialog)
        if block_unvoted_switch:
            block_unvoted_switch.set_active(self.preferences_manager.get_block_unvoted_packages())
            
        # Load clean after build setting
        clean_after_build_switch = self.builder.get_object('clean_after_build_switch', dialog)
        if clean_after_build_switch:
            clean_after_build_switch.set_active(self.preferences_manager.get_clean_after_build())
            
        # Load terminal setting
        terminal_switch = self.builder.get_object('terminal_switch', dialog)
        if terminal_switch:
            terminal_switch.set_active(self.preferences_manager.get_show_realtime_terminal())
            
    # Preference callback methods
    def _on_editor_combo_changed(self, combo: Gtk.ComboBoxText):
        """Handles editor selection change."""
        if self.preferences_manager:
            self.preferences_manager.set_default_editor(combo.get_active_id())
            print(f"Default editor set to: {combo.get_active_id()}")
            
    def _on_simplified_mode_toggled(self, switch: Gtk.Switch, gparam):
        """Handles simplified mode toggle."""
        if self.preferences_manager:
            self.preferences_manager.set_simplified_mode(switch.get_active())
            print(f"Simplified mode toggled: {switch.get_active()}")
            # Re-scan to reflect changes in UI
            if hasattr(self.window, 'file_operations'):
                self.window.file_operations.start_scan_compatible_files_async(
                    self.window.current_path
                )
                
    def _on_trust_icons_toggled(self, switch: Gtk.Switch, gparam):
        """Handles trust icons toggle."""
        if self.preferences_manager:
            self.preferences_manager.set_show_trust_icons(switch.get_active())
            print(f"Show trust icons toggled: {switch.get_active()}")
            # Re-scan to reflect changes in UI
            if hasattr(self.window, 'file_operations'):
                self.window.file_operations.start_scan_compatible_files_async(
                    self.window.current_path
                )
                
    def _on_block_unvoted_toggled(self, switch: Gtk.Switch, gparam):
        """Handles block unvoted packages toggle."""
        if self.preferences_manager:
            self.preferences_manager.set_block_unvoted_packages(switch.get_active())
            print(f"Block unvoted packages toggled: {switch.get_active()}")
            
    def _on_clean_after_build_toggled(self, switch: Gtk.Switch, gparam):
        """Handles clean after build toggle."""
        if self.preferences_manager:
            self.preferences_manager.set_clean_after_build(switch.get_active())
            print(f"Clean after build toggled: {switch.get_active()}")
            
    def _on_show_realtime_terminal_toggled(self, switch: Gtk.Switch, gparam):
        """Handles real-time terminal toggle."""
        if self.preferences_manager:
            active = switch.get_active()
            self.preferences_manager.set_show_realtime_terminal(active)
            print(f"Show real-time terminal toggled: {active}")
            
            # Update terminal manager visibility
            if hasattr(self.window, 'terminal_manager'):
                if active:
                    self.window.terminal_manager.show_terminal_panel()
                else:
                    self.window.terminal_manager.hide_terminal_panel()
