#!/usr/bin/env python3
import sys
import os
import gi
import subprocess
import importlib.util
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw, GLib, Gdk

# CONFIGURAÇÃO CRÍTICA: SEU PREFIXO REAL
RESOURCE_PREFIX = "/org/gnome/painel_paru"

# Configuração para permitir importações relativas quando executado como script
if __name__ == "__main__":
    # Adiciona o diretório src ao sys.path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

# Importações dos módulos lógicos que você criou
try:
    from .content_detector import ContentDetector
    from .paru_runner import ParuRunner
    from .build_manager import BuildManager
    from .aur_downloader import AurDownloader
    from .terminal import TerminalView
except ImportError:
    # Fallback para execução direta (não como módulo)
    spec = importlib.util.spec_from_file_location(
        "content_detector",
        os.path.join(os.path.dirname(__file__), "content_detector.py")
    )
    content_detector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(content_detector)
    ContentDetector = content_detector.ContentDetector

    spec = importlib.util.spec_from_file_location(
        "paru_runner",
        os.path.join(os.path.dirname(__file__), "paru_runner.py")
    )
    paru_runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(paru_runner)
    ParuRunner = paru_runner.ParuRunner

    spec = importlib.util.spec_from_file_location(
        "build_manager",
        os.path.join(os.path.dirname(__file__), "build_manager.py")
    )
    build_manager = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_manager)
    BuildManager = build_manager.BuildManager

    spec = importlib.util.spec_from_file_location(
        "aur_downloader",
        os.path.join(os.path.dirname(__file__), "aur_downloader.py")
    )
    aur_downloader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(aur_downloader)
    AurDownloader = aur_downloader.AurDownloader

    spec = importlib.util.spec_from_file_location(
        "terminal",
        os.path.join(os.path.dirname(__file__), "terminal.py")
    )
    terminal = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(terminal)
    TerminalView = terminal.TerminalView

