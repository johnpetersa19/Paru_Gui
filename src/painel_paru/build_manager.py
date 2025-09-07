import subprocess
import os
from gi.repository import GLib

class BuildManager:
    """Gerencia operações de build com Paru"""
    
    @staticmethod
    def get_paru_command(target_path: str, install: bool = False) -> list:
        """Gera comando Paru para build"""
        cmd = ["paru", "-B", target_path]
        if install:
            cmd.append("--install")
        return cmd
    
    @staticmethod
    def start_build(target_path: str, install: bool, output_callback) -> None:
        """Inicia processo de build com fallback seguro"""
        try:
            cmd = BuildManager.get_paru_command(target_path, install)
            output_callback(f"Iniciando build de {target_path}...")

            # Verifica se estamos em um ambiente Flatpak
            is_flatpak = os.path.exists("/.flatpak-info")

            # Tenta usar flatpak-spawn se estiver em Flatpak
            if is_flatpak:
                try:
                    # Primeira tentativa com flatpak-spawn
                    full_cmd = ["flatpak-spawn", "--host"] + cmd
                    output_callback("⚠️ Executando em ambiente Flatpak, usando flatpak-spawn")

                    # Verifica se o flatpak-spawn está disponível
                    subprocess.run(["flatpak-spawn", "--version"],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL,
                                  check=True)

                    process = subprocess.Popen(
                        full_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        cwd=target_path
                    )
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    output_callback("⚠️ flatpak-spawn não disponível, tentando diretamente...")
                    # Fallback: tenta executar o comando diretamente
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        cwd=target_path
                    )
            else:
                # Não é Flatpak, executa normalmente
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    cwd=target_path
                )

            def read_output():
                for line in process.stdout:
                    GLib.idle_add(output_callback, line.strip())
                return process.poll() is None

            GLib.idle_add(read_output)
        except Exception as e:
            output_callback(f"❌ Erro ao iniciar build: {str(e)}", "error")
            print(f"❌ Erro ao iniciar build: {e}")
