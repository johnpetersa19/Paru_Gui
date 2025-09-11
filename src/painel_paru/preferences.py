# preferences.py
from gi.repository import Gio, Gtk, Adw
import os
import gettext
_ = gettext.gettext

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
            title=_("Preferências"),
            hide_on_close=True
        )
        
        # Cria as páginas de preferências
        self._create_main_preferences_page()
        self._create_debug_preferences_page()
        self._create_review_preferences_page()
        self._create_devel_preferences_page()
        
        self.window.connect("close-request", self._on_close)
        self.window.present()
    
    def _on_close(self, *args):
        """Callback quando a janela de preferências é fechada"""
        self.window = None
        return False
    
    def _create_main_preferences_page(self):
        """Cria a página principal de preferências"""
        page = Adw.PreferencesPage(title=_("Geral"), icon_name="preferences-system-symbolic")
        # Grupo de edição
        group = Adw.PreferencesGroup(title=_("Editor"))
        page.add(group)
        
        # Editor padrão
        editor_row = Adw.ActionRow(title=_("Editor de texto"))
        group.add(editor_row)
        editor = Gtk.Entry()
        editor.set_text(self.settings.get_string("editor"))
        editor.set_placeholder_text(_("gedit, code, etc."))
        editor.connect("changed", lambda e: 
            self.settings.set_string("editor", e.get_text()))
        editor_box = Gtk.Box(halign=Gtk.Align.END, spacing=10)
        editor_box.append(editor)
        editor_row.add_suffix(editor_box)
        
        # Grupo de build
        build_group = Adw.PreferencesGroup(title=_("Build"))
        page.add(build_group)
        
        # Opção de instalação automática
        install_switch = Gtk.Switch()
        install_switch.set_active(self.settings.get_boolean("auto-install"))
        install_switch.connect("notify::active", lambda s, p: 
            self.settings.set_boolean("auto-install", s.get_active()))
        install_row = Adw.ActionRow(
            title=_("Instalar após build"),
            subtitle=_("Instala automaticamente após o build ser concluído")
        )
        install_row.add_suffix(install_switch)
        build_group.add(install_row)
        
        self.window.add(page)
    
    def _create_debug_preferences_page(self):
        """Cria a página de preferências de depuração"""
        page = Adw.PreferencesPage(title=_("Depuração"), icon_name="system-run-symbolic")
        # Grupo de logs
        group = Adw.PreferencesGroup(title=_("Logs"))
        page.add(group)
        
        # Nível de log
        log_level_row = Adw.ComboRow(
            title=_("Nível de log"),
            subtitle=_("Define a verbosidade dos logs")
        )
        model = Gtk.StringList()
        for level in [_("Erro"), _("Aviso"), _("Informação"), _("Detalhado")]:
            model.append(level)
        log_level_row.set_model(model)
        current_level = self.settings.get_int("log-level")
        log_level_row.set_selected(current_level)
        log_level_row.connect("notify::selected", lambda r, p: 
            self.settings.set_int("log-level", r.get_selected()))
        group.add(log_level_row)
        
        # Limpar cache
        clear_cache_row = Adw.ActionRow(
            title=_("Limpar cache"),
            subtitle=_("Remove arquivos temporários e cache do AUR")
        )
        clear_button = Gtk.Button(label=_("Limpar"))
        clear_button.add_css_class("destructive-action")
        clear_button.connect("clicked", self._clear_cache)
        clear_cache_row.add_suffix(clear_button)
        group.add(clear_cache_row)
        
        # Grupo de pacotes de depuração
        debug_group = Adw.PreferencesGroup(title=_("Pacotes de Depuração"))
        page.add(debug_group)

        # Instalar pacotes de depuração
        debug_switch = Gtk.Switch()
        debug_switch.set_active(self.settings.get_boolean("install-debug"))
        debug_switch.connect("notify::active", lambda s, p:
            self.settings.set_boolean("install-debug", s.get_active()))
        debug_row = Adw.ActionRow(
            title=_("Instalar pacotes de depuração"),
            subtitle=_("Instala automaticamente pacotes -debug para diagnóstico de crashes")
        )
        debug_row.add_suffix(debug_switch)
        debug_group.add(debug_row)

        # Mostrar warnings detalhados
        verbose_switch = Gtk.Switch()
        verbose_switch.set_active(self.settings.get_boolean("verbose-debug"))
        verbose_switch.connect("notify::active", lambda s, p:
            self.settings.set_boolean("verbose-debug", s.get_active()))
        verbose_row = Adw.ActionRow(
            title=_("Mostrar warnings detalhados"),
            subtitle=_("Exibe avisos técnicos durante builds (útil para relatar bugs)")
        )
        verbose_row.add_suffix(verbose_switch)
        debug_group.add(verbose_row)

        self.window.add(page)

    def _create_review_preferences_page(self):
        """Cria a página de preferências de revisão do PKGBUILD"""
        page = Adw.PreferencesPage(title=_("Revisão PKGBUILD"), icon_name="document-edit-symbolic")

        # Grupo de revisão PKGBUILD
        review_group = Adw.PreferencesGroup(title=_("Revisão PKGBUILD"))
        page.add(review_group)

        # Revisar PKGBUILD
        review_switch = Gtk.Switch()
        review_switch.set_active(self.settings.get_boolean("review-pkgbuild"))
        review_switch.connect("notify::active", lambda s, p: {
            self.settings.set_boolean("review-pkgbuild", s.get_active()),
            # Se desativar revisão, ativa skip-review
            self.settings.set_boolean("skip-review", not s.get_active()) if not s.get_active() else None
        })
        review_row = Adw.ActionRow(
            title=_("Revisar PKGBUILD"),
            subtitle=_("Mostra diff visual do PKGBUILD antes de compilar")
        )
        review_row.add_suffix(review_switch)
        review_group.add(review_row)

        # Limpar após build
        clean_switch = Gtk.Switch()
        clean_switch.set_active(self.settings.get_boolean("clean-after"))
        clean_switch.connect("notify::active", lambda s, p:
            self.settings.set_boolean("clean-after", s.get_active()))
        clean_row = Adw.ActionRow(
            title=_("Limpar após build"),
            subtitle=_("Remove arquivos temporários após compilação")
        )
        clean_row.add_suffix(clean_switch)
        review_group.add(clean_row)

        # Opção para desativar revisão
        skip_review_switch = Gtk.Switch()
        skip_review_switch.set_active(self.settings.get_boolean("skip-review"))
        skip_review_switch.connect("notify::active", lambda s, p: {
            self.settings.set_boolean("skip-review", s.get_active()),
            # Se ativar skip-review, desativa revisão
            self.settings.set_boolean("review-pkgbuild", not s.get_active()) if s.get_active() else None
        })
        skip_review_row = Adw.ActionRow(
            title=_("Ignorar revisão"),
            subtitle=_("Pula a revisão do PKGBUILD (paru --skipreview)")
        )
        skip_review_row.add_suffix(skip_review_switch)
        review_group.add(skip_review_row)

        # Informações adicionais
        info_group = Adw.PreferencesGroup(title=_("Informação"))
        page.add(info_group)

        info_row = Adw.ActionRow(
            title=_("Sobre a revisão do PKGBUILD"),
            activatable=False
        )
        info_label = Gtk.Label(
            label=_("A revisão do PKGBUILD permite que você visualize alterações antes de compilar. É recomendado para segurança, especialmente quando baixando de fontes não confiáveis."),
            wrap=True,
            xalign=0,
            margin_top=5,
            margin_bottom=5,
            margin_start=10,
            margin_end=10
        )
        info_row.add_suffix(info_label)
        info_group.add(info_row)

        self.window.add(page)
    
    def _create_devel_preferences_page(self):
        """Cria a página de preferências para desenvolvedores"""
        page = Adw.PreferencesPage(title=_("Desenvolvedor"), icon_name="applications-engineering-symbolic")
        # Grupo de recarga automática
        group = Adw.PreferencesGroup(title=_("Modo de desenvolvimento"))
        page.add(group)
        
        # Recarga automática de UI
        reload_switch = Gtk.Switch()
        reload_switch.set_active(self.settings.get_boolean("dev-reload-ui"))
        reload_switch.connect("notify::active", lambda s, p: 
            self.settings.set_boolean("dev-reload-ui", s.get_active()))
        reload_row = Adw.ActionRow(
            title=_("Recarga automática de UI"),
            subtitle=_("Recarrega recursos da interface ao pressionar Ctrl+R")
        )
        reload_row.add_suffix(reload_switch)
        group.add(reload_row)
        
        # Grupo de atualizações Devel
        devel_group = Adw.PreferencesGroup(title=_("Atualizações Devel"))
        page.add(devel_group)

        # Verificar atualizações para pacotes -git, -svn, etc.
        devel_switch = Gtk.Switch()
        devel_switch.set_active(self.settings.get_boolean("devel-mode"))
        devel_switch.connect("notify::active", lambda s, p:
            self.settings.set_boolean("devel-mode", s.get_active()))
        devel_row = Adw.ActionRow(
            title=_("Verificar atualizações para pacotes -git, -svn, etc."),
            subtitle=_("Atualiza pacotes em desenvolvimento automaticamente")
        )
        devel_row.add_suffix(devel_switch)
        devel_group.add(devel_row)

        # Diretório de build
        build_dir_row = Adw.ActionRow(title=_("Diretório de build"))
        group.add(build_dir_row)
        build_dir = Gtk.Entry()
        build_dir.set_text(self.settings.get_string("build-dir") or "build")
        build_dir.connect("changed", lambda e: 
            self.settings.set_string("build-dir", e.get_text()))
        build_dir_box = Gtk.Box(halign=Gtk.Align.END, spacing=10)
        build_dir_box.append(build_dir)
        build_dir_row.add_suffix(build_dir_box)
        
        # Grupo de pacotes ignorados
        ignore_group = Adw.PreferencesGroup(title=_("Ignorar Pacotes Específicos"))
        ignore_group.set_description(_("Pacotes devel que NÃO serão atualizados"))
        page.add(ignore_group)

        # Lista de pacotes ignorados
        ignored_list = Gtk.ListBox()
        ignored_list.set_selection_mode(Gtk.SelectionMode.NONE)
        ignored_list.set_css_classes(["boxed-list"])

        # Carrega pacotes ignorados das configurações
        ignored_packages = self.settings.get_strv("ignored-packages")
        for package in ignored_packages:
            row = Adw.ActionRow(title=package)
            remove_button = Gtk.Button(
                icon_name="user-trash-symbolic",
                css_classes=["flat"],
                tooltip_text=_("Remover")
            )
            remove_button.connect("clicked", lambda b, pkg=package:
                self._remove_ignored_package(pkg, ignored_list))
            row.add_suffix(remove_button)
            ignored_list.append(row)

        # Campo para adicionar novos
        add_box = Gtk.Box(spacing=10)
        add_entry = Gtk.Entry(placeholder_text=_("firefox-git"))
        add_button = Gtk.Button(
            label="+",
            css_classes=["suggested-action"],
            tooltip_text=_("Adicionar")
        )
        add_button.connect("clicked", lambda b:
            self._add_ignored_package(add_entry, ignored_list))
        add_entry.connect("activate", lambda e:
            self._add_ignored_package(e, ignored_list))

        add_box.append(add_entry)
        add_box.append(add_button)

        # Adiciona à interface
        ignore_group.add(ignored_list)

        add_row = Adw.ActionRow(title=_("Adicionar Pacote"))
        add_row.add_suffix(add_box)
        ignore_group.add(add_row)

        # Informações
        info_group = Adw.PreferencesGroup(title=_("Informação"))
        page.add(info_group)

        info_row = Adw.ActionRow(
            title=_("O que são pacotes devel?"),
            activatable=False
        )
        info_label = Gtk.Label(
            label=_("Pacotes devel (ex: -git, -svn) são versões em desenvolvimento que atualizam frequentemente. Úteis para testar recursos novos, mas podem conter bugs."),
            wrap=True,
            xalign=0,
            margin_top=5,
            margin_bottom=5,
            margin_start=10,
            margin_end=10
        )
        info_row.add_suffix(info_label)
        info_group.add(info_row)

        self.window.add(page)
    
    def _add_ignored_package(self, entry, list_box):
        """Adiciona um pacote à lista de ignorados"""
        package = entry.get_text().strip()
        if package and package not in self.settings.get_strv("ignored-packages"):
            # Adiciona à interface
            row = Adw.ActionRow(title=package)
            remove_button = Gtk.Button(
                icon_name="user-trash-symbolic",
                css_classes=["flat"],
                tooltip_text=_("Remover")
            )
            remove_button.connect("clicked", lambda b:
                self._remove_ignored_package(package, list_box))
            row.add_suffix(remove_button)
            list_box.append(row)

            # Atualiza configurações
            ignored_packages = self.settings.get_strv("ignored-packages")
            ignored_packages.append(package)
            self.settings.set_strv("ignored-packages", ignored_packages)

            # Limpa entrada
            entry.set_text("")

    def _remove_ignored_package(self, package, list_box):
        """Remove um pacote da lista de ignorados"""
        # Remove da interface
        row = list_box.get_first_child()
        while row:
            if isinstance(row, Adw.ActionRow) and row.get_title() == package:
                list_box.remove(row)
                break
            row = row.get_next_sibling()

        # Atualiza configurações
        ignored_packages = self.settings.get_strv("ignored-packages")
        if package in ignored_packages:
            ignored_packages.remove(package)
            self.settings.set_strv("ignored-packages", ignored_packages)

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
                heading=_("Cache limpo"),
                body=_("O cache do AUR foi limpo com sucesso.")
            )
            dialog.add_response("ok", _("OK"))
            dialog.set_default_response("ok")
            dialog.present()
        except Exception as e:
            dialog = Adw.MessageDialog(
                transient_for=self.window,
                heading=_("Erro ao limpar cache"),
                body=_("Ocorreu um erro: {}").format(str(e))
            )
            dialog.add_response("ok", _("OK"))
            dialog.set_default_response("ok")
            dialog.present()
