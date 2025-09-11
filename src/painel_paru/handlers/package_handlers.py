from gi.repository import Gtk
import os
import gettext
from pathlib import Path
_ = gettext.gettext

# ❌ Removido: check_path_exists (não existe mais)
# ✅ Usamos apenas validate_path
from .utils import validate_path
from .paru_runner import ParuRunner


class PackageHandlers:
    def __init__(self, window):
        self.window = window
        self.logger = window.logger
        self.terminal_manager = window.terminal_manager

    def on_install_packages(self, *args, **kwargs):
        """Instala todos os pacotes .pkg.tar.zst encontrados no diretório atual.
        Este método localiza todos os pacotes no formato .pkg.tar.zst no diretório
        selecionado e os instala usando o comando `sudo pacman -U`.
        """
        # Valida: caminho existe e é um diretório
        if not validate_path(
            self.window,
            self.terminal_manager,
            must_be_directory=True
        ):
            return

        try:
            # Listar todos os pacotes no diretório
            packages = list(Path(self.window.content_path).glob("*.pkg.tar.zst"))
            if not packages:
                self.terminal_manager.show_warning(_("Nenhum pacote encontrado para instalar."))
                return

            self.terminal_manager.show_progress(_("Preparando para instalação..."))

            # Comando para instalar todos os pacotes
            cmd = ["sudo", "pacman", "-U"] + [str(pkg) for pkg in packages]

            # Executar instalação
            self.terminal_manager.show_info(_("Instalando %d pacotes...") % len(packages))
            ParuRunner.run_command(cmd, self.terminal_manager.append)
            self.terminal_manager.show_success(_("Instalação concluída!"))

        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao instalar pacotes: %s") % error_type
            self.terminal_manager.show_error(error_msg)
            self.logger.error("Error installing packages: %s - %s", error_type, str(e))

    def on_packages_info(self, *args, **kwargs):
        """Mostra informações detalhadas de todos os pacotes no diretório atual.
        Este método localiza todos os pacotes no formato .pkg.tar.zst no diretório
        atual e executa `pacman -Qi` para obter informações detalhadas.
        """
        # Valida: caminho existe e é um diretório
        if not validate_path(
            self.window,
            self.terminal_manager,
            must_be_directory=True
        ):
            return

        try:
            # Listar todos os pacotes no diretório
            packages = list(Path(self.window.content_path).glob("*.pkg.tar.zst"))
            if not packages:
                self.terminal_manager.show_warning(_("Nenhum pacote encontrado para verificar."))
                return

            for pkg in packages:
                # Extrai o nome do pacote do arquivo
                pkg_name = pkg.name.split('-')[0]
                self.terminal_manager.show_info(_("Verificando informações: %s") % pkg_name)

                # Comando para obter informações do pacote
                ParuRunner.run_command(["pacman", "-Qi", pkg_name], self.terminal_manager.append)

        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao obter informações dos pacotes: %s") % error_type
            self.terminal_manager.show_error(error_msg)
            self.logger.error("Error getting packages info: %s - %s", error_type, str(e))

    def on_verify_signatures(self, *args, **kwargs):
        """Verifica assinaturas de pacotes e sua integridade no diretório atual.
        Este método realiza duas verificações importantes:
        1. Verifica assinaturas de arquivos .sig usando pacman-key
        2. Verifica a integridade de pacotes instalados usando pacman -Qk
        """
        # Valida: caminho existe e é um diretório
        if not validate_path(
            self.window,
            self.terminal_manager,
            must_be_directory=True
        ):
            return

        try:
            self.terminal_manager.show_progress(_("Verificando assinaturas e integridade..."))

            # Verificar assinaturas dos arquivos .sig
            sig_files = list(Path(self.window.content_path).glob("*.sig"))
            if sig_files:
                self.terminal_manager.show_info(_("Verificando %d assinaturas...") % len(sig_files))
                for sig_file in sig_files:
                    pkg_file = sig_file.with_suffix('')
                    if pkg_file.exists():
                        self.terminal_manager.append(_("Verificando: %s") % pkg_file.name)
                        ParuRunner.run_command(
                            ["pacman-key", "-v", str(sig_file)],
                            self.terminal_manager.append
                        )
                    else:
                        self.terminal_manager.show_warning(
                            _("Arquivo correspondente não encontrado para %s") % sig_file.name
                        )

            # Verificar integridade dos pacotes
            packages = list(Path(self.window.content_path).glob("*.pkg.tar.zst"))
            if packages:
                self.terminal_manager.show_info(_("Verificando integridade de %d pacotes...") % len(packages))
                for pkg in packages:
                    # Extrai o nome do pacote do arquivo
                    pkg_name = pkg.name.split('-')[0]
                    self.terminal_manager.append(_("Verificando integridade: %s") % pkg_name)

                    # Comando correto para verificar a integridade de pacotes instalados
                    ParuRunner.run_command(["pacman", "-Qk", pkg_name], self.terminal_manager.append)

            if not sig_files and not packages:
                self.terminal_manager.show_warning(_("Nenhum arquivo para verificar."))

        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao verificar assinaturas: %s") % error_type
            self.terminal_manager.show_error(error_msg)
            self.logger.error("Error verifying signatures: %s - %s", error_type, str(e))
