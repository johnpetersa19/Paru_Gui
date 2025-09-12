"""Módulo principal do Painel Paru

Este módulo configura os imports para a arquitetura modularizada do aplicativo.
Durante o processo de refatoração, ele permite que os novos módulos sejam
importados corretamente sem quebrar a aplicação.
"""

# Importações dos novos módulos desmembrados
try:
    from .window_core import *
    from .window_ui import *
    from .window_content import *
    from .window_build import *
    from .window_aur import *
    from .window_preferences import *
    from .window_conflicts import *
    from .window_signatures import *
    from .window_notifications import *
    from .window_patches import *
except ImportError:
    # Durante a migração, os arquivos podem estar vazios ou incompletos
    # Este bloco permite que a aplicação continue funcionando enquanto
    # realizamos a refatoração gradual dos arquivos
    pass
