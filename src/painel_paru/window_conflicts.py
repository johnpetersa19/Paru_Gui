from gi.repository import Gtk, Adw
import os
import gettext
from .conflict_resolver import ConflictResolver

_ = gettext.gettext

class WindowConflicts:
    """Módulo de conflitos para a janela principal - gerencia detecção e resolução de conflitos"""

    def on_build(self, button, install=False):
        """Inicia processo de build com verificação de conflitos"""
        if not hasattr(self, 'content_path') or not self.content_path:
            self.terminal.append(_("❌ Nenhum diretório selecionado."), "error")
            return

        if not os.path.exists(self.content_path):
            self.terminal.append(_("❌ Caminho não existe."), "error")
            return

        # Obtém as configurações necessárias
        review_pkgbuild = self.settings.get_boolean("review-pkgbuild")
        skip_review = self.settings.get_boolean("skip-review")
        clean_after = self.settings.get_boolean("clean-after")
        pkgbuild_path = os.path.join(self.content_path, "PKGBUILD")

        def start_build():
            # Primeiro verifica se há conflitos
            self.terminal.append(_("🔍 Verificando possíveis conflitos..."), "progress")

            # Extrai o nome do pacote do PKGBUILD
            package_name = None
            try:
                with open(pkgbuild_path, 'r') as f:
                    for line in f:
                        if line.startswith("pkgname="):
                            package_name = line.split("=")[1].strip().strip('"')
                            break
            except Exception as e:
                self.terminal.append(f"⚠️ {_('Erro ao ler PKGBUILD:')} {str(e)}", "info")

            # Se não encontrou o nome do pacote, usa o nome da pasta
            if not package_name:
                package_name = os.path.basename(self.content_path)

            # Verifica conflitos
            conflicts = ConflictResolver.check_for_conflicts(package_name)
            if conflicts:
                self.terminal.append(_("⚠️ {} conflitos detectados. Resolvendo...").format(len(conflicts)), "info")

                # Define o callback para continuar o build após resolver conflitos
                self.build_callback = lambda: self._continue_build(install)

                # Mostra o diálogo de conflitos
                ConflictResolver.show_conflict_dialog(self, conflicts, self._on_conflict_resolved)
            else:
                self.terminal.append(_("✅ Nenhum conflito detectado"), "success")
                self._continue_build(install)

        # Se a revisão estiver ativada e não devemos pular
        if review_pkgbuild and not skip_review:
            if hasattr(self, 'show_pkgbuild_review_dialog'):
                self.show_pkgbuild_review_dialog(pkgbuild_path, start_build)
            else:
                start_build()
        else:
            start_build()

    def _continue_build(self, install):
        """Continua o processo de build após verificar conflitos"""
        action = _("Compilando e instalando") if install else _("Compilando")
        self.terminal.append(f"{action} {os.path.basename(self.content_path)}...", "progress")
        self.terminal.show_progress(True, 0.1)

        # Inicia o build com as configurações
        if hasattr(self, 'build_manager'):
            self.build_manager.start_build(
                self.content_path,
                install,
                self.terminal.append,
                clean_after=self.settings.get_boolean("clean-after"),
                skip_review=self.settings.get_boolean("skip-review")
            )

    def _on_conflict_resolved(self, success):
        """Callback chamado após resolver conflitos"""
        if success:
            self.terminal.append(_("✅ Conflitos resolvidos com sucesso"), "success")

            # Executa o callback de build
            if self.build_callback:
                self.build_callback()
                self.build_callback = None
        else:
            self.terminal.append(_("❌ Operação cancelada pelo usuário"), "error")
            self.terminal.show_progress(False)
