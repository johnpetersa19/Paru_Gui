import logging
import traceback
from enum import Enum
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime

from gi.repository import Gtk, Adw, Gdk # Gdk para copiar para clipboard


logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("error_handler")

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
    CLOSE_APP = "Close Application" # For critical, unrecoverable errors

@dataclass
class ErrorDetail:
    """Detalhes adicionais para um erro, que podem ser exibidos no log."""
    message: str
    level: str = "info" # "info", "warning", "error"

@dataclass
class ErrorContext:
    """Contexto abrangente para um erro, a ser usado no diálogo de erro."""
    category: ErrorCategory
    summary: str
    details: str # Mensagem mais longa e técnica do erro
    timestamp: datetime = field(default_factory=datetime.utcnow)
    file_path: Optional[str] = None
    pkgname: Optional[str] = None
    pkgver: Optional[str] = None
    command_executed: Optional[str] = None
    working_directory: Optional[str] = None
    stdout: Optional[str] = None # Saída padrão do comando que falhou
    stderr: Optional[str] = None # Saída de erro padrão do comando que falhou
    traceback: Optional[str] = None # Stack trace completo se for uma exceção Python
    original_exception: Optional[Exception] = None # A exceção Python original
    additional_context: List[ErrorDetail] = field(default_factory=list)
    suggested_actions: List[SuggestedAction] = field(default_factory=list)

