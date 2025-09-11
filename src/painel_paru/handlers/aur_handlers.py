from gi.repository import Gtk
import os
import gettext
_ = gettext.gettext

from .aur_downloader import AurDownloader
from .paru_runner import ParuRunner
from .utils import validate_path

class AurHandlers:
    def __init__(self, window):
        self.window = window
        self.logger = window.logger
        self.terminal_manager = window.terminal_manager

    def on_download_pkgbuild(self, *args, **kwargs):
        """Baixa o PKGBUILD de um pacote do AUR.
        Este método permite ao usuário baixar o PKGBUILD de um pacote específico do AUR.
        """
        if not check_content_path(self.window, self.terminal_manager):
            return

        # Verifica se é um diretório
        if not os.path.isdir(self.window.content_path):
            self.terminal_manager.show_error(_("Caminho selecionado não é um diretório"))
            return

        # Criar diálogo para entrada do nome do pacote
        dialog = Gtk.Dialog(
            title=_("Baixar PKGBUILD do AUR"),
            transient_for=self.window,
            modal=True
        )
        dialog.set_default_size(400, 150)

        # Adicionar botões
        dialog.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Baixar"), Gtk.ResponseType.OK)

        # Container principal
        content_area = dialog.get_content_area()
        content_area.set_orientation(Gtk.Orientation.VERTICAL)
        content_area.set_spacing(10)
        content_area.set_margin_start(10)
        content_area.set_margin_end(10)
        content_area.set_margin_top(10)
        content_area.set_margin_bottom(10)

        # Campo de entrada
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

        label = Gtk.Label(
            label=_("Nome do pacote no AUR:"),
            halign=Gtk.Align.START
        )
        box.append(label)

        entry = Gtk.Entry()
        entry.set_placeholder_text(_("pacote-exemplo"))
        box.append(entry)

        content_area.append(box)
        dialog.present()

        # Conectar sinal de resposta
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.OK:
                package_name = entry.get_text().strip()
                if package_name:
                    self._download_pkgbuild(package_name)
            dialog.destroy()

        dialog.connect("response", on_response)

    def _download_pkgbuild(self, package_name):
        """Baixa o PKGBUILD do pacote especificado"""
        try:
            target_dir = self.window.content_path
            self.terminal_manager.show_progress(_("Baixando PKGBUILD de %s...") % package_name)

            # Obter preferências
            from .preferences_manager import PreferencesManager
            use_ssh = PreferencesManager.get_preferences().get_boolean("aur-ssh")

            # Baixar PKGBUILD
            cmd = AurDownloader.download_pkgbuild(package_name, target_dir, use_ssh)
            ParuRunner.run_command(cmd, self.terminal_manager.append)

        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao baixar PKGBUILD: %s") % error_type
            self.terminal_manager.show_error(error_msg)
            self.logger.error("Error downloading PKGBUILD: %s - %s", error_type, str(e))

    def on_search_pkgbuild(self, search_term, *args, **kwargs):
        """Busca pacotes no AUR.
        Este método permite ao usuário buscar pacotes no AUR usando um termo de busca.
        """
        if not search_term or not search_term.strip():
            self.terminal_manager.show_warning(_("Termo de busca não pode ser vazio"))
            return

        search_term = search_term.strip()
        self.terminal_manager.show_progress(_("Buscando pacotes no AUR: %s...") % search_term)

        try:
            # Executar busca no AUR
            ParuRunner.run_command(["paru", "-Ss", search_term], self.terminal_manager.append)

        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao buscar pacotes: %s") % error_type
            self.terminal_manager.show_error(error_msg)
            self.logger.error("Error searching packages: %s - %s", error_type, str(e))
