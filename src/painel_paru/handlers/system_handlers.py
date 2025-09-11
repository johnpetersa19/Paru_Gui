from gi.repository import Gtk
import os
import gettext
_ = gettext.gettext

from .paru_runner import ParuRunner
from .utils import validate_path  # Função única para validação de caminhos


class SystemHandlers:
    def __init__(self, window):
        self.window = window
        self.logger = window.logger
        self.terminal_manager = window.terminal_manager

    def on_check_updates(self, *args, **kwargs):
        """Verifica atualizações disponíveis no sistema.
        Este método executa o comando `paru -Qua` para listar todas as atualizações
        disponíveis, incluindo pacotes do AUR.
        """
        self.terminal_manager.show_progress(_("Verificando atualizações..."))

        try:
            # Obter preferências
            from .preferences_manager import PreferencesManager
            prefs = PreferencesManager.get_preferences()
            devel_mode = prefs.get_boolean("devel-mode")

            # Montar comando
            cmd = ["paru", "-Qua"]
            if not devel_mode:
                # Filtrar pacotes de desenvolvimento
                cmd.extend(["--ignore", "*-git", "*-svn", "*-hg", "*-bzr", "*-darcs", "*-nightly"])

            # Executar verificação
            ParuRunner.run_command(cmd, self.terminal_manager.append)

        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao verificar atualizações: %s") % error_type
            self.terminal_manager.show_error(error_msg)
            self.logger.error("Error checking updates: %s - %s", error_type, str(e))

    def on_update_system(self, *args, **kwargs):
        """Atualiza o sistema completo.
        Este método executa o comando `paru -Syu` para atualizar todos os pacotes
        do sistema, incluindo pacotes do AUR.
        """
        self.terminal_manager.show_progress(_("Atualizando sistema..."))
        ParuRunner.run_command(["paru", "-Syu"], self.terminal_manager.append)

    def on_check_dependencies(self, *args, **kwargs):
        """Verifica as dependências do pacote no diretório atual.
        Este método executa o comando `paru -Si` para obter informações detalhadas
        sobre um pacote, incluindo suas dependências.
        """
        # Validação do caminho usando a função unificada
        if not validate_path(
            self.window,
            self.terminal_manager,
            must_be_directory=True  # Verifica apenas se o caminho existe e é um diretório
        ):
            return

        try:
            package_name = os.path.basename(self.window.content_path)
            self.terminal_manager.show_progress(_("Verificando dependências de %s...") % package_name)
            ParuRunner.run_command(["paru", "-Si", package_name], self.terminal_manager.append)

        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao verificar dependências: %s") % error_type
            self.terminal_manager.show_error(error_msg)
            self.logger.error("Error checking dependencies: %s - %s", error_type, str(e))
