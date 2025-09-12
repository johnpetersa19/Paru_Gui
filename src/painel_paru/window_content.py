# window_content.py
from gi.repository import Gtk
from pathlib import Path
from .content_detector import ContentDetector
import gettext

_ = gettext.gettext

class WindowContent:
    """Classe mixin para gerenciamento de conteúdo e navegação no PainelParuWindow.

    Esta classe lida com:
    - Navegação entre diretórios
    - Detecção de conteúdo
    - Carregamento de telas específicas baseadas no conteúdo
    - Gerenciamento do histórico de navegação
    """

    def __init__(self):
        """Inicializa os componentes de gerenciamento de conteúdo.

        Deve ser chamado durante a inicialização da janela principal.
        """
        # Histórico de navegação
        self.previous_paths = []
        self.current_path = None
        self.content_path = None
        self.current_state = None

        # Configuração inicial dos botões de navegação
        self.back_button = None

    def setup_content_navigation(self):
        """Configura os elementos de navegação de conteúdo."""
        # Configura o botão Voltar
        self.back_button = Gtk.Button(
            icon_name="go-previous-symbolic",
            tooltip_text=_("Voltar")
        )
        self.back_button.set_sensitive(False)
        self.back_button.connect("clicked", self.on_back_button_clicked)
        self.header_bar.pack_start(self.back_button)

        # Configura os botões de seleção
        select_file_button = Gtk.Button(
            icon_name="document-open-symbolic",
            tooltip_text=_("Selecionar arquivo")
        )
        select_file_button.connect("clicked", self.on_select_file)
        self.header_bar.pack_start(select_file_button)

        select_folder_button = Gtk.Button(
            icon_name="folder-symbolic",
            tooltip_text=_("Selecionar pasta")
        )
        select_folder_button.connect("clicked", self.on_select_folder)
        self.header_bar.pack_start(select_folder_button)

    def on_back_button_clicked(self, button):
        """Manipula o clique no botão de voltar.

        Retorna para o diretório anterior no histórico de navegação.

        Args:
            button (Gtk.Button): O botão que foi clicado.
        """
        if self.previous_paths:
            # Salva o caminho atual como sendo o próximo no histórico
            next_path = self.content_path
            self.content_path = self.previous_paths.pop()

            # Atualiza o botão Voltar
            self.back_button.set_sensitive(bool(self.previous_paths))

            # Carrega o conteúdo do caminho anterior
            self.status_label.set_label(_("Analisando: ") + self.content_path)
            state = ContentDetector.detect_content(self.content_path)
            self._load_content_screen(state)

            # Atualiza o estado dos botões
            self.open_folder_button.set_sensitive(True)

    def on_select_file(self, button):
        """Handler para seleção de arquivo único."""
        self._show_file_chooser(Gtk.FileChooserAction.OPEN)

    def on_select_folder(self, button):
        """Handler para seleção de pasta."""
        self._show_file_chooser(Gtk.FileChooserAction.SELECT_FOLDER)

    def _show_file_chooser(self, action):
        """Mostra diálogo de seleção de arquivo/pasta.

        Args:
            action (Gtk.FileChooserAction): Tipo de ação (abrir arquivo ou selecionar pasta).
        """
        dialog = Gtk.FileChooserNative(
            title=_("Selecionar") + (" " + _("Arquivo") if action == Gtk.FileChooserAction.OPEN else " " + _("Pasta")),
            transient_for=self,
            action=action
        )
        dialog.connect("response", self.on_file_chooser_response)
        dialog.show()

    def on_file_chooser_response(self, dialog, response):
        """Processa resposta do diálogo de seleção.

        Args:
            dialog (Gtk.FileChooserNative): O diálogo de seleção.
            response (Gtk.ResponseType): Tipo de resposta (aceito ou cancelado).
        """
        if response == Gtk.ResponseType.ACCEPT:
            # Salva o caminho atual no histórico antes de mudar
            if hasattr(self, 'content_path') and self.content_path:
                self.previous_paths.append(self.content_path)
                self.back_button.set_sensitive(True)

            self.content_path = dialog.get_file().get_path()
            self.current_path = self.content_path
            self.status_label.set_label(_("Analisando: ") + self.content_path)

            state = ContentDetector.detect_content(self.content_path)
            self._load_content_screen(state)

            # Atualiza o estado dos botões
            self.open_folder_button.set_sensitive(True)

    def _load_content_screen(self, state):
        """Carrega a tela correspondente ao estado detectado.

        Args:
            state (str): Estado do conteúdo detectado (pkgbuild, packages, patches, etc.).
        """
        self.current_state = state

        # Limpa o conteúdo atual
        while self.content_box.get_first_child():
            self.content_box.remove(self.content_box.get_first_child())

        # Mapeamento de estados para UIs e IDs corretos
        ui_config = {
            "pkgbuild": {
                "file": "gtk/content_detection/pkgbuild_card.ui",
                "widget_id": "PkgbuildCard"
            },
            "packages": {
                "file": "gtk/content_detection/packages_card.ui",
                "widget_id": "PackagesCard"
            },
            "patches": {
                "file": "gtk/content_detection/patches_card.ui",
                "widget_id": "PatchesCard"
            },
            "empty": {
                "file": "gtk/content_detection/empty_card.ui",
                "widget_id": "EmptyCard"
            },
            "generic": {
                "file": "gtk/content_detection/generic_card.ui",
                "widget_id": "GenericCard"
            }
        }

        # Usa configuração padrão se estado não for encontrado
        config = ui_config.get(state, ui_config["generic"])

        # Carrega o arquivo UI
        builder = Gtk.Builder()
        builder.set_translation_domain("painel_paru")
        builder.add_from_resource(f"/org/gnome/painel_paru/{config['file']}")

        # Obtém o widget principal
        content_widget = builder.get_object(config["widget_id"])
        if content_widget:
            # Conecta os sinais
            self._connect_content_signals(builder, state)

            # Adiciona o widget ao conteúdo
            self.content_box.append(content_widget)
        else:
            self.terminal.append(f"❌ {_('Erro: Widget não encontrado')} ({config['widget_id']})", "error")

    def _connect_content_signals(self, builder, state):
        """Conecta os sinais dos widgets de conteúdo.

        Args:
            builder (Gtk.Builder): Builder com os widgets carregados.
            state (str): Estado do conteúdo atual.
        """
        # Botões comuns a todos os estados
        if build_button := builder.get_object("build_button"):
            build_button.connect("clicked", self.on_build)

        if install_button := builder.get_object("install_button"):
            install_button.connect("clicked", lambda b: self.on_build(b, install=True))

        # Funcionalidades específicas por estado
        if state == "pkgbuild":
            if download_pkgbuild_button := builder.get_object("download_pkgbuild_button"):
                download_pkgbuild_button.connect("clicked", self.on_download_pkgbuild)

            if edit_pkgbuild_button := builder.get_object("edit_pkgbuild_button"):
                edit_pkgbuild_button.connect("clicked", self.on_edit_pkgbuild)

            if check_deps_button := builder.get_object("check_dependencies_button"):
                check_deps_button.connect("clicked", self.on_check_dependencies)

            if verify_signatures_button := builder.get_object("verify_signatures_button"):
                verify_signatures_button.connect("clicked", self.on_verify_signatures)

        elif state == "packages":
            if install_packages_button := builder.get_object("install_packages_button"):
                install_packages_button.connect("clicked", self.on_install_packages)

            if package_info_button := builder.get_object("package_info_button"):
                package_info_button.connect("clicked", self.on_package_info)

            if verify_packages_button := builder.get_object("verify_packages_button"):
                verify_packages_button.connect("clicked", self.on_verify_packages)

        elif state == "patches":
            if apply_patches_button := builder.get_object("apply_patches_button"):
                apply_patches_button.connect("clicked", self.on_apply_patches)

            if view_patch_button := builder.get_object("view_patch_button"):
                view_patch_button.connect("clicked", self.on_view_patch)

            if refresh_patches_button := builder.get_object("refresh_patches_button"):
                refresh_patches_button.connect("clicked", self.on_refresh_patches)
