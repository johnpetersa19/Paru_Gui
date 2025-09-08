from gi.repository import Gtk, Adw
import os
import subprocess
import gettext
_ = gettext.gettext

class ConflictResolver:
    """Gerencia resolução de conflitos de pacotes"""
    
    @staticmethod
    def show_conflict_dialog(parent_window, conflicts, callback):
        """
        Mostra diálogo de resolução de conflitos
        :param parent_window: Janela pai para o diálogo
        :param conflicts: Lista de conflitos detectados
        :param callback: Callback para quando a resolução for concluída
        """
        if not conflicts:
            callback(True)
            return
        
        # Cria o diálogo
        dialog = Adw.Window(
            transient_for=parent_window,
            modal=True,
            title=_("Conflitos Detectados"),
            default_width=800,
            default_height=600
        )
        
        # Cria o conteúdo principal
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
        close_button.connect("clicked", lambda _: {
            dialog.close(),
            callback(False)
        })
        header.pack_end(close_button)
        
        # Botão de ação principal
        action_button = Gtk.Button(
            label=_("Resolver e Continuar"),
            css_classes=["suggested-action"]
        )
        header.pack_end(action_button)
        
        # Cria o conteúdo principal
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        
        # Label informativo
        info_label = Gtk.Label(
            label=_("Foram detectados conflitos com outros pacotes. Selecione como resolver cada conflito."),
            wrap=True,
            xalign=0,
            margin_bottom=15
        )
        main_box.append(info_label)
        
        # Cria um Paned para dividir a tela
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        
        # Painel ESQUERDA: Lista de conflitos
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        left_label = Gtk.Label(
            label=_("Conflitos"), 
            xalign=0,
            css_classes=["heading"]
        )
        left_box.append(left_label)
        
        # Lista de conflitos
        conflicts_list = Gtk.ListBox()
        conflicts_list.set_selection_mode(Gtk.SelectionMode.NONE)
        conflicts_list.set_css_classes(["boxed-list"])
        
        # Preenche a lista de conflitos
        for conflict in conflicts:
            row = Adw.ActionRow(title=conflict["package"])
            subtitle = f"{conflict['current']} → {conflict['new']}"
            row.set_subtitle(subtitle)
            
            # Adiciona switch para permitir resolução
            switch = Gtk.Switch()
            switch.set_active(True)
            switch.set_valign(Gtk.Align.CENTER)
            row.add_suffix(switch)
            
            # Armazena o conflito nos dados do row
            row.conflict = conflict
            conflicts_list.append(row)
        
        left_scroll = Gtk.ScrolledWindow()
        left_scroll.set_vexpand(True)
        left_scroll.set_child(conflicts_list)
        left_box.append(left_scroll)
        
        # Painel DIREITA: Detalhes do conflito
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
        
        # Adiciona os painéis ao Paned
        paned.set_start_child(left_box)
        paned.set_end_child(right_box)
        paned.set_position(400)
        
        main_box.append(paned)
        content.set_content(main_box)
        
        # Configura o callback quando um conflito é selecionado
        def on_row_selected(row):
            if hasattr(row, 'conflict'):
                conflict = row.conflict
                details_buffer.set_text(
                    _("Conflito detectado com o pacote: {}\n\n"
                      "Versão atual: {}\n"
                      "Nova versão: {}\n\n"
                      "Este conflito ocorre porque ambos os pacotes tentam "
                      "instalar o mesmo arquivo ou recurso.").format(
                        conflict["package"],
                        conflict["current"],
                        conflict["new"]
                      )
                )
        
        # Configura a seleção de conflitos
        for row in conflicts_list:
            row.connect("activated", lambda r: on_row_selected(r))
        
        # Configura os handlers
        action_button.connect("clicked", lambda _: {
            dialog.close(),
            callback(True)
        })
        
        # Apresenta o diálogo
        dialog.present()

    @staticmethod
    def check_for_conflicts(package_name):
        """Verifica se há conflitos para o pacote especificado"""
        try:
            # Comando para verificar conflitos
            result = subprocess.run(
                ["paru", "-Si", package_name],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Processa a saída para encontrar conflitos
            conflicts = []
            in_conflicts_section = False
            
            for line in result.stdout.splitlines():
                if line.startswith("Conflicts With:"):
                    in_conflicts_section = True
                    packages = line.replace("Conflicts With:", "").strip()
                    for pkg in packages.split():
                        if pkg != "None" and pkg != "-":
                            conflicts.append({
                                "package": pkg,
                                "current": _("instalado"),
                                "new": _("será instalado")
                            })
                elif in_conflicts_section and line.strip() == "":
                    break
                elif in_conflicts_section:
                    # Linhas adicionais na seção de conflitos
                    for pkg in line.strip().split():
                        if pkg != "None" and pkg != "-":
                            conflicts.append({
                                "package": pkg,
                                "current": _("instalado"),
                                "new": _("será instalado")
                            })
            
            return conflicts
        except subprocess.CalledProcessError as e:
            print(f"Erro ao verificar conflitos: {e}")
            return []
        except Exception as e:
            print(f"Erro inesperado ao verificar conflitos: {e}")
            return []
