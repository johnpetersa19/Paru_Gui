from gi.repository import Gtk, GObject, Adw, Pango
from typing import Optional, List, Dict, Any, Tuple

# The .ui file specifies <template class="PkgbuildReviewDialog" parent="AdwDialog">
@Gtk.Template(resource_path="/org/gnome/paru-gui/ui/screens/pkgbuild_review.ui")
class PkgbuildReviewDialog(Adw.Dialog):
    __gtype_name__ = "PkgbuildReviewDialog"

    # --- UI Elements from pkgbuild_review.ui ---
    # Package Info Box
    package_icon = Gtk.Template.Child()
    package_name = Gtk.Template.Child()
    package_trust_label = Gtk.Template.Child()
    version_label = Gtk.Template.Child()
    source_label = Gtk.Template.Child()
    votes_label = Gtk.Template.Child()
    package_path = Gtk.Template.Child()

    # Steps Navigation
    step1_button = Gtk.Template.Child()
    step2_button = Gtk.Template.Child()

    # Step 1 Content: Critical Changes
    step1_content = Gtk.Template.Child()
    source_diff_view = Gtk.Template.Child()
    prepare_diff_view = Gtk.Template.Child()
    package_diff_view = Gtk.Template.Child()

    # Step 2 Content: Risk Checklist & Heatmap
    step2_content = Gtk.Template.Child()
    risk_checklist_box = Gtk.Template.Child() # Container for dynamic risk items
    risk_summary_text = Gtk.Template.Child()
    heatmap_view = Gtk.Template.Child() # GtkTextView for the heatmap

    # Sandboxing Options
    sandbox_expander = Gtk.Template.Child()
    enable_sandbox_check = Gtk.Template.Child()
    sandbox_options_box = Gtk.Template.Child()
    sandbox_level_combo = Gtk.Template.Child()
    sandbox_network_check = Gtk.Template.Child()
    sandbox_home_check = Gtk.Template.Child()

    # Action Area Buttons
    cancel_button = Gtk.Template.Child()
    previous_button = Gtk.Template.Child()
    next_button = Gtk.Template.Child()
    build_button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Adw.Dialog automatically creates a headerbar
        self.set_title("PKGBUILD Security Review") # As defined in UI template
        self.set_default_size(700, 750)
        self.set_modal(True)

        # Connect signals defined in the UI template
        self.step1_button.connect("toggled", self._on_step_toggled)
        self.step2_button.connect("toggled", self._on_step_toggled)
        self.cancel_button.connect("clicked", self.close) # Default close behavior
        self.previous_button.connect("clicked", self._on_previous_clicked)
        self.next_button.connect("clicked", self._on_next_clicked)
        # build_button will be connected by window.py once analysis is complete
        # enable_sandbox_check will be connected by window.py

        self.heatmap_text_buffer = self.heatmap_view.get_buffer()
        self._setup_heatmap_tags()

        print("PkgbuildReviewDialog initialized.")

    def _setup_heatmap_tags(self):
        """Sets up Gtk.TextTag objects for heatmap highlighting."""
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

        # Apply CSS classes to tags so themes can style them
        for level in ["critical", "high", "medium", "low"]:
            tag = tag_table.lookup(f'risk-{level}')
            if tag:
                tag.add_css_class(f'risk-{level}')
        print("Heatmap text tags set up.")

    def update_package_info(self, name: str, version: str, path: str,
                            trust_level_str: str, votes: int = 0, last_update: str = "N/A"):
        """Populates the package information section."""
        self.package_name.set_label(name)
        self.version_label.set_label(f"Version: {version}")
        self.package_path.set_label(f"Path: {path}")
        self.package_trust_label.set_label(f"Trust: {trust_level_str}")
        self.votes_label.set_label(f"Votes: {votes}")
        # self.source_label.set_label(f"Source: AUR") # Already static in UI

        # Update styling for trust label
        self.package_trust_label.get_style_context().remove_class("success-color")
        self.package_trust_label.get_style_context().remove_class("warning-color")
        self.package_trust_label.get_style_context().remove_class("error-color")
        if "HIGH" in trust_level_str or "NONE" in trust_level_str:
            self.package_trust_label.get_style_context().add_class("success-color")
        elif "MEDIUM" in trust_level_str:
            self.package_trust_label.get_style_context().add_class("warning-color")
        else:
            self.package_trust_label.get_style_context().add_class("error-color")

        # Update detailed trust info in the UI (if available from analysis results)
        pkgbuild_votes_label = self.builder.get_object('pkgbuild_votes_label')
        pkgbuild_update_time_label = self.builder.get_object('pkgbuild_update_time_label')
        pkgbuild_pgp_status_label = self.builder.get_object('pkgbuild_pgp_status_label')
        if pkgbuild_votes_label: pkgbuild_votes_label.set_label(f"Votes: {votes}")
        if pkgbuild_update_time_label: pkgbuild_update_time_label.set_label(f"Last Update: {last_update}")
        # PGP status will come from security_analyzer


    def update_critical_changes_view(self, source_content: str, prepare_content: str, package_content: str):
        """Updates the TextViews in Step 1 with content from critical sections."""
        self.source_diff_view.get_buffer().set_text(source_content)
        self.prepare_diff_view.get_buffer().set_text(prepare_content)
        self.package_diff_view.get_buffer().set_text(package_content)

    def update_risk_checklist(self, risks: List[Dict[str, Any]], overall_risk_summary: str):
        """Populates the risk checklist in Step 2."""
        # Clear existing list items first
        while self.risk_checklist_box.get_first_child() is not None:
            self.risk_checklist_box.remove(self.risk_checklist_box.get_first_child())

        if not risks:
            label = Gtk.Label(label="No specific security risks detected.")
            label.set_halign(Gtk.Align.START)
            self.risk_checklist_box.append(label)
            return

        for risk_item in risks:
            # Create dynamic UI for each risk. Could be GtkCheckButton or just GtkLabel
            # For brevity, a simple label based on the format in error_dialog.py
            label_text = f"• {risk_item.get('description', 'Unknown risk')}"
            if risk_item.get('line_number'):
                label_text += f" (Line: {risk_item['line_number']})"
            if risk_item.get('snippet'):
                label_text += f" -> '{risk_item['snippet']}'"

            label = Gtk.Label(label=label_text)
            label.set_halign(Gtk.Align.START)
            label.set_wrap(True)
            label.set_xalign(0)

            # Apply color classes based on risk level
            risk_level = risk_item.get('level')
            if risk_level == "Critical": label.get_style_context().add_class('error-color')
            elif risk_level == "High": label.get_style_context().add_class('warning-color')
            # Add GtkCheckButton if user interaction (acknowledgement) is desired
            self.risk_checklist_box.append(label)

        self.risk_summary_text.set_label(overall_risk_summary)
        # Adjust risk_summary_icon and its class based on severity of overall_risk_summary

    def update_heatmap_view(self, pkgbuild_content: str, heatmap_annotations: List[Tuple[int, Any, str]]):
        """
        Populates the heatmap TextView with PKGBUILD content and applies highlighting tags.

        Args:
            pkgbuild_content: The full raw content of the PKGBUILD.
            heatmap_annotations: A list of (line_number, RiskLevel_enum, description_str) tuples.
        """
        self.heatmap_text_buffer.set_text(pkgbuild_content)

        for line_num, risk_level, _description in heatmap_annotations:
            # GtkTextBuffer is 0-indexed for lines
            start_iter = self.heatmap_text_buffer.get_iter_at_line(line_num - 1)
            # End iterator points to the start of the next line, or end of buffer if last line
            end_iter = self.heatmap_text_buffer.get_iter_at_line(line_num) # This gets iter at start of line_num+1

            tag_name = f"risk-{risk_level.value.lower()}"
            self.heatmap_text_buffer.apply_tag_by_name(tag_name, start_iter, end_iter)

        # Ensure the heatmap view is scrolled to the top initially
        self.heatmap_view.scroll_to_iter(self.heatmap_text_buffer.get_start_iter(), 0.0, False, 0.0, 0.0)


    def _on_step_toggled(self, toggle_button: Gtk.ToggleButton):
        """Handler for toggling between review steps."""
        self.step1_button.remove_css_class('active-step')
        self.step2_button.remove_css_class('active-step')

        if toggle_button.get_name() == 'step1' and toggle_button.get_active():
            self.step2_button.set_active(False)
            self.step1_content.set_visible(True)
            self.step2_content.set_visible(False)
            self.previous_button.set_visible(False)
            self.next_button.set_visible(True)
            self.build_button.set_visible(False)
            self.step1_button.add_css_class('active-step')
        elif toggle_button.get_name() == 'step2' and toggle_button.get_active():
            self.step1_button.set_active(False)
            self.step1_content.set_visible(False)
            self.step2_content.set_visible(True)
            self.previous_button.set_visible(True)
            self.next_button.set_visible(False)
            self.build_button.set_visible(True)
            self.step2_button.add_css_class('active-step')

    def _on_next_clicked(self, button: Gtk.Button):
        """Advances to the next step (Step 2)."""
        if self.step1_button.get_active():
            self.step2_button.set_active(True)

    def _on_previous_clicked(self, button: Gtk.Button):
        """Goes back to the previous step (Step 1)."""
        if self.step2_button.get_active():
            self.step1_button.set_active(True)

    def _on_sandbox_toggled(self, checkbutton: Gtk.CheckButton):
        """Handler for toggling the sandboxing options expander."""
        self.sandbox_options_box.set_visible(checkbutton.get_active())

    # The build_button's 'clicked' signal should be connected by window.py
    # to on_build_package_sandboxed or on_build_package based on context.
