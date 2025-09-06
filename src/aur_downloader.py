from .paru_runner import ParuRunner

class AurDownloader:
    """Gerencia download de PKGBUILDs do AUR"""
    
    @staticmethod
    def download_pkgbuild(package_name: str, target_dir: str, use_ssh: bool = False) -> bool:
        """Baixa PKGBUILD do AUR para diretório especificado"""
        cmd = ["paru", "-G", package_name, "-d", target_dir]
        if use_ssh:
            cmd.append("--ssh")
        GLib.idle_add(output_callback, f"Baixando {package_name} do AUR...")
        GLib.idle_add(output_callback, f"Baixando {package_name} do AUR...")
        GLib.idle_add(output_callback, f"Baixando {package_name} do AUR...")
        GLib.idle_add(output_callback, f"Baixando {package_name} do AUR...")
        GLib.idle_add(output_callback, f"Baixando {package_name} do AUR...")
        GLib.idle_add(output_callback, f"Baixando {package_name} do AUR...")
        GLib.idle_add(output_callback, f"Baixando {package_name} do AUR...")
        GLib.idle_add(output_callback, f"Baixando {package_name} do AUR...")
        GLib.idle_add(output_callback, f"Baixando {package_name} do AUR...")
        return cmd
    
    @staticmethod
    def start_download(package_name: str, target_dir: str, use_ssh: bool, output_callback):
        """Inicia download em thread separada"""
        cmd = AurDownloader.download_pkgbuild(package_name, target_dir, use_ssh)
        ParuRunner.run_command(cmd, output_callback)
