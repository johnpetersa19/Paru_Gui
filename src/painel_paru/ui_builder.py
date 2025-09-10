from gi.repository import Gtk, Adw, Gio
import gettext
_ = gettext.gettext

# Configuração de mapeamento de estados para interfaces
UI_BUILDER_CONFIG = {
    "packages": {
        "file": "content_detection/packages_card.ui",
        "widget_id": "PackagesCard"
    },
    "patches": {
        "file": "content_detection/patches_card.ui",
        "widget_id": "PatchesCard"
    },
    "aur": {
        "file": "content_detection/aur_search.ui",
        "widget_id": "AurSearchCard"
    },
    "empty": {
        "file": "content_detection/empty_card.ui",
        "widget_id": "EmptyCard"
    },
    "generic": {
        "file": "content_detection/empty_card.ui",
        "widget_id": "EmptyCard"
    }
}

class UI_Builder:
    def __init__(self, window):
        self.window = window
        self.content_box = None
        self.toolbar_box = None
        self.header_title = None
        self.header_bar = None
        self.back_button = None
        self.open_folder_button = None
        self.cancel_button = None

    def build_main_interface(self):
        """Constrói a interface principal da aplicação"""
        # Configuração principal da janela
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.window.set_content(main_box)

        # Cabeçalho
        self.header_bar = Adw.HeaderBar()
        self.header_title = Adw.WindowTitle(title=_("Explorador"))
        self.header_bar.set_title_widget(self.header_title)
        main_box.append(self.header_bar)

        # Menu
        menu_button = self.window.menu_manager.create_menu()
        self.header_bar.pack_end(menu_button)

        # Barra de ferramentas
        toolbar_view = Adw.ToolbarView()
        main_box.append(toolbar_view)

        # Caixa da toolbar
        self.toolbar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.toolbar_box.set_margin_start(10)
        self.toolbar_box.set_margin_end(10)
        self.toolbar_box.set_margin_top(5)
        self.toolbar_box.set_margin_bottom(5)

        # Botões de navegação
        self.back_button = Gtk.Button(
            icon_name="go-previous-symbolic",
            tooltip_text=_("Voltar")
        )
        self.back_button.set_sensitive(False)
        self.back_button.connect("clicked", self.window.handlers.on_back)

        self.open_folder_button = Gtk.Button(
            icon_name="folder-open-symbolic",
            tooltip_text=_("Abrir pasta no gerenciador de arquivos"),
            sensitive=False
        )
        self.open_folder_button.connect("clicked", self.window.handlers.on_open_folder)

        # Botão de cancelar operação
        self.cancel_button = Gtk.Button(
            icon_name="process-stop-symbolic",
            tooltip_text=_("Cancelar operação"),
            visible=False
        )
        self.cancel_button.connect("clicked", self.window.handlers.on_cancel_operation)

        # Caixa para os botões de navegação
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        nav_box.append(self.back_button)
        nav_box.append(self.open_folder_button)
        nav_box.append(self.cancel_button)

        # Adiciona os botões na toolbar
        center_box = Gtk.Box()
        center_box.set_hexpand(True)
        self.toolbar_box.append(nav_box)
        self.toolbar_box.append(center_box)

        toolbar_view.add_top_bar(self.toolbar_box)

        # Conteúdo principal
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content_box.set_vexpand(True)
        toolbar_view.set_content(self.content_box)

        # Terminal - Configuração correta do terminal
        terminal_components = self.window.terminal_manager.create_terminal()
        terminal = terminal_components['terminal']
        progress_bar = terminal_components['progress_bar']
        terminal_box = terminal_components['terminal_box']

        # Configura propriedades e adiciona à interface
        terminal.set_vexpand(True)
        self.content_box.append(terminal_box)

        # SÓ AGORA que todos os componentes estão criados, configuramos o estado inicial
        # Isso é CRÍTICO para evitar erros de inicialização
        self.window.content_path = None
        self.window.current_state = None
        self.window.current_process = None
        # Mantido por compatibilidade, mas o navigation_manager gerencia o histórico
        self.window._navigation_history = []
        self.window.navigation_manager.previous_paths = []

        # Configura o estado inicial dos botões
        # (já que os componentes já foram criados, podemos configurá-los)
        self.back_button.set_sensitive(False)
        self.open_folder_button.set_sensitive(False)
        self.cancel_button.set_visible(False)

        # Retorna todos os componentes necessários
        return {
            'content_box': self.content_box,
            'toolbar_box': self.toolbar_box,
            'header_title': self.header_title,
            'header_bar': self.header_bar,
            'back_button': self.back_button,
            'open_folder_button': self.open_folder_button,
            'cancel_button': self.cancel_button,
            'terminal': terminal,
            'progress_bar': progress_bar,
            'terminal_box': terminal_box
        }

    def load_initial_screen(self):
        """Carrega a tela inicial da aplicação"""
        # Limpa o conteúdo atual
        while self.content_box.get_first_child():
            self.content_box.remove(self.content_box.get_first_child())

        try:
            # Carrega a tela inicial - CAMINHO CORRIGIDO (sem "src/gtk" extra)
            builder = Gtk.Builder.new_from_resource("/org/gnome/painel_paru/gtk/initial_screen.ui")
            initial_screen = builder.get_object("main_box")

            if initial_screen:
                self.content_box.append(initial_screen)

                # Configura os botões
                select_file_button = builder.get_object("select_file_button")
                select_folder_button = builder.get_object("select_folder_button")

                if select_file_button:
                    select_file_button.connect("clicked", self.window.handlers.on_select_file)

                if select_folder_button:
                    select_folder_button.connect("clicked", self.window.handlers.on_select_folder)

                return True
            else:
                self.window.terminal_manager.append(_("❌ Erro: Tela inicial não encontrada"), "error")
                return False

        except Exception as e:
            self.window.terminal_manager.append(f"❌ {_('Erro ao carregar tela inicial:')} {str(e)}", "error")
            print(f"❌ Erro ao carregar tela inicial: {e}")
            return False

    def load_content_screen(self, state):
        """Carrega a tela de conteúdo adequada baseado no estado detectado"""
        self.window.current_state = state

        # Usa configuração padrão se estado não for encontrado
        config = UI_BUILDER_CONFIG.get(state, UI_BUILDER_CONFIG["empty"])

        try:
            # Carrega o recurso - CAMINHO CORRIGIDO (prefixo correto do gresource)
            resource_path = f"/org/gnome/painel_paru/gtk/{config['file']}"
            builder = Gtk.Builder.new_from_resource(resource_path)

            # Procura o widget principal
            widgets = builder.get_objects()
            main_widget = None
            for widget in widgets:
                if hasattr(widget, 'get_widget_id') and widget.get_widget_id() == config["widget_id"]:
                    main_widget = widget
                    break

            if not main_widget:
                # Tenta encontrar por classe
                for widget in widgets:
                    if isinstance(widget, Gtk.Widget):
                        main_widget = widget
                        break

            if main_widget:
                # Remove conteúdo atual
                if self.content_box.get_first_child():
                    self.content_box.remove(self.content_box.get_first_child())

                # Adiciona novo conteúdo
                self.content_box.append(main_widget)

                # Configura botões específicos do estado
                self.window.navigation_manager._setup_state_buttons(main_widget, state)

                # Atualiza informações do cabeçalho
                self.window.navigation_manager._update_header(state)

                return True
            else:
                self.window.terminal_manager.append(_("❌ Erro: Widget principal não encontrado"), "error")
                return False

        except Exception as e:
            self.window.terminal_manager.append(f"❌ {_('Erro ao carregar interface:')} {str(e)}", "error")
            print(f"❌ Erro ao carregar interface: {e}")
            return False

    def update_operation_ui_state(self, is_running):
        """Atualiza a interface baseado no estado de operação"""
        # Atualiza visibilidade do botão de cancelar
        if hasattr(self, 'cancel_button') and self.cancel_button is not None:
            self.cancel_button.set_visible(is_running)

        # Atualiza sensibilidade do menu
        if hasattr(self.window, 'menu_manager') and self.window.menu_manager is not None:
            self.window.menu_manager.update_menu_state(is_running)

        # Usa o navigation_manager para verificar o histórico
        if hasattr(self, 'back_button') and self.back_button is not None:
            # Verifica se o navigation_manager está disponível
            if hasattr(self.window, 'navigation_manager'):
                can_navigate_back = bool(self.window.navigation_manager.previous_paths)
                self.back_button.set_sensitive(can_navigate_back and not is_running)
            else:
                self.back_button.set_sensitive(False)

        if hasattr(self, 'open_folder_button') and self.open_folder_button is not None:
            self.open_folder_button.set_sensitive(
                self.window.content_path is not None and not is_running
            )