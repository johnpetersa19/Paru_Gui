# window.py - Janela Principal do Paru GUI v2.7.0
# Janela principal completa com integração a todos os módulos

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gio', '2.0')
gi.require_version('Gdk', '4.0')

from gi.repository import Gtk, Adw, Gio, Gdk, GLib, GObject
from typing import Optional, Dict, List, Any, Callable
from pathlib import Path
import threading
import asyncio
import json
import os
import sys

# Imports dos módulos da aplicação
try:
    from .paru_gui.preferences_manager import PreferencesManager
    from .paru_gui.file_utils import FileAnalyzer
    from .paru_gui.security_analyzer import SecurityAnalyzer
    from .paru_gui.upstream_checker import UpstreamChecker
    from .paru_gui.terminal_manager import TerminalManager
    from .paru_gui.history_manager import HistoryManager
    from .paru_gui.tour_guide import TourGuide
    from .paru_gui.error_handler import ErrorHandler
    from .paru_gui.sandboxing import SandboxManager
    from .paru_gui.pkgbuild_analyzer import PKGBUILDAnalyzer
    
    # UI Managers
    from .ui.managers.action_handlers import ActionHandlers
    from .ui.managers.content_view_manager import ContentViewManager
    from .ui.managers.ui_manager import UIManager
    from .ui.managers.search_manager import SearchManager
    from .ui.managers.preferences_dialog_manager import PreferencesDialogManager
    from .ui.managers.file_operations import FileOperations
    
    # UI Components
    from .ui.components.error_dialog import ErrorDialogComponent
    from .ui.components.help_overlay import HelpOverlayComponent
    from .ui.components.search_bar import SearchBarComponent
    
    # UI Screens
    from .ui.screens.welcome_screen import WelcomeScreenComponent
    from .ui.screens.content_view import ContentViewComponent
    from .ui.screens.pkgbuild_review_dialog import PKGBUILDReviewDialog
    from .ui.screens.upstream_update import UpstreamUpdateComponent

except ImportError as e:
    print(f"⚠️ Erro ao importar módulos: {e}")
    print("💡 Tentando importações alternativas...")
    try:
        # Core modules
        from paru_gui.preferences_manager import PreferencesManager
        from paru_gui.file_utils import FileAnalyzer
        from paru_gui.security_analyzer import SecurityAnalyzer
        from paru_gui.upstream_checker import UpstreamChecker
        from paru_gui.terminal_manager import TerminalManager
        from paru_gui.history_manager import HistoryManager
        from paru_gui.tour_guide import TourGuide
        from paru_gui.error_handler import ErrorHandler
        from paru_gui.sandboxing import SandboxManager
        from paru_gui.pkgbuild_analyzer import PKGBUILDAnalyzer
        
        # UI Managers
        from ui.managers.action_handlers import ActionHandlers
        from ui.managers.content_view_manager import ContentViewManager
        from ui.managers.ui_manager import UIManager
        from ui.managers.search_manager import SearchManager
        from ui.managers.preferences_dialog_manager import PreferencesDialogManager
        from ui.managers.file_operations import FileOperations
        
        # UI Components
        from ui.components.error_dialog import ErrorDialogComponent
        from ui.components.help_overlay import HelpOverlayComponent
        from ui.components.search_bar import SearchBarComponent
        
        # UI Screens
        from ui.screens.welcome_screen import WelcomeScreenComponent
        from ui.screens.content_view import ContentViewComponent
        from ui.screens.pkgbuild_review_dialog import PKGBUILDReviewDialog
        from ui.screens.upstream_update import UpstreamUpdateComponent
        
        print("✅ Módulos importados com sucesso")
        
    except ImportError as e2:
        print(f"❌ Importação alternativa falhou: {e2}")
        try:
            import sys
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            src_dir = os.path.join(current_dir, "src")
            if src_dir not in sys.path:
                sys.path.insert(0, src_dir)
            from paru_gui.preferences_manager import PreferencesManager
            from ui.managers.ui_manager import UIManager
            print("✅ Importação mínima realizada")
        except ImportError as e3:
            print(f"❌ Última tentativa falhou: {e3}")
            print("🔧 Criando classes mock...")
            class PreferencesManager:
                def __init__(self):
                    print("⚠️ Mock PreferencesManager inicializado")
            class UIManager:
                def __init__(self, window):
                    print("⚠️ Mock UIManager inicializado")
                    self.window = window