class ErrorHandler:
    """
    Gerencia a exibição de diálogos de erro contextuais e sugestões de ações.
    Usa Gtk.Builder para carregar a UI do diálogo a partir de um arquivo .ui.
    """
    def __init__(self, builder: Gtk.Builder, parent_window: Gtk.Window, app_version: str):
        self.builder = builder
        self.parent_window = parent_window
        self.app_version = app_version
        logger.info("ErrorHandler initialized.")

        # Carregar o template do diálogo de erro uma vez
        self.error_dialog_template = self.builder.get_object('ErrorDialog')
        if not self.error_dialog_template:
            logger.critical("ErrorDialog template (error_dialog.ui) not found in Gtk.Builder.")
            raise RuntimeError("Missing ErrorDialog UI template.")
        # Desparentar para que o template possa ser instanciado múltiplas vezes
        # self.error_dialog_template.unparent() # Adw.Dialogs são criados a partir do template, não desparentados assim.

    def show_error_dialog(self, context: ErrorContext):
        """
        Exibe um diálogo de erro rico em contexto para o usuário.

        Args:
            context: Um objeto ErrorContext contendo todos os detalhes do erro.
        """
        logger.error(f"Showing error dialog: {context.summary} ({context.category.value})")

        # Criar uma nova instância do diálogo a partir do template
        dialog = self.builder.get_object('ErrorDialog', self.parent_window) # 'self.parent_window' é o scope
        if not dialog:
            logger.critical("Failed to create ErrorDialog instance from template.")
            # Fallback to a simple message dialog
            self._show_fallback_dialog(context)
            return

        dialog.set_transient_for(self.parent_window)
        dialog.set_modal(True)
        dialog.set_title(f"Error: {context.category.value}") # Define o título da janela do diálogo

        # Obter os widgets do diálogo usando o escopo da instância `dialog`
        error_icon_header = self.builder.get_object('error_icon_header', dialog)
        error_type_label = self.builder.get_object('error_type_label', dialog)
        error_package_label = self.builder.get_object('error_package_label', dialog)
        problems_list = self.builder.get_object('problems_list', dialog)
        critical_lines_content = self.builder.get_object('critical_lines_content', dialog)
        context_list = self.builder.get_object('context_list', dialog)
        actions_buttons_box = self.builder.get_object('actions_buttons', dialog)
        close_button = self.builder.get_object('close_button', dialog)
        copy_log_button = self.builder.get_object('copy_log_button', dialog)

        # Preencher o cabeçalho do erro
        if error_type_label: error_type_label.set_label(f"ERROR: {context.category.value.upper()}")
        if error_package_label:
            package_info = f"Package: {context.pkgname}" if context.pkgname else "N/A"
            if context.pkgver: package_info += f" (v{context.pkgver})"
            error_package_label.set_label(package_info)

        # Limpar listas anteriores
        if problems_list:
            while problems_list.get_first_child() is not None:
                problems_list.remove(problems_list.get_first_child())
        if critical_lines_content:
            while critical_lines_content.get_first_child() is not None:
                critical_lines_content.remove(critical_lines_content.get_first_child())
        if context_list:
            while context_list.get_first_child() is not None:
                context_list.remove(context_list.get_first_child())
        if actions_buttons_box:
            while actions_buttons_box.get_first_child() is not None:
                actions_buttons_box.remove(actions_buttons_box.get_first_child())


        # Preencher "Detected Problems" com o resumo e detalhes
        problem_label = Gtk.Label(label=f"• {context.summary}")
        problem_label.set_halign(Gtk.Align.START)
        problem_label.set_wrap(True)
        problem_label.set_xalign(0)
        if problems_list: problems_list.append(problem_label)

        detail_label = Gtk.Label(label=f"  Details: {context.details}")
        detail_label.set_halign(Gtk.Align.START)
        detail_label.set_wrap(True)
        detail_label.set_xalign(0)
        detail_label.add_css_class("caption")
        detail_label.add_css_class("dim-label")
        if problems_list: problems_list.append(detail_label)


        # Preencher "Critical Lines" ou snippets (se aplicável)
        if context.command_executed:
            cmd_label = Gtk.Label(label=f"Command: {context.command_executed}")
            cmd_label.add_css_class("monospace")
            cmd_label.add_css_class("error-color")
            cmd_label.set_halign(Gtk.Align.START)
            cmd_label.set_wrap(True)
            cmd_label.set_xalign(0)
            if critical_lines_content: critical_lines_content.append(cmd_label)
        if context.stderr:
            stderr_label = Gtk.Label(label=f"Stderr: {context.stderr.strip()}")
            stderr_label.add_css_class("monospace")
            stderr_label.add_css_class("error-color")
            stderr_label.add_css_class("small-text")
            stderr_label.set_halign(Gtk.Align.START)
            stderr_label.set_wrap(True)
            stderr_label.set_xalign(0)
            if critical_lines_content: critical_lines_content.append(stderr_label)


        # Preencher "Additional Context"
        if context.file_path:
            ctx_label_path = Gtk.Label(label=f"- File Path: {context.file_path}")
            ctx_label_path.set_halign(Gtk.Align.START)
            ctx_label_path.set_wrap(True)
            ctx_label_path.set_xalign(0)
            if context_list: context_list.append(ctx_label_path)
        if context.working_directory:
            ctx_label_cwd = Gtk.Label(label=f"- Working Directory: {context.working_directory}")
            ctx_label_cwd.set_halign(Gtk.Align.START)
            ctx_label_cwd.set_wrap(True)
            ctx_label_cwd.set_xalign(0)
            if context_list: context_list.append(ctx_label_cwd)
        if context.traceback:
            ctx_label_tb = Gtk.Label(label="- Internal Traceback available in full log.")
            ctx_label_tb.set_halign(Gtk.Align.START)
            ctx_label_tb.set_wrap(True)
            ctx_label_tb.set_xalign(0)
            if context_list: context_list.append(ctx_label_tb)
        for detail in context.additional_context:
            det_label = Gtk.Label(label=f"- {detail.message}")
            det_label.set_halign(Gtk.Align.START)
            det_label.set_wrap(True)
            det_label.set_xalign(0)
            if detail.level == "warning": det_label.add_css_class("warning-color")
            elif detail.level == "error": det_label.add_css_class("error-color")
            if context_list: context_list.append(det_label)


        # Adicionar botões de ação sugeridas
        for action in context.suggested_actions:
            button = Gtk.Button()
            button.add_css_class("flat")
            button.add_css_class("pill")

            if action == SuggestedAction.RETRY:
                button.set_label(_("Retry"))
                button.add_css_class("suggested-action")
                # button.connect("clicked", lambda b: self._on_retry_action(context, dialog))
            elif action == SuggestedAction.CHECK_LOG:
                button.set_label(_("View Log"))
                button.add_css_class("warning-color")
                # button.connect("clicked", lambda b: self._on_view_log_action(context, dialog))
            elif action == SuggestedAction.CONSULT_DOCS:
                button.set_label(_("Consult Docs"))
                # button.connect("clicked", lambda b: self._on_consult_docs_action(context, dialog))
            elif action == SuggestedAction.REPORT_AUR:
                button.set_label(_("Report to AUR"))
                # button.connect("clicked", lambda b: self._on_report_aur_action(context, dialog))
            elif action == SuggestedAction.OPEN_PKGBUILD:
                button.set_label(_("Open PKGBUILD"))
                # button.connect("clicked", lambda b: self._on_open_pkgbuild_action(context, dialog))
            elif action == SuggestedAction.ADJUST_SETTINGS:
                button.set_label(_("Adjust Settings"))
                # button.connect("clicked", lambda b: self._on_adjust_settings_action(context, dialog))
            elif action == SuggestedAction.INSTALL_DEPENDENCY:
                button.set_label(_("Install Dependency"))
                button.add_css_class("suggested-action")
                # button.connect("clicked", lambda b: self._on_install_dependency_action(context, dialog))
            elif action == SuggestedAction.CLOSE_APP:
                button.set_label(_("Close Application"))
                button.add_css_class("destructive-action")
                # button.connect("clicked", lambda b: self._on_close_app_action(context, dialog))

            if actions_buttons_box: actions_buttons_box.append(button)

        # Conectar botões de controle
        if close_button: close_button.connect("clicked", lambda b: dialog.close())
        if copy_log_button: copy_log_button.connect("clicked", lambda b: self._on_copy_log_action(context))

        dialog.present()

    def _show_fallback_dialog(self, context: ErrorContext):
        """Exibe um diálogo simples caso o template principal não possa ser carregado."""
        Adw.MessageDialog(
            transient_for=self.parent_window,
            heading=f"Critical Error: {context.category.value}",
            body=f"{context.summary}\n\nDetails: {context.details}\n\nCheck logs for more information.",
            extra_button_label=_("Close")
        ).present()

    def _on_copy_log_action(self, context: ErrorContext):
        """Copia o log completo e o contexto do erro para a área de transferência."""
        log_content = self._format_full_log(context)
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set_text(log_content)
        logger.info("Error log copied to clipboard.")

        # Opcional: Mostrar um toast de confirmação
        toast_overlay = Adw.ToastOverlay.get_for_window(self.parent_window)
        if toast_overlay:
            toast = Adw.Toast.new(_("Error log copied to clipboard!"))
            toast.set_timeout(2)
            toast_overlay.add_toast(toast)


    def _format_full_log(self, context: ErrorContext) -> str:
        """Formata todos os detalhes do contexto do erro em uma string."""
        log_parts: List[str] = [
            f"--- Paru GUI Error Report ({context.timestamp.isoformat()}) ---",
            f"Application Version: {self.app_version}",
            f"Error Category: {context.category.value}",
            f"Summary: {context.summary}",
            f"Details: {context.details}",
        ]

        if context.pkgname: log_parts.append(f"Related Package: {context.pkgname}")
        if context.pkgver: log_parts.append(f"Package Version: {context.pkgver}")
        if context.file_path: log_parts.append(f"File Path: {context.file_path}")
        if context.working_directory: log_parts.append(f"Working Directory: {context.working_directory}")
        if context.command_executed: log_parts.append(f"Command Executed: {context.command_executed}")

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

    # TODO: Implementar callbacks para ações sugeridas (ex: _on_retry_action)
    # Estes callbacks precisarão interagir com a lógica principal da janela.
    # Por exemplo, _on_retry_action pode chamar um método na ParuGuiWindow para re-executar o comando.
    # Isso implica que a ParuGuiWindow precisaria expor métodos para essas ações, ou o ErrorHandler
    # precisaria de uma referência mais direta ao controller da aplicação.
