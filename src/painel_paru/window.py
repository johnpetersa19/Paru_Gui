# window.py
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw
import os
import subprocess
import shlex
import shutil
from pathlib import Path
from .terminal import TerminalView
from .content_detector import ContentDetector
from .build_manager import BuildManager
from .paru_runner import ParuRunner
from .aur_downloader import AurDownloader
from .conflict_resolver import ConflictResolver
import gettext

_ = gettext.gettext

# Imports dos novos módulos desmembrados
try:
    from .window_core import WindowCore
    from .window_ui import WindowUI
    from .window_content import WindowContent
    from .window_build import WindowBuild
    from .window_aur import WindowAUR
    from .window_preferences import WindowPreferences
    from .window_conflicts import WindowConflicts
    from .window_signatures import WindowSignatures
    from .window_notifications import WindowNotifications
    from .window_patches import WindowPatches
    print("✅ Módulos importados com sucesso")
except ImportError as e:
    print(f"❌ Erro ao importar módulos: {str(e)}")
    # Configura fallback para o código original
    class WindowCore: pass
    class WindowUI: pass
    class WindowContent: pass
    class WindowBuild: pass
    class WindowAUR: pass
    class WindowPreferences: pass
    class WindowConflicts: pass
    class WindowSignatures: pass
    class WindowNotifications: pass
    class WindowPatches: pass

class PainelParuWindow(Adw.ApplicationWindow,
                      WindowCore,
                      WindowUI,
                      WindowContent,
                      WindowBuild,
                      WindowAUR,
                      WindowPreferences,
                      WindowConflicts,
                      WindowSignatures,
                      WindowNotifications,
                      WindowPatches):
    """Janela principal configurada para sua estrutura atual"""

    def __init__(self, *args, **kwargs):
        # Inicializa traduções
        gettext.bindtextdomain("painel_paru", "/usr/share/locale")
        gettext.textdomain("painel_paru")
        super().__init__(*args, **kwargs)

        self.set_title(_("Paru GUI"))
        self.set_default_size(900, 650)

        # INICIALIZAÇÃO DAS CONFIGURAÇÕES
        try:
            self.settings = Gio.Settings.new("org.gnome.painel_paru")
            print("✅ Configurações inicializadas com sucesso")
        except Exception as e:
            print(f"❌ Erro ao inicializar configurações: {str(e)}")
            # Cria configurações básicas de fallback
            self.settings = Gio.Settings.new_with_path("org.gnome.painel_paru", "/defaults")

        # INICIALIZIZAÇÃO DOS COMPONENTES
        try:
            # Inicializa os componentes básicos
            self._init_core_components()

            # Configura a interface do usuário
            self.setup_main_ui()

            # Configurações iniciais
            self.status_label.set_label(_("Bem-vindo ao Paru GUI"))
            self.back_button.set_sensitive(False)
            self.open_folder_button.set_sensitive(False)

            print("✅ Janela inicializada com sucesso")
        except Exception as e:
            print(f"❌ Erro ao inicializar janela: {str(e)}")
            error_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            error_box.set_margin_start(20)
            error_box.set_margin_end(20)
            error_box.set_margin_top(20)
            error_box.set_margin_bottom(20)

            error_label = Gtk.Label()
            error_label.set_markup(f"<span foreground='red' size='large'>{_('Erro na inicialização')}</span>")
            error_label.set_justify(Gtk.Justification.CENTER)
            error_box.append(error_label)

            message_label = Gtk.Label()
            message_label.set_markup(f"<span foreground='red'>{_('Detalhes:')}</span> {str(e)}")
            message_label.set_wrap(True)  # Correção: set_line_wrap() -> set_wrap()
            message_label.set_justify(Gtk.Justification.CENTER)
            error_box.append(message_label)

            self.set_content(error_box)

    def _init_core_components(self):
        """Inicializa os componentes básicos da aplicação"""
        # Inicializa histórico de navegação
        self.previous_paths = []
        self.content_path = None
        self.current_path = None
        self.current_state = None

        # Inicializa o terminal
        self.terminal = TerminalView()

        # Inicializa os componentes de gerenciamento
        self.build_callback = None  # Callback para continuar o build após resolver conflitos
        self.current_process = None  # Armazena o processo atual para permitir cancelamento
        self.conflict_resolver = ConflictResolver()

        # Inicializa o build manager
        self.build_manager = BuildManager()

        # Inicializa o aur downloader (correção: passando callback)
        try:
            self.aur_downloader = AurDownloader(self.terminal.append)
        except TypeError:
            # Caso a classe AurDownloader não aceite callback no construtor
            self.aur_downloader = AurDownloader()
            print("⚠️ AurDownloader não aceita callback no construtor. Usando fallback.")

        print("✅ Componentes básicos inicializados")

    def _init_all_components(self):
        """Inicializa todos os componentes dos diferentes módulos"""
        # Inicializa componentes básicos
        self._init_core_components()

        # Inicializa componentes de UI
        if hasattr(self, '_init_ui_components'):
            self._init_ui_components()

        # Inicializa componentes de conteúdo
        if hasattr(self, '_init_content_components'):
            self._init_content_components()

        # Inicializa componentes de build
        if hasattr(self, '_init_build_components'):
            self._init_build_components()

        # Inicializa componentes do AUR
        if hasattr(self, '_init_aur_components'):
            self._init_aur_components()

        # Inicializa componentes de conflitos
        if hasattr(self, '_init_conflict_components'):
            self._init_conflict_components()

        # Inicializa componentes de assinaturas
        if hasattr(self, '_init_signatures_components'):
            self._init_signatures_components()

        # Inicializa componentes de notificações
        if hasattr(self, '_init_notifications_components'):
            self._init_notifications_components()

        # Inicializa componentes de patches
        if hasattr(self, '_init_patches_components'):
            self._init_patches_components()

        # Inicializa componentes de preferências
        if hasattr(self, '_init_preferences_components'):
            self._init_preferences_components()

        print("✅ Todos os componentes foram inicializados com sucesso")

    def on_show_about(self, action, parameter):
        """Mostra janela Sobre"""
        about = Adw.AboutWindow(
            transient_for=self,
            application_name=_("Paru GUI"),
            application_icon="org.gnome.painel_paru",
            developer_name=_("Equipe Paru GUI"),
            version="0.1.0",
            release_notes=[
                _("Interface gráfica moderna para o gerenciador de pacotes Paru"),
                _("Suporte a builds com revisão do PKGBUILD"),
                _("Detecção automática de conteúdo (PKGBUILD, pacotes, patches)"),
                _("Integração completa com o AUR")
            ],
            developers=[
                _("Desenvolvedor Principal <dev@paru-gui.org>"),
                _("Contribuidores <https://github.com/paru-gui/contributors>")
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

    def on_update_system(self, action, parameter):
        """Atualiza o sistema com paru -Syu"""
        self.terminal.append(_("🔄 Atualizando sistema..."), "progress")
        ParuRunner.run_command(["paru", "-Syu"], self.terminal.append)
