from gi.repository import Gtk, Gio, GLib, Adw
import gettext
import logging

_ = gettext.gettext

class ActionManager:
    """Gerenciador centralizado de ações da aplicação

    Esta classe é responsável por criar e gerenciar todas as ações da aplicação,
    incluindo ações de menu, atalhos de teclado e ações de contexto. Ela centraliza
    a lógica de execução de comandos do sistema, preferências, ajuda e outras
    funcionalidades principais da interface.

    Principais responsabilidades:
    - Criação de ações GIO para integração com GTK
    - Conexão de handlers para execução de comandos Paru
    - Gerenciamento do estado das ações baseado nas operações em andamento
    - Integração com outros componentes da aplicação (terminal, gerenciador de menu)

    A classe segue o padrão singleton dentro do contexto da janela principal,
    garantindo que haja apenas uma instância por janela da aplicação.
    """

    def __init__(self, window):
        """
        Inicializa o gerenciador de ações.

        Args:
            window (PainelParuWindow): Referência para a janela principal da aplicação.
                Deve conter os atributos necessários para integração, como
                terminal_manager, menu_manager, etc.

        Example:
            >>> window = PainelParuWindow()
            >>> action_manager = ActionManager(window)
            >>> action_manager.create_actions()
        """
        self.window = window
        self.logger = logging.getLogger(__name__)

    def create_actions(self):
        """
        Cria e configura todas as ações da aplicação para integração com GTK.

        Este método cria todas as ações GIO necessárias para a aplicação, incluindo
        ações para o menu principal, atalhos de teclado e funcionalidades específicas.
        As ações são registradas na janela principal para que possam ser acessadas
        por outros componentes da interface.

        Ações criadas:
        - show-stats: Mostra estatísticas do sistema
        - show-news: Mostra notícias do Arch Linux
        - clear-cache: Limpa o cache do paru
        - update-system: Atualiza o sistema completo
        - show-preferences: Abre as preferências da aplicação
        - show-help-overlay: Mostra a sobreposição de ajuda
        - show-about: Mostra a janela "Sobre"

        Note:
            - Este método deve ser chamado durante a inicialização da janela
            - As ações são registradas na janela principal com window.add_action()
            - As ações são automaticamente vinculadas aos handlers apropriados
        """
        # Ações do menu Sistema
        self._create_system_actions()

        # Ações de interface
        self._create_ui_actions()

    def _create_system_actions(self):
        """Cria ações relacionadas ao sistema e operações do paru"""
        # Estatísticas do sistema
        stats_action = Gio.SimpleAction(name="show-stats")
        stats_action.connect("activate", lambda a, p: self._run_paru_command(["paru", "-s"]))
        self.window.add_action(stats_action)

        # Notícias do Arch
        news_action = Gio.SimpleAction(name="show-news")
        news_action.connect("activate", lambda a, p: self._run_paru_command(["paru", "-w"]))
        self.window.add_action(news_action)

        # Limpar cache
        clear_cache_action = Gio.SimpleAction(name="clear-cache")
        clear_cache_action.connect("activate", self._on_clear_cache)
        self.window.add_action(clear_cache_action)

        # Atualizar sistema
        update_system_action = Gio.SimpleAction(name="update-system")
        update_system_action.connect("activate", self._on_update_system)
        self.window.add_action(update_system_action)

    def _create_ui_actions(self):
        """Cria ações relacionadas à interface do usuário"""
        # Preferências
        preferences_action = Gio.SimpleAction(name="show-preferences")
        preferences_action.connect("activate", self._on_show_preferences)
        self.window.add_action(preferences_action)

        # Ajuda
        help_action = Gio.SimpleAction(name="show-help-overlay")
        help_action.connect("activate", self._on_show_help)
        self.window.add_action(help_action)

        # Sobre
        about_action = Gio.SimpleAction(name="show-about")
        about_action.connect("activate", self._on_show_about)
        self.window.add_action(about_action)

    def _run_paru_command(self, command):
        """
        Executa um comando paru no terminal com feedback adequado ao usuário.

        Este método é um helper para execução de comandos do paru, garantindo
        que a interface do usuário seja atualizada corretamente com o status
        da operação. Ele utiliza o TerminalManager para exibir mensagens de
        progresso e resultados.

        Args:
            command (list): Lista de strings representando o comando a ser executado.
                           Exemplo: ["paru", "-Syu"]

        Returns:
            None: A execução é assíncrona, o resultado é exibido no terminal

        Example:
            >>> self._run_paru_command(["paru", "-Si", "firefox"])
            # Executa o comando e exibe a saída no terminal

        Note:
            - O método mostra automaticamente uma mensagem de progresso
            - A saída do comando é direcionada para o terminal da aplicação
            - Não bloqueia a interface do usuário durante a execução
        """
        try:
            # Mostra mensagem de progresso no terminal
            self.window.terminal_manager.show_info(_("Executando: %s") % " ".join(command))

            # Executa o comando usando ParuRunner
            from .paru_runner import ParuRunner
            process = ParuRunner.run_command(command, self.window.terminal_manager.append)

            # Armazena o processo atual para permitir cancelamento
            if hasattr(self.window, 'current_process'):
                self.window.current_process = process

        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao executar comando: %s") % error_type
            self.window.terminal_manager.show_error(error_msg)
            self.logger.error("Error executing command %s: %s", command, str(e))

    def _on_clear_cache(self, action, parameter):
        """
        Handler para limpeza do cache do paru.

        Este método é chamado quando o usuário seleciona a opção de limpar cache
        no menu da aplicação. Ele inicia o processo de limpeza do cache do paru,
        exibindo mensagens de progresso apropriadas na interface.

        Args:
            action (Gio.Action): A ação GIO que disparou este handler
            parameter (GLib.Variant): Parâmetro opcional passado com a ação

        Returns:
            None: A execução é assíncrona, o resultado é exibido no terminal

        Note:
            - Utiliza o método helper show_progress() para feedback ao usuário
            - Executa o comando "paru -Sc" para limpar o cache
            - A saída do comando é exibida diretamente no terminal da aplicação
        """
        try:
            # Mostra mensagem de progresso
            self.window.terminal_manager.show_progress(_("Limpando cache do paru..."))

            # Executa o comando
            from .paru_runner import ParuRunner
            process = ParuRunner.run_command(["paru", "-Sc"], self.window.terminal_manager.append)

            # Armazena o processo atual
            if hasattr(self.window, 'current_process'):
                self.window.current_process = process

        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao limpar cache: %s") % error_type
            self.window.terminal_manager.show_error(error_msg)
            self.logger.error("Error clearing cache: %s", str(e))

    def _on_update_system(self, action, parameter):
        """
        Handler para atualização do sistema completo.

        Este método é chamado quando o usuário seleciona a opção de atualização
        do sistema no menu da aplicação. Ele inicia o processo de atualização
        completa do sistema usando o paru, exibindo mensagens de progresso
        apropriadas na interface.

        Args:
            action (Gio.Action): A ação GIO que disparou este handler
            parameter (GLib.Variant): Parâmetro opcional passado com a ação

        Returns:
            None: A execução é assíncrona, o resultado é exibido no terminal

        Note:
            - Utiliza o método helper show_progress() para feedback ao usuário
            - Executa o comando "paru -Syu" para atualizar o sistema
            - A saída do comando é exibida diretamente no terminal da aplicação
            - Este é um processo que pode levar tempo considerável
        """
        try:
            # Mostra mensagem de progresso
            self.window.terminal_manager.show_progress(_("Atualizando sistema..."))

            # Executa o comando
            from .paru_runner import ParuRunner
            process = ParuRunner.run_command(["paru", "-Syu"], self.window.terminal_manager.append)

            # Armazena o processo atual
            if hasattr(self.window, 'current_process'):
                self.window.current_process = process

        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao atualizar sistema: %s") % error_type
            self.window.terminal_manager.show_error(error_msg)
            self.logger.error("Error updating system: %s", str(e))

    def _on_show_preferences(self, action, parameter):
        """
        Handler para exibição da janela de preferências.

        Este método é chamado quando o usuário seleciona a opção de preferências
        no menu da aplicação. Ele cria e exibe a janela de preferências, permitindo
        que o usuário configure as opções da aplicação.

        Args:
            action (Gio.Action): A ação GIO que disparou este handler
            parameter (GLib.Variant): Parâmetro opcional passado com a ação

        Returns:
            None: A janela de preferências é exibida diretamente

        Note:
            - Utiliza PreferencesManager para gerenciar a interface de preferências
            - A janela é modal e vinculada à janela principal
            - As alterações nas preferências são salvas automaticamente
        """
        try:
            from .preferences_manager import PreferencesManager
            PreferencesManager(self.window).show_preferences()
        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao abrir preferências: %s") % error_type
            self.window.terminal_manager.show_error(error_msg)
            self.logger.error("Error showing preferences: %s", str(e))

    def _on_show_help(self, action, parameter):
        """
        Handler para exibição da sobreposição de ajuda.

        Este método é chamado quando o usuário seleciona a opção de ajuda
        no menu da aplicação ou pressiona o atalho de teclado apropriado.
        Ele carrega e exibe a sobreposição de ajuda com os atalhos e
        informações básicas sobre o uso da aplicação.

        Args:
            action (Gio.Action): A ação GIO que disparou este handler
            parameter (GLib.Variant): Parâmetro opcional passado com a ação

        Returns:
            None: A sobreposição de ajuda é exibida diretamente

        Note:
            - A sobreposição é carregada a partir de um arquivo .ui
            - É uma janela modal vinculada à janela principal
            - Fecha automaticamente quando o usuário pressiona Esc ou clica fora
        """
        try:
            builder = Gtk.Builder.new_from_resource("/org/gnome/painel_paru/gtk/help-overlay.ui")
            help_overlay = builder.get_object("help_overlay")
            if help_overlay:
                help_overlay.set_transient_for(self.window)
                help_overlay.present()
            else:
                self.window.terminal_manager.show_error(_("Erro ao carregar sobreposição de ajuda"))
                self.logger.error("Help overlay not found in UI file")
        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao carregar ajuda: %s") % error_type
            self.window.terminal_manager.show_error(error_msg)
            self.logger.error("Error showing help overlay: %s", str(e))

    def _on_show_about(self, action, parameter):
        """
        Handler para exibição da janela "Sobre".

        Este método é chamado quando o usuário seleciona a opção "Sobre"
        no menu da aplicação. Ele cria e exibe a janela de informações
        sobre a aplicação, incluindo versão, créditos e links úteis.

        Args:
            action (Gio.Action): A ação GIO que disparou este handler
            parameter (GLib.Variant): Parâmetro opcional passado com a ação

        Returns:
            None: A janela "Sobre" é exibida diretamente

        Note:
            - Utiliza Adw.AboutWindow para uma integração nativa com Adwaita
            - Inclui links para documentação, doações e repositório
            - Mostra informações de versão e licença
        """
        try:
            about = Adw.AboutWindow(
                transient_for=self.window,
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

            # Links adicionais
            about.add_link(_("Documentação"), "https://github.com/paru-gui/wiki")
            about.add_link(_("Doações"), "https://github.com/sponsors/paru-gui")

            # Apresenta a janela
            about.present()

        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao exibir janela Sobre: %s") % error_type
            self.window.terminal_manager.show_error(error_msg)
            self.logger.error("Error showing about window: %s", str(e))