import subprocess
import os
from gi.repository import GLib

class BuildManager:
    """Gerencia operações de build com Paru e suporte a cancelamento"""

    @staticmethod
    def get_paru_command(target_path: str, install: bool = False,
                        clean_after: bool = False, skip_review: bool = False) -> list:
        """
        Gera comando Paru para build com todas as opções configuráveis

        :param target_path: Caminho para o diretório do PKGBUILD
        :param install: Se deve instalar após o build
        :param clean_after: Se deve limpar após o build
        :param skip_review: Se deve pular a revisão do PKGBUILD
        :return: Lista de comandos a serem executados
        """
        cmd = ["paru", "-B", target_path]
        if install:
            cmd.append("--install")
        if clean_after:
            cmd.append("--cleanafter")
        if skip_review:
            cmd.append("--skipreview")
        return cmd

    @staticmethod
    def start_build(target_path: str, install: bool, output_callback,
                   clean_after: bool = False, skip_review: bool = False):
        """
        Inicia processo de build com fallback seguro e opções configuráveis.
        Retorna o objeto do processo para permitir cancelamento.

        :param target_path: Caminho para o diretório do PKGBUILD
        :param install: Se deve instalar após o build
        :param output_callback: Função para atualizar a interface com a saída
        :param clean_after: Se deve limpar após o build
        :param skip_review: Se deve pular a revisão do PKGBUILD
        :return: Objeto do processo ou None em caso de falha
        """
        try:
            cmd = BuildManager.get_paru_command(target_path, install, clean_after, skip_review)
            output_callback(f"Iniciando build de {target_path}...")

            # Adiciona informações sobre as opções selecionadas
            options_info = []
            if clean_after:
                options_info.append(_("limpeza após build ativada"))
            if skip_review:
                options_info.append(_("revisão do PKGBUILD ignorada"))
            if options_info:
                output_callback(f"ℹ️ {_('Opções selecionadas:')} {', '.join(options_info)}")

            # Verifica se estamos em um ambiente Flatpak
            is_flatpak = os.path.exists("/.flatpak-info")
            full_cmd = cmd

            # Configura o comando baseado no ambiente
            if is_flatpak:
                try:
                    # Verifica se flatpak-spawn está disponível
                    subprocess.run(["flatpak-spawn", "--version"],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL,
                                  check=True)
                    full_cmd = ["flatpak-spawn", "--host"] + cmd
                    output_callback("ℹ️ Executando em ambiente Flatpak com flatpak-spawn")
                except (subprocess.CalledProcessError, FileNotFoundError):
                    output_callback("⚠️ flatpak-spawn não disponível, executando diretamente")

            try:
                process = subprocess.Popen(
                    full_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    cwd=target_path,
                    bufsize=1,
                    close_fds=True
                )

                def read_output():
                    """Lê a saída do processo e atualiza a interface"""
                    try:
                        for line in process.stdout:
                            GLib.idle_add(output_callback, line.strip())
                        return False  # Processo terminou, para de monitorar
                    except Exception as e:
                        output_callback(f"❌ {_('Erro ao ler saída:')} {str(e)}", "error")
                        return False

                GLib.idle_add(read_output)
                return process  # Retorna o processo para permitir cancelamento

            except Exception as e:
                output_callback(f"⚠️ {_('Falha ao executar comando:')} {str(e)}", "error")
                print(f"⚠️ Falha ao executar comando: {e}")
                return None

        except Exception as e:
            error_msg = f"❌ {_('Erro crítico ao iniciar build:')} {str(e)}"
            output_callback(error_msg, "error")
            print(error_msg)
            return None
