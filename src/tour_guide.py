import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from gi.repository import Gtk, Gio, GLib, Adw, Gdk # Gdk for display context for UI

# Basic logging configuration for this module
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("tour_guide")

class TourGuide:
    """
    Manages the initial interactive tour for new users and contextual help.
    It provides non-intrusive modals, adapts to user preferences (like simplified mode),
    and can be accessed via keyboard shortcuts.
    """

    SCHEMA_ID = 'org.gnome.paru-gui' # GSettings schema ID
    TOUR_COMPLETED_KEY = 'tour-completed'
    SIMPLIFIED_MODE_KEY = 'simplified-mode'

    def __init__(self, parent_window: Gtk.Window, builder: Gtk.Builder, preferences_manager: Optional[Any] = None):
        """
        Initializes the TourGuide.

        Args:
            parent_window: The main application window to make tour popovers/dialogs transient for.
            builder: The Gtk.Builder instance holding the UI templates.
            preferences_manager: An instance of PreferencesManager for GSettings interaction.
        """
        self.parent_window = parent_window
        self.builder = builder
        self.preferences_manager = preferences_manager
        self.settings: Optional[Gio.Settings] = None
        self.current_tour_step = -1
        self.tour_steps: List[Dict[str, Any]] = [] # Will be populated based on mode

        self._initialize_settings()
        logger.info("TourGuide initialized.")

    def _initialize_settings(self):
        """Initializes GSettings for tour preferences."""
        if self.preferences_manager:
            # If PreferencesManager is used, rely on it
            self.settings = self.preferences_manager.settings # Assuming PreferencesManager holds Gio.Settings
        else:
            # Fallback if PreferencesManager is not provided (e.g., for direct testing)
            try:
                self.settings = Gio.Settings.new(self.SCHEMA_ID)
                logger.debug("TourGuide using direct GSettings instance.")
            except Gio.Error as e:
                logger.error(f"Failed to initialize GSettings in TourGuide: {e}. Tour state may not be persistent.")
                self.settings = None

    def _get_setting(self, key: str, default_value: Any) -> Any:
        """Helper to get a GSetting, handling missing settings."""
        if self.settings:
            try:
                # GSettings access methods are type-specific
                schema_type = self.settings.get_value(key).get_type().peek_string()
                if schema_type == 'b':
                    return self.settings.get_boolean(key)
                elif schema_type == 's':
                    return self.settings.get_string(key)
                # Add other types as needed
            except Gio.Error: # Key not found or schema not installed
                logger.warning(f"GSettings key '{key}' not found or schema error. Using default: {default_value}")
                return default_value
        return default_value

    def _set_setting(self, key: str, value: Any):
        """Helper to set a GSetting."""
        if self.settings:
            try:
                schema_type = self.settings.get_value(key).get_type().peek_string()
                if schema_type == 'b':
                    self.settings.set_boolean(key, value)
                elif schema_type == 's':
                    self.settings.set_string(key, value)
                logger.debug(f"GSettings key '{key}' set to '{value}'.")
            except Gio.Error as e:
                logger.error(f"Error setting GSettings key '{key}': {e}")

    def is_tour_completed(self) -> bool:
        """Checks if the initial tour has been completed."""
        return self._get_setting(self.TOUR_COMPLETED_KEY, False)

    def set_tour_completed(self, completed: bool):
        """Marks the initial tour as completed or not."""
        self._set_setting(self.TOUR_COMPLETED_KEY, completed)

    def is_simplified_mode_enabled(self) -> bool:
        """Checks if simplified mode is enabled."""
        return self._get_setting(self.SIMPLIFIED_MODE_KEY, True)

    def show_initial_tour(self):
        """
        [ ] Implement non-intrusive modal tour for the first execution.
        Initiates the initial tour if it hasn't been completed.
        """
        if self.is_tour_completed():
            logger.info("Initial tour already completed. Skipping.")
            return

        logger.info("Starting initial tour for the first-time user.")
        self.set_tour_completed(False) # Reset in case it was half-finished or opted to restart
        self._prepare_tour_steps()
        self.current_tour_step = 0
        self._show_tour_step(self.current_tour_step)

    def _prepare_tour_steps(self):
        """
        [ ] Develop adaptive tour logic based on user profile (simplified mode).
        Prepares the sequence of tour steps based on current preferences.
        """
        simplified_mode = self.is_simplified_mode_enabled()
        self.tour_steps = [
            {
                "title": "Welcome to Paru GUI!",
                "message": "This tour will guide you through the main features. Click 'Next' to continue.",
                "ui_element_id": None, # No specific element for welcome
                "icon": "dialog-information-symbolic"
            },
            {
                "title": "Select Files or Folders",
                "message": "Start by selecting a PKGBUILD, a package, or a folder with compatible files from the welcome screen.",
                "ui_element_id": "select_folder_button", # Points to specific button on welcome screen
                "icon": "document-open-symbolic"
            },
            {
                "title": "Smart File Visualization",
                "message": "Once a folder is open, you'll see smart cards for PKGBUILDs, packages, and patches.",
                "ui_element_id": "content_cards", # Points to the flowbox in content_view
                "icon": "folder-open-symbolic"
            },
        ]

        if not simplified_mode:
            self.tour_steps.append({
                "title": "Advanced Security Review",
                "message": "For PKGBUILDs, access the detailed security review with a risk heatmap for in-depth analysis.",
                "ui_element_id": "PkgbuildReviewDialog", # Points to the review dialog (once open)
                "icon": "system-search-symbolic"
            })
            self.tour_steps.append({
                "title": "Sandboxed Operations",
                "message": "Execute critical actions like building or installing packages in an isolated environment for enhanced security.",
                "ui_element_id": "sandbox_expander", # Points to sandbox expander in review dialog
                "icon": "security-high-symbolic"
            })

        self.tour_steps.extend([
            {
                "title": "Real-time Terminal Output",
                "message": "Monitor command execution with real-time output and filtering options at the bottom of the content view.",
                "ui_element_id": "terminal_area", # Points to terminal area in content_view
                "icon": "utilities-terminal-symbolic"
            },
            {
                "title": "Keyboard Shortcuts (F1)",
                "message": "Press F1 at any time for a list of keyboard shortcuts to quickly navigate and perform actions.",
                "ui_element_id": "help_button", # Points to help button in header bar
                "icon": "help-about-symbolic"
            },
            {
                "title": "Tour Complete!",
                "message": "You're all set! Explore Paru GUI and manage your AUR packages securely. You can restart the tour anytime from the app menu.",
                "ui_element_id": None,
                "icon": "face-cool-symbolic"
            }
        ])
        logger.debug(f"Tour steps prepared. Simplified mode: {simplified_mode}, Total steps: {len(self.tour_steps)}")


    def _show_tour_step(self, step_index: int):
        """Displays a single step of the tour using an Adw.Toast or Popover."""
        if not (0 <= step_index < len(self.tour_steps)):
            self._finish_tour()
            return

        step = self.tour_steps[step_index]
        logger.debug(f"Showing tour step {step_index}: {step['title']}")

        # For a non-intrusive tour, Adw.Toast is simple. For pointing to UI elements, Gtk.Popover is better.
        # This example uses Adw.Toast for simplicity across steps, but Popovers are ideal for direct UI interaction.

        toast = Adw.Toast.new(step["message"])
        toast.set_title(step["title"])
        toast.set_timeout(5) # Auto-hide after 5 seconds
        toast.set_priority(Adw.ToastPriority.HIGH)
        toast.set_icon_name(step["icon"])

        # Add buttons to progress or skip
        next_button = Gtk.Button.new_with_label("Next")
        next_button.connect("clicked", lambda b: self._advance_tour())
        next_button.add_css_class("suggested-action")
        toast.add_button(next_button)

        skip_button = Gtk.Button.new_with_label("Skip Tour")
        skip_button.connect("clicked", lambda b: self._finish_tour(skipped=True))
        toast.add_button(skip_button)

        self.parent_window.get_child().get_child().add_toast(toast) # Assuming main_stack is child of main_box
        # Note: This assumes specific UI hierarchy. A robust approach would use self.get_application().add_toast(toast)
        # or target a specific Adw.ToastOverlay in the main window.

        # If a UI element ID is specified, we could try to highlight it or attach a Popover
        if step["ui_element_id"]:
            element = self.builder.get_object(step["ui_element_id"], self.parent_window) # Try to find in parent window scope
            if element:
                # For demo, just print that it's found. In real app, attach Gtk.Popover.
                logger.debug(f"UI element '{step['ui_element_id']}' found for step {step_index}. (Popover would attach here).")
                # Example Popover attachment (conceptual):
                # popover = Gtk.Popover.new_from_model(None)
                # popover.set_child(Gtk.Label(label=step["message"]))
                # popover.set_parent(element)
                # popover.set_pointing_to(element.get_allocation())
                # popover.popup()
            else:
                logger.warning(f"UI element '{step['ui_element_id']}' not found for tour step.")


    def _advance_tour(self):
        """Advances the tour to the next step."""
        self.current_tour_step += 1
        self._show_tour_step(self.current_tour_step)

    def _finish_tour(self, skipped: bool = False):
        """Completes or skips the tour and updates preferences."""
        if not skipped:
            logger.info("Initial tour completed successfully.")
        else:
            logger.info("Initial tour skipped by user.")
        self.set_tour_completed(True)
        self.current_tour_step = -1 # Reset tour state

    def show_contextual_help_overlay(self):
        """
        [ ] Create contextual help system accessible via F1.
        Displays the keyboard shortcuts overlay or a contextual help dialog.
        """
        logger.info("Showing contextual help overlay (keyboard shortcuts).")
        help_overlay = self.builder.get_object('help_overlay')
        if help_overlay:
            help_overlay.set_transient_for(self.parent_window)
            help_overlay.present()
        else:
            logger.error("Help overlay (GtkShortcutsWindow) not found in builder.")
            # Fallback to a simple dialog
            dialog = Adw.MessageDialog(
                transient_for=self.parent_window,
                heading="Help",
                body="Keyboard shortcuts list not available. See application documentation.",
                extra_button_label="OK"
            )
            dialog.connect("response", lambda d, r: d.close())
            dialog.present()

    def _on_skip_tour(self, button: Gtk.Button):
        """Callback for the 'Skip Tour' button."""
        self._finish_tour(skipped=True)

    def _on_restart_tour(self, button: Gtk.Button):
        """Callback to restart the tour (e.g., from app menu)."""
        logger.info("Restarting initial tour.")
        self.set_tour_completed(False) # Mark as not completed to re-run
        self.show_initial_tour()


