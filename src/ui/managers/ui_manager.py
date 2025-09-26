import os
from typing import Optional, List, Dict, Any, Callable
from gi.repository import Gtk, Gio, GLib, Gdk, GObject, Adw, Pango
from datetime import datetime
from enum import Enum


class ViewType(Enum):
    WELCOME = "welcome"
    CONTENT = "content"
    PROCESSING = "processing"
    SETTINGS = "settings"
    HISTORY = "history"


class NotificationType(Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class UIManager:
    
    def __init__(self, window, builder, preferences_manager=None, history_manager=None):
        self.window = window
        self.builder = builder
        self.preferences_manager = preferences_manager
        self.history_manager = history_manager
        
        self.main_stack: Optional[Gtk.Stack] = None
        self.header_bar: Optional[Adw.HeaderBar] = None
        self.search_entry: Optional[Gtk.SearchEntry] = None
        self.recent_dirs_flowbox: Optional[Gtk.FlowBox] = None
        self.navigation_view: Optional[Adw.NavigationView] = None
        self.toast_overlay: Optional[Adw.ToastOverlay] = None
        self.leaflet: Optional[Adw.Leaflet] = None
        
        self._current_view: ViewType = ViewType.WELCOME
        self._navigation_stack: List[ViewType] = []
        self._view_callbacks: Dict[str, Callable] = {}
        self._dialogs: List[Adw.Dialog] = []
        
        self._setup_ui_components()
        self._setup_shortcuts()

    def _setup_ui_components(self):
        if not self.builder:
            return

        self.main_stack = self.builder.get_object('main_stack')
        self.header_bar = self.builder.get_object('header_bar')
        self.search_entry = self.builder.get_object('search_entry')
        self.recent_dirs_flowbox = self.builder.get_object('recent_dirs_flowbox')
        self.navigation_view = self.builder.get_object('navigation_view')
        self.toast_overlay = self.builder.get_object('toast_overlay')
        self.leaflet = self.builder.get_object('leaflet')
        
        if self.main_stack:
            self.main_stack.connect('notify::visible-child-name', self._on_view_changed)

    def _setup_shortcuts(self):
        if not self.window:
            return
            
        shortcut_controller = Gtk.ShortcutController()
        self.window.add_controller(shortcut_controller)

        shortcuts = [
            ('Escape', self._handle_escape),
            ('<Control>f', self._handle_search_focus),
            ('<Control>comma', self._handle_preferences),
            ('<Alt>Left', self._handle_navigate_back),
            ('<Alt>Right', self._handle_navigate_forward),
            ('<Control>r', self._handle_refresh),
            ('<Control>h', self._handle_home),
            ('<Control>q', self._handle_quit),
            ('F5', self._handle_refresh),
            ('F11', self._handle_fullscreen)
        ]

        for key_combo, callback in shortcuts:
            shortcut = Gtk.Shortcut()
            shortcut.set_trigger(Gtk.ShortcutTrigger.parse_string(key_combo))
            shortcut.set_action(Gtk.CallbackAction.new(callback))
            shortcut_controller.add_shortcut(shortcut)

    def setup_main_interface(self, app_menu_model: Optional[Gio.MenuModel] = None, search_callbacks: Optional[Dict[str, Callable]] = None):
        if self.header_bar:
            self.window.set_titlebar(self.header_bar)

        app_menu_button = self.builder.get_object('app_menu_button') if self.builder else None
        if app_menu_button and app_menu_model:
            app_menu_button.set_menu_model(app_menu_model)

        if self.search_entry and search_callbacks:
            for signal_name, callback in search_callbacks.items():
                if signal_name == 'changed':
                    self.search_entry.connect('search-changed', callback)
                elif signal_name == 'activated':
                    self.search_entry.connect('activate', callback)
                elif signal_name == 'stopped':
                    self.search_entry.connect('search-stopped', callback)
        
        if self.main_stack:
            if self.toast_overlay:
                self.toast_overlay.set_child(self.main_stack)
                self.window.set_content(self.toast_overlay)
            else:
                self.window.set_content(self.main_stack)

    def show_view(self, view_type: ViewType, push_to_stack: bool = True):
        if not self.main_stack:
            return False
            
        if push_to_stack and self._current_view != view_type:
            self._navigation_stack.append(self._current_view)

        self._current_view = view_type
        self.main_stack.set_visible_child_name(view_type.value)

        if view_type.value in self._view_callbacks:
            self._view_callbacks[view_type.value]()

        self._update_navigation_sensitivity()
        self._log_view_change(view_type)
        return True

    def show_welcome_screen(self):
        return self.show_view(ViewType.WELCOME)

    def show_content_view(self):
        return self.show_view(ViewType.CONTENT)

    def show_processing_screen(self, message: str = "Processing...", progress_value: float = -1.0, cancellable: bool = False):
        if not self.show_view(ViewType.PROCESSING, push_to_stack=False):
            return False

        spinner = self.builder.get_object('processing_spinner') if self.builder else None
        label = self.builder.get_object('processing_label') if self.builder else None
        progress_bar = self.builder.get_object('processing_progress') if self.builder else None
        cancel_button = self.builder.get_object('processing_cancel_button') if self.builder else None

        if spinner:
            spinner.set_spinning(True)

        if label:
            label.set_text(message)

        if progress_bar:
            if progress_value >= 0.0:
                progress_bar.set_fraction(min(max(progress_value, 0.0), 1.0))
                progress_bar.set_visible(True)
            else:
                progress_bar.set_visible(False)

        if cancel_button:
            cancel_button.set_visible(cancellable)

        return True

    def update_processing_progress(self, progress_value: float, message: Optional[str] = None):
        if self._current_view != ViewType.PROCESSING:
            return False

        progress_bar = self.builder.get_object('processing_progress') if self.builder else None
        label = self.builder.get_object('processing_label') if self.builder else None

        if progress_bar:
            progress_bar.set_fraction(min(max(progress_value, 0.0), 1.0))
            progress_bar.set_visible(True)

        if message and label:
            label.set_text(message)

        return True

    def hide_processing_screen(self, return_to_previous: bool = True):
        spinner = self.builder.get_object('processing_spinner') if self.builder else None
        if spinner:
            spinner.set_spinning(False)

        if return_to_previous and self._navigation_stack:
            previous_view = self._navigation_stack.pop()
            return self.show_view(previous_view, push_to_stack=False)
        else:
            return self.show_view(ViewType.CONTENT, push_to_stack=False)

    def navigate_back(self) -> bool:
        if self._navigation_stack:
            previous_view = self._navigation_stack.pop()
            self._current_view = previous_view
            if self.main_stack:
                self.main_stack.set_visible_child_name(previous_view.value)
            self._update_navigation_sensitivity()
            return True
        return False

    def navigate_forward(self) -> bool:
        return False

    def navigate_home(self):
        self._navigation_stack.clear()
        return self.show_view(ViewType.WELCOME, push_to_stack=False)

    def can_navigate_back(self) -> bool:
        return len(self._navigation_stack) > 0

    def can_navigate_forward(self) -> bool:
        return False

    def update_window_title(self, title: str, subtitle: Optional[str] = None):
        if self.header_bar:
            self.header_bar.set_title(title)
            if hasattr(self.header_bar, 'set_subtitle') and subtitle:
                self.header_bar.set_subtitle(subtitle)
        else:
            self.window.set_title(title)

    def show_toast(self, message: str, timeout: int = 3, priority: str = "normal"):
        if not self.toast_overlay:
            return False

        toast = Adw.Toast.new(message)
        toast.set_timeout(timeout)

        if priority == "high":
            toast.set_priority(Adw.ToastPriority.HIGH)
        elif priority == "low":
            toast.set_priority(Adw.ToastPriority.LOW)
        else:
            toast.set_priority(Adw.ToastPriority.NORMAL)

        self.toast_overlay.add_toast(toast)
        return True

    def add_notification(self, message: str, notification_type: NotificationType = NotificationType.INFO, timeout: int = 5):
        self.show_toast(message, timeout, "normal" if notification_type == NotificationType.INFO else "high")

        if self.history_manager:
            from ..paru_gui.history_manager import ActionType, ActionStatus, HistoryEntry
            
            status_map = {
                NotificationType.INFO: ActionStatus.INFO,
                NotificationType.SUCCESS: ActionStatus.SUCCESS,
                NotificationType.WARNING: ActionStatus.WARNING,
                NotificationType.ERROR: ActionStatus.FAILED
            }
            
            self.history_manager.add_action(HistoryEntry(
                id=None,
                timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Notification: {message}",
                status=status_map.get(notification_type, ActionStatus.INFO)
            ))

    def setup_navigation_callbacks(self, callbacks: Dict[str, Callable]):
        nav_buttons = {
            'back_button': 'back',
            'forward_button': 'forward',
            'home_button': 'home',
            'up_button': 'up',
            'refresh_button': 'refresh'
        }
        
        for button_name, callback_key in nav_buttons.items():
            button = self.builder.get_object(button_name) if self.builder else None
            if button and callback_key in callbacks:
                button.connect('clicked', lambda btn, cb=callbacks[callback_key]: cb())

    def register_view_callback(self, view_name: str, callback: Callable):
        self._view_callbacks[view_name] = callback

    def update_navigation_sensitivity(self, can_go_back: Optional[bool] = None, can_go_forward: Optional[bool] = None):
        if can_go_back is None:
            can_go_back = self.can_navigate_back()
        if can_go_forward is None:
            can_go_forward = self.can_navigate_forward()

        back_button = self.builder.get_object('back_button') if self.builder else None
        forward_button = self.builder.get_object('forward_button') if self.builder else None
        
        if back_button:
            back_button.set_sensitive(can_go_back)
        if forward_button:
            forward_button.set_sensitive(can_go_forward)

    def _update_navigation_sensitivity(self):
        self.update_navigation_sensitivity()

    def get_main_stack(self) -> Optional[Gtk.Stack]:
        return self.main_stack

    def get_current_view(self) -> ViewType:
        return self._current_view

    def get_current_view_name(self) -> str:
        return self._current_view.value

    def show_dialog(self, dialog: Adw.Dialog) -> bool:
        if not dialog or not self.window:
            return False
        
        self._dialogs.append(dialog)
        dialog.connect('closed', self._on_dialog_closed)
        dialog.present(self.window)
        return True

    def show_error_dialog(self, title: str, message: str, details: Optional[str] = None) -> Adw.MessageDialog:
        dialog = Adw.MessageDialog.new(self.window, title, message)
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        
        if details:
            dialog.set_body_use_markup(True)
            dialog.set_body(f"{message}\n\n<small>{details}</small>")

        self.show_dialog(dialog)
        self._log_dialog_shown("error", title, message)
        return dialog

    def show_info_dialog(self, title: str, message: str) -> Adw.MessageDialog:
        dialog = Adw.MessageDialog.new(self.window, title, message)
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")

        self.show_dialog(dialog)
        self._log_dialog_shown("info", title, message)
        return dialog

    def show_warning_dialog(self, title: str, message: str) -> Adw.MessageDialog:
        dialog = Adw.MessageDialog.new(self.window, title, message)
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        
        self.show_dialog(dialog)
        self._log_dialog_shown("warning", title, message)
        return dialog

    def show_confirmation_dialog(self, title: str, message: str, confirm_text: str = "Confirm", cancel_text: str = "Cancel") -> Adw.MessageDialog:
        dialog = Adw.MessageDialog.new(self.window, title, message)
        dialog.add_response("cancel", cancel_text)
        dialog.add_response("confirm", confirm_text)
        dialog.set_default_response("confirm")
        dialog.set_close_response("cancel")
        
        if "delete" in confirm_text.lower() or "remove" in confirm_text.lower():
            dialog.set_response_appearance("confirm", Adw.ResponseAppearance.DESTRUCTIVE)
        else:
            dialog.set_response_appearance("confirm", Adw.ResponseAppearance.SUGGESTED)

        self.show_dialog(dialog)
        self._log_dialog_shown("confirmation", title, message)
        return dialog

    def show_input_dialog(self, title: str, message: str, placeholder: str = "", input_text: str = "") -> Adw.MessageDialog:
        dialog = Adw.MessageDialog.new(self.window, title, message)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.set_close_response("cancel")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)

        entry = Gtk.Entry()
        entry.set_placeholder_text(placeholder)
        entry.set_text(input_text)
        entry.set_margin_top(12)

        entry.connect('activate', lambda e: dialog.response("ok"))

        dialog.set_extra_child(entry)

        self.show_dialog(dialog)
        self._log_dialog_shown("input", title, message)
        return dialog

    def close_all_dialogs(self):
        for dialog in self._dialogs[:]:
            try:
                dialog.close()
            except:
                pass
        self._dialogs.clear()

    def set_search_mode(self, enabled: bool):
        if self.search_entry:
            if enabled:
                self.search_entry.grab_focus()
            else:
                self.search_entry.set_text("")

    def get_search_text(self) -> str:
        if self.search_entry:
            return self.search_entry.get_text()
        return ""

    def set_search_text(self, text: str):
        if self.search_entry:
            self.search_entry.set_text(text)

    def toggle_sidebar(self):
        if self.leaflet:
            self.leaflet.set_folded(not self.leaflet.get_folded())

    def set_sidebar_visible(self, visible: bool):
        if self.leaflet:
            self.leaflet.set_show_content(visible)

    def is_sidebar_visible(self) -> bool:
        if self.leaflet:
            return self.leaflet.get_show_content()
        return True

    def _on_view_changed(self, stack: Gtk.Stack, param):
        visible_child_name = stack.get_visible_child_name()
        if visible_child_name:
            try:
                self._current_view = ViewType(visible_child_name)
            except ValueError:
                pass

    def _on_dialog_closed(self, dialog: Adw.Dialog):
        if dialog in self._dialogs:
            self._dialogs.remove(dialog)

    def _handle_escape(self, widget, args):
        if self._dialogs:
            self._dialogs[-1].close()
            return True

        if self._current_view == ViewType.PROCESSING:
            return True

        if self.can_navigate_back():
            self.navigate_back()
            return True

        return False

    def _handle_search_focus(self, widget, args):
        self.set_search_mode(True)
        return True

    def _handle_preferences(self, widget, args):
        self.show_view(ViewType.SETTINGS)
        return True

    def _handle_navigate_back(self, widget, args):
        return self.navigate_back()

    def _handle_navigate_forward(self, widget, args):
        return self.navigate_forward()

    def _handle_refresh(self, widget, args):
        refresh_button = self.builder.get_object('refresh_button') if self.builder else None
        if refresh_button:
            refresh_button.activate()
        return True

    def _handle_home(self, widget, args):
        self.navigate_home()
        return True

    def _handle_quit(self, widget, args):
        if hasattr(self.window, 'close'):
            self.window.close()
        return True

    def _handle_fullscreen(self, widget, args):
        if hasattr(self.window, 'is_fullscreen'):
            if self.window.is_fullscreen():
                self.window.unfullscreen()
            else:
                self.window.fullscreen()
        return True

    def _log_view_change(self, view_type: ViewType):
        if self.history_manager:
            from ..paru_gui.history_manager import ActionType, ActionStatus, HistoryEntry
            self.history_manager.add_action(HistoryEntry(
                id=None,
                timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"Navigated to {view_type.value} view",
                status=ActionStatus.INFO
            ))

    def _log_dialog_shown(self, dialog_type: str, title: str, message: str):
        if self.history_manager:
            from ..paru_gui.history_manager import ActionType, ActionStatus, HistoryEntry
            self.history_manager.add_action(HistoryEntry(
                id=None,
                timestamp=datetime.utcnow(),
                action_type=ActionType.UI_INTERACTION,
                summary=f"{dialog_type.title()} dialog shown: {title}",
                status=ActionStatus.INFO,
                details={"message": message}
            ))
