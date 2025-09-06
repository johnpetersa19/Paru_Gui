from gi.repository import Gio, Gtk, Adw
import os

class PreferencesManager:
    """Gerencia as preferências do usuário"""
    
    def __init__(self, application):
        self.app = application
        self.settings = Gio.Settings.new("org.gnome.painel_paru")
        self.window = None
    
    def show_preferences(self, parent_window):
        """Mostra a janela de preferências"""
        if self.window and self.window.is_visible():
            self.window.present()
            return
            
        self.window = Adw.PreferencesWindow(
            transient_for=parent_window,
            modal=True,
            title="Preferências",
            hide_on_close=True
        )
        
        # Cria as páginas de preferências
        self._create_main_preferences_page()
        self._create_debug_preferences_page()
        self._create_devel_preferences_page()
        
        self.window.connect("close-request", self._on_close)
        self.window.present()
    
    def _on_close(self, *args):
        """Callback quando a janela de preferências é fechada"""
        self.window = None
        return False
    
    def _create_main_preferences_page(self):
        """Cria a página principal de preferências"""
        page = Adw.PreferencesPage(title="Geral", icon_name="preferences-system-symbolic")
        
        # Grupo de edição
        group = Adw.PreferencesGroup(title="Editor")
        page.add(group)
        
        # Editor padrão
        editor_row = Adw.ActionRow(title="Editor de texto")
        group.add(editor_row)
        
        editor = Gtk.Entry()
        editor.set_text(self.settings.get_string("editor"))
        editor.set_placeholder_text("gedit, code, etc.")
        editor.connect("changed", lambda e: 
            self.settings.set_string("editor", e.get_text()))
        
        editor_box = Gtk.Box(halign=Gtk.Align.END, spacing=10)
        editor_box.append(editor)
        
        editor_row.add_suffix(editor_box)
        
        # Grupo de build
        build_group = Adw.PreferencesGroup(title="Build")
        page.add(build_group)
        
        # Opção de instalação automática
        install_switch = Gtk.Switch()
        install_switch.set_active(self.settings.get_boolean("auto-install"))
        install_switch.connect("notify::active", lambda s, p: 
            self.settings.set_boolean("auto-install", s.get_active()))
        
        install_row = Adw.ActionRow(
            title="Instalar após build",
            subtitle="Instala automaticamente após o build ser concluído"
        )
        install_row.add_suffix(install_switch)
        build_group.add(install_row)
        
        self.window.add(page)
    
    def _create_debug_preferences_page(self):
        """Cria a página de preferências de depuração"""
        page = Adw.PreferencesPage(title="Depuração", icon_name="system-run-symbolic")
        
        # Grupo de logs
        group = Adw.PreferencesGroup(title="Logs")
        page.add(group)
        
        # Nível de log
        log_level_row = Adw.ComboRow(
            title="Nível de log",
            subtitle="Define a verbosidade dos logs"
        )
        
        model = Gtk.StringList()
        for level in ["Erro", "Aviso", "Informação", "Detalhado"]:
            model.append(level)
        
        log_level_row.set_model(model)
        current_level = self.settings.get_int("log-level")
        log_level_row.set_selected(current_level)
        
        log_level_row.connect("notify::selected", lambda r, p: 
            self.settings.set_int("log-level", r.get_selected()))
        
        group.add(log_level_row)
        
        # Limpar cache
        clear_cache_row = Adw.ActionRow(
            title="Limpar cache",
            subtitle="Remove arquivos temporários e cache do AUR"
        )
        
        clear_button = Gtk.Button(label="Limpar")
        clear_button.add_css_class("destructive-action")
        clear_button.connect("clicked", self._clear_cache)
        
        clear_cache_row.add_suffix(clear_button)
        group.add(clear_cache_row)
        
        self.window.add(page)
    
    def _create_devel_preferences_page(self):
        """Cria a página de preferências para desenvolvedores"""
        page = Adw.PreferencesPage(title="Desenvolvedor", icon_name="applications-engineering-symbolic")
        
        # Grupo de recarga automática
        group = Adw.PreferencesGroup(title="Modo de desenvolvimento")
        page.add(group)
        
        # Recarga automática de UI
        reload_switch = Gtk.Switch()
        reload_switch.set_active(self.settings.get_boolean("dev-reload-ui"))
        reload_switch.connect("notify::active", lambda s, p: 
            self.settings.set_boolean("dev-reload-ui", s.get_active()))
        
        reload_row = Adw.ActionRow(
            title="Recarga automática de UI",
            subtitle="Recarrega recursos da interface ao pressionar Ctrl+R"
        )
        reload_row.add_suffix(reload_switch)
        group.add(reload_row)
        
        # Diretório de build
        build_dir_row = Adw.ActionRow(title="Diretório de build")
        group.add(build_dir_row)
        
        build_dir = Gtk.Entry()
        build_dir.set_text(self.settings.get_string("build-dir") or "build")
        build_dir.connect("changed", lambda e: 
            self.settings.set_string("build-dir", e.get_text()))
        
        build_dir_box = Gtk.Box(halign=Gtk.Align.END, spacing=10)
        build_dir_box.append(build_dir)
        
        build_dir_row.add_suffix(build_dir_box)
        
        self.window.add(page)
    
    def _clear_cache(self, button):
        """Limpa o cache do AUR"""
        try:
            # Remove cache do paru
            cache_dir = os.path.expanduser("~/.cache/paru/clone")
            if os.path.exists(cache_dir):
                import shutil
                shutil.rmtree(cache_dir)
                os.makedirs(cache_dir)
            
            # Mostra confirmação
            dialog = Adw.MessageDialog(
                transient_for=self.window,
                heading="Cache limpo",
                body="O cache do AUR foi limpo com sucesso."
            )
            dialog.add_response("ok", "OK")
            dialog.set_default_response("ok")
            dialog.present()
        except Exception as e:
            dialog = Adw.MessageDialog(
                transient_for=self.window,
                heading="Erro ao limpar cache",
                body=f"Ocorreu um erro: {str(e)}"
            )
            dialog.add_response("ok", "OK")
            dialog.set_default_response("ok")
            dialog.present()
