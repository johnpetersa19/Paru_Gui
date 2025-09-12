# window_patches.py
"""
Módulo responsável pela funcionalidade de aplicação e visualização de patches.

Este módulo contém a classe WindowPatches que gerencia todas as operações
relacionadas a patches no aplicativo, incluindo aplicação, visualização e
atualização da lista de patches.
"""

from pathlib import Path
from gi.repository import Gtk
from .paru_runner import ParuRunner
import gettext
import os

_ = gettext.gettext

class WindowPatches:
    """
    Classe que gerencia a funcionalidade de patches na interface do usuário.

    Esta classe contém todos os métodos relacionados à aplicação, visualização
    e gerenciamento de patches no contexto do PKGBUILD.
    """

    def __init__(self, window):
        """
        Inicializa a funcionalidade de patches.

        Args:
            window: Referência à janela principal para acesso aos componentes da UI
        """
        self.window = window
        self.terminal = window.terminal
        self.content_path = None

    def setup_patches_ui(self, builder):
        """
        Configura os elementos da UI relacionados a patches.

        Args:
            builder: Gtk.Builder para acessar os objetos da interface
        """
        apply_button = builder.get_object("apply_patches")
        view_button = builder.get_object("view_patch")
        refresh_button = builder.get_object("refresh_list")

        if apply_button:
            apply_button.connect("clicked", self.on_apply_patches)
        if view_button:
            view_button.connect("clicked", self.on_view_patch)
        if refresh_button:
            refresh_button.connect("clicked", self.on_refresh_patches)

    def on_apply_patches(self, button):
        """
        Aplica patches ao PKGBUILD do diretório atual.

        Este método:
        1. Verifica se há um diretório selecionado
        2. Localiza todos os arquivos .patch no diretório
        3. Aplica cada patch usando o comando patch
        4. Exibe feedback no terminal

        Args:
            button: O botão que disparou o evento
        """
        if not hasattr(self.window, 'content_path') or not self.window.content_path:
            self.terminal.append(_("❌ Nenhum diretório selecionado."), "error")
            return

        self.content_path = self.window.content_path

        try:
            self.terminal.append(_("🔧 Aplicando patches..."), "progress")

            # Lógica para aplicar patches
            patches = list(Path(self.content_path).glob("*.patch"))
            if not patches:
                self.terminal.append(_("⚠️ Nenhum patch encontrado"), "info")
                return

            for patch in patches:
                self.terminal.append(f"Aplicando {patch.name}...", "info")
                ParuRunner.run_command(["patch", "-p1", "-i", str(patch)], self.terminal.append)

            self.terminal.append(_("✅ Patches aplicados com sucesso"), "success")
        except Exception as e:
            self.terminal.append(f"❌ {_('Erro ao aplicar patches:')} {str(e)}", "error")
            print(f"❌ Erro ao aplicar patches: {e}")

    def on_view_patch(self, button):
        """
        Visualiza o conteúdo de um patch.

        Este método:
        1. Verifica se há um diretório selecionado
        2. Localiza todos os arquivos .patch no diretório
        3. Exibe o conteúdo do primeiro patch encontrado

        Args:
            button: O botão que disparou o evento
        """
        if not hasattr(self.window, 'content_path') or not self.window.content_path:
            self.terminal.append(_("❌ Nenhum diretório selecionado."), "error")
            return

        self.content_path = self.window.content_path

        try:
            patches = list(Path(self.content_path).glob("*.patch"))
            if not patches:
                self.terminal.append(_("⚠️ Nenhum patch encontrado"), "info")
                return

            # Mostra o conteúdo do primeiro patch como exemplo
            patch = patches[0]
            self.terminal.append(f"Conteúdo de {patch.name}:", "info")
            with open(patch, 'r') as f:
                self.terminal.append(f.read(), "normal")
        except Exception as e:
            self.terminal.append(f"❌ {_('Erro ao visualizar patch:')} {str(e)}", "error")
            print(f"❌ Erro ao visualizar patch: {e}")

    def on_refresh_patches(self, button):
        """
        Atualiza a lista de patches exibida na interface.

        Este método:
        1. Verifica se há um diretório selecionado
        2. Simula a atualização da lista de patches
        3. (Futuramente) atualizaria a interface com a nova lista

        Args:
            button: O botão que disparou o evento
        """
        if not hasattr(self.window, 'content_path') or not self.window.content_path:
            self.terminal.append(_("❌ Nenhum diretório selecionado."), "error")
            return

        self.content_path = self.window.content_path

        try:
            self.terminal.append(_("🔄 Atualizando lista de patches..."), "progress")

            # Aqui você implementaria a lógica real de atualização
            # Atualmente, apenas simula o processo
            patches = list(Path(self.content_path).glob("*.patch"))
            count = len(patches)

            if count > 0:
                self.terminal.append(_("✅ {} patches encontrados").format(count), "success")
            else:
                self.terminal.append(_("ℹ️ Nenhum patch encontrado"), "info")

        except Exception as e:
            self.terminal.append(f"❌ {_('Erro ao atualizar lista:')} {str(e)}", "error")
            print(f"❌ Erro ao atualizar lista: {e}")

    def get_patches_list(self):
        """
        Retorna a lista de patches no diretório atual.

        Returns:
            list: Lista de objetos Path dos arquivos .patch encontrados
        """
        if not hasattr(self.window, 'content_path') or not self.window.content_path:
            return []

        self.content_path = self.window.content_path
        return list(Path(self.content_path).glob("*.patch"))

    def update_patches_ui(self):
        """
        Atualiza a interface do usuário com a lista atual de patches.

        Nota: Este método deve ser implementado para atualizar a interface
        com base na lista real de patches encontrados.
        """
        patches = self.get_patches_list()

        # Aqui você implementaria a lógica para atualizar a UI
        # Por exemplo, atualizar uma lista ou grid de patches
        if hasattr(self.window, 'patches_list'):
            # Limpa a lista atual
            for row in self.window.patches_list:
                self.window.patches_list.remove(row)

            # Adiciona os novos patches
            for patch in patches:
                row = Gtk.ListBoxRow()
                box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

                label = Gtk.Label(label=patch.name, hexpand=True, halign=Gtk.Align.START)
                box.append(label)

                row.set_child(box)
                self.window.patches_list.append(row)
