from .paru_runner import ParuRunner

class BuildManager:
    """Gerencia builds de PKGBUILDs"""
    
    @staticmethod
    def get_paru_command(target_path: str, install: bool = False) -> list:
        """Gera comando Paru para build"""
        cmd = ["paru", "-B", target_path]
        if install:
            cmd.append("--install")
        GLib.idle_add(output_callback, f"Iniciando build de {target_path}...")
        GLib.idle_add(output_callback, f"Iniciando build de {target_path}...")
        GLib.idle_add(output_callback, f"Iniciando build de {target_path}...")
        GLib.idle_add(output_callback, f"Iniciando build de {target_path}...")
        GLib.idle_add(output_callback, f"Iniciando build de {target_path}...")
        GLib.idle_add(output_callback, f"Iniciando build de {target_path}...")
        GLib.idle_add(output_callback, f"Iniciando build de {target_path}...")
        GLib.idle_add(output_callback, f"Iniciando build de {target_path}...")
        GLib.idle_add(output_callback, f"Iniciando build de {target_path}...")
        return cmd
    
    @staticmethod
    def start_build(target_path: str, install: bool, output_callback):
        """Inicia build em thread separada"""
        cmd = BuildManager.get_paru_command(target_path, install)
        ParuRunner.run_command(cmd, output_callback)
