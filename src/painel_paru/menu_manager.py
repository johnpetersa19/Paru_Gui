from gi.repository import Gtk, Gio
import gettext
_ = gettext.gettext

class MenuManager:
    def __init__(self, window):
        self.window = window
        self.popover = None

    def create_menu(self):
        """Cria e configura o menu popover da aplicação"""
        # Botão de menu
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_tooltip_text(_("Menu"))

        # Menu popover
        self.popover = Gtk.PopoverMenu()
        menu_button.set_popover(self.popover)

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

        return menu_button

    def create_actions(self):
        """Cria todas as ações da aplicação"""
        # Ações do menu Sistema
        stats_action = Gio.SimpleAction(name="show-stats")
        stats_action.connect("activate", lambda a, p: self._run_paru_command(["paru", "-s"]))
        self.window.add_action(stats_action)

        news_action = Gio.SimpleAction(name="show-news")
        news_action.connect("activate", lambda a, p: self._run_paru_command(["paru", "-w"]))
        self.window.add_action(news_action)

        # Conecta diretamente aos handlers centralizados
        clear_cache_action = Gio.SimpleAction(name="clear-cache")
        clear_cache_action.connect("activate", self.window.handlers.on_clear_cache)
        self.window.add_action(clear_cache_action)

        update_system_action = Gio.SimpleAction(name="update-system")
        update_system_action.connect("activate", self.window.handlers.on_update_system)
        self.window.add_action(update_system_action)

        # Ação de preferências
        preferences_action = Gio.SimpleAction(name="show-preferences")
        preferences_action.connect("activate", self.window.handlers.on_show_preferences)
        self.window.add_action(preferences_action)

        # Ação de ajuda
        help_action = Gio.SimpleAction(name="show-help-overlay")
        help_action.connect("activate", self.window.handlers.on_show_help)
        self.window.add_action(help_action)

        # Ação Sobre
        about_action = Gio.SimpleAction(name="show-about")
        about_action.connect("activate", self.window.handlers.on_show_about)
        self.window.add_action(about_action)

        # Ação para atualizar sistema (duplicada para o menu)
        update_action = Gio.SimpleAction(name="update-system")
        update_action.connect("activate", self.window.handlers.on_update_system)
        self.window.add_action(update_action)

    def _run_paru_command(self, command):
        """Executa um comando paru no terminal"""
        # CORREÇÃO: Usando método helper show_info() em vez de append() com status
        self.window.terminal_manager.show_info(f"Executando: {' '.join(command)}")
        from .paru_runner import ParuRunner
        ParuRunner.run_command(command, self.window.terminal_manager.append)

    def update_menu_state(self, is_operation_running):
        """Atualiza o estado do menu baseado em operações em andamento"""
        if self.popover and hasattr(self.popover, 'set_sensitive'):
            self.popover.set_sensitive(not is_operation_running)
