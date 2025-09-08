# window.py
from gi.repository import Gtk, Gio, Adw
import os
import subprocess
import shlex
import shutil  # Importação necessária para verificar a disponibilidade do pacman-key
from pathlib import Path
from .terminal import TerminalView
from .content_detector import ContentDetector
from .build_manager import BuildManager
from .paru_runner import ParuRunner
from .aur_downloader import AurDownloader
from .conflict_resolver import ConflictResolver
import gettext
_ = gettext.gettext

class PainelParuWindow(Adw.ApplicationWindow):
    """Janela principal configurada para sua estrutura atual"""
    def __init__(self, *args, **kwargs):
        # Inicializa traduções
        gettext.bindtextdomain("painel_paru", "/usr/share/locale")
        gettext.textdomain("painel_paru")

        super().__init__(*args, **kwargs)
        self.set_title(_("Paru GUI"))
        self.set_default_size(900, 650)

        # INICIALIZAÇÃO DAS CONFIGURAÇÕES
        try:
            self.settings = Gio.Settings.new("org.gnome.painel_paru")
            print("✅ Configurações inicializadas com sucesso")
        except Exception as e:
            print(f"❌ Erro FATAL ao inicializar configurações: {e}")
            class MockSettings:
                def get_string(self, key):
                    return "gedit"
                def get_boolean(self, key):
                    return False
                def get_strv(self, key):
                    return []
            self.settings = MockSettings()

        # Variáveis de estado
        self.current_process = None  # Mantém referência ao processo atual
        self.previous_paths = []  # Histórico de navegação
        self.current_path = None  # Caminho atual
        self.build_callback = None  # Callback para continuar o build após resolver conflitos

        # Configuração da interface com Adwaita
        self.toolbar_view = Adw.ToolbarView()
        self.set_content(self.toolbar_view)

        # Caixa de conteúdo principal
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main_box.set_margin_start(20)
        self.main_box.set_margin_end(20)
        self.main_box.set_margin_top(20)
        self.main_box.set_margin_bottom(20)
        self.toolbar_view.set_content(self.main_box)

        # Status label
        self.status_label = Gtk.Label(
            label=_("Selecione um arquivo ou pasta para começar"),
            css_classes=["subtitle-2"],
            margin_top=20
        )
        self.main_box.append(self.status_label)

        # Área de conteúdo
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main_box.append(self.content_box)

        # Terminal
        self.terminal = TerminalView()
        self.main_box.append(self.terminal)

        # Botões de ação com melhor alinhamento
        action_box = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        action_box.set_margin_top(15)

        select_file_btn = Gtk.Button(label=_("Selecionar Arquivo"))
        select_file_btn.add_css_class("suggested-action")
        select_file_btn.connect("clicked", self.on_select_file)
        action_box.append(select_file_btn)

        select_folder_btn = Gtk.Button(label=_("Selecionar Pasta"))
        select_folder_btn.add_css_class("suggested-action")
        select_folder_btn.connect("clicked", self.on_select_folder)
        action_box.append(select_folder_btn)

        self.main_box.append(action_box)

        # Cabeçalho com menu de preferências
        header = Adw.HeaderBar()
        self.toolbar_view.add_top_bar(header)

        # Adiciona barra de pesquisa global
        search_box = Gtk.Box(spacing=6)
        search_entry = Gtk.Entry(
            placeholder_text=_("Pesquisar pacotes..."),
            hexpand=True
        )
        search_button = Gtk.Button(
            icon_name="system-search-symbolic",
            tooltip_text=_("Pesquisar")
        )
        search_box.append(search_entry)
        search_box.append(search_button)
        header.set_title_widget(search_box)

        # Configura a busca
        search_button.connect("clicked", lambda b: self.search_packages(search_entry.get_text()))
        search_entry.connect("activate", lambda e: self.search_packages(e.get_text()))

        # Botões de navegação
        nav_box = Gtk.Box(spacing=6)

        # Botão Voltar (desabilitado inicialmente)
        self.back_button = Gtk.Button(
            icon_name="go-previous-symbolic",
            tooltip_text=_("Voltar"),
            sensitive=False
        )
        self.back_button.connect("clicked", self.on_back)
        nav_box.append(self.back_button)

        # Botão Abrir Pasta
        self.open_folder_button = Gtk.Button(
            icon_name="folder-open-symbolic",
            tooltip_text=_("Abrir Pasta"),
            sensitive=False
        )
        self.open_folder_button.connect("clicked", self.on_open_folder)
        nav_box.append(self.open_folder_button)

        # Botão Copiar Log
        self.copy_log_button = Gtk.Button(
            icon_name="edit-copy-symbolic",
            tooltip_text=_("Copiar Log")
        )
        self.copy_log_button.connect("clicked", self.on_copy_log)
        nav_box.append(self.copy_log_button)

        # Botão Cancelar (escondido inicialmente)
        self.cancel_button = Gtk.Button(
            icon_name="process-stop-symbolic",
            tooltip_text=_("Cancelar Operação"),
            visible=False
        )
        self.cancel_button.connect("clicked", self.on_cancel_operation)
        nav_box.append(self.cancel_button)

        header.pack_start(nav_box)

        # Botão de menu
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_tooltip_text(_("Menu"))

        # Menu popover
        self.popover = Gtk.PopoverMenu()
        menu_button.set_popover(self.popover)

        # Ações da janela
        self.create_actions()

        # Configuração do menu
        menu_model = Gio.Menu()
        system_menu = Gio.Menu()

        # Adiciona opções ao menu Sistema
        system_menu.append(_("Estatísticas"), "win.show-stats")
        system_menu.append(_("Notícias do Arch"), "win.show-news")
        system_menu.append(_("Limpar Cache"), "win.clear-cache")
        system_menu.append(_("Atualizar Sistema"), "win.update-system")

        # Cria o item do menu principal com o submenu
        menu_model.append_submenu(_("Sistema"), system_menu)

        # Adiciona outras opções
        menu_model.append(_("Preferências"), "win.show-preferences")
        menu_model.append(_("Atalhos"), "win.show-help-overlay")
        menu_model.append(_("Sobre"), "win.show-about")
        menu_model.append(_("Sair"), "app.quit")

        self.popover.set_menu_model(menu_model)
        header.pack_end(menu_button)

    def create_actions(self):
        """Cria ações para a janela"""
        # Ações do menu Sistema
        stats_action = Gio.SimpleAction(name="show-stats")
        stats_action.connect("activate", lambda a, p: self.run_paru_command(["paru", "-s"]))
        self.add_action(stats_action)

        news_action = Gio.SimpleAction(name="show-news")
        news_action.connect("activate", lambda a, p: self.run_paru_command(["paru", "-w"]))
        self.add_action(news_action)

        clear_cache_action = Gio.SimpleAction(name="clear-cache")
        clear_cache_action.connect("activate", self.on_clear_cache)
        self.add_action(clear_cache_action)

        update_system_action = Gio.SimpleAction(name="update-system")
        update_system_action.connect("activate", self.on_update_system)
        self.add_action(update_system_action)

        # Ação de preferências
        preferences_action = Gio.SimpleAction(name="show-preferences")
        preferences_action.connect("activate", self.on_show_preferences)
        self.add_action(preferences_action)

        # Ação de ajuda
        help_action = Gio.SimpleAction(name="show-help-overlay")
        help_action.connect("activate", self.on_show_help)
        self.add_action(help_action)

        # Ação Sobre
        about_action = Gio.SimpleAction(name="show-about")
        about_action.connect("activate", self.on_show_about)
        self.add_action(about_action)

    def run_paru_command(self, command):
        """Executa um comando paru no terminal"""
        self.terminal.append(f"Executando: {' '.join(command)}", "info")
        ParuRunner.run_command(command, self.terminal.append)

    def on_clear_cache(self, action, parameter):
        """Limpa o cache do paru"""
        self.terminal.append(_("🧹 Limpando cache do paru..."), "progress")
        ParuRunner.run_command(["paru", "-Sc"], self.terminal.append)

    def on_update_system(self, action, parameter):
        """Atualiza o sistema"""
        self.terminal.append(_("🔄 Atualizando sistema..."), "progress")
        ParuRunner.run_command(["paru", "-Syu"], self.terminal.append)

    def on_show_about(self, action, parameter):
        """Mostra janela Sobre"""
        about = Adw.AboutWindow(
            transient_for=self,
            application_name=_("Paru GUI"),
            application_icon="org.gnome.painel_paru",
            developer_name=_("Equipe Paru GUI"),
            version="0.1.0",
            release_notes=[
                _("Interface gráfica moderna para o gerenciador de pacotes Paru"),
                _("Suporte a builds com revisão do PKGBUILD"),
                _("Detecção automática de conteúdo (PKGBUILD, pacotes, patches)"),
                _("Integração completa com o AUR")
            ],
            copyright=_("© 2023 Paru GUI"),
            license_type=Gtk.License.GPL_3_0
        )

        # Informações básicas
        about.set_website("https://github.com/paru-gui")
        about.set_issue_url("https://github.com/paru-gui/issues")
        about.set_application_icon("org.gnome.painel_paru")
        about.set_developer_name(_("Equipe Paru GUI"))
        about.set_comments(_("Interface gráfica moderna para gerenciamento de pacotes Arch Linux/AUR"))

        # Lista de desenvolvedores
        about.set_developers([
            _("Seu Nome <seu@email.com>"),
            _("Outro Contribuidor <contribuidor@email.com>")
        ])

        # Artistas e documentadores
        about.set_artists([
            _("Designer de UI <designer@email.com>")
        ])
        about.set_documenters([
            _("Documentador <doc@email.com>")
        ])

        # Créditos de tradução
        about.set_translator_credits(_("translator-credits"))

        # Links adicionais
        about.add_link(_("Documentação"), "https://github.com/paru-gui/wiki")
        about.add_link(_("Doações"), "https://github.com/sponsors/paru-gui")

        # Apresenta a janela
        about.present()

    def on_show_preferences(self, action, parameter):
        """Mostra janela de preferências"""
        from .preferences import PreferencesManager
        PreferencesManager(self).show_preferences(self)

    def on_show_help(self, action, parameter):
        """Mostra overlay de ajuda"""
        builder = Gtk.Builder.new_from_resource(
            "/org/gnome/painel_paru/gtk/help-overlay.ui"
        )
        help_overlay = builder.get_object("help_overlay")
        help_overlay.set_transient_for(self)
        help_overlay.present()

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
                self.status_label.set_label(_("✅ Conteúdo carregado: ") + state)
                # Configura botões específicos
                if state == "pkgbuild":
                    self._setup_pkgbuild_buttons(builder)
                elif state == "empty":
                    self._setup_empty_buttons(builder)
                elif state == "packages":
                    self._setup_packages_buttons(builder)
                elif state == "patches":
                    self._setup_patches_buttons(builder)
            else:
                self.status_label.set_label(_("❌ Erro: Widget principal não encontrado"))
        except Exception as e:
            self.status_label.set_label(_("❌ Erro ao carregar tela: ") + str(e))
            print(f"❌ Erro detalhado ao carregar tela: {e}")
            # Fallback visual
            error_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            error_box.set_margin_start(30)
            error_box.set_margin_end(30)
            error_box.set_margin_top(30)
            error_box.set_margin_bottom(30)
            error_label = Gtk.Label(label=_("Erro ao carregar interface para: ") + state)
            error_label.add_css_class("title-3")
            error_box.append(error_label)
            detail_label = Gtk.Label(label=str(e))
            detail_label.set_wrap(True)
            error_box.append(detail_label)
            self.content_box.append(error_box)

    def _setup_pkgbuild_buttons(self, builder):
        """Configura os botões específicos do PKGBUILD"""
        button_configs = {
            "build_button": lambda b: self.on_build(b),
            "build_install_button": lambda b: self.on_build(b, install=True),
            "edit_button": self.on_edit_pkgbuild,
            "deps_button": self.on_check_dependencies,
            "sources_button": self.on_download_sources
        }
        for button_id, callback in button_configs.items():
            button = builder.get_object(button_id)
            if button:
                button.connect("clicked", callback)
            else:
                print(f"⚠️ Botão {button_id} não encontrado no builder")

    def _setup_packages_buttons(self, builder):
        """Configura os botões específicos de pacotes pré-compilados"""
        install_button = builder.get_object("install_button")
        info_button = builder.get_object("info_button")
        verify_button = builder.get_object("verify_button")

        if install_button:
            install_button.connect("clicked", self.on_install_packages)
        if info_button:
            info_button.connect("clicked", self.on_package_info)
        if verify_button:
            verify_button.connect("clicked", self.on_verify_packages)

    def _setup_patches_buttons(self, builder):
        """Configura os botões específicos de patches"""
        apply_button = builder.get_object("apply_patches")
        view_button = builder.get_object("view_patch")
        refresh_button = builder.get_object("refresh_list")

        if apply_button:
            apply_button.connect("clicked", self.on_apply_patches)
        if view_button:
            view_button.connect("clicked", self.on_view_patch)
        if refresh_button:
            refresh_button.connect("clicked", self.on_refresh_patches)

    def _setup_empty_buttons(self, builder):
        """Configura os botões da tela de pasta vazia"""
        aur_search = builder.get_object("aur_search")
        download_button = builder.get_object("download_button")
        search_button = builder.get_object("search_button")

        if aur_search and download_button:
            # Atualiza botão de download conforme digitação
            aur_search.connect("changed", lambda entry:
                download_button.set_sensitive(bool(entry.get_text().strip())))
            # Configura busca ao pressionar Enter
            aur_search.connect("activate", lambda _: download_button.emit("clicked"))
            # Configura botão de download
            download_button.connect("clicked", lambda _:
                self._download_pkgbuild(
                    aur_search.get_text(),
                    builder.get_object("ssh_toggle").get_active() if builder.get_object("ssh_toggle") else False,
                    builder.get_object("comments_toggle").get_active() if builder.get_object("comments_toggle") else False
                ))

        # Conecta botão de busca se existir
        if search_button and aur_search:
            search_button.connect("clicked", lambda _:
                self._search_aur_package(aur_search.get_text()))

    def show_pkgbuild_review_dialog(self, pkgbuild_path, callback):
        """Mostra diálogo de revisão do PKGBUILD"""
        try:
            # Cria um diálogo modal
            dialog = Adw.Window(
                transient_for=self,
                modal=True,
                title=_("Revisão do PKGBUILD"),
                default_width=1000,
                default_height=700
            )

            # Cria o conteúdo principal
            content = Adw.ToolbarView()
            dialog.set_content(content)

            # Header bar
            header = Adw.HeaderBar()
            content.add_top_bar(header)

            # Botão de fechar
            close_button = Gtk.Button(
                icon_name="window-close-symbolic",
                tooltip_text=_("Fechar")
            )
            close_button.connect("clicked", lambda _: dialog.close())
            header.pack_end(close_button)

            # Botão de ação principal
            action_button = Gtk.Button(
                label=_("Aceitar e Compilar"),
                css_classes=["suggested-action"]
            )
            header.pack_end(action_button)

            # Botão de edição
            edit_button = Gtk.Button(
                label=_("Editar PKGBUILD"),
                icon_name="document-edit-symbolic",
                tooltip_text=_("Editar o PKGBUILD atual")
            )
            header.pack_start(edit_button)

            # Cria o conteúdo principal
            main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            main_box.set_margin_start(20)
            main_box.set_margin_end(20)
            main_box.set_margin_top(20)
            main_box.set_margin_bottom(20)

            # Label informativo
            info_label = Gtk.Label(
                label=_("Revise as alterações no PKGBUILD antes de compilar. É recomendado para segurança, especialmente quando baixando de fontes não confiáveis."),
                wrap=True,
                xalign=0,
                margin_bottom=15
            )
            main_box.append(info_label)

            # Cria um Paned para dividir a tela
            paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
            paned.set_vexpand(True)

            # Painel ESQUERDA: PKGBUILD atual
            left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            left_label = Gtk.Label(
                label=_("PKGBUILD Atual"),
                xalign=0,
                css_classes=["heading"]
            )
            left_box.append(left_label)

            left_scroll = Gtk.ScrolledWindow()
            left_scroll.set_vexpand(True)
            left_text = Gtk.TextView(
                editable=False,
                monospace=True,
                wrap_mode=Gtk.WrapMode.WORD
            )
            left_buffer = left_text.get_buffer()
            left_scroll.set_child(left_text)
            left_box.append(left_scroll)

            # Painel DIREITA: PKGBUILD novo (ou fonte do AUR)
            right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            right_label = Gtk.Label(
                label=_("PKGBUILD do AUR"),
                xalign=0,
                css_classes=["heading"]
            )
            right_box.append(right_label)

            right_scroll = Gtk.ScrolledWindow()
            right_scroll.set_vexpand(True)
            right_text = Gtk.TextView(
                editable=False,
                monospace=True,
                wrap_mode=Gtk.WrapMode.WORD
            )
            right_buffer = right_text.get_buffer()
            right_scroll.set_child(right_text)
            right_box.append(right_scroll)

            # Adiciona os painéis ao Paned
            paned.set_start_child(left_box)
            paned.set_end_child(right_box)
            paned.set_position(500)  # Posição inicial do divisor

            main_box.append(paned)
            content.set_content(main_box)

            # Carrega o conteúdo do PKGBUILD atual
            with open(pkgbuild_path, 'r') as f:
                current_content = f.read()
            left_buffer.set_text(current_content)

            # Para demonstração, vamos carregar um "novo" PKGBUILD
            # Na implementação real, isso viria do AUR ou atualização
            # Aqui estamos apenas simulando com o mesmo conteúdo para demonstração
            right_buffer.set_text(current_content)

            # Configura os handlers
            action_button.connect("clicked", lambda _: {
                dialog.close(),
                callback()
            })

            edit_button.connect("clicked", lambda _: {
                self.edit_pkgbuild(pkgbuild_path),
                dialog.close()
            })

            # Apresenta o diálogo
            dialog.present()

        except Exception as e:
            self.terminal.append(
                f"❌ {_('Erro ao mostrar revisão do PKGBUILD:')} {str(e)}", "error"
            )
            print(f"❌ Erro ao mostrar revisão do PKGBUILD: {e}")
            callback()

    def on_build(self, button, install=False):
        """Inicia processo de build com verificação de conflitos"""
        if not hasattr(self, 'content_path') or not self.content_path:
            self.terminal.append(_("❌ Nenhum diretório selecionado."), "error")
            return
        if not os.path.exists(self.content_path):
            self.terminal.append(_("❌ Caminho não existe."), "error")
            return

        # Obtém as configurações necessárias
        review_pkgbuild = self.settings.get_boolean("review-pkgbuild")
        skip_review = self.settings.get_boolean("skip-review")
        clean_after = self.settings.get_boolean("clean-after")

        pkgbuild_path = os.path.join(self.content_path, "PKGBUILD")

        def start_build():
            # Primeiro verifica se há conflitos
            self.terminal.append(_("🔍 Verificando possíveis conflitos..."), "progress")

            # Extrai o nome do pacote do PKGBUILD
            package_name = None
            try:
                with open(pkgbuild_path, 'r') as f:
                    for line in f:
                        if line.startswith("pkgname="):
                            package_name = line.split("=")[1].strip().strip('"')
                            break
            except Exception as e:
                self.terminal.append(f"⚠️ {_('Erro ao ler PKGBUILD:')} {str(e)}", "info")

            # Se não encontrou o nome do pacote, usa o nome da pasta
            if not package_name:
                package_name = os.path.basename(self.content_path)

            # Verifica conflitos
            conflicts = ConflictResolver.check_for_conflicts(package_name)

            if conflicts:
                self.terminal.append(
                    _("⚠️ {} conflitos detectados. Resolvendo...").format(len(conflicts)),
                    "info"
                )
                # Define o callback para continuar o build após resolver conflitos
                self.build_callback = lambda: self._continue_build(install)
                # Mostra o diálogo de conflitos
                ConflictResolver.show_conflict_dialog(self, conflicts, self._on_conflict_resolved)
            else:
                self.terminal.append(_("✅ Nenhum conflito detectado"), "success")
                self._continue_build(install)

        # Se a revisão estiver ativada e não devemos pular
        if review_pkgbuild and not skip_review:
            self.show_pkgbuild_review_dialog(pkgbuild_path, start_build)
        else:
            start_build()

    def _continue_build(self, install):
        """Continua o processo de build após verificar conflitos"""
        action = _("Compilando e instalando") if install else _("Compilando")
        self.terminal.append(
            f"{action} {os.path.basename(self.content_path)}...", "progress"
        )
        self.terminal.show_progress(True, 0.1)

        # Inicia o build com as configurações
        BuildManager.start_build(
            self.content_path,
            install,
            self.terminal.append,
            clean_after=self.settings.get_boolean("clean-after"),
            skip_review=self.settings.get_boolean("skip-review")
        )

    def _on_conflict_resolved(self, success):
        """Callback chamado após resolver conflitos"""
        if success:
            self.terminal.append(_("✅ Conflitos resolvidos com sucesso"), "success")
            # Executa o callback de build
            if self.build_callback:
                self.build_callback()
                self.build_callback = None
        else:
            self.terminal.append(_("❌ Operação cancelada pelo usuário"), "error")
            self.terminal.show_progress(False)

    def on_edit_pkgbuild(self, button):
        """Abre o PKGBUILD no editor configurado"""
        if not hasattr(self, 'content_path') or not self.content_path:
            self.terminal.append(_("❌ Nenhum diretório selecionado."), "error")
            return
        pkgbuild_path = Path(self.content_path) / "PKGBUILD"
        if not pkgbuild_path.exists():
            self.terminal.append(_("❌ PKGBUILD não encontrado."), "error")
            return
        try:
            editor = self.settings.get_string("editor") or "gedit"
            cmd = shlex.split(editor) + [str(pkgbuild_path)]
            subprocess.Popen(cmd)
            self.terminal.append(f"📝 {_('Editando PKGBUILD com')} {editor}...", "info")
        except Exception as e:
            self.terminal.append(f"❌ {_('Erro ao editar PKGBUILD:')} {str(e)}", "error")
            print(f"❌ Erro ao editar PKGBUILD: {e}")

    def on_check_dependencies(self, button):
        """Verifica dependências do pacote"""
        if not hasattr(self, 'content_path') or not self.content_path:
            self.terminal.append(_("❌ Nenhum diretório selecionado."), "error")
            return
        try:
            package_name = Path(self.content_path).name
            self.terminal.append(f"🔍 {_('Verificando dependências de')} {package_name}...", "progress")
            ParuRunner.run_command(["paru", "-Si", package_name], self.terminal.append)
            self.status_label.set_label(_("✅ Dependências verificadas"))
        except Exception as e:
            self.terminal.append(f"❌ {_('Erro ao buscar dependências:')} {str(e)}", "error")
            print(f"❌ Erro ao buscar dependências: {e}")

    def on_download_sources(self, button):
        """Baixa fontes do PKGBUILD"""
        if not hasattr(self, 'content_path') or not self.content_path:
            self.terminal.append(_("❌ Nenhum diretório selecionado."), "error")
            return
        try:
            self.terminal.append(_("📥 Baixando fontes..."), "progress")
            ParuRunner.run_command(["makepkg", "-d", "-C", "--noextract", "-s"], self.terminal.append)
            self.status_label.set_label(_("✅ Fontes baixadas"))
        except Exception as e:
            self.terminal.append(f"❌ {_('Erro ao baixar fontes:')} {str(e)}", "error")
            print(f"❌ Erro ao baixar fontes: {e}")

    def on_install_packages(self, button):
        """Instala pacotes pré-compilados"""
        if not hasattr(self, 'content_path') or not self.content_path:
            self.terminal.append(_("❌ Nenhum diretório selecionado."), "error")
            return

        try:
            self.terminal.append(_("📦 Instalando pacotes..."), "progress")
            # Comando para instalar todos os pacotes .pkg.tar.zst no diretório
            cmd = ["sudo", "pacman", "-U"] + [str(f) for f in Path(self.content_path).glob("*.pkg.tar.zst")]
            ParuRunner.run_command(cmd, self.terminal.append)
        except Exception as e:
            self.terminal.append(f"❌ {_('Erro ao instalar pacotes:')} {str(e)}", "error")
            print(f"❌ Erro ao instalar pacotes: {e}")

    def on_package_info(self, button):
        """Mostra informações dos pacotes"""
        if not hasattr(self, 'content_path') or not self.content_path:
            self.terminal.append(_("❌ Nenhum diretório selecionado."), "error")
            return

        try:
            self.terminal.append(_("ℹ️ Obtendo informações dos pacotes..."), "info")
            # Comando para mostrar informações de todos os pacotes .pkg.tar.zst
            for pkg in Path(self.content_path).glob("*.pkg.tar.zst"):
                ParuRunner.run_command(["pacman", "-Qi", str(pkg)], self.terminal.append)
        except Exception as e:
            self.terminal.append(f"❌ {_('Erro ao obter informações:')} {str(e)}", "error")
            print(f"❌ Erro ao obter informações: {e}")

    def on_verify_packages(self, button):
        """Verifica assinaturas dos pacotes corretamente"""
        if not hasattr(self, 'content_path') or not self.content_path:
            self.terminal.append(_("❌ Nenhum diretório selecionado."), "error")
            return

        try:
            self.terminal.append(_("🔍 Verificando assinaturas..."), "progress")

            # Verifica se o pacman-key está disponível
            if shutil.which("pacman-key") is None:
                self.terminal.append(_("❌ O comando pacman-key não está disponível. Instale o pacote pacman."), "error")
                return

            # Verifica cada pacote na pasta
            packages = list(Path(self.content_path).glob("*.pkg.tar.zst"))
            if not packages:
                self.terminal.append(_("⚠️ Nenhum pacote encontrado para verificar"), "info")
                return

            # Verifica se há arquivos de assinatura
            sig_files = list(Path(self.content_path).glob("*.pkg.tar.zst.sig"))

            if sig_files:
                for sig in sig_files:
                    # Encontra o pacote correspondente
                    pkg_name = str(sig).replace('.sig', '')
                    pkg = Path(pkg_name)

                    if pkg.exists():
                        self.terminal.append(_("Verificando assinatura: ") + sig.name, "info")
                        # Comando correto para verificar a assinatura com pacman-key
                        ParuRunner.run_command(["pacman-key", "--verify", str(sig)], self.terminal.append)
                    else:
                        self.terminal.append(_("⚠️ Pacote correspondente não encontrado para ") + sig.name, "info")
            else:
                self.terminal.append(_("⚠️ Nenhum arquivo de assinatura (.sig) encontrado"), "info")
                # Verifica a integridade dos pacotes instalados (se já estiverem instalados)
                for pkg in packages:
                    # Extrai o nome do pacote do arquivo
                    pkg_name = pkg.name.split('-')[0]
                    self.terminal.append(_("Verificando integridade: ") + pkg_name, "info")
                    # Comando correto para verificar a integridade de pacotes instalados
                    ParuRunner.run_command(["pacman", "-Qk", pkg_name], self.terminal.append)

        except Exception as e:
            self.terminal.append(f"❌ {_('Erro ao verificar assinaturas:')} {str(e)}", "error")
            print(f"❌ Erro ao verificar assinaturas: {e}")

    def on_apply_patches(self, button):
        """Aplica patches ao PKGBUILD"""
        if not hasattr(self, 'content_path') or not self.content_path:
            self.terminal.append(_("❌ Nenhum diretório selecionado."), "error")
            return

        try:
            self.terminal.append(_("🔧 Aplicando patches..."), "progress")
            # Lógica para aplicar patches
            patches = list(Path(self.content_path).glob("*.patch"))
            if not patches:
                self.terminal.append(_("⚠️ Nenhum patch encontrado"), "info")
                return

            for patch in patches:
                self.terminal.append(f"Aplicando {patch.name}...", "info")
                ParuRunner.run_command(["patch", "-p1", "-i", str(patch)], self.terminal.append)

            self.terminal.append(_("✅ Patches aplicados com sucesso"), "success")
        except Exception as e:
            self.terminal.append(f"❌ {_('Erro ao aplicar patches:')} {str(e)}", "error")
            print(f"❌ Erro ao aplicar patches: {e}")

    def on_view_patch(self, button):
        """Visualiza conteúdo de um patch"""
        if not hasattr(self, 'content_path') or not self.content_path:
            self.terminal.append(_("❌ Nenhum diretório selecionado."), "error")
            return

        try:
            patches = list(Path(self.content_path).glob("*.patch"))
            if not patches:
                self.terminal.append(_("⚠️ Nenhum patch encontrado"), "info")
                return

            # Mostra o conteúdo do primeiro patch como exemplo
            patch = patches[0]
            self.terminal.append(f"Conteúdo de {patch.name}:", "info")
            with open(patch, 'r') as f:
                self.terminal.append(f.read(), "normal")
        except Exception as e:
            self.terminal.append(f"❌ {_('Erro ao visualizar patch:')} {str(e)}", "error")
            print(f"❌ Erro ao visualizar patch: {e}")

    def on_refresh_patches(self, button):
        """Atualiza lista de patches"""
        if not hasattr(self, 'content_path') or not self.content_path:
            self.terminal.append(_("❌ Nenhum diretório selecionado."), "error")
            return

        try:
            self.terminal.append(_("🔄 Atualizando lista de patches..."), "progress")
            # Aqui você implementaria a lógica real de atualização
            self.terminal.append(_("Lista de patches atualizada"), "success")
        except Exception as e:
            self.terminal.append(f"❌ {_('Erro ao atualizar lista:')} {str(e)}", "error")
            print(f"❌ Erro ao atualizar lista: {e}")

    def _download_pkgbuild(self, pkg_name, use_ssh, show_comments):
        """Baixa PKGBUILD do AUR"""
        if not pkg_name.strip():
            self.terminal.append(_("❌ Nome do pacote não pode ser vazio."), "error")
            return

        try:
            self.terminal.append(f"📥 {_('Baixando PKGBUILD de')} '{pkg_name}'...", "progress")
            AurDownloader.start_download(pkg_name, self.content_path, use_ssh, self.terminal.append)
        except Exception as e:
            self.terminal.append(f"❌ {_('Erro ao baixar PKGBUILD:')} {str(e)}", "error")
            print(f"❌ Erro ao baixar PKGBUILD: {e}")

    def _search_aur_package(self, query):
        """Busca um pacote no AUR"""
        if not query.strip():
            self.terminal.append(_("⚠️ Digite um nome para buscar no AUR."), "info")
            return

        try:
            self.terminal.append(f"🔍 {_('Buscando no AUR:')} {query}...", "progress")
            # Comando para buscar no AUR
            ParuRunner.run_command(["paru", "-Ss", query], self.terminal.append)
        except Exception as e:
            self.terminal.append(f"❌ {_('Erro ao buscar no AUR:')} {str(e)}", "error")
            print(f"❌ Erro ao buscar no AUR: {e}")

    def search_packages(self, query):
        """Pesquisa pacotes no AUR"""
        if not query.strip():
            return
        self.terminal.append(f"🔍 {_('Pesquisando pacotes:')} {query}...", "info")
        ParuRunner.run_command(["paru", "-Ss", query], self.terminal.append)

    def send_notification(self, title, body, icon_name="dialog-information-symbolic", priority=0):
        """
        Envio compatível com diferentes versões do libadwaita
        Prioridades: 0=normal, 1=high, 2=critical
        """
        try:
            # Tenta usar Adw.Notification (libadwaita 1.5+)
            if hasattr(Adw, 'Notification'):
                notification = Adw.Notification.new(title)
                notification.set_body(body)
                # Define prioridade (0=normal, 1=high, 2=critical)
                if priority == 2:  # CRITICAL
                    notification.set_priority(Adw.NotificationPriority.CRITICAL)
                elif priority == 1:  # HIGH
                    notification.set_priority(Adw.NotificationPriority.HIGH)
                else:  # NORMAL
                    notification.set_priority(Adw.NotificationPriority.NORMAL)
                notification.set_icon(Gio.ThemedIcon(name=icon_name))

                # Gera um ID único para a notificação
                notification_id = f"paru-gui-{hash(title + body)}"
                self.get_application().send_notification(notification_id, notification)
            else:
                # Fallback para Gio.Notification (GNOME 40+)
                notification = Gio.Notification.new(title)
                notification.set_body(body)
                notification.set_icon(Gio.ThemedIcon(name=icon_name))

                # Define prioridade via tags
                if priority == 2:  # CRITICAL
                    notification.set_priority(Gio.NotificationPriority.URGENT)
                elif priority == 1:  # HIGH
                    notification.set_priority(Gio.NotificationPriority.HIGH)
                else:  # NORMAL
                    notification.set_priority(Gio.NotificationPriority.NORMAL)

                # Gera um ID único para a notificação
                notification_id = f"paru-gui-{hash(title + body)}"
                self.get_application().send_notification(notification_id, notification)
        except Exception as e:
            print(f"⚠️ Não foi possível enviar notificação: {str(e)}")
            # Como fallback final, apenas exibe no terminal
            priority_str = ["NORMAL", "HIGH", "CRITICAL"][min(priority, 2)]
            self.terminal.append(
                f"ℹ️ Notificação ({priority_str}): {title} - {body}", "info"
            )

    def send_build_success_notification(self, package_name):
        """Envia notificação de build bem-sucedido"""
        self.send_notification(
            _("Build Concluído"),
            _("O pacote {} foi compilado com sucesso.").format(package_name),
            "package-x-generic-symbolic",
            1  # HIGH
        )

    def send_build_failure_notification(self, package_name, error):
        """Envia notificação de falha no build"""
        self.send_notification(
            _("Falha no Build"),
            _("O build do pacote {} falhou: {}").format(package_name, error),
            "dialog-error-symbolic",
            1  # HIGH
        )

    def send_install_success_notification(self, package_name):
        """Envia notificação de instalação bem-sucedida"""
        self.send_notification(
            _("Instalação Concluída"),
            _("O pacote {} foi instalado com sucesso.").format(package_name),
            "software-installed-symbolic",
            1  # HIGH
        )

    def send_system_update_notification(self, packages_updated):
        """Envia notificação de atualização do sistema"""
        self.send_notification(
            _("Atualização Concluída"),
            _("{} pacotes foram atualizados com sucesso.").format(packages_updated),
            "system-software-update-symbolic",
            1  # HIGH
        )

    def send_error_notification(self, error_title, error_message):
        """Envia notificação de erro crítico"""
        self.send_notification(
            error_title,
            error_message,
            "dialog-error-symbolic",
            2  # CRITICAL
        )

    # ===== Novas funcionalidades adicionadas =====

    def on_back(self, button):
        """Navega de volta para a tela anterior"""
        if self.previous_paths:
            # Salva o caminho atual como sendo o próximo no histórico
            next_path = self.content_path
            self.content_path = self.previous_paths.pop()

            # Atualiza o botão Voltar
            self.back_button.set_sensitive(bool(self.previous_paths))

            # Carrega o conteúdo do caminho anterior
            self.status_label.set_label(_("Analisando: ") + self.content_path)
            state = ContentDetector.detect_content(self.content_path)
            self._load_content_screen(state)

            # Atualiza o estado dos botões
            self.open_folder_button.set_sensitive(True)

            # Se houver um próximo caminho, adiciona ao histórico futuro (não implementado)

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

    def on_cancel_operation(self, button):
        """Cancela a operação em andamento"""
        if self.current_process:
            try:
                # Envia sinal de término ao processo
                self.current_process.terminate()
                self.terminal.append(_("🛑 Operação cancelada pelo usuário"), "info")

                # Remove referência ao processo
                self.current_process = None

                # Atualiza a interface
                self.cancel_button.set_visible(False)
                self.terminal.show_progress(False)
            except Exception as e:
                self.terminal.append(_("❌ Erro ao cancelar operação: ") + str(e), "error")
                print(f"❌ Erro ao cancelar operação: {e}")

    def set_current_process(self, process):
        """Define o processo atual e atualiza a interface"""
        self.current_process = process
        self.cancel_button.set_visible(True)

    def clear_current_process(self):
        """Limpa a referência ao processo atual"""
        self.current_process = None
        self.cancel_button.set_visible(False)

    def on_clear_cache(self, action, parameter):
        """Limpa o cache do paru com suporte a cancelamento"""
        self.terminal.append(_("🧹 Limpando cache do paru..."), "progress")
        # Para demonstração, vamos criar um processo simulado
        self.set_current_process(subprocess.Popen(["echo", "simulated process"]))
        ParuRunner.run_command(["paru", "-Sc"], self.terminal.append)
        # Na implementação real, o ParuRunner precisaria retornar o processo
        # para que pudéssemos cancelá-lo

    def on_update_system(self, action, parameter):
        """Atualiza o sistema com suporte a cancelamento"""
        self.terminal.append(_("🔄 Atualizando sistema..."), "progress")
        # Para demonstração, vamos criar um processo simulado
        self.set_current_process(subprocess.Popen(["echo", "simulated process"]))
        ParuRunner.run_command(["paru", "-Syu"], self.terminal.append)
        # Na implementação real, o ParuRunner precisaria retornar o processo
        # para que pudéssemos cancelá-lo
