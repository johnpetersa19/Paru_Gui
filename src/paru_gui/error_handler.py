import logging
import traceback
import os
import json
import datetime
import hashlib
from enum import Enum
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, asdict
from gi.repository import Gtk, Adw, GLib, Gio, Gdk

logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("error_handler")

class ErrorLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class ErrorCategory(Enum):
    SYSTEM = "system"
    NETWORK = "network"
    PARSING = "parsing"
    SECURITY = "security"
    USER_INPUT = "user_input"
    FILE_IO = "file_io"
    DEPENDENCIES = "dependencies"
    UNKNOWN = "unknown"

@dataclass
class ErrorReport:
    timestamp: str
    error_id: str
    level: ErrorLevel
    category: ErrorCategory
    title: str
    message: str
    context: str
    stack_trace: Optional[str] = None
    user_action: Optional[str] = None
    system_info: Optional[Dict[str, Any]] = None
    suggested_actions: List[str] = None

    def __post_init__(self):
        if self.suggested_actions is None:
            self.suggested_actions = []

class MarkdownFormatter:
    @staticmethod
    def format_error_report(report: ErrorReport) -> str:
        level_emoji = {
            ErrorLevel.CRITICAL: "🔴",
            ErrorLevel.HIGH: "🟠", 
            ErrorLevel.MEDIUM: "🟡",
            ErrorLevel.LOW: "🔵",
            ErrorLevel.INFO: "ℹ️"
        }
        
        category_emoji = {
            ErrorCategory.SYSTEM: "⚙️",
            ErrorCategory.NETWORK: "🌐",
            ErrorCategory.PARSING: "📝",
            ErrorCategory.SECURITY: "🔒",
            ErrorCategory.USER_INPUT: "👤",
            ErrorCategory.FILE_IO: "📁",
            ErrorCategory.DEPENDENCIES: "📦",
            ErrorCategory.UNKNOWN: "❓"
        }

        markdown = f"""# {level_emoji.get(report.level, '❓')} {report.title}

**Error ID:** `{report.error_id}`  
**Level:** {level_emoji.get(report.level, '❓')} {report.level.value.upper()}  
**Category:** {category_emoji.get(report.category, '❓')} {report.category.value.replace('_', ' ').title()}  
**Timestamp:** {report.timestamp}  
**Context:** {report.context}

## Description

{report.message}

"""

        if report.user_action:
            markdown += f"""## User Action

{report.user_action}

"""

        if report.suggested_actions:
            markdown += "## Suggested Actions\n\n"
            for i, action in enumerate(report.suggested_actions, 1):
                markdown += f"{i}. {action}\n"
            markdown += "\n"

        if report.system_info:
            markdown += "## System Information\n\n"
            for key, value in report.system_info.items():
                markdown += f"- **{key.replace('_', ' ').title()}:** {value}\n"
            markdown += "\n"

        if report.stack_trace:
            markdown += f"""## Stack Trace

```python
{report.stack_trace}
```

"""

        return markdown

    @staticmethod
    def format_log_entry(level: str, message: str, context: str = "", timestamp: str = None) -> str:
        if timestamp is None:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        level_format = {
            'CRITICAL': '🔴 **CRITICAL**',
            'ERROR': '❌ **ERROR**',
            'WARNING': '⚠️ **WARNING**',
            'INFO': 'ℹ️ **INFO**',
            'DEBUG': '🔍 **DEBUG**'
        }
        
        formatted_level = level_format.get(level.upper(), f'📝 **{level.upper()}**')
        context_text = f" - *{context}*" if context else ""
        
        return f"`{timestamp}` {formatted_level}{context_text}: {message}"