class ParuApplication(Adw.Application):
    """Aplicação principal configurada para sua estrutura atual"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.props.application_id = "org.gnome.painel_paru"

        # Configuração de schemas (usando seu arquivo .gschema.xml existente)
        self.settings = Gio.Settings.new("org.gnome.painel_paru")

        # Conecta o sinal de ativação
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        """Callback quando a aplicação é ativada"""
        # Verifica se já existe uma janela
        if not hasattr(app, "win"):
            app.win = PainelParuWindow(application=app)

        # Mostra a janela
        app.win.present()


class PainelParuWindow(Adw.ApplicationWindow):
    """Janela principal configurada para sua estrutura atual"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("Paru GUI")
        self.set_default_size(900, 650)

        # Barra superior com menu padrão GNOME
        self.setup_header_bar()

        # Estado atual da interface
        self.current_state = None
        self.content_path = None

        # Terminal integrado para saída de comandos
        self.terminal = TerminalView()
        self.terminal.set_vexpand(True)

        # Carrega a tela inicial
        self.load_initial_screen()

    def setup_header_bar(self):
        """Configura a barra superior com menu padrão GNOME"""
        header = Adw.HeaderBar()
        self.set_titlebar(header)

        # Botão de menu
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_tooltip_text("Menu do aplicativo")

        # Cria menu do aplicativo
        menu = Gio.Menu()
        menu.append("Preferências", "app.preferences")
        menu.append("Sobre", "app.about")
        menu.append("Sair", "app.quit")

        # Associa menu ao botão
        menu_button.set_menu_model(menu)
        header.pack_end(menu_button)

    def load_initial_screen(self):
        """Carrega a tela inicial com os dois ícones centrais"""
        self.current_state = "initial"

        # Carrega EXATAMENTE o recurso que você criou
        try:
            builder = Gtk.Builder.new_from_resource(
                f"{RESOURCE_PREFIX}/gtk/initial_screen.ui"
            )
            self.set_content(builder.get_object("initial_screen"))

            # Conecta os botões
            builder.get_object("file_button").connect(
                "clicked", self.on_select_file
            )
            builder.get_object("folder_button").connect(
                "clicked", self.on_select_folder
            )
            self.status_label = builder.get_object("status_label")
        except Exception as e:
            print(f"❌ ERRO FATAL ao carregar tela inicial: {e}")
            # Cria fallback simples para diagnóstico
            label = Gtk.Label(label="ERRO: Recursos UI não encontrados\nVerifique seu meson.build e main.py",
                             css_classes=["error"],
                             wrap=True)
            self.set_content(label)

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

            # Usa detecção REAL com content_detector.py
            state = self._detect_content(self.content_path)
            self._load_content_screen(state)

    def _detect_content(self, path):
        """Detecção real usando content_detector.py"""
        try:
            return ContentDetector.detect_content(path)
        except Exception as e:
            print(f"❌ Erro na detecção de conteúdo: {e}")
            return "generic"

    def _load_content_screen(self, state):
        """Carrega a tela correspondente ao estado detectado"""
        self.current_state = state

        # Mapeamento de estados para UIs - USANDO EXATAMENTE SEUS CAMINHOS
        ui_map = {
            "pkgbuild": "gtk/content_detection/pkgbuild_card.ui",
            "packages": "gtk/content_detection/packages_card.ui",
            "patches": "gtk/content_detection/patches_card.ui",
            "empty": "gtk/content_detection/empty_card.ui",
        }

        # Carrega o recurso correto
        try:
            builder = Gtk.Builder.new_from_resource(
                f"{RESOURCE_PREFIX}/{ui_map.get(state, 'gtk/initial_screen.ui')}"
            )
        except Exception as e:
            print(f"❌ Erro ao carregar recurso: {e}")
            self.status_label.set_label(f"Erro ao carregar {state} UI")
            return

        # Configura o conteúdo principal
        if state == "pkgbuild":
            self._setup_pkgbuild_card(builder)
        elif state == "empty":
            self._setup_empty_card(builder)
        # Adicione outros estados conforme necessário

        # Define o conteúdo (o nome do objeto raiz deve corresponder ao seu .ui)
        screen_id = f"{state}_card" if state != "initial" else "initial_screen"
        try:
            # Cria container para adicionar o terminal
            container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            container.append(builder.get_object(screen_id))

            # Adiciona o terminal abaixo do conteúdo principal
            terminal_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            terminal_box.append(Gtk.Label(label="Saída:", halign=Gtk.Align.START))
            terminal_box.append(self.terminal)
            container.append(terminal_box)

            self.set_content(container)
            self.status_label.set_label(f"Modo: {state.replace('_', ' ').title()}")
        except Exception as e:
            print(f"❌ Erro ao definir conteúdo: {e}")
            self.status_label.set_label(f"Erro ao exibir {state} UI")

    def _setup_pkgbuild_card(self, builder):
        """Configura ações para o card PKGBUILD"""
        pkgbuild_dir = os.path.dirname(self.content_path)

        # Configura botões reais
        builder.get_object("build_button").connect(
            "clicked", lambda _: self._start_build(pkgbuild_dir, False)
        )

        # Verifica se o botão "build_install_button" existe
        build_install_button = builder.get_object("build_install_button")
        if build_install_button:
            build_install_button.connect(
                "clicked", lambda _: self._start_build(pkgbuild_dir, True)
            )
        else:
            print("⚠️ Botão 'build_install_button' não encontrado - usando apenas 'build_button'")

        builder.get_object("edit_button").connect(
            "clicked", lambda _: self._edit_pkgbuild(pkgbuild_dir)
        )

        builder.get_object("deps_button").connect(
            "clicked", lambda _: self._show_dependencies(pkgbuild_dir)
        )

        builder.get_object("sources_button").connect(
            "clicked", lambda _: self._download_sources(pkgbuild_dir)
        )

    def _setup_empty_card(self, builder):
        """Configura ações para o card de pasta vazia"""
        # Configura campo de busca
        aur_search = builder.get_object("aur_search")
        if aur_search:
            aur_search.connect("changed", lambda entry:
                builder.get_object("download_button").set_sensitive(bool(entry.get_text().strip()))
            )

        # Configura botão de download
        download_button = builder.get_object("download_button")
        if download_button:
            download_button.connect(
                "clicked", lambda _: self._download_pkgbuild(
                    aur_search.get_text() if aur_search else "",
                    builder.get_object("ssh_toggle").get_active() if builder.get_object("ssh_toggle") else False,
                    builder.get_object("comments_toggle").get_active() if builder.get_object("comments_toggle") else False
                )
            )

    def _start_build(self, pkgbuild_dir, install):
        """Inicia build do PKGBUILD"""
        try:
            BuildManager.start_build(
                pkgbuild_dir,
                install,
                self.terminal.append
            )
            self.status_label.set_label("🏗️ Iniciando build...")
        except Exception as e:
            self.terminal.append(f"❌ Erro ao iniciar build: {str(e)}", "error")
            print(f"❌ Erro ao iniciar build: {e}")

    def _edit_pkgbuild(self, pkgbuild_dir):
        """Abre PKGBUILD no editor configurado"""
        try:
            editor = self.settings.get_string("editor") or "gedit"
            subprocess.Popen([editor, f"{pkgbuild_dir}/PKGBUILD"])
            self.status_label.set_label(f"✏️ Editando PKGBUILD com {editor}")
        except Exception as e:
            self.terminal.append(f"❌ Erro ao editar PKGBUILD: {str(e)}", "error")
            print(f"❌ Erro ao editar PKGBUILD: {e}")

    def _show_dependencies(self, pkgbuild_dir):
        """Mostra dependências do PKGBUILD"""
        try:
            ParuRunner.run_command(
                ["paru", "-Si", f"{pkgbuild_dir}/PKGBUILD"],
                self.terminal.append
            )
            self.status_label.set_label("🔍 Buscando dependências...")
        except Exception as e:
            self.terminal.append(f"❌ Erro ao buscar dependências: {str(e)}", "error")
            print(f"❌ Erro ao buscar dependências: {e}")

    def _download_sources(self, pkgbuild_dir):
        """Baixa fontes do PKGBUILD"""
        try:
            ParuRunner.run_command(
                ["makepkg", "-d", "-C", "--noextract"],
                self.terminal.append
            )
            self.status_label.set_label("📥 Baixando fontes...")
        except Exception as e:
            self.terminal.append(f"❌ Erro ao baixar fontes: {str(e)}", "error")
            print(f"❌ Erro ao baixar fontes: {e}")

    def _download_pkgbuild(self, pkg_name, use_ssh, show_comments):
        """Baixa PKGBUILD do AUR"""
        if not pkg_name or not pkg_name.strip():
            self.status_label.set_label("⚠️ Nome do pacote é obrigatório")
            self.terminal.append("⚠️ Nome do pacote é obrigatório", "error")
            return

        try:
            AurDownloader.start_download(
                pkg_name,
                self.content_path,
                use_ssh,
                show_comments,
                self.terminal.append
            )
            self.status_label.set_label(f"⬇️ Baixando {pkg_name} do AUR...")
        except Exception as e:
            self.terminal.append(f"❌ Erro ao baixar PKGBUILD: {str(e)}", "error")
            print(f"❌ Erro ao baixar PKGBUILD: {e}")


