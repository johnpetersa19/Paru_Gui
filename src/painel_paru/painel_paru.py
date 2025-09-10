#!/usr/bin/env python3
import sys
import os
import gi
import subprocess
import importlib.util
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw, GLib, Gdk

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
        os.path.dirname(bin_dir),  # Corrigido: deve ser o diretório pai, não 'src'
    ]

    for path in possible_locations:
        full_path = os.path.abspath(path)
        print(f" → Verificando: {full_path}")
        # Verifica se o diretório contém o pacote painel_paru
        if os.path.exists(os.path.join(full_path, 'painel_paru', 'main.py')):
            print(f"✅ Módulos encontrados em: {full_path}")
            return full_path

    print("❌ Nenhum diretório válido encontrado")
    return None

# Configura o PYTHONPATH
module_dir = find_module_dir()
if module_dir:
    print(f"✅ Adicionado ao PYTHONPATH: {module_dir}")
    sys.path.insert(0, module_dir)
else:
    print("❌ Erro: Não foi possível encontrar o diretório do módulo")
    sys.exit(1)

# Importações dos módulos
try:
    # Primeira tentativa: Import absoluto correto (para ambiente instalado)
    from painel_paru.main import main as app_main
    print("✅ Módulo 'painel_paru.main' importado com sucesso (ambiente instalado)")
except ImportError as e:
    try:
        # Segunda tentativa: Import para ambientes de desenvolvimento
        # CORREÇÃO: Deve importar de 'painel_paru.main', não apenas 'main'
        # O diretório adicionado ao sys.path já contém o pacote painel_paru
        from painel_paru.main import main as app_main
        print("✅ Módulo 'painel_paru.main' importado com sucesso (ambiente de desenvolvimento)")
    except ImportError as e2:
        print(f"❌ Erro ao importar módulos:")
        print(f" - Primeira tentativa (painel_paru.main): {str(e)}")
        print(f" - Segunda tentativa (painel_paru.main): {str(e2)}")
        print("\nDiretórios no PYTHONPATH:")
        for i, path in enumerate(sys.path, 1):
            print(f" {i}. {path}")

        # Tenta diagnosticar o problema
        print("\n🔍 Diagnóstico adicional:")
        if module_dir:
            print(f" - Diretório do módulo: {module_dir}")
            print(" - Arquivos disponíveis:")
            try:
                for file in os.listdir(module_dir):
                    print(f"   * {file}")
            except Exception as diag_error:
                print(f"   ❌ Erro ao listar diretório: {diag_error}")

        # Verifica estrutura do pacote
        if module_dir:
            painel_paru_dir = os.path.join(module_dir, 'painel_paru')
            if os.path.exists(painel_paru_dir):
                print(f"\n - Diretório painel_paru encontrado: {painel_paru_dir}")
                print(" - Arquivos no diretório painel_paru:")
                try:
                    for file in os.listdir(painel_paru_dir):
                        print(f"   * {file}")
                except Exception as diag_error:
                    print(f"   ❌ Erro ao listar diretório: {diag_error}")
            else:
                print(f"\n - Diretório painel_paru NÃO encontrado em: {module_dir}")

        sys.exit(1)

# Executa o aplicativo
print("🚀 Iniciando aplicativo...")
sys.exit(app_main("0.1.0"))
