from gi.repository import Gtk, Gio, Adw
import os
import gettext
_ = gettext.gettext

class UIHandlers:
    def __init__(self, window):
        """Inicializa o gerenciador de handlers de UI.

        Args:
            window (Gtk.Window): Referência para a janela principal da aplicação
        """
        self.window = window
        self.logger = window.logger

    def on_show_preferences(self, *args, **kwargs):
        """Abre a janela de preferências da aplicação.
        Esta janela permite ao usuário configurar opções como editor padrão,
        limpeza após build e outras configurações específicas.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: A janela de preferências é exibida de forma modal

        Example:
            >>> handlers.on_show_preferences()
            # Abre a janela de preferências

        Note:
            - A janela é modal e vinculada à janela principal
            - As alterações nas preferências são salvas automaticamente
            - A interface é atualizada para refletir as novas configurações
            - Usa PreferencesManager para gerenciar a lógica da janela
        """
        try:
            from .preferences_manager import PreferencesManager
            PreferencesManager(self.window).show_preferences()
        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao abrir preferências: %s") % error_type
            self.window.terminal_manager.show_error(error_msg)
            self.logger.error("Error showing preferences: %s", str(e))

    def on_show_help(self, *args, **kwargs):
        """Exibe a sobreposição de ajuda da aplicação.
        Este método carrega e exibe a sobreposição de ajuda com os atalhos
        e informações básicas sobre o uso da aplicação.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: A sobreposição de ajuda é exibida diretamente

        Note:
            - A sobreposição é carregada a partir de um arquivo .ui
            - É uma janela modal vinculada à janela principal
            - Fecha automaticamente quando o usuário pressiona Esc ou clica fora
            - Mostra apenas atalhos relevantes para o estado atual da aplicação
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
            error_msg = _("Erro ao exibir ajuda: %s") % error_type
            self.window.terminal_manager.show_error(error_msg)
            self.logger.error("Error showing help: %s", str(e))

    def on_show_about(self, *args, **kwargs):
        """Exibe a janela "Sobre" com informações da aplicação.
        Esta janela contém informações como nome e versão da aplicação,
        créditos da equipe de desenvolvimento e links úteis.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: A janela "Sobre" é exibida de forma modal

        Example:
            >>> handlers.on_show_about()
            # Exibe a janela "Sobre" com informações da aplicação

        Note:
            - A janela é modal e vinculada à janela principal
            - Contém informações básicas, créditos e links úteis
            - Usa Adw.AboutWindow para uma integração nativa com libadwaita
            - A licença é exibida como GPL 3.0
        """
        try:
            about = Adw.AboutWindow(
                transient_for=self.window,
                application_name=_("Painel Paru"),
                application_icon="org.gnome.painel_paru",
                developer_name=_("Equipe de Desenvolvimento"),
                version="1.0",
                developers=["Desenvolvedor 1", "Desenvolvedor 2"],
                comments=_("Interface gráfica para gerenciamento de pacotes com Paru"),
                website="https://example.com",
                issue_url="https://example.com/issues",
                license_type=Gtk.License.GPL_3_0
            )

            # Adicionar seções de doação e recursos
            about.add_link(_("Documentação"), "https://example.com/docs")
            about.add_link(_("Doações"), "https://example.com/donate")
            about.add_link(_("Repositório"), "https://github.com/example/painel_paru")

            about.present()
        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao exibir sobre: %s") % error_type
            self.window.terminal_manager.show_error(error_msg)
            self.logger.error("Error showing about: %s", str(e))
