#!/usr/bin/env python3
import sys
import os
import gi
import subprocess
import importlib.util
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw, GLib, Gdk

# CONFIGURAÇÃO CRÍTICA: SEU PREFIXO REAL
RESOURCE_PREFIX = "/org/gnome/painel_paru"

def find_module_dir():
    """Tenta encontrar o diretório onde os módulos estão instalados"""
    print("🔍 Procurando diretório do módulo...")
    bin_dir = os.path.dirname(os.path.abspath(__file__))
    print(f" - Diretório do executável: {bin_dir}")

    # Identifica a versão do Python
    python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"

    # Possíveis locais onde os módulos podem estar
    possible_locations = [
        # Diretório principal de dados (onde os arquivos estão)
        os.path.join(bin_dir, '../share/painel_paru'),
        '/app/share/painel_paru',
        os.path.join(sys.prefix, 'share/painel_paru'),
        # Local de desenvolvimento
        os.path.join(os.path.dirname(bin_dir), 'src'),
    ]

    for path in possible_locations:
        full_path = os.path.abspath(path)
        print(f" → Verificando: {full_path}")
        if os.path.exists(full_path) and os.path.isfile(os.path.join(full_path, 'main.py')):
            print(f"✅ Módulos encontrados em: {full_path}")
            return full_path

    print("❌ Nenhum diretório válido encontrado")
    return None

def load_gresource():
    """Carrega o recurso GResource"""
    try:
        resource_path = RESOURCE_PREFIX + ".gresource"
        print(f"🔍 Carregando recursos de: {resource_path}")
        resource = Gio.Resource.load(resource_path)
        resource._register()
        print("✅ Recursos carregados com sucesso")
        return True
    except Exception as e:
        print(f"❌ Falha ao carregar recursos: {str(e)}")
        return False

# Configura o PYTHONPATH
module_dir = find_module_dir()
if module_dir:
    print(f"✅ Adicionado ao PYTHONPATH: {module_dir}")
    sys.path.insert(0, module_dir)
else:
    print("❌ Erro: Não foi possível encontrar o diretório do módulo")
    sys.exit(1)

# Carrega os recursos
if not load_gresource():
    print("❌ Erro crítico: Não foi possível carregar os recursos")
    sys.exit(1)

# Importações dos módulos
try:
    from main import main as app_main
    print("✅ Módulo 'main' importado com sucesso")
except ImportError as e:
    print(f"❌ Erro ao importar módulos: {str(e)}")
    print("Diretórios no PYTHONPATH:")
    for path in sys.path:
        print(f" - {path}")
    sys.exit(1)

# Executa o aplicativo
print("🚀 Iniciando aplicativo...")
sys.exit(app_main("0.1.0"))