@Gtk.Template(resource_path='/org/gnome/paru-gui/window.ui')
class ParuGuiWindow(Gtk.ApplicationWindow):
    """
    Janela principal do Paru GUI v2.7.0
    Implementa todas as funcionalidades especificadas na estrutura do projeto
    """
    __gtype_name__ = 'ParuGuiWindow'

    # Template Children - Widgets principais do window.ui
    header_bar = Gtk.Template.Child()
    app_menu_button = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()
    help_button = Gtk.Template.Child()
    
    # Main Stack - controla as telas principais
    main_stack = Gtk.Template.Child()
    
    # Welcome Screen
    welcome_screen = Gtk.Template.Child()
    select_file_button = Gtk.Template.Child()
    select_folder_button = Gtk.Template.Child()
    recent_dirs_label = Gtk.Template.Child()
    recent_dirs_flowbox = Gtk.Template.Child()
    
    # Content View 
    content_view = Gtk.Template.Child()
    content_cards = Gtk.Template.Child()
    action_bar = Gtk.Template.Child()
    back_button = Gtk.Template.Child()
    status_label = Gtk.Template.Child()
    action_button = Gtk.Template.Child()
    
    # Processing Screen
    processing_screen = Gtk.Template.Child()
    processing_label = Gtk.Template.Child()
    processing_spinner = Gtk.Template.Child()
    processing_progress = Gtk.Template.Child()
    log_textview = Gtk.Template.Child()
    cancel_button = Gtk.Template.Child()
    details_button = Gtk.Template.Child()
    
    # Upstream Updates View (nova tela v2.7.0)
    upstream_updates_view = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        print("🚀 Inicializando Paru GUI Window v2.7.0...")
        
        # Estado da aplicação
        self.current_view = "welcome"
        self.current_folder = None
        self.current_file = None
        self.processing_task = None
        self.is_simplified_mode = True
        
        # Managers e componentes
        self.preferences_manager = None
        self.file_analyzer = None
        self.security_analyzer = None
        self.upstream_checker = None
        self.terminal_manager = None
        self.history_manager = None
        self.tour_guide = None
        self.error_handler = None
        self.sandbox_manager = None
        self.pkgbuild_analyzer = None
        
        # UI Managers
        self.action_handlers = None
        self.content_manager = None
        self.ui_manager = None
        self.search_manager = None
        self.preferences_dialog_manager = None
        self.file_operations = None
        
        # UI Components
        self.error_dialog_component = None
        self.help_overlay_component = None
        self.search_bar_component = None
        self.welcome_screen_component = None
        self.content_view_component = None
        self.upstream_update_component = None
        
        # Estado interno
        self.css_providers = []
        self.icon_fallbacks = {}
        self.selected_items = []
        self.recent_directories = []
        self.current_operation = None
        
        # Inicialização
        self._initialize_window()
        
        print("✅ Paru GUI Window v2.7.0 inicializada com sucesso!")

    def _initialize_window(self):
        """Inicialização completa da janela em etapas"""
        try:
            print("🔧 Configurando janela principal...")
            
            # 1. Configuração básica da janela
            self._setup_window_properties()
            
            # 2. Configuração de tema e CSS
            self._setup_theme_and_styling()
            
            # 3. Inicialização dos managers
            self._initialize_managers()
            
            # 4. Inicialização dos componentes UI
            self._initialize_ui_components()
            
            # 5. Configuração de ações e menu
            self._setup_actions_and_menu()
            
            # 6. Conexão de sinais
            self._connect_all_signals()
            
            # 7. Configuração inicial das telas
            self._setup_screens()
            
            # 8. Carregar preferências e estado
            self._load_state_and_preferences()
            
            # 9. Mostrar tela inicial
            self._show_initial_screen()
            
        except Exception as e:
            print(f"❌ Erro durante inicialização: {e}")
            self._handle_initialization_error(e)

    def _setup_window_properties(self):
        """Configuração básica das propriedades da janela"""
        try:
            print("  🏠 Configurando propriedades da janela...")
            
            # Título e identificação
            self.set_title("Paru GUI v2.7.0")
            self.set_application(self.get_application())
            
            # Tamanho e posição
            self.set_default_size(1200, 800)
            self.set_resizable(True)
            
            # Ícone da aplicação
            try:
                self.set_icon_name("org.gnome.paru-gui")
            except:
                self.set_icon_name("system-software-install")
            
            print("    ✅ Propriedades configuradas")
            
        except Exception as e:
            print(f"    ❌ Erro ao configurar propriedades: {e}")

    def _setup_theme_and_styling(self):
        """Configuração de tema e CSS"""
        try:
            print("  🎨 Configurando tema e estilos...")
            
            # Gerenciador de estilo Adwaita
            style_manager = Adw.StyleManager.get_default()
            style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
            
            # Carregar CSS principal
            css_files = [
                "/org/gnome/paru-gui/ui/style.css",
                "/org/gnome/paru-gui/ui/image_fixes.css", 
                "/org/gnome/paru-gui/ui/screens/pkgbuild-review.css"
            ]
            
            for css_file in css_files:
                self._load_css_provider(css_file)
            
            # Configurar fallbacks de ícones
            self._setup_icon_fallbacks()
            
            print("    ✅ Tema configurado")
            
        except Exception as e:
            print(f"    ❌ Erro ao configurar tema: {e}")

    def _load_css_provider(self, resource_path: str, priority: int = Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION):
        """Carrega um provider CSS"""
        try:
            css_provider = Gtk.CssProvider()
            css_provider.load_from_resource(resource_path)
            
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                priority
            )
            
            self.css_providers.append(css_provider)
            print(f"    📝 CSS carregado: {resource_path}")
            
        except Exception as e:
            print(f"    ❌ Erro ao carregar CSS {resource_path}: {e}")

    def _setup_icon_fallbacks(self):
        """Configura fallbacks para ícones"""
        try:
            icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            
            fallback_map = {
                "system-software-install-symbolic": ["software-install-symbolic", "package-install-symbolic"],
                "text-x-generic-symbolic": ["document-text-symbolic", "text-x-generic"],
                "package-x-generic-symbolic": ["package-symbolic", "application-x-rpm"],
                "text-x-patch-symbolic": ["document-edit-symbolic", "text-x-patch"],
                "applications-system-symbolic": ["preferences-system-symbolic", "system-run-symbolic"],
                "security-high-symbolic": ["security-high", "dialog-password-symbolic"],
                "security-low-symbolic": ["security-low", "dialog-warning-symbolic"],
                "security-medium-symbolic": ["security-medium", "dialog-information-symbolic"]
            }
            
            for original, fallbacks in fallback_map.items():
                if not icon_theme.has_icon(original):
                    for fallback in fallbacks:
                        if icon_theme.has_icon(fallback):
                            self.icon_fallbacks[original] = fallback
                            break
                    else:
                        self.icon_fallbacks[original] = "image-missing"
            
            print("    ✅ Fallbacks de ícones configurados")
            
        except Exception as e:
            print(f"    ❌ Erro ao configurar fallbacks: {e}")

    def _initialize_managers(self):
        """Inicializa todos os managers do sistema"""
        try:
            print("  🔧 Inicializando managers...")
            
            # Core managers
            self.preferences_manager = PreferencesManager()
            self.error_handler = ErrorHandler(self)
            self.history_manager = HistoryManager()
            self.terminal_manager = TerminalManager()
            
            # Analyzers
            self.file_analyzer = FileAnalyzer()
            self.security_analyzer = SecurityAnalyzer()
            self.pkgbuild_analyzer = PKGBUILDAnalyzer()
            self.upstream_checker = UpstreamChecker()
            
            # Sandbox e Tour
            self.sandbox_manager = SandboxManager()
            self.tour_guide = TourGuide(self)
            
            print("    ✅ Core managers inicializados")
            
        except Exception as e:
            print(f"    ❌ Erro ao inicializar managers: {e}")

    def _initialize_ui_components(self):
        """Inicializa componentes da interface"""
        try:
            print("  🖼️ Inicializando componentes UI...")
            
            # UI Managers
            self.ui_manager = UIManager(self)
            self.action_handlers = ActionHandlers(self)
            self.content_manager = ContentViewManager(self)
            self.search_manager = SearchManager(self)
            self.preferences_dialog_manager = PreferencesDialogManager(self)
            self.file_operations = FileOperations(self)
            
            # UI Components
            self.error_dialog_component = ErrorDialogComponent(self)
            self.help_overlay_component = HelpOverlayComponent(self)
            self.search_bar_component = SearchBarComponent(self.search_entry)
            
            # Screen Components
            self.welcome_screen_component = WelcomeScreenComponent(self.welcome_screen, self)
            self.content_view_component = ContentViewComponent(self.content_view, self)
            self.upstream_update_component = UpstreamUpdateComponent(self.upstream_updates_view, self)
            
            print("    ✅ Componentes UI inicializados")
            
        except Exception as e:
            print(f"    ❌ Erro ao inicializar componentes UI: {e}")

    def _setup_actions_and_menu(self):
        """Configura ações da aplicação e menu"""
        try:
            print("  📋 Configurando ações e menu...")
            
            # Ações do Sistema
            system_actions = [
                ("system-stats", self._on_system_stats),
                ("arch-news", self._on_arch_news),
                ("clear-cache", self._on_clear_cache),
                ("update-system", self._on_update_system),
                ("check-upstream", self._on_check_upstream_updates),
                ("tour", self._on_tour_initial)
            ]
            
            # Ações de Preferências
            preference_actions = [
                ("preferences", self._on_preferences),
                ("default-editor", None),  # Handled by preferences dialog
                ("upstream-settings", None),
                ("trust-settings", None),
                ("simplified-mode", self._on_toggle_simplified_mode),
                ("developer-mode", self._on_toggle_developer_mode)
            ]
            
            # Ações de Histórico
            history_actions = [
                ("action-history", self._on_action_history),
                ("undo-action", self._on_undo_last_action),
                ("export-log", self._on_export_log)
            ]
            
            # Ações Gerais
            general_actions = [
                ("shortcuts", self._on_keyboard_shortcuts),
                ("about", self._on_about),
                ("quit", self._on_quit)
            ]
            
            # Registrar todas as ações
            all_actions = system_actions + preference_actions + history_actions + general_actions
            
            for action_name, callback in all_actions:
                action = Gio.SimpleAction.new(action_name, None)
                if callback:
                    action.connect("activate", callback)
                self.add_action(action)
            
            # Ações com estado (toggle)
            simplified_action = Gio.SimpleAction.new_stateful(
                "simplified-mode-toggle", 
                None, 
                GLib.Variant.new_boolean(self.is_simplified_mode)
            )
            simplified_action.connect("activate", self._on_toggle_simplified_mode)
            self.add_action(simplified_action)
            
            print("    ✅ Ações configuradas")
            
        except Exception as e:
            print(f"    ❌ Erro ao configurar ações: {e}")

    def _connect_all_signals(self):
        """Conecta todos os sinais da interface"""
        try:
            print("  🔗 Conectando sinais...")
            
            # Sinais da janela principal
            self.connect('close-request', self._on_close_request)
            
            # Sinais do header bar
            if self.search_entry:
                self.search_entry.connect('search-changed', self._on_search_changed)
                self.search_entry.connect('activate', self._on_search_activated)
                
            if self.help_button:
                self.help_button.connect('clicked', self._on_help_clicked)
            
            # Sinais da welcome screen
            if self.select_file_button:
                self.select_file_button.connect('clicked', self._on_select_file_clicked)
                
            if self.select_folder_button:
                self.select_folder_button.connect('clicked', self._on_select_folder_clicked)
                
            # Sinais da content view
            if self.back_button:
                self.back_button.connect('clicked', self._on_back_clicked)
                
            if self.action_button:
                self.action_button.connect('clicked', self._on_action_button_clicked)
            
            # Sinais da processing screen
            if self.cancel_button:
                self.cancel_button.connect('clicked', self._on_cancel_processing)
                
            if self.details_button:
                self.details_button.connect('clicked', self._on_show_processing_details)
            
            # Sinais de cards de conteúdo (serão conectados dinamicamente)
            if self.content_cards:
                self.content_cards.connect('child-activated', self._on_content_card_activated)
            
            print("    ✅ Sinais conectados")
            
        except Exception as e:
            print(f"    ❌ Erro ao conectar sinais: {e}")

    def _setup_screens(self):
        """Configura as telas da aplicação"""
        try:
            print("  📺 Configurando telas...")
            
            # Configurar welcome screen
            if self.welcome_screen_component:
                self.welcome_screen_component.setup()
                self._load_recent_directories()
            
            # Configurar content view
            if self.content_view_component:
                self.content_view_component.setup()
            
            # Configurar upstream updates view
            if self.upstream_update_component:
                self.upstream_update_component.setup()
            
            print("    ✅ Telas configuradas")
            
        except Exception as e:
            print(f"    ❌ Erro ao configurar telas: {e}")

    def _load_state_and_preferences(self):
        """Carrega estado da aplicação e preferências"""
        try:
            print("  💾 Carregando estado e preferências...")
            
            if self.preferences_manager:
                # Carregar preferências
                prefs = self.preferences_manager.get_all_preferences()
                
                # Aplicar modo simplificado
                self.is_simplified_mode = prefs.get('simplified_mode', True)
                self._update_simplified_mode()
                
                # Carregar diretórios recentes
                self.recent_directories = prefs.get('recent_directories', [])
                
                # Configurar editor padrão
                default_editor = prefs.get('default_editor', 'gedit')
                os.environ['EDITOR'] = default_editor
                
                print(f"    📂 {len(self.recent_directories)} diretórios recentes carregados")
                print(f"    🔧 Editor padrão: {default_editor}")
                print(f"    🎯 Modo simplificado: {'Ativo' if self.is_simplified_mode else 'Inativo'}")
            
            print("    ✅ Estado carregado")
            
        except Exception as e:
            print(f"    ❌ Erro ao carregar estado: {e}")

    def _show_initial_screen(self):
        """Mostra a tela inicial apropriada"""
        try:
            print("  🎬 Mostrando tela inicial...")
            
            # Verificar se deve mostrar tour para novos usuários
            if self.preferences_manager and self.preferences_manager.is_first_run():
                self._show_tour_dialog()
            else:
                self.show_welcome_screen()
            
            print("    ✅ Tela inicial mostrada")
            
        except Exception as e:
            print(f"    ❌ Erro ao mostrar tela inicial: {e}")

    # ===== MÉTODOS DE NAVEGAÇÃO ENTRE TELAS =====
    
    def show_welcome_screen(self):
        """Mostra a tela de boas-vindas"""
        try:
            print("🏠 Mostrando tela de boas-vindas...")
            
            if self.main_stack and self.welcome_screen:
                self.main_stack.set_visible_child_name("welcome")
                self.current_view = "welcome"
                
                # Atualizar header bar
                self._update_header_for_welcome()
                
                # Atualizar lista de diretórios recentes
                self._update_recent_directories_display()
                
                print("✅ Tela de boas-vindas ativa")
            
        except Exception as e:
            print(f"❌ Erro ao mostrar tela de boas-vindas: {e}")

    def show_content_view(self, path: str):
        """Mostra a visualização de conteúdo"""
        try:
            print(f"📁 Mostrando visualização de conteúdo: {path}")
            
            if self.main_stack and self.content_view:
                self.main_stack.set_visible_child_name("content")
                self.current_view = "content"
                self.current_folder = path
                
                # Adicionar aos recentes
                self._add_to_recent_directories(path)
                
                # Atualizar header bar
                self._update_header_for_content()
                
                # Carregar conteúdo
                if self.content_manager:
                    self.content_manager.load_content(path)
                
                print("✅ Visualização de conteúdo ativa")
            
        except Exception as e:
            print(f"❌ Erro ao mostrar visualização de conteúdo: {e}")

    def show_processing_screen(self, operation: str, description: str = "Processing..."):
        """Mostra a tela de processamento"""
        try:
            print(f"⚙️ Mostrando tela de processamento: {operation}")
            
            if self.main_stack and self.processing_screen:
                self.main_stack.set_visible_child_name("processing")
                self.current_view = "processing"
                self.current_operation = operation
                
                # Configurar elementos da tela
                if self.processing_label:
                    self.processing_label.set_text(description)
                
                if self.processing_spinner:
                    self.processing_spinner.start()
                
                if self.processing_progress:
                    self.processing_progress.set_fraction(0.0)
                    self.processing_progress.set_text("Starting...")
                
                # Limpar log
                if self.log_textview:
                    buffer = self.log_textview.get_buffer()
                    buffer.set_text("")
                
                # Atualizar header bar
                self._update_header_for_processing()
                
                print("✅ Tela de processamento ativa")
            
        except Exception as e:
            print(f"❌ Erro ao mostrar tela de processamento: {e}")

    def show_upstream_updates(self, updates: List[Dict]):
        """Mostra a tela de atualizações upstream"""
        try:
            print(f"🆙 Mostrando atualizações upstream: {len(updates)} disponíveis")
            
            if self.main_stack and self.upstream_updates_view:
                self.main_stack.set_visible_child_name("upstream_updates")
                self.current_view = "upstream_updates"
                
                # Carregar dados de atualizações
                if self.upstream_update_component:
                    self.upstream_update_component.load_updates(updates)
                
                # Atualizar header bar
                self._update_header_for_upstream()
                
                print("✅ Tela de atualizações upstream ativa")
            
        except Exception as e:
            print(f"❌ Erro ao mostrar tela de atualizações upstream: {e}")

    # ===== HANDLERS DE EVENTOS DA UI =====
    
    def _on_select_file_clicked(self, button):
        """Handler para seleção de arquivo"""
        print("📄 Seleção de arquivo solicitada")
        
        if self.file_operations:
            self.file_operations.select_file(
                callback=self._on_file_selected,
                file_filters=[
                    ("PKGBUILD Files", ["PKGBUILD"]),
                    ("Package Files", ["*.pkg.tar.xz", "*.pkg.tar.zst"]),
                    ("Patch Files", ["*.patch", "*.diff"]),
                    ("All Files", ["*"])
                ]
            )

    def _on_select_folder_clicked(self, button):
        """Handler para seleção de pasta"""
        print("📂 Seleção de pasta solicitada")
        
        if self.file_operations:
            self.file_operations.select_folder(
                callback=self._on_folder_selected
            )

    def _on_file_selected(self, file_path: str):
        """Callback quando arquivo é selecionado"""
        print(f"📄 Arquivo selecionado: {file_path}")
        
        self.current_file = file_path
        
        # Determinar ação baseada no tipo de arquivo
        if file_path.endswith('PKGBUILD'):
            self._handle_pkgbuild_file(file_path)
        elif file_path.endswith(('.pkg.tar.xz', '.pkg.tar.zst')):
            self._handle_package_file(file_path)
        elif file_path.endswith(('.patch', '.diff')):
            self._handle_patch_file(file_path)
        else:
            self._handle_generic_file(file_path)

    def _on_folder_selected(self, folder_path: str):
        """Callback quando pasta é selecionada"""
        print(f"📂 Pasta selecionada: {folder_path}")
        
        self.show_processing_screen("folder_analysis", "Analyzing folder contents...")
        
        # Analisar conteúdo da pasta em thread separada
        def analyze_folder():
            try:
                if self.file_analyzer:
                    content = self.file_analyzer.analyze_folder(folder_path)
                    GLib.idle_add(self._on_folder_analyzed, folder_path, content)
            except Exception as e:
                GLib.idle_add(self._on_folder_analysis_error, str(e))
        
        threading.Thread(target=analyze_folder, daemon=True).start()

    def _on_folder_analyzed(self, folder_path: str, content: Dict):
        """Callback quando análise da pasta é concluída"""
        print(f"✅ Análise da pasta concluída: {len(content.get('items', []))} itens encontrados")
        
        # Mostrar visualização de conteúdo
        self.show_content_view(folder_path)

    def _on_folder_analysis_error(self, error_message: str):
        """Callback quando análise da pasta falha"""
        print(f"❌ Erro na análise da pasta: {error_message}")
        
        self.show_welcome_screen()
        self.show_error("Folder Analysis Error", f"Failed to analyze folder: {error_message}")

    def _on_search_changed(self, search_entry):
        """Handler para mudanças na pesquisa"""
        query = search_entry.get_text().strip()
        
        if len(query) >= 2:  # Pesquisa mínima de 2 caracteres
            print(f"🔍 Pesquisa: {query}")
            
            if self.search_manager:
                self.search_manager.search_packages(query)
        elif len(query) == 0:
            # Limpar resultados da pesquisa
            if self.search_manager:
                self.search_manager.clear_search()

    def _on_search_activated(self, search_entry):
        """Handler quando pesquisa é ativada (Enter pressionado)"""
        query = search_entry.get_text().strip()
        
        if query:
            print(f"🎯 Pesquisa ativada: {query}")
            
            if self.search_manager:
                self.search_manager.execute_search(query)

    def _on_help_clicked(self, button):
        """Handler para botão de ajuda"""
        print("❓ Ajuda solicitada")
        
        if self.help_overlay_component:
            self.help_overlay_component.show()

    def _on_back_clicked(self, button):
        """Handler para botão voltar"""
        print("◀️ Voltando para tela anterior")
        
        # Determinar tela anterior baseada no contexto
        if self.current_view == "content":
            self.show_welcome_screen()
        elif self.current_view == "upstream_updates":
            if self.current_folder:
                self.show_content_view(self.current_folder)
            else:
                self.show_welcome_screen()
        elif self.current_view == "processing":
            # Cancelar operação se possível
            self._on_cancel_processing(None)
        else:
            self.show_welcome_screen()

    def _on_action_button_clicked(self, button):
        """Handler para botão de ação principal"""
        print("⚡ Ação principal solicitada")
        
        if self.action_handlers:
            # Determinar ação baseada no contexto atual
            if self.current_view == "content" and self.selected_items:
                self.action_handlers.execute_primary_action(self.selected_items[0])
            else:
                print("⚠️ Nenhuma ação definida para o contexto atual")

    def _on_content_card_activated(self, flowbox, child):
        """Handler quando card de conteúdo é ativado"""
        try:
            # Obter item associado ao card
            item_data = child.get_data("item_data")
            if item_data:
                print(f"🎯 Card ativado: {item_data.get('name', 'Unknown')}")
                
                if self.action_handlers:
                    self.action_handlers.handle_item_activation(item_data)
                
        except Exception as e:
            print(f"❌ Erro ao processar ativação do card: {e}")

    def _on_cancel_processing(self, button):
        """Handler para cancelar processamento"""
        print("🛑 Cancelamento de processamento solicitado")
        
        if self.processing_task:
            try:
                # Tentar cancelar a tarefa atual
                if hasattr(self.processing_task, 'cancel'):
                    self.processing_task.cancel()
                
                print("✅ Processamento cancelado")
                
                # Voltar à tela anterior
                if self.current_folder:
                    self.show_content_view(self.current_folder)
                else:
                    self.show_welcome_screen()
                    
            except Exception as e:
                print(f"❌ Erro ao cancelar processamento: {e}")

    def _on_show_processing_details(self, button):
        """Handler para mostrar detalhes do processamento"""
        print("📋 Detalhes do processamento solicitados")
        
        # Expandir área de log ou abrir janela de detalhes
        if self.log_textview:
            parent = self.log_textview.get_parent()
            if parent and hasattr(parent, 'set_policy'):
                parent.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

    # ===== HANDLERS DE AÇÕES DO MENU =====
    
    def _on_system_stats(self, action, param):
        """Handler para estatísticas do sistema"""
        print("📊 Estatísticas do sistema solicitadas")
        
        # Implementar diálogo de estatísticas
        self._show_system_stats_dialog()

    def _on_arch_news(self, action, param):
        """Handler para notícias do Arch"""
        print("📰 Notícias do Arch Linux solicitadas")
        
        # Implementar visualizador de notícias
        self._show_arch_news_dialog()

    def _on_clear_cache(self, action, param):
        """Handler para limpar cache"""
        print("🗑️ Limpeza de cache solicitada")
        
        self._execute_system_operation("clear_cache", "Clearing package cache...")

    def _on_update_system(self, action, param):
        """Handler para atualizar sistema"""
        print("🔄 Atualização do sistema solicitada")
        
        # Confirmar antes de atualizar
        dialog = self._create_confirmation_dialog(
            "System Update",
            "This will update your system packages. Continue?",
            callback=lambda: self._execute_system_operation("system_update", "Updating system...")
        )
        dialog.present()

    def _on_check_upstream_updates(self, action, param):
        """Handler para verificar atualizações upstream"""
        print("🔍 Verificação de atualizações upstream solicitada")
        
        self.show_processing_screen("upstream_check", "Checking for upstream updates...")
        
        def check_updates():
            try:
                if self.upstream_checker:
                    updates = self.upstream_checker.check_all_packages()
                    GLib.idle_add(self._on_upstream_updates_found, updates)
            except Exception as e:
                GLib.idle_add(self._on_upstream_check_error, str(e))
        
        threading.Thread(target=check_updates, daemon=True).start()

    def _on_upstream_updates_found(self, updates: List[Dict]):
        """Callback quando atualizações upstream são encontradas"""
        if updates:
            print(f"🆙 {len(updates)} atualizações upstream encontradas")
            self.show_upstream_updates(updates)
        else:
            print("✅ Nenhuma atualização upstream encontrada")
            self.show_welcome_screen()
            self.show_info("No Updates", "All packages are up to date with upstream.")

    def _on_upstream_check_error(self, error_message: str):
        """Callback quando verificação upstream falha"""
        print(f"❌ Erro na verificação upstream: {error_message}")
        self.show_welcome_screen()
        self.show_error("Update Check Failed", error_message)

    def _on_tour_initial(self, action, param):
        """Handler para tour inicial"""
        print("🗺️ Tour inicial solicitado")
        
        if self.tour_guide:
            self.tour_guide.start_tour()

    def _on_preferences(self, action, param):
        """Handler para preferências"""
        print("⚙️ Preferências solicitadas")
        
        if self.preferences_dialog_manager:
            self.preferences_dialog_manager.show_dialog()

    def _on_toggle_simplified_mode(self, action, param):
        """Handler para alternar modo simplificado"""
        self.is_simplified_mode = not self.is_simplified_mode
        
        print(f"🎯 Modo simplificado: {'Ativado' if self.is_simplified_mode else 'Desativado'}")
        
        # Salvar preferência
        if self.preferences_manager:
            self.preferences_manager.set_preference('simplified_mode', self.is_simplified_mode)
        
        # Atualizar UI
        self._update_simplified_mode()

    def _on_toggle_developer_mode(self, action, param):
        """Handler para alternar modo desenvolvedor"""
        is_developer = self.preferences_manager.get_preference('developer_mode', False) if self.preferences_manager else False
        is_developer = not is_developer
        
        print(f"👨‍💻 Modo desenvolvedor: {'Ativado' if is_developer else 'Desativado'}")
        
        if self.preferences_manager:
            self.preferences_manager.set_preference('developer_mode', is_developer)
        
        # Atualizar UI baseada no modo desenvolvedor
        self._update_developer_mode(is_developer)

    def _on_action_history(self, action, param):
        """Handler para histórico de ações"""
        print("📚 Histórico de ações solicitado")
        
        if self.history_manager:
            self._show_action_history_dialog()

    def _on_undo_last_action(self, action, param):
        """Handler para desfazer última ação"""
        print("↶ Desfazer última ação solicitado")
        
        if self.history_manager:
            if self.history_manager.can_undo():
                self.history_manager.undo_last_action()
                self.show_info("Action Undone", "Last action has been undone.")
            else:
                self.show_info("Nothing to Undo", "No recent actions to undo.")

    def _on_export_log(self, action, param):
        """Handler para exportar log"""
        print("📤 Exportação de log solicitada")
        
        if self.file_operations:
            self.file_operations.export_log()

    def _on_keyboard_shortcuts(self, action, param):
        """Handler para atalhos de teclado"""
        print("⌨️ Atalhos de teclado solicitados")
        
        if self.help_overlay_component:
            self.help_overlay_component.show_shortcuts()

    def _on_about(self, action, param):
        """Handler para sobre"""
        print("ℹ️ Sobre solicitado")
        
        self._show_about_dialog()

    def _on_quit(self, action, param):
        """Handler para sair"""
        print("🚪 Saída solicitada")
        
        self.close()

    def _on_close_request(self, window):
        """Handler para solicitação de fechamento"""
        print("🚪 Solicitação de fechamento da janela")
        
        # Salvar estado antes de fechar
        self._save_window_state()
        
        # Cancelar operações em andamento
        if self.processing_task:
            try:
                self.processing_task.cancel()
            except:
                pass
        
        return False  # Permitir fechamento

    # ===== MÉTODOS AUXILIARES =====
    
    def _handle_pkgbuild_file(self, file_path: str):
        """Processa arquivo PKGBUILD"""
        print(f"📋 Processando PKGBUILD: {file_path}")
        
        # Analisar PKGBUILD
        if self.pkgbuild_analyzer:
            analysis = self.pkgbuild_analyzer.analyze(file_path)
            
            # Mostrar diálogo de revisão se necessário
            if analysis.get('needs_review', True):
                self._show_pkgbuild_review_dialog(file_path, analysis)
            else:
                # Ir direto para a pasta do arquivo
                folder_path = os.path.dirname(file_path)
                self.show_content_view(folder_path)

    def _handle_package_file(self, file_path: str):
        """Processa arquivo de pacote"""
        print(f"📦 Processando pacote: {file_path}")
        
        # Ir para a pasta do arquivo e destacar o pacote
        folder_path = os.path.dirname(file_path)
        self.show_content_view(folder_path)

    def _handle_patch_file(self, file_path: str):
        """Processa arquivo de patch"""
        print(f"🧩 Processando patch: {file_path}")
        
        # Ir para a pasta do arquivo
        folder_path = os.path.dirname(file_path)
        self.show_content_view(folder_path)

    def _handle_generic_file(self, file_path: str):
        """Processa arquivo genérico"""
        print(f"📄 Processando arquivo genérico: {file_path}")
        
        # Ir para a pasta do arquivo
        folder_path = os.path.dirname(file_path)
        self.show_content_view(folder_path)

    def _update_header_for_welcome(self):
        """Atualiza header bar para tela de boas-vindas"""
        if self.search_entry:
            self.search_entry.set_placeholder_text("Search packages...")

    def _update_header_for_content(self):
        """Atualiza header bar para visualização de conteúdo"""
        if self.search_entry:
            self.search_entry.set_placeholder_text("Search in folder...")

    def _update_header_for_processing(self):
        """Atualiza header bar para tela de processamento"""
        if self.search_entry:
            self.search_entry.set_sensitive(False)

    def _update_header_for_upstream(self):
        """Atualiza header bar para tela de atualizações upstream"""
        if self.search_entry:
            self.search_entry.set_placeholder_text("Search updates...")

    def _load_recent_directories(self):
        """Carrega diretórios recentes na welcome screen"""
        if self.recent_dirs_flowbox and self.recent_directories:
            # Limpar existentes
            child = self.recent_dirs_flowbox.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                self.recent_dirs_flowbox.remove(child)
                child = next_child
            
            # Adicionar diretórios recentes
            for dir_path in self.recent_directories[:6]:  # Máximo 6
                self._create_recent_dir_card(dir_path)

    def _create_recent_dir_card(self, dir_path: str):
        """Cria card para diretório recente"""
        try:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            card.add_css_class("card")
            card.set_size_request(200, 120)
            
            # Ícone da pasta
            icon = Gtk.Image.new_from_icon_name("folder-symbolic")
            icon.set_pixel_size(48)
            card.append(icon)
            
            # Nome da pasta
            name = os.path.basename(dir_path) or dir_path
            label = Gtk.Label(label=name)
            label.add_css_class("heading")
            label.set_ellipsize(3)  # ELLIPSIZE_END
            card.append(label)
            
            # Path completo (menor)
            path_label = Gtk.Label(label=dir_path)
            path_label.add_css_class("caption")
            path_label.add_css_class("dim-label")
            path_label.set_ellipsize(3)
            card.append(path_label)
            
            # Tornar clicável
            click_controller = Gtk.GestureClick()
            click_controller.connect('pressed', lambda gesture, n_press, x, y: self.show_content_view(dir_path))
            card.add_controller(click_controller)
            
            # Adicionar ao flowbox
            self.recent_dirs_flowbox.append(card)
            
        except Exception as e:
            print(f"❌ Erro ao criar card de diretório recente: {e}")

    def _add_to_recent_directories(self, path: str):
        """Adiciona diretório à lista de recentes"""
        if path in self.recent_directories:
            self.recent_directories.remove(path)
        
        self.recent_directories.insert(0, path)
        
        # Manter apenas os 10 mais recentes
        self.recent_directories = self.recent_directories[:10]
        
        # Salvar nas preferências
        if self.preferences_manager:
            self.preferences_manager.set_preference('recent_directories', self.recent_directories)

    def _update_recent_directories_display(self):
        """Atualiza exibição de diretórios recentes"""
        self._load_recent_directories()

    def _update_simplified_mode(self):
        """Atualiza UI baseada no modo simplificado"""
        # Esconder/mostrar elementos baseado no modo
        if self.is_simplified_mode:
            # Esconder opções avançadas
            print("🎯 Aplicando modo simplificado")
        else:
            # Mostrar todas as opções
            print("🔧 Aplicando modo completo")
        
        # Atualizar estado da ação
        action = self.lookup_action("simplified-mode-toggle")
        if action:
            action.set_state(GLib.Variant.new_boolean(self.is_simplified_mode))

    def _update_developer_mode(self, enabled: bool):
        """Atualiza UI baseada no modo desenvolvedor"""
        if enabled:
            print("👨‍💻 Modo desenvolvedor ativado")
            # Mostrar opções avançadas de desenvolvimento
        else:
            print("👥 Modo usuário ativado")
            # Esconder opções de desenvolvimento

    def _execute_system_operation(self, operation: str, description: str):
        """Executa operação do sistema"""
        print(f"⚙️ Executando operação: {operation}")
        
        self.show_processing_screen(operation, description)
        
        def execute_operation():
            try:
                if self.terminal_manager:
                    success = self.terminal_manager.execute_system_operation(operation)
                    GLib.idle_add(self._on_system_operation_complete, operation, success)
            except Exception as e:
                GLib.idle_add(self._on_system_operation_error, operation, str(e))
        
        threading.Thread(target=execute_operation, daemon=True).start()

    def _on_system_operation_complete(self, operation: str, success: bool):
        """Callback quando operação do sistema é concluída"""
        if success:
            print(f"✅ Operação {operation} concluída com sucesso")
            self.show_welcome_screen()
            self.show_info("Operation Complete", f"{operation.replace('_', ' ').title()} completed successfully.")
        else:
            print(f"❌ Operação {operation} falhou")
            self.show_welcome_screen()
            self.show_error("Operation Failed", f"{operation.replace('_', ' ').title()} failed.")

    def _on_system_operation_error(self, operation: str, error_message: str):
        """Callback quando operação do sistema falha"""
        print(f"❌ Erro na operação {operation}: {error_message}")
        self.show_welcome_screen()
        self.show_error("System Operation Error", error_message)

    def _show_pkgbuild_review_dialog(self, file_path: str, analysis: Dict):
        """Mostra diálogo de revisão do PKGBUILD"""
        try:
            dialog = PKGBUILDReviewDialog(self, file_path, analysis)
            dialog.present()
        except Exception as e:
            print(f"❌ Erro ao mostrar diálogo de revisão: {e}")

    def _show_system_stats_dialog(self):
        """Mostra diálogo de estatísticas do sistema"""
        # Implementar diálogo de estatísticas
        pass

    def _show_arch_news_dialog(self):
        """Mostra diálogo de notícias do Arch"""
        # Implementar visualizador de notícias
        pass

    def _show_action_history_dialog(self):
        """Mostra diálogo de histórico de ações"""
        # Implementar diálogo de histórico
        pass

    def _show_about_dialog(self):
        """Mostra diálogo sobre"""
        try:
            dialog = Adw.AboutWindow(
                transient_for=self,
                application_name="Paru GUI",
                application_icon="org.gnome.paru-gui",
                version="2.7.0",
                developer_name="Paru GUI Team",
                copyright="© 2025 Paru GUI Team",
                license_type=Gtk.License.GPL_3_0,
                website="https://github.com/paru-gui-project",
                issue_url="https://github.com/paru-gui-project/paru-gui/issues"
            )
            
            dialog.set_comments("Manage AUR packages easily and securely")
            dialog.set_developers([
                "Paru GUI Team",
                "MiniMax Agent"
            ])
            
            dialog.present()
            
        except Exception as e:
            print(f"❌ Erro ao mostrar diálogo sobre: {e}")

    def _show_tour_dialog(self):
        """Mostra diálogo de tour inicial"""
        if self.tour_guide:
            self.tour_guide.show_welcome_tour()

    def _create_confirmation_dialog(self, title: str, message: str, callback: Callable = None):
        """Cria diálogo de confirmação"""
        try:
            dialog = Adw.MessageDialog.new(self, title)
            dialog.set_body(message)
            
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("confirm", "Confirm")
            dialog.set_response_appearance("confirm", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("cancel")
            
            def on_response(dialog, response):
                if response == "confirm" and callback:
                    callback()
                dialog.close()
            
            dialog.connect("response", on_response)
            return dialog
            
        except Exception as e:
            print(f"❌ Erro ao criar diálogo de confirmação: {e}")
            return None

    def _save_window_state(self):
        """Salva estado da janela"""
        try:
            if self.preferences_manager:
                # Salvar tamanho da janela
                width, height = self.get_default_size()
                self.preferences_manager.set_preference('window_width', width)
                self.preferences_manager.set_preference('window_height', height)
                
                # Salvar diretórios recentes
                self.preferences_manager.set_preference('recent_directories', self.recent_directories)
                
                print("💾 Estado da janela salvo")
                
        except Exception as e:
            print(f"❌ Erro ao salvar estado: {e}")

    def _handle_initialization_error(self, error: Exception):
        """Trata erros de inicialização"""
        print(f"❌ Erro crítico de inicialização: {error}")
        
        # Mostrar diálogo de erro crítico
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Initialization Error"
        )
        dialog.format_secondary_text(
            f"Failed to initialize Paru GUI: {error}\n\n"
            "Please check your installation and try again."
        )
        
        dialog.connect('response', lambda d, r: self.close())
        dialog.present()

    # ===== MÉTODOS PÚBLICOS PARA COMPONENTS =====
    
    def show_info(self, title: str, message: str):
        """Mostra diálogo de informação"""
        try:
            dialog = Adw.MessageDialog.new(self, title)
            dialog.set_body(message)
            dialog.add_response("ok", "OK")
            dialog.set_default_response("ok")
            dialog.present()
        except Exception as e:
            print(f"❌ Erro ao mostrar info: {e}")

    def show_warning(self, title: str, message: str):
        """Mostra diálogo de aviso"""
        try:
            dialog = Adw.MessageDialog.new(self, title)
            dialog.set_body(message)
            dialog.add_css_class("warning")
            dialog.add_response("ok", "OK")
            dialog.set_default_response("ok")
            dialog.present()
        except Exception as e:
            print(f"❌ Erro ao mostrar aviso: {e}")

    def show_error(self, title: str, message: str, details: str = None):
        """Mostra diálogo de erro"""
        try:
            if self.error_dialog_component:
                self.error_dialog_component.show_error(title, message, details)
            else:
                # Fallback básico
                dialog = Gtk.MessageDialog(
                    transient_for=self,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text=title
                )
                dialog.format_secondary_text(message)
                dialog.present()
        except Exception as e:
            print(f"❌ Erro ao mostrar erro: {e}")

    def update_processing_progress(self, fraction: float, text: str = None):
        """Atualiza progresso do processamento"""
        if self.processing_progress:
            self.processing_progress.set_fraction(fraction)
            if text:
                self.processing_progress.set_text(text)

    def append_processing_log(self, text: str):
        """Adiciona texto ao log de processamento"""
        if self.log_textview:
            buffer = self.log_textview.get_buffer()
            end_iter = buffer.get_end_iter()
            buffer.insert(end_iter, text + "\n")
            
            # Auto-scroll para o final
            mark = buffer.get_insert()
            self.log_textview.scroll_mark_onscreen(mark)

    def get_preferences_manager(self) -> Optional['PreferencesManager']:
        """Retorna o gerenciador de preferências"""
        return self.preferences_manager

    def get_current_folder(self) -> Optional[str]:
        """Retorna a pasta atual"""
        return self.current_folder

    def get_selected_items(self) -> List[Dict]:
        """Retorna itens selecionados"""
        return self.selected_items

    def set_selected_items(self, items: List[Dict]):
        """Define itens selecionados"""
        self.selected_items = items
        
        # Atualizar UI baseada na seleção
        self._update_ui_for_selection()

    def _update_ui_for_selection(self):
        """Atualiza UI baseada nos itens selecionados"""
        has_selection = len(self.selected_items) > 0
        
        if self.action_button:
            self.action_button.set_sensitive(has_selection)
            
            if has_selection:
                item = self.selected_items[0]
                item_type = item.get('type', 'unknown')
                
                # Definir texto do botão baseado no tipo
                if item_type == 'pkgbuild':
                    self.action_button.set_label("Compile")
                elif item_type == 'package':
                    self.action_button.set_label("Install")
                elif item_type == 'patch':
                    self.action_button.set_label("Apply")
                else:
                    self.action_button.set_label("Action")
            else:
                self.action_button.set_label("Action")


# Função auxiliar para debugging
def debug_print(message: str, level: str = "INFO"):
    """Print com nível de debug"""
    levels = {
        "DEBUG": "🔍",
        "INFO": "ℹ️",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "SUCCESS": "✅"
    }
    
    icon = levels.get(level, "📝")
    print(f"{icon} {message}")
