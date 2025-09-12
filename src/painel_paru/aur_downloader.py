# aur_downloader.py
import os
import subprocess
import tempfile
import shutil
import gi
import threading
import time
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib
import gettext

_ = gettext.gettext

class AurDownloader:
    """Gerencia download de PKGBUILDs do AUR"""

    def __init__(self, output_callback=None):
        """Inicializa o downloader com callback opcional para saída

        Args:
            output_callback (callable, optional): Função para processar saída do terminal.
                Deve aceitar (message, log_type) onde log_type é 'info', 'error', 'success', 'progress'
        """
        self.output_callback = output_callback
        self.temp_dir = None
        self.active_download = False
        self.download_thread = None

    def _log(self, message, log_type="info"):
        """Registra mensagens no terminal se houver callback

        Args:
            message (str): Mensagem a ser registrada
            log_type (str, optional): Tipo da mensagem. Defaults to "info".
        """
        if self.output_callback:
            self.output_callback(message, log_type)
        else:
            print(f"[AUR] {message}")

    def download_pkgbuild(self, package_name, target_dir=None, use_ssh=False, show_comments=False):
        """Baixa PKGBUILD do AUR para diretório especificado

        Args:
            package_name (str): Nome do pacote a ser baixado
            target_dir (str, optional): Diretório de destino. Defaults to None (temporário).
            use_ssh (bool, optional): Usar SSH para clonar. Defaults to False.
            show_comments (bool, optional): Mostrar comentários. Defaults to False.

        Returns:
            tuple: (bool, str) - Sucesso e caminho do diretório
        """
        self.active_download = True

        try:
            # Cria um diretório temporário se não for especificado
            if not target_dir:
                self.temp_dir = tempfile.mkdtemp(prefix="aur_")
                self._log(_("📁 Diretório temporário criado: ") + self.temp_dir, "info")
                target_dir = self.temp_dir
            else:
                self.temp_dir = None

            # Prepara o comando
            cmd = ["paru", "-G", package_name]
            if use_ssh:
                cmd.append("--ssh")
            if show_comments:
                cmd.append("--comments")

            # Executa o comando
            self._log(_("📥 Baixando PKGBUILD para: ") + package_name, "progress")

            # Executa em thread separada para não bloquear a UI
            self.download_thread = threading.Thread(
                target=self._run_download,
                args=(cmd, target_dir)
            )
            self.download_thread.daemon = True
            self.download_thread.start()

            return True

        except Exception as e:
            self._log(_("❌ Erro ao preparar download: ") + str(e), "error")
            self.active_download = False
            return False

    def _run_download(self, cmd, target_dir):
        """Executa o download em uma thread separada"""
        try:
            # Executa o comando no diretório alvo
            process = subprocess.Popen(
                cmd,
                cwd=target_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Lê a saída em tempo real
            while self.active_download and process.poll() is None:
                # Lê stdout
                stdout = process.stdout.readline()
                if stdout:
                    GLib.idle_add(lambda: self._log(stdout.strip(), "info"))

                # Lê stderr
                stderr = process.stderr.readline()
                if stderr:
                    GLib.idle_add(lambda: self._log(stderr.strip(), "error"))

                # Pequena pausa para não consumir muitos recursos
                time.sleep(0.1)

            # Processa saída restante
            for line in process.stdout:
                GLib.idle_add(lambda: self._log(line.strip(), "info"))
            for line in process.stderr:
                GLib.idle_add(lambda: self._log(line.strip(), "error"))

            # Verifica resultado
            if process.returncode == 0:
                self._log(_("✅ PKGBUILD baixado com sucesso para: ") + target_dir, "success")
                GLib.idle_add(lambda: self._on_download_complete(True, target_dir))
            else:
                self._log(_("❌ Falha ao baixar PKGBUILD. Código de saída: ") + str(process.returncode), "error")
                GLib.idle_add(lambda: self._on_download_complete(False, None))

        except Exception as e:
            self._log(_("❌ Erro durante o download: ") + str(e), "error")
            GLib.idle_add(lambda: self._on_download_complete(False, None))
        finally:
            self.active_download = False

    def cancel_download(self):
        """Cancela o download em andamento"""
        if self.active_download:
            self._log(_("⚠️ Cancelando download em andamento..."), "info")
            self.active_download = False
            if self.download_thread and self.download_thread.is_alive():
                # Não podemos realmente interromper a thread, mas vamos parar de ler a saída
                pass

    def _on_download_complete(self, success, path=None):
        """Callback chamado quando o download é concluído"""
        # Se foi criado um diretório temporário e houve falha, limpa
        if success:
            self._log(_("📦 Conteúdo disponível em: ") + path, "info")
        else:
            if self.temp_dir and os.path.exists(self.temp_dir):
                try:
                    shutil.rmtree(self.temp_dir)
                    self._log(_("🧹 Diretório temporário removido devido à falha"), "info")
                except Exception as e:
                    self._log(_("❌ Erro ao remover diretório temporário: ") + str(e), "error")

        # Notifica qualquer callback registrado
        if hasattr(self, 'completion_callback') and callable(self.completion_callback):
            self.completion_callback(success, path)

    def set_completion_callback(self, callback):
        """Define um callback para ser chamado quando o download for concluído

        Args:
            callback (callable): Função a ser chamada com (success, path)
        """
        self.completion_callback = callback
