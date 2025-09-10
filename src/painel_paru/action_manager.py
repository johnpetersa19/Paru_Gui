from gi.repository import Gtk, Gio, GLib
import gettext
_ = gettext.gettext

class ActionManager:
    def __init__(self, window):
        self.window = window

    def create_actions(self):
        """Cria todas as ações da aplicação"""
        # Ações do menu Sistema
        stats_action = Gio.SimpleAction(name="show-stats")
        stats_action.connect("activate", lambda a, p: self._run_paru_command(["paru", "-s"]))
        self.window.add_action(stats_action)

        news_action = Gio.SimpleAction(name="show-news")
        news_action.connect("activate", lambda a, p: self._run_paru_command(["paru", "-w"]))
        self.window.add_action(news_action)

        clear_cache_action = Gio.SimpleAction(name="clear-cache")
        clear_cache_action.connect("activate", self._on_clear_cache)
        self.window.add_action(clear_cache_action)

        update_system_action = Gio.SimpleAction(name="update-system")
        update_system_action.connect("activate", self._on_update_system)
        self.window.add_action(update_system_action)

        # Ação de preferências
        preferences_action = Gio.SimpleAction(name="show-preferences")
        preferences_action.connect("activate", self._on_show_preferences)
        self.window.add_action(preferences_action)

        # Ação de ajuda
        help_action = Gio.SimpleAction(name="show-help-overlay")
        help_action.connect("activate", self._on_show_help)
        self.window.add_action(help_action)

        # Ação Sobre
        about_action = Gio.SimpleAction(name="show-about")
        about_action.connect("activate", self._on_show_about)
        self.window.add_action(about_action)

        # Ação para atualizar sistema (duplicada para o menu)
        update_action = Gio.SimpleAction(name="update-system")
        update_action.connect("activate", self._on_update_system)
        self.window.add_action(update_action)

    def _run_paru_command(self, command):
        """Executa um comando paru no terminal"""
        # CORREÇÃO: Usando método helper show_info() em vez de append() com status
        self.window.terminal_manager.show_info(f"Executando: {' '.join(command)}")
        from .paru_runner import ParuRunner
        ParuRunner.run_command(command, self.window.terminal_manager.append)

    def _on_clear_cache(self, action, parameter):
        """Limpa o cache do paru"""
        # CORREÇÃO: Usando método helper show_progress() em vez de append() com status
        # REMOVIDO o emoji 🧹 pois o método helper já adiciona o emoji 🔄 automaticamente
        self.window.terminal_manager.show_progress(_("Limpando cache do paru..."))
        from .paru_runner import ParuRunner
        ParuRunner.run_command(["paru", "-Sc"], self.window.terminal_manager.append)

    def _on_update_system(self, action, parameter):
        """Atualiza o sistema"""
        # CORREÇÃO: Usando método helper show_progress() em vez de append() com status
        # REMOVIDO o emoji 🔄 pois o método helper já adiciona o emoji automaticamente
        self.window.terminal_manager.show_progress(_("Atualizando sistema..."))
        from .paru_runner import ParuRunner
        ParuRunner.run_command(["paru", "-Syu"], self.window.terminal_manager.append)

    def _on_show_preferences(self, action, parameter):
        """Mostra janela de preferências"""
        from .preferences_manager import PreferencesManager
        PreferencesManager(self.window).show_preferences(self.window)

    def _on_show_help(self, action, parameter):
        """Mostra overlay de ajuda"""
        builder = Gtk.Builder.new_from_resource("/org/gnome/painel_paru/gtk/help-overlay.ui")
        help_overlay = builder.get_object("help_overlay")
        help_overlay.set_transient_for(self.window)
        help_overlay.present()

    def _on_show_about(self, action, parameter):
        """Mostra janela Sobre"""
        from gi.repository import Adw
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
        about.set_website("https://github.com/paru-gui  ")

        # Links adicionais
        about.add_link(_("Documentação"), "https://github.com/paru-gui/wiki  ")
        about.add_link(_("Doações"), "https://github.com/sponsors/paru-gui  ")

        # Apresenta a janela
        about.present()
