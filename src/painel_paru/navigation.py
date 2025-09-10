from gi.repository import Gtk, Gio, GLib
import os
from pathlib import Path
import gettext
_ = gettext.gettext

from .content_detector import ContentDetector
from .ui_builder import UI_BUILDER_CONFIG

class NavigationManager:
    def __init__(self, window):
        self.window = window
        self.navigation_history = []
        # Removido self.current_state - agora centralizado na window

    def navigate_to(self, path):
        """Navega para um novo caminho/diretório"""
        if path and os.path.exists(path):
            # Atualiza o histórico de navegação
            if self.window.content_path:
                self.navigation_history.append(self.window.content_path)
            self.window.content_path = path

            # Detecta conteúdo e carrega a tela apropriada
            state = ContentDetector.detect_content(self.window.content_path)
            self._load_content_screen(state)

            # Atualiza o estado dos botões
            self.window.open_folder_button.set_sensitive(True)
            self.window.back_button.set_sensitive(len(self.navigation_history) > 0)

            return True
        return False

    def go_back(self):
        """Navega de volta para a tela anterior"""
        if len(self.navigation_history) > 0:
            # Remove o atual do histórico
            if self.window.content_path:
                self.navigation_history.append(self.window.content_path)

            # Vai para o anterior
            previous_path = self.navigation_history.pop()
            self.window.content_path = previous_path

            # Detecta conteúdo e carrega a tela apropriada
            state = ContentDetector.detect_content(self.window.content_path)
            self._load_content_screen(state)

            # Atualiza o estado dos botões
            self.window.open_folder_button.set_sensitive(True)
            self.window.back_button.set_sensitive(len(self.navigation_history) > 0)

            return True
        else:
            self.window.back_button.set_sensitive(False)
            return False

    def _load_content_screen(self, state):
        """Carrega a tela de conteúdo adequada baseado no estado detectado"""
        # Centraliza o gerenciamento de estado usando os métodos da window
        self.window.set_current_state(state)

        # Usa configuração padrão se estado não for encontrado
        config = UI_BUILDER_CONFIG.get(state, UI_BUILDER_CONFIG["empty"])

        try:
            # Carrega o recurso
            resource_path = f"/org/gnome/painel_paru/{config['file']}"
            builder = Gtk.Builder.new_from_resource(resource_path)

            # Procura o widget principal
            widgets = builder.get_objects()
            main_widget = None
            for widget in widgets:
                if hasattr(widget, 'get_widget_id') and widget.get_widget_id() == config["widget_id"]:
                    main_widget = widget
                    break

            if not main_widget:
                # Tenta encontrar por classe
                for widget in widgets:
                    if isinstance(widget, Gtk.Widget):
                        main_widget = widget
                        break

            if main_widget:
                # Remove conteúdo atual
                if self.window.content_box.get_first_child():
                    self.window.content_box.remove(self.window.content_box.get_first_child())

                # Adiciona novo conteúdo
                self.window.content_box.append(main_widget)

                # Configura botões específicos do estado
                self._setup_state_buttons(main_widget, state)

                # Atualiza informações do cabeçalho
                self._update_header(state)

                return True
            else:
                self.window.terminal_manager.append(_("❌ Erro: Widget principal não encontrado"), "error")
                return False

        except Exception as e:
            self.window.terminal_manager.append(f"❌ {_('Erro ao carregar interface:')} {str(e)}", "error")
            print(f"❌ Erro ao carregar interface: {e}")
            return False

    def _setup_state_buttons(self, content_widget, state):
        """Configura os botões específicos para o estado atual"""
        # Primeiro remove todos os botões existentes
        while self.window.toolbar_box.get_first_child():
            self.window.toolbar_box.remove(self.window.toolbar_box.get_first_child())

        # Configura botões baseados no estado
        if state == "pkgbuild":
            self._setup_pkgbuild_buttons(content_widget)
        elif state == "packages":
            self._setup_packages_buttons(content_widget)
        elif state == "patches":
            self._setup_patches_buttons(content_widget)
        elif state == "aur":
            self._setup_aur_buttons(content_widget)

    def _setup_pkgbuild_buttons(self, content_widget):
        """Configura os botões para estado PKGBUILD"""
        # Botão de build
        build_button = Gtk.Button(
            label=_("Compilar"),
            icon_name="media-playback-start",
            css_classes=["suggested-action"]
        )
        build_button.connect("clicked", self.window.handlers.on_build_package)

        # Botão de editar PKGBUILD
        edit_button = Gtk.Button(
            label=_("Editar PKGBUILD"),
            icon_name="document-edit"
        )
        edit_button.connect("clicked", self.window.handlers.on_edit_pkgbuild)

        # Botão de verificar assinaturas
        verify_button = Gtk.Button(
            label=_("Verificar Assinaturas"),
            icon_name="security-high"
        )
        verify_button.connect("clicked", self.window.handlers.on_verify_signatures)

        # Botão de dependências
        deps_button = Gtk.Button(
            label=_("Verificar Dependências"),
            icon_name="system-search"
        )
        deps_button.connect("clicked", self.window.handlers.on_check_dependencies)

        # Adiciona botões na toolbar
        self.window.toolbar_box.append(build_button)
        self.window.toolbar_box.append(edit_button)
        self.window.toolbar_box.append(verify_button)
        self.window.toolbar_box.append(deps_button)

    def _setup_packages_buttons(self, content_widget):
        """Configura os botões para estado PACKAGES"""
        # Botão de instalação
        install_button = Gtk.Button(
            label=_("Instalar Pacotes"),
            icon_name="software-install",
            css_classes=["suggested-action"]
        )
        install_button.connect("clicked", self.window.handlers.on_install_packages)

        # Botão de verificar assinaturas
        verify_button = Gtk.Button(
            label=_("Verificar Assinaturas"),
            icon_name="security-high"
        )
        verify_button.connect("clicked", self.window.handlers.on_verify_signatures)

        # Adiciona botões na toolbar
        self.window.toolbar_box.append(install_button)
        self.window.toolbar_box.append(verify_button)

    def _setup_patches_buttons(self, content_widget):
        """Configura os botões para estado PATCHES"""
        # Botão de aplicar patches
        apply_button = Gtk.Button(
            label=_("Aplicar Patches"),
            icon_name="document-edit",
            css_classes=["suggested-action"]
        )
        apply_button.connect("clicked", self.window.handlers.on_apply_patches)

        # Adiciona botões na toolbar
        self.window.toolbar_box.append(apply_button)

    def _setup_aur_buttons(self, content_widget):
        """Configura os botões para estado AUR"""
        # Botão de download
        download_button = content_widget.get_first_child().get_first_child().get_next_sibling().get_next_sibling().get_first_child()
        if download_button:
            download_button.connect("clicked", self.window.handlers.on_download_pkgbuild)

        # Botão de busca
        search_button = content_widget.get_first_child().get_first_child().get_next_sibling().get_first_child().get_next_sibling()
        if search_button:
            search_button.connect("clicked", lambda b: self.window.handlers.on_search_pkgbuild(
                content_widget.get_first_child().get_first_child().get_next_sibling().get_first_child().get_first_child()
            ))

    def _update_header(self, state):
        """Atualiza informações do cabeçalho baseado no estado"""
        if self.window.content_path:
            path = Path(self.window.content_path)
            if state == "pkgbuild":
                title = _("PKGBUILD - ") + path.name
            elif state == "packages":
                title = _("Pacotes - ") + path.name
            elif state == "patches":
                title = _("Patches - ") + path.name
            elif state == "aur":
                title = _("AUR - ") + path.name
            else:
                title = _("Explorador - ") + path.name

            self.window.header_title.set_label(title)
            self.window.header_title.set_tooltip_text(str(path))
