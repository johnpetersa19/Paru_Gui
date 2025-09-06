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
    # Diretório base do executável
    bin_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"  - Diretório do executável: {bin_dir}")
    
    # Identifica a versão do Python
    python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    print(f"  - Versão do Python detectada: {python_version}")
    
    # Possíveis locais onde os módulos podem estar
    possible_locations = [
        # Dentro do Flatpak (com ID correto)
        os.path.join(bin_dir, '../share/painel_paru/painel_paru'),
        os.path.join(bin_dir, '../lib/python3.12/site-packages/painel_paru'),
        # Local de instalação padrão
        os.path.join(sys.prefix, 'share/painel_paru/painel_paru'),
        os.path.join(sys.prefix, 'lib', python_version, 'site-packages', 'painel_paru'),
        # Local de desenvolvimento
        os.path.join(os.path.dirname(bin_dir), 'painel_paru'),
        os.path.join(os.path.dirname(bin_dir), 'src'),
        os.path.dirname(bin_dir),
    ]
    
    # Verifica qual local existe
    for location in possible_locations:
        normalized = os.path.normpath(location)
        print(f"  - Verificando: {normalized}")
        if os.path.exists(normalized):
            print(f"✅ Diretório do módulo encontrado: {normalized}")
            return normalized
    
    # Se nada for encontrado, retorna None
    print("❌ Nenhum diretório do módulo encontrado")
    return None

def find_gresource():
    """Tenta encontrar o arquivo GResource"""
    print("🔍 Procurando arquivo GResource...")
    # Diretório base do executável
    bin_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Possíveis nomes para o arquivo GResource
    resource_names = [
        "org.gnome.painel_paru.gresource",  # Nome padrão Flatpak
        "painel_paru.gresource",
        "painel_paru-0.gresource",  # Nome com sufixo numérico
    ]
    
    # Possíveis locais onde o GResource pode estar
    possible_paths = [
        # Dentro do Flatpak (local padrão GLib)
        "/app/share/glib-2.0/resources",
        # Locais de instalação comuns
        "/app/share/painel_paru",
        "/app/share/org.gnome.painel_paru",
        # Dentro do Flatpak (com ID correto)
        os.path.join(bin_dir, '../share/painel_paru'),
        os.path.join(bin_dir, '../share/org.gnome.painel_paru'),
        # Local de desenvolvimento
        os.path.join(os.path.dirname(bin_dir), 'build', 'meson-private'),
    ]
    
    # Testa todas as combinações de nome e caminho
    for path in possible_paths:
        for name in resource_names:
            full_path = os.path.join(path, name)
            print(f"  - Verificando: {full_path}")
            if os.path.exists(full_path):
                print(f"✅ GResource encontrado em: {full_path}")
                return full_path
    
    # Se nada for encontrado
    print("❌ Nenhum arquivo GResource encontrado")
    return None

def load_gresource():
    """Carrega o arquivo GResource"""
    path = find_gresource()
    if not path:
        print("❌ Erro: Não foi possível encontrar o arquivo .gresource")
        return False
    
    try:
        resource = Gio.Resource.load(path)
        resource._register()
        print(f"✅ Recursos carregados com sucesso de {path}")
        return True
    except Exception as e:
        print(f"❌ Falha ao carregar {path}: {str(e)}")
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
    # IMPORTAÇÃO CORRETA: Usando o nome do pacote 'painel_paru'
    from painel_paru import main
    print("✅ Módulos importados com sucesso")
    
    # Verifica se a função main existe
    if hasattr(main, 'main') and callable(main.main):
        app_main = main.main
        print("✅ Função main importada com sucesso")
    else:
        raise ImportError("main não é uma função callable")
except ImportError as e:
    print(f"❌ Erro ao importar módulos: {str(e)}")
    print("Diretórios no PYTHONPATH:")
    for path in sys.path:
        print(f"  - {path}")
    
    # Tenta diagnosticar o problema
    if module_dir and os.path.exists(module_dir):
        print("Arquivos disponíveis no diretório do módulo:")
        for file in os.listdir(module_dir):
            print(f"  - {file}")
    sys.exit(1)
except Exception as e2:
    print(f"❌ Erro ao importar funções: {str(e2)}")
    sys.exit(1)

# Executa o aplicativo
print("🚀 Iniciando aplicativo...")
sys.exit(app_main("0.1.0"))
