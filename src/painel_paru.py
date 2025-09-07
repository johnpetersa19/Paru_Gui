#!/usr/bin/env python3
import sys
import os
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw

# Caminho do módulo
module_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'painel_paru')
if module_dir not in sys.path:
    sys.path.insert(0, module_dir)

# Importa main
try:
    from main import main as app_main
    print("✅ Módulo 'main' importado com sucesso")
except ImportError as e:
    print(f"❌ Erro ao importar módulos: {str(e)}")
    sys.exit(1)

# Executa
app_main("0.1.0")
