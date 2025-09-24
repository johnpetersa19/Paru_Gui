# src/paru_gui/error_handler.py
"""
Error Handler for Paru GUI

Simplified error handler that uses the new template-based ErrorDialog.
This replaces the previous Gtk.Builder-based implementation.

Author: MiniMax Agent
Date: 2025-09-25
"""

import logging
import traceback
from typing import Optional, Callable, Dict, Any
from gi.repository import Gtk, Adw, GLib

# Import the new template-based ErrorDialog
from .ui.components.error_dialog import (
    ErrorDialog, ErrorContext, ErrorCategory, SuggestedAction, ErrorDetail
)

logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("error_handler")

class ErrorHandler:
    """Simplified Error Handler using template-based ErrorDialog."""

    def __init__(self, parent_window: Gtk.Window, app_version: str):
        """
        Initialize the ErrorHandler.

        Args:
            parent_window: Parent window for error dialogs
            app_version: Application version string
        """
        self.parent_window = parent_window
        self.app_version = app_version
        self._action_handlers: Dict[str, Callable] = {}

        logger.info("ErrorHandler initialized with template-based approach.")

    def show_error_dialog(self, context: ErrorContext) -> ErrorDialog:
        """
        Show an error dialog with the provided context.

        Args:
            context: ErrorContext object containing all error details

        Returns:
            ErrorDialog instance that was created and shown
        """
        logger.error(f"Showing error dialog: {context.summary} ({context.category.value})")

        try:
            # Create new ErrorDialog instance
            dialog = ErrorDialog(transient_for=self.parent_window)

            # Populate with context
            dialog.populate_with_context(context, self.app_version)

            # Connect to dialog signals for handling actions
            dialog.connect('action-requested', self._on_dialog_action_requested)
            dialog.connect('retry-requested', self._on_retry_requested)
            dialog.connect('log-copy-requested', self._on_log_copy_requested)

            # Register any custom action handlers
            self._register_dialog_handlers(dialog)

            # Show the dialog
            dialog.present()

            return dialog

        except Exception as e:
            logger.critical(f"Failed to create ErrorDialog: {e}")
            # Fallback to simple message dialog
            self._show_fallback_dialog(context)
            return None

    def register_action_handler(self, action_name: str, handler: Callable):
        """
        Register a custom handler for dialog actions.

        Args:
            action_name: Name of the action (e.g., 'view-log', 'retry')
            handler: Callable that takes (action_name, context) parameters
        """
        self._action_handlers[action_name] = handler

    def _register_dialog_handlers(self, dialog: ErrorDialog):
        """Register standard action handlers with the dialog."""
        # Register handlers for specific SuggestedAction enums
        standard_handlers = {
            SuggestedAction.RETRY: self._handle_retry_action,
            SuggestedAction.CHECK_LOG: self._handle_view_log_action,
            SuggestedAction.CONSULT_DOCS: self._handle_consult_docs_action,
            SuggestedAction.REPORT_AUR: self._handle_report_aur_action,
            SuggestedAction.OPEN_PKGBUILD: self._handle_open_pkgbuild_action,
            SuggestedAction.ADJUST_SETTINGS: self._handle_adjust_settings_action,
            SuggestedAction.INSTALL_DEPENDENCY: self._handle_install_dependency_action,
            SuggestedAction.CLOSE_APP: self._handle_close_app_action
        }

        for action, handler in standard_handlers.items():
            dialog.register_action_handler(action, handler)

    def _on_dialog_action_requested(self, dialog: ErrorDialog, action_name: str, context: ErrorContext):
        """Handle action requests from the dialog."""
        logger.info(f"Dialog action requested: {action_name}")

        if action_name in self._action_handlers:
            try:
                self._action_handlers[action_name](action_name, context)
            except Exception as e:
                logger.error(f"Error executing action handler {action_name}: {e}")
        else:
            logger.warning(f"No handler registered for action: {action_name}")

    def _on_retry_requested(self, dialog: ErrorDialog, context: ErrorContext):
        """Handle retry requests from the dialog."""
        logger.info("Retry requested from error dialog")
        if 'retry' in self._action_handlers:
            try:
                self._action_handlers['retry']('retry', context)
            except Exception as e:
                logger.error(f"Error executing retry handler: {e}")

    def _on_log_copy_requested(self, dialog: ErrorDialog, context: ErrorContext):
        """Handle log copy requests from the dialog."""
        logger.info("Log copy completed from error dialog")
        # The dialog handles the actual copying, this is just for logging

    # Standard action handlers - these can be overridden by registering custom handlers
    def _handle_retry_action(self, action: SuggestedAction, context: ErrorContext):
        """Handle retry action - override this or register custom handler."""
        logger.info(f"Default retry action handler called for: {context.summary}")
        # Default implementation - can be overridden

    def _handle_view_log_action(self, action: SuggestedAction, context: ErrorContext):
        """Handle view log action."""
        logger.info("View log action triggered")
        # Could open log viewer or terminal

    def _handle_consult_docs_action(self, action: SuggestedAction, context: ErrorContext):
        """Handle consult documentation action."""
        logger.info("Consult docs action triggered")
        # Could open documentation in browser

    def _handle_report_aur_action(self, action: SuggestedAction, context: ErrorContext):
        """Handle report to AUR action."""
        logger.info("Report AUR action triggered")
        # Could open AUR package page or compose email

    def _handle_open_pkgbuild_action(self, action: SuggestedAction, context: ErrorContext):
        """Handle open PKGBUILD action."""
        logger.info("Open PKGBUILD action triggered")
        # Could open PKGBUILD file in editor

    def _handle_adjust_settings_action(self, action: SuggestedAction, context: ErrorContext):
        """Handle adjust settings action."""
        logger.info("Adjust settings action triggered")
        # Could open preferences dialog

    def _handle_install_dependency_action(self, action: SuggestedAction, context: ErrorContext):
        """Handle install dependency action."""
        logger.info("Install dependency action triggered")
        # Could trigger dependency installation

    def _handle_close_app_action(self, action: SuggestedAction, context: ErrorContext):
        """Handle close application action."""
        logger.info("Close app action triggered")
        # Could close the entire application
        if self.parent_window:
            self.parent_window.close()

    def _show_fallback_dialog(self, context: ErrorContext):
        """Show a simple fallback dialog if the main ErrorDialog fails."""
        logger.warning("Using fallback error dialog")

        try:
            dialog = Adw.MessageDialog(
                transient_for=self.parent_window,
                heading=f"Critical Error: {context.category.value}",
                body=f"{context.summary}\n\nDetails: {context.details}\n\nCheck logs for more information."
            )
            dialog.add_response("close", "Close")
            dialog.set_response_appearance("close", Adw.ResponseAppearance.SUGGESTED)
            dialog.present()

        except Exception as e:
            logger.critical(f"Even fallback dialog failed: {e}")
            # Last resort - print to stderr
            print(f"CRITICAL ERROR: {context.category.value}")
            print(f"Summary: {context.summary}")
            print(f"Details: {context.details}")

    # Convenience methods for creating common error contexts
    @staticmethod
    def create_file_error(summary: str, file_path: str, details: str = "") -> ErrorContext:
        """Create a file operation error context."""
        return ErrorContext(
            category=ErrorCategory.FILE_OPERATION,
            summary=summary,
            details=details or f"Error accessing file: {file_path}",
            file_path=file_path,
            suggested_actions=[SuggestedAction.RETRY, SuggestedAction.CHECK_LOG]
        )

    @staticmethod
    def create_command_error(summary: str, command: str, stderr: str = "",
                           working_dir: str = "") -> ErrorContext:
        """Create a command execution error context."""
        return ErrorContext(
            category=ErrorCategory.COMMAND_EXECUTION,
            summary=summary,
            details=f"Command failed: {command}",
            command_executed=command,
            stderr=stderr,
            working_directory=working_dir,
            suggested_actions=[SuggestedAction.RETRY, SuggestedAction.CHECK_LOG]
        )

    @staticmethod
    def create_security_error(summary: str, pkgname: str, details: str,
                            critical_lines: str = "") -> ErrorContext:
        """Create a security risk error context."""
        context = ErrorContext(
            category=ErrorCategory.SECURITY_RISK,
            summary=summary,
            details=details,
            pkgname=pkgname,
            suggested_actions=[
                SuggestedAction.REPORT_AUR,
                SuggestedAction.OPEN_PKGBUILD,
                SuggestedAction.CHECK_LOG
            ]
        )

        if critical_lines:
            context.additional_context.append(
                ErrorDetail(f"Critical code: {critical_lines}", "error")
            )

        return context

    @staticmethod
    def create_network_error(summary: str, details: str = "") -> ErrorContext:
        """Create a network error context."""
        return ErrorContext(
            category=ErrorCategory.NETWORK,
            summary=summary,
            details=details or "Network connection failed",
            suggested_actions=[SuggestedAction.RETRY, SuggestedAction.ADJUST_SETTINGS]
        )

    @staticmethod
    def create_internal_error(summary: str, exception: Exception,
                            details: str = "") -> ErrorContext:
        """Create an internal application error context."""
        return ErrorContext(
            category=ErrorCategory.INTERNAL,
            summary=summary,
            details=details or f"Internal error: {type(exception).__name__}: {str(exception)}",
            original_exception=exception,
            traceback=traceback.format_exc(),
            suggested_actions=[SuggestedAction.CHECK_LOG, SuggestedAction.CLOSE_APP]
        )

# Example usage function
def example_usage():
    """Example of how to use the new ErrorHandler."""
    # This would typically be called from your main window or application

    # Create error handler
    # error_handler = ErrorHandler(parent_window, "1.0.0")

    # Register custom action handlers if needed
    # error_handler.register_action_handler('retry', my_custom_retry_handler)

    # Create and show error dialog
    # context = ErrorHandler.create_security_error(
    #     "Suspicious PKGBUILD detected",
    #     "malicious-package-git",
    #     "Package contains potentially harmful commands",
    #     "sudo rm -rf /usr/bin/*"
    # )
    # error_handler.show_error_dialog(context)

    pass
