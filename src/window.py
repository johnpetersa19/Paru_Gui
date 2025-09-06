from gi.repository import Gtk, Gio, Adw
import os
from pathlib import Path
from .terminal import TerminalView

class PainelParuWindow(Adw.ApplicationWindow):
    """Janela principal configurada para sua estrutura atual"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("Paru GUI")
        self.set_default_size(900, 650)

        # Cria um ToolbarView para gerenciar a interface
        self.toolbar_view = Adw.ToolbarView()
        
        # Cria uma HeaderBar personalizada
        self.header_bar = Adw.HeaderBar()
        self.header_bar.set_title_widget(Adw.WindowTitle(title="Paru GUI", subtitle="Gerenciador de Pacotes AUR"))
        
        # Adiciona um botão de menu
        menu_button = Gtk.MenuButton()
        menu_icon = Gtk.Image.new_from_icon_name("open-menu-symbolic")
        menu_button.set_child(menu_icon)
        
        # Cria o menu popover
        menu_model = Gio.Menu.new()
        menu_model.append("Preferências", "app.preferences")
        menu_model.append("Sobre", "app.about")
        menu_model.append("Sair", "app.quit")
        
        # Conecta as ações
        action_group = Gio.SimpleActionGroup.new()
        
        preferences_action = Gio.SimpleAction.new("preferences", None)
        preferences_action.connect("activate", self.show_preferences)
        action_group.add_action(preferences_action)
        
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.show_about)
        action_group.add_action(about_action)
        
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda a, p: self.get_application().quit())
        action_group.add_action(quit_action)
        
        self.insert_action_group("app", action_group)
        
        # Configura o popover do menu
        popover = Gtk.PopoverMenu.new_from_model(menu_model)
        menu_button.set_popover(popover)
        
        # Adiciona o botão de menu à header bar
        self.header_bar.pack_end(menu_button)
        
        # Adiciona a header bar ao toolbar view
        self.toolbar_view.add_top_bar(self.header_bar)
        
        # Configura o conteúdo principal
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toolbar_view.set_content(self.content_box)
        
        # Define o toolbar view como conteúdo da janela
        self.set_content(self.toolbar_view)

        # Estado atual da interface
        self.current_state = None
        self.content_path = None

        # Terminal integrado para saída de comandos
        self.terminal = TerminalView()
        self.terminal.set_vexpand(True)
        
        # Carrega a tela inicial
        self.load_initial_screen()

    def load_initial_screen(self):
        """Carrega a tela inicial com os dois ícones centrais"""
        self.current_state = "initial"
        
        # Limpa o conteúdo atual
        for child in self.content_box:
            self.content_box.remove(child)
        
        # Cria o conteúdo da tela inicial
        builder = Gtk.Builder.new_from_resource(
            "/org/gnome/painel_paru/gtk/initial_screen.ui"
        )
        
        # Adiciona o conteúdo à caixa principal
        self.content_box.append(builder.get_object("initial_screen"))
        
        # Conecta os botões
        builder.get_object("file_button").connect(
            "clicked", self.on_select_file
        )
        builder.get_object("folder_button").connect(
            "clicked", self.on_select_folder
        )
        self.status_label = builder.get_object("status_label")

    def on_select_file(self, button):
        """Handler para seleção de arquivo único"""
        self._show_file_chooser(Gtk.FileChooserAction.OPEN)

    def on_select_folder(self, button):
        """Handler para seleção de pasta"""
        self._show_file_chooser(Gtk.FileChooserAction.SELECT_FOLDER)

    def _show_file_chooser(self, action):
        """Mostra diálogo de seleção de arquivo/pasta"""
        dialog = Gtk.FileChooserNative(
            title="Selecionar" + (" Arquivo" if action == Gtk.FileChooserAction.OPEN else " Pasta"),
            transient_for=self,
            action=action
        )
        dialog.connect("response", self.on_file_chooser_response)
        dialog.show()

    def on_file_chooser_response(self, dialog, response):
        """Processa resposta do diálogo de seleção"""
        if response == Gtk.ResponseType.ACCEPT:
            self.content_path = dialog.get_file().get_path()
            self.status_label.set_label(f"Analisando: {self.content_path}")

            # Detecta conteúdo e carrega tela apropriada
            from .content_detector import ContentDetector
            state = ContentDetector.detect_content(self.content_path)
            self._load_content_screen(state)

    def _load_content_screen(self, state):
        """Carrega a tela correspondente ao estado detectado"""
        self.current_state = state
        
        # Limpa o conteúdo atual
        for child in self.content_box:
            self.content_box.remove(child)

        # Mapeamento de estados para UIs
        ui_map = {
            "pkgbuild": "gtk/content_detection/pkgbuild_card.ui",
            "packages": "gtk/content_detection/packages_card.ui",
            "patches": "gtk/content_detection/patches_card.ui",
            "empty": "gtk/content_detection/empty_card.ui",
            "generic": "gtk/content_detection/pkgbuild_card.ui"
        }

        # Carrega o recurso correto
        builder = Gtk.Builder.new_from_resource(
            f"/org/gnome/painel_paru/{ui_map.get(state, 'gtk/initial_screen.ui')}"
        )

        # Configura o conteúdo principal
        if state == "pkgbuild":
            self._setup_pkgbuild_card(builder)
        elif state == "packages":
            self._setup_packages_card(builder)
        elif state == "empty":
            self._setup_empty_card(builder)
        elif state == "patches":
            self._setup_patches_card(builder)

        self.content_box.append(builder.get_object(f"{state}_card"))
        self.status_label.set_label(f"Modo: {state.replace('_', ' ').title()}")

    def _setup_pkgbuild_card(self, builder):
        """Configura ações para o card PKGBUILD"""
        builder.get_object("build_button").connect(
            "clicked", lambda _: self._build_pkgbuild()
        )
        builder.get_object("edit_button").connect(
            "clicked", lambda _: self._edit_pkgbuild()
        )
        builder.get_object("deps_button").connect(
            "clicked", lambda _: self._show_dependencies()
        )
        builder.get_object("sources_button").connect(
            "clicked", lambda _: self._download_sources()
        )

        # Atualiza o caminho exibido
        builder.get_object("pkgbuild_path").set_label(
            f"Caminho: {Path(self.content_path).parent}"
        )

    def _setup_empty_card(self, builder):
        """Configura ações para o card de pasta vazia"""
        aur_search = builder.get_object("aur_search")

        # Atualiza botão de download conforme digitação
        aur_search.connect("changed", lambda entry:
            builder.get_object("download_button").set_sensitive(bool(entry.get_text().strip()))
        )

        # Configura busca ao pressionar Enter
        aur_search.connect("activate", lambda _:
            builder.get_object("download_button").clicked()
        )

        # Configura botão de download
        builder.get_object("download_button").connect(
            "clicked", lambda _: self._download_pkgbuild(
                aur_search.get_text(),
                builder.get_object("ssh_toggle").get_active(),
                builder.get_object("comments_toggle").get_active()
            )
        )

    def _setup_patches_card(self, builder):
        """Configura ações para o card de patches"""
        # Preenche lista de patches
        patches_list = builder.get_object("patches_list")
        patch_template = builder.get_object("patch_template")

        # Limpa itens existentes
        while patches_list.get_first_child():
            patches_list.remove(patches_list.get_first_child())

        # Adiciona patches detectados
        from .content_detector import ContentDetector
        patches = ContentDetector.get_patches_in_folder(self.content_path)

        for patch in patches:
            row = Gtk.ListBoxRow()
            action_row = Adw.ActionRow(
                title=patch.name,
                subtitle=self._get_patch_description(patch)
            )
            row.set_child(action_row)
            patches_list.append(row)

        # Configura ações
        builder.get_object("apply_patches").connect(
            "clicked", lambda _: self._apply_patches()
        )
        builder.get_object("view_patch").connect(
            "clicked", lambda _: self._view_selected_patch(patches_list)
        )
        builder.get_object("refresh_list").connect(
            "clicked", lambda _: self._load_content_screen("patches")
        )

    def _get_patch_description(self, patch_path):
        """Gera descrição para o patch (simulação)"""
        # Na implementação real, isso leria metadados do patch
        if "fix" in patch_path.name.lower():
            return "Corrige bugs críticos"
        elif "security" in patch_path.name.lower():
            return "Atualização de segurança"
        return "Modificações gerais"

    def _build_pkgbuild(self):
        """Simulação de build do PKGBUILD"""
        print(f"Building PKGBUILD at {self.content_path}")
        # Na implementação real: chamar build_manager.py

    def _download_pkgbuild(self, pkg_name, use_ssh, show_comments):
        """Simulação de download do PKGBUILD do AUR"""
        print(f"Downloading {pkg_name} from AUR (SSH: {use_ssh}, Comments: {show_comments})")
        # Na implementação real: chamar aur_downloader.py

    def _apply_patches(self):
        """Simulação de aplicação de patches"""
        print(f"Applying patches from {self.content_path}")
        # Na implementação real: executar patch commands

    def _view_selected_patch(self, patches_list):
        """Visualiza o patch selecionado"""
        selected_row = patches_list.get_selected_row()
        if selected_row:
            patch_name = selected_row.get_child().get_title()
            print(f"Viewing patch: {patch_name}")
            # Na implementação real: abrir diff viewer

    def go_back(self, *args):
        """Volta para a tela inicial"""
        self.load_initial_screen()
    
    def show_preferences(self, action, parameter):
        """Mostra a janela de preferências"""
        print("Abrindo preferências")
        # Na implementação real: criar e mostrar a janela de preferências
    
    def show_about(self, action, parameter):
        """Mostra a janela Sobre"""
        about = Adw.AboutWindow(
            transient_for=self,
            application_name="Painel Paru",
            application_icon="org.gnome.painel_paru",
            developer_name="Seu Nome",
            version="0.1.0",
            developers=["Seu Nome <seu@email.com>"],
            copyright="© 2023 Seu Nome"
        )
        about.present()
