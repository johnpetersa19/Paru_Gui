from gi.repository import Gtk, Gio, GLib, Adw
import os
import gettext
import logging
_ = gettext.gettext

# CORREÇÃO: Removido o ".handlers" extra nas importações
from .build_handlers import BuildHandlers
from .package_handlers import PackageHandlers
from .system_handlers import SystemHandlers
from .ui_handlers import UIHandlers
from .aur_handlers import AurHandlers

class WindowHandlers:
    """Gerenciador centralizado de handlers da interface do usuário

    Esta classe centraliza TODOS os handlers de eventos da aplicação, garantindo
    uma arquitetura limpa e organizada. Em vez de espalhar handlers por toda a
    aplicação, todos são agrupados aqui, facilitando a manutenção e evitando
    duplicação de código.

    Principais responsabilidades:
    - Gerenciar ações do usuário (cliques, seleções, etc.)
    - Coordenar operações com o sistema de arquivos e comandos do paru
    - Integrar com outros componentes da aplicação (terminal, gerenciador de menu)
    - Gerenciar diálogos e feedback ao usuário

    A classe segue um padrão consistente onde todos os handlers têm a assinatura:
    `def on_handler_name(self, *args, **kwargs)`

    Para usar:
    1. Crie uma instância na janela principal: `self.handlers = WindowHandlers(self)`
    2. Conecte os handlers aos widgets: `button.connect("clicked", self.handlers.on_build_package)`

    Note:
    - A classe depende de outros componentes como TerminalManager e NavigationManager
    - Todos os handlers tratam erros adequadamente e fornecem feedback ao usuário
    - A classe é projetada para ser stateless, mantendo referências apenas aos componentes necessários
    """
    def __init__(self, window):
        """Inicializa o gerenciador de handlers com as dependências necessárias.

        Args:
            window (Gtk.Window): Referência para a janela principal da aplicação
        """
        self.window = window
        self.logger = logging.getLogger("painel_paru.handlers")

        # Inicializa os handlers especializados
        self.build_handlers = BuildHandlers(window)
        self.package_handlers = PackageHandlers(window)
        self.system_handlers = SystemHandlers(window)
        self.ui_handlers = UIHandlers(window)
        self.aur_handlers = AurHandlers(window)

    # Handlers de build
    def on_build_package(self, *args, **kwargs):
        """Inicia o processo de build de um pacote com verificação de conflitos.
        Este método coordena todo o processo de build de um pacote, incluindo:
        - Verificação de conflitos potenciais com pacotes já instalados
        - Revisão opcional do PKGBUILD (configurável nas preferências)
        - Execução do build com as opções configuradas
        """
        return self.build_handlers.on_build_package(*args, **kwargs)

    def show_pkgbuild_review(self, on_build_accepted):
        """Exibe diálogo de revisão do PKGBUILD antes do build.
        Permite ao usuário revisar o PKGBUILD antes de continuar com o build.
        """
        return self.build_handlers.show_pkgbuild_review(on_build_accepted)

    def on_edit_pkgbuild(self, *args, **kwargs):
        """Abre o PKGBUILD no editor configurado.
        Este método verifica se o diretório selecionado contém um PKGBUILD válido
        e abre-o no editor configurado nas preferências.
        """
        return self.build_handlers.on_edit_pkgbuild(*args, **kwargs)

    # Handlers de pacotes
    def on_install_packages(self, *args, **kwargs):
        """Instala todos os pacotes .pkg.tar.zst encontrados no diretório atual.
        Este método localiza todos os pacotes no formato .pkg.tar.zst no diretório
        selecionado e os instala usando o comando `sudo pacman -U`.
        """
        return self.package_handlers.on_install_packages(*args, **kwargs)

    def on_packages_info(self, *args, **kwargs):
        """Mostra informações detalhadas de todos os pacotes no diretório atual.
        Este método localiza todos os pacotes no formato .pkg.tar.zst no diretório
        atual e executa `pacman -Qi` para obter informações detalhadas.
        """
        return self.package_handlers.on_packages_info(*args, **kwargs)

    def on_verify_signatures(self, *args, **kwargs):
        """Verifica assinaturas de pacotes e sua integridade no diretório atual.
        Este método realiza duas verificações importantes:
        1. Verifica assinaturas de arquivos .sig usando pacman-key
        2. Verifica a integridade de pacotes instalados usando pacman -Qk
        """
        return self.package_handlers.on_verify_signatures(*args, **kwargs)

    # Handlers do sistema
    def on_check_updates(self, *args, **kwargs):
        """Verifica atualizações disponíveis no sistema.
        Este método executa o comando `paru -Qua` para listar todas as atualizações
        disponíveis, incluindo pacotes do AUR.
        """
        return self.system_handlers.on_check_updates(*args, **kwargs)

    def on_update_system(self, *args, **kwargs):
        """Atualiza o sistema completo.
        Este método executa o comando `paru -Syu` para atualizar todos os pacotes
        do sistema, incluindo pacotes do AUR.
        """
        return self.system_handlers.on_update_system(*args, **kwargs)

    def on_check_dependencies(self, *args, **kwargs):
        """Verifica as dependências do pacote no diretório atual.
        Este método executa o comando `paru -Si` para obter informações detalhadas
        sobre um pacote, incluindo suas dependências.
        """
        return self.system_handlers.on_check_dependencies(*args, **kwargs)

    # Handlers de UI
    def on_show_preferences(self, *args, **kwargs):
        """Abre a janela de preferências da aplicação.
        Esta janela permite ao usuário configurar opções como editor padrão,
        limpeza após build e outras configurações específicas.
        """
        return self.ui_handlers.on_show_preferences(*args, **kwargs)

    def on_show_help(self, *args, **kwargs):
        """Exibe a sobreposição de ajuda da aplicação.
        Este método carrega e exibe a sobreposição de ajuda com os atalhos
        e informações básicas sobre o uso da aplicação.
        """
        return self.ui_handlers.on_show_help(*args, **kwargs)

    def on_show_about(self, *args, **kwargs):
        """Exibe a janela "Sobre" com informações da aplicação.
        Esta janela contém informações como nome e versão da aplicação,
        créditos da equipe de desenvolvimento e links úteis.
        """
        return self.ui_handlers.on_show_about(*args, **kwargs)

    # Handlers do AUR
    def on_download_pkgbuild(self, *args, **kwargs):
        """Baixa o PKGBUILD de um pacote do AUR.
        Este método permite ao usuário baixar o PKGBUILD de um pacote específico do AUR.
        """
        return self.aur_handlers.on_download_pkgbuild(*args, **kwargs)

    def on_search_pkgbuild(self, search_term, *args, **kwargs):
        """Busca pacotes no AUR.
        Este método permite ao usuário buscar pacotes no AUR usando um termo de busca.
        """
        return self.aur_handlers.on_search_pkgbuild(search_term, *args, **kwargs)

    # Handlers adicionais (mantidos para compatibilidade)
    def on_clear_cache(self, *args, **kwargs):
        """Limpa o cache do paru.
        Este método executa o comando `paru -Scc` para limpar o cache do paru,
        removendo todos os pacotes armazenados em cache.
        """
        try:
            self.window.terminal_manager.show_progress(_("Limpando cache do paru..."))
            from .paru_runner import ParuRunner
            ParuRunner.run_command(["paru", "-Scc"], self.window.terminal_manager.append)
        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao limpar cache: %s") % error_type
            self.window.terminal_manager.show_error(error_msg)
            self.logger.error("Error clearing cache: %s", str(e))

    def on_back(self, *args, **kwargs):
        """Navega para o diretório anterior no histórico.
        Este método permite ao usuário retornar ao diretório anteriormente visitado,
        mantendo um histórico de navegação semelhante a um navegador web.
        """
        if self.window.navigation_manager.previous_paths:
            # Salva o caminho atual para poder avançar depois
            if hasattr(self.window, 'content_path') and self.window.content_path:
                self.window.navigation_manager.forward_paths.append(self.window.content_path)

            # Obtém o próximo caminho do histórico
            previous_path = self.window.navigation_manager.previous_paths.pop()
            self.window.content_path = previous_path

            # Atualiza a interface
            from .content_detector import ContentDetector
            ContentDetector.detect_and_show_content(self.window)

            # Atualiza a sensibilidade do botão de voltar
            self.window.update_ui_state()

    def on_forward(self, *args, **kwargs):
        """Navega para o diretório seguinte no histórico.
        Este método permite ao usuário avançar para o diretório visitado anteriormente
        após ter usado o botão de voltar.
        """
        if self.window.navigation_manager.forward_paths:
            # Salva o caminho atual para poder voltar depois
            if hasattr(self.window, 'content_path') and self.window.content_path:
                self.window.navigation_manager.previous_paths.append(self.window.content_path)

            # Obtém o próximo caminho do histórico
            forward_path = self.window.navigation_manager.forward_paths.pop()
            self.window.content_path = forward_path

            # Atualiza a interface
            from .content_detector import ContentDetector
            ContentDetector.detect_and_show_content(self.window)

            # Atualiza a sensibilidade do botão de avançar
            self.window.update_ui_state()
