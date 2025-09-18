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
import gi
from gettext import gettext as _

# --- CORRECTION: gi.require_version MUST COME BEFORE IMPORTS ---
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
# --- END OF CORRECTION ---

from gi.repository import Gtk, Gio, Adw, Gdk
from .window import ParuGuiWindow


class ParuGuiApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(application_id='org.gnome.paru-gui',
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
                         resource_base_path='/org/gnome/paru-gui')
        self.create_action('quit', lambda *_: self.quit(), ['<primary>q'])
        self.create_action('about', self.on_about_action)
        self.create_action('preferences', self.on_preferences_action)
        # TODO: Add actions for other menu items from src/window.ui primary_menu here if not handled elsewhere
        # Example: self.create_action('system', self.on_system_action)

    def do_activate(self):
        """Called when the application is activated.

        Loads CSS styles and raises the application's main window,
        creating it if necessary.
        """
        self.load_css()
        win = self.props.active_window
        if not win:
            # Note: The ParuGuiWindow class currently constructs its UI programmatically in Python.
            # If a Gtk.Builder based approach loading window.ui were to be used,
            # this instantiation might need to pass the builder, or the window class itself
            # would handle loading its UI from the .ui file resource.
            win = ParuGuiWindow(application=self)
        win.present()

    def load_css(self):
        """Load the CSS styles for the application"""
        css_provider = Gtk.CssProvider()
        # Loads the main style file
        css_provider.load_from_resource("/org/gnome/paru-gui/ui/style.css")
        # Loads the specific style file for PKGBUILD review,
        # assuming it's part of the global application theme.
        css_provider.load_from_resource("/org/gnome/paru-gui/ui/screens/pkgbuild-review.css")
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

    def on_preferences_action(self, widget, _):
        """Callback for the app.preferences action."""
        print('app.preferences action activated')
        # TODO: Instantiate and show the preferences dialog from src/window.ui (preferences_dialog)
        # Example:
        # builder = Gtk.Builder()
        # builder.add_from_resource('/org/gnome/paru-gui/window.ui') # Assumes preferences_dialog is in window.ui
        # prefs_dialog = builder.get_object('preferences_dialog')
        # prefs_dialog.set_transient_for(self.props.active_window)
        # prefs_dialog.present()


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
