# window_preferences.py
from gi.repository import Gtk, Adw, Gio
import gettext

_ = gettext.gettext

class WindowPreferences:
    """Mixin para gerenciar funcionalidades de preferências na janela principal"""

    def setup_preferences_actions(self):
        """Configura as ações relacionadas às preferências"""
        # Ação de preferências
        preferences_action = Gio.SimpleAction(name="show-preferences")
        preferences_action.connect("activate", self.on_show_preferences)
        self.add_action(preferences_action)

    def on_show_preferences(self, action, parameter):
        """Mostra janela de preferências"""
        from .preferences import PreferencesManager
        PreferencesManager(self).show_preferences(self)

    def on_show_help(self, action, parameter):
        """Mostra overlay de ajuda"""
        builder = Gtk.Builder.new_from_resource("/org/gnome/painel_paru/gtk/help-overlay.ui")
        help_overlay = builder.get_object("help_overlay")
        help_overlay.set_transient_for(self)
        help_overlay.present()

    def on_show_about(self, action, parameter):
        """Mostra janela 'Sobre'"""
        about = Adw.AboutWindow(
            transient_for=self,
            application_name=_("Painel Paru"),
            application_icon="org.gnome.painel_paru",
            developer_name=_("Equipe Painel Paru"),
            version="0.1.0",
            developers=[
                _("Seu Nome <seu@email.com>"),
                _("Outro Contribuidor <contribuidor@email.com>")
            ],
            designers=[
                _("Designer de UI <designer@email.com>")
            ],
            documenters=[
                _("Documentador <doc@email.com>")
            ],
            copyright=_("© 2023 Painel Paru"),
            website="https://github.com/paru-gui",
            issue_url="https://github.com/paru-gui/issues",
            license_type=Gtk.License.GPL_3_0
        )

        # Créditos de tradução
        about.set_translator_credits(_("translator-credits"))

        # Links adicionais
        about.add_link(_("Documentação"), "https://github.com/paru-gui/wiki")
        about.add_link(_("Doações"), "https://github.com/sponsors/paru-gui")

        # Apresenta a janela
        about.present()
