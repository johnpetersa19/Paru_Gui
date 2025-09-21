from gi.repository import Gtk, GObject, Adw, Pango
from typing import Optional, List, Dict, Any, Tuple

# SOLUÇÃO ALTERNATIVA: Não usar @Gtk.Template, carregar manualmente
class PkgbuildReviewDialog(Adw.Dialog):
    __gtype_name__ = "PkgbuildReviewDialog"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Configurar propriedades do diálogo
        self.set_title("PKGBUILD Security Review")
        self.set_default_size(700, 750)
        self.set_modal(True)

        # Carregar UI manualmente
        self._load_ui()

        # Conectar sinais
        self._connect_signals()

        # Configurar heatmap
        if hasattr(self, 'heatmap_view'):
            self.heatmap_text_buffer = self.heatmap_view.get_buffer()
            self._setup_heatmap_tags()

        print("PkgbuildReviewDialog initialized.")

    def _load_ui(self):
        """Carrega o arquivo UI manualmente"""
        try:
            # Tentar carregar do recurso primeiro
            builder = Gtk.Builder()
            builder.add_from_resource("/org/gnome/paru-gui/ui/screens/pkgbuild_review.ui")
            print("✅ UI carregada do recurso")

        except Exception as e:
            print(f"❌ Erro ao carregar do recurso: {e}")
            try:
                # Fallback: carregar do arquivo local
                import os
                ui_file = os.path.join(os.path.dirname(__file__), 'pkgbuild_review.ui')
                builder = Gtk.Builder()
                builder.add_from_file(ui_file)
                print(f"✅ UI carregada do arquivo: {ui_file}")

            except Exception as e2:
                print(f"❌ Erro ao carregar do arquivo: {e2}")
                # Criar UI programaticamente como último recurso
                self._create_ui_programmatically()
                return

        # Obter o conteúdo principal e definir como child
        main_content = builder.get_object('main_box')
        if main_content:
            self.set_child(main_content)

            # Conectar referências aos elementos
            self._connect_ui_elements(builder)
        else:
            print("❌ Não foi possível encontrar 'main_box' no UI")
            self._create_ui_programmatically()

    def _connect_ui_elements(self, builder):
        """Conecta referências aos elementos UI"""
        # Package Info Box
        self.package_icon = builder.get_object('package_icon')
        self.package_name = builder.get_object('package_name')
        self.package_trust_label = builder.get_object('package_trust_label')
        self.version_label = builder.get_object('version_label')
        self.source_label = builder.get_object('source_label')
        self.votes_label = builder.get_object('votes_label')
        self.package_path = builder.get_object('package_path')

        # Steps Navigation
        self.step1_button = builder.get_object('step1_button')
        self.step2_button = builder.get_object('step2_button')

        # Step 1 Content: Critical Changes
        self.step1_content = builder.get_object('step1_content')
        self.source_diff_view = builder.get_object('source_diff_view')
        self.prepare_diff_view = builder.get_object('prepare_diff_view')
        self.package_diff_view = builder.get_object('package_diff_view')

        # Step 2 Content: Risk Checklist & Heatmap
        self.step2_content = builder.get_object('step2_content')
        self.risk_checklist_box = builder.get_object('risk_checklist_box')
        self.risk_summary_text = builder.get_object('risk_summary_text')
        self.heatmap_view = builder.get_object('heatmap_view')

        # Sandboxing Options
        self.sandbox_expander = builder.get_object('sandbox_expander')
        self.enable_sandbox_check = builder.get_object('enable_sandbox_check')
        self.sandbox_options_box = builder.get_object('sandbox_options_box')
        self.sandbox_level_combo = builder.get_object('sandbox_level_combo')
        self.sandbox_network_check = builder.get_object('sandbox_network_check')
        self.sandbox_home_check = builder.get_object('sandbox_home_check')

        # Action Area Buttons
        self.cancel_button = builder.get_object('cancel_button')
        self.previous_button = builder.get_object('previous_button')
        self.next_button = builder.get_object('next_button')
        self.build_button = builder.get_object('build_button')

    def _create_ui_programmatically(self):
        """Cria UI programaticamente como último recurso"""
        print("🔧 Criando UI programaticamente...")

        # Criar container principal
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(12)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)

        # Criar elementos básicos
        self.package_name = Gtk.Label(label="Package Name")
        self.package_name.add_css_class("title-2")
        main_box.append(self.package_name)

        # Placeholder para outros elementos
        placeholder = Gtk.Label(label="UI sendo carregada programaticamente...")
        placeholder.add_css_class("dim-label")
        main_box.append(placeholder)

        # Botões de ação
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)

        self.cancel_button = Gtk.Button(label="Cancelar")
        self.build_button = Gtk.Button(label="Build")
        self.build_button.add_css_class("suggested-action")

        button_box.append(self.cancel_button)
        button_box.append(self.build_button)
        main_box.append(button_box)

        # Definir como conteúdo do diálogo
        self.set_child(main_box)

        print("✅ UI básica criada programaticamente")

    def _connect_signals(self):
        """Conecta sinais dos elementos"""
        if hasattr(self, 'step1_button') and self.step1_button:
            self.step1_button.connect("toggled", self._on_step_toggled)
        if hasattr(self, 'step2_button') and self.step2_button:
            self.step2_button.connect("toggled", self._on_step_toggled)
        if hasattr(self, 'cancel_button') and self.cancel_button:
            self.cancel_button.connect("clicked", lambda *args: self.close())
        if hasattr(self, 'previous_button') and self.previous_button:
            self.previous_button.connect("clicked", self._on_previous_clicked)
        if hasattr(self, 'next_button') and self.next_button:
            self.next_button.connect("clicked", self._on_next_clicked)

    def _setup_heatmap_tags(self):
        """Sets up Gtk.TextTag objects for heatmap highlighting."""
        if not hasattr(self, 'heatmap_text_buffer'):
            return

        tag_table = self.heatmap_text_buffer.get_tag_table()

        # The CSS file (pkgbuild-review.css) defines colors for these classes
        # We apply them as tags here.
        if not tag_table.lookup('risk-critical'):
            self.heatmap_text_buffer.create_tag('risk-critical', background_set=True)
        if not tag_table.lookup('risk-high'):
            self.heatmap_text_buffer.create_tag('risk-high', background_set=True)
        if not tag_table.lookup('risk-medium'):
            self.heatmap_text_buffer.create_tag('risk-medium', background_set=True)
        if not tag_table.lookup('risk-low'):
            self.heatmap_text_buffer.create_tag('risk-low', background_set=True)
        if not tag_table.lookup('risk-none'):
            self.heatmap_text_buffer.create_tag('risk-none', background_set=True)

    def _on_step_toggled(self, button):
        """Handle step button toggle"""
        if not button.get_active():
            return

        if hasattr(self, 'step1_content') and hasattr(self, 'step2_content'):
            if button == getattr(self, 'step1_button', None):
                self.step1_content.set_visible(True)
                self.step2_content.set_visible(False)
            elif button == getattr(self, 'step2_button', None):
                self.step1_content.set_visible(False)
                self.step2_content.set_visible(True)

    def _on_previous_clicked(self, button):
        """Handle previous button click"""
        if hasattr(self, 'step1_button'):
            self.step1_button.set_active(True)

    def _on_next_clicked(self, button):
        """Handle next button click"""
        if hasattr(self, 'step2_button'):
            self.step2_button.set_active(True)

    # Métodos existentes da classe original...
    def populate_package_info(self, package_data: Dict[str, Any]):
        """Populates the package information section."""
        if hasattr(self, 'package_name') and self.package_name:
            self.package_name.set_text(package_data.get('name', 'Unknown'))
        # ... resto da implementação

    def populate_diff_analysis(self, diff_data: Dict[str, str]):
        """Populates the diff analysis views."""
        # ... implementação
        pass

    def populate_risk_checklist(self, risks: List[Dict[str, Any]]):
        """Populates the risk checklist."""
        # ... implementação
        pass

    def populate_heatmap(self, heatmap_data: str, risk_ranges: List[Tuple[int, int, str]]):
        """Populates the heatmap view with syntax highlighting."""
        # ... implementação
        pass
