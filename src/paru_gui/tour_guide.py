import os
import sys
from typing import Optional, List, Dict, Any, Callable
from gi.repository import Gtk, Gio, GLib, Adw, Gdk

class TourGuide:
    SCHEMA_ID = 'org.gnome.paru-gui'
    TOUR_COMPLETED_KEY = 'tour-completed'
    SIMPLIFIED_MODE_KEY = 'simplified-mode'
    SHOW_TOOLTIPS_KEY = 'show-tooltips'
    ANIMATION_SPEED_KEY = 'animation-speed'

    def __init__(self, parent_window: Gtk.Window, builder: Gtk.Builder, preferences_manager: Optional[Any] = None):
        self.parent_window = parent_window
        self.builder = builder
        self.preferences_manager = preferences_manager
        self.settings = None
        self.current_tour_step = -1
        self.tour_steps = []
        self.active_popover = None
        self.tour_overlay = None
        self.animation_duration = 300
        self.step_callbacks = {}
        
        self._initialize_settings()
        self._setup_tour_overlay()
        self._register_shortcuts()

    def _initialize_settings(self):
        if self.preferences_manager and hasattr(self.preferences_manager, 'settings'):
            self.settings = self.preferences_manager.settings
        else:
            try:
                self.settings = Gio.Settings.new(self.SCHEMA_ID)
            except Exception:
                self.settings = None

    def _setup_tour_overlay(self):
        self.tour_overlay = Gtk.Overlay()
        self.tour_overlay.set_child(self.parent_window.get_child())
        self.parent_window.set_child(self.tour_overlay)

    def _register_shortcuts(self):
        shortcut_controller = Gtk.ShortcutController()
        shortcut_controller.set_scope(Gtk.ShortcutScope.GLOBAL)
        
        help_shortcut = Gtk.Shortcut()
        help_shortcut.set_trigger(Gtk.ShortcutTrigger.parse_string("F1"))
        help_shortcut.set_action(Gtk.CallbackAction.new(self._on_help_shortcut))
        shortcut_controller.add_shortcut(help_shortcut)
        
        tour_shortcut = Gtk.Shortcut()
        tour_shortcut.set_trigger(Gtk.ShortcutTrigger.parse_string("<Control>h"))
        tour_shortcut.set_action(Gtk.CallbackAction.new(self._on_tour_shortcut))
        shortcut_controller.add_shortcut(tour_shortcut)
        
        self.parent_window.add_controller(shortcut_controller)

    def _get_setting(self, key: str, default_value: Any) -> Any:
        if not self.settings:
            return default_value
            
        try:
            value = self.settings.get_value(key)
            if value.get_type_string() == 'b':
                return value.get_boolean()
            elif value.get_type_string() == 's':
                return value.get_string()
            elif value.get_type_string() == 'i':
                return value.get_int32()
            elif value.get_type_string() == 'd':
                return value.get_double()
            return value.unpack()
        except Exception:
            return default_value

    def _set_setting(self, key: str, value: Any):
        if not self.settings:
            return
            
        try:
            if isinstance(value, bool):
                variant = GLib.Variant.new_boolean(value)
            elif isinstance(value, str):
                variant = GLib.Variant.new_string(value)
            elif isinstance(value, int):
                variant = GLib.Variant.new_int32(value)
            elif isinstance(value, float):
                variant = GLib.Variant.new_double(value)
            else:
                variant = GLib.Variant.new_string(str(value))
            
            self.settings.set_value(key, variant)
        except Exception:
            pass

    def is_tour_completed(self) -> bool:
        return self._get_setting(self.TOUR_COMPLETED_KEY, False)

    def set_tour_completed(self, completed: bool):
        self._set_setting(self.TOUR_COMPLETED_KEY, completed)

    def is_simplified_mode_enabled(self) -> bool:
        return self._get_setting(self.SIMPLIFIED_MODE_KEY, True)

    def get_animation_speed(self) -> str:
        return self._get_setting(self.ANIMATION_SPEED_KEY, 'normal')

    def should_show_tooltips(self) -> bool:
        return self._get_setting(self.SHOW_TOOLTIPS_KEY, True)

    def show_initial_tour(self):
        if self.is_tour_completed():
            return

        self.set_tour_completed(False)
        self._prepare_tour_steps()
        self.current_tour_step = 0
        self._show_tour_step(self.current_tour_step)

    def restart_tour(self):
        self.set_tour_completed(False)
        self.show_initial_tour()

    def _prepare_tour_steps(self):
        simplified_mode = self.is_simplified_mode_enabled()
        
        self.tour_steps = [
            {
                "id": "welcome",
                "title": "Welcome to Paru GUI",
                "message": "This interactive tour will guide you through the main features of Paru GUI, your secure AUR package manager.",
                "ui_element_id": None,
                "icon": "dialog-information-symbolic",
                "position": "center",
                "duration": 5000,
                "buttons": ["next", "skip"]
            },
            {
                "id": "file_selection",
                "title": "Select Files and Folders",
                "message": "Start by selecting PKGBUILD files, packages, or folders containing compatible files.",
                "ui_element_id": "select_folder_button",
                "icon": "document-open-symbolic",
                "position": "bottom",
                "duration": 4000,
                "buttons": ["next", "previous", "skip"]
            },
            {
                "id": "smart_visualization",
                "title": "Smart File Visualization",
                "message": "View organized cards for PKGBUILDs, packages, and patches with detailed information.",
                "ui_element_id": "content_cards",
                "icon": "folder-open-symbolic",
                "position": "top",
                "duration": 4000,
                "buttons": ["next", "previous", "skip"]
            }
        ]

        if not simplified_mode:
            advanced_steps = [
                {
                    "id": "security_review",
                    "title": "Advanced Security Analysis",
                    "message": "Access detailed security reviews with risk assessment and vulnerability scanning.",
                    "ui_element_id": "security_button",
                    "icon": "system-search-symbolic",
                    "position": "right",
                    "duration": 5000,
                    "buttons": ["next", "previous", "skip"]
                },
                {
                    "id": "sandbox_operations",
                    "title": "Sandboxed Operations",
                    "message": "Execute package building and installation in isolated, secure environments.",
                    "ui_element_id": "sandbox_expander",
                    "icon": "security-high-symbolic",
                    "position": "left",
                    "duration": 4000,
                    "buttons": ["next", "previous", "skip"]
                },
                {
                    "id": "custom_rules",
                    "title": "Custom Security Rules",
                    "message": "Create and manage custom security rules and exclusion patterns.",
                    "ui_element_id": "rules_editor",
                    "icon": "preferences-system-symbolic",
                    "position": "bottom",
                    "duration": 4000,
                    "buttons": ["next", "previous", "skip"]
                }
            ]
            self.tour_steps.extend(advanced_steps)

        final_steps = [
            {
                "id": "terminal_output",
                "title": "Real-time Terminal Output",
                "message": "Monitor command execution with live output, filtering, and log management.",
                "ui_element_id": "terminal_area",
                "icon": "utilities-terminal-symbolic",
                "position": "top",
                "duration": 4000,
                "buttons": ["next", "previous", "skip"]
            },
            {
                "id": "keyboard_shortcuts",
                "title": "Keyboard Shortcuts",
                "message": "Press F1 anytime for keyboard shortcuts, or Ctrl+H to restart this tour.",
                "ui_element_id": "help_button",
                "icon": "input-keyboard-symbolic",
                "position": "bottom",
                "duration": 4000,
                "buttons": ["next", "previous", "skip"]
            },
            {
                "id": "completion",
                "title": "Tour Complete!",
                "message": "You're ready to manage AUR packages securely. Explore the interface and discover more features!",
                "ui_element_id": None,
                "icon": "emblem-ok-symbolic",
                "position": "center",
                "duration": 3000,
                "buttons": ["finish", "restart"]
            }
        ]
        self.tour_steps.extend(final_steps)

        for i, step in enumerate(self.tour_steps):
            step["step_number"] = i + 1
            step["total_steps"] = len(self.tour_steps)

    def _show_tour_step(self, step_index: int):
        if not (0 <= step_index < len(self.tour_steps)):
            self._finish_tour()
            return

        if self.active_popover:
            self.active_popover.popdown()
            self.active_popover = None

        step = self.tour_steps[step_index]
        
        if step["ui_element_id"]:
            target_element = self._find_ui_element(step["ui_element_id"])
            if target_element:
                self._show_popover_step(step, target_element)
            else:
                self._show_toast_step(step)
        else:
            self._show_modal_step(step)

        self._highlight_element(step.get("ui_element_id"))

    def _show_popover_step(self, step: Dict[str, Any], target_element: Gtk.Widget):
        popover = Gtk.Popover()
        popover.set_parent(target_element)
        popover.set_position(self._get_popover_position(step["position"]))
        popover.set_autohide(False)
        popover.set_has_arrow(True)
        
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(16)
        content_box.set_margin_bottom(16)
        content_box.set_margin_start(16)
        content_box.set_margin_end(16)
        
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        if step["icon"]:
            icon = Gtk.Image.new_from_icon_name(step["icon"])
            icon.set_icon_size(Gtk.IconSize.LARGE)
            header_box.append(icon)
        
        title_label = Gtk.Label()
        title_label.set_markup(f"<b>{step['title']}</b>")
        title_label.set_halign(Gtk.Align.START)
        header_box.append(title_label)
        
        progress_label = Gtk.Label()
        progress_label.set_markup(f"<small>{step['step_number']}/{step['total_steps']}</small>")
        progress_label.set_halign(Gtk.Align.END)
        progress_label.set_hexpand(True)
        header_box.append(progress_label)
        
        content_box.append(header_box)
        
        message_label = Gtk.Label()
        message_label.set_text(step["message"])
        message_label.set_wrap(True)
        message_label.set_max_width_chars(50)
        message_label.set_halign(Gtk.Align.START)
        content_box.append(message_label)
        
        button_box = self._create_tour_buttons(step["buttons"])
        content_box.append(button_box)
        
        popover.set_child(content_box)
        popover.popup()
        
        self.active_popover = popover
        
        if step["duration"] > 0:
            GLib.timeout_add(step["duration"], self._auto_advance_step)

    def _show_toast_step(self, step: Dict[str, Any]):
        toast = Adw.Toast.new(step["message"])
        toast.set_title(step["title"])
        toast.set_timeout(step["duration"] // 1000)
        toast.set_priority(Adw.ToastPriority.HIGH)
        
        if step["icon"]:
            toast.set_icon_name(step["icon"])
        
        next_button = Gtk.Button.new_with_label("Next")
        next_button.connect("clicked", lambda b: self._advance_tour())
        next_button.add_css_class("suggested-action")
        toast.set_action_name("tour.next")
        
        skip_button = Gtk.Button.new_with_label("Skip")
        skip_button.connect("clicked", lambda b: self._finish_tour(skipped=True))
        toast.set_action_name("tour.skip")
        
        self._get_toast_overlay().add_toast(toast)

    def _show_modal_step(self, step: Dict[str, Any]):
        dialog = Adw.MessageDialog(
            transient_for=self.parent_window,
            heading=step["title"],
            body=step["message"]
        )
        
        if "finish" in step["buttons"]:
            dialog.add_response("finish", "Finish")
            dialog.set_response_appearance("finish", Adw.ResponseAppearance.SUGGESTED)
        
        if "restart" in step["buttons"]:
            dialog.add_response("restart", "Restart Tour")
        
        if "next" in step["buttons"]:
            dialog.add_response("next", "Next")
            dialog.set_response_appearance("next", Adw.ResponseAppearance.SUGGESTED)
        
        if "skip" in step["buttons"]:
            dialog.add_response("skip", "Skip Tour")
        
        dialog.connect("response", self._on_modal_response)
        dialog.present()

    def _create_tour_buttons(self, button_types: List[str]) -> Gtk.Box:
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)
        
        for button_type in button_types:
            if button_type == "previous":
                button = Gtk.Button.new_with_label("Previous")
                button.connect("clicked", lambda b: self._previous_step())
                button.set_sensitive(self.current_tour_step > 0)
            elif button_type == "next":
                button = Gtk.Button.new_with_label("Next")
                button.connect("clicked", lambda b: self._advance_tour())
                button.add_css_class("suggested-action")
            elif button_type == "skip":
                button = Gtk.Button.new_with_label("Skip Tour")
                button.connect("clicked", lambda b: self._finish_tour(skipped=True))
            elif button_type == "finish":
                button = Gtk.Button.new_with_label("Finish")
                button.connect("clicked", lambda b: self._finish_tour())
                button.add_css_class("suggested-action")
            elif button_type == "restart":
                button = Gtk.Button.new_with_label("Restart")
                button.connect("clicked", lambda b: self.restart_tour())
            else:
                continue
            
            button_box.append(button)
        
        return button_box

    def _find_ui_element(self, element_id: str) -> Optional[Gtk.Widget]:
        if not element_id:
            return None
            
        element = self.builder.get_object(element_id)
        if element and isinstance(element, Gtk.Widget):
            return element
            
        def find_in_widget(widget: Gtk.Widget, target_id: str) -> Optional[Gtk.Widget]:
            if hasattr(widget, 'get_buildable_id') and widget.get_buildable_id() == target_id:
                return widget
            
            if hasattr(widget, 'get_first_child'):
                child = widget.get_first_child()
                while child:
                    result = find_in_widget(child, target_id)
                    if result:
                        return result
                    child = child.get_next_sibling()
            
            return None
        
        return find_in_widget(self.parent_window, element_id)

    def _get_popover_position(self, position: str) -> Gtk.PositionType:
        position_map = {
            "top": Gtk.PositionType.TOP,
            "bottom": Gtk.PositionType.BOTTOM,
            "left": Gtk.PositionType.LEFT,
            "right": Gtk.PositionType.RIGHT
        }
        return position_map.get(position, Gtk.PositionType.BOTTOM)

    def _get_toast_overlay(self) -> Adw.ToastOverlay:
        def find_toast_overlay(widget):
            if isinstance(widget, Adw.ToastOverlay):
                return widget
            
            if hasattr(widget, 'get_first_child'):
                child = widget.get_first_child()
                while child:
                    result = find_toast_overlay(child)
                    if result:
                        return result
                    child = child.get_next_sibling()
            
            return None
        
        overlay = find_toast_overlay(self.parent_window)
        if not overlay:
            overlay = Adw.ToastOverlay()
            current_child = self.parent_window.get_child()
            self.parent_window.set_child(overlay)
            overlay.set_child(current_child)
        
        return overlay

    def _highlight_element(self, element_id: Optional[str]):
        if not element_id:
            return
            
        element = self._find_ui_element(element_id)
        if not element:
            return
        
        element.add_css_class("tour-highlight")
        GLib.timeout_add(2000, lambda: element.remove_css_class("tour-highlight"))

    def _advance_tour(self):
        self.current_tour_step += 1
        self._show_tour_step(self.current_tour_step)

    def _previous_step(self):
        if self.current_tour_step > 0:
            self.current_tour_step -= 1
            self._show_tour_step(self.current_tour_step)

    def _auto_advance_step(self) -> bool:
        speed = self.get_animation_speed()
        if speed != "disabled":
            self._advance_tour()
        return False

    def _finish_tour(self, skipped: bool = False):
        if self.active_popover:
            self.active_popover.popdown()
            self.active_popover = None
        
        self.set_tour_completed(True)
        self.current_tour_step = -1
        
        if not skipped:
            completion_toast = Adw.Toast.new("Tour completed! You can restart it anytime with Ctrl+H")
            completion_toast.set_timeout(3)
            self._get_toast_overlay().add_toast(completion_toast)

    def _on_modal_response(self, dialog: Adw.MessageDialog, response: str):
        dialog.close()
        
        if response == "finish":
            self._finish_tour()
        elif response == "restart":
            self.restart_tour()
        elif response == "next":
            self._advance_tour()
        elif response == "skip":
            self._finish_tour(skipped=True)

    def _on_help_shortcut(self, widget, args):
        self.show_contextual_help_overlay()
        return True

    def _on_tour_shortcut(self, widget, args):
        if not self.is_tour_completed() and self.current_tour_step >= 0:
            self._finish_tour(skipped=True)
        else:
            self.restart_tour()
        return True

    def show_contextual_help_overlay(self):
        help_overlay = self.builder.get_object('help_overlay')
        if help_overlay:
            help_overlay.set_transient_for(self.parent_window)
            help_overlay.present()
        else:
            self._show_keyboard_shortcuts_dialog()

    def _show_keyboard_shortcuts_dialog(self):
        shortcuts = [
            ("F1", "Show help and keyboard shortcuts"),
            ("Ctrl+H", "Start/restart tour"),
            ("Ctrl+O", "Open file or folder"),
            ("Ctrl+R", "Refresh package list"),
            ("Ctrl+F", "Search packages"),
            ("Ctrl+T", "Toggle terminal view"),
            ("Ctrl+P", "Open preferences"),
            ("Ctrl+Q", "Quit application"),
            ("Escape", "Cancel current operation"),
            ("Enter", "Confirm action"),
            ("Delete", "Remove selected item"),
            ("F5", "Refresh current view"),
            ("F11", "Toggle fullscreen"),
            ("Ctrl+1", "Switch to welcome view"),
            ("Ctrl+2", "Switch to content view"),
            ("Ctrl+3", "Switch to terminal view")
        ]
        
        dialog = Adw.PreferencesDialog(transient_for=self.parent_window)
        dialog.set_title("Keyboard Shortcuts")
        
        page = Adw.PreferencesPage()
        page.set_title("Shortcuts")
        dialog.add(page)
        
        group = Adw.PreferencesGroup()
        group.set_title("Application Shortcuts")
        page.add(group)
        
        for key, description in shortcuts:
            row = Adw.ActionRow()
            row.set_title(description)
            row.set_subtitle(key)
            
            key_label = Gtk.Label()
            key_label.set_markup(f"<tt>{key}</tt>")
            key_label.add_css_class("monospace")
            key_label.add_css_class("dim-label")
            row.add_suffix(key_label)
            
            group.add(row)
        
        dialog.present()

    def show_feature_tooltip(self, element_id: str, message: str, duration: int = 3000):
        if not self.should_show_tooltips():
            return
            
        element = self._find_ui_element(element_id)
        if not element:
            return
        
        tooltip_popover = Gtk.Popover()
        tooltip_popover.set_parent(element)
        tooltip_popover.set_position(Gtk.PositionType.BOTTOM)
        tooltip_popover.set_autohide(True)
        
        label = Gtk.Label()
        label.set_text(message)
        label.set_margin_top(8)
        label.set_margin_bottom(8)
        label.set_margin_start(12)
        label.set_margin_end(12)
        
        tooltip_popover.set_child(label)
        tooltip_popover.popup()
        
        if duration > 0:
            GLib.timeout_add(duration, lambda: tooltip_popover.popdown())

    def register_step_callback(self, step_id: str, callback: Callable):
        self.step_callbacks[step_id] = callback

    def trigger_step_callback(self, step_id: str, *args, **kwargs):
        if step_id in self.step_callbacks:
            self.step_callbacks[step_id](*args, **kwargs)

    def get_tour_progress(self) -> Dict[str, Any]:
        return {
            "completed": self.is_tour_completed(),
            "current_step": self.current_tour_step,
            "total_steps": len(self.tour_steps),
            "simplified_mode": self.is_simplified_mode_enabled(),
            "animation_speed": self.get_animation_speed()
        }

    def set_animation_speed(self, speed: str):
        valid_speeds = ["disabled", "slow", "normal", "fast"]
        if speed in valid_speeds:
            self._set_setting(self.ANIMATION_SPEED_KEY, speed)
            self.animation_duration = {
                "disabled": 0,
                "slow": 600,
                "normal": 300,
                "fast": 150
            }.get(speed, 300)

    def enable_tooltips(self, enabled: bool):
        self._set_setting(self.SHOW_TOOLTIPS_KEY, enabled)

    def export_tour_settings(self) -> Dict[str, Any]:
        return {
            "tour_completed": self.is_tour_completed(),
            "simplified_mode": self.is_simplified_mode_enabled(),
            "show_tooltips": self.should_show_tooltips(),
            "animation_speed": self.get_animation_speed()
        }

    def import_tour_settings(self, settings: Dict[str, Any]):
        for key, value in settings.items():
            if key == "tour_completed":
                self.set_tour_completed(value)
            elif key == "simplified_mode":
                self._set_setting(self.SIMPLIFIED_MODE_KEY, value)
            elif key == "show_tooltips":
                self.enable_tooltips(value)
            elif key == "animation_speed":
                self.set_animation_speed(value)
