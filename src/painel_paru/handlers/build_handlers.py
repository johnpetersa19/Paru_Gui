from gi.repository import Gtk, GLib
import os
import gettext
_ = gettext.gettext

# Removido: check_path_exists, check_pkgbuild_exists, check_content_path
# Substituído tudo por validate_path
from .utils import validate_path
from .paru_runner import ParuRunner
from .build_manager import BuildManager


class BuildHandlers:
    """Gerencia operações relacionadas à construção de pacotes.

    Esta classe lida com todas as operações relacionadas à construção de pacotes
    a partir de PKGBUILDs, incluindo:
    - Iniciar o processo de build com verificação de conflitos
    - Exibir diálogo de revisão do PKGBUILD
    - Editar o PKGBUILD no editor configurado

    A classe é projetada para ser usada como parte da arquitetura de handlers
    da aplicação, sendo inicializada com uma referência à janela principal.

    Principais métodos:
    - on_build_package(): Inicia o processo de build de um pacote
    - show_pkgbuild_review(): Exibe diálogo de revisão do PKGBUILD
    - on_edit_pkgbuild(): Abre o PKGBUILD no editor configurado
    """

    def __init__(self, window):
        """Inicializa o gerenciador de handlers de build.

        Args:
            window (Gtk.Window): Referência para a janela principal da aplicação
        """
        self.window = window
        self.logger = window.logger
        self.terminal_manager = window.terminal_manager

    def on_build_package(self, *args, **kwargs):
        """Inicia o processo de build de um pacote com verificação de conflitos.
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
            - Mostra progresso adequado durante a operação
            - Trata erros e exibe mensagens claras ao usuário
        """
        # Validação unificada: caminho existe, é diretório e tem PKGBUILD
        if not validate_path(
            self.window,
            self.terminal_manager,
            must_be_directory=True,
            must_contain_pkgbuild=True
        ):
            return

        try:
            package_name = os.path.basename(self.window.content_path)
            self.terminal_manager.show_progress(_("Iniciando build de %s...") % package_name)

            # Obter preferências
            from .preferences_manager import PreferencesManager
            prefs = PreferencesManager.get_preferences()
            review_pkgbuild = prefs.get_boolean("review-pkgbuild")
            clean_after = prefs.get_boolean("clean-after")
            skip_review = prefs.get_boolean("skip-review")

            # Função para iniciar o build
            def start_build():
                try:
                    # Extrair nome do pacote do PKGBUILD
                    pkgbuild_path = os.path.join(self.window.content_path, "PKGBUILD")
                    package_name = self._extract_package_name(pkgbuild_path)

                    # Verificar conflitos
                    conflicts = self._check_conflicts(package_name)
                    if conflicts:
                        self._show_conflict_dialog(conflicts, package_name)
                        return

                    # Executar build
                    BuildManager.start_build(
                        self.window.content_path,
                        self.terminal_manager.append,
                        clean_after,
                        skip_review
                    )
                except Exception as e:
                    error_type = type(e).__name__
                    error_msg = _("Erro ao iniciar build: %s") % error_type
                    self.terminal_manager.show_error(error_msg)
                    self.logger.error("Error starting build: %s - %s", error_type, str(e))

            if review_pkgbuild and not skip_review:
                # Mostrar tela de revisão do PKGBUILD
                self.show_pkgbuild_review(start_build)
            else:
                start_build()

        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao iniciar build: %s") % error_type
            self.terminal_manager.show_error(error_msg)
            self.logger.error("Error starting build: %s - %s", error_type, str(e))

    def show_pkgbuild_review(self, on_build_accepted):
        """Exibe diálogo de revisão do PKGBUILD antes do build.
        Permite ao usuário revisar o PKGBUILD antes de continuar com o build.

        Args:
            on_build_accepted (callable): Função a ser chamada quando o usuário aceitar
            o diálogo (clicar em "Continuar com o Build"). Não recebe argumentos.

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
        # Mesma validação: deve existir, ser diretório e conter PKGBUILD
        if not validate_path(
            self.window,
            self.terminal_manager,
            must_be_directory=True,
            must_contain_pkgbuild=True
        ):
            return

        pkgbuild_path = os.path.join(self.window.content_path, "PKGBUILD")

        # Criar diálogo
        dialog = Gtk.Dialog(
            title=_("Revisão do PKGBUILD"),
            transient_for=self.window,
            modal=True
        )
        dialog.set_default_size(800, 600)

        # Adicionar botões
        dialog.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Continuar com o Build"), Gtk.ResponseType.OK)

        # Container principal
        content_area = dialog.get_content_area()
        content_area.set_orientation(Gtk.Orientation.VERTICAL)
        content_area.set_spacing(10)
        content_area.set_margin_start(10)
        content_area.set_margin_end(10)
        content_area.set_margin_top(10)
        content_area.set_margin_bottom(10)

        # Adicionar aviso de segurança
        warning_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        warning_box.add_css_class("warning")

        warning_icon = Gtk.Image.new_from_icon_name("dialog-warning")
        warning_icon.add_css_class("error-color")
        warning_box.append(warning_icon)

        warning_label = Gtk.Label(
            label=_("Aviso: PKGBUILDs podem conter código arbitrário. "
                   "Revise cuidadosamente antes de continuar."),
            wrap=True,
            hexpand=True,
            halign=Gtk.Align.START
        )
        warning_box.append(warning_label)
        content_area.append(warning_box)

        # Área de visualização do PKGBUILD
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_vexpand(True)
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        # Tentar usar GtkSourceView se disponível
        try:
            import gi
            gi.require_version('GtkSource', '5')
            from gi.repository import GtkSource

            buffer = GtkSource.Buffer()
            language_manager = GtkSource.LanguageManager.get_default()
            language = language_manager.get_language("sh")
            buffer.set_language(language)
            buffer.set_highlight_syntax(True)

            source_view = GtkSource.View(buffer=buffer, monospace=True)
            source_view.set_wrap_mode(Gtk.WrapMode.WORD)
            source_view.set_left_margin(10)
            source_view.set_right_margin(10)
            source_view.set_top_margin(5)
            source_view.set_bottom_margin(5)

            scrolled_window.set_child(source_view)

            # Carrega o conteúdo do PKGBUILD
            try:
                with open(pkgbuild_path, 'r', encoding='utf-8') as f:
                    buffer.set_text(f.read(), -1)
            except Exception as e:
                buffer.set_text(_("Erro ao carregar PKGBUILD: %s") % str(e), -1)
                self.terminal_manager.show_warning(_("Erro ao carregar PKGBUILD: %s") % str(e))
        except (ImportError, ValueError):
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
                with open(pkgbuild_path, 'r', encoding='utf-8') as f:
                    text_buffer.set_text(f.read(), -1)
            except Exception as e:
                text_buffer.set_text(_("Erro ao carregar PKGBUILD: %s") % str(e), -1)
                self.terminal_manager.show_warning(_("Erro ao carregar PKGBUILD: %s") % str(e))

            scrolled_window.set_child(text_view)

        content_area.append(scrolled_window)
        dialog.present()

        # Conectar sinal de resposta
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.OK:
                on_build_accepted()
            dialog.destroy()

        dialog.connect("response", on_response)

    def on_edit_pkgbuild(self, *args, **kwargs):
        """Abre o PKGBUILD no editor configurado.
        Este método verifica se o diretório selecionado contém um PKGBUILD válido
        e abre-o no editor configurado nas preferências.

        Args:
            *args: Argumentos posicionais padrão para handlers GTK
            **kwargs: Argumentos nomeados padrão para handlers GTK

        Returns:
            None: O PKGBUILD é aberto no editor de forma assíncrona

        Example:
            >>> handlers.on_edit_pkgbuild()
            # Abre o PKGBUILD no editor configurado

        Note:
            - Verifica se o editor configurado está disponível no sistema
            - Usa o editor padrão (mousepad) se o configurado não estiver disponível
            - Mostra mensagens adequadas de erro em caso de falha
        """
        # Validação: caminho existe, é diretório e tem PKGBUILD
        if not validate_path(
            self.window,
            self.terminal_manager,
            must_be_directory=True,
            must_contain_pkgbuild=True
        ):
            return

        pkgbuild_path = os.path.join(self.window.content_path, "PKGBUILD")

        try:
            # Obter editor configurado
            from .preferences_manager import PreferencesManager
            editor = PreferencesManager.get_preferences().get_string("editor")

            # Validar editor
            valid_editors = ["mousepad", "gedit", "code", "kate", "nano", "vim", "emacs"]
            if not editor or editor not in valid_editors:
                editor = "mousepad"  # Editor padrão

            # Verificar se o editor existe
            import shutil
            if not shutil.which(editor):
                self.terminal_manager.show_error(_("Editor não encontrado: %s") % editor)
                return

            # Executar editor
            import subprocess
            self.terminal_manager.show_info(_("Abrindo PKGBUILD com %s...") % editor)
            subprocess.Popen([editor, pkgbuild_path])

        except Exception as e:
            error_type = type(e).__name__
            error_msg = _("Erro ao abrir editor: %s") % error_type
            self.terminal_manager.show_error(error_msg)
            self.logger.error("Error opening editor: %s - %s", error_type, str(e))

    def _extract_package_name(self, pkgbuild_path):
        """Extrai o nome do pacote do PKGBUILD"""
        try:
            with open(pkgbuild_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("pkgname="):
                        return line.split('=', 1)[1].strip("'\"")
        except Exception as e:
            self.logger.warning("Error extracting package name: %s", str(e))
        return os.path.basename(os.path.dirname(pkgbuild_path))

    def _check_conflicts(self, package_name):
        """Verifica conflitos com pacotes já instalados"""
        try:
            conflicts = []
            pkgbuild_path = os.path.join(self.window.content_path, "PKGBUILD")

            with open(pkgbuild_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("conflicts="):
                        # Remove 'conflicts=(' e extrai pacotes
                        content = line.split('=', 1)[1].strip("()'\"")
                        for pkg in content.replace("'", "").replace('"', '').split():
                            pkg = pkg.strip()
                            if pkg and pkg not in ["None", "-"]:
                                conflicts.append({
                                    "package": pkg,
                                    "current": _("instalado"),
                                    "new": _("será instalado")
                                })
                        break
            return conflicts
        except Exception as e:
            print(f"Erro ao ler PKGBUILD para conflitos: {e}")
            return []

    def _show_conflict_dialog(self, conflicts, package_name):
        """Exibe diálogo de conflitos encontrados"""
        dialog = Gtk.Dialog(
            title=_("Conflitos Detectados"),
            transient_for=self.window,
            modal=True
        )
        dialog.set_default_size(600, 400)

        # Adicionar botões
        dialog.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Forçar Instalação"), Gtk.ResponseType.OK)

        # Container principal
        content_area = dialog.get_content_area()
        content_area.set_orientation(Gtk.Orientation.VERTICAL)
        content_area.set_spacing(10)
        content_area.set_margin_start(10)
        content_area.set_margin_end(10)
        content_area.set_margin_top(10)
        content_area.set_margin_bottom(10)

        # Adicionar mensagem de aviso
        warning_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        warning_box.add_css_class("warning")

        warning_icon = Gtk.Image.new_from_icon_name("dialog-warning")
        warning_icon.add_css_class("error-color")
        warning_box.append(warning_icon)

        warning_label = Gtk.Label(
            label=_("Conflitos detectados com pacotes já instalados. "
                   "Continuar pode remover pacotes existentes."),
            wrap=True,
            hexpand=True,
            halign=Gtk.Align.START
        )
        warning_box.append(warning_label)
        content_area.append(warning_box)

        # Listar conflitos
        conflicts_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

        for conflict in conflicts:
            conflict_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            conflict_row.set_margin_start(10)
            conflict_row.set_margin_end(10)

            pkg_label = Gtk.Label(
                label=f"• {conflict['package']}",
                halign=Gtk.Align.START,
                hexpand=True
            )
            pkg_label.add_css_class("heading")
            conflict_row.append(pkg_label)

            status_label = Gtk.Label(
                label=f"{conflict['current']} → {conflict['new']}",
                halign=Gtk.Align.END
            )
            status_label.add_css_class("dim-label")
            conflict_row.append(status_label)

            conflicts_box.append(conflict_row)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(conflicts_box)

        content_area.append(scrolled)
        dialog.present()

        # Conectar sinal de resposta
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.OK:
                # Forçar instalação
                BuildManager.start_build(
                    self.window.content_path,
                    self.terminal_manager.append,
                    True,  # clean_after
                    True   # skip_review
                )
            dialog.destroy()

        dialog.connect("response", on_response)
