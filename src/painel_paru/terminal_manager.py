from gi.repository import Gtk, Gdk, GLib, Pango
import gettext
_ = gettext.gettext

class TerminalManager:
    def __init__(self, window):
        self.window = window
        self.terminal = None
        self.progress_bar = None
        self.tag_table = None

    def create_terminal(self):
        """Cria e configura o terminal integrado"""
        # Cria o TextView para o terminal
        terminal = Gtk.TextView(
            editable=False,
            monospace=True,
            wrap_mode=Gtk.WrapMode.WORD,
            cursor_visible=False,
            left_margin=10,
            right_margin=10,
            top_margin=5,
            bottom_margin=5
        )

        # Configura o buffer com tags para formatação
        buffer = terminal.get_buffer()
        self.tag_table = buffer.get_tag_table()

        # Tag para erros
        error_tag = Gtk.TextTag(name="error")
        error_tag.props.foreground = "#FF5252"  # Vermelho
        error_tag.props.weight = Pango.Weight.BOLD
        self.tag_table.add(error_tag)

        # Tag para progresso
        progress_tag = Gtk.TextTag(name="progress")
        progress_tag.props.foreground = "#FFD700"  # Amarelo dourado
        progress_tag.props.weight = Pango.Weight.BOLD
        self.tag_table.add(progress_tag)

        # Tag para informações
        info_tag = Gtk.TextTag(name="info")
        info_tag.props.foreground = "#2196F3"  # Azul
        self.tag_table.add(info_tag)

        # Tag para sucesso
        success_tag = Gtk.TextTag(name="success")
        success_tag.props.foreground = "#4CAF50"  # Verde
        success_tag.props.weight = Pango.Weight.BOLD
        self.tag_table.add(success_tag)

        # Tag para normal
        normal_tag = Gtk.TextTag(name="normal")
        normal_tag.props.foreground = "#FFFFFF"  # Branco
        self.tag_table.add(normal_tag)

        # Adiciona uma barra de progresso
        progress_bar = Gtk.ProgressBar(
            valign=Gtk.Align.CENTER,
            margin_top=10,
            margin_bottom=10
        )
        progress_bar.set_visible(False)
        progress_bar.set_fraction(0.0)

        # Cria um box para conter o terminal e a barra de progresso
        terminal_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        terminal_box.append(terminal)
        terminal_box.append(progress_bar)

        # Armazena referências internas para uso posterior
        self.terminal = terminal
        self.progress_bar = progress_bar

        # Retorna os componentes necessários SEM configurar referências no window
        return {
            'terminal': terminal,
            'progress_bar': progress_bar,
            'terminal_box': terminal_box
        }

    def append(self, text, status="normal"):
        """Adiciona texto ao terminal com formatação"""
        if not self.terminal:
            return

        buffer = self.terminal.get_buffer()
        end_iter = buffer.get_end_iter()

        # Aplica a tag apropriada
        tag = self.tag_table.lookup(status)
        if tag:
            buffer.insert_with_tags(end_iter, text + "\n", tag)
        else:
            buffer.insert(end_iter, text + "\n")

        # Rola para o final
        GLib.idle_add(self._scroll_to_end)

    def show_error(self, message):
        """Exibe mensagem de erro com formatação"""
        self.append(f"❌ {message}", "error")

    def show_info(self, message):
        """Exibe mensagem informativa com formatação"""
        self.append(f"ℹ️ {message}", "info")

    def show_success(self, message):
        """Exibe mensagem de sucesso com formatação"""
        self.append(f"✅ {message}", "success")

    def show_warning(self, message):
        """Exibe mensagem de aviso com formatação"""
        self.append(f"⚠️ {message}", "warning")

    def show_progress(self, message):
        """Exibe mensagem de progresso com formatação"""
        self.append(f"🔄 {message}", "progress")

    def clear(self):
        """Limpa o conteúdo do terminal"""
        if not self.terminal:
            return

        buffer = self.terminal.get_buffer()
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        buffer.delete(start_iter, end_iter)

    def update_progress(self, show, fraction=0.0):
        """Mostra ou esconde a barra de progresso"""
        if not self.progress_bar:
            return

        self.progress_bar.set_visible(show)
        if show:
            self.progress_bar.set_fraction(fraction)

    def start_operation(self):
        """Inicia uma operação e atualiza a UI"""
        self.update_progress(True, 0.1)
        self.window.cancel_button.set_visible(True)
        self.window.menu_manager.update_menu_state(True)
        self.window.back_button.set_sensitive(False)
        self.window.open_folder_button.set_sensitive(False)

    def end_operation(self):
        """Finaliza uma operação e atualiza a UI"""
        self.update_progress(False)
        self.window.cancel_button.set_visible(False)
        self.window.menu_manager.update_menu_state(False)
        # Corrigido: Usa o navigation_manager para verificar o histórico
        self.window.back_button.set_sensitive(bool(self.window.navigation_manager.previous_paths))
        self.window.open_folder_button.set_sensitive(bool(self.window.content_path))

    def _scroll_to_end(self):
        """Rola o terminal para o final"""
        if not self.terminal:
            return False

        buffer = self.terminal.get_buffer()
        end_iter = buffer.get_end_iter()
        self.terminal.scroll_to_iter(end_iter, 0.0, False, 0.0, 0.0)
        return False

    def on_copy_log(self):
        """Copia o conteúdo do terminal para a área de transferência"""
        if not self.terminal:
            return

        buffer = self.terminal.get_buffer()
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        log_content = buffer.get_text(start_iter, end_iter, False)

        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(log_content)
        self.show_info(_("Log copiado para a área de transferência"))

    def on_cancel_operation(self, button=None):
        """Cancela a operação em andamento"""
        if hasattr(self.window, 'current_process') and self.window.current_process:
            self.window.current_process.terminate()
            self.show_info(_("Operação cancelada"))
            self.window.current_process = None
            # Atualiza o estado do botão de cancelar
            self.window.cancel_button.set_visible(False)
            self.end_operation()
