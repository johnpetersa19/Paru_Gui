from gi.repository import Gtk, Gio, Adw
import os
from pathlib import Path
from .terminal import TerminalView

class PainelParuWindow(Adw.ApplicationWindow):
    """Janela principal configurada para sua estrutura atual"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("Paru GUI")
        self.set_default_size(900, 650)
        
        # INICIALIZAÇÃO ABSOLUTAMENTE PRIMÁRIA DAS CONFIGURAÇÕES
        # IMPORTANTE: Importação explícita de Gio dentro do bloco try-except
        try:
            from gi.repository import Gio
            self.settings = Gio.Settings.new("org.gnome.painel_paru")
            print("✅ Configurações inicializadas com sucesso")
        except Exception as e:
            print(f"❌ Erro FATAL ao inicializar configurações: {e}")
            # Cria um objeto mock para evitar erros - DEVE SER FEITO MESMO EM CASO DE FALHA
            class MockSettings:
                def get_string(self, key):
                    return "gedit"  # Editor padrão
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
        self.main_box.set_homogeneous(False)
        
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
            # Detecta conteúdo e carrega tela apropriada
            from .content_detector import ContentDetector
            state = ContentDetector.detect_content(self.content_path)
            self._load_content_screen(state)

    def _load_content_screen(self, state):
        """Carrega a tela correspondente ao estado detectado"""
        self.current_state = state
        
        # Limpa o conteúdo atual
        for child in self.content_box:
            self.content_box.remove(child)

        # Mapeamento de estados para UIs
        ui_map = {
            "pkgbuild": "gtk/content_detection/pkgbuild_card.ui",
            "packages": "gtk/content_detection/packages_card.ui",
            "patches": "gtk/content_detection/patches_card.ui",
            "empty": "gtk/content_detection/empty_card.ui",
            "generic": "gtk/content_detection/pkgbuild_card.ui"
        }

        # Carrega o recurso correto
        try:
            builder = Gtk.Builder.new_from_resource(f"/org/gnome/painel_paru/{ui_map.get(state, 'gtk/initial_screen.ui')}")

            # Configura o conteúdo principal
            widget = builder.get_object(f"{state}_card")
            if widget:
                self.content_box.append(widget)

                # Configura botões específicos
                if state == "pkgbuild":
                    build_button = builder.get_object("build_button")
                    build_install_button = builder.get_object("build_install_button")
                    edit_button = builder.get_object("edit_button")
                    deps_button = builder.get_object("deps_button")
                    sources_button = builder.get_object("sources_button")

                    if build_button:
                        build_button.connect("clicked", self.on_build)

                    if build_install_button:
                        build_install_button.connect("clicked", lambda b: self.on_build(b, install=True))

                    if edit_button:
                        edit_button.connect("clicked", self.on_edit_pkgbuild)

                    if deps_button:
                        deps_button.connect("clicked", self.on_check_dependencies)

                    if sources_button:
                        sources_button.connect("clicked", self.on_download_sources)

                elif state == "empty":
                    aur_search = builder.get_object("aur_search")
                    download_button = builder.get_object("download_button")

                    if aur_search and download_button:
                        # Atualiza botão de download conforme digitação
                        aur_search.connect("changed", lambda entry:
                            download_button.set_sensitive(bool(entry.get_text().strip())))

                        # Configura busca ao pressionar Enter
                        aur_search.connect("activate", lambda _: download_button.clicked())

                        # Configura botão de download
                        download_button.connect("clicked", lambda _:
                            self._download_pkgbuild(
                                aur_search.get_text(),
                                builder.get_object("ssh_toggle").get_active(),
                                builder.get_object("comments_toggle").get_active()
                            ))
            else:
                self.status_label.set_label("❌ Erro: Tela não encontrada")
        except Exception as e:
            self.status_label.set_label(f"❌ Erro ao carregar tela: {str(e)}")
    
    def on_build(self, button, install=False):
        """Inicia processo de build"""
        try:
            self.terminal.append(f"Iniciando build de {self.content_path}...")
            from .build_manager import BuildManager
            BuildManager.start_build(self.content_path, install, self.terminal.append)
        except Exception as e:
            self.terminal.append(f"❌ Erro ao iniciar build: {str(e)}", "error")
            print(f"❌ Erro ao iniciar build: {e}")
    
    def on_edit_pkgbuild(self, button):
        """Abre o PKGBUILD no editor configurado"""
        try:
            # Usa editor configurado nas preferências
            editor = self.settings.get_string("editor") or "gedit"
            pkgbuild_path = os.path.join(self.content_path, "PKGBUILD")
            subprocess.Popen([editor, pkgbuild_path])
        except Exception as e:
            self.terminal.append(f"❌ Erro ao editar PKGBUILD: {str(e)}", "error")
            print(f"❌ Erro ao editar PKGBUILD: {e}")

    def on_check_dependencies(self, button):
        """Verifica dependências do pacote"""
        try:
            from .paru_runner import ParuRunner
            ParuRunner.run_command(["paru", "-Si", Path(self.content_path).name], self.terminal.append)
            self.status_label.set_label("✅ Dependências verificadas")
        except Exception as e:
            self.terminal.append(f"❌ Erro ao buscar dependências: {str(e)}", "error")
            print(f"❌ Erro ao buscar dependências: {e}")

    def on_download_sources(self, button):
        """Baixa fontes do PKGBUILD"""
        try:
            from .paru_runner import ParuRunner
            ParuRunner.run_command(["makepkg", "-d", "-C", "--noextract"], self.terminal.append)
            self.status_label.set_label("✅ Baixando fontes...")
        except Exception as e:
            self.terminal.append(f"❌ Erro ao baixar fontes: {str(e)}", "error")
            print(f"❌ Erro ao baixar fontes: {e}")

    def _download_pkgbuild(self, pkg_name, use_ssh, show_comments):
        """Baixa PKGBUILD do AUR"""
        try:
            from .aur_downloader import AurDownloader
            AurDownloader.download_pkgbuild(pkg_name, self.content_path, use_ssh, show_comments, self.terminal.append)
            self.status_label.set_label(f"✅ PKGBUILD de {pkg_name} baixado")
        except Exception as e:
            self.terminal.append(f"❌ Erro ao baixar PKGBUILD: {str(e)}", "error")
            print(f"❌ Erro ao baixar PKGBUILD: {e}")