def main(version):
    app = ParuApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    # Configuração crítica para modo de desenvolvimento
    if os.environ.get('DEV_MODE'):
        print("🔧 Modo de desenvolvimento ativado - recarregando recursos")
        try:
            # Tenta múltiplos caminhos possíveis para o GResource
            possible_paths = [
                # Caminhos locais
                "build/meson-private/Example.gresource",
                "meson-private/Example.gresource",
                "../build/meson-private/Example.gresource",

                # Caminhos do Flatpak
                "/app/share/Example/Example.gresource",
                "/app/share/org.gnome.Example/Example.gresource",
                "share/Example/Example.gresource",
                "share/org.gnome.Example/Example.gresource"
            ]

            for path in possible_paths:
                try:
                    resource = Gio.Resource.load(path)
                    resource._register()
                    print(f"✅ Recursos recarregados com sucesso de {path}")
                    break
                except Exception as e:
                    continue
            else:
                print("❌ Erro ao recarregar recursos: nenhum caminho encontrado")
                print("💡 Dicas:")
                print("   - Execute 'ninja -C build' primeiro")
                print("   - Verifique se o diretório de build está correto")
                print("   - Confira se o nome do recurso é 'painel_paru.gresource'")
        except Exception as e:
            print(f"❌ Erro ao recarregar recursos: {e}")

    # Recarga automática com Ctrl+R
    def reload_ui(self):
        if not os.getenv("DEV_MODE"):
            return

        try:
            # Tenta múltiplos caminhos possíveis
            possible_paths = [
                # Caminhos locais
                "build/meson-private/Example.gresource",
                "meson-private/Example.gresource",
                "../build/meson-private/Example.gresource",

                # Caminhos do Flatpak
                "/app/share/Example/Example.gresource",
                "/app/share/org.gnome.Example/Example.gresource",
                "share/Example/Example.gresource",
                "share/org.gnome.Example/Example.gresource"
            ]

            for path in possible_paths:
                try:
                    resource = Gio.Resource.load(path)
                    resource._register()
                    print(f"✅ UI recarregada com sucesso de {path}")
                    break
                except Exception as e:
                    continue
            else:
                print("❌ Erro ao recarregar UI: nenhum caminho encontrado")
                return

            # Recarrega tela atual
            if self.current_state == "initial":
                self.load_initial_screen()
            elif self.current_state == "pkgbuild":
                self._load_content_screen("pkgbuild")
            elif self.current_state == "empty":
                self._load_content_screen("empty")
        except Exception as e:
            print(f"❌ Erro ao recarregar UI: {str(e)}")

    # Adiciona ao PainelParuWindow
    PainelParuWindow.reload_ui = reload_ui

    # Conecta o evento de tecla
    original_init = PainelParuWindow.__init__
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.connect("key-press-event", lambda w, e:
            self.reload_ui() if e.keyval == Gdk.KEY_R and
            e.state & Gdk.ModifierType.CONTROL_MASK else None
        )
    PainelParuWindow.__init__ = new_init

    sys.exit(main("0.1.0"))
