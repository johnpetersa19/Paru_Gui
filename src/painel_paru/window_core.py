# window_core.py
from gi.repository import Gtk, Gio, Adw, GLib
import gettext
import os
import sys
from .terminal import TerminalView
from .content_detector import ContentDetector
from .build_manager import BuildManager
from .paru_runner import ParuRunner
from .aur_downloader import AurDownloader
from .conflict_resolver import ConflictResolver

_ = gettext.gettext

class WindowCore:
    """Classe base com a funcionalidade central da janela e inicialização"""

    def __init__(self):
        """Inicializa os componentes básicos da janela"""
        self._setup_translations()
        self._setup_window_properties()
        self._setup_settings()
        self._setup_internal_state()
        self._init_core_components()

    def _setup_translations(self):
        """Configura o sistema de traduções para o aplicativo"""
        try:
            # Tenta encontrar o diretório de localização
            localedir = self._find_localedir()
            if localedir:
                gettext.bindtextdomain("painel_paru", localedir)
                gettext.textdomain("painel_paru")
                print(f"✅ Traduções configuradas com localedir: {localedir}")
            else:
                print("⚠️ Diretório de traduções não encontrado, usando padrões do sistema")
        except Exception as e:
            print(f"❌ Erro ao configurar traduções: {str(e)}")

    def _find_localedir(self):
        """Encontra o diretório de localização para traduções"""
        # Possíveis locais onde os arquivos de tradução podem estar
        possible_locations = [
            # Diretório padrão de instalação
            os.path.join(sys.prefix, 'share/locale'),
            # Diretório de instalação personalizado
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'locale'),
            # Diretório de desenvolvimento
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'po'),
            # Diretório Flatpak
            "/app/share/runtime/locale"
        ]

        for localedir in possible_locations:
            if os.path.exists(os.path.join(localedir, "pt_BR", "LC_MESSAGES", "painel_paru.mo")):
                return localedir

        return None

    def _setup_window_properties(self):
        """Configura propriedades básicas da janela"""
        self.set_title(_("Paru GUI"))
        self.set_default_size(900, 650)
        self.set_icon_name("org.gnome.painel_paru")

        # Configura o fechamento da janela
        self.connect("close-request", self.on_close_request)

        print("✅ Propriedades da janela configuradas")

    def _setup_settings(self):
        """Configura o sistema de preferências usando GSettings"""
        try:
            self.settings = Gio.Settings.new("org.gnome.painel_paru")
            print("✅ Configurações inicializadas com sucesso")

            # Configura listeners para mudanças nas configurações
            self._setup_settings_listeners()
        except Exception as e:
            print(f"❌ Erro ao inicializar configurações: {str(e)}")
            # Cria um objeto vazio para evitar erros
            self.settings = type('Settings', (), {
                'get_boolean': lambda x: False,
                'get_string': lambda x: '',
                'set_boolean': lambda x, y: None,
                'set_string': lambda x, y: None
            })()

    def _setup_settings_listeners(self):
        """Configura listeners para mudanças nas configurações"""
        # Exemplo de listener (pode ser expandido conforme necessário)
        self.settings.connect("changed::theme", self._on_theme_changed)

    def _on_theme_changed(self, settings, key):
        """Callback para mudanças no tema"""
        theme = settings.get_string(key)
        print(f"🎨 Tema alterado para: {theme}")

        # Aplica o tema ao aplicativo
        app = self.get_application()
        if app:
            style_manager = app.get_style_manager()

            if theme == "system":
                style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
            elif theme == "light":
                style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
            elif theme == "dark":
                style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)

    def _setup_internal_state(self):
        """Configura o estado interno da aplicação"""
        # Variáveis de estado
        self.previous_paths = []
        self.current_path = None
        self.current_state = None
        self.process = None
        self.content_path = None
        self.build_callback = None
        self.toolbar_view = None
        self.status_label = None
        self.back_button = None
        self.open_folder_button = None
        self.cancel_button = None
        self.terminal = None
        self.content_box = None

        print("✅ Estado interno configurado")

    def _init_core_components(self):
        """Inicializa os componentes básicos da aplicação"""
        # Inicializa histórico de navegação
        self.previous_paths = []
        self.content_path = None
        self.current_path = None
        self.current_state = None

        # Inicializa o terminal
        self.terminal = TerminalView()

        # Inicializa os componentes de gerenciamento
        self.build_callback = None  # Callback para continuar o build após resolver conflitos
        self.current_process = None  # Armazena o processo atual para permitir cancelamento
        self.conflict_resolver = ConflictResolver()

        # Inicializa outros componentes
        self.build_manager = BuildManager()
        self.paru_runner = ParuRunner()
        self.aur_downloader = AurDownloader(self.terminal.append)

        print("✅ Componentes básicos inicializados")

    def on_close_request(self, window):
        """Handler para quando a janela é fechada"""
        print("CloseOperation: Janela sendo fechada")

        # Cancela qualquer processo em execução
        if hasattr(self, 'process') and self.process:
            try:
                self.process.terminate()
                print("CloseOperation: Processo em execução terminado")
            except Exception as e:
                print(f"CloseOperation: Erro ao terminar processo: {str(e)}")

        # Salva configurações atuais
        self._save_window_state()

        # Permite que a janela seja fechada
        return False

    def _save_window_state(self):
        """Salva o estado atual da janela nas configurações"""
        width, height = self.get_default_size()
        self.settings.set_int("window-width", width)
        self.settings.set_int("window-height", height)

        # Salva estado do painel lateral
        if hasattr(self, 'sidebar'):
            self.settings.set_boolean("sidebar-visible", self.sidebar.get_visible())

        print(f"CloseOperation: Estado da janela salvo ({width}x{height})")

    def setup_window(self):
        """Configuração final da janela antes de exibir"""
        # Restaura tamanho da janela
        width = self.settings.get_int("window-width")
        height = self.settings.get_int("window-height")
        if width > 0 and height > 0:
            self.set_default_size(width, height)

        # Configura o tema inicial
        theme = self.settings.get_string("theme")
        self._on_theme_changed(self.settings, "theme")

        print("✅ Configuração final da janela concluída")

    def get_application(self):
        """Obtém a aplicação associada a esta janela"""
        return super().get_application()

    def show_error_message(self, title, message):
        """Exibe uma mensagem de erro para o usuário"""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=title,
            body=message
        )
        dialog.add_response("ok", _("OK"))
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.present()

    def show_info_message(self, title, message):
        """Exibe uma mensagem informativa para o usuário"""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=title,
            body=message
        )
        dialog.add_response("ok", _("OK"))
        dialog.present()

    def log_startup(self):
        """Registra informações de inicialização"""
        print(f"✅ Aplicativo iniciado às {GLib.DateTime.new_now_local().format('%H:%M:%S')}")
        print(f"ℹ️ Versão: {self.get_application().props.application_id}")
        print(f"ℹ️ Ambiente: {'Flatpak' if self.is_flatpak() else 'Nativo'}")

    def is_flatpak(self):
        """Verifica se o aplicativo está sendo executado em um ambiente Flatpak"""
        return os.path.exists("/.flatpak-info")

    def set_current_process(self, process):
        """Define o processo atual que está sendo executado"""
        self.process = process
        print(f"🔄 Processo definido: {process.pid if process else 'None'}")

    def initialize_ui(self):
        """Inicializa a interface do usuário"""
        # Criação do layout principal
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Configura a barra de ferramentas
        self.setup_toolbar(main_box)

        # Configura a barra de status
        self.setup_status_bar(main_box)

        # Configura a área de conteúdo
        self.setup_content_area(main_box)

        # Configura as ações da janela
        self.setup_window_actions()

        print("✅ Interface do usuário inicializada")

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

        print("✅ Barra de ferramentas configurada")

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

        # Botão de cópia do log
        copy_log_button = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
        copy_log_button.set_tooltip_text(_("Copiar log para área de transferência"))
        copy_log_button.connect("clicked", self.on_copy_log)
        status_box.append(copy_log_button)

        # Botão de cancelamento
        self.cancel_button = Gtk.Button.new_from_icon_name("process-stop-symbolic")
        self.cancel_button.set_tooltip_text(_("Cancelar operação atual"))
        self.cancel_button.set_sensitive(False)
        status_box.append(self.cancel_button)

        # Adiciona à interface
        parent_box.append(status_box)

        # Terminal
        self.terminal = TerminalView()
        self.terminal.set_size_request(-1, 150)
        terminal_box = Gtk.ScrolledWindow()
        terminal_box.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        terminal_box.set_child(self.terminal)

        parent_box.append(terminal_box)

        print("✅ Barra de status configurada")

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

        print("✅ Área de conteúdo configurada")

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

        print("✅ Ações da janela configuradas")

    def on_back_button_clicked(self, button):
        """Handler para o botão Voltar"""
        if self.previous_paths:
            self.content_path = self.previous_paths.pop()
            self.current_path = self.content_path

            state = ContentDetector.detect_content(self.content_path)
            self._load_content_screen(state)

            self.back_button.set_sensitive(bool(self.previous_paths))

    def on_update_system(self, action, parameter):
        """Atualiza o sistema usando Paru"""
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

        # Créditos
        about.set_developers([
            _("Desenvolvedor Principal <dev@email.com>"),
            _("Contribuidores <contrib@email.com>")
        ])
        about.set_designers([
            _("Designer de UI <designer@email.com>")
        ])
        about.set_documenters([
            _("Documentador <doc@email.com>")
        ])
        about.set_copyright(_("© 2023 Painel Paru"))
        about.set_website("https://github.com/paru-gui")
        about.set_issue_url("https://github.com/paru-gui/issues")
        about.set_license_type(Gtk.License.GPL_3_0)

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
        builder = Gtk.Builder.new_from_resource("/org/gnome/painel_paru/gtk/help-overlay.ui")
        help_overlay = builder.get_object("help_overlay")
        self.set_help_overlay(help_overlay)
        help_overlay.present()

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

    def _setup_patches_card_buttons(self, patches_card):
        """Configura os botões específicos do card Patches"""
        apply_button = patches_card.get_template_child(type(patches_card), 'apply_button')
        if apply_button:
            apply_button.connect("clicked", self.on_apply_patches)

        view_button = patches_card.get_template_child(type(patches_card), 'view_button')
        if view_button:
            view_button.connect("clicked", self.on_view_patch)

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
