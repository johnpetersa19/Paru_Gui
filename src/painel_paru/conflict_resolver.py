# src/painel_paru/conflict_resolver.py
from gi.repository import Gtk, Adw
import os
import subprocess
import gettext
from functools import partial

_ = gettext.gettext


class ConflictResolver:
    """
    Gerencia resolução de conflitos de pacotes.
    Detecta conflitos via `paru -Si` (AUR) ou diretamente do PKGBUILD.
    """

    @staticmethod
    def extract_conflicts_from_pkgbuild(pkgbuild_path):
        """
        Extrai conflitos diretamente do arquivo PKGBUILD.
        :param pkgbuild_path: Caminho para o PKGBUILD
        :return: Lista de conflitos no formato {"package": str, "current": str, "new": str}
        """
        conflicts = []
        try:
            if not os.path.exists(pkgbuild_path):
                return conflicts

            with open(pkgbuild_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("conflicts="):
                        # Remove 'conflicts=(' e extrai pacotes
                        content = line.split('=', 1)[1].strip("()'")
                        for pkg in content.replace("'", "").split():
                            pkg = pkg.strip()
                            if pkg and pkg not in ["None", "-"]:
                                conflicts.append({
                                    "package": pkg,
                                    "current": _("instalado"),
                                    "new": _("será instalado")
                                })
                        break
        except Exception as e:
            print(f"Erro ao ler PKGBUILD para conflitos: {e}")
        return conflicts

    @staticmethod
    def check_for_conflicts(package_name):
        """
        Verifica conflitos no AUR usando `paru -Si`.
        :param package_name: Nome do pacote no AUR
        :return: Lista de conflitos
        """
        try:
            result = subprocess.run(
                ["paru", "-Si", package_name],
                capture_output=True,
                text=True,
                check=True
            )

            conflicts = []
            in_conflicts_section = False

            for line in result.stdout.splitlines():
                if line.startswith("Conflicts With:"):
                    in_conflicts_section = True
                    packages = line.replace("Conflicts With:", "").strip()
                    for pkg in packages.split():
                        if pkg not in ["None", "-", ""]:
                            conflicts.append({
                                "package": pkg,
                                "current": _("instalado"),
                                "new": _("será instalado")
                            })
                elif in_conflicts_section and line.strip() == "":
                    break  # Fim da seção
                elif in_conflicts_section:
                    # Linhas adicionais na seção de conflitos
                    for pkg in line.strip().split():
                        if pkg not in ["None", "-", ""]:
                            conflicts.append({
                                "package": pkg,
                                "current": _("instalado"),
                                "new": _("será instalado")
                            })

            return conflicts

        except subprocess.CalledProcessError as e:
            print(f"⚠️ AUR: Pacote '{package_name}' não encontrado ou erro no paru: {e}")
            return []
        except FileNotFoundError:
            print("❌ Erro: 'paru' não está instalado ou não está no PATH.")
            return []
        except Exception as e:
            print(f"❌ Erro inesperado ao verificar conflitos: {e}")
            return []

    @staticmethod
    def show_conflict_dialog(parent_window, conflicts, callback, terminal=None):
        """
        Mostra diálogo de resolução de conflitos com suporte a seleção e detalhes.
        :param parent_window: Janela pai (ex: PainelParuWindow)
        :param conflicts: Lista de conflitos
        :param callback: Função chamada com dicionário de resoluções ou None se cancelado
        :param terminal: Terminal opcional para log (ex: self.terminal.append)
        """
        if not conflicts:
            if terminal:
                terminal.append(_("✅ Nenhum conflito detectado."), "success")
            callback({})  # Dicionário vazio indica nenhum conflito
            return

        # Cria o diálogo
        dialog = Adw.Window(
            transient_for=parent_window,
            modal=True,
            title=_("Conflitos Detectados"),
            default_width=800,
            default_height=600
        )

        # Conteúdo principal
        content = Adw.ToolbarView()
        dialog.set_content(content)

        # Header bar
        header = Adw.HeaderBar()
        content.add_top_bar(header)

        # Botão de fechar
        close_button = Gtk.Button(
            icon_name="window-close-symbolic",
            tooltip_text=_("Fechar")
        )
        close_button.connect("clicked", lambda *args, **kwargs: {
            dialog.close(),
            callback(None)  # None indica cancelamento
        })
        header.pack_end(close_button)

        # Botão de ação principal
        action_button = Gtk.Button(
            label=_("Resolver e Continuar"),
            css_classes=["suggested-action"]
        )
        header.pack_end(action_button)

        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        content.set_content(main_box)

        # Label informativo
        info_label = Gtk.Label(
            label=_("Foram detectados conflitos com outros pacotes. "
                    "Use os switches para escolher como resolver cada conflito."),
            wrap=True,
            xalign=0,
            margin_bottom=15
        )
        main_box.append(info_label)

        # Paned: Lista de conflitos + Detalhes
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        paned.set_position(400)
        main_box.append(paned)

        # Painel ESQUERDA: Lista de conflitos
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        left_label = Gtk.Label(
            label=_("Conflitos"),
            xalign=0,
            css_classes=["heading"]
        )
        left_box.append(left_label)

        conflicts_list = Gtk.ListBox()
        conflicts_list.set_selection_mode(Gtk.SelectionMode.NONE)
        conflicts_list.set_css_classes(["boxed-list"])
        left_scroll = Gtk.ScrolledWindow()
        left_scroll.set_vexpand(True)
        left_scroll.set_child(conflicts_list)
        left_box.append(left_scroll)
        paned.set_start_child(left_box)

        # Painel DIREITA: Detalhes
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        right_label = Gtk.Label(
            label=_("Detalhes"),
            xalign=0,
            css_classes=["heading"]
        )
        right_box.append(right_label)

        details_text = Gtk.TextView(
            editable=False,
            monospace=True,
            wrap_mode=Gtk.WrapMode.WORD
        )
        details_buffer = details_text.get_buffer()
        details_buffer.set_text(_("Selecione um conflito para ver detalhes."))

        right_scroll = Gtk.ScrolledWindow()
        right_scroll.set_vexpand(True)
        right_scroll.set_child(details_text)
        right_box.append(right_scroll)
        paned.set_end_child(right_box)

        # Dicionário para armazenar as resoluções escolhidas pelo usuário
        resolutions = {}
        
        # Função de seleção de conflito
        def on_row_selected(*args, **kwargs):
            # O primeiro argumento é a row
            if args and hasattr(args[0], 'conflict'):
                conflict = args[0].conflict
                details_buffer.set_text(
                    _("Conflito detectado com o pacote: {pkg}\n\n"
                      "Estado atual: {current}\n"
                      "Estado após instalação: {new}\n\n"
                      "Este conflito ocorre porque ambos os pacotes tentam "
                      "instalar os mesmos arquivos ou recursos do sistema.").format(
                        pkg=conflict["package"],
                        current=conflict["current"],
                        new=conflict["new"]
                    )
                )

        # Preenche a lista de conflitos com eventos seguros
        for conflict in conflicts:
            row = Adw.ActionRow(title=conflict["package"])
            subtitle = f"{conflict['current']} → {conflict['new']}"
            row.set_subtitle(subtitle)

            switch = Gtk.Switch()
            switch.set_active(True)
            switch.set_valign(Gtk.Align.CENTER)
            switch.set_tooltip_text(_(
                "Ativado: Sobrescrever arquivos em conflito (Aceitar Novo)\n"
                "Desativado: Manter o pacote atual (Manter Meu)"
            ))
            row.add_suffix(switch)

            # Armazena o conflito na row
            row.conflict = conflict
            conflicts_list.append(row)

            # Conecta evento com referência segura
            row.connect("activated", on_row_selected)
            
            # Inicializa o dicionário com o estado atual do switch
            resolutions[conflict["package"]] = True
            
            # Conecta o evento do switch para atualizar as resoluções
            def on_switch_toggled(*args, **kwargs):
                # O primeiro argumento é o switch
                if args:
                    switch = args[0]
                    # Usamos o pkg do closure (capturado na definição da função)
                    # Precisamos acessar o pkg do escopo externo
                    if hasattr(switch, 'pkg'):
                        pkg = switch.pkg
                        resolutions[pkg] = switch.get_active()
            
            # Armazenamos o pkg no switch para acessar no callback
            switch.pkg = conflict["package"]
            switch.connect("notify::active", on_switch_toggled)

        # Ação ao clicar em "Resolver e Continuar"
        def on_action_clicked(*args, **kwargs):
            dialog.close()
            callback(resolutions)  # Passa o dicionário de resoluções

        action_button.connect("clicked", on_action_clicked)

        # Apresenta o diálogo
        dialog.present()
