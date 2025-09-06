from gi.repository import Gtk, Adw
import os
import subprocess

class ConflictResolver:
    """Gerencia resolução de conflitos de pacotes"""
    
    @staticmethod
    def show_conflict_dialog(parent_window, conflicts):
        """
        Mostra diálogo de resolução de conflitos
        :param parent_window: Janela pai para o diálogo
        :param conflicts: Lista de conflitos detectados
        """
        if not conflicts:
            return True
            
        # Carrega o diálogo do UI
        builder = Gtk.Builder.new_from_resource(
            "/org/gnome/Example/gtk/conflict_resolver/conflict_dialog.ui"
        )
        dialog = builder.get_object("conflict_dialog")
        dialog.set_transient_for(parent_window)
        
        # Preenche a lista de conflitos
        conflicts_list = builder.get_object("conflicts_list")
        
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
        
        # Configura os handlers
        builder.get_object("resolve_button").connect(
            "clicked", lambda _: ConflictResolver._resolve_selected(dialog, conflicts_list)
        )
        builder.get_object("cancel_button").connect(
            "clicked", lambda _: dialog.close()
        )
        
        dialog.present()
        return False
    
    @staticmethod
    def _resolve_selected(dialog, conflicts_list):
        """Processa resolução dos conflitos selecionados"""
        selected = []
        row = conflicts_list.get_first_child()
        
        while row:
            if row.get_child().get_last_child().get_active():  # Switch está ativo
                selected.append(row.conflict)
            row = row.get_next_sibling()
        
        if selected:
            # Aqui você implementaria a lógica real de resolução
            # Por enquanto, só fechamos o diálogo
            dialog.close()
            return True
        return False
    
    @staticmethod
    def check_for_conflicts(package_name):
        """Verifica se há conflitos para o pacote especificado"""
        try:
            # Comando para verificar conflitos (simulação)
            result = subprocess.run(
                ["paru", "-Si", package_name],
                capture_output=True,
                text=True
            )
            
            # Processa a saída para encontrar conflitos
            conflicts = []
            for line in result.stdout.splitlines():
                if line.startswith("Conflicts With:"):
                    packages = line.replace("Conflicts With:", "").strip()
                    for pkg in packages.split():
                        if pkg != "None":
                            conflicts.append({
                                "package": pkg,
                                "current": "installed_version",
                                "new": "new_version"
                            })
            
            return conflicts
        except Exception as e:
            print(f"Erro ao verificar conflitos: {e}")
            return []
