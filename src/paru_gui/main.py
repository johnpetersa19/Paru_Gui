# main.py
#
# Copyright 2025 Unknown
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import os
import gi
from gettext import gettext as _

# --- CORRECTION: gi.require_version MUST COME BEFORE IMPORTS ---
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
# --- END OF CORRECTION ---

from gi.repository import Gtk, Gio, Adw, Gdk


def load_resources():
    """Carrega recursos GTK explicitamente ANTES de qualquer importação"""
    print("🔍 Procurando recursos...")

    # Determinar o caminho dos recursos
    if hasattr(sys, 'frozen'):
        # Executável congelado (PyInstaller, etc.)
        resource_path = os.path.join(sys._MEIPASS, 'paru_gui.gresource')
    else:
        # Desenvolvimento ou instalação padrão
        possible_paths = [
            '/usr/local/share/paru_gui/paru_gui.gresource',
            '/usr/share/paru_gui/paru_gui.gresource',
            '/app/share/paru_gui/paru_gui.gresource',  # Flatpak
            os.path.join(os.path.dirname(__file__), '..', 'paru_gui.gresource'),
            'paru_gui.gresource',
            './build/src/paru_gui.gresource',
            './paru_gui.gresource'
        ]
        resource_path = None
        for path in possible_paths:
            if os.path.exists(path):
                resource_path = path
                break

    if resource_path and os.path.exists(resource_path):
        try:
            resource = Gio.Resource.load(resource_path)
            Gio.resources_register(resource)
            print(f"✅ Recursos carregados de: {resource_path}")
            return True
        except Exception as e:
            print(f"❌ Erro ao carregar recursos: {e}")
            return False
    else:
        print("⚠️  Arquivo de recursos não encontrado. Paths testados:")
        for path in possible_paths:
            exists = "✓" if os.path.exists(path) else "✗"
            print(f"  {exists} {path}")
        return False


def debug_resources():
    """Verificar recursos disponíveis"""
    print("\n🔍 === DEBUG DE RECURSOS ===")

    try:
        # Listar recursos no prefixo principal
        resource_path = "/org/gnome/paru-gui"
        children = Gio.resources_enumerate_children(resource_path, Gio.ResourceLookupFlags.NONE)
        print(f"📁 Recursos encontrados em {resource_path}:")
        for child in children:
            print(f"  ✓ {child}")

        # Verificar especificamente o arquivo problemático
        ui_path = "/org/gnome/paru-gui/ui/screens/pkgbuild_review.ui"
        try:
            data = Gio.resources_lookup_data(ui_path, Gio.ResourceLookupFlags.NONE)
            print(f"✅ {ui_path} encontrado ({len(data.get_data())} bytes)")
        except Exception as e:
            print(f"❌ Erro ao acessar {ui_path}: {e}")

        # Tentar listar subdiretórios
        ui_screens_path = "/org/gnome/paru-gui/ui/screens"
        try:
            screens = Gio.resources_enumerate_children(ui_screens_path, Gio.ResourceLookupFlags.NONE)
            print(f"📁 Arquivos em {ui_screens_path}:")
            for screen in screens:
                print(f"  ✓ {screen}")
        except Exception as e:
            print(f"❌ Erro ao listar {ui_screens_path}: {e}")

        # Tentar listar componentes UI
        ui_components_path = "/org/gnome/paru-gui/ui/components"
        try:
            components = Gio.resources_enumerate_children(ui_components_path, Gio.ResourceLookupFlags.NONE)
            print(f"📁 Arquivos em {ui_components_path}:")
            for component in components:
                print(f"  ✓ {component}")
        except Exception as e:
            print(f"❌ Erro ao listar {ui_components_path}: {e}")

    except Exception as e:
        print(f"❌ Erro geral ao enumerar recursos: {e}")

    print("🔍 === FIM DEBUG DE RECURSOS ===\n")


# CRÍTICO: Carregar recursos ANTES de importar paru_gui.window
print("🚀 Iniciando aplicativo Paru GUI...")
resources_loaded = load_resources()
debug_resources()

if not resources_loaded:
    print("❌ ERRO CRÍTICO: Recursos não puderam ser carregados!")
    print("   Verifique se o build foi feito corretamente com:")
    print("   rm -rf build && meson setup build && meson compile -C build")
    sys.exit(1)

# AGORA sim importar os módulos que dependem dos recursos
try:
    from .window import ParuGuiWindow
    print("✅ Módulos importados com sucesso")
except Exception as e:
    print(f"❌ Erro ao importar módulos: {e}")
    sys.exit(1)


class ParuGuiApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(application_id='org.gnome.paru-gui',
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
                         resource_base_path='/org/gnome/paru-gui')
        self.create_action('quit', lambda *_: self.quit(), ['<primary>q'])
        self.create_action('about', self.on_about_action)
        self.create_action('preferences', self.on_preferences_action)
        # These actions are defined in window.ui's primary_menu
        # and will be handled by methods in ParuGuiWindow
        # The accels are defined in ParuGuiWindow or help-overlay.ui
        self.create_action('system', lambda *_: None)
        self.create_action('statistics', lambda *_: None)
        self.create_action('arch-news', lambda *_: None)
        self.create_action('clean-cache', lambda *_: None)
        self.create_action('update-system', lambda *_: None)
        self.create_action('initial-tour', lambda *_: None)
        self.create_action('show-upstream-updates', lambda *_: None)
        self.create_action('refresh-upstream-updates', lambda *_: None) # New action
        self.create_action('action-history', lambda *_: None)
        self.create_action('shortcuts', lambda *_: None) # Handled by TourGuide via help_button
        self.create_action('hide-advanced', lambda *_: None) # Toggle simplified mode
        self.create_action('check-devel', lambda *_: None)
        self.create_action('install-debug', lambda *_: None)
        self.create_action('show-warnings', lambda *_: None)
        self.create_action('show-terminal', lambda *_: None)
        self.create_action('review-pkgbuild', lambda *_: None)
        self.create_action('go-home', lambda *_: None) # From help-overlay.ui
        self.create_action('go-back', lambda *_: None) # From help-overlay.ui
        self.create_action('go-forward', lambda *_: None) # From help-overlay.ui
        self.create_action('search-packages', lambda *_: None) # From help-overlay.ui
        self.create_action('select-file', lambda *_: None) # From help-overlay.ui
        self.create_action('select-folder', lambda *_: None) # From help-overlay.ui
        self.create_action('refresh-view', lambda *_: None) # From help-overlay.ui
        self.create_action('download-sources', lambda *_: None) # From help-overlay.ui
        self.create_action('build-package', lambda *_: None) # From help-overlay.ui
        self.create_action('edit-pkgbuild', lambda *_: None) # From help-overlay.ui
        self.create_action('view-analysis', lambda *_: None) # From help-overlay.ui
        self.create_action('install-package', lambda *_: None) # From help-overlay.ui
        self.create_action('verify-signature', lambda *_: None) # From help-overlay.ui
        self.create_action('apply-patch', lambda *_: None) # From help-overlay.ui
        self.create_action('view-diff', lambda *_: None) # From help-overlay.ui
        self.create_action('execute-custom-command', lambda *_: None) # From help-overlay.ui
        self.create_action('dry-run', lambda *_: None) # From help-overlay.ui
        self.create_action('consult-docs', lambda *_: None) # From help-overlay.ui
        self.create_action('show-help-overlay', lambda *_: None) # From help-overlay.ui

    def do_startup(self):
        """Called once when the application is started."""
        Gtk.Application.do_startup(self)
        self.load_css() # Load CSS early during startup

    def do_activate(self):
        """Called when the application is activated.

        Raises the application's main window, creating it if necessary.
        """
        win = self.props.active_window
        if not win:
            # The ParuGuiWindow class now fully manages its UI loading from .ui files.
            win = ParuGuiWindow(application=self)
        win.present()
        # Optionally, start the initial tour after the window is presented.
        # This is now handled by a signal connection in ParuGuiWindow's setup_main_interface
        # or directly in do_activate if preferred.
        # win.tour_guide.show_initial_tour()


    def load_css(self):
        """Load the CSS styles for the application"""
        css_provider = Gtk.CssProvider()
        try:
            # Loads the main style file
            css_provider.load_from_resource("/org/gnome/paru-gui/ui/style.css")
            print("✅ CSS principal carregado com sucesso")
        except Exception as e:
            print(f"❌ Erro ao carregar CSS principal: {e}")

        try:
            # Loads the specific style file for PKGBUILD review,
            # assuming it's part of the global application theme.
            css_provider.load_from_resource("/org/gnome/paru-gui/ui/screens/pkgbuild-review.css")
            print("✅ CSS do PKGBUILD review carregado com sucesso")
        except Exception as e:
            print(f"❌ Erro ao carregar CSS do PKGBUILD review: {e}")

        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_about_action(self, *args):
        """Callback for the app.about action."""
        about = Adw.AboutDialog(application_name='Paru GUI',
                                application_icon='org.gnome.paru-gui',
                                developer_name='Paru GUI Team',
                                version='2.5',
                                developers=['Paru GUI Developers'],
                                copyright='© 2025 Paru GUI Team')
        # Translators: Replace "translator-credits" with your name/username, and optionally an email or URL.
        about.set_translator_credits(_('translator-credits'))
        about.present(self.props.active_window)

    def on_preferences_action(self, *args):
        """Callback for the app.preferences action."""
        print('app.preferences action activated from main.py')
        win = self.props.active_window
        if win and hasattr(win, 'on_preferences_action'):
            win.on_preferences_action() # Delegate to the window's method to show preferences dialog


    def create_action(self, name, callback, shortcuts=None):
        """Add an application action.

        Args:
            name: the name of the action
            callback: the function to be called when the action is
              activated
            shortcuts: an optional list of accelerators
        """
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)


def main(version):
    """The application's entry point."""
    app = ParuGuiApplication()
    return app.run(sys.argv)

if __name__ == '__main__':
    main('2.7.0')
