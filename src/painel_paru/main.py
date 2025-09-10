#!/usr/bin/env python3
import sys
import os
import gi
import subprocess
import importlib.util
import gettext

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw, GLib, Gdk, Pango

# Configurar gettext para internacionalização
# Define o domínio e diretório de traduções
gettext.bindtextdomain('painel_paru', os.path.join(sys.prefix, 'share', 'locale'))
gettext.textdomain('painel_paru')
_ = gettext.gettext

def find_module_dir():
    """Tenta encontrar o diretório onde os módulos estão instalados"""
    print(_("🔍 Procurando diretório do módulo..."))
    bin_dir = os.path.dirname(os.path.abspath(__file__))
    print(_(" - Diretório do executável: %s") % bin_dir)

    # Identifica a versão do Python
    python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"

    # Possíveis locais onde os módulos podem estar
    possible_locations = [
        # Diretório principal de dados (onde os arquivos estão)
        os.path.join(bin_dir, '../share/painel_paru'),
        '/app/share/painel_paru',
        os.path.join(sys.prefix, 'share/painel_paru'),
        # Local de desenvolvimento
        os.path.dirname(bin_dir),
    ]

    for path in possible_locations:
        full_path = os.path.abspath(path)
        print(_(" → Verificando: %s") % full_path)
        # Verifica se o diretório contém o pacote painel_paru
        if os.path.exists(os.path.join(full_path, 'painel_paru', 'main.py')):
            print(_("✅ Módulos encontrados em: %s") % full_path)
            return full_path

    print(_("❌ Nenhum diretório válido encontrado"))
    return None

# Configura o PYTHONPATH
module_dir = find_module_dir()
if module_dir:
    print(_("✅ Adicionado ao PYTHONPATH: %s") % module_dir)
    sys.path.insert(0, module_dir)
else:
    print(_("❌ Erro: Não foi possível encontrar o diretório do módulo"))
    print(_("Diretórios no PYTHONPATH:"))
    for i, path in enumerate(sys.path, 1):
        print(_(" %d. %s") % (i, path))
    # Diagnóstico adicional
    print(_("🔍 Diagnóstico adicional:"))
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(current_dir):
        print(_(" - Diretório atual: %s") % current_dir)
        print(_(" - Arquivos disponíveis:"))
        try:
            for file in os.listdir(current_dir):
                print(_(" * %s") % file)
        except Exception as diag_error:
            print(_(" ❌ Erro ao listar diretório: %s") % type(diag_error).__name__)
    sys.exit(1)

# Importações dos módulos lógicos
try:
    # Primeira tentativa: Import absoluto (ambiente instalado)
    from painel_paru.content_detector import ContentDetector
    from painel_paru.paru_runner import ParuRunner
    from painel_paru.build_manager import BuildManager
    from painel_paru.aur_downloader import AurDownloader
    from painel_paru.terminal_manager import TerminalManager
    print(_("✅ Módulos importados com sucesso (ambiente instalado)"))
except ImportError as e:
    try:
        # Segunda tentativa: Import para ambientes de desenvolvimento
        from content_detector import ContentDetector
        from paru_runner import ParuRunner
        from build_manager import BuildManager
        from aur_downloader import AurDownloader
        from terminal_manager import TerminalManager
        print(_("✅ Módulos importados com sucesso (ambiente de desenvolvimento)"))
    except ImportError as e2:
        print(_("❌ Erro ao importar módulos:"))
        print(_(" - Primeira tentativa (painel_paru.*): %s") % type(e).__name__)
        print(_(" - Segunda tentativa (*): %s") % type(e2).__name__)
        print(_("Diretórios no PYTHONPATH:"))
        for i, path in enumerate(sys.path, 1):
            print(_(" %d. %s") % (i, path))

        # Diagnóstico adicional
        print(_("🔍 Diagnóstico adicional:"))
        if module_dir:
            print(_(" - Diretório do módulo: %s") % module_dir)
            print(_(" - Arquivos disponíveis:"))
            try:
                for file in os.listdir(module_dir):
                    print(_(" * %s") % file)

                # Verifica estrutura do pacote
                painel_paru_dir = os.path.join(module_dir, 'painel_paru')
                if os.path.exists(painel_paru_dir):
                    print(_(" - Diretório painel_paru encontrado: %s") % painel_paru_dir)
                    print(_(" - Arquivos no diretório painel_paru:"))
                    try:
                        for file in os.listdir(painel_paru_dir):
                            print(_(" * %s") % file)
                    except Exception as diag_error:
                        print(_(" ❌ Erro ao listar diretório: %s") % type(diag_error).__name__)
                else:
                    print(_(" - Diretório painel_paru NÃO encontrado em: %s") % module_dir)
            except Exception as diag_error:
                print(_(" ❌ Erro ao listar diretório: %s") % type(diag_error).__name__)

        sys.exit(1)

def main(version):
    """Função principal do aplicativo

    Args:
        version: Versão do aplicativo passada pelo sistema de build
    """
    print(_("Aplicativo iniciado às %s") % GLib.DateTime.new_now_local().format('%H:%M:%S'))
    print(_("Versão: %s") % version)

    # Cria a aplicação
    app = Adw.Application(
        application_id="org.gnome.painel_paru",
        flags=Gio.ApplicationFlags.FLAGS_NONE
    )

    def on_activate(app):
        # Cria a janela principal
        try:
            from painel_paru.window import PainelParuWindow
        except ImportError:
            try:
                from window import PainelParuWindow
            except ImportError as e:
                error_msg = _("❌ Erro crítico ao importar PainelParuWindow")
                print(error_msg)
                print(_("Tipo do erro: %s") % type(e).__name__)

                # Mostra informações adicionais para diagnóstico (somente no log técnico)
                print("\nTechnical details (for debugging):")
                print(f"Error details: {str(e)}")
                print("\nEstrutura do diretório painel_paru:")
                try:
                    if module_dir:
                        painel_paru_path = os.path.join(module_dir, 'painel_paru')
                        if os.path.exists(painel_paru_path):
                            for file in os.listdir(painel_paru_path):
                                print(f" - {file}")
                        else:
                            print(f"O diretório {painel_paru_path} não existe")
                    else:
                        print("module_dir não está definido")
                except Exception as diag_error:
                    print(f"Erro ao verificar estrutura do diretório: {diag_error}")
                sys.exit(1)

        win = PainelParuWindow(application=app)
        win.present()

    app.connect("activate", on_activate)
    return app.run(None)

if __name__ == "__main__":
    # Executa o aplicativo com versão padrão para execução direta
    print(_("🚀 Iniciando aplicativo..."))
    sys.exit(main("0.1.0"))