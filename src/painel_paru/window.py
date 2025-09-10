from gi.repository import Gtk, Gio, Adw
from .handlers import WindowHandlers
from .menu_manager import MenuManager
from .action_manager import ActionManager
from .navigation import NavigationManager
from .ui_builder import UI_Builder
from .terminal_manager import TerminalManager
from .preferences_manager import PreferencesManager
import gettext
_ = gettext.gettext

class PainelParuWindow(Adw.ApplicationWindow):
    """Janela principal configurada para sua estrutura atual"""
    def __init__(self, *args, **kwargs):
        # Inicializa traduções
        super().__init__(*args, **kwargs)

        # Configurações iniciais da janela
        self.set_title(_("Paru GUI"))
        self.set_default_size(1000, 700)

        # Inicializa estado da aplicação
        self._content_path = None
        self._current_state = None
        self._is_operation_running = False
        self._navigation_history = []

        # Inicializa os componentes
        self.menu_manager = MenuManager(self)
        self.action_manager = ActionManager(self)
        self.navigation_manager = NavigationManager(self)
        self.terminal_manager = TerminalManager(self)
        self.handlers = WindowHandlers(self)

        # Configura a interface - ARMAZENA A INSTÂNCIA DO UI_BUILDER
        self.ui_builder = UI_Builder(self)
        ui_components = self.ui_builder.build_main_interface()

        # Armazena os componentes sem criar referências circulares
        self._content_box = ui_components['content_box']
        self._toolbar_box = ui_components['toolbar_box']
        self._header_title = ui_components['header_title']
        self._header_bar = ui_components['header_bar']
        self._back_button = ui_components['back_button']
        self._open_folder_button = ui_components['open_folder_button']
        self._cancel_button = ui_components['cancel_button']
        self._terminal = ui_components['terminal']
        self._progress_bar = ui_components['progress_bar']
        self._terminal_box = ui_components['terminal_box']

        # Configura o estado inicial dos botões
        if self._back_button:
            self._back_button.set_sensitive(False)
        if self._open_folder_button:
            self._open_folder_button.set_sensitive(False)
        if self._cancel_button:
            self._cancel_button.set_visible(False)

        # CORREÇÃO: Usa o UI_BUILDER para carregar a tela inicial
        # O NavigationManager não tem o método load_initial_screen
        self.ui_builder.load_initial_screen()

        # Janela de preferências (inicialmente nula)
        self.preferences_window = None

    # Métodos de acesso para o estado centralizado
    def set_content_path(self, path):
        """Define o caminho do conteúdo atual"""
        self._content_path = path
        self.update_ui_state()

    def get_content_path(self):
        """Retorna o caminho do conteúdo atual"""
        return self._content_path

    def set_current_state(self, state):
        """Define o estado atual da aplicação e atualiza a interface"""
        self._current_state = state
        # Atualiza o cabeçalho conforme o estado
        self.navigation_manager._update_header(state)

    def get_current_state(self):
        """Retorna o estado atual da aplicação"""
        return self._current_state

    def set_operation_running(self, is_running):
        """Define se uma operação está em execução"""
        self._is_operation_running = is_running
        self.update_ui_state()

    def is_operation_running(self):
        """Verifica se uma operação está em execução"""
        return self._is_operation_running

    def get_navigation_history(self):
        """Retorna o histórico de navegação"""
        return self._navigation_history

    def update_ui_state(self):
        """Atualiza todos os componentes da UI com base no estado atual"""
        # Atualiza botões de navegação
        can_navigate_back = bool(self._navigation_history)

        # Verificação crítica: só atualiza se o botão já foi criado
        if hasattr(self, '_back_button') and self._back_button is not None:
            self._back_button.set_sensitive(can_navigate_back and not self._is_operation_running)

        has_content_path = bool(self._content_path)
        if hasattr(self, '_open_folder_button') and self._open_folder_button is not None:
            self._open_folder_button.set_sensitive(has_content_path and not self._is_operation_running)

        # Atualiza botão de cancelar
        if hasattr(self, '_cancel_button') and self._cancel_button is not None:
            self._cancel_button.set_visible(self._is_operation_running)

        # Atualiza menu
        if hasattr(self, 'menu_manager') and self.menu_manager is not None:
            self.menu_manager.update_menu_state(not self._is_operation_running)

    def show_pkgbuild_review(self, on_confirm):
        """Mostra diálogo de revisão do PKGBUILD"""
        # Implementação do diálogo de revisão
        pass

    def end_operation(self):
        """Finaliza uma operação e atualiza a UI"""
        self.set_operation_running(False)
        self.terminal_manager.append(_("✅ Operação concluída"), "success")
        self.terminal_manager.append(_("──────────────────────────────────"), "normal")

    def _scroll_to_end(self):
        """Rola o terminal para o final"""
        if not self._terminal:
            return

        buffer = self._terminal.get_buffer()
        end_iter = buffer.get_end_iter()
        self._terminal.scroll_to_iter(end_iter, 0.0, False, 0.0, 0.0)

    # Propriedades para acesso seguro aos componentes
    @property
    def content_box(self):
        return self._content_box

    @property
    def toolbar_box(self):
        return self._toolbar_box

    @property
    def header_title(self):
        return self._header_title

    @property
    def header_bar(self):
        return self._header_bar

    @property
    def back_button(self):
        return self._back_button

    @property
    def open_folder_button(self):
        return self._open_folder_button

    @property
    def cancel_button(self):
        return self._cancel_button

    @property
    def terminal(self):
        return self._terminal

    @property
    def progress_bar(self):
        return self._progress_bar

    @property
    def terminal_box(self):
        return self._terminal_box

    @property
    def navigation_history(self):
        return self._navigation_history

    @navigation_history.setter
    def navigation_history(self, value):
        self._navigation_history = value
        # Não chama update_ui_state() imediatamente durante a inicialização
        # Isso evita tentar acessar componentes que ainda não foram criados
        if hasattr(self, '_back_button') and self._back_button is not None:
            self.update_ui_state()
