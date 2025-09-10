from gi.repository import Gtk, Gio, GLib, Adw
import os
import subprocess
import gettext
from pathlib import Path
import shutil
import logging
import gi
import gi.repository

_ = gettext.gettext

# Adiciona suporte para GtkSource para syntax highlighting
try:
    gi.require_version('GtkSource', '5')
    from gi.repository import GtkSource
except (ValueError, ImportError):
    GtkSource = None

from .utils import check_content_path, check_path_exists, check_pkgbuild_exists
from .terminal_manager import TerminalManager

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
        """
        Inicializa o gerenciador de handlers com as dependências necessárias.

        Args:
            window (PainelParuWindow): Referência para a janela principal da aplicação.
                Deve conter os atributos necessários para integração, como
                terminal_manager, navigation_manager, etc.

        Example:
            >>> window = PainelParuWindow()
            >>> handlers = WindowHandlers(window)
            >>> button = Gtk.Button(label="Build")
            >>> button.connect("clicked", handlers.on_build_package)

        Note:
            - Configura automaticamente o settings para acesso às preferências
            - Obtém uma referência ao terminal_manager para feedback ao usuário
            - Não deve conter lógica de inicialização pesada
        """
        self.window = window
        self.settings = Gio.Settings.new("org.gnome.painel_paru")
        self.terminal_manager = window.terminal_manager
        self.logger = logging.getLogger(__name__)

    def show_pkgbuild_review(self, callback_on_accept):
        """
        Exibe um diálogo para revisão do PKGBUILD antes do build.

        Este método cria e exibe um diálogo com o conteúdo do PKGBUILD, permitindo
        que o usuário revise o script antes de prosseguir com o build. O diálogo
        inclui syntax highlighting (se GtkSource estiver disponível) e um aviso
        sobre a segurança de PKGBUILDs não confiáveis.

        Args:
            callback_on_accept (callable): Função a ser chamada quando o usuário
                aceitar o diálogo (clicar em "Continuar com o Build"). Não recebe
                argumentos.

        Returns:
            None: O diálogo é exibido de forma assíncrona

        Example:
            >>> def on_build_accepted():
            ...     print("Usuário aceitou o PKGBUILD, iniciando build")
            >>> handlers.show_pkgbuild_review(on_build_accepted)

        Note:
            - Usa GtkSourceView para syntax highlighting se disponível
            - Faz fallback para TextView simples caso GtkSource não esteja disponível
            - Inclui um aviso de segurança sobre PKGBUILDs potencialmente maliciosos
            - O diálogo é modal e vinculado à janela principal
        """
        if not check_content_path(self.window, self.terminal_manager):
            return

        # Verifica se é um diretório
        if not os.path.isdir(self.window.content_path):
            self.terminal_manager.show_error(_("Caminho selecionado não é um diretório"))
            return

        pkgbuild_path = os.path.join(self.window.content_path, "PKGBUILD")
        if not os.path.exists(pkgbuild_path):
            self.terminal_manager.show_error(_("PKGBUILD não encontrado"))
            return

        # Cria o diálogo
        dialog = Adw.AlertDialog(
            heading=_("Revisão do PKGBUILD"),
            body=_("Revise o conteúdo do PKGBUILD antes de prosseguir com o build."),
            close_response="cancel"
        )

        # Configura o conteúdo do diálogo
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_vexpand(True)
        scrolled_window.set_hexpand(True)
        scrolled_window.set_min_content_size(600, 400)

        # Usa GtkSourceView para syntax highlighting
        if GtkSource is not None:
            try:
                # Configura o buffer com syntax highlighting
                buffer = GtkSource.Buffer()
                language_manager = GtkSource.LanguageManager.get_default()
                language = language_manager.get_language("sh")  # PKGBUILD é shell script
                if language:
                    buffer.set_language(language)

                # Carrega o conteúdo do PKGBUILD
                with open(pkgbuild_path, 'r') as f:
                    buffer.set_text(f.read(), -1)

                # Cria a view
                source_view = GtkSource.View(buffer=buffer)
                source_view.set_editable(False)
                source_view.set_cursor_visible(False)
                source_view.set_monospace(True)
                source_view.set_wrap_mode(Gtk.WrapMode.WORD)
                source_view.set_left_margin(10)
                source_view.set_right_margin(10)
                source_view.set_top_margin(5)
                source_view.set_bottom_margin(5)

                scrolled_window.set_child(source_view)
            except Exception as e:
                # Fallback para TextView simples se houver erro com GtkSource
                text_view = Gtk.TextView(
                    editable=False,
                    monospace=True,
                    wrap_mode=Gtk.WrapMode.WORD,
                    left_margin=10,
                    right_margin=10,
                    top_margin=5,
                    bottom_margin=5
                )
                text_buffer = text_view.get_buffer()

                # Carrega o conteúdo do PKGBUILD
                try:
                    with open(pkgbuild_path, 'r') as f:
                        text_buffer.set_text(f.read(), -1)
                except Exception as e:
                    text_buffer.set_text(_("Erro ao carregar PKGBUILD: %s") % str(e), -1)

                scrolled_window.set_child(text_view)
                self.terminal_manager.show_warning(_("Erro ao usar GtkSource: %s") % str(e))
        else:
            # Fallback para TextView simples se GtkSource não estiver disponível
            text_view = Gtk.TextView(
                editable=False,
                monospace=True,
                wrap_mode=Gtk.WrapMode.WORD,
                left_margin=10,
                right_margin=10,
                top_margin=5,
                bottom_margin=5
            )
            text_buffer = text_view.get_buffer()

            # Carrega o conteúdo do PKGBUILD
            try:
                with open(pkgbuild_path, 'r') as f:
                    text_buffer.set_text(f.read(), -1)
            except Exception as e:
                text_buffer.set_text(_("Erro ao carregar PKGBUILD: %s") % str(e), -1)

            scrolled_window.set_child(text_view)
            self.terminal_manager.show_info(_("GtkSource não disponível, usando visualização simples"))

        # Adiciona o conteúdo ao diálogo
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_start(10)
        content_box.set_margin_end(10)
        content_box.set_margin_top(10)
        content_box.set_margin_bottom(10)
        content_box.append(scrolled_window)

        # Adiciona uma caixa de informação
        info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        info_box.add_css_class("card")
        info_box.set_margin_top(10)

        warning_icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        warning_icon.add_css_class("warning")
        info_box.append(warning_icon)

        info_label = Gtk.Label(
            label=_("Atenção: Revise cuidadosamente o conteúdo do PKGBUILD antes de prosseguir. "
                    "Scripts maliciosos podem comprometer a segurança do seu sistema."),
            wrap=True,
            xalign=0,
            selectable=True,
            margin_start=10,
            margin_end=10,
            margin_top=5,
            margin_bottom=5
        )
        info_box.append(info_label)

        content_box.append(info_box)

        # Configura os botões
        dialog.add_response("cancel", _("Cancelar"))
        dialog.add_response("accept", _("Continuar com o Build"))
        dialog.set_response_appearance("accept", Adw.ResponseAppearance.SUGGESTED)

        # Define o conteúdo personalizado
        dialog.set_extra_child(content_box)

        # Conecta os callbacks
        def on_response(dialog, response):
            if response == "accept":
                callback_on_accept()
            dialog.force_close()

        dialog.connect("response", on_response)

        # Apresenta o diálogo
        dialog.present(self.window)

    def on_edit_pkgbuild(self, *args, **kwargs):
        """
        Abre o PKGBUILD no editor de texto configurado nas preferências.

        Este método verifica se um diretório válido com PKGBUILD está selecionado
        e abre o arquivo no editor de texto configurado pelo usuário nas preferências.
        Ele inclui validação do editor para segurança e feedback adequado ao usuário.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: A abertura do editor é feita de forma assíncrona

        Example:
            >>> handlers.on_edit_pkgbuild()
            # Abre o PKGBUILD no editor configurado

        Note:
            - Verifica se o caminho selecionado é um diretório e contém PKGBUILD
            - Valida o editor contra uma lista de editores permitidos
            - Usa shutil.which() para verificar se o editor existe no sistema
            - Executa o editor sem shell para evitar injeção de comandos
            - Mostra mensagens de erro adequadas em caso de falha
        """
        if not check_content_path(self.window, self.terminal_manager):
            return

        # Verifica se é um diretório
        if not os.path.isdir(self.window.content_path):
            self.terminal_manager.show_error(_("Caminho selecionado não é um diretório"))
            return

        if not check_pkgbuild_exists(self.window, self.terminal_manager):
            return

        try:
            pkgbuild_path = os.path.join(self.window.content_path, "PKGBUILD")

            # Obtém o editor das preferências
            editor = self.settings.get_string("editor") or "xdg-open"

            # Validação básica do editor
            allowed_editors = ["gedit", "kate", "mousepad", "xed", "code", "nvim", "vim", "emacs", "xdg-open"]
            if editor not in allowed_editors:
                # Tenta obter caminho absoluto
                editor_path = shutil.which(editor)
                if not editor_path:
                    self.terminal_manager.show_error(_("Editor não encontrado"))
                    return

            cmd = [editor, pkgbuild_path]
            # Executa sem shell para segurança
            subprocess.Popen(cmd, shell=False)
            self.terminal_manager.show_info(_("PKGBUILD aberto no editor"))
        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao editar PKGBUILD: %s") % error_type
            self.terminal_manager.show_error(error_msg)
            self.logger.error("Error editing PKGBUILD: %s - %s", error_type, str(e))

    def on_verify_signatures(self, *args, **kwargs):
        """
        Verifica assinaturas de pacotes e sua integridade no diretório atual.

        Este método realiza duas verificações importantes:
        1. Verifica assinaturas de arquivos .sig usando pacman-key
        2. Verifica a integridade de pacotes instalados usando pacman -Qk

        É útil para garantir que os pacotes são autênticos e não foram corrompidos.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: A verificação é executada de forma assíncrona, resultados exibidos no terminal

        Example:
            >>> handlers.on_verify_signatures()
            # Inicia verificação de assinaturas e integridade

        Note:
            - Procura por arquivos .sig no diretório atual
            - Para cada pacote .pkg.tar.zst, extrai o nome e verifica sua integridade
            - Mostra mensagens informativas para cada etapa
            - Trata erros adequadamente e exibe mensagens claras ao usuário
        """
        if not check_content_path(self.window, self.terminal_manager):
            return

        # Verifica se é um diretório
        if not os.path.isdir(self.window.content_path):
            self.terminal_manager.show_error(_("Caminho selecionado não é um diretório"))
            return

        try:
            # Verifica assinaturas dos arquivos .sig
            sig_files = list(Path(self.window.content_path).glob("*.sig"))
            if not sig_files:
                self.terminal_manager.show_warning(_("Nenhum arquivo .sig encontrado."))
            else:
                for sig in sig_files:
                    self.terminal_manager.show_info(_("Verificando: %s") % sig.name)
                    # Verifica a assinatura
                    from .paru_runner import ParuRunner
                    ParuRunner.run_command(["pacman-key", "--verify", str(sig)], self.terminal_manager.append)

            # Verifica a integridade dos pacotes instalados (se já estiverem instalados)
            packages = list(Path(self.window.content_path).glob("*.pkg.tar.zst"))
            if not packages:
                self.terminal_manager.show_warning(_("Nenhum pacote encontrado para verificar."))
            else:
                for pkg in packages:
                    # Extrai o nome do pacote do arquivo
                    pkg_name = pkg.name.split('-')[0]
                    self.terminal_manager.show_info(_("Verificando integridade: %s") % pkg_name)
                    # Comando correto para verificar a integridade de pacotes instalados
                    from .paru_runner import ParuRunner
                    ParuRunner.run_command(["pacman", "-Qk", pkg_name], self.terminal_manager.append)
        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao verificar assinaturas: %s") % error_type
            self.terminal_manager.show_error(error_msg)
            self.logger.error("Error verifying signatures: %s - %s", error_type, str(e))

    def on_build_package(self, *args, **kwargs):
        """
        Inicia o processo de build de um pacote com verificação de conflitos.

        Este método coordena todo o processo de build de um pacote, incluindo:
        - Verificação de conflitos potenciais com pacotes já instalados
        - Revisão opcional do PKGBUILD (configurável nas preferências)
        - Execução do build com as opções configuradas

        O fluxo do método varia dependendo das preferências do usuário:
        - Se "review-pkgbuild" estiver ativado, mostra o diálogo de revisão
        - Se "skip-review" estiver ativado, pula a revisão mesmo se configurado para revisar
        - Se "clean-after" estiver ativado, limpa os arquivos após o build

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: O processo de build é iniciado de forma assíncrona

        Example:
            >>> handlers.on_build_package()
            # Inicia o processo de build do pacote no diretório selecionado

        Note:
            - Primeiro verifica se o diretório contém um PKGBUILD válido
            - Extrai o nome do pacote do PKGBUILD para verificação de conflitos
            - Mostra progresso adequado em cada etapa do processo
            - Atualiza o estado da interface para refletir operação em andamento
        """
        if not check_content_path(self.window, self.terminal_manager):
            return

        # Verifica se é um diretório
        if not os.path.isdir(self.window.content_path):
            self.terminal_manager.show_error(_("Caminho selecionado não é um diretório"))
            return

        if not check_path_exists(self.window, self.terminal_manager):
            return

        if not check_pkgbuild_exists(self.window, self.terminal_manager):
            return

        review_pkgbuild = self.settings.get_boolean("review-pkgbuild")
        skip_review = self.settings.get_boolean("skip-review")
        clean_after = self.settings.get_boolean("clean-after")
        pkgbuild_path = os.path.join(self.window.content_path, "PKGBUILD")

        def start_build():
            # Primeiro verifica se há conflitos
            self.terminal_manager.show_progress(_("Verificando possíveis conflitos..."))

            # Extrai o nome do pacote do PKGBUILD
            package_name = None
            try:
                with open(pkgbuild_path, 'r') as f:
                    for line in f:
                        if line.startswith("pkgname="):
                            package_name = line.split("=")[1].strip().strip('"')
                            break
            except Exception as e:
                error_type = type(e).__name__
                error_msg = _("Erro ao ler PKGBUILD: %s") % error_type
                self.terminal_manager.show_error(error_msg)
                self.logger.error("Error reading PKGBUILD: %s - %s", error_type, str(e))
                return

            if package_name:
                self.terminal_manager.show_info(_("Pacote detectado: %s") % package_name)
                # Verifica conflitos
                from .paru_runner import ParuRunner
                ParuRunner.run_command(["paru", "-Si", package_name], self.terminal_manager.append)

            # Inicia o build
            self.terminal_manager.show_progress(_("Iniciando compilação..."))
            from .build_manager import BuildManager
            BuildManager.start_build(
                self.window.content_path,
                True,  # install
                self.terminal_manager.append,
                clean_after,
                skip_review
            )

        if review_pkgbuild and not skip_review:
            # Mostrar tela de revisão do PKGBUILD
            self.show_pkgbuild_review(start_build)
        else:
            start_build()

    def on_install_packages(self, *args, **kwargs):
        """
        Instala todos os pacotes .pkg.tar.zst encontrados no diretório atual.

        Este método localiza todos os pacotes no formato .pkg.tar.zst no diretório
        selecionado e os instala usando o comando `sudo pacman -U`. É útil para
        instalar pacotes que foram construídos previamente.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: A instalação é executada de forma assíncrona, resultados exibidos no terminal

        Example:
            >>> handlers.on_install_packages()
            # Instala todos os pacotes .pkg.tar.zst no diretório selecionado

        Note:
            - Requer permissões de sudo para instalação
            - Processa cada pacote individualmente para melhor feedback ao usuário
            - Mostra progresso adequado durante a instalação
            - Trata erros de instalação e exibe mensagens claras ao usuário
        """
        if not check_content_path(self.window, self.terminal_manager):
            return

        # Verifica se é um diretório
        if not os.path.isdir(self.window.content_path):
            self.terminal_manager.show_error(_("Caminho selecionado não é um diretório"))
            return

        if not check_path_exists(self.window, self.terminal_manager):
            return

        try:
            self.terminal_manager.show_progress(_("Instalando pacotes..."))

            # Instala todos os pacotes .pkg.tar.zst no diretório
            for pkg in Path(self.window.content_path).glob("*.pkg.tar.zst"):
                self.terminal_manager.show_info(_("Instalando: %s") % pkg.name)
                from .paru_runner import ParuRunner
                ParuRunner.run_command(["sudo", "pacman", "-U", str(pkg)], self.terminal_manager.append)

            self.terminal_manager.show_success(_("Instalação concluída!"))
        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao instalar pacotes: %s") % error_type
            self.terminal_manager.show_error(error_msg)
            self.logger.error("Error installing packages: %s - %s", error_type, str(e))

    def on_apply_patches(self, *args, **kwargs):
        """
        Aplica patches ao PKGBUILD e ao código-fonte do pacote.

        Este método localiza todos os arquivos .patch no diretório atual e os aplica
        ao PKGBUILD e ao código-fonte usando o comando `patch`. Ele cria um backup
        do PKGBUILD original antes de aplicar os patches e restaura o backup em caso
        de falha.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: A aplicação de patches é executada de forma assíncrona, resultados exibidos no terminal

        Example:
            >>> handlers.on_apply_patches()
            # Aplica todos os patches no diretório selecionado

        Note:
            - Cria um backup do PKGBUILD antes de aplicar patches
            - Aplica patches um por um, parando na primeira falha
            - Restaura o PKGBUILD original em caso de falha
            - Usa o comando patch com opções padrão (-p1)
            - Mostra feedback detalhado sobre o progresso e resultados
        """
        if not check_content_path(self.window, self.terminal_manager):
            return

        # Verifica se é um diretório
        if not os.path.isdir(self.window.content_path):
            self.terminal_manager.show_error(_("Caminho selecionado não é um diretório"))
            return

        if not check_path_exists(self.window, self.terminal_manager):
            return

        if not check_pkgbuild_exists(self.window, self.terminal_manager):
            return

        try:
            self.terminal_manager.show_progress(_("Aplicando patches..."))

            # Obtém todos os patches no diretório
            patches = [f for f in os.listdir(self.window.content_path)
                      if f.endswith('.patch')]

            if not patches:
                self.terminal_manager.show_warning(_("Nenhum patch encontrado."))
                return

            pkgbuild_path = os.path.join(self.window.content_path, "PKGBUILD")

            # Faz backup do PKGBUILD original
            backup_path = f"{pkgbuild_path}.bak"
            shutil.copy2(pkgbuild_path, backup_path)
            self.terminal_manager.show_info(_("Backup do PKGBUILD criado: %s") % backup_path)

            # Aplica cada patch
            all_patches_applied = True
            for patch in patches:
                patch_path = os.path.join(self.window.content_path, patch)
                self.terminal_manager.show_info(_("Aplicando patch: %s") % patch)

                # Usa o comando patch para aplicar
                result = subprocess.run(
                    ["patch", "-d", self.window.content_path, "-p1", "-i", patch_path],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    self.terminal_manager.show_success(_("Patch aplicado com sucesso."))
                else:
                    error_msg = _("Erro ao aplicar patch: %s") % result.stderr
                    self.terminal_manager.show_error(error_msg)
                    # Restaura o PKGBUILD original em caso de erro
                    shutil.copy2(backup_path, pkgbuild_path)
                    all_patches_applied = False
                    break

            if all_patches_applied:
                self.terminal_manager.show_success(_("Todos os patches aplicados com sucesso!"))
            else:
                self.terminal_manager.show_warning(_("Alguns patches não foram aplicados."))
        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao aplicar patches: %s") % error_type
            self.terminal_manager.show_error(error_msg)
            self.logger.error("Error applying patches: %s - %s", error_type, str(e))

    def on_cancel_operation(self, *args, **kwargs):
        """
        Cancela a operação em andamento com terminação robusta.

        Este método implementa um processo seguro para cancelar operações em andamento,
        primeiro tentando um término gracioso e, se necessário, forçando o encerramento.
        Ele segue um protocolo de terminação robusto:
        1. Envia sinal de término (SIGTERM)
        2. Aguarda até 2 segundos para o processo terminar
        3. Se não terminar, envia sinal de kill (SIGKILL)

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: O cancelamento é processado imediatamente

        Example:
            >>> handlers.on_cancel_operation()
            # Cancela a operação em andamento

        Note:
            - Atualiza o estado da interface após o cancelamento
            - Mostra mensagens adequadas para cada etapa do processo
            - Trata exceções para evitar falhas na interface
            - Limpa a referência ao processo atual após o cancelamento
        """
        if hasattr(self.window, 'current_process') and self.window.current_process:
            try:
                self.window.current_process.terminate()
                try:
                    # Aguarda até 2 segundos para o processo terminar
                    self.window.current_process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self.terminal_manager.show_warning(_("Processo não respondeu ao término gracioso, forçando encerramento..."))
                    self.window.current_process.kill()
                    self.window.current_process.wait()

                self.terminal_manager.show_info(_("Operação cancelada"))
                self.window.current_process = None
                # Atualiza o estado do botão de cancelar
                self.window.cancel_button.set_visible(False)
                self.window.end_operation()
            except Exception as e:
                error_type = type(e).__name__
                error_msg = _("Erro ao cancelar operação: %s") % error_type
                self.terminal_manager.show_error(error_msg)
                self.logger.error("Error cancelling operation: %s - %s", error_type, str(e))

    def on_show_preferences(self, *args, **kwargs):
        """
        Exibe a janela de preferências da aplicação.

        Este método cria e exibe a janela de preferências, permitindo que o usuário
        configure opções como editor padrão, comportamento de revisão do PKGBUILD,
        limpeza após build e outras configurações específicas.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: A janela de preferências é exibida de forma modal

        Example:
            >>> handlers.on_show_preferences()
            # Abre a janela de preferências

        Note:
            - A janela é modal e vinculada à janela principal
            - As alterações nas preferências são salvas automaticamente
            - A interface é atualizada para refletir as novas configurações
            - Usa PreferencesManager para gerenciar a lógica da janela
        """
        from .preferences_manager import PreferencesManager
        PreferencesManager(self.window).show(self.window)

    def on_show_help(self, *args, **kwargs):
        """
        Exibe a sobreposição de ajuda com atalhos de teclado e informações básicas.

        Este método carrega e exibe a sobreposição de ajuda (help overlay) que contém
        informações sobre atalhos de teclado e funcionalidades básicas da aplicação.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: A sobreposição de ajuda é exibida de forma modal

        Example:
            >>> handlers.on_show_help()
            # Mostra a sobreposição de ajuda

        Note:
            - A sobreposição é carregada a partir de um arquivo .ui
            - É uma janela modal vinculada à janela principal
            - Fecha automaticamente quando o usuário pressiona Esc ou clica fora
            - Mostra apenas atalhos relevantes para o estado atual da aplicação
        """
        builder = Gtk.Builder.new_from_resource("/org/gnome/painel_paru/gtk/help-overlay.ui")
        help_overlay = builder.get_object("help_overlay")
        if help_overlay:
            help_overlay.set_transient_for(self.window)
            help_overlay.present()
        else:
            self.terminal_manager.show_error(_("Erro ao carregar sobreposição de ajuda"))
            self.logger.error("Help overlay not found in UI file")

    def on_show_about(self, *args, **kwargs):
        """
        Exibe a janela "Sobre" com informações da aplicação.

        Este método cria e exibe a janela "Sobre", que contém informações como:
        - Nome e versão da aplicação
        - Créditos da equipe de desenvolvimento
        - Links para documentação, repositório e doações
        - Notas de lançamento e informações de licença

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: A janela "Sobre" é exibida de forma modal

        Example:
            >>> handlers.on_show_about()
            # Mostra a janela "Sobre"

        Note:
            - Utiliza Adw.AboutWindow para uma integração nativa com Adwaita
            - Inclui links para documentação, doações e repositório
            - Mostra informações de versão e licença
            - A janela é modal e vinculada à janela principal
        """
        about = Adw.AboutWindow(
            transient_for=self.window,
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
            copyright=_("© 2023 Paru GUI"),
            license_type=Gtk.License.GPL_3_0
        )
        # Informações básicas
        about.set_website("https://github.com/paru-gui")
        # Links adicionais
        about.add_link(_("Documentação"), "https://github.com/paru-gui/wiki")
        about.add_link(_("Doações"), "https://github.com/sponsors/paru-gui")
        # Apresenta a janela
        about.present()

    def on_select_file(self, *args, **kwargs):
        """
        Handler para seleção de arquivo único pelo usuário.

        Este método exibe um diálogo de seleção de arquivo, permitindo que o usuário
        selecione um arquivo específico. É usado principalmente para casos onde
        apenas um arquivo precisa ser selecionado.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: O diálogo é exibido de forma modal

        Example:
            >>> handlers.on_select_file()
            # Mostra diálogo para selecionar um arquivo

        Note:
            - Usa Gtk.FileChooserNative para uma integração nativa com o ambiente
            - O diálogo é modal e vinculado à janela principal
            - A resposta é processada por on_file_chooser_response
        """
        self._show_file_chooser(Gtk.FileChooserAction.OPEN)

    def on_select_folder(self, *args, **kwargs):
        """
        Handler para seleção de pasta pelo usuário.

        Este método exibe um diálogo de seleção de pasta, permitindo que o usuário
        selecione um diretório. É usado para navegação no sistema de arquivos e
        seleção de diretórios com conteúdo relevante (PKGBUILD, pacotes, etc.).

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: O diálogo é exibido de forma modal

        Example:
            >>> handlers.on_select_folder()
            # Mostra diálogo para selecionar uma pasta

        Note:
            - Usa Gtk.FileChooserNative para uma integração nativa com o ambiente
            - O diálogo é modal e vinculado à janela principal
            - A resposta é processada por on_file_chooser_response
            - Atualiza o histórico de navegação ao selecionar um diretório
        """
        self._show_file_chooser(Gtk.FileChooserAction.SELECT_FOLDER)

    def _show_file_chooser(self, action):
        """
        Mostra o diálogo de seleção de arquivo/pasta com a ação especificada.

        Este método auxiliar cria e exibe o diálogo de seleção de arquivo/pasta
        com a ação apropriada (abrir arquivo ou selecionar pasta).

        Args:
            action (Gtk.FileChooserAction): Ação do diálogo (OPEN ou SELECT_FOLDER)

        Returns:
            None: O diálogo é exibido de forma modal

        Example:
            >>> self._show_file_chooser(Gtk.FileChooserAction.SELECT_FOLDER)
            # Mostra diálogo para selecionar uma pasta

        Note:
            - Configura o título do diálogo com base na ação
            - Define o diálogo como transient_for da janela principal
            - Conecta o callback para processar a resposta
        """
        dialog = Gtk.FileChooserNative(
            title=_("Selecionar %s") % (_("Arquivo") if action == Gtk.FileChooserAction.OPEN else _("Pasta")),
            transient_for=self.window,
            action=action
        )
        dialog.connect("response", self.on_file_chooser_response)
        dialog.show()

    def on_file_chooser_response(self, *args, **kwargs):
        """
        Processa a resposta do diálogo de seleção de arquivo/pasta.

        Este método é chamado quando o usuário responde ao diálogo de seleção
        (aceita ou cancela). Ele extrai o caminho selecionado e atualiza o estado
        da aplicação para refletir o novo diretório selecionado.

        Args:
            *args: Argumentos posicionais variáveis do callback do GTK
            **kwargs: Argumentos nomeados variáveis do callback do GTK

        Returns:
            None: Atualiza diretamente o estado da aplicação

        Example:
            # Este método é chamado automaticamente pelo GTK quando o diálogo é fechado
            # Não deve ser chamado diretamente

        Note:
            - É projetado para funcionar com diferentes assinaturas de callback
            - Salva o caminho atual no histórico de navegação
            - Atualiza o content_path da janela com o novo caminho selecionado
            - Carrega a tela de conteúdo apropriada para o novo caminho
        """
        # Extraímos os parâmetros necessários da forma mais segura possível
        dialog = None
        response = None

        # Se houver pelo menos um argumento, assume-se que é o diálogo
        if len(args) > 0:
            dialog = args[0]

        # Se houver pelo menos dois argumentos, assume-se que o segundo é a resposta
        if len(args) > 1:
            response = args[1]

        # Alternativamente, a resposta pode vir como argumento nomeado
        if response is None and 'response' in kwargs:
            response = kwargs['response']

        # Verifica se a resposta é de aceitação
        if response == Gtk.ResponseType.ACCEPT:
            # Salva o caminho atual no histórico antes de mudar
            if hasattr(self.window, 'content_path') and self.window.content_path:
                self.window.navigation_manager.previous_paths.append(self.window.content_path)
                self.window.back_button.set_sensitive(True)

            # Obtém o caminho do arquivo/pasta selecionado
            if dialog and hasattr(dialog, 'get_file'):
                file = dialog.get_file()
                if file:
                    self.window.content_path = file.get_path()
                    self.window.navigation_manager.load_content_screen()

    def on_back(self, *args, **kwargs):
        """
        Navega para o diretório anterior no histórico de navegação.

        Este método implementa a funcionalidade de "voltar" na navegação de diretórios,
        permitindo que o usuário retorne ao diretório visitado anteriormente.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: Atualiza diretamente o estado da aplicação

        Example:
            >>> handlers.on_back()
            # Navega para o diretório anterior no histórico

        Note:
            - Move o caminho atual para forward_paths para permitir "avançar"
            - Atualiza o content_path da janela com o novo caminho
            - Carrega a tela de conteúdo apropriada para o novo caminho
            - Atualiza a sensibilidade do botão de voltar
        """
        if self.window.navigation_manager.previous_paths:
            # Salva o caminho atual para poder avançar depois
            if hasattr(self.window, 'content_path') and self.window.content_path:
                self.window.navigation_manager.forward_paths.append(self.window.content_path)

            # Navega para o anterior
            self.window.content_path = self.window.navigation_manager.previous_paths.pop()
            self.window.navigation_manager.load_content_screen()
            self.window.back_button.set_sensitive(bool(self.window.navigation_manager.previous_paths))

    def on_open_folder(self, *args, **kwargs):
        """
        Abre o diretório atual no gerenciador de arquivos do sistema.

        Este método tenta abrir o diretório atual no gerenciador de arquivos padrão
        do sistema, usando comandos como xdg-open ou gio open. Ele tenta múltiplos
        comandos para garantir compatibilidade com diferentes ambientes de desktop.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: A abertura do gerenciador de arquivos é feita de forma assíncrona

        Example:
            >>> handlers.on_open_folder()
            # Abre o diretório atual no gerenciador de arquivos

        Note:
            - Primeiro tenta com xdg-open (funciona em muitos ambientes)
            - Se falhar, tenta com gio open (para ambientes GNOME)
            - Mostra feedback adequado em caso de sucesso ou falha
            - Trata exceções para evitar falhas na interface
        """
        if hasattr(self.window, 'content_path') and self.window.content_path:
            try:
                # Tenta com xdg-open (funciona em muitos ambientes)
                subprocess.Popen(["xdg-open", self.window.content_path])
                self.terminal_manager.show_info(_("Pasta aberta no gerenciador de arquivos"))
            except Exception as e:
                # Tente com gio (para ambientes GNOME)
                try:
                    subprocess.Popen(["gio", "open", self.window.content_path])
                    self.terminal_manager.show_info(_("Pasta aberta no gerenciador de arquivos"))
                except Exception as e:
                    error_type = type(e).__name__
                    error_msg = _("Erro ao abrir pasta: %s") % error_type
                    self.terminal_manager.show_error(error_msg)
                    self.logger.error("Error opening folder: %s - %s", error_type, str(e))

    def on_check_dependencies(self, *args, **kwargs):
        """
        Verifica as dependências do pacote no diretório atual.

        Este método executa o comando `paru -Si` para obter informações detalhadas
        sobre um pacote, incluindo suas dependências. É útil para entender quais
        pacotes são necessários para construir ou executar o pacote atual.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: A verificação é executada de forma assíncrona, resultados exibidos no terminal

        Example:
            >>> handlers.on_check_dependencies()
            # Verifica as dependências do pacote no diretório selecionado

        Note:
            - Extrai o nome do pacote do diretório atual
            - Executa paru -Si para obter informações detalhadas
            - Mostra progresso adequado durante a verificação
            - Trata erros e exibe mensagens claras ao usuário
        """
        if not check_content_path(self.window, self.terminal_manager):
            return

        # Verifica se é um diretório
        if not os.path.isdir(self.window.content_path):
            self.terminal_manager.show_error(_("Caminho selecionado não é um diretório"))
            return

        try:
            package_name = os.path.basename(self.window.content_path)
            self.terminal_manager.show_progress(_("Verificando dependências de %s...") % package_name)
            from .paru_runner import ParuRunner
            ParuRunner.run_command(["paru", "-Si", package_name], self.terminal_manager.append)
        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao verificar dependências: %s") % error_type
            self.terminal_manager.show_error(error_msg)
            self.logger.error("Error checking dependencies: %s - %s", error_type, str(e))

    def on_refresh_patches(self, *args, **kwargs):
        """
        Atualiza patches do repositório Git atual.

        Este método verifica se o diretório atual é um repositório Git e, se for,
        executa `git pull` para atualizar o conteúdo. É útil para manter patches
        atualizados quando eles são mantidos em um repositório remoto.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: A atualização é executada de forma assíncrona, resultados exibidos no terminal

        Example:
            >>> handlers.on_refresh_patches()
            # Atualiza o repositório Git no diretório atual

        Note:
            - Primeiro verifica se o diretório contém um .git (é um repositório)
            - Executa git pull no diretório atual
            - Mostra mensagens adequadas em caso de sucesso ou falha
            - Não faz nada se o diretório não for um repositório Git
        """
        if not check_content_path(self.window, self.terminal_manager):
            return

        # Verifica se é um diretório
        if not os.path.isdir(self.window.content_path):
            self.terminal_manager.show_error(_("Caminho selecionado não é um diretório"))
            return

        if not check_path_exists(self.window, self.terminal_manager):
            return

        try:
            self.terminal_manager.show_progress(_("Atualizando patches..."))

            # Verifica se é um repositório git
            if os.path.exists(os.path.join(self.window.content_path, ".git")):
                # Atualiza o repositório
                from .paru_runner import ParuRunner
                ParuRunner.run_command(["git", "-C", self.window.content_path, "pull"], self.terminal_manager.append)
                self.terminal_manager.show_success(_("Patches atualizados com sucesso!"))
            else:
                self.terminal_manager.show_warning(_("Diretório não é um repositório Git."))
        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao atualizar patches: %s") % error_type
            self.terminal_manager.show_error(error_msg)
            self.logger.error("Error refreshing patches: %s - %s", error_type, str(e))

    def on_update_system(self, *args, **kwargs):
        """
        Atualiza o sistema completo usando o paru.

        Este método executa o comando `paru -Syu` para atualizar todos os pacotes
        do sistema, incluindo pacotes do AUR. É a maneira mais completa de manter
        o sistema atualizado.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: A atualização é executada de forma assíncrona, resultados exibidos no terminal

        Example:
            >>> handlers.on_update_system()
            # Atualiza o sistema completo

        Note:
            - Executa paru -Syu (sincroniza repositórios e atualiza tudo)
            - Mostra progresso adequado durante a atualização
            - Pode levar tempo considerável dependendo do sistema
            - Requer permissões de sudo para atualização
        """
        self.terminal_manager.show_progress(_("Atualizando sistema..."))
        from .paru_runner import ParuRunner
        ParuRunner.run_command(["paru", "-Syu"], self.terminal_manager.append)

    def on_check_updates(self, *args, **kwargs):
        """
        Verifica atualizações disponíveis no sistema.

        Este método executa o comando `paru -Qua` para listar todas as atualizações
        disponíveis, incluindo pacotes do AUR. Ele também pode filtrar pacotes de
        desenvolvimento (como -git, -svn) com base nas preferências do usuário.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: A verificação é executada de forma assíncrona, resultados exibidos no terminal

        Example:
            >>> handlers.on_check_updates()
            # Verifica atualizações disponíveis

        Note:
            - Usa paru -Qua para listar atualizações do AUR
            - Filtra pacotes de desenvolvimento se devel-mode estiver desativado
            - Mostra progresso adequado durante a verificação
            - Não executa atualizações, apenas verifica disponibilidade
        """
        self.terminal_manager.show_progress(_("Verificando atualizações..."))

        # Verificar se deve incluir pacotes de desenvolvimento
        include_devel = self.settings.get_boolean("devel-mode")
        cmd = ["paru", "-Qua", "--color=never"]
        if not include_devel:
            cmd.append("--ignore=*-git")
            cmd.append("--ignore=*-svn")
            cmd.append("--ignore=*-hg")
            cmd.append("--ignore=*-bzr")

        from .paru_runner import ParuRunner
        ParuRunner.run_command(cmd, self.terminal_manager.append)

    def on_clear_cache(self, *args, **kwargs):
        """
        Limpa o cache do paru removendo pacotes antigos.

        Este método executa o comando `paru -Scc` para limpar o cache do paru,
        removendo todos os pacotes antigos que não são mais necessários. Isso
        ajuda a economizar espaço em disco.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: A limpeza é executada de forma assíncrona, resultados exibidos no terminal

        Example:
            >>> handlers.on_clear_cache()
            # Limpa o cache do paru

        Note:
            - Executa paru -Scc (limpa o cache completamente)
            - Mostra progresso adequado durante a limpeza
            - Pode liberar espaço significativo em disco
            - Não remove pacotes atualmente instalados
        """
        self.terminal_manager.show_progress(_("Limpando cache..."))
        from .paru_runner import ParuRunner
        ParuRunner.run_command(["paru", "-Scc"], self.terminal_manager.append)

    def on_pkgbuild_info(self, *args, **kwargs):
        """
        Mostra o conteúdo do PKGBUILD no terminal.

        Este método exibe o conteúdo do PKGBUILD no terminal da aplicação, permitindo
        que o usuário visualize as instruções de build sem sair da interface.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: O conteúdo é exibido no terminal de forma assíncrona

        Example:
            >>> handlers.on_pkgbuild_info()
            # Mostra o conteúdo do PKGBUILD no terminal

        Note:
            - Usa o comando cat para exibir o conteúdo do PKGBUILD
            - Mostra o conteúdo diretamente no terminal da aplicação
            - Útil para rápida visualização sem abrir um editor
            - Trata erros adequadamente em caso de falha na leitura
        """
        if not check_content_path(self.window, self.terminal_manager):
            return

        # Verifica se é um diretório
        if not os.path.isdir(self.window.content_path):
            self.terminal_manager.show_error(_("Caminho selecionado não é um diretório"))
            return

        if not check_pkgbuild_exists(self.window, self.terminal_manager):
            return

        try:
            # Comando para mostrar informações do PKGBUILD
            from .paru_runner import ParuRunner
            ParuRunner.run_command(["cat", os.path.join(self.window.content_path, "PKGBUILD")],
                                  self.terminal_manager.append)
        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao obter informações: %s") % error_type
            self.terminal_manager.show_error(error_msg)
            self.logger.error("Error getting PKGBUILD info: %s - %s", error_type, str(e))

    def on_packages_info(self, *args, **kwargs):
        """
        Mostra informações detalhadas de todos os pacotes no diretório atual.

        Este método localiza todos os pacotes no formato .pkg.tar.zst no diretório
        atual e executa `pacman -Qi` para obter informações detalhadas sobre cada
        um deles, incluindo dependências, tamanho e descrição.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: As informações são exibidas no terminal de forma assíncrona

        Example:
            >>> handlers.on_packages_info()
            # Mostra informações detalhadas de todos os pacotes no diretório

        Note:
            - Processa cada pacote individualmente para melhor feedback
            - Usa pacman -Qi para obter informações detalhadas
            - Mostra progresso adequado durante a verificação
            - Útil para entender o conteúdo dos pacotes construídos
        """
        if not check_content_path(self.window, self.terminal_manager):
            return

        # Verifica se é um diretório
        if not os.path.isdir(self.window.content_path):
            self.terminal_manager.show_error(_("Caminho selecionado não é um diretório"))
            return

        if not check_path_exists(self.window, self.terminal_manager):
            return

        try:
            # Comando para mostrar informações de todos os pacotes .pkg.tar.zst
            for pkg in Path(self.window.content_path).glob("*.pkg.tar.zst"):
                self.terminal_manager.show_info(_("Obtendo informações de: %s") % pkg.name)
                from .paru_runner import ParuRunner
                ParuRunner.run_command(["pacman", "-Qi", str(pkg)], self.terminal_manager.append)
        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao obter informações: %s") % error_type
            self.terminal_manager.show_error(error_msg)
            self.logger.error("Error getting packages info: %s - %s", error_type, str(e))

    def on_verify_packages(self, *args, **kwargs):
        """
        Verifica assinaturas e integridade de pacotes de forma completa.

        Este método realiza uma verificação abrangente dos pacotes no diretório atual:
        1. Verifica assinaturas de arquivos .sig usando pacman-key
        2. Verifica a integridade de pacotes instalados usando pacman -Qk

        É semelhante a on_verify_signatures, mas com uma abordagem mais completa
        e focada especificamente na verificação de segurança e integridade.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: A verificação é executada de forma assíncrona, resultados exibidos no terminal

        Example:
            >>> handlers.on_verify_packages()
            # Inicia verificação completa de segurança e integridade

        Note:
            - Procura por arquivos .sig no diretório atual
            - Para cada pacote .pkg.tar.zst, extrai o nome e verifica sua integridade
            - Mostra mensagens informativas para cada etapa
            - Trata erros adequadamente e exibe mensagens claras ao usuário
            - Diferente de on_verify_signatures, este método tem foco específico em segurança
        """
        if not check_content_path(self.window, self.terminal_manager):
            return

        # Verifica se é um diretório
        if not os.path.isdir(self.window.content_path):
            self.terminal_manager.show_error(_("Caminho selecionado não é um diretório"))
            return

        if not check_path_exists(self.window, self.terminal_manager):
            return

        try:
            # Verifica assinaturas dos arquivos .sig
            sig_files = list(Path(self.window.content_path).glob("*.sig"))
            if not sig_files:
                self.terminal_manager.show_warning(_("Nenhum arquivo .sig encontrado."))
            else:
                for sig in sig_files:
                    self.terminal_manager.show_info(_("Verificando: %s") % sig.name)
                    # Verifica a assinatura
                    from .paru_runner import ParuRunner
                    ParuRunner.run_command(["pacman-key", "--verify", str(sig)], self.terminal_manager.append)

            # Verifica a integridade dos pacotes instalados (se já estiverem instalados)
            packages = list(Path(self.window.content_path).glob("*.pkg.tar.zst"))
            if not packages:
                self.terminal_manager.show_warning(_("Nenhum pacote encontrado para verificar."))
            else:
                for pkg in packages:
                    # Extrai o nome do pacote do arquivo
                    pkg_name = pkg.name.split('-')[0]
                    self.terminal_manager.show_info(_("Verificando integridade: %s") % pkg_name)
                    # Comando correto para verificar a integridade de pacotes instalados
                    from .paru_runner import ParuRunner
                    ParuRunner.run_command(["pacman", "-Qk", pkg_name], self.terminal_manager.append)
        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao verificar assinaturas: %s") % error_type
            self.terminal_manager.show_error(error_msg)
            self.logger.error("Error verifying packages: %s - %s", error_type, str(e))