import sys
import os
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw

# CORREÇÃO: Múltiplas estratégias para importar ParuGUIWindow
# Remove a importação relativa problemática: from ..window import ParuGUIWindow
try:
    # Estratégia 1: Importação absoluta assumindo estrutura correta de pacotes
    from paru_gui.window import ParuGUIWindow
except ImportError:
    try:
        # Estratégia 2: Adiciona o diretório raiz do projeto ao sys.path
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from window import ParuGUIWindow
    except ImportError:
        # Estratégia 3: Fallback final usando importlib
        current_dir = os.path.dirname(__file__)
        window_path = os.path.join(current_dir, '..', '..', 'window.py')
        if os.path.exists(window_path):
            import importlib.util
            spec = importlib.util.spec_from_file_location("window", window_path)
            window_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(window_module)
            ParuGUIWindow = window_module.ParuGUIWindow
        else:
            raise ImportError("Não foi possível localizar o módulo window.py")


class ParuGUIApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="org.gnome.paru-gui",
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        self.window = None

    def do_activate(self):
        self.window = ParuGUIWindow(application=self)
        self.window.present()


def main():
    app = ParuGUIApplication()
    return app.run(sys.argv)