class ErrorHandler:
    def __init__(self, parent_window: Optional[Gtk.Window] = None, app_version: str = "1.0.0"):
        self.parent_window = parent_window
        self.app_version = app_version
        self._action_handlers: Dict[str, Callable] = {}
        self._error_counts: Dict[str, int] = {}
        self._error_history: List[ErrorReport] = []
        self._max_history = 100
        self._log_file_path = os.path.expanduser("~/.cache/paru-gui/error_logs.md")
        self._ensure_log_directory()
        
        logger.info(f"ErrorHandler initialized - Version: {app_version}")

    def _ensure_log_directory(self):
        log_dir = os.path.dirname(self._log_file_path)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

    def _generate_error_id(self, error_str: str, context: str) -> str:
        combined = f"{error_str}_{context}_{datetime.datetime.now().strftime('%Y%m%d')}"
        return hashlib.md5(combined.encode()).hexdigest()[:8]

    def _get_system_info(self) -> Dict[str, Any]:
        try:
            import platform
            import psutil
            
            return {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "architecture": platform.architecture()[0],
                "processor": platform.processor() or "Unknown",
                "memory_total": f"{psutil.virtual_memory().total // (1024**3)} GB",
                "memory_available": f"{psutil.virtual_memory().available // (1024**3)} GB",
                "disk_free": f"{psutil.disk_usage('/').free // (1024**3)} GB",
                "app_version": self.app_version
            }
        except ImportError:
            return {
                "app_version": self.app_version,
                "platform": "Unknown",
                "python_version": "Unknown"
            }
        except Exception:
            return {"app_version": self.app_version}

    def _categorize_error(self, error) -> ErrorCategory:
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        if any(keyword in error_str for keyword in ['network', 'connection', 'timeout', 'dns']):
            return ErrorCategory.NETWORK
        elif any(keyword in error_str for keyword in ['permission', 'access', 'unauthorized']):
            return ErrorCategory.SECURITY
        elif any(keyword in error_str for keyword in ['file', 'directory', 'path', 'io']):
            return ErrorCategory.FILE_IO
        elif any(keyword in error_str for keyword in ['parse', 'syntax', 'format']):
            return ErrorCategory.PARSING
        elif any(keyword in error_str for keyword in ['module', 'import', 'dependency']):
            return ErrorCategory.DEPENDENCIES
        elif 'system' in error_str or error_type in ['oserror', 'systemerror']:
            return ErrorCategory.SYSTEM
        else:
            return ErrorCategory.UNKNOWN

    def _determine_error_level(self, error, context: str) -> ErrorLevel:
        error_type = type(error).__name__.lower()
        error_str = str(error).lower()
        
        critical_patterns = ['critical', 'fatal', 'segfault', 'memory', 'corruption']
        high_patterns = ['failed', 'error', 'exception', 'cannot', 'unable']
        medium_patterns = ['warning', 'deprecated', 'missing']
        
        if any(pattern in error_str for pattern in critical_patterns):
            return ErrorLevel.CRITICAL
        elif any(pattern in error_str for pattern in high_patterns):
            return ErrorLevel.HIGH
        elif any(pattern in error_str for pattern in medium_patterns):
            return ErrorLevel.MEDIUM
        else:
            return ErrorLevel.LOW

    def _get_suggested_actions(self, error, category: ErrorCategory) -> List[str]:
        suggestions = []
        
        if category == ErrorCategory.NETWORK:
            suggestions.extend([
                "Check your internet connection",
                "Verify that the target servers are accessible",
                "Check if a proxy or firewall is blocking the connection",
                "Try again later if the service is temporarily unavailable"
            ])
        elif category == ErrorCategory.FILE_IO:
            suggestions.extend([
                "Check if the file or directory exists",
                "Verify read/write permissions",
                "Ensure sufficient disk space is available",
                "Check if the file is being used by another process"
            ])
        elif category == ErrorCategory.DEPENDENCIES:
            suggestions.extend([
                "Install missing dependencies using your package manager",
                "Update existing packages to their latest versions",
                "Check if all required system libraries are installed"
            ])
        elif category == ErrorCategory.SECURITY:
            suggestions.extend([
                "Check file and directory permissions",
                "Run with appropriate user privileges",
                "Verify authentication credentials if required"
            ])
        elif category == ErrorCategory.PARSING:
            suggestions.extend([
                "Verify the input format is correct",
                "Check for syntax errors in configuration files",
                "Ensure all required fields are present"
            ])
        else:
            suggestions.extend([
                "Check the application logs for more details",
                "Restart the application if the issue persists",
                "Report this issue to the developers if it continues"
            ])
            
        return suggestions

    def set_parent_window(self, window: Gtk.Window):
        self.parent_window = window

    def handle_error(self, error, context: str = "Unknown", user_action: str = None) -> str:
        try:
            error_id = self._generate_error_id(str(error), context)
            category = self._categorize_error(error)
            level = self._determine_error_level(error, context)
            suggested_actions = self._get_suggested_actions(error, category)
            
            self._error_counts[error_id] = self._error_counts.get(error_id, 0) + 1
            
            report = ErrorReport(
                timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                error_id=error_id,
                level=level,
                category=category,
                title=f"{type(error).__name__}: {context}",
                message=str(error),
                context=context,
                stack_trace=traceback.format_exc() if traceback.format_exc().strip() != 'NoneType: None' else None,
                user_action=user_action,
                system_info=self._get_system_info(),
                suggested_actions=suggested_actions
            )
            
            self._error_history.append(report)
            if len(self._error_history) > self._max_history:
                self._error_history = self._error_history[-self._max_history:]
            
            self._log_to_file(report)
            self._log_to_console(report)
            
            if level in [ErrorLevel.CRITICAL, ErrorLevel.HIGH]:
                self.show_error_dialog(report)
            
            return error_id
            
        except Exception as handler_error:
            fallback_msg = f"Error Handler Failed: {handler_error} | Original: {error}"
            logger.critical(fallback_msg)
            print(f"CRITICAL: {fallback_msg}")
            return "handler_error"

    def handle_critical_error(self, error, context: str = "Critical Error", user_action: str = None) -> str:
        try:
            error_id = self._generate_error_id(str(error), context)
            category = self._categorize_error(error)
            suggested_actions = self._get_suggested_actions(error, category)
            
            self._error_counts[error_id] = self._error_counts.get(error_id, 0) + 1
            
            report = ErrorReport(
                timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                error_id=error_id,
                level=ErrorLevel.CRITICAL,
                category=category,
                title=f"Critical Error: {context}",
                message=str(error),
                context=context,
                stack_trace=traceback.format_exc() if traceback.format_exc().strip() != 'NoneType: None' else None,
                user_action=user_action,
                system_info=self._get_system_info(),
                suggested_actions=suggested_actions
            )
            
            self._error_history.append(report)
            if len(self._error_history) > self._max_history:
                self._error_history = self._error_history[-self._max_history:]
            
            self._log_to_file(report)
            self._log_to_console(report)
            
            self.show_error_dialog(report)
            
            return error_id
            
        except Exception as handler_error:
            fallback_msg = f"Critical Error Handler Failed: {handler_error} | Original: {error}"
            logger.critical(fallback_msg)
            print(f"CRITICAL: {fallback_msg}")
            return "critical_handler_error"

    def _log_to_file(self, report: ErrorReport):
        try:
            markdown_content = MarkdownFormatter.format_error_report(report)
            
            with open(self._log_file_path, 'a', encoding='utf-8') as f:
                f.write(markdown_content)
                f.write("\n---\n\n")
                
        except Exception as e:
            logger.error(f"Failed to write to log file: {e}")

    def _log_to_console(self, report: ErrorReport):
        level_map = {
            ErrorLevel.CRITICAL: logging.CRITICAL,
            ErrorLevel.HIGH: logging.ERROR,
            ErrorLevel.MEDIUM: logging.WARNING,
            ErrorLevel.LOW: logging.INFO,
            ErrorLevel.INFO: logging.INFO
        }
        
        log_level = level_map.get(report.level, logging.ERROR)
        logger.log(log_level, f"[{report.context}] {report.message}")

    def log_warning(self, message: str, context: str = "Warning"):
        try:
            formatted_log = MarkdownFormatter.format_log_entry("WARNING", message, context)
            logger.warning(f"[{context}] {message}")
            
            with open(self._log_file_path, 'a', encoding='utf-8') as f:
                f.write(f"{formatted_log}\n\n")
                
        except Exception as e:
            logger.error(f"Failed to log warning: {e}")

    def log_info(self, message: str, context: str = "Info"):
        try:
            formatted_log = MarkdownFormatter.format_log_entry("INFO", message, context)
            logger.info(f"[{context}] {message}")
            
            with open(self._log_file_path, 'a', encoding='utf-8') as f:
                f.write(f"{formatted_log}\n\n")
                
        except Exception as e:
            logger.error(f"Failed to log info: {e}")

    def show_error_dialog(self, report: ErrorReport):
        try:
            if not self.parent_window:
                print(f"ERROR DIALOG: {report.title} - {report.message}")
                return
                
            dialog = Adw.MessageDialog.new(
                self.parent_window,
                report.title,
                report.message
            )
            
            dialog.add_response("ok", "OK")
            
            if report.suggested_actions:
                dialog.add_response("details", "Show Details")
                dialog.set_response_appearance("details", Adw.ResponseAppearance.SUGGESTED)
                
            dialog.connect("response", self._on_error_dialog_response, report)
            dialog.present()
            
        except Exception as e:
            logger.error(f"Failed to show error dialog: {e}")
            print(f"ERROR DIALOG: {report.title} - {report.message}")

    def _on_error_dialog_response(self, dialog, response_id, report: ErrorReport):
        if response_id == "details":
            self.show_detailed_error_dialog(report)
        dialog.close()

    def show_detailed_error_dialog(self, report: ErrorReport):
        try:
            if not self.parent_window:
                return
                
            dialog = Adw.Dialog()
            dialog.set_title("Error Details")
            
            content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            content_box.set_margin_top(24)
            content_box.set_margin_bottom(24)
            content_box.set_margin_start(24)
            content_box.set_margin_end(24)
            
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scrolled.set_min_content_height(400)
            scrolled.set_min_content_width(600)
            
            text_view = Gtk.TextView()
            text_view.set_editable(False)
            text_view.set_wrap_mode(Gtk.WrapMode.WORD)
            text_view.set_monospace(True)
            
            buffer = text_view.get_buffer()
            markdown_content = MarkdownFormatter.format_error_report(report)
            buffer.set_text(markdown_content)
            
            scrolled.set_child(text_view)
            content_box.append(scrolled)
            
            button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            button_box.set_halign(Gtk.Align.END)
            
            copy_button = Gtk.Button(label="Copy to Clipboard")
            copy_button.connect("clicked", self._copy_error_details, markdown_content)
            button_box.append(copy_button)
            
            close_button = Gtk.Button(label="Close")
            close_button.add_css_class("suggested-action")
            close_button.connect("clicked", lambda b: dialog.close())
            button_box.append(close_button)
            
            content_box.append(button_box)
            dialog.set_child(content_box)
            dialog.present(self.parent_window)
            
        except Exception as e:
            logger.error(f"Failed to show detailed error dialog: {e}")

    def _copy_error_details(self, button, content: str):
        try:
            clipboard = Gdk.Display.get_default().get_clipboard()
            clipboard.set(content)
        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")

    def show_simple_dialog(self, title: str, message: str, dialog_type: str = "error"):
        try:
            if not self.parent_window:
                print(f"DIALOG: {title} - {message}")
                return
                
            dialog = Adw.MessageDialog.new(self.parent_window, title, message)
            dialog.add_response("ok", "OK")
            
            if dialog_type == "error":
                dialog.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
            elif dialog_type == "warning":
                dialog.set_response_appearance("ok", Adw.ResponseAppearance.DEFAULT)
                
            dialog.present()
            
        except Exception as e:
            logger.error(f"Failed to show simple dialog: {e}")
            print(f"DIALOG: {title} - {message}")

    def register_action_handler(self, action_name: str, handler: Callable):
        self._action_handlers[action_name] = handler
        logger.info(f"Action handler registered: {action_name}")

    def safe_call(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            func_name = func.__name__ if hasattr(func, '__name__') else 'unknown_function'
            self.handle_error(e, f"safe_call({func_name})")
            return None

    def get_error_statistics(self) -> Dict[str, Any]:
        return {
            "total_errors": len(self._error_history),
            "error_counts": dict(self._error_counts),
            "categories": {cat.value: len([r for r in self._error_history if r.category == cat]) 
                         for cat in ErrorCategory},
            "levels": {level.value: len([r for r in self._error_history if r.level == level]) 
                      for level in ErrorLevel}
        }

    def clear_error_history(self):
        self._error_history.clear()
        self._error_counts.clear()
        logger.info("Error history cleared")

    def export_error_report(self, file_path: str) -> bool:
        try:
            report_data = {
                "export_timestamp": datetime.datetime.now().isoformat(),
                "app_version": self.app_version,
                "statistics": self.get_error_statistics(),
                "errors": [asdict(report) for report in self._error_history]
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Error report exported to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export error report: {e}")
            return False