# Example Usage (for testing this module directly)
if __name__ == "__main__":
    # Ensure gi is initialized for Gtk/Adw
    try:
        import gi
        gi.require_version('Gtk', '4.0')
        gi.require_version('Adw', '1')
    except ValueError as e:
        print(f"GI requirements not met for testing: {e}")
        print("Please ensure you have pygobject installed and GTK/Adwaita libraries are available.")
        print("Skipping direct test of TourGuide due to GI environment.")
        exit(1)

    # Mock a PreferencesManager for testing GSettings interaction
    class MockPreferencesManager:
        def __init__(self):
            self._settings = {} # Simple dictionary to simulate GSettings
            self._settings[TourGuide.TOUR_COMPLETED_KEY] = False
            self._settings[TourGuide.SIMPLIFIED_MODE_KEY] = True # Simulate simplified mode by default

            # This is a hacky way to make TourGuide use this mock
            # In a real app, preferences_manager would hold a real Gio.Settings object
            # and TourGuide would use it directly.
            self.settings = self # Mimic Gio.Settings for _get_setting/_set_setting

        def get_boolean(self, key: str) -> bool:
            return self._settings.get(key, False)

        def set_boolean(self, key: str, value: bool):
            self._settings[key] = value

        def get_string(self, key: str) -> str:
            return self._settings.get(key, "")

        def get_value(self, key:str): # Mock Gio.Settings.get_value for type introspection
            class MockVariant:
                def peek_string(self): return 'b' if isinstance(self._settings.get(key), bool) else 's'
            return MockVariant()

        def is_simplified_mode_enabled(self):
            return self._settings.get(TourGuide.SIMPLIFIED_MODE_KEY, True)

    # Create a dummy GtkApplication for context
    class TestApp(Adw.Application):
        def __init__(self):
            super().__init__(application_id='org.gnome.paru-gui.tourguide-test')
            self.window: Optional[Gtk.ApplicationWindow] = None
            self.builder = Gtk.Builder()

            # Mock some UI content for the builder to find elements
            mock_ui_content = """
            <?xml version="1.0" encoding="UTF-8"?>
            <interface>
                <requires lib="gtk" version="4.0"/>
                <requires lib="libadwaita" version="1.0"/>
                <object class="AdwApplicationWindow" id="main_window">
                    <property name="title">Paru GUI Tour Test</property>
                    <property name="default-width">800</property>
                    <property name="default-height">600</property>
                    <child>
                        <object class="AdwToastOverlay" id="toast_overlay">
                            <child>
                                <object class="GtkBox" id="main_box">
                                    <property name="orientation">vertical</property>
                                    <child>
                                        <object class="GtkHeaderBar" id="header_bar">
                                            <child type="end">
                                                <object class="GtkButton" id="help_button">
                                                    <property name="icon-name">help-about-symbolic</property>
                                                    <property name="tooltip-text">Help</property>
                                                </object>
                                            </child>
                                        </object>
                                    </child>
                                    <child>
                                        <object class="GtkStack" id="main_stack">
                                            <child>
                                                <object class="GtkStackPage">
                                                    <property name="name">welcome</property>
                                                    <property name="child">
                                                        <object class="GtkBox" orientation="vertical" spacing="20">
                                                            <property name="halign">center</property>
                                                            <property name="valign">center</property>
                                                            <child><object class="GtkLabel"><property name="label">Welcome Screen</property></object></child>
                                                            <child><object class="GtkButton" id="select_folder_button"><property name="label">Select Folder</property></object></child>
                                                        </object>
                                                    </property>
                                                </object>
                                            </child>
                                            <child>
                                                <object class="GtkStackPage">
                                                    <property name="name">content</property>
                                                    <property name="child">
                                                        <object class="GtkBox" orientation="vertical" spacing="20">
                                                            <child><object class="GtkLabel"><property name="label">Content View</property></object></child>
                                                            <child><object class="GtkFlowBox" id="content_cards"><property name="max-children-per-line">3</property></object></child>
                                                            <child><object class="GtkBox" id="terminal_area"><property name="visible">False"></property><child><object class="GtkLabel"><property name="label">Terminal</property></object></child></object></child>
                                                        </object>
                                                    </property>
                                                </object>
                                            </child>
                                        </object>
                                    </child>
                                </object>
                            </child>
                        </object>
                    </child>
                </object>
                <object class="GtkShortcutsWindow" id="help_overlay">
                    <property name="modal">True</property>
                    <child><object class="GtkShortcutsSection"><property name="section-name">general</property></object></child>
                </object>
                <template class="PkgbuildReviewDialog" parent="AdwDialog" id="PkgbuildReviewDialog">
                    <property name="title">PKGBUILD Review</property>
                    <child><object class="GtkBox"><property name="orientation">vertical"><child><object class="GtkExpander" id="sandbox_expander"><property name="label">Sandbox Settings</property></object></child></property></object></child>
                </template>
            </interface>
            """
            self.builder.add_from_string(mock_ui_content)

            # Load CSS to ensure classes like "suggested-action" exist if needed by Toast buttons
            css_provider = Gtk.CssProvider()
            css_provider.load_from_data(b".suggested-action { background-color: #0078d4; color: white; padding: 5px 10px; border-radius: 5px; }")
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        def do_activate(self):
            if not self.window:
                self.window = self.builder.get_object('main_window')
                self.window.set_application(self) # Link window to app

                self.preferences_manager = MockPreferencesManager()
                self.tour_guide = TourGuide(self.window, self.builder, self.preferences_manager)

                # Connect the help button (F1 equivalent)
                help_button = self.builder.get_object('help_button')
                if help_button:
                    help_button.connect('clicked', lambda w: self.tour_guide.show_contextual_help_overlay())

                # Make toast_overlay accessible for the tour guide
                # Adw.ApplicationWindow typically manages a ToastOverlay itself
                # or you add one explicitly. In this mock, we get it.
                self.window.get_child().add_toast = lambda toast: self.window.get_child().add_toast(toast)

            self.window.present()
            self.tour_guide.show_initial_tour() # Start the tour on activation

        def get_version(self): # Mock get_version for ErrorHandler/other components
            return "1.0-test"

    app = TestApp()
    sys.exit(app.run(sys.argv))
