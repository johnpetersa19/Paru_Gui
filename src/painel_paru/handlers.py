from gi.repository import Gtk, Gio, GLib, Adw
import os
import subprocess
import gettext
from pathlib import Path
import shutil
_ = gettext.gettext

from .utils import check_content_path, check_path_exists, check_pkgbuild_exists
from .terminal_manager import TerminalManager

class WindowHandlers:
    """Classe centralizada para todos os handlers da aplicação.

    Esta classe deve ser usada para centralizar TODOS os handlers da aplicação,
    evitando duplicação e espalhamento de código. Todos os handlers devem seguir
    a mesma assinatura padrão: def on_handler(self, *args, **kwargs)

    Para usar:
    1. Crie uma instância em Window: self.handlers = WindowHandlers(self)
    2. Conecte os handlers: button.connect("clicked", self.handlers.on_build_package)
    """

    def __init__(self, window):
        """Inicializa o gerenciador de handlers.

        Args:
            window: Referência para a janela principal da aplicação
        """
        self.window = window
        self.settings = Gio.Settings.new("org.gnome.painel_paru")
        self.terminal_manager = window.terminal_manager

    def on_edit_pkgbuild(self, *args, **kwargs):
        """Edita o PKGBUILD com o editor padrão"""
        if not check_content_path(self.window, self.terminal_manager):
            return

        if not check_pkgbuild_exists(self.window, self.terminal_manager):
            return

        try:
            pkgbuild_path = os.path.join(self.window.content_path, "PKGBUILD")

            # Obtém o editor das preferências
            editor = self.settings.get_string("editor") or "gedit"
            cmd = [editor, pkgbuild_path]

            # Tenta abrir com o editor configurado
            subprocess.Popen(cmd)
            self.terminal_manager.show_info(_("PKGBUILD aberto no editor"))
        except Exception as e:
            self.terminal_manager.show_error(_("Erro ao editar PKGBUILD: ") + str(e))
            print(f"❌ Erro ao editar PKGBUILD: {e}")

    def on_verify_signatures(self, *args, **kwargs):
        """Verifica assinaturas dos pacotes"""
        if not check_content_path(self.window, self.terminal_manager):
            return

        try:
            # Verifica assinaturas dos arquivos .sig
            sig_files = list(Path(self.window.content_path).glob("*.sig"))
            if not sig_files:
                self.terminal_manager.show_warning(_("Nenhum arquivo .sig encontrado."))
            else:
                for sig in sig_files:
                    self.terminal_manager.show_info(_("Verificando: ") + sig.name)
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
                    self.terminal_manager.show_info(_("Verificando integridade: ") + pkg_name)
                    # Comando correto para verificar a integridade de pacotes instalados
                    from .paru_runner import ParuRunner
                    ParuRunner.run_command(["pacman", "-Qk", pkg_name], self.terminal_manager.append)
        except Exception as e:
            self.terminal_manager.show_error(_("Erro ao verificar assinaturas: ") + str(e))
            print(f"❌ Erro ao verificar assinaturas: {e}")

    def on_build_package(self, *args, **kwargs):
        """Inicia processo de build com verificação de conflitos"""
        if not check_content_path(self.window, self.terminal_manager):
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
                self.terminal_manager.show_error(_("Erro ao ler PKGBUILD: ") + str(e))
                return

            if package_name:
                self.terminal_manager.show_info(_("Pacote detectado: ") + package_name)
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
            self.window.show_pkgbuild_review(start_build)
        else:
            start_build()

    def on_install_packages(self, *args, **kwargs):
        """Instala pacotes .pkg.tar.zst encontrados"""
        if not check_content_path(self.window, self.terminal_manager):
            return

        if not check_path_exists(self.window, self.terminal_manager):
            return

        try:
            self.terminal_manager.show_progress(_("Instalando pacotes..."))

            # Instala todos os pacotes .pkg.tar.zst no diretório
            for pkg in Path(self.window.content_path).glob("*.pkg.tar.zst"):
                self.terminal_manager.show_info(_("Instalando: ") + pkg.name)
                from .paru_runner import ParuRunner
                ParuRunner.run_command(["sudo", "pacman", "-U", str(pkg)], self.terminal_manager.append)

            self.terminal_manager.show_success(_("Instalação concluída!"))
        except Exception as e:
            self.terminal_manager.show_error(_("Erro ao instalar pacotes: ") + str(e))
            print(f"❌ Erro ao instalar pacotes: {e}")

    def on_apply_patches(self, *args, **kwargs):
        """Aplica patches ao PKGBUILD"""
        if not check_content_path(self.window, self.terminal_manager):
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
            self.terminal_manager.show_info(_("Backup do PKGBUILD criado: ") + backup_path)

            # Aplica cada patch
            all_patches_applied = True
            for patch in patches:
                patch_path = os.path.join(self.window.content_path, patch)
                self.terminal_manager.show_info(_("Aplicando patch: ") + patch)

                # Usa o comando patch para aplicar
                result = subprocess.run(
                    ["patch", "-d", self.window.content_path, "-p1", "-i", patch_path],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    self.terminal_manager.show_success(_("Patch aplicado com sucesso."))
                else:
                    self.terminal_manager.show_error(_("Erro ao aplicar patch:") + result.stderr)
                    # Restaura o PKGBUILD original em caso de erro
                    shutil.copy2(backup_path, pkgbuild_path)
                    all_patches_applied = False
                    break

            if all_patches_applied:
                self.terminal_manager.show_success(_("Todos os patches aplicados com sucesso!"))
            else:
                self.terminal_manager.show_warning(_("Alguns patches não foram aplicados."))
        except Exception as e:
            self.terminal_manager.show_error(_("Erro ao aplicar patches: ") + str(e))
            print(f"❌ Erro ao aplicar patches: {e}")

    def on_cancel_operation(self, *args, **kwargs):
        """Cancela a operação em andamento"""
        if hasattr(self.window, 'current_process') and self.window.current_process:
            try:
                self.window.current_process.terminate()
                self.terminal_manager.show_info(_("Operação cancelada"))
                self.window.current_process = None
                # Atualiza o estado do botão de cancelar
                self.window.cancel_button.set_visible(False)
                self.window.end_operation()
            except Exception as e:
                self.terminal_manager.show_error(_("Erro ao cancelar operação: ") + str(e))

    def on_show_preferences(self, *args, **kwargs):
        """Mostra janela de preferências"""
        from .preferences_manager import PreferencesManager
        PreferencesManager(self.window).show(self.window)

    def on_show_help(self, *args, **kwargs):
        """Mostra overlay de ajuda"""
        builder = Gtk.Builder.new_from_resource("/org/gnome/painel_paru/gtk/help-overlay.ui")
        help_overlay = builder.get_object("help_overlay")
        help_overlay.set_transient_for(self.window)
        help_overlay.present()

    def on_show_about(self, *args, **kwargs):
        """Mostra janela Sobre"""
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
        about.set_website("https://github.com/paru-gui      ")
        # Links adicionais
        about.add_link(_("Documentação"), "https://github.com/paru-gui/wiki      ")
        about.add_link(_("Doações"), "https://github.com/sponsors/paru-gui      ")
        # Apresenta a janela
        about.present()

    def on_select_file(self, *args, **kwargs):
        """Handler para seleção de arquivo único"""
        self._show_file_chooser(Gtk.FileChooserAction.OPEN)

    def on_select_folder(self, *args, **kwargs):
        """Handler para seleção de pasta"""
        self._show_file_chooser(Gtk.FileChooserAction.SELECT_FOLDER)

    def _show_file_chooser(self, action):
        """Mostra diálogo de seleção de arquivo/pasta"""
        dialog = Gtk.FileChooserNative(
            title=_("Selecionar") + (" " + _("Arquivo") if action == Gtk.FileChooserAction.OPEN else " " + _("Pasta")),
            transient_for=self.window,
            action=action
        )
        dialog.connect("response", self.on_file_chooser_response)
        dialog.show()

    def on_file_chooser_response(self, *args, **kwargs):
        """Processa resposta do diálogo de seleção

        Este método foi atualizado para usar *args, **kwargs para garantir consistência
        com os outros handlers, permitindo que seja chamado com diferentes assinaturas
        dependendo do contexto (GTK signals, GIO actions, etc).

        Args:
            *args: Argumentos posicionais variáveis
            **kwargs: Argumentos nomeados variáveis
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
        """Navega para o diretório anterior no histórico"""
        if self.window.navigation_manager.previous_paths:
            # Salva o caminho atual para poder avançar depois
            if hasattr(self.window, 'content_path') and self.window.content_path:
                self.window.navigation_manager.forward_paths.append(self.window.content_path)

            # Navega para o anterior
            self.window.content_path = self.window.navigation_manager.previous_paths.pop()
            self.window.navigation_manager.load_content_screen()
            self.window.back_button.set_sensitive(bool(self.window.navigation_manager.previous_paths))

    def on_open_folder(self, *args, **kwargs):
        """Abre a pasta atual no gerenciador de arquivos"""
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
                    self.terminal_manager.show_error(_("Erro ao abrir pasta: ") + str(e))

    def on_check_dependencies(self, *args, **kwargs):
        """Verifica dependências do pacote"""
        if not check_content_path(self.window, self.terminal_manager):
            return

        try:
            package_name = os.path.basename(self.window.content_path)
            self.terminal_manager.show_progress(_("Verificando dependências de") + f" {package_name}...")
            from .paru_runner import ParuRunner
            ParuRunner.run_command(["paru", "-Si", package_name], self.terminal_manager.append)
        except Exception as e:
            self.terminal_manager.show_error(_("Erro ao verificar dependências: ") + str(e))
            print(f"❌ Erro ao verificar dependências: {e}")

    def on_refresh_patches(self, *args, **kwargs):
        """Atualiza patches do repositório"""
        if not check_content_path(self.window, self.terminal_manager):
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
            self.terminal_manager.show_error(_("Erro ao atualizar patches: ") + str(e))
            print(f"❌ Erro ao atualizar patches: {e}")

    def on_update_system(self, *args, **kwargs):
        """Atualiza o sistema completo"""
        # Extraímos os parâmetros necessários para lidar com diferentes tipos de conexão
        action = None
        parameter = None

        # Se houver pelo menos um argumento, assume-se que é o action
        if len(args) > 0:
            action = args[0]

        # Se houver pelo menos dois argumentos, assume-se que o segundo é o parameter
        if len(args) > 1:
            parameter = args[1]

        # Alternativamente, os parâmetros podem vir como argumentos nomeados
        if action is None and 'action' in kwargs:
            action = kwargs['action']
        if parameter is None and 'parameter' in kwargs:
            parameter = kwargs['parameter']

        self.terminal_manager.show_progress(_("Atualizando sistema..."))
        from .paru_runner import ParuRunner
        ParuRunner.run_command(["paru", "-Syu"], self.terminal_manager.append)

    def on_check_updates(self, *args, **kwargs):
        """Verifica atualizações disponíveis"""
        # Extraímos os parâmetros necessários para lidar com diferentes tipos de conexão
        action = None
        parameter = None

        # Se houver pelo menos um argumento, assume-se que é o action
        if len(args) > 0:
            action = args[0]

        # Se houver pelo menos dois argumentos, assume-se que o segundo é o parameter
        if len(args) > 1:
            parameter = args[1]

        # Alternativamente, os parâmetros podem vir como argumentos nomeados
        if action is None and 'action' in kwargs:
            action = kwargs['action']
        if parameter is None and 'parameter' in kwargs:
            parameter = kwargs['parameter']

        self.terminal_manager.show_progress(_("Verificando atualizações..."))
        from .paru_runner import ParuRunner
        ParuRunner.run_command(["paru", "-Syu", "--dryrun"], self.terminal_manager.append)

    def on_clear_cache(self, *args, **kwargs):
        """Limpa o cache do paru"""
        # Extraímos os parâmetros necessários para lidar com diferentes tipos de conexão
        action = None
        parameter = None

        # Se houver pelo menos um argumento, assume-se que é o action
        if len(args) > 0:
            action = args[0]

        # Se houver pelo menos dois argumentos, assume-se que o segundo é o parameter
        if len(args) > 1:
            parameter = args[1]

        # Alternativamente, os parâmetros podem vir como argumentos nomeados
        if action is None and 'action' in kwargs:
            action = kwargs['action']
        if parameter is None and 'parameter' in kwargs:
            parameter = kwargs['parameter']

        self.terminal_manager.show_progress(_("Limpando cache..."))
        from .paru_runner import ParuRunner
        ParuRunner.run_command(["paru", "-Scc"], self.terminal_manager.append)

    def on_pkgbuild_info(self, *args, **kwargs):
        """Mostra informações do PKGBUILD"""
        if not check_content_path(self.window, self.terminal_manager):
            return

        if not check_pkgbuild_exists(self.window, self.terminal_manager):
            return

        try:
            # Comando para mostrar informações do PKGBUILD
            from .paru_runner import ParuRunner
            ParuRunner.run_command(["cat", os.path.join(self.window.content_path, "PKGBUILD")],
                                  self.terminal_manager.append)
        except Exception as e:
            self.terminal_manager.show_error(_("Erro ao obter informações: ") + str(e))
            print(f"❌ Erro ao obter informações: {e}")

    def on_packages_info(self, *args, **kwargs):
        """Mostra informações dos pacotes"""
        if not check_content_path(self.window, self.terminal_manager):
            return

        if not check_path_exists(self.window, self.terminal_manager):
            return

        try:
            # Comando para mostrar informações de todos os pacotes .pkg.tar.zst
            for pkg in Path(self.window.content_path).glob("*.pkg.tar.zst"):
                self.terminal_manager.show_info(_("Obtendo informações de: ") + pkg.name)
                from .paru_runner import ParuRunner
                ParuRunner.run_command(["pacman", "-Qi", str(pkg)], self.terminal_manager.append)
        except Exception as e:
            self.terminal_manager.show_error(_("Erro ao obter informações: ") + str(e))
            print(f"❌ Erro ao obter informações: {e}")

    def on_verify_packages(self, *args, **kwargs):
        """Verifica assinaturas dos pacotes corretamente"""
        if not check_content_path(self.window, self.terminal_manager):
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
                    self.terminal_manager.show_info(_("Verificando: ") + sig.name)
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
                    self.terminal_manager.show_info(_("Verificando integridade: ") + pkg_name)
                    # Comando correto para verificar a integridade de pacotes instalados
                    from .paru_runner import ParuRunner
                    ParuRunner.run_command(["pacman", "-Qk", pkg_name], self.terminal_manager.append)
        except Exception as e:
            self.terminal_manager.show_error(_("Erro ao verificar assinaturas: ") + str(e))
            print(f"❌ Erro ao verificar assinaturas: {e}")
