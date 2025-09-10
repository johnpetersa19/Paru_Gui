from gi.repository import Gtk, Gdk, GLib, Pango
import gettext
_ = gettext.gettext

class TerminalView(Gtk.TextView):
    """Terminal integrado com syntax highlighting e melhor feedback"""
    def __init__(self):
        super().__init__(
            editable=False,
            monospace=True,
            wrap_mode=Gtk.WrapMode.WORD,
            cursor_visible=False
        )
        # Configura tags de syntax highlighting
        self.tag_table = self.get_buffer().get_tag_table()

        # Tag para sucesso
        success_tag = Gtk.TextTag(name="success")
        success_tag.props.foreground = "#4CAF50"  # Verde
        success_tag.props.weight = Pango.Weight.BOLD
        self.tag_table.add(success_tag)

        # Tag para erros
        error_tag = Gtk.TextTag(name="error")
        error_tag.props.foreground = "#F44336"  # Vermelho
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

        # Adiciona uma barra de progresso
        self.progress_bar = Gtk.ProgressBar(
            valign=Gtk.Align.CENTER,
            margin_top=10,
            margin_bottom=10
        )
        self.progress_bar.set_visible(False)
        self.progress_bar.set_fraction(0.0)

    def append(self, text: str, status: str = "normal"):
        """Adiciona texto ao terminal com formatação"""
        buffer = self.get_buffer()
        end_iter = buffer.get_end_iter()

        # Adiciona nova linha se não terminar com ela
        if text and not text.endswith('\n'):
            text += '\n'

        # Aplica tag conforme status
        if status == "success":
            buffer.insert_with_tags_by_name(end_iter, text, "success")
        elif status == "error":
            buffer.insert_with_tags_by_name(end_iter, text, "error")
        elif status == "progress":
            buffer.insert_with_tags_by_name(end_iter, text, "progress")
            self.show_progress()
        elif status == "info":
            buffer.insert_with_tags_by_name(end_iter, text, "info")
        else:
            buffer.insert(end_iter, text)

        # Rola para o final
        self.scroll_to_iter(end_iter, 0, False, 0, 0)

    def show_progress(self, visible=True, fraction=None):
        """Mostra ou oculta a barra de progresso"""
        if hasattr(self, 'progress_bar'):
            self.progress_bar.set_visible(visible)
            if fraction is not None:
                self.progress_bar.set_fraction(fraction)
            # Adiciona a barra de progresso ao container (uma única vez)
            if visible and self.get_parent() and not self.progress_bar.get_parent():
                parent_box = self.get_parent()
                if isinstance(parent_box, Gtk.Box):
                    parent_box.append(self.progress_bar)

    def clear(self):
        """Limpa o terminal"""
        self.get_buffer().set_text("")
        self.show_progress(False)
