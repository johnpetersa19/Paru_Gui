from gi.repository import Gtk, Gio, GLib
import gettext
import logging

_ = gettext.gettext

class MenuManager:
    """Gerenciador centralizado do menu da aplicação

    Esta classe é responsável por criar, configurar e gerenciar o menu popover da aplicação,
    incluindo todas as opções e ações associadas. Ela integra-se com o sistema de ações GIO
    do GTK para fornecer uma interface de menu consistente e responsiva.

    Principais responsabilidades:
    - Criação do menu popover com organização lógica das opções
    - Configuração das ações GIO e conexão com os handlers apropriados
    - Atualização do estado do menu durante operações em andamento
    - Integração com outros componentes da aplicação (terminal, action manager)

    O menu é organizado em seções lógicas, com ênfase nas operações mais comuns do sistema
    e preferências de usuário. A classe garante que o menu permaneça responsivo mesmo durante
    operações longas, desabilitando opções inapropriadas.
    """

    def __init__(self, window):
        """
        Inicializa o gerenciador de menu.

        Args:
            window (PainelParuWindow): Referência para a janela principal da aplicação.
                Deve conter os atributos necessários para integração, como
                handlers, terminal_manager, etc.

        Example:
            >>> window = PainelParuWindow()
            >>> menu_manager = MenuManager(window)
            >>> menu_button = menu_manager.create_menu()
            >>> header_bar.pack_end(menu_button)
        """
        self.window = window
        self.popover = None
        self.logger = logging.getLogger(__name__)
        self._is_initialized = False

    def create_menu(self):
        """
        Cria e configura o menu popover da aplicação.

        Este método constrói a estrutura completa do menu, organizando as opções
        em seções lógicas e conectando-as às ações apropriadas. O menu é criado
        como um Gtk.PopoverMenu com uma hierarquia clara de opções.

        Returns:
            Gtk.MenuButton: Botão de menu configurado, pronto para ser adicionado
                           à interface (geralmente no HeaderBar)

        Example:
            >>> menu_button = menu_manager.create_menu()
            >>> header_bar.pack_end(menu_button)

        Note:
            - O método deve ser chamado após a inicialização completa da janela
            - O menu criado inclui seções para Sistema, Preferências e Informações
            - O popover é configurado automaticamente com o modelo de menu adequado
        """
        try:
            # Botão de menu
            menu_button = Gtk.MenuButton()
            menu_button.set_icon_name("open-menu-symbolic")
            menu_button.set_tooltip_text(_("Menu da aplicação"))

            # Menu popover
            self.popover = Gtk.PopoverMenu()
            menu_button.set_popover(self.popover)

            # Configuração do menu
            menu_model = Gio.Menu()

            # Adiciona seções do menu
            self._add_system_section(menu_model)
            self._add_preferences_section(menu_model)
            self._add_info_section(menu_model)

            # Configura o modelo no popover
            self.popover.set_menu_model(menu_model)

            # Marca como inicializado
            self._is_initialized = True

            return menu_button

        except Exception as e:
            error_type = type(e).__name__
            self.logger.error("Error creating menu: %s", str(e))
            # Cria um botão de fallback em caso de erro
            fallback_button = Gtk.MenuButton()
            fallback_button.set_icon_name("open-menu-symbolic")
            fallback_button.set_sensitive(False)
            fallback_button.set_tooltip_text(_("Menu indisponível"))
            return fallback_button

    def _add_system_section(self, menu_model):
        """
        Adiciona a seção do menu Sistema ao modelo.

        Esta seção contém operações relacionadas ao sistema e ao gerenciador de pacotes,
        como verificação de estatísticas, notícias, limpeza de cache e atualização do sistema.

        Args:
            menu_model (Gio.Menu): Modelo de menu ao qual a seção será adicionada
        """
        system_menu = Gio.Menu()

        # Adiciona opções ao menu Sistema
        system_menu.append(_("Estatísticas"), "win.show-stats")
        system_menu.append(_("Notícias do Arch"), "win.show-news")
        system_menu.append(_("Limpar Cache"), "win.clear-cache")
        system_menu.append(_("Atualizar Sistema"), "win.update-system")

        # Cria o item do menu principal com o submenu
        menu_model.append_submenu(_("Sistema"), system_menu)

    def _add_preferences_section(self, menu_model):
        """
        Adiciona a seção de preferências ao modelo do menu.

        Esta seção contém opções relacionadas às configurações da aplicação.

        Args:
            menu_model (Gio.Menu): Modelo de menu ao qual a seção será adicionada
        """
        preferences_menu = Gio.Menu()
        preferences_menu.append(_("Preferências"), "win.show-preferences")
        menu_model.append_submenu(_("Configurações"), preferences_menu)

    def _add_info_section(self, menu_model):
        """
        Adiciona a seção de informações ao modelo do menu.

        Esta seção contém opções de ajuda, informações sobre a aplicação e saída.

        Args:
            menu_model (Gio.Menu): Modelo de menu ao qual a seção será adicionada
        """
        info_menu = Gio.Menu()
        info_menu.append(_("Atalhos"), "win.show-help-overlay")
        info_menu.append(_("Sobre"), "win.show-about")
        info_menu.append(_("Sair"), "app.quit")

        menu_model.append_submenu(_("Informações"), info_menu)

    def create_actions(self):
        """
        Cria e registra todas as ações GIO necessárias para o funcionamento do menu.

        Este método cria todas as ações GIO que são referenciadas pelo menu, conectando-as
        aos handlers apropriados na classe WindowHandlers. As ações são registradas na
        janela principal para que possam ser acessadas por outros componentes.

        Note:
            - Deve ser chamado após a inicialização do WindowHandlers
            - As ações são registradas com window.add_action()
            - Ações são organizadas por categoria (sistema, interface, etc.)
        """
        try:
            # Ações do menu Sistema
            self._create_system_actions()

            # Ações de interface
            self._create_ui_actions()

            # Ações do aplicativo
            self._create_app_actions()

        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao criar ações do menu: %s") % error_type
            if hasattr(self.window, 'terminal_manager'):
                self.window.terminal_manager.show_error(error_msg)
            self.logger.error("Error creating menu actions: %s", str(e))

    def _create_system_actions(self):
        """Cria ações relacionadas ao sistema e operações do paru"""
        # Conecta diretamente aos handlers centralizados
        clear_cache_action = Gio.SimpleAction(name="clear-cache")
        clear_cache_action.connect("activate", self.window.handlers.on_clear_cache)
        self.window.add_action(clear_cache_action)

        update_system_action = Gio.SimpleAction(name="update-system")
        update_system_action.connect("activate", self.window.handlers.on_update_system)
        self.window.add_action(update_system_action)

    def _create_ui_actions(self):
        """Cria ações relacionadas à interface do usuário"""
        # Ação de preferências
        preferences_action = Gio.SimpleAction(name="show-preferences")
        preferences_action.connect("activate", self.window.handlers.on_show_preferences)
        self.window.add_action(preferences_action)

        # Ação de ajuda
        help_action = Gio.SimpleAction(name="show-help-overlay")
        help_action.connect("activate", self.window.handlers.on_show_help)
        self.window.add_action(help_action)

    def _create_app_actions(self):
        """Cria ações relacionadas ao aplicativo como um todo"""
        # Ação Sobre
        about_action = Gio.SimpleAction(name="show-about")
        about_action.connect("activate", self.window.handlers.on_show_about)
        self.window.add_action(about_action)

    def update_menu_state(self, is_operation_running):
        """
        Atualiza o estado do menu baseado em operações em andamento.

        Este método desabilita o menu durante operações que modificam o sistema
        (como atualizações ou limpeza de cache), evitando que o usuário inicie
        múltiplas operações simultâneas que possam causar conflitos.

        Args:
            is_operation_running (bool): Indica se uma operação está em andamento

        Returns:
            None: O método atualiza diretamente o estado do menu

        Example:
            >>> menu_manager.update_menu_state(True)  # Desativa o menu
            >>> menu_manager.update_menu_state(False) # Reativa o menu

        Note:
            - O menu é desabilitado durante operações longas para evitar conflitos
            - O estado é atualizado imediatamente na interface
            - O método é seguro para chamar mesmo se o menu não estiver inicializado
        """
        try:
            # Verifica se o menu foi inicializado
            if not self._is_initialized:
                return

            # Atualiza a sensibilidade do popover
            if self.popover and hasattr(self.popover, 'set_sensitive'):
                self.popover.set_sensitive(not is_operation_running)

        except Exception as e:
            error_type = type(e).__name__
            self.logger.warning("Error updating menu state: %s", str(e))

    def is_initialized(self):
        """
        Verifica se o menu foi inicializado com sucesso.

        Returns:
            bool: True se o menu foi inicializado, False caso contrário
        """
        return self._is_initialized