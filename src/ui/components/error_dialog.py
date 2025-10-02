# src/ui/components/error_dialog.py
"""
Error Dialog Component for Paru GUI

This module implements a GTK Template-based error dialog that displays
contextual error information with suggested actions.

Author: MiniMax Agent
Date: 2025-09-25
"""

from gi.repository import Gtk, GObject, Adw, Gdk, GLib
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("error_dialog")

class ErrorCategory(Enum):
    """Categorias de erros para facilitar o tratamento e a sugestão de ações."""
    FILE_OPERATION = "File Operation Error"
    NETWORK = "Network Error"
    COMMAND_EXECUTION = "Command Execution Error"
    PKGBUILD_ANALYSIS = "PKGBUILD Analysis Error"
    SECURITY_RISK = "Security Risk"
    UI_ERROR = "UI Error"
    INTERNAL = "Internal Application Error"
    SYSTEM = "System Configuration Error"
    OTHER = "Other Error"

class SuggestedAction(Enum):
    """Ações sugeridas ao usuário para resolver ou mitigar um erro."""
    RETRY = "Retry Operation"
    CHECK_LOG = "View Detailed Log"
    CONSULT_DOCS = "Consult Documentation"
    REPORT_AUR = "Report to AUR Maintainer"
    OPEN_PKGBUILD = "Open PKGBUILD for Review"
    ADJUST_SETTINGS = "Adjust Preferences"
    INSTALL_DEPENDENCY = "Install Missing Dependency"
    CLOSE_APP = "Close Application"  # For critical, unrecoverable errors

@dataclass
class ErrorDetail:
    """Detalhes adicionais para um erro, que podem ser exibidos no log."""
    message: str
    level: str = "info"  # "info", "warning", "error"

@dataclass
class ErrorContext:
    """Contexto abrangente para um erro, a ser usado no diálogo de erro."""
    category: ErrorCategory
    summary: str
    details: str  # Mensagem mais longa e técnica do erro
    timestamp: datetime = field(default_factory=datetime.utcnow)
    file_path: Optional[str] = None
    pkgname: Optional[str] = None
    pkgver: Optional[str] = None
    command_executed: Optional[str] = None
    working_directory: Optional[str] = None
    stdout: Optional[str] = None  # Saída padrão do comando que falhou
    stderr: Optional[str] = None  # Saída de erro padrão do comando que falhou
    traceback: Optional[str] = None  # Stack trace completo se for uma exceção Python
    original_exception: Optional[Exception] = None  # A exceção Python original
    additional_context: List[ErrorDetail] = field(default_factory=list)
    suggested_actions: List[SuggestedAction] = field(default_factory=list)

@Gtk.Template(resource_path="/org/gnome/paru-gui/ui/components/error_dialog.ui")
class ErrorDialog(Gtk.Dialog):
    """Template-based Error Dialog for displaying contextual error information."""
    __gtype_name__ = "ErrorDialog"
    
    # Template Children - mapped from error_dialog.ui
    error_icon_header = Gtk.Template.Child()
    error_type_label = Gtk.Template.Child()
    error_package_label = Gtk.Template.Child()
    problems_list = Gtk.Template.Child()
    critical_lines_content = Gtk.Template.Child()
    context_list = Gtk.Template.Child()
    actions_buttons = Gtk.Template.Child()
    close_button = Gtk.Template.Child()
    copy_log_button = Gtk.Template.Child()
    
    # Additional elements for dynamic content
    error_scrolled_window = Gtk.Template.Child()
    error_content_box = Gtk.Template.Child()
    
    __gsignals__ = {
        'action-requested': (GObject.SignalFlags.RUN_LAST, None, (str, object)),
        'retry-requested': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'log-copy-requested': (GObject.SignalFlags.RUN_LAST, None, (object,))
    }
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._context: Optional[ErrorContext] = None
        self._app_version: str = "Unknown"
        self._action_handlers: Dict[SuggestedAction, Callable] = {}
        
        self.set_destroy_with_parent(True)
        self.set_default_size(700, 500)
        
        self._connect_signals()
    
    def _connect_signals(self):
        """Connect internal UI signals."""
        self.close_button.connect("clicked", self._on_close_clicked)
        self.copy_log_button.connect("clicked", self._on_copy_log_clicked)
    
    def populate_with_context(self, context: ErrorContext, app_version: str = "Unknown"):
        """Populate the dialog with error context information.
        
        Args:
            context: ErrorContext object containing all error details
            app_version: Application version string
        """
        self._context = context
        self._app_version = app_version
        
        logger.error(f"Populating error dialog: {context.summary} ({context.category.value})")
        
        # Set dialog title
        self.set_title(f"Error: {context.category.value}")
        
        # Populate header information
        self._populate_header(context)
        
        # Clear existing dynamic content
        self._clear_dynamic_content()
        
        # Populate content sections
        self._populate_problems_section(context)
        self._populate_critical_lines_section(context)
        self._populate_context_section(context)
        self._populate_actions_section(context)
    
    def _populate_header(self, context: ErrorContext):
        """Populate header with error type and package information."""
        if self.error_type_label:
            self.error_type_label.set_label(f"ERROR: {context.category.value.upper()}")
        
        if self.error_package_label:
            package_info = f"Package: {context.pkgname}" if context.pkgname else "N/A"
            if context.pkgver:
                package_info += f" (v{context.pkgver})"
            self.error_package_label.set_label(package_info)
    
    def _clear_dynamic_content(self):
        """Clear all dynamically added content from previous use."""
        containers = [self.problems_list, self.critical_lines_content, 
                     self.context_list, self.actions_buttons]
        
        for container in containers:
            if container:
                while container.get_first_child() is not None:
                    container.remove(container.get_first_child())
    
    def _populate_problems_section(self, context: ErrorContext):
        """Populate the detected problems section."""
        if not self.problems_list:
            return
        
        # Main problem summary
        problem_label = Gtk.Label(label=f"• {context.summary}")
        problem_label.set_halign(Gtk.Align.START)
        problem_label.set_wrap(True)
        problem_label.set_xalign(0)
        self.problems_list.append(problem_label)
        
        # Detailed description
        if context.details:
            detail_label = Gtk.Label(label=f"  Details: {context.details}")
            detail_label.set_halign(Gtk.Align.START)
            detail_label.set_wrap(True)
            detail_label.set_xalign(0)
            detail_label.add_css_class("caption")
            detail_label.add_css_class("dim-label")
            self.problems_list.append(detail_label)
    
    def _populate_critical_lines_section(self, context: ErrorContext):
        """Populate critical lines or command output section."""
        if not self.critical_lines_content:
            return
        
        # Show executed command if available
        if context.command_executed:
            cmd_label = Gtk.Label(label=f"Command: {context.command_executed}")
            cmd_label.add_css_class("monospace")
            cmd_label.add_css_class("error-color")
            cmd_label.set_halign(Gtk.Align.START)
            cmd_label.set_wrap(True)
            cmd_label.set_xalign(0)
            self.critical_lines_content.append(cmd_label)
        
        # Show stderr output if available
        if context.stderr:
            stderr_label = Gtk.Label(label=f"Error output: {context.stderr.strip()}")
            stderr_label.add_css_class("monospace")
            stderr_label.add_css_class("error-color")
            stderr_label.add_css_class("small-text")
            stderr_label.set_halign(Gtk.Align.START)
            stderr_label.set_wrap(True)
            stderr_label.set_xalign(0)
            self.critical_lines_content.append(stderr_label)
    
    def _populate_context_section(self, context: ErrorContext):
        """Populate additional context information."""
        if not self.context_list:
            return
        
        # File path context
        if context.file_path:
            ctx_label = Gtk.Label(label=f"- File Path: {context.file_path}")
            ctx_label.set_halign(Gtk.Align.START)
            ctx_label.set_wrap(True)
            ctx_label.set_xalign(0)
            self.context_list.append(ctx_label)
        
        # Working directory context
        if context.working_directory:
            ctx_label = Gtk.Label(label=f"- Working Directory: {context.working_directory}")
            ctx_label.set_halign(Gtk.Align.START)
            ctx_label.set_wrap(True)
            ctx_label.set_xalign(0)
            self.context_list.append(ctx_label)
        
        # Traceback availability
        if context.traceback:
            ctx_label = Gtk.Label(label="- Internal Traceback available in full log.")
            ctx_label.set_halign(Gtk.Align.START)
            ctx_label.set_wrap(True)
            ctx_label.set_xalign(0)
            self.context_list.append(ctx_label)
        
        # Additional context details
        for detail in context.additional_context:
            det_label = Gtk.Label(label=f"- {detail.message}")
            det_label.set_halign(Gtk.Align.START)
            det_label.set_wrap(True)
            det_label.set_xalign(0)
            
            if detail.level == "warning":
                det_label.add_css_class("warning-color")
            elif detail.level == "error":
                det_label.add_css_class("error-color")
            
            self.context_list.append(det_label)
    
    def _populate_actions_section(self, context: ErrorContext):
        """Populate suggested actions buttons."""
        if not self.actions_buttons:
            return
        
        for action in context.suggested_actions:
            button = self._create_action_button(action, context)
            if button:
                self.actions_buttons.append(button)
    
    def _create_action_button(self, action: SuggestedAction, context: ErrorContext) -> Optional[Gtk.Button]:
        """Create a button for a suggested action."""
        button = Gtk.Button()
        button.add_css_class("flat")
        button.add_css_class("pill")
        
        action_config = {
            SuggestedAction.RETRY: ("Retry", "suggested-action", self._on_retry_clicked),
            SuggestedAction.CHECK_LOG: ("View Log", "warning-color", self._on_view_log_clicked),
            SuggestedAction.CONSULT_DOCS: ("Consult Docs", None, self._on_consult_docs_clicked),
            SuggestedAction.REPORT_AUR: ("Report to AUR", None, self._on_report_aur_clicked),
            SuggestedAction.OPEN_PKGBUILD: ("Open PKGBUILD", None, self._on_open_pkgbuild_clicked),
            SuggestedAction.ADJUST_SETTINGS: ("Adjust Settings", None, self._on_adjust_settings_clicked),
            SuggestedAction.INSTALL_DEPENDENCY: ("Install Dependency", "suggested-action", self._on_install_dependency_clicked),
            SuggestedAction.CLOSE_APP: ("Close Application", "destructive-action", self._on_close_app_clicked)
        }
        
        if action not in action_config:
            return None
        
        label, css_class, callback = action_config[action]
        button.set_label(label)
        
        if css_class:
            button.add_css_class(css_class)
        
        button.connect("clicked", lambda b, a=action: callback(a))
        
        return button
    
    def register_action_handler(self, action: SuggestedAction, handler: Callable):
        """Register a custom handler for a specific action.
        
        Args:
            action: The SuggestedAction enum value
            handler: Callable that takes (action, context) as parameters
        """
        self._action_handlers[action] = handler
    
    def _on_close_clicked(self, button: Gtk.Button):
        """Handle close button click."""
        self.close()
    
    def _on_copy_log_clicked(self, button: Gtk.Button):
        """Handle copy log button click."""
        if self._context:
            self.emit('log-copy-requested', self._context)
            self._copy_log_to_clipboard()
    
    def _copy_log_to_clipboard(self):
        """Copy formatted log to clipboard."""
        if not self._context:
            return
        
        log_content = self._format_full_log(self._context)
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set_text(log_content)
        logger.info("Error log copied to clipboard.")
        
        # Show confirmation toast if possible
        self._show_toast("Error log copied to clipboard!")
    
    def _format_full_log(self, context: ErrorContext) -> str:
        """Format all error context details into a comprehensive log string."""
        log_parts: List[str] = [
            f"--- Paru GUI Error Report ({context.timestamp.isoformat()}) ---",
            f"Application Version: {self._app_version}",
            f"Error Category: {context.category.value}",
            f"Summary: {context.summary}",
            f"Details: {context.details}",
        ]
        
        if context.pkgname:
            log_parts.append(f"Related Package: {context.pkgname}")
        if context.pkgver:
            log_parts.append(f"Package Version: {context.pkgver}")
        if context.file_path:
            log_parts.append(f"File Path: {context.file_path}")
        if context.working_directory:
            log_parts.append(f"Working Directory: {context.working_directory}")
        if context.command_executed:
            log_parts.append(f"Command Executed: {context.command_executed}")
        
        if context.stdout:
            log_parts.append("\n--- STDOUT ---")
            log_parts.append(context.stdout.strip())
        if context.stderr:
            log_parts.append("\n--- STDERR ---")
            log_parts.append(context.stderr.strip())
        if context.traceback:
            log_parts.append("\n--- PYTHON TRACEBACK ---")
            log_parts.append(context.traceback.strip())
        if context.original_exception:
            log_parts.append(f"\nOriginal Exception Type: {type(context.original_exception).__name__}")
        if context.additional_context:
            log_parts.append("\n--- ADDITIONAL CONTEXT ---")
            for detail in context.additional_context:
                log_parts.append(f"[{detail.level.upper()}] {detail.message}")
        
        log_parts.append("\n--- END OF REPORT ---")
        return "\n".join(log_parts)
    
    def _show_toast(self, message: str):
        """Show a toast notification if possible."""
        try:
            parent = self.get_transient_for()
            if parent:
                toast_overlay = Adw.ToastOverlay.get_for_widget(parent)
                if toast_overlay:
                    toast = Adw.Toast.new(message)
                    toast.set_timeout(2)
                    toast_overlay.add_toast(toast)
        except Exception as e:
            logger.debug(f"Could not show toast: {e}")
    
    # Action button handlers - emit signals to allow external handling
    def _on_retry_clicked(self, action: SuggestedAction):
        if action in self._action_handlers:
            self._action_handlers[action](action, self._context)
        else:
            self.emit('retry-requested', self._context)
    
    def _on_view_log_clicked(self, action: SuggestedAction):
        if action in self._action_handlers:
            self._action_handlers[action](action, self._context)
        else:
            self.emit('action-requested', 'view-log', self._context)
    
    def _on_consult_docs_clicked(self, action: SuggestedAction):
        if action in self._action_handlers:
            self._action_handlers[action](action, self._context)
        else:
            self.emit('action-requested', 'consult-docs', self._context)
    
    def _on_report_aur_clicked(self, action: SuggestedAction):
        if action in self._action_handlers:
            self._action_handlers[action](action, self._context)
        else:
            self.emit('action-requested', 'report-aur', self._context)
    
    def _on_open_pkgbuild_clicked(self, action: SuggestedAction):
        if action in self._action_handlers:
            self._action_handlers[action](action, self._context)
        else:
            self.emit('action-requested', 'open-pkgbuild', self._context)
    
    def _on_adjust_settings_clicked(self, action: SuggestedAction):
        if action in self._action_handlers:
            self._action_handlers[action](action, self._context)
        else:
            self.emit('action-requested', 'adjust-settings', self._context)
    
    def _on_install_dependency_clicked(self, action: SuggestedAction):
        if action in self._action_handlers:
            self._action_handlers[action](action, self._context)
        else:
            self.emit('action-requested', 'install-dependency', self._context)
    
    def _on_close_app_clicked(self, action: SuggestedAction):
        if action in self._action_handlers:
            self._action_handlers[action](action, self._context)
        else:
            self.emit('action-requested', 'close-app', self._context)
