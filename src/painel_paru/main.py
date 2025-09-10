#!/usr/bin/env python3
import sys
import os
import gi
import subprocess
import importlib.util

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw, GLib, Gdk

# Importações dos módulos lógicos
try:
    from .content_detector import ContentDetector
    from .paru_runner import ParuRunner
    from .build_manager import BuildManager
    from .aur_downloader import AurDownloader
    from .terminal import TerminalView
    print("✅ Módulos importados com sucesso")
except ImportError as e:
    print(f"❌ Erro ao importar módulos: {str(e)}")
    print("Diretórios no PYTHONPATH:")
    for path in sys.path:
        print(f"  - {path}")

    # Tenta diagnosticar o problema
    module_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(module_dir):
        print("Arquivos disponíveis no diretório do módulo:")
        for file in os.listdir(module_dir):
            print(f"  - {file}")
    sys.exit(1)

def main(version):
    """Função principal do aplicativo"""
    print(f"Aplicativo iniciado às {GLib.DateTime.new_now_local().format('%H:%M:%S')}")

    # Cria a aplicação
    app = Adw.Application(
        application_id="org.gnome.painel_paru",
        flags=Gio.ApplicationFlags.FLAGS_NONE
    )

    def on_activate(app):
        # Cria a janela principal
        from .window import PainelParuWindow
        win = PainelParuWindow(application=app)
        win.present()

    app.connect("activate", on_activate)
    return app.run(None)
