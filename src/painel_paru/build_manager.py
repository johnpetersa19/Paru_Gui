import subprocess
import os
from gi.repository import GLib

class BuildManager:
    """Gerencia operações de build com Paru"""
    @staticmethod
    def get_paru_command(target_path: str, install: bool = False,
                        clean_after: bool = False, skip_review: bool = False) -> list:
        """Gera comando Paru para build com todas as opções configuráveis"""
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
                   clean_after: bool = False, skip_review: bool = False) -> None:
        """Inicia processo de build com fallback seguro e opções configuráveis"""
        try:
            cmd = BuildManager.get_paru_command(target_path, install, clean_after, skip_review)
            output_callback(f"Iniciando build de {target_path}...")

            # Adiciona informações sobre as opções selecionadas
            options_info = []
            if clean_after:
                options_info.append("limpeza após build ativada")
            if skip_review:
                options_info.append("revisão do PKGBUILD ignorada")
            if options_info:
                output_callback(f"ℹ️ Opções selecionadas: {', '.join(options_info)}")

            # Verifica se estamos em um ambiente Flatpak
            is_flatpak = os.path.exists("/.flatpak-info")

            # Tenta executar com ou sem flatpak-spawn
            try:
                if is_flatpak:
                    # Tenta usar flatpak-spawn
                    try:
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
                    universal_newlines=True,
                    cwd=target_path
                )

                def read_output():
                    for line in process.stdout:
                        GLib.idle_add(output_callback, line.strip())
                    return process.poll() is None

                GLib.idle_add(read_output)

            except Exception as e:
                output_callback(f"⚠️ Falha ao usar flatpak-spawn, tentando execução direta: {str(e)}")
                # Tenta executar diretamente como último recurso
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    cwd=target_path
                )

                def read_output_direct():
                    for line in process.stdout:
                        GLib.idle_add(output_callback, line.strip())
                    return process.poll() is None

                GLib.idle_add(read_output_direct)

        except Exception as e:
            output_callback(f"❌ Erro crítico ao iniciar build: {str(e)}", "error")
            print(f"❌ Erro crítico ao iniciar build: {e}")
