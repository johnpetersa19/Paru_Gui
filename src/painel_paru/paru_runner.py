import subprocess
import os
import logging
from gi.repository import GLib, Gio
import gettext

_ = gettext.gettext

class ParuRunner:
    """Executa comandos Paru com suporte a atualização da interface e cancelamento"""
    
    @staticmethod
    def run_command(cmd, output_callback):
        """
        Executa um comando Paru e atualiza a interface com a saída.
        Retorna o objeto do processo para permitir cancelamento.

        :param cmd: Lista de comandos a serem executados
        :param output_callback: Função de callback para atualizar a interface
        :return: Objeto do processo ou None em caso de erro
        """
        # Validação básica do comando
        if not cmd or not isinstance(cmd, list) or len(cmd) == 0:
            error_msg = _("Comando inválido: lista de comandos vazia ou não é uma lista")
            logging.error("Invalid command: empty command list or not a list")
            if output_callback:
                output_callback(error_msg, "error")
            return None

        # Log para depuração (em inglês para facilitar diagnóstico)
        logging.debug("Executing command: %s", " ".join(cmd))

        try:
            # Verifica se estamos em um ambiente Flatpak
            is_flatpak = os.path.exists("/.flatpak-info")
            full_cmd = cmd.copy()  # Cria cópia para não modificar o original

            # Se for Flatpak, tenta usar flatpak-spawn para acessar comandos do host
            if is_flatpak:
                try:
                    # Verifica se flatpak-spawn está disponível
                    subprocess.run(["flatpak-spawn", "--version"],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL,
                                  check=True,
                                  timeout=2.0)
                    full_cmd = ["flatpak-spawn", "--host"] + cmd
                    if output_callback:
                        output_callback(_("Executando em ambiente Flatpak com flatpak-spawn"), "info")
                except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                    if output_callback:
                        output_callback(_("flatpak-spawn não disponível, executando diretamente"), "warning")
            else:
                if output_callback:
                    output_callback(_("Executando em ambiente nativo"), "info")

            # Configura o ambiente para evitar problemas de localização
            env = os.environ.copy()
            env["LANG"] = "C"
            env["LC_ALL"] = "C"

            process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                env=env,
                bufsize=1,
                close_fds=True
            )

            def read_output():
                """Lê a saída do processo e atualiza a interface"""
                try:
                    for line in process.stdout:
                        stripped_line = line.strip()
                        if stripped_line and output_callback:
                            GLib.idle_add(output_callback, stripped_line)
                    return False  # Processo terminou, para de monitorar
                except Exception as e:
                    error_msg = _("Erro ao ler saída: %s") % str(e)
                    logging.error("Error reading output: %s", str(e))
                    if output_callback:
                        output_callback(error_msg, "error")
                    return False

            # Configura o monitoramento da saída
            GLib.idle_add(read_output)

            return process  # Retorna o processo para permitir cancelamento

        except FileNotFoundError as e:
            error_msg = _("Comando não encontrado: %s") % cmd[0]
            logging.error("Command not found: %s", cmd[0])
            if output_callback:
                output_callback(error_msg, "error")
        except PermissionError as e:
            error_msg = _("Permissão negada para executar: %s") % cmd[0]
            logging.error("Permission denied for command: %s", cmd[0])
            if output_callback:
                output_callback(error_msg, "error")
        except subprocess.SubprocessError as e:
            error_msg = _("Erro ao executar subprocesso: %s") % str(e)
            logging.error("Subprocess error: %s", str(e))
            if output_callback:
                output_callback(error_msg, "error")
        except Exception as e:
            error_msg = _("Erro inesperado ao executar comando: %s") % str(e)
            logging.exception("Critical error in ParuRunner")
            if output_callback:
                output_callback(error_msg, "error")

        return None