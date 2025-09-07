# window.py
from gi.repository import Gtk, Gio, Adw
import os
import subprocess
import shlex
from pathlib import Path

from .terminal import TerminalView
from .content_detector import ContentDetector
from .build_manager import BuildManager
from .paru_runner import ParuRunner
from .aur_downloader import AurDownloader


class PainelParuWindow(Adw.ApplicationWindow):
    """Janela principal configurada para sua estrutura atual"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("Paru GUI")
        self.set_default_size(900, 650)

        # INICIALIZAÇÃO DAS CONFIGURAÇÕES
        try:
            self.settings = Gio.Settings.new("org.gnome.painel_paru")
            print("✅ Configurações inicializadas com sucesso")
        except Exception as e:
            print(f"❌ Erro FATAL ao inicializar configurações: {e}")
            class MockSettings:
                def get_string(self, key):
                    return "gedit"
            self.settings = MockSettings()

        # Configuração da interface
        self.toolbar_view = Adw.ToolbarView()
        self.set_content(self.toolbar_view)

        # Cabeçalho
        header = Adw.HeaderBar()
        self.toolbar_view.add_top_bar(header)

        # Caixa de conteúdo principal
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main_box.set_margin_start(20)
        self.main_box.set_margin_end(20)
        self.main_box.set_margin_top(20)
        self.main_box.set_margin_bottom(20)
        self.toolbar_view.set_content(self.main_box)

        # Status label
        self.status_label = Gtk.Label(
            label="Selecione um arquivo ou pasta para começar",
            css_classes=["subtitle-2"],
            margin_top=20
        )
        self.main_box.append(self.status_label)

        # Área de conteúdo
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main_box.append(self.content_box)

        # Terminal
        self.terminal = TerminalView()
        self.main_box.append(self.terminal)

        # Botões de ação
        action_box = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)

        select_file_btn = Gtk.Button(label="Selecionar Arquivo")
        select_file_btn.connect("clicked", self.on_select_file)
        action_box.append(select_file_btn)

        select_folder_btn = Gtk.Button(label="Selecionar Pasta")
        select_folder_btn.connect("clicked", self.on_select_folder)
        action_box.append(select_folder_btn)

        self.main_box.append(action_box)

    def on_select_file(self, button):
        """Handler para seleção de arquivo único"""
        self._show_file_chooser(Gtk.FileChooserAction.OPEN)

    def on_select_folder(self, button):
        """Handler para seleção de pasta"""
        self._show_file_chooser(Gtk.FileChooserAction.SELECT_FOLDER)

    def _show_file_chooser(self, action):
        """Mostra diálogo de seleção de arquivo/pasta"""
        dialog = Gtk.FileChooserNative(
            title="Selecionar" + (" Arquivo" if action == Gtk.FileChooserAction.OPEN else " Pasta"),
            transient_for=self,
            action=action
        )
        dialog.connect("response", self.on_file_chooser_response)
        dialog.show()

    def on_file_chooser_response(self, dialog, response):
        """Processa resposta do diálogo de seleção"""
        if response == Gtk.ResponseType.ACCEPT:
            self.content_path = dialog.get_file().get_path()
            self.status_label.set_label(f"Analisando: {self.content_path}")

            state = ContentDetector.detect_content(self.content_path)
            self._load_content_screen(state)

    def _load_content_screen(self, state):
        """Carrega a tela correspondente ao estado detectado"""
        self.current_state = state

        # Limpa o conteúdo atual
        while self.content_box.get_first_child():
            self.content_box.remove(self.content_box.get_first_child())

        # Mapeamento de estados para UIs e IDs corretos
        ui_config = {
            "pkgbuild": {
                "file": "src/gtk/content_detection/pkgbuild_card.ui",
                "widget_id": "PkgbuildCard"
            },
            "packages": {
                "file": "src/gtk/content_detection/packages_card.ui",
                "widget_id": "PackagesCard"
            },
            "patches": {
                "file": "src/gtk/content_detection/patches_card.ui",
                "widget_id": "PatchesCard"
            },
            "empty": {
                "file": "src/gtk/content_detection/empty_card.ui",
                "widget_id": "EmptyCard"
            }
        }

        # Usa configuração padrão se estado não for encontrado
        config = ui_config.get(state, ui_config["empty"])

        try:
            # Carrega o recurso
            resource_path = f"/org/gnome/painel_paru/{config['file']}"
            builder = Gtk.Builder.new_from_resource(resource_path)

            # Procura o widget principal
            widgets = builder.get_objects()
            main_widget = None

            for widget in widgets:
                if hasattr(widget, 'get_template_child'):  # Widget com template
                    main_widget = widget
                    break
                elif isinstance(widget, Gtk.Box):  # Container principal
                    main_widget = widget
                    break

            if not main_widget and widgets:
                main_widget = widgets[0]  # Fallback

            if main_widget:
                self.content_box.append(main_widget)
                self.status_label.set_label(f"✅ Conteúdo carregado: {state}")

                # Configura botões específicos
                if state == "pkgbuild":
                    self._setup_pkgbuild_buttons(builder)
                elif state == "empty":
                    self._setup_empty_buttons(builder)
            else:
                self.status_label.set_label("❌ Erro: Widget principal não encontrado")

        except Exception as e:
            self.status_label.set_label(f"❌ Erro ao carregar tela: {str(e)}")
            print(f"❌ Erro detalhado ao carregar tela: {e}")

            # Fallback visual
            error_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            error_box.set_margin_start(30)
            error_box.set_margin_end(30)
            error_box.set_margin_top(30)
            error_box.set_margin_bottom(30)

            error_label = Gtk.Label(label=f"Erro ao carregar interface para: {state}")
            error_label.add_css_class("title-3")
            error_box.append(error_label)

            detail_label = Gtk.Label(label=str(e))
            detail_label.set_wrap(True)
            error_box.append(detail_label)

            self.content_box.append(error_box)

    def _setup_pkgbuild_buttons(self, builder):
        """Configura os botões específicos do PKGBUILD"""
        button_configs = {
            "build_button": lambda b: self.on_build(b),
            "build_install_button": lambda b: self.on_build(b, install=True),
            "edit_button": self.on_edit_pkgbuild,
            "deps_button": self.on_check_dependencies,
            "sources_button": self.on_download_sources
        }

        for button_id, callback in button_configs.items():
            button = builder.get_object(button_id)
            if button:
                button.connect("clicked", callback)
            else:
                print(f"⚠️ Botão {button_id} não encontrado no builder")

    def _setup_empty_buttons(self, builder):
        """Configura os botões da tela de pasta vazia"""
        aur_search = builder.get_object("aur_search")
        download_button = builder.get_object("download_button")
        search_button = builder.get_object("search_button")

        if aur_search and download_button:
            # Atualiza botão de download conforme digitação
            aur_search.connect("changed", lambda entry:
                download_button.set_sensitive(bool(entry.get_text().strip())))

            # Configura busca ao pressionar Enter
            aur_search.connect("activate", lambda _: download_button.emit("clicked"))

            # Configura botão de download
            download_button.connect("clicked", lambda _:
                self._download_pkgbuild(
                    aur_search.get_text(),
                    builder.get_object("ssh_toggle").get_active() if builder.get_object("ssh_toggle") else False,
                    builder.get_object("comments_toggle").get_active() if builder.get_object("comments_toggle") else False
                ))

        # Conecta botão de busca se existir
        if search_button and aur_search:
            search_button.connect("clicked", lambda _:
                self._search_aur_package(aur_search.get_text()))

    def on_build(self, button, install=False):
        """Inicia processo de build"""
        if not hasattr(self, 'content_path') or not self.content_path:
            self.terminal.append("❌ Nenhum diretório selecionado.", "error")
            return
        if not os.path.exists(self.content_path):
            self.terminal.append("❌ Caminho não existe.", "error")
            return

        try:
            self.terminal.append(f"Iniciando build de {self.content_path}...")
            BuildManager.start_build(self.content_path, install, self.terminal.append)
        except Exception as e:
            self.terminal.append(f"❌ Erro ao iniciar build: {str(e)}", "error")
            print(f"❌ Erro ao iniciar build: {e}")

    def on_edit_pkgbuild(self, button):
        """Abre o PKGBUILD no editor configurado"""
        if not hasattr(self, 'content_path') or not self.content_path:
            self.terminal.append("❌ Nenhum diretório selecionado.", "error")
            return

        pkgbuild_path = Path(self.content_path) / "PKGBUILD"
        if not pkgbuild_path.exists():
            self.terminal.append("❌ PKGBUILD não encontrado.", "error")
            return

        try:
            editor = self.settings.get_string("editor") or "gedit"
            cmd = shlex.split(editor) + [str(pkgbuild_path)]
            subprocess.Popen(cmd)
        except Exception as e:
            self.terminal.append(f"❌ Erro ao editar PKGBUILD: {str(e)}", "error")
            print(f"❌ Erro ao editar PKGBUILD: {e}")

    def on_check_dependencies(self, button):
        """Verifica dependências do pacote"""
        if not hasattr(self, 'content_path') or not self.content_path:
            self.terminal.append("❌ Nenhum diretório selecionado.", "error")
            return

        try:
            package_name = Path(self.content_path).name
            ParuRunner.run_command(["paru", "-Si", package_name], self.terminal.append)
            self.status_label.set_label("✅ Dependências verificadas")
        except Exception as e:
            self.terminal.append(f"❌ Erro ao buscar dependências: {str(e)}", "error")
            print(f"❌ Erro ao buscar dependências: {e}")

    def on_download_sources(self, button):
        """Baixa fontes do PKGBUILD"""
        if not hasattr(self, 'content_path') or not self.content_path:
            self.terminal.append("❌ Nenhum diretório selecionado.", "error")
            return

        try:
            ParuRunner.run_command(["makepkg", "-d", "-C", "--noextract"], self.terminal.append)
            self.status_label.set_label("✅ Baixando fontes...")
        except Exception as e:
            self.terminal.append(f"❌ Erro ao baixar fontes: {str(e)}", "error")
            print(f"❌ Erro ao baixar fontes: {e}")

    def _download_pkgbuild(self, pkg_name, use_ssh, show_comments):
        """Baixa PKGBUILD do AUR"""
        if not pkg_name.strip():
            self.terminal.append("❌ Nome do pacote não pode ser vazio.", "error")
            return

        try:
            AurDownloader.download_pkgbuild(pkg_name, self.content_path, use_ssh, show_comments, self.terminal.append)
            self.status_label.set_label(f"✅ PKGBUILD de '{pkg_name}' baixado")
        except Exception as e:
            self.terminal.append(f"❌ Erro ao baixar PKGBUILD: {str(e)}", "error")
            print(f"❌ Erro ao baixar PKGBUILD: {e}")

    def _search_aur_package(self, query):
        """Busca um pacote no AUR (placeholder para futura implementação)"""
        if not query.strip():
            self.terminal.append("⚠️ Digite um nome para buscar no AUR.")
            return
        self.terminal.append(f"🔍 Buscando no AUR: {query}...")
        # Exemplo futuro: chamar API do AUR
        # AurDownloader.search(query, callback=self.update_search_results)
