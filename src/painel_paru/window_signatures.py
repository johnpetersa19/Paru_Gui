# window_signatures.py
from gi.repository import Gtk, Gio
import gettext
import shutil
import subprocess
from pathlib import Path

_ = gettext.gettext

class WindowSignatures:
    """Gerencia verificação de assinaturas e integridade dos pacotes"""

    def __init__(self):
        """Inicializa os componentes relacionados a assinaturas"""
        pass

    def on_verify_signatures(self, button):
        """Verifica assinaturas e integridade dos pacotes"""
        if not hasattr(self, 'content_path') or not self.content_path:
            self.terminal.append(_("❌ Nenhum diretório selecionado."), "error")
            return

        self.terminal.append(_("🔍 Verificando assinaturas..."), "progress")

        # Verifica se o pacman-key está disponível
        if shutil.which("pacman-key") is None:
            self.terminal.append(_("❌ O comando pacman-key não está disponível. Instale o pacote pacman."), "error")
            return

        # Verifica cada pacote na pasta
        packages = list(Path(self.content_path).glob("*.pkg.tar.zst"))
        if not packages:
            self.terminal.append(_("⚠️ Nenhum pacote encontrado para verificar"), "info")
            return

        # Verifica se há arquivos de assinatura
        sig_files = list(Path(self.content_path).glob("*.pkg.tar.zst.sig"))
        if sig_files:
            for sig in sig_files:
                # Encontra o pacote correspondente
                pkg_name = str(sig).replace('.sig', '')
                pkg = Path(pkg_name)
                if pkg.exists():
                    self.terminal.append(_("Verificando assinatura: ") + sig.name, "info")
                    # Comando correto para verificar a assinatura com pacman-key
                    try:
                        result = subprocess.run(["pacman-key", "--verify", str(sig)],
                                              capture_output=True, text=True)
                        if result.returncode == 0:
                            self.terminal.append(_("✅ Assinatura válida para: ") + sig.name, "success")
                        else:
                            self.terminal.append(_("❌ Assinatura inválida para: ") + sig.name + "\n" + result.stderr, "error")
                    except Exception as e:
                        self.terminal.append(_("❌ Erro ao verificar assinatura: ") + str(e), "error")
                        print(f"❌ Erro ao verificar assinatura: {e}")
                else:
                    self.terminal.append(_("⚠️ Pacote correspondente não encontrado para ") + sig.name, "info")
        else:
            self.terminal.append(_("⚠️ Nenhum arquivo de assinatura (.sig) encontrado"), "info")

        # Verifica a integridade dos pacotes instalados (se já estiverem instalados)
        for pkg in packages:
            # Extrai o nome do pacote do arquivo
            pkg_name = pkg.name.split('-')[0]
            self.terminal.append(_("Verificando integridade: ") + pkg_name, "info")
            try:
                result = subprocess.run(["pacman", "-Qk", pkg_name],
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    self.terminal.append(_("✅ Pacote ") + pkg_name + _(" está intacto"), "success")
                else:
                    self.terminal.append(_("❌ Problemas com o pacote ") + pkg_name + ":\n" + result.stderr, "error")
            except Exception as e:
                self.terminal.append(_("❌ Erro ao verificar integridade: ") + str(e), "error")
                print(f"❌ Erro ao verificar integridade: {e}")
