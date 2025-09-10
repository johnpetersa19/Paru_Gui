from gi.repository import Gio, Gtk, Adw
import gettext
_ = gettext.gettext

class PreferencesManager:
    """Gerencia as preferências do usuário de forma centralizada"""

    def __init__(self, window):
        """
        Inicializa o gerenciador de preferências.

        :param window: Janela principal da aplicação (PainelParuWindow)
        """
        self.window = window
        self.settings = Gio.Settings.new("org.gnome.painel_paru")
        self.preferences_window = None  # Janela de preferências atual

    def show(self, parent_window=None):
        """
        Mostra a janela de preferências.

        :param parent_window: Janela pai para modal (opcional, usa self.window se não fornecido)
        """
        if self.preferences_window and self.preferences_window.is_visible():
            self.preferences_window.present()
            return

        # Usa a janela principal como pai se nenhum for especificado
        parent = parent_window or self.window

        self.preferences_window = Adw.PreferencesWindow(
            transient_for=parent,
            modal=True,
            title=_("Preferências"),
            hide_on_close=True
        )

        # Cria todas as páginas de preferências
        self._create_main_page()
        self._create_debug_page()
        self._create_review_page()
        self._create_devel_page()

        # Conecta o callback de fechamento
        self.preferences_window.connect("close-request", self._on_close)
        self.preferences_window.present()

    def _on_close(self, *args, **kwargs):
        """Callback quando a janela de preferências é fechada

        Este método foi atualizado para usar *args, **kwargs para garantir consistência
        com os outros handlers do sistema, permitindo que seja chamado com diferentes
        assinaturas dependendo do contexto.

        Args:
            *args: Argumentos posicionais variáveis
            **kwargs: Argumentos nomeados variáveis

        Returns:
            bool: False para permitir que o fechamento prossiga
        """
        self.preferences_window = None
        return False

    def _create_main_page(self):
        """Cria a página principal de preferências (Geral)"""
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

        def on_editor_changed(entry):
            self.settings.set_string("editor", entry.get_text())

        editor.connect("changed", on_editor_changed)
        editor_row.add_suffix(editor)

        # Diretório de build
        build_dir_row = Adw.ActionRow(
            title=_("Diretório de Build"),
            subtitle=_("Localização padrão para builds")
        )
        group.add(build_dir_row)

        build_dir = Gtk.Entry()
        build_dir.set_text(self.settings.get_string("build-dir"))
        build_dir.set_placeholder_text(_("Ex: ~/paru-build"))

        def on_build_dir_changed(entry):
            self.settings.set_string("build-dir", entry.get_text())

        build_dir.connect("changed", on_build_dir_changed)
        build_dir_box = Gtk.Box(halign=Gtk.Align.END, spacing=10)
        build_dir_box.append(build_dir)
        build_dir_row.add_suffix(build_dir_box)

        # Instalar após build
        install_row = Adw.ActionRow(
            title=_("Instalar após build"),
            subtitle=_("Instala automaticamente após o build ser concluído")
        )
        group.add(install_row)

        install_switch = Gtk.Switch()
        install_switch.set_active(self.settings.get_boolean("install-after-build"))
        install_switch.connect("notify::active", lambda s, p:
                              self.settings.set_boolean("install-after-build", s.get_active()))
        install_row.add_suffix(install_switch)

        self.preferences_window.add(page)

    def _create_debug_page(self):
        """Cria a página de preferências de depuração"""
        page = Adw.PreferencesPage(title=_("Depuração"), icon_name="system-run-symbolic")

        # Grupo de logs
        group = Adw.PreferencesGroup(title=_("Logs"))
        page.add(group)

        # Nível de log
        log_level_row = Adw.ComboRow(title=_("Nível de log"),
                                    subtitle=_("Define a verbosidade dos logs"))
        model = Gtk.StringList()
        levels = [
            _("Erro"),     # 0 - Erros críticos
            _("Aviso"),    # 1 - Avisos
            _("Info"),     # 2 - Informações
            _("Detalhado") # 3 - Detalhes completos
        ]

        for level in levels:
            model.append(level)

        log_level_row.set_model(model)
        current_level = self.settings.get_int("log-level")
        log_level_row.set_selected(current_level)

        def on_log_level_selected(row):
            self.settings.set_int("log-level", row.get_selected())

        log_level_row.connect("notify::selected", on_log_level_selected)
        group.add(log_level_row)

        # Modo detalhado
        debug_group = Adw.PreferencesGroup(title=_("Modo Detalhado"))
        page.add(debug_group)

        verbose_switch = Gtk.Switch()
        verbose_switch.set_active(self.settings.get_boolean("verbose-build"))
        verbose_switch.connect("notify::active", lambda s, p:
                              self.settings.set_boolean("verbose-build", s.get_active()))

        verbose_row = Adw.ActionRow(
            title=_("Exibir detalhes"),
            subtitle=_("Exibe avisos técnicos durante builds (útil para relatar bugs)")
        )
        verbose_row.add_suffix(verbose_switch)
        debug_group.add(verbose_row)

        self.preferences_window.add(page)

    def _create_review_page(self):
        """Cria a página de preferências de revisão do PKGBUILD"""
        page = Adw.PreferencesPage(title=_("Revisão PKGBUILD"), icon_name="document-edit-symbolic")

        # Grupo de revisão PKGBUILD
        review_group = Adw.PreferencesGroup(title=_("Revisão PKGBUILD"))
        page.add(review_group)

        # Revisar PKGBUILD
        review_switch = Gtk.Switch()
        review_switch.set_active(self.settings.get_boolean("review-pkgbuild"))
        review_switch.connect("notify::active", lambda s, p:
                             self.settings.set_boolean("review-pkgbuild", s.get_active()))

        review_row = Adw.ActionRow(
            title=_("Revisar PKGBUILD"),
            subtitle=_("Permite visualizar alterações antes de compilar")
        )
        review_row.add_suffix(review_switch)
        review_group.add(review_row)

        # Limpar após build
        clean_switch = Gtk.Switch()
        clean_switch.set_active(self.settings.get_boolean("clean-after-build"))
        clean_switch.connect("notify::active", lambda s, p:
                            self.settings.set_boolean("clean-after-build", s.get_active()))

        clean_row = Adw.ActionRow(
            title=_("Limpar após build"),
            subtitle=_("Remove arquivos temporários após compilação")
        )
        clean_row.add_suffix(clean_switch)
        review_group.add(clean_row)

        # Opção para desativar revisão
        skip_review_switch = Gtk.Switch()
        skip_review_switch.set_active(self.settings.get_boolean("skip-review"))

        def on_skip_review_toggled(switch, *args):
            """Callback para quando o switch skip-review é alterado"""
            self.settings.set_boolean("skip-review", switch.get_active())
            # Se ativar skip-review, desativa revisão
            if switch.get_active():
                self.settings.set_boolean("review-pkgbuild", False)

        skip_review_switch.connect("notify::active", on_skip_review_toggled)

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

        self.preferences_window.add(page)

    def _create_devel_page(self):
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
            subtitle=_("Recarrega automaticamente a interface após mudanças nos arquivos UI")
        )
        reload_row.add_suffix(reload_switch)
        group.add(reload_row)

        # Grupo de pacotes ignorados
        ignore_group = Adw.PreferencesGroup(
            title=_("Ignorar Pacotes Específicos"),
            description=_("Pacotes devel que NÃO serão atualizados")
        )
        page.add(ignore_group)

        # Lista de pacotes ignorados
        ignored_list = Gtk.ListBox()
        ignored_list.set_selection_mode(Gtk.SelectionMode.NONE)
        ignored_list.set_css_classes(["boxed-list"])

        # Carrega pacotes ignorados das configurações
        ignored_packages = self.settings.get_strv("ignored-packages")
        for pkg in ignored_packages:
            row = Adw.ActionRow(title=pkg)

            remove_button = Gtk.Button(
                icon_name="window-close",
                valign=Gtk.Align.CENTER
            )

            def on_remove_package(btn, package=pkg, list_box=ignored_list):
                # Remove o pacote da lista de ignorados
                ignored = self.settings.get_strv("ignored-packages")
                if package in ignored:
                    ignored.remove(package)
                    self.settings.set_strv("ignored-packages", ignored)

                # Remove da interface
                for child in list(list_box):
                    if isinstance(child, Adw.ActionRow) and child.get_title() == package:
                        list_box.remove(child)
                        break

            remove_button.connect("clicked", on_remove_package)
            row.add_suffix(remove_button)
            ignored_list.append(row)

        # Campo para adicionar novos pacotes
        add_box = Gtk.Box(spacing=5)
        add_entry = Gtk.Entry(placeholder_text=_("Nome do pacote"))
        add_button = Gtk.Button(
            label=_("Adicionar"),
            halign=Gtk.Align.END
        )

        def _add_ignored_package(entry, list_box):
            package = entry.get_text().strip()
            if not package:
                return

            # Adiciona às configurações
            ignored = self.settings.get_strv("ignored-packages")
            if package not in ignored:
                ignored.append(package)
                self.settings.set_strv("ignored-packages", ignored)

                # Adiciona à interface
                row = Adw.ActionRow(title=package)

                remove_button = Gtk.Button(
                    icon_name="window-close",
                    valign=Gtk.Align.CENTER
                )

                def on_remove(btn):
                    # Remove o pacote da lista de ignorados
                    ignored_list = self.settings.get_strv("ignored-packages")
                    if package in ignored_list:
                        ignored_list.remove(package)
                        self.settings.set_strv("ignored-packages", ignored_list)

                    # Remove da interface
                    list_box.remove(row)

                remove_button.connect("clicked", on_remove)
                row.add_suffix(remove_button)
                list_box.append(row)

                # Limpa o campo
                entry.set_text("")

        add_button.connect("clicked", lambda b: _add_ignored_package(add_entry, ignored_list))
        add_entry.connect("activate", lambda e: _add_ignored_package(e, ignored_list))

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
            title=_("Configuração para desenvolvedores"),
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

        self.preferences_window.add(page)
