from gi.repository import Gtk, Adw, GLib, Gio, GObject, Gdk
from typing import Optional, List, Dict, Any
import os

@Gtk.Template(resource_path='/org/gnome/paru-gui/window.ui')
class ParuGuiWindow(Gtk.ApplicationWindow):
    __gtype_name__ = 'ParuGuiWindow'

    # Template Children - Definições básicas
    header_bar = Gtk.Template.Child()
    app_menu_button = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()
    help_button = Gtk.Template.Child()
    main_stack = Gtk.Template.Child()
    welcome_screen = Gtk.Template.Child()
    select_file_button = Gtk.Template.Child()
    select_folder_button = Gtk.Template.Child()
    recent_dirs_label = Gtk.Template.Child()
    recent_dirs_flowbox = Gtk.Template.Child()
    content_view = Gtk.Template.Child()
    content_cards = Gtk.Template.Child()
    action_bar = Gtk.Template.Child()
    back_button = Gtk.Template.Child()
    status_label = Gtk.Template.Child()
    processing_screen = Gtk.Template.Child()
    processing_label = Gtk.Template.Child()
    processing_spinner = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        print("🚀 Inicializando ParuGuiWindow...")

        # Estado da aplicação
        self.current_view = "welcome"
        self.current_folder = None
        self.content_manager = None

        # Configuração inicial
        self._setup_window()
        self._setup_theme()
        self._connect_signals()
        self._setup_actions()
        self._init_components()

        # Mostrar tela inicial
        self.show_welcome_screen()

        print("✅ ParuGuiWindow inicializada com sucesso!")

    def _setup_window(self):
        """Configuração básica da janela"""
        try:
            print("🔧 Configurando janela...")

            # Título da janela
            self.set_title("Paru GUI")

            # Tamanho inicial
            self.set_default_size(1200, 800)

            # Permitir redimensionamento
            self.set_resizable(True)

            print("✅ Janela configurada")

        except Exception as e:
            print(f"❌ Erro ao configurar janela: {e}")

    def _setup_theme(self):
        """Configura tema padrão do sistema sem CSS customizado"""
        try:
            print("🎨 Configurando tema padrão do sistema...")

            # Usar o tema padrão do sistema
            style_manager = Adw.StyleManager.get_default()

            # Detectar preferência do sistema (claro/escuro)
            # Deixar o sistema decidir automaticamente
            style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

            print("✅ Tema padrão do sistema aplicado")

        except Exception as e:
            print(f"⚠️ Aviso: Erro ao configurar tema: {e}")
            # Continua mesmo sem configuração de tema

    def _connect_signals(self):
        """Conecta sinais dos widgets"""
        try:
            print("🔧 Conectando sinais...")

            # Botões principais
            if self.select_file_button:
                self.select_file_button.connect('clicked', self.on_select_file_clicked)

            if self.select_folder_button:
                self.select_folder_button.connect('clicked', self.on_select_folder_clicked)

            if self.back_button:
                self.back_button.connect('clicked', self.on_back_button_clicked)

            # Entrada de pesquisa
            if self.search_entry:
                self.search_entry.connect('search-changed', self.on_search_changed)

            # Botão de ajuda
            if self.help_button:
                self.help_button.connect('clicked', self.on_help_button_clicked)

            # Sinal de fechamento da janela
            self.connect('close-request', self.on_close_request)

            print("✅ Sinais conectados com sucesso")

        except Exception as e:
            print(f"❌ Erro ao conectar sinais: {e}")

    def _setup_actions(self):
        """Configura ações da aplicação"""
        try:
            print("🔧 Configurando ações...")

            # Ação de preferências
            preferences_action = Gio.SimpleAction.new("preferences", None)
            preferences_action.connect("activate", self.on_preferences_action)
            self.add_action(preferences_action)

            # Ação de sobre
            about_action = Gio.SimpleAction.new("about", None)
            about_action.connect("activate", self.on_about_action)
            self.add_action(about_action)

            # Ação de sair
            quit_action = Gio.SimpleAction.new("quit", None)
            quit_action.connect("activate", self.on_quit_action)
            self.add_action(quit_action)

            print("✅ Ações configuradas")

        except Exception as e:
            print(f"❌ Erro ao configurar ações: {e}")

    def _init_components(self):
        """Inicializa componentes da interface"""
        try:
            print("🔧 Inicializando componentes...")

            # Verificar disponibilidade dos widgets
            self._debug_widgets()

            # Inicializar manager de conteúdo se existir
            try:
                from .ui.managers.content_view_manager import ContentViewManager
                self.content_manager = ContentViewManager(self)
            except ImportError:
                print("⚠️ ContentViewManager não encontrado - usando implementação básica")

            print("✅ Componentes inicializados")

        except Exception as e:
            print(f"❌ Erro ao inicializar componentes: {e}")

    def show_welcome_screen(self):
        """Mostra a tela de boas-vindas"""
        try:
            print("🏠 Mostrando tela de boas-vindas...")

            if self.main_stack and self.welcome_screen:
                self.welcome_screen.set_visible(True)
                self.main_stack.set_visible_child(self.welcome_screen)
                self.current_view = "welcome"

                # Configurar componentes da tela de boas-vindas
                self._setup_welcome_components()

                print("✅ Tela de boas-vindas ativa")
            else:
                print("❌ ERRO: main_stack ou welcome_screen é nulo!")

        except Exception as e:
            print(f"❌ Erro ao mostrar tela de boas-vindas: {e}")

    def _setup_welcome_components(self):
        """Configura componentes da tela de boas-vindas"""
        try:
            # Configurar botões com estilo padrão
            if self.select_file_button:
                self.select_file_button.add_css_class("pill")
                self.select_file_button.add_css_class("suggested-action")

            if self.select_folder_button:
                self.select_folder_button.add_css_class("pill")

            print("✅ Componentes de boas-vindas configurados")

        except Exception as e:
            print(f"❌ Erro ao configurar componentes de boas-vindas: {e}")

    def show_content_view(self, folder_path: Optional[str] = None):
        """Mostra a visualização de conteúdo"""
        try:
            print("📁 Mostrando visualização de conteúdo...")

            if self.main_stack and self.content_view:
                self.content_view.set_visible(True)
                self.main_stack.set_visible_child(self.content_view)
                self.current_view = "content"

                if folder_path:
                    self.current_folder = folder_path
                    self._update_content_view(folder_path)

                print("✅ Visualização de conteúdo ativa")
            else:
                print("❌ ERRO: main_stack ou content_view é nulo!")

        except Exception as e:
            print(f"❌ Erro ao mostrar visualização de conteúdo: {e}")

    def show_processing_screen(self, message: str = "Processing..."):
        """Mostra a tela de processamento"""
        try:
            print(f"⚙️ Mostrando tela de processamento: {message}")

            if self.main_stack and self.processing_screen:
                self.processing_screen.set_visible(True)
                self.main_stack.set_visible_child(self.processing_screen)
                self.current_view = "processing"

                if self.processing_label:
                    self.processing_label.set_text(message)

                if self.processing_spinner:
                    self.processing_spinner.start()

                print("✅ Tela de processamento ativa")
            else:
                print("❌ ERRO: main_stack ou processing_screen é nulo!")

        except Exception as e:
            print(f"❌ Erro ao mostrar tela de processamento: {e}")

    def _update_content_view(self, folder_path: str):
        """Atualiza a visualização de conteúdo"""
        try:
            print(f"🔄 Atualizando visualização de conteúdo: {folder_path}")

            # Usar content manager se disponível
            if self.content_manager:
                self.content_manager.load_folder_content(folder_path)
            else:
                print("⚠️ Content manager não disponível")

            # Atualizar status
            if self.status_label:
                self.status_label.set_text(f"Pasta: {folder_path}")

        except Exception as e:
            print(f"❌ Erro ao atualizar visualização: {e}")

    def _debug_widgets(self):
        """Debug dos widgets principais"""
        print("👀 Verificando widgets...")

        widgets = [
            'main_stack', 'welcome_screen', 'header_bar',
            'select_file_button', 'select_folder_button'
        ]

        for widget_name in widgets:
            widget = getattr(self, widget_name, None)
            if widget:
                print(f"  ✅ {widget_name}: OK")
            else:
                print(f"  ❌ {widget_name}: não encontrado")

    # ===== HANDLERS DE EVENTOS =====

    def on_select_file_clicked(self, button):
        """Handler para seleção de arquivo"""
        print("📄 Seleção de arquivo solicitada")
        # Implementar seleção de arquivo

    def on_select_folder_clicked(self, button):
        """Handler para seleção de pasta"""
        print("📂 Seleção de pasta solicitada")
        # Implementar seleção de pasta

    def on_back_button_clicked(self, button):
        """Handler para botão voltar"""
        print("◀️ Botão voltar pressionado")
        self.show_welcome_screen()

    def on_search_changed(self, search_entry):
        """Handler para mudanças na pesquisa"""
        query = search_entry.get_text()
        print(f"🔍 Pesquisa alterada: {query}")
        # Implementar lógica de pesquisa

    def on_help_button_clicked(self, button):
        """Handler para botão de ajuda"""
        print("❓ Ajuda solicitada")
        # Implementar diálogo de ajuda

    def on_preferences_action(self, action, parameter):
        """Handler para ação de preferências"""
        print("⚙️ Preferências solicitadas")
        # Implementar diálogo de preferências

    def on_about_action(self, action, parameter):
        """Handler para ação sobre"""
        print("ℹ️ Sobre solicitado")
        # Implementar diálogo sobre

    def on_quit_action(self, action, parameter):
        """Handler para ação sair"""
        print("🚪 Sair solicitado")
        self.close()

    def on_close_request(self, window):
        """Handler para fechamento da janela"""
        print("🚪 Solicitação de fechamento da janela")
        return False  # Permite o fechamento
