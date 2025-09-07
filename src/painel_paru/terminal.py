from gi.repository import Gtk, Gdk, GLib, Pango

class TerminalView(Gtk.TextView):
    """Terminal integrado com syntax highlighting"""
    
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
    
    def append(self, text: str, status: str = "normal"):
        """Adiciona texto ao terminal com formatação"""
        buffer = self.get_buffer()
        end_iter = buffer.get_end_iter()
        
        # Aplica tag conforme status
        if status == "success":
            buffer.insert_with_tags_by_name(end_iter, text, "success")
        elif status == "error":
            buffer.insert_with_tags_by_name(end_iter, text, "error")
        else:
            buffer.insert(end_iter, text)
        
        # Rola para o final
        self.scroll_to_iter(end_iter, 0, False, 0, 0)
    
    def clear(self):
        """Limpa o terminal"""
        self.get_buffer().set_text("")
