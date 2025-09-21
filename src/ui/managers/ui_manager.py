# src/ui/ui_manager.py
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
from typing import Optional, List
from gi.repository import Gtk, Gio, GLib, Gdk, GObject, Adw, Pango
from datetime import datetime

# CORREÇÃO: Importação com 3 pontos para chegar ao src/ corretamente
from ...history_manager import HistoryManager, ActionType, ActionStatus, HistoryEntry
from ...preferences_manager import PreferencesManager


class UIManager:
    """Manages UI elements, navigation and screen transitions."""
    
    def __init__(self, window, builder, preferences_manager, history_manager):
        self.window = window
        self.builder = builder
        self.preferences_manager = preferences_manager
        self.history_manager = history_manager
        
        # UI Components
        self.main_stack = None
        self.header_bar = None
        self.search_entry = None
        self.recent_dirs_flowbox = None
        
        self._setup_ui_components()
        
    def _setup_ui_components(self):
        """Initialize main UI components."""
        self.main_stack = self.builder.get_object('main_stack')
        self.header_bar = self.builder.get_object('header_bar')
        self.search_entry = self.builder.get_object('search_entry')
        self.recent_dirs_flowbox = self.builder.get_object('recent_dirs_flowbox')
        
    def setup_main_interface(self, app_menu_callback=None, search_callbacks=None):
        """Configures the main interface, attaching UI elements."""
        self.window.set_titlebar(self.header_bar)
        
        # Setup app menu
        app_menu_button = self.builder.get_object('app_menu_button')
        if app_menu_button and app_menu_callback:
            app_menu_button.set_menu_model(app_menu_callback())
            
        # Setup search
        if self.search_entry and search_callbacks:
            if 'changed' in search_callbacks:
                self.search_entry.connect('search-changed', search_callbacks['changed'])
            if 'activated' in search_callbacks:
                self.search_entry.connect('activate', search_callbacks['activated'])
                
        self.window.set_child(self.main_stack)
        
    def show_welcome_screen(self):
        """Displays the welcome screen."""
        if self.main_stack:
            self.main_stack.set_visible_child_name("welcome")
            self.history_manager.add_action(HistoryEntry(
                id=None, timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary="Displayed welcome screen",
                status=ActionStatus.INFO
            ))
            
    def show_content_view(self):
        """Displays the content view."""
        if self.main_stack:
            self.main_stack.set_visible_child_name("content")
            
    def show_processing_screen(self, message: str, progress_value: float = -1.0, dialog: Optional[Adw.Dialog] = None):
        """Displays the processing screen."""
        spinner = None
        label = None
        progress_bar = None
        
        # If using a dialog, find elements within it
        if dialog:
            # Assuming dialog has these widgets
            spinner = dialog.get_child() if hasattr(dialog, 'get_child') else None
            # Note: This would need to be adjusted based on actual dialog structure
        else:
            # Use main interface elements
            spinner = self.builder.get_object('processing_spinner')
            label = self.builder.get_object('processing_label')
            progress_bar = self.builder.get_object('processing_progress')
            
        if spinner:
            spinner.set_spinning(True)
            
        if label:
            label.set_text(message)
            
        if progress_bar:
            if progress_value >= 0.0:
                progress_bar.set_fraction(min(progress_value, 1.0))
                progress_bar.set_visible(True)
            else:
                progress_bar.set_visible(False)
                
        # Show processing screen if not using dialog
        if not dialog and self.main_stack:
            self.main_stack.set_visible_child_name("processing")
            
    def hide_processing_screen(self, return_to_screen: str = "content"):
        """Hides the processing screen and returns to specified screen."""
        spinner = self.builder.get_object('processing_spinner')
        if spinner:
            spinner.set_spinning(False)
            
        if self.main_stack:
            self.main_stack.set_visible_child_name(return_to_screen)
            
    def update_window_title(self, title: str):
        """Updates the window title."""
        if self.header_bar:
            self.header_bar.set_title(title)
        else:
            self.window.set_title(title)
            
    def add_notification(self, message: str, notification_type: str = "info"):
        """Adds a notification to the UI."""
        # This would need to be implemented based on your notification system
        # For now, just log the action
        action_type = ActionType.UI_INTERACTION
        status = ActionStatus.INFO
        
        if notification_type == "error":
            status = ActionStatus.FAILED
        elif notification_type == "warning":
            status = ActionStatus.WARNING
        elif notification_type == "success":
            status = ActionStatus.SUCCESS
            
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=action_type,
            summary=f"Notification: {message}",
            status=status
        ))
        
    def setup_navigation_callbacks(self, callbacks: dict):
        """Setup navigation button callbacks."""
        nav_buttons = {
            'back_button': 'back',
            'forward_button': 'forward',
            'home_button': 'home',
            'up_button': 'up'
        }
        
        for button_name, callback_key in nav_buttons.items():
            button = self.builder.get_object(button_name)
            if button and callback_key in callbacks:
                button.connect('clicked', callbacks[callback_key])
                
    def update_navigation_sensitivity(self, can_go_back: bool = True, can_go_forward: bool = True):
        """Updates navigation button sensitivity."""
        back_button = self.builder.get_object('back_button')
        forward_button = self.builder.get_object('forward_button')
        
        if back_button:
            back_button.set_sensitive(can_go_back)
        if forward_button:
            forward_button.set_sensitive(can_go_forward)
            
    def get_main_stack(self):
        """Returns the main stack widget."""
        return self.main_stack
        
    def get_current_view(self) -> Optional[str]:
        """Returns the name of the currently visible view."""
        if self.main_stack:
            return self.main_stack.get_visible_child_name()
        return None
        
    def show_error_dialog(self, title: str, message: str, parent_window=None):
        """Shows an error dialog."""
        if not parent_window:
            parent_window = self.window
            
        dialog = Adw.MessageDialog.new(
            parent_window,
            title,
            message
        )
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.present()
        
        # Log the error
        self.history_manager.add_action(HistoryEntry(
            id=None, timestamp=datetime.utcnow(),
            action_type=ActionType.UI_INTERACTION,
            summary=f"Error dialog shown: {title}",
            status=ActionStatus.FAILED,
            details={"message": message}
        ))
        
    def show_info_dialog(self, title: str, message: str, parent_window=None):
        """Shows an information dialog."""
        if not parent_window:
            parent_window = self.window
            
        dialog = Adw.MessageDialog.new(
            parent_window,
            title,
            message
        )
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.present()
        
    def show_confirmation_dialog(self, title: str, message: str, callback, parent_window=None):
        """Shows a confirmation dialog with Yes/No options."""
        if not parent_window:
            parent_window = self.window
            
        dialog = Adw.MessageDialog.new(
            parent_window,
            title,
            message
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("confirm", "Confirm")
        dialog.set_default_response("confirm")
        dialog.set_close_response("cancel")
        
        def on_response(dialog, response):
            if response == "confirm":
                callback(True)
            else:
                callback(False)
                
        dialog.connect("response", on_response)
        dialog.present()
