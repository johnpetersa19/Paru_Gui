import subprocess
import os
from gi.repository import GLib, Gio

class ParuRunner:
    """Executa comandos Paru com suporte a atualização da interface"""
    
    @staticmethod
    def run_command(cmd, output_callback):
        """Executa um comando Paru e atualiza a interface com a saída"""
        try:
            # Verifica se estamos em um ambiente Flatpak
            is_flatpak = os.path.exists("/.flatpak-info")

            # Se for Flatpak, usa flatpak-spawn para acessar comandos do host
            if is_flatpak:
                full_cmd = ["flatpak-spawn", "--host"] + cmd
                output_callback("⚠️ Executando em ambiente Flatpak, usando flatpak-spawn")
            else:
                full_cmd = cmd

            process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )

            def read_output():
                for line in process.stdout:
                    GLib.idle_add(output_callback, line.strip())
                return process.poll() is None
                
            GLib.idle_add(read_output)
        except Exception as e:
            output_callback(f"❌ Erro ao executar comando: {str(e)}", "error")
            print(f"❌ Erro ao executar comando: {e}")
