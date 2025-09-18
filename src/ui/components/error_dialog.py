import os
import sys
import logging
import traceback
from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field

from gi.repository import Gtk, Gio, GLib, Gdk, Adw, Pango

# Basic logging configuration for this module
logging.basicConfig(
    level=logging.ERROR, # Default to ERROR for error handler
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("error_handler")

class ErrorCategory(Enum):
    """Categorizes different types of errors."""
    SYSTEM = "System Error"
    NETWORK = "Network Error"
    PKGBUILD_ANALYSIS = "PKGBUILD Analysis Error"
    COMMAND_EXECUTION = "Command Execution Error"
    SECURITY_RISK = "Security Risk Detected"
    FILE_OPERATION = "File Operation Error"
    UI_ERROR = "User Interface Error"
    INTERNAL = "Internal Application Error"
    UNKNOWN = "Unknown Error"

class SuggestedAction(Enum):
    """Defines suggested actions for the user."""
    NONE = "None"
    IGNORE_RISK = "Ignore Risk"
    VIEW_ANALYSIS = "View Complete Analysis"
    REPORT_AUR = "Report to AUR"
    RETRY = "Retry Operation"
    CHECK_LOG = "Check Full Log"
    CONSULT_DOCS = "Consult Documentation"
    CLOSE_APP = "Close Application"

@dataclass
class ErrorDetail:
    """Detailed information about a specific problem or context."""
    message: str
    level: str = "info" # "info", "warning", "error", "critical"
    line_number: Optional[int] = None
    snippet: Optional[str] = None

@dataclass
class ErrorContext:
    """A rich context object for a detected error."""
    category: ErrorCategory
    summary: str # Short summary for the dialog heading
    details: str # Longer, technical description
    timestamp: datetime = field(default_factory=datetime.utcnow)
    application_version: str = "N/A"
    file_path: Optional[str] = None
    pkgname: Optional[str] = None
    pkgver: Optional[str] = None
    command_executed: Optional[str] = None
    working_directory: Optional[str] = None
    stdout: Optional[str] = None # Output from command, if relevant
    stderr: Optional[str] = None # Error output from command, if relevant
    traceback: Optional[str] = None # Python traceback, if an exception occurred
    additional_problems: List[ErrorDetail] = field(default_factory=list)
    additional_context: List[ErrorDetail] = field(default_factory=list)
    suggested_actions: List[SuggestedAction] = field(default_factory=list)
    # Reference to the original exception, if any
    original_exception: Optional[Exception] = None

class ErrorHandler:
    """
    Manages the creation and display of contextualized error dialogs.
    It encapsulates error categorization, context collection, and action suggestions.
    """

    # --- Error Catalog (internal mapping for specific scenarios) ---
    _error_catalog: Dict[ErrorCategory, Dict[str, Any]] = {
        ErrorCategory.SECURITY_RISK: {
            "title": "Security Risk Detected",
            "icon": "dialog-warning-symbolic",
            "base_actions": [SuggestedAction.IGNORE_RISK, SuggestedAction.VIEW_ANALYSIS, SuggestedAction.REPORT_AUR]
        },
        ErrorCategory.COMMAND_EXECUTION: {
            "title": "Command Failed",
            "icon": "dialog-error-symbolic",
            "base_actions": [SuggestedAction.RETRY, SuggestedAction.CHECK_LOG, SuggestedAction.CONSULT_DOCS]
        },
        ErrorCategory.NETWORK: {
            "title": "Network Issue",
            "icon": "network-offline-symbolic",
            "base_actions": [SuggestedAction.RETRY, SuggestedAction.CHECK_LOG]
        },
        ErrorCategory.FILE_OPERATION: {
            "title": "File Operation Failed",
            "icon": "document-error-symbolic",
            "base_actions": [SuggestedAction.CHECK_LOG]
        },
        ErrorCategory.INTERNAL: {
            "title": "Application Error",
            "icon": "application-x-executable-symbolic",
            "base_actions": [SuggestedAction.CLOSE_APP, SuggestedAction.CHECK_LOG]
        },
        ErrorCategory.UNKNOWN: {
            "title": "An Unknown Error Occurred",
            "icon": "dialog-question-symbolic",
            "base_actions": [SuggestedAction.CHECK_LOG]
        }
        # ... add more categories as needed
    }

    def __init__(self, builder: Gtk.Builder, parent_window: Gtk.Window, app_version: str = "N/A"):
        self.builder = builder
        self.parent_window = parent_window
        self.app_version = app_version
        self.error_dialog: Optional[Adw.Dialog] = None

        # This assumes the ErrorDialog is a template in the builder passed to it.
        # It needs to be a distinct dialog, not embedded in the main window.
        self._load_dialog_from_builder()
        logger.info("ErrorHandler initialized.")

    def _load_dialog_from_builder(self):
        """Loads the ErrorDialog from the Gtk.Builder and connects its signals."""
        try:
            self.error_dialog = self.builder.get_object('ErrorDialog')
            if not self.error_dialog:
                logger.error("ErrorDialog template with ID 'ErrorDialog' not found in provided builder.")
                raise ValueError("ErrorDialog UI template not found.")

            # Connect general dialog actions (Close, Copy Log)
            close_button = self.builder.get_object('close_button')
            if close_button:
                close_button.connect('clicked', lambda w: self.error_dialog.close())
            else:
                logger.warning("ErrorDialog 'close_button' not found.")

            copy_log_button = self.builder.get_object('copy_log_button')
            if copy_log_button:
                copy_log_button.connect('clicked', self._on_copy_log_clicked)
            else:
                logger.warning("ErrorDialog 'copy_log_button' not found.")

            # Connect dynamic action buttons (will be enabled/disabled later)
            self.builder.get_object('ignore_risk_button').connect('clicked', lambda w: self._on_suggested_action_clicked(SuggestedAction.IGNORE_RISK))
            self.builder.get_object('view_analysis_button').connect('clicked', lambda w: self._on_suggested_action_clicked(SuggestedAction.VIEW_ANALYSIS))
            self.builder.get_object('report_aur_button').connect('clicked', lambda w: self._on_suggested_action_clicked(SuggestedAction.REPORT_AUR))
            # Other actions like RETRY, CONSULT_DOCS, CLOSE_APP might need specific buttons or be handled via the main close.

        except Exception as e:
            logger.critical(f"Failed to load or configure ErrorDialog from builder: {e}")
            self.error_dialog = None # Ensure it's None if setup failed

    def show_error_dialog(self, error_context: ErrorContext):
        """
        Displays a contextualized error dialog to the user.
        """
        if not self.error_dialog:
            logger.error("Cannot show error dialog: Dialog object not initialized.")
            # Fallback to a simple message if the rich dialog fails
            self._show_fallback_dialog(error_context)
            return

        logger.error(f"Displaying error: {error_context.summary} (Category: {error_context.category.value})")

        self.error_dialog.set_transient_for(self.parent_window)
        self.error_dialog.set_modal(True)
        # Adwaita dialogs manage their own headerbar and title.
        # The internal elements are updated via _populate_dialog.

        self._populate_dialog_content(error_context)
        self.error_dialog.present()

    def _populate_dialog_content(self, context: ErrorContext):
        """Populates the Gtk.ErrorDialog elements with information from ErrorContext."""
        if not self.error_dialog: return

        catalog_entry = self._error_catalog.get(context.category, self._error_catalog[ErrorCategory.UNKNOWN])

        # Header Section
        # This requires traversing the complex structure of error_dialog.ui
        # Assuming direct access to child widgets by ID is possible after builder.get_object('ErrorDialog')
        # if the dialog itself is the template root.
        # If ErrorDialog is a <template class="ErrorDialog" parent="AdwDialog">, then self.error_dialog is the AdwDialog.
        # Its direct child is main_dialog_content_box.

        error_type_label = self.builder.get_object('error_type_label')
        error_package_label = self.builder.get_object('error_package_label')
        error_icon_header = self.builder.get_object('error_icon_header')

        if error_type_label:
            error_type_label.set_label(f"ERROR: {context.category.value.upper().replace(' ', '_')}")
            # Dynamic styling for type label (e.g., error-color for critical)
        if error_package_label:
            pkg_info = f"Package: {context.pkgname} (v{context.pkgver})" if context.pkgname else "N/A"
            if context.file_path:
                pkg_info += f" | File: {os.path.basename(context.file_path)}"
            error_package_label.set_label(f"{context.summary} - {pkg_info}")
            # Dynamic styling for package label
        if error_icon_header:
            error_icon_header.set_from_icon_name(catalog_entry["icon"])
            error_icon_header.get_style_context().add_class('error-color') # Default for errors

        # Detected Problems Section (problems_list)
        problems_list_box = self.builder.get_object('problems_list')
        self._clear_and_populate_box(problems_list_box, context.additional_problems)

        # Critical Lines Section (critical_lines_content)
        critical_lines_box = self.builder.get_object('critical_lines_content')
        if critical_lines_box:
            # Clear existing content
            self._clear_box(critical_lines_box)
            if context.stderr:
                # Add a label for stderr
                stderr_label = Gtk.Label(label=f"<b>Command STDERR:</b>\n{context.stderr}", use_markup=True)
                stderr_label.set_halign(Gtk.Align.START)
                stderr_label.set_wrap(True)
                stderr_label.get_style_context().add_class('monospace')
                critical_lines_box.append(stderr_label)
            if context.traceback:
                # Add a label for traceback
                traceback_label = Gtk.Label(label=f"<b>Python Traceback:</b>\n{context.traceback}", use_markup=True)
                traceback_label.set_halign(Gtk.Align.START)
                traceback_label.set_wrap(True)
                traceback_label.get_style_context().add_class('monospace')
                critical_lines_box.append(traceback_label)
            if not context.stderr and not context.traceback and not context.additional_problems:
                label = Gtk.Label(label="No specific critical lines/output provided.")
                label.set_halign(Gtk.Align.START)
                critical_lines_box.append(label)

        # Additional Context Section (context_list)
        context_list_box = self.builder.get_object('context_list')
        self._clear_and_populate_box(context_list_box, context.additional_context)

        # Action Buttons Section
        self._configure_action_buttons(context)

    def _clear_box(self, box: Gtk.Box):
        """Clears all children from a Gtk.Box."""
        if box:
            while box.get_first_child() is not None:
                box.remove(box.get_first_child())

    def _clear_and_populate_box(self, box: Gtk.Box, details: List[ErrorDetail]):
        """Clears a Gtk.Box and populates it with ErrorDetail labels."""
        self._clear_box(box)
        if not details:
            label = Gtk.Label(label="No specific issues detected.")
            label.set_halign(Gtk.Align.START)
            box.append(label)
            return

        for detail in details:
            label_text = f"• {detail.message}"
            if detail.line_number:
                label_text += f" (Line: {detail.line_number})"
            if detail.snippet:
                label_text += f" -> '{detail.snippet}'"

            label = Gtk.Label(label=label_text)
            label.set_halign(Gtk.Align.START)
            label.set_wrap(True)
            label.set_xalign(0) # Align text to start

            # Apply styling based on level
            if detail.level == "error":
                label.get_style_context().add_class('error-color')
            elif detail.level == "warning":
                label.get_style_context().add_class('warning-color')
            elif detail.level == "critical":
                label.get_style_context().add_class('error-color')
                label.get_style_context().add_class('bold')

            box.append(label)

    def _configure_action_buttons(self, context: ErrorContext):
        """Enables/disables and configures action buttons based on error context."""
        ignore_risk_button = self.builder.get_object('ignore_risk_button')
        view_analysis_button = self.builder.get_object('view_analysis_button')
        report_aur_button = self.builder.get_object('report_aur_button')

        all_action_buttons = [ignore_risk_button, view_analysis_button, report_aur_button]
        for btn in all_action_buttons:
            if btn: btn.set_visible(False) # Hide all by default

        actions_to_display = self._error_catalog.get(context.category, {}).get("base_actions", [])
        if context.suggested_actions: # Override with specific suggestions if present
            actions_to_display = context.suggested_actions

        for action in actions_to_display:
            if action == SuggestedAction.IGNORE_RISK and ignore_risk_button:
                ignore_risk_button.set_label(_("Ignore Risk"))
                ignore_risk_button.set_tooltip_text(_("Proceed with installation despite detected risks. Use with caution."))
                ignore_risk_button.get_child().get_child_at(1).set_label(_("Ignore Risk")) # Update label within the box
                ignore_risk_button.get_child().get_child_at(2).set_label(_("Only for experienced users")) # Update sub-label
                ignore_risk_button.set_visible(True)
            elif action == SuggestedAction.VIEW_ANALYSIS and view_analysis_button:
                view_analysis_button.set_label(_("View Complete Analysis"))
                view_analysis_button.set_tooltip_text(_("Open the PKGBUILD review screen with heatmap analysis."))
                view_analysis_button.get_child().get_child_at(1).set_label(_("View Complete Analysis"))
                view_analysis_button.get_child().get_child_at(2).set_label(_("Show PKGBUILD heatmap"))
                view_analysis_button.set_visible(True)
            elif action == SuggestedAction.REPORT_AUR and report_aur_button:
                report_aur_button.set_label(_("Report to AUR"))
                report_aur_button.set_tooltip_text(_("Report this package's issues to the AUR maintainer and community."))
                report_aur_button.get_child().get_child_at(1).set_label(_("Report to AUR"))
                report_aur_button.get_child().get_child_at(2).set_label(_("Send warning to community"))
                report_aur_button.set_visible(True)
            # Add conditions for other SuggestedAction enums if they have dedicated buttons

    # --- Signal Handlers for Dialog Actions ---
    def _on_copy_log_clicked(self, button: Gtk.Button):
        """Callback for the 'Copy Log' button."""
        if not self.error_dialog: return

        # Retrieve the current error context (assuming it's stored or can be re-generated)
        # For this example, let's just grab visible text
        log_content_parts = []
        error_type_label = self.builder.get_object('error_type_label')
        if error_type_label: log_content_parts.append(error_type_label.get_label())
        error_package_label = self.builder.get_object('error_package_label')
        if error_package_label: log_content_parts.append(error_package_label.get_label())

        problems_list_box = self.builder.get_object('problems_list')
        if problems_list_box:
            log_content_parts.append("\nDetected Problems:")
            for child in problems_list_box:
                if isinstance(child, Gtk.Label): log_content_parts.append(f"  {child.get_label()}")

        critical_lines_box = self.builder.get_object('critical_lines_content')
        if critical_lines_box:
            log_content_parts.append("\nCritical Lines/Output:")
            for child in critical_lines_box:
                if isinstance(child, Gtk.Label): log_content_parts.append(f"  {child.get_label()}")

        context_list_box = self.builder.get_object('context_list')
        if context_list_box:
            log_content_parts.append("\nAdditional Context:")
            for child in context_list_box:
                if isinstance(child, Gtk.Label): log_content_parts.append(f"  {child.get_label()}")

        full_log_content = "\n".join(log_content_parts)

        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set_text(full_log_content)
        logger.info("Error log copied to clipboard.")

        # Optional: Provide a visual cue that it was copied
        button.set_label(_("Copied!"))
        GLib.timeout_add_seconds(2, lambda: button.set_label(_("Copy Log")) or GLib.SOURCE_REMOVE)


    def _on_suggested_action_clicked(self, action: SuggestedAction, *args):
        """Generic handler for suggested action buttons."""
        logger.info(f"Suggested action '{action.value}' clicked.")
        self.error_dialog.close() # Close dialog after action is selected

        # TODO: Implement actual logic for each action type.
        # This would typically emit a signal or call a method on the main window
        # to trigger the requested operation.
        if action == SuggestedAction.IGNORE_RISK:
            logger.info("Logic for 'Ignore Risk' would proceed with the original operation.")
            # Example: self.parent_window.continue_operation_ignoring_risk(self._last_error_context)
        elif action == SuggestedAction.VIEW_ANALYSIS:
            logger.info("Logic for 'View Complete Analysis' would navigate to PKGBUILD review screen.")
            # Example: self.parent_window.show_pkgbuild_review(self._last_error_context.file_path)
        elif action == SuggestedAction.REPORT_AUR:
            logger.info("Logic for 'Report to AUR' would open a browser to AUR package page.")
            # Example: Gtk.show_uri(self.parent_window, f"https://aur.archlinux.org/packages/{self._last_error_context.pkgname}", Gdk.CURRENT_TIME)
        elif action == SuggestedAction.RETRY:
            logger.info("Logic for 'Retry Operation' would re-attempt the failed command.")
            # Example: self.parent_window.retry_last_command(self._last_error_context)
        elif action == SuggestedAction.CLOSE_APP:
            logger.info("Logic for 'Close Application' would initiate app.quit.")
            # Example: self.parent_window.get_application().quit()


    def _show_fallback_dialog(self, context: ErrorContext):
        """Displays a simple Adw.MessageDialog if the rich dialog fails to load/setup."""
        dialog = Adw.MessageDialog(
            transient_for=self.parent_window,
            heading=f"{context.category.value}: {context.summary}",
            body=f"{context.details}\n\nCheck logs for more details.",
            modal=True,
        )
        dialog.add_response("ok", _("OK"))
        dialog.set_default_response("ok")
        dialog.connect("response", lambda d, r: d.close())
        dialog.present()


# Example Usage (for testing this module directly)
if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG) # Enable DEBUG logs for testing

    # Initialize Gtk and Adw for standalone dialog test
    gi.require_version('Gtk', '4.0')
    gi.require_version('Adw', '1')

    # Create a dummy GtkApplication for context
    class TestApp(Adw.Application):
        def __init__(self):
            super().__init__(application_id='org.gnome.paru-gui.errorhandler-test')
            self.window: Optional[Gtk.Window] = None
            self.builder = Gtk.Builder()
            # Assuming error_dialog.ui content is available as a resource or file
            # For this standalone test, we need to manually load it.
            # In a real app, the main builder would have loaded it.
            # Let's mock a simple UI template that only has the error dialog.
            # This is a bit hacky for direct execution, usually the ErrorDialog would be
            # defined within the main application's UI file or its own resource.

            # Mock a minimal error_dialog.ui content for standalone testing
            error_ui_content = """
            <?xml version="1.0" encoding="UTF-8"?>
            <interface>
            <requires lib="gtk" version="4.0"/>
            <requires lib="libadwaita" version="1.0"/>
            <template class="ErrorDialog" parent="AdwDialog">
                <child>
                <object class="GtkBox" id="main_dialog_content_box">
                    <property name="orientation">vertical</property>
                    <property name="spacing">0</property>
                    <property name="vexpand">True</property>
                    <property name="hexpand">True</property>
                    <child>
                    <object class="GtkBox" id="error_header">
                        <property name="orientation">vertical</property>
                        <property name="spacing">12</property>
                        <property name="margin-bottom">12</property>
                        <property name="halign">fill</property>
                        <property name="hexpand">True</property>
                        <child>
                        <object class="GtkBox">
                            <property name="orientation">horizontal</property>
                            <property name="spacing">8</property>
                            <property name="margin-start">16</property>
                            <property name="margin-end">16</property>
                            <child>
                            <object class="GtkImage" id="error_icon_header">
                                <property name="icon-name">dialog-error-symbolic</property>
                                <property name="pixel-size">32</property>
                                <style><class name="error-color"/></style>
                            </object>
                            </child>
                            <child>
                            <object class="GtkLabel" id="error_type_label">
                                <property name="label">ERROR: RISK_DETECTED</property>
                                <property name="halign">start</property>
                                <property name="valign">center</property>
                                <property name="hexpand">True</property>
                                <style><class name="title-3"/><class name="bold"/></style>
                            </object>
                            </child>
                        </object>
                        </child>
                        <child>
                        <object class="GtkLabel" id="error_package_label">
                            <property name="label">Package: suspicious-package-git (AUR)</property>
                            <property name="halign">start</property>
                            <property name="margin-start">16</property>
                            <property name="margin-end">16</property>
                            <style><class name="title-2"/><class name="bold"/></style>
                        </object>
                        </child>
                    </object>
                    </child>
                    <child>
                    <object class="GtkScrolledWindow" id="error_scrolled_window">
                        <property name="vscrollbar-policy">automatic</property>
                        <property name="hscrollbar-policy">automatic</property>
                        <property name="vexpand">True</property>
                        <property name="hexpand">True</property>
                        <property name="margin-start">16</property>
                        <property name="margin-end">16</property>
                        <property name="margin-top">12</property>
                        <property name="margin-bottom">12</property>
                        <child>
                        <object class="GtkViewport">
                            <child>
                            <object class="GtkBox" id="error_content_box">
                                <property name="orientation">vertical</property>
                                <property name="spacing">24</property>
                                <property name="margin-top">12</property>
                                <property name="margin-bottom">12</property>
                                <property name="margin-start">16</property>
                                <property name="margin-end">16</property>
                                <child>
                                <object class="GtkBox" id="problems_section">
                                    <property name="orientation">vertical</property>
                                    <property name="spacing">8</property>
                                    <child><object class="GtkLabel"><property name="label">Detected Problems:</property><property name="halign">start</property><style><class name="heading"/></style></object></child>
                                    <child><object class="GtkBox" id="problems_list"><property name="orientation">vertical</property><property name="spacing">6</property></object></child>
                                </object>
                                </child>
                                <child>
                                <object class="GtkBox" id="actions_section">
                                    <property name="orientation">vertical</property>
                                    <property name="spacing">12</property>
                                    <child><object class="GtkLabel"><property name="label">Recommended Actions:</property><property name="halign">start</property><style><class name="heading"/></style></object></child>
                                    <child>
                                    <object class="GtkBox" id="actions_buttons">
                                        <property name="orientation">vertical</property><property name="spacing">8</property>
                                        <child><object class="GtkButton" id="ignore_risk_button"><property name="halign">fill</property><property name="hexpand">True</property><style><class name="flat"/><class name="error-color"/><class name="pill"/></style><child><object class="GtkBox"><property name="orientation">horizontal</property><property name="spacing">8</property><child><object class="GtkImage"><property name="icon-name">dialog-warning-symbolic</property></object></child><child><object class="GtkLabel"><property name="label">Ignore Risk</property><property name="halign">start"/><style><class name="bold"/></style></object></child><child><object class="GtkLabel"><property name="label">Only for experienced users</property><property name="halign">end"/><property name="hexpand">True</property><style><class name="caption"/><class name="dim-label"/></style></object></child></object></child></object></child>
                                        <child><object class="GtkButton" id="view_analysis_button"><property name="halign">fill</property><property name="hexpand">True</property><style><class name="flat"/><class name="warning-color"/><class name="pill"/></style><child><object class="GtkBox"><property name="orientation">horizontal</property><property name="spacing">8</property><child><object class="GtkImage"><property name="icon-name">system-search-symbolic</property></object></child><child><object class="GtkLabel"><property name="label">View Complete Analysis</property><property name="halign">start"/><style><class name="bold"/></style></object></child><child><object class="GtkLabel"><property name="label">Show PKGBUILD heatmap</property><property name="halign">end"/><property name="hexpand">True</property><style><class name="caption"/><class name="dim-label"/></style></object></child></object></child></object></child>
                                        <child><object class="GtkButton" id="report_aur_button"><property name="halign">fill</property><property name="hexpand">True</property><style><class name="flat"/><class name="success-color"/><class name="pill"/></style><child><object class="GtkBox"><property name="orientation">horizontal</property><property name="spacing">8</property><child><object class="GtkImage"><property name="icon-name">dialog-information-symbolic</property></object></child><child><object class="GtkLabel"><property name="label">Report to AUR</property><property name="halign">start"/><style><class name="bold"/></style></object></child><child><object class="GtkLabel"><property name="label">Send warning to community</property><property name="halign">end"/><property name="hexpand">True</property><style><class name="caption"/><class name="dim-label"/></style></object></child></object></child></object></child>
                                    </object>
                                    </child>
                                </object>
                                </child>
                                <child>
                                <object class="GtkBox" id="critical_lines_section">
                                    <property name="orientation">vertical</property><property name="spacing">8</property>
                                    <child><object class="GtkLabel"><property name="label">Critical Lines:</property><property name="halign">start</property><style><class name="heading"/></style></object></child>
                                    <child><object class="GtkBox" id="critical_lines_content"><property name="orientation">vertical</property><property name="spacing">4</property></object></child>
                                </object>
                                </child>
                                <child>
                                <object class="GtkBox" id="context_section">
                                    <property name="orientation">vertical</property><property name="spacing">8</property>
                                    <child><object class="GtkLabel"><property name="label">Additional Context:</property><property name="halign">start</property><style><class name="heading"/></style></object></child>
                                    <child><object class="GtkBox" id="context_list"><property name="orientation">vertical</property><property name="spacing">4</property></object></child>
                                </object>
                                </child>
                            </object>
                            </child>
                        </object>
                        </child>
                        <child>
                        <object class="GtkBox" id="action_area">
                            <property name="orientation">horizontal</property><property name="spacing">12</property><property name="margin-bottom">12</property><property name="margin-end">12</property><property name="margin-start">12</property><property name="margin-top">12</property><property name="halign">end</property>
                            <child><object class="GtkButton" id="close_button"><property name="label">Close</property></object></child>
                            <child><object class="GtkButton" id="copy_log_button"><property name="label">Copy Log</property><style><class name="suggested-action"/><class name="pill"/></style></object></child>
                        </object>
                        </child>
                    </object>
                    </child>
                </template>
                </interface>
            """
            self.builder.add_from_string(error_ui_content)

            # Load CSS for styles like .error-color (if not loaded globally by app)
            css_provider = Gtk.CssProvider()
            css_provider.load_from_data(b'.error-color { color: #f00; } .warning-color { color: #ffa500; } .bold { font-weight: bold; } .monospace { font-family: monospace; }')
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        def do_activate(self):
            if not self.window:
                self.window = Gtk.ApplicationWindow(application=self)
                self.window.set_title("ErrorHandler Test")
                self.window.set_default_size(300, 200)

                # Create a simple button to trigger the error dialog
                button = Gtk.Button(label="Show Error Dialog")
                button.connect("clicked", self.on_show_error_clicked)
                self.window.set_child(button)
                self.window.present()
                self.error_handler = ErrorHandler(self.builder, self.window, "1.0-test")

            # Example: Trigger an error directly after window is shown
            GLib.idle_add(self.trigger_test_errors)

        def trigger_test_errors(self):
            # Example 1: Security Risk Detected
            try:
                # Simulate an internal error leading to a security risk detection
                raise ValueError("An internal parsing error occurred in pkgbuild_analyzer.py")
            except Exception as e:
                context_security = ErrorContext(
                    category=ErrorCategory.SECURITY_RISK,
                    summary="Dangerous command found in PKGBUILD!",
                    details="The static analyzer detected a 'sudo rm -rf /' command in the prepare() function. This is highly dangerous and should be reviewed immediately.",
                    application_version=self.error_handler.app_version,
                    file_path="/home/user/my-bad-package/PKGBUILD",
                    pkgname="my-bad-package-git",
                    pkgver="1.2.3-1",
                    command_executed="paru -U --noconfirm",
                    stderr="Detected 'sudo rm -rf /' at line 42.",
                    traceback=traceback.format_exc(),
                    additional_problems=[
                        ErrorDetail("Less than 10 votes + 5 recent negative comments", level="warning"),
                        ErrorDetail("Maintainer without verified PGP keys", level="error"),
                        ErrorDetail("Unjustified `sudo` commands in PKGBUILD", level="critical", line_number=42, snippet="sudo rm -rf /")
                    ],
                    additional_context=[
                        ErrorDetail("Last update: 2 hours ago (unusual for stable package)"),
                        ErrorDetail("Maintainer: \"user123\" (no verifiable history)")
                    ],
                    suggested_actions=[SuggestedAction.IGNORE_RISK, SuggestedAction.VIEW_ANALYSIS]
                )
                self.error_handler.show_error_dialog(context_security)

            # Example 2: Command Execution Error
            GLib.timeout_add_seconds(3, self.show_command_error)
            return GLib.SOURCE_REMOVE

        def show_command_error(self):
            context_command = ErrorContext(
                category=ErrorCategory.COMMAND_EXECUTION,
                summary="Paru command failed!",
                details="The 'paru -Syu' command failed to execute correctly. This might indicate network issues or a problem with paru itself.",
                application_version=self.error_handler.app_version,
                command_executed="paru -Syu",
                working_directory="/",
                stdout=":: Synchronizing package databases...\nerror: failed retrieving file 'core.db' from mirror.archlinux.org : Could not resolve host: mirror.archlinux.org",
                stderr="error: failed to update core (invalid or corrupted database (PGP signature))\nerror: failed to synchronize all databases",
                additional_problems=[
                    ErrorDetail("Network connectivity issue during database sync."),
                    ErrorDetail("Corrupted pacman database detected.")
                ],
                suggested_actions=[SuggestedAction.RETRY, SuggestedAction.CHECK_LOG, SuggestedAction.CONSULT_DOCS]
            )
            self.error_handler.show_error_dialog(context_command)
            return GLib.SOURCE_REMOVE


        def on_show_error_clicked(self, button):
            # This will now trigger the security risk example
            self.trigger_test_errors()

    app = TestApp()
    sys.exit(app.run(sys.argv))
