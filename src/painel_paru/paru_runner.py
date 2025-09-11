import subprocess
import os
from gi.repository import GLib, Gio

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
        try:
            # Verifica se estamos em um ambiente Flatpak
            is_flatpak = os.path.exists("/.flatpak-info")

            # Se for Flatpak, tenta usar flatpak-spawn para acessar comandos do host
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
                    full_cmd = cmd
            else:
                full_cmd = cmd

            process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )

            def read_output():
                """Lê a saída do processo e atualiza a interface"""
                try:
                    for line in process.stdout:
                        GLib.idle_add(output_callback, line.strip())
                    return False  # Processo terminou, para de monitorar
                except Exception as e:
                    output_callback(f"❌ Erro ao ler saída: {str(e)}", "error")
                    return False

            # Configura o monitoramento da saída
            GLib.idle_add(read_output)

            return process  # Retorna o processo para permitir cancelamento

        except Exception as e:
            output_callback(f"❌ Erro ao executar comando: {str(e)}", "error")
            print(f"❌ Erro ao executar comando: {e}")
            return None
