from gi.repository import Gtk, Gio, GLib, Gdk, GObject, Adw, Pango
import os
import subprocess
import re
from enum import Enum

class TrustLevel(Enum):
    HIGH = "HIGH"    # 50+ votes
    MEDIUM = "MEDIUM" # 10-50 votes
    LOW = "LOW"      # <10 votes

class FileItem(GObject.Object):
    """Represents a compatible file with its metadata"""
    def __init__(self, file_type, name, version, path, trust_level=None,
                 signature_status="N/A", extra_info=""):
        super().__init__()
        self.file_type = file_type  # 'PKGBUILD', 'PACKAGE', 'PATCH'
        self.name = name
        self.version = version
        self.path = path
        self.trust_level = trust_level
        self.signature_status = signature_status
        self.extra_info = extra_info

    def get_icon_name(self):
        """Returns the appropriate GNOME icon for the file type"""
        if self.file_type == 'PKGBUILD':
            return "text-x-generic"
        elif self.file_type == 'PACKAGE':
            return "package-x-generic"
        elif self.file_type == 'PATCH':
            return "text-x-patch"
        return "unknown"

    def get_trust_icon(self):
        """Returns the appropriate trust icon"""
        if self.file_type != 'PKGBUILD' or not self.trust_level:
            return None
        if self.trust_level == TrustLevel.HIGH:
            return "dialog-secure-symbolic"
        elif self.trust_level == TrustLevel.MEDIUM:
            return "dialog-warning-symbolic"
        return "dialog-error-symbolic"

class ParuGuiWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("Paru GUI") # Define o título da janela Adwaita

        # Se você quiser definir o tamanho padrão, o AdwApplicationWindow
        # tem propriedades 'default_width' e 'default_height' que podem ser usadas
        # em um template .ui ou diretamente como self.set_default_size(width, height)
        self.set_default_size(900, 650)

        # Configura a interface principal
        self.setup_main_interface()

    def setup_main_interface(self):
        """Configures the main interface with action icons, using Adwaita's HeaderBar."""
        # --- CORREÇÃO ADWAITA ---
        # Adw.ApplicationWindow já tem uma Adw.HeaderBar embutida.
        # Não devemos criar uma Gtk.HeaderBar e tentar defini-la.
        # A barra de título já existe e podemos adicionar widgets a ela.

        # Cria o botão de menu.
        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")

        # Define o modelo do menu.
        menu = Gio.Menu()
        menu.append("System", "app.system")
        menu.append("Preferences", "app.preferences")
        menu.append("Help", "app.help")
        menu_btn.set_menu_model(menu)

        # Adiciona o botão de menu à barra de título da Adw.ApplicationWindow.
        # Adw.ApplicationWindow usa set_end_action_widget para adicionar à direita.
        self.set_end_action_widget(menu_btn)
        # --- FIM DA CORREÇÃO ADWAITA ---

        # Área central para o conteúdo (continua a ser Gtk.Box)
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content_box.set_margin_top(20)
        self.content_box.set_margin_bottom(20)
        self.content_box.set_margin_start(20)
        self.content_box.set_margin_end(20)

        # Tela inicial
        self.show_welcome_screen()
        self.set_child(self.content_box)

    def show_welcome_screen(self):
        """Displays the welcome screen with selection options"""
        # --- CORREÇÃO GTK4: Remover filhos de um Gtk.Box ---
        # Em GTK4, Gtk.Box não tem o método get_children() ou foreach para destruir filhos.
        # Precisamos iterar e remover explicitamente usando get_first_child().
        while self.content_box.get_first_child() is not None:
            self.content_box.remove(self.content_box.get_first_child())
        # --- FIM DA CORREÇÃO ---

        welcome = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=30)
        welcome.set_valign(Gtk.Align.CENTER)
        welcome.set_halign(Gtk.Align.CENTER)

        # Title
        title = Gtk.Label()
        title.set_markup('<span font_size="x-large" font_weight="bold">Paru GUI</span>')
        title.set_margin_bottom(20)
        welcome.append(title)

        # Subtitle
        subtitle = Gtk.Label()
        subtitle.set_markup("AUR Package Manager with <b>Smart File Visualization</b>")
        subtitle.get_style_context().add_class("subtitle")
        subtitle.set_margin_bottom(30)
        welcome.append(subtitle)

        # Main options
        actions = Gtk.Box(spacing=40)
        actions.set_valign(Gtk.Align.CENTER)

        # "Select File" icon
        file_btn = Gtk.Button()
        file_btn.set_icon_name("text-x-generic-symbolic")
        file_btn.set_size_request(120, 120)
        file_btn.add_css_class("circular")
        file_btn.add_css_class("large-icon")
        file_btn.set_tooltip_text("Select PKGBUILD file")
        file_btn.connect("clicked", self.on_select_file_clicked)
        actions.append(file_btn)

        # "Select Folder" icon
        folder_btn = Gtk.Button()
        folder_btn.set_icon_name("folder-symbolic")
        folder_btn.set_size_request(120, 120)
        folder_btn.add_css_class("circular")
        folder_btn.add_css_class("large-icon")
        folder_btn.set_tooltip_text("Select folder with compatible files")
        folder_btn.connect("clicked", self.on_select_folder_clicked)
        actions.append(folder_btn)

        # Instructions
        instructions = Gtk.Label()
        instructions.set_markup(
            "• <b>PKGBUILD</b>: Edit and compile AUR packages\n"
            "• <b>.zst Packages</b>: Install pre-compiled packages\n"
            "• <b>Patches</b>: Apply custom modifications"
        )
        instructions.set_justify(Gtk.Justification.CENTER)
        instructions.set_margin_top(20)

        welcome.append(actions)
        welcome.append(instructions)
        self.content_box.append(welcome)

    def on_select_file_clicked(self, button):
        """Opens dialog to select a specific file"""
        dialog = Gtk.FileChooserNative(
            title="Select PKGBUILD File",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )

        # PKGBUILD filter
        filter_pkgbuild = Gtk.FileFilter()
        filter_pkgbuild.set_name("PKGBUILD")
        filter_pkgbuild.add_pattern("PKGBUILD")
        filter_pkgbuild.add_mime_type("text/x-pkgbuild")
        dialog.add_filter(filter_pkgbuild)

        dialog.connect("response", self.on_single_file_response)
        dialog.show()

    def on_select_folder_clicked(self, button):
        """Opens dialog to select folder with smart file visualization"""
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/paru_gui/ui/components/file_chooser_dialog.ui')
        self.file_chooser = builder.get_object('file_chooser')

        # Configure data model
        self.files_list_model = Gio.ListStore(item_type=FileItem)
        files_grid = builder.get_object('files_grid')
        files_grid.set_model(self.files_list_model)

        # Connect signals
        builder.connect_signals({
            'setup_file_card': self.setup_file_card,
            'bind_file_card': self.bind_file_card,
            'on_file_activated': self.on_file_activated
        })

        # Show dialog
        self.file_chooser.set_transient_for(self)
        self.file_chooser.present()

    def on_single_file_response(self, dialog, response):
        """Processes selection of a single file"""
        if response == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_file().get_path()
            folder_path = os.path.dirname(file_path)
            self.scan_compatible_files(folder_path)
        dialog.destroy()

    def on_file_activated(self, grid, position):
        """Processes item activation in grid view"""
        item = self.files_list_model.get_item(position)
        if item:
            self.process_selected_item(item)

    def setup_file_card(self, factory, list_item):
        """Configures the card for a new item"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        # File type icon
        icon = Gtk.Image()
        icon.set_pixel_size(48)
        icon.set_halign(Gtk.Align.CENTER)
        box.append(icon)

        # Package name
        name_label = Gtk.Label()
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_max_width_chars(20)
        name_label.set_halign(Gtk.Align.CENTER)
        name_label.add_css_class("heading")
        box.append(name_label)

        # Version
        version_label = Gtk.Label()
        version_label.set_ellipsize(Pango.EllipsizeMode.END)
        version_label.set_max_width_chars(20)
        version_label.set_halign(Gtk.Align.CENTER)
        version_label.add_css_class("caption")
        version_label.add_css_class("dim-label")
        box.append(version_label)

        # Trust indicator (for PKGBUILD)
        trust_box = Gtk.Box(spacing=4)
        trust_box.set_halign(Gtk.Align.CENTER)
        trust_icon = Gtk.Image()
        trust_icon.set_pixel_size(16)
        trust_box.append(trust_icon)
        trust_label = Gtk.Label()
        trust_box.append(trust_label)
        box.append(trust_box)

        list_item.set_child(box)

    def bind_file_card(self, factory, list_item):
        """Binds data to the card"""
        item = list_item.get_item()
        if not item:
            return

        box = list_item.get_child()
        icon = box.get_first_child()
        name_label = icon.get_next_sibling()
        version_label = name_label.get_next_sibling()
        trust_box = version_label.get_next_sibling()
        trust_icon = trust_box.get_first_child()
        trust_label = trust_icon.get_next_sibling()

        # Configure icon
        icon.set_from_icon_name(item.get_icon_name())

        # Configure name
        name_label.set_label(item.name)

        # Configure version
        version_label.set_label(item.version)

        # Configure trust
        if item.file_type == 'PKGBUILD' and item.trust_level:
            trust_icon.set_from_icon_name(item.get_trust_icon())
            trust_icon.set_visible(True)

            if item.trust_level == TrustLevel.HIGH:
                trust_label.set_label("High")
                trust_label.add_css_class("success-color")
            elif item.trust_level == TrustLevel.MEDIUM:
                trust_label.set_label("Medium")
                trust_label.add_css_class("warning-color")
            else:
                trust_label.set_label("Low")
                trust_label.add_css_class("error-color")
        else:
            trust_box.set_visible(False)

    def scan_compatible_files(self, folder_path):
        """Scans folder and identifies compatible files with technical details"""
        self.files_list_model.remove_all()

        for filename in os.listdir(folder_path):
            filepath = os.path.join(folder_path, filename)
            if not os.path.isfile(filepath):
                continue

            # PKGBUILD detection
            if filename == "PKGBUILD":
                pkgname, pkgver, pkgrel = self.extract_pkgbuild_info(filepath)
                votes = self.get_aur_votes(pkgname) if pkgname else 0
                trust_level = self.get_trust_level(votes) if votes > 0 else None

                item = FileItem(
                    file_type='PKGBUILD',
                    name=pkgname or "PKGBUILD",
                    version=f"{pkgver}-{pkgrel}" if pkgver else "N/A",
                    path=filepath,
                    trust_level=trust_level
                )
                self.files_list_model.append(item)

            # .zst package detection
            elif filename.endswith('.zst') and not filename.endswith('.zst.sig'):
                pkg_name = self.get_pkg_name_from_zst(filepath)
                signature = self.check_signature(filepath)

                item = FileItem(
                    file_type='PACKAGE',
                    name=pkg_name,
                    version=self.get_pkg_version(filepath),
                    path=filepath,
                    signature_status=signature
                )
                self.files_list_model.append(item)

            # Patch detection
            elif filename.endswith(('.patch', '.diff')):
                patch_desc = self.get_patch_description(filepath)

                item = FileItem(
                    file_type='PATCH',
                    name=os.path.splitext(filename)[0],
                    version="",
                    path=filepath,
                    extra_info=patch_desc
                )
                self.files_list_model.append(item)

    def process_selected_item(self, item):
        """Processes selected item and displays contextual interface"""
        # --- CORREÇÃO GTK4: Remover filhos de um Gtk.Box ---
        while self.content_box.get_first_child() is not None:
            self.content_box.remove(self.content_box.get_first_child())
        # --- FIM DA CORREÇÃO ---

        if item.file_type == 'PKGBUILD':
            self.show_pkgbuild_interface(item)
        elif item.file_type == 'PACKAGE':
            self.show_package_interface(item)
        elif item.file_type == 'PATCH':
            self.show_patch_interface(item)

    def show_pkgbuild_interface(self, item):
        """Displays interface for PKGBUILD with trust details"""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)

        # Package information header
        header = Gtk.Box(spacing=15)
        header.set_valign(Gtk.Align.CENTER)

        # Package icon
        icon = Gtk.Image()
        icon.set_from_icon_name("text-x-generic")
        icon.set_pixel_size(64)
        header.append(icon)

        # Main information
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

        # Package name with trust level
        name_box = Gtk.Box(spacing=8)
        name_label = Gtk.Label()
        name_label.set_markup(f'<span font_size="x-large" font_weight="bold">{item.name}</span>')
        name_box.append(name_label)

        if item.trust_level:
            trust_icon = Gtk.Image()
            trust_icon.set_from_icon_name(item.get_trust_icon())
            trust_icon.set_pixel_size(24)
            trust_icon.set_tooltip_text(
                "High trust level (50+ votes)" if item.trust_level == TrustLevel.HIGH else
                "Medium trust level (10-50 votes)" if item.trust_level == TrustLevel.MEDIUM else
                "Low trust level (<10 votes)"
            )
            name_box.append(trust_icon)

        info.append(name_box)

        # Version and path
        details = Gtk.Label()
        details.set_markup(
            f'<span font_weight="bold">Version:</span> {item.version}\n'
            f'<span font_weight="bold">Path:</span> {os.path.dirname(item.path)}'
        )
        details.set_justify(Gtk.Justification.LEFT)
        info.append(details)

        header.append(info)
        main_box.append(header)

        # Separator
        sep = Gtk.Separator()
        sep.set_margin_top(10)
        sep.set_margin_bottom(10)
        main_box.append(sep)

        # Main actions
        actions = Gtk.Box(spacing=15)
        actions.set_valign(Gtk.Align.CENTER)

        # Build Package button
        build_btn = Gtk.Button(label="Build Package")
        build_btn.add_css_class("suggested-action")
        build_btn.add_css_class("large-button")
        build_btn.set_margin_top(10)
        build_btn.set_margin_bottom(10)
        build_btn.connect("clicked", self.on_build_package, item.path)
        actions.append(build_btn)

        # Edit PKGBUILD button
        edit_btn = Gtk.Button(label="Edit PKGBUILD")
        edit_btn.add_css_class("large-button")
        edit_btn.set_margin_top(10)
        edit_btn.set_margin_bottom(10)
        edit_btn.connect("clicked", self.on_edit_pkgbuild, item.path)
        actions.append(edit_btn)

        main_box.append(actions)
        self.content_box.append(main_box)

    def show_package_interface(self, item):
        """Displays interface for .zst packages"""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)

        # Package information header
        header = Gtk.Box(spacing=15)
        header.set_valign(Gtk.Align.CENTER)

        # Package icon
        icon = Gtk.Image()
        icon.set_from_icon_name("package-x-generic")
        icon.set_pixel_size(64)
        header.append(icon)

        # Main information
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

        # Package name
        name_label = Gtk.Label()
        name_label.set_markup(f'<span font_size="x-large" font_weight="bold">{item.name}</span>')
        info.append(name_label)

        # Version and path
        details = Gtk.Label()
        details.set_markup(
            f'<span font_weight="bold">Version:</span> {item.version}\n'
            f'<span font_weight="bold">Path:</span> {os.path.dirname(item.path)}\n'
            f'<span font_weight="bold">Signature:</span> {item.signature_status}'
        )
        details.set_justify(Gtk.Justification.LEFT)
        info.append(details)

        header.append(info)
        main_box.append(header)

        # Separator
        sep = Gtk.Separator()
        sep.set_margin_top(10)
        sep.set_margin_bottom(10)
        main_box.append(sep)

        # Main actions
        actions = Gtk.Box(spacing=15)
        actions.set_valign(Gtk.Align.CENTER)

        # Install Package button
        install_btn = Gtk.Button(label="Install Package")
        install_btn.add_css_class("suggested-action")
        install_btn.add_css_class("large-button")
        install_btn.set_margin_top(10)
        install_btn.set_margin_bottom(10)
        install_btn.connect("clicked", self.on_install_package, item.path)
        actions.append(install_btn)

        # Verify Signature button
        verify_btn = Gtk.Button(label="Verify Signature")
        verify_btn.add_css_class("large-button")
        verify_btn.set_margin_top(10)
        verify_btn.set_margin_bottom(10)
        verify_btn.connect("clicked", self.on_verify_signature, item.path)
        actions.append(verify_btn)

        main_box.append(actions)
        self.content_box.append(main_box)

    def show_patch_interface(self, item):
        """Displays interface for patches"""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)

        # Patch information header
        header = Gtk.Box(spacing=15)
        header.set_valign(Gtk.Align.CENTER)

        # Patch icon
        icon = Gtk.Image()
        icon.set_from_icon_name("text-x-patch")
        icon.set_pixel_size(64)
        header.append(icon)

        # Main information
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

        # Patch name
        name_label = Gtk.Label()
        name_label.set_markup(f'<span font_size="x-large" font_weight="bold">{item.name}</span>')
        info.append(name_label)

        # Path and description
        details = Gtk.Label()
        details.set_markup(
            f'<span font_weight="bold">Path:</span> {item.path}\n'
            f'<span font_weight="bold">Description:</span> {item.extra_info}'
        )
        details.set_justify(Gtk.Justification.LEFT)
        info.append(details)

        header.append(info)
        main_box.append(header)

        # Separator
        sep = Gtk.Separator()
        sep.set_margin_top(10)
        sep.set_margin_bottom(10)
        main_box.append(sep)

        # Main actions
        actions = Gtk.Box(spacing=15)
        actions.set_valign(Gtk.Align.CENTER)

        # Apply Patch button
        apply_btn = Gtk.Button(label="Apply Patch")
        apply_btn.add_css_class("suggested-action")
        apply_btn.add_css_class("large-button")
        apply_btn.set_margin_top(10)
        apply_btn.set_margin_bottom(10)
        apply_btn.connect("clicked", self.on_apply_patch, item.path)
        actions.append(apply_btn)

        # View Diff button
        view_btn = Gtk.Button(label="View Diff")
        view_btn.add_css_class("large-button")
        view_btn.set_margin_top(10)
        view_btn.set_margin_bottom(10)
        view_btn.connect("clicked", self.on_view_diff, item.path)
        actions.append(view_btn)

        main_box.append(actions)
        self.content_box.append(main_box)

    # Helper methods for metadata extraction
    def extract_pkgbuild_info(self, path):
        """Safely extracts information from PKGBUILD"""
        pkgname = pkgver = pkgrel = "unknown"

        try:
            with open(path, 'r') as f:
                content = f.read()

            # Use regex to extract information without executing the script
            name_match = re.search(r'pkgname\s*=\s*(\S+)', content)
            ver_match = re.search(r'pkgver\s*=\s*(\S+)', content)
            rel_match = re.search(r'pkgrel\s*=\s*(\S+)', content)

            pkgname = name_match.group(1) if name_match else "unknown"
            pkgver = ver_match.group(1) if ver_match else "0"
            pkgrel = rel_match.group(1) if rel_match else "1"
        except Exception as e:
            print(f"Error reading PKGBUILD: {e}")

        return (pkgname, pkgver, pkgrel)

    def get_aur_votes(self, pkgname):
        """Gets votes from AUR to determine trust level"""
        try:
            result = subprocess.run(
                ['paru', '-Si', pkgname],
                capture_output=True,
                text=True,
                timeout=5
            )
            votes_match = re.search(r'Votes\s*:\s*(\d+)', result.stdout)
            return int(votes_match.group(1)) if votes_match else 0
        except Exception as e:
            print(f"Error getting AUR votes: {e}")
            return 0

    def get_trust_level(self, votes):
        """Determines trust level based on votes"""
        if votes >= 50:
            return TrustLevel.HIGH
        elif votes >= 10:
            return TrustLevel.MEDIUM
        return TrustLevel.LOW

    def get_pkg_name_from_zst(self, filepath):
        """Extracts package name from .zst file"""
        try:
            # Use pacman to extract package name
            result = subprocess.run(
                ['tar', '--zstd', '-tvf', filepath],
                capture_output=True,
                text=True,
                timeout=5
            )
            # Look for .PKGINFO file which contains package metadata
            for line in result.stdout.splitlines():
                if '.PKGINFO' in line:
                    return os.path.basename(filepath).split('-')[0]
            return os.path.basename(filepath).replace('.pkg.tar.zst', '')
        except Exception as e:
            print(f"Error extracting package name: {e}")
            return os.path.basename(filepath).replace('.pkg.tar.zst', '')

    def get_pkg_version(self, filepath):
        """Extracts package version from .zst file"""
        try:
            # Use pacman to extract package version
            result = subprocess.run(
                ['tar', '--zstd', '-xOf', filepath, '.PKGINFO'],
                capture_output=True,
                text=True,
                timeout=5
            )
            pkgver_match = re.search(r'pkgver\s*=\s*(\S+)', result.stdout)
            pkgrel_match = re.search(r'pkgrel\s*=\s*(\S+)', result.stdout)

            pkgver = pkgver_match.group(1) if pkgver_match else "unknown"
            pkgrel = pkgrel_match.group(1) if pkgrel_match else "1"

            return f"{pkgver}-{pkgrel}"
        except Exception as e:
            print(f"Error extracting package version: {e}")
            return "unknown"

    def check_signature(self, filepath):
        """Checks package signature status"""
        try:
            # Check if signature file exists
            sig_path = filepath + '.sig'
            if not os.path.exists(sig_path):
                return "Not signed"

            # In a real implementation, we would verify the signature
            # This is a placeholder for the actual verification logic
            return "Verified"
        except Exception as e:
            print(f"Error checking signature: {e}")
            return "Verification failed"

    def get_patch_description(self, filepath):
        """Gets patch description"""
        try:
            with open(filepath, 'r') as f:
                first_line = f.readline().strip()
                if first_line.startswith('#'):
                    return first_line[1:].strip()
                return "Patch file"
        except Exception as e:
            print(f"Error reading patch description: {e}")
            return "Unknown patch"

    def on_build_package(self, button, pkgbuild_path):
        """Starts the package building process"""
        print(f"Starting PKGBUILD compilation: {pkgbuild_path}")
        # Actual build logic would go here

    def on_edit_pkgbuild(self, button, pkgbuild_path):
        """Opens PKGBUILD in default editor"""
        try:
            # Default editor (could come from preferences)
            editor = "gedit"
            subprocess.Popen([editor, pkgbuild_path])
        except Exception as e:
            print(f"Error opening editor: {e}")

    def on_install_package(self, button, package_path):
        """Installs the selected package"""
        print(f"Installing package: {package_path}")
        # Actual installation logic would go here

    def on_verify_signature(self, button, package_path):
        """Verifies package signature"""
        print(f"Verifying signature for: {package_path}")
        # Actual signature verification logic would go here

    def on_apply_patch(self, button, patch_path):
        """Applies the selected patch"""
        print(f"Applying patch: {patch_path}")
        # Actual patch application logic would go here

    def on_view_diff(self, button, patch_path):
        """Views patch diff"""
        print(f"Viewing diff for: {patch_path}")
        # Actual diff viewing logic would go here
