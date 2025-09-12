# window_ui.py
from gi.repository import Gtk, Gio, Adw
import os
import subprocess
import gettext
from .terminal import TerminalView
from .content_detector import ContentDetector

_ = gettext.gettext

class WindowUI:
    """Gerencia a construção e manipulação da interface do usuário"""

    def setup_main_ui(self):
        """Configura a interface principal da aplicação"""
        # Criação do layout principal
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Barra de ferramentas superior
        self.setup_toolbar(main_box)

        # Status bar inferior
        self.setup_status_bar(main_box)

        # Área de conteúdo principal
        self.setup_content_area(main_box)

        # Configura ações da janela
        self.setup_window_actions()

        # Configurações iniciais
        self.status_label.set_label(_("Bem-vindo ao Paru GUI"))
        self.back_button.set_sensitive(False)
        self.open_folder_button.set_sensitive(False)

    def setup_toolbar(self, parent_box):
        """Configura a barra de ferramentas principal"""
        toolbar = Adw.ToolbarView()
        parent_box.append(toolbar)

        # Header bar
        header_bar = Adw.HeaderBar()
        toolbar.add_top_bar(header_bar)

        # Botão Voltar
        self.back_button = Gtk.Button.new_from_icon_name("go-previous-symbolic")
        self.back_button.set_tooltip_text(_("Voltar"))
        self.back_button.connect("clicked", self.on_back_button_clicked)
        header_bar.pack_start(self.back_button)

        # Botão Abrir Pasta
        self.open_folder_button = Gtk.Button.new_from_icon_name("folder-open-symbolic")
        self.open_folder_button.set_tooltip_text(_("Abrir pasta no gerenciador de arquivos"))
        self.open_folder_button.connect("clicked", self.on_open_folder)
        header_bar.pack_end(self.open_folder_button)

        # Botão Preferências
        preferences_button = Gtk.Button.new_from_icon_name("preferences-system-symbolic")
        preferences_button.set_tooltip_text(_("Preferências"))
        preferences_button.connect("clicked", self.on_show_preferences)
        header_bar.pack_end(preferences_button)

        # Botão Ajuda
        help_button = Gtk.Button.new_from_icon_name("help-about-symbolic")
        help_button.set_tooltip_text(_("Ajuda"))
        help_button.connect("clicked", self.on_show_help)
        header_bar.pack_end(help_button)

        # Botão Sobre
        about_button = Gtk.Button.new_from_icon_name("help-about-symbolic")
        about_button.set_tooltip_text(_("Sobre"))
        about_button.connect("clicked", self.on_show_about)
        header_bar.pack_end(about_button)

    def setup_status_bar(self, parent_box):
        """Configura a barra de status inferior"""
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        status_box.set_margin_start(10)
        status_box.set_margin_end(10)
        status_box.set_margin_top(5)
        status_box.set_margin_bottom(5)

        # Label de status
        self.status_label = Gtk.Label()
        self.status_label.set_hexpand(True)
        self.status_label.set_halign(Gtk.Align.START)
        status_box.append(self.status_label)

        # Terminal
        self.terminal = TerminalView()
        self.terminal.set_size_request(-1, 150)
        terminal_box = Gtk.ScrolledWindow()
        terminal_box.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        terminal_box.set_child(self.terminal)

        # Adiciona à interface
        parent_box.append(status_box)
        parent_box.append(terminal_box)

    def setup_content_area(self, parent_box):
        """Configura a área principal de conteúdo"""
        # Container principal para conteúdo
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.content_box.set_margin_start(10)
        self.content_box.set_margin_end(10)
        self.content_box.set_margin_top(10)
        self.content_box.set_margin_bottom(10)
        self.content_box.set_vexpand(True)

        # Tela inicial
        builder = Gtk.Builder.new_from_resource("/org/gnome/painel_paru/gtk/initial_screen.ui")
        initial_screen = builder.get_object("initial_screen")
        self.content_box.append(initial_screen)

        parent_box.append(self.content_box)

    def setup_window_actions(self):
        """Configura as ações da janela"""
        # Ação para mostrar sobre
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.on_show_about)
        self.add_action(about_action)

        # Ação para mostrar preferências
        preferences_action = Gio.SimpleAction.new("preferences", None)
        preferences_action.connect("activate", self.on_show_preferences)
        self.add_action(preferences_action)

        # Ação para mostrar ajuda
        help_action = Gio.SimpleAction.new("help", None)
        help_action.connect("activate", self.on_show_help)
        self.add_action(help_action)

        # Ação para atualizar sistema
        update_action = Gio.SimpleAction.new("update-system", None)
        update_action.connect("activate", self.on_update_system)
        self.add_action(update_action)

        # Ação para mostrar estatísticas
        stats_action = Gio.SimpleAction.new("show-stats", None)
        stats_action.connect("activate", self.on_show_stats)
        self.add_action(stats_action)

        # Ação para mostrar notícias do Arch
        news_action = Gio.SimpleAction.new("show-news", None)
        news_action.connect("activate", self.on_show_news)
        self.add_action(news_action)

        # Ação para limpar cache
        clear_cache_action = Gio.SimpleAction.new("clear-cache", None)
        clear_cache_action.connect("activate", self.on_clear_cache)
        self.add_action(clear_cache_action)

    def on_open_folder(self, button):
        """Abre a pasta atual no gerenciador de arquivos"""
        if hasattr(self, 'content_path') and self.content_path:
            try:
                # Tenta com xdg-open (funciona em muitos ambientes)
                subprocess.Popen(["xdg-open", self.content_path])
                self.terminal.append(_("📁 Pasta aberta no gerenciador de arquivos"), "info")
            except Exception as e:
                # Tenta com gio (para ambientes GNOME)
                try:
                    subprocess.Popen(["gio", "open", self.content_path])
                    self.terminal.append(_("📁 Pasta aberta no gerenciador de arquivos"), "info")
                except Exception as e:
                    self.terminal.append(_("❌ Erro ao abrir pasta: ") + str(e), "error")
                    print(f"❌ Erro ao abrir pasta: {e}")

    def on_copy_log(self, button):
        """Copia o conteúdo do terminal para a área de transferência"""
        buffer = self.terminal.get_buffer()
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        log_content = buffer.get_text(start_iter, end_iter, False)
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(log_content)
        self.terminal.append(_("📋 Log copiado para a área de transferência"), "info")

    def on_select_file(self, button):
        """Handler para seleção de arquivo único"""
        self._show_file_chooser(Gtk.FileChooserAction.OPEN)

    def on_select_folder(self, button):
        """Handler para seleção de pasta"""
        self._show_file_chooser(Gtk.FileChooserAction.SELECT_FOLDER)

    def _show_file_chooser(self, action):
        """Mostra diálogo de seleção de arquivo/pasta"""
        dialog = Gtk.FileChooserNative(
            title=_("Selecionar") + (" " + _("Arquivo") if action == Gtk.FileChooserAction.OPEN else " " + _("Pasta")),
            transient_for=self,
            action=action
        )
        dialog.connect("response", self.on_file_chooser_response)
        dialog.show()

    def on_file_chooser_response(self, dialog, response):
        """Processa resposta do diálogo de seleção"""
        if response == Gtk.ResponseType.ACCEPT:
            # Salva o caminho atual no histórico antes de mudar
            if hasattr(self, 'content_path') and self.content_path:
                self.previous_paths.append(self.content_path)
                self.back_button.set_sensitive(True)

            self.content_path = dialog.get_file().get_path()
            self.current_path = self.content_path
            self.status_label.set_label(_("Analisando: ") + self.content_path)

            state = ContentDetector.detect_content(self.content_path)
            self._load_content_screen(state)

            # Atualiza o estado dos botões
            self.open_folder_button.set_sensitive(True)

    def _load_content_screen(self, state):
        """Carrega a tela correspondente ao estado detectado"""
        self.current_state = state

        # Limpa o conteúdo atual
        while self.content_box.get_first_child():
            self.content_box.remove(self.content_box.get_first_child())

        # Mapeamento de estados para UIs e IDs corretos
        ui_config = {
            "pkgbuild": {
                "file": "gtk/content_detection/pkgbuild_card.ui",
                "widget_id": "PkgbuildCard"
            },
            "packages": {
                "file": "gtk/content_detection/packages_card.ui",
                "widget_id": "PackagesCard"
            },
            "patches": {
                "file": "gtk/content_detection/patches_card.ui",
                "widget_id": "PatchesCard"
            },
            "empty": {
                "file": "gtk/content_detection/empty_card.ui",
                "widget_id": "EmptyCard"
            }
        }

        # Usa configuração padrão se estado não for encontrado
        config = ui_config.get(state, ui_config["empty"])

        try:
            # Carrega o recurso
            resource_path = f"/org/gnome/painel_paru/{config['file']}"
            builder = Gtk.Builder.new_from_resource(resource_path)

            # Procura o widget principal
            widgets = builder.get_objects()
            main_widget = None
            for widget in widgets:
                if hasattr(widget, 'get_template_child'):  # Widget com template
                    main_widget = widget
                    break
                elif isinstance(widget, Gtk.Box):  # Container principal
                    main_widget = widget
                    break

            if not main_widget and widgets:
                main_widget = widgets[0]  # Fallback

            if main_widget:
                self.content_box.append(main_widget)

                # Configura os botões específicos do card
                if state == "pkgbuild":
                    self._setup_pkgbuild_card_buttons(main_widget)
                elif state == "packages":
                    self._setup_packages_card_buttons(main_widget)
                elif state == "patches":
                    self._setup_patches_card_buttons(main_widget)
                elif state == "empty":
                    self._setup_empty_card_buttons(main_widget)

        except Exception as e:
            self.terminal.append(_("❌ Erro ao carregar interface: ") + str(e), "error")
            # Carrega tela de erro
            self._load_error_screen(str(e))

    def _setup_pkgbuild_card_buttons(self, pkgbuild_card):
        """Configura os botões específicos do card PKGBUILD"""
        build_button = pkgbuild_card.get_template_child(type(pkgbuild_card), 'build_button')
        if build_button:
            build_button.connect("clicked", self.on_build)

        download_button = pkgbuild_card.get_template_child(type(pkgbuild_card), 'download_button')
        if download_button:
            download_button.connect("clicked", self.on_download_pkgbuild)

        edit_button = pkgbuild_card.get_template_child(type(pkgbuild_card), 'edit_button')
        if edit_button:
            edit_button.connect("clicked", self.on_edit_pkgbuild)

    def _setup_packages_card_buttons(self, packages_card):
        """Configura os botões específicos do card Pacotes"""
        install_button = packages_card.get_template_child(type(packages_card), 'install_button')
        if install_button:
            install_button.connect("clicked", self.on_install_packages)

        verify_button = packages_card.get_template_child(type(packages_card), 'verify_button')
        if verify_button:
            verify_button.connect("clicked", self.on_verify_signatures)

    def _setup_patches_card_buttons(self, patches_card):
        """Configura os botões específicos do card Patches"""
        apply_button = patches_card.get_template_child(type(patches_card), 'apply_button')
        if apply_button:
            apply_button.connect("clicked", self.on_apply_patches)

        refresh_button = patches_card.get_template_child(type(patches_card), 'refresh_button')
        if refresh_button:
            refresh_button.connect("clicked", self.on_refresh_patches)

    def _setup_empty_card_buttons(self, empty_card):
        """Configura os botões específicos do card Vazio"""
        # Configura busca AUR
        aur_search = empty_card.get_template_child(type(empty_card), 'aur_search')
        download_button = empty_card.get_template_child(type(empty_card), 'download_button')

        if aur_search and download_button:
            # Atualiza botão de download conforme digitação
            aur_search.connect("changed", lambda entry:
                download_button.set_sensitive(bool(entry.get_text().strip())))
            # Configura busca ao pressionar Enter
            aur_search.connect("activate", lambda _: download_button.emit("clicked"))
            # Configura botão de download
            download_button.connect("clicked", self.on_download_pkgbuild_from_search)

    def on_download_pkgbuild_from_search(self, button):
        """Baixa PKGBUILD do AUR com base na busca"""
        if hasattr(self, 'content_box'):
            for child in self.content_box:
                if hasattr(child, 'get_template_child'):
                    aur_search = child.get_template_child(type(child), 'aur_search')
                    if aur_search:
                        package_name = aur_search.get_text().strip()
                        if package_name:
                            self.terminal.append(_("📥 Buscando PKGBUILD para: ") + package_name, "progress")
                            # Aqui você chamaria o método do AUR
                            if hasattr(self, 'on_download_pkgbuild'):
                                self.on_download_pkgbuild(button, package_name)
                            break

    def _load_error_screen(self, error_message):
        """Carrega uma tela de erro genérica"""
        error_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        error_box.set_margin_start(20)
        error_box.set_margin_end(20)
        error_box.set_margin_top(20)
        error_box.set_margin_bottom(20)

        error_label = Gtk.Label()
        error_label.set_markup(f"<span foreground='red' size='large'>{_('Erro')}</span>")
        error_label.set_justify(Gtk.Justification.CENTER)
        error_box.append(error_label)

        message_label = Gtk.Label()
        message_label.set_markup(f"<span foreground='red'>{_('Detalhes:')}</span> {error_message}")
        message_label.set_line_wrap(True)
        message_label.set_justify(Gtk.Justification.CENTER)
        error_box.append(message_label)

        retry_button = Gtk.Button(label=_("Tentar novamente"))
        retry_button.add_css_class("suggested-action")
        retry_button.connect("clicked", lambda b: self._reload_current_content())
        error_box.append(retry_button)

        self.content_box.append(error_box)

    def _reload_current_content(self):
        """Recarrega o conteúdo atual"""
        if hasattr(self, 'content_path') and self.content_path:
            self.status_label.set_label(_("Recarregando: ") + self.content_path)
            state = ContentDetector.detect_content(self.content_path)
            self._load_content_screen(state)

    def on_back_button_clicked(self, button):
        """Volta para o diretório anterior no histórico"""
        if self.previous_paths:
            self.content_path = self.previous_paths.pop()
            self.current_path = self.content_path
            self.status_label.set_label(_("Voltando para: ") + self.content_path)

            state = ContentDetector.detect_content(self.content_path)
            self._load_content_screen(state)

            # Atualiza o estado do botão Voltar
            self.back_button.set_sensitive(bool(self.previous_paths))

    def on_show_help(self, action, parameter):
        """Mostra janela de ajuda"""
        help_dialog = Adw.Window(
            transient_for=self,
            modal=True,
            title=_("Ajuda do Paru GUI"),
            default_width=700,
            default_height=500
        )

        # Conteúdo da ajuda
        content = Adw.ToolbarView()
        help_dialog.set_content(content)

        # Header bar
        header = Adw.HeaderBar()
        content.add_top_bar(header)

        # Botão de fechar
        close_button = Gtk.Button(
            icon_name="window-close-symbolic",
            tooltip_text=_("Fechar")
        )
        close_button.connect("clicked", lambda b: help_dialog.close())
        header.pack_end(close_button)

        # Scrollable content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        # Conteúdo da ajuda
        help_content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=15,
            margin_start=20,
            margin_end=20,
            margin_top=20,
            margin_bottom=20
        )

        # Título
        title = Gtk.Label()
        title.set_markup(f"<span size='x-large' weight='bold'>{_('Ajuda do Paru GUI')}</span>")
        title.set_halign(Gtk.Align.START)
        help_content.append(title)

        # Seções de ajuda
        sections = [
            (_("Detecção de Conteúdo"), _(
                "O Paru GUI detecta automaticamente o conteúdo do diretório selecionado e exibe a interface apropriada:\n\n"
                "• PKGBUILD: Mostra opções para compilar e instalar o pacote\n"
                "• Pacotes (.pkg.tar.zst): Mostra opções para instalar e verificar assinaturas\n"
                "• Patches: Mostra opções para aplicar patches\n"
                "• Diretório Vazio: Permite buscar e baixar PKGBUILDs do AUR"
            )),
            (_("Compilação de Pacotes"), _(
                "Para compilar um pacote:\n\n"
                "1. Selecione um diretório contendo um PKGBUILD\n"
                "2. Clique em 'Compilar' para iniciar o processo\n"
                "3. Se configurado, você será solicitado a revisar o PKGBUILD\n"
                "4. O terminal exibirá o progresso da compilação"
            )),
            (_("Atualizações de Sistema"), _(
                "Para atualizar todo o sistema:\n\n"
                "1. Clique no menu Sistema > Atualizar Sistema\n"
                "2. Confirme a operação\n"
                "3. O terminal exibirá o progresso da atualização"
            ))
        ]

        for title, content_text in sections:
            section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

            section_title = Gtk.Label()
            section_title.set_markup(f"<span size='large' weight='bold'>{title}</span>")
            section_title.set_halign(Gtk.Align.START)
            section.append(section_title)

            section_content = Gtk.Label()
            section_content.set_markup(content_text)
            section_content.set_wrap(True)
            section_content.set_xalign(0)
            section_content.set_justify(Gtk.Justification.FILL)
            section.append(section_content)

            help_content.append(section)

        scrolled.set_child(help_content)
        content.set_content(scrolled)
        help_dialog.present()

    def on_show_stats(self, action, parameter):
        """Mostra estatísticas do sistema"""
        self.terminal.append(_("📊 Coletando estatísticas do sistema..."), "progress")

        # Coleta informações do sistema
        stats = []

        # Informações do sistema
        stats.append(_("=== Informações do Sistema ==="))
        try:
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if line.startswith('PRETTY_NAME='):
                        stats.append(line.split('=')[1].strip().strip('"'))
        except:
            pass

        # Espaço em disco
        stats.append(_("\n=== Espaço em Disco ==="))
        try:
            df_output = subprocess.check_output(['df', '-h'], text=True)
            stats.append(df_output)
        except:
            stats.append(_("Erro ao coletar informações de disco"))

        # Pacotes instalados
        stats.append(_("\n=== Pacotes Instalados ==="))
        try:
            num_packages = subprocess.check_output(['pacman', '-Qq', '|', 'wc', '-l'], shell=True, text=True)
            stats.append(_("Total de pacotes instalados: ") + num_packages.strip())
        except:
            stats.append(_("Erro ao coletar informações de pacotes"))

        # Mostra as estatísticas no terminal
        for stat in stats:
            self.terminal.append(stat, "info")

    def on_show_news(self, action, parameter):
        """Mostra notícias do Arch Linux"""
        self.terminal.append(_("📰 Buscando notícias do Arch Linux..."), "progress")

        # Usa o archnews para obter as notícias
        try:
            subprocess.Popen(["archnews"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.terminal.append(_("Aberto visualizador de notícias do Arch"), "success")
        except Exception as e:
            self.terminal.append(_("❌ Erro ao abrir notícias do Arch: ") + str(e), "error")
            print(f"❌ Erro ao abrir notícias do Arch: {e}")

    def on_clear_cache(self, action, parameter):
        """Limpa o cache do pacman/paru"""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Limpar Cache"),
            body=_("Deseja limpar o cache de pacotes? Isso removerá pacotes antigos e pode economizar espaço em disco.")
        )

        dialog.add_response("cancel", _("Cancelar"))
        dialog.add_response("clear", _("Limpar"))
        dialog.set_default_response("cancel")
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)

        def handle_response(dialog, response):
            if response == "clear":
                self.terminal.append(_("🧹 Limpando cache de pacotes..."), "progress")
                ParuRunner.run_command(["paru", "-Scc"], self.terminal.append)

        dialog.connect("response", handle_response)
        dialog.present()
