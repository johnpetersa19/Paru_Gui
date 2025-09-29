from gi.repository import Gtk, GObject, Adw, Pango
from typing import Optional, List, Dict, Any, Tuple

@Gtk.Template(resource_path="/org/gnome/paru-gui/ui/screens/pkgbuild_review.ui")
class PkgbuildReviewDialog(Adw.Dialog):
    __gtype_name__ = "PkgbuildReviewDialog"

    package_icon: Gtk.Image = Gtk.Template.Child()
    package_name: Gtk.Label = Gtk.Template.Child()
    package_details: Gtk.Label = Gtk.Template.Child()

    step_switcher: Adw.ViewSwitcher = Gtk.Template.Child()
    review_view_stack: Adw.ViewStack = Gtk.Template.Child()

    source_diff_view: Gtk.TextView = Gtk.Template.Child()

    risk_sudo_row: Adw.SwitchRow = Gtk.Template.Child()
    risk_unverified_sources_row: Adw.SwitchRow = Gtk.Template.Child()
    heatmap_view: Gtk.TextView = Gtk.Template.Child()

    sandbox_expander_row: Adw.ExpanderRow = Gtk.Template.Child()
    sandbox_level_combo: Gtk.DropDown = Gtk.Template.Child()

    cancel_button: Gtk.Button = Gtk.Template.Child()
    previous_button: Gtk.Button = Gtk.Template.Child()
    next_button: Gtk.Button = Gtk.Template.Child()
    build_button: Gtk.Button = Gtk.Template.Child()

    __gsignals__ = {
        'build-requested': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'cancel-requested': (GObject.SignalFlags.RUN_LAST, None, ()),
        'step-changed': (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.current_package_data = {}
        self.current_risks = []
        self.security_analysis = {}

        if self.heatmap_view:
            self.heatmap_text_buffer = self.heatmap_view.get_buffer()
            self._setup_heatmap_tags()

        if self.source_diff_view:
            self.source_diff_buffer = self.source_diff_view.get_buffer()

        self._setup_initial_state()

    def _setup_initial_state(self):
        self.review_view_stack.set_visible_child_name("step1")
        self._update_button_visibility()
        self.review_view_stack.connect("notify::visible-child-name", self._on_view_changed)

    def _setup_heatmap_tags(self):
        if not hasattr(self, 'heatmap_text_buffer'):
            return

        tag_table = self.heatmap_text_buffer.get_tag_table()

        risk_tags = {
            'risk-critical': {'background': '#e01b24', 'foreground': 'white'},
            'risk-high': {'background': '#f57c00', 'foreground': 'white'},
            'risk-medium': {'background': '#f9c23c', 'foreground': 'black'},
            'risk-low': {'background': '#8ff0a4', 'foreground': 'black'},
            'risk-none': {'background': '#ffffff', 'foreground': 'black'}
        }

        for tag_name, properties in risk_tags.items():
            if not tag_table.lookup(tag_name):
                self.heatmap_text_buffer.create_tag(tag_name, **properties)

    def _update_button_visibility(self):
        current_page = self.review_view_stack.get_visible_child_name()

        visibility_map = {
            "step1": {"previous": False, "next": True, "build": False},
            "step2": {"previous": True, "next": True, "build": False},
            "step3": {"previous": True, "next": False, "build": True}
        }

        if current_page in visibility_map:
            vis = visibility_map[current_page]
            self.previous_button.set_visible(vis["previous"])
            self.next_button.set_visible(vis["next"])
            self.build_button.set_visible(vis["build"])

    def _on_view_changed(self, stack, param):
        self._update_button_visibility()
        current_step = self.get_current_step()
        self.emit('step-changed', current_step)

    @Gtk.Template.Callback()
    def on_cancel_clicked(self, button):
        self.emit('cancel-requested')
        self.close()

    @Gtk.Template.Callback()
    def on_previous_clicked(self, button):
        current_page = self.review_view_stack.get_visible_child_name()

        navigation_map = {
            "step2": "step1",
            "step3": "step2"
        }

        if current_page in navigation_map:
            self.review_view_stack.set_visible_child_name(navigation_map[current_page])

    @Gtk.Template.Callback()
    def on_next_clicked(self, button):
        current_page = self.review_view_stack.get_visible_child_name()

        navigation_map = {
            "step1": "step2",
            "step2": "step3"
        }

        if current_page in navigation_map:
            self.review_view_stack.set_visible_child_name(navigation_map[current_page])

    @Gtk.Template.Callback()
    def on_build_clicked(self, button):
        build_settings = self._gather_build_settings()
        self.emit('build-requested', build_settings)
        self.close()

    def _gather_build_settings(self) -> Dict[str, Any]:
        return {
            'package_data': self.current_package_data,
            'sandbox_enabled': self.sandbox_expander_row.get_enable_expansion(),
            'sandbox_level': self.sandbox_level_combo.get_selected(),
            'acknowledged_risks': {
                'sudo_commands': self.risk_sudo_row.get_active(),
                'unverified_sources': self.risk_unverified_sources_row.get_active(),
            },
            'security_analysis': self.security_analysis,
            'build_environment': self._get_build_environment_settings()
        }

    def _get_build_environment_settings(self) -> Dict[str, Any]:
        sandbox_levels = ["strict", "medium", "minimal"]
        selected_level = self.sandbox_level_combo.get_selected()

        return {
            'isolation_level': sandbox_levels[selected_level] if 0 <= selected_level < len(sandbox_levels) else "medium",
            'network_access': False,
            'filesystem_access': "restricted",
            'environment_variables': {}
        }

    def populate_package_info(self, package_data: Dict[str, Any]):
        self.current_package_data = package_data.copy()

        if self.package_name:
            self.package_name.set_text(package_data.get('name', 'Unknown Package'))

        if self.package_details:
            version = package_data.get('version', 'Unknown')
            votes = package_data.get('votes', 0)
            source = package_data.get('source', 'Unknown')
            details_text = f"Version: {version} | Votes: {votes} | Source: {source}"
            self.package_details.set_text(details_text)

        if self.package_icon:
            icon_name = package_data.get('icon', 'text-x-generic-symbolic')
            self.package_icon.set_from_icon_name(icon_name)

    def populate_diff_analysis(self, diff_data: Dict[str, str]):
        if self.source_diff_buffer and 'source_diff' in diff_data:
            self.source_diff_buffer.set_text(diff_data['source_diff'])

    def populate_risk_checklist(self, risks: List[Dict[str, Any]]):
        self.current_risks = risks.copy()

        risk_handlers = {
            'sudo_commands': (self.risk_sudo_row, "Contains sudo commands"),
            'unverified_sources': (self.risk_unverified_sources_row, "Contains unverified sources")
        }

        for risk in risks:
            risk_type = risk.get('type')
            detected = risk.get('detected', False)

            if risk_type in risk_handlers:
                row, default_desc = risk_handlers[risk_type]
                row.set_active(detected)
                if detected:
                    description = risk.get('description', default_desc)
                    row.set_subtitle(description)

    def populate_heatmap(self, heatmap_data: str, risk_ranges: List[Tuple[int, int, str]]):
        if not self.heatmap_text_buffer:
            return

        self.heatmap_text_buffer.set_text(heatmap_data)

        for start_line, end_line, risk_level in risk_ranges:
            if start_line < 0 or end_line < start_line:
                continue

            start_iter = self.heatmap_text_buffer.get_iter_at_line(start_line)
            end_iter = self.heatmap_text_buffer.get_iter_at_line(end_line)

            tag_name = f'risk-{risk_level.lower()}'
            if self.heatmap_text_buffer.get_tag_table().lookup(tag_name):
                self.heatmap_text_buffer.apply_tag_by_name(tag_name, start_iter, end_iter)

    def populate_security_analysis(self, analysis: Dict[str, Any]):
        self.security_analysis = analysis.copy()

        risk_score = analysis.get('risk_score', 0)
        threats = analysis.get('threats', [])
        recommendations = analysis.get('recommendations', [])

        self._update_risk_indicators(risk_score, threats)
        self._apply_security_recommendations(recommendations)

    def _update_risk_indicators(self, risk_score: int, threats: List[Dict[str, Any]]):
        threat_types = [threat.get('type') for threat in threats]

        self.risk_sudo_row.set_active('sudo_usage' in threat_types)
        self.risk_unverified_sources_row.set_active('unverified_sources' in threat_types)

    def _apply_security_recommendations(self, recommendations: List[Dict[str, Any]]):
        for recommendation in recommendations:
            rec_type = recommendation.get('type')
            enabled = recommendation.get('enabled', False)

            if rec_type == 'enable_sandbox':
                self.sandbox_expander_row.set_enable_expansion(enabled)
            elif rec_type == 'strict_isolation':
                self.sandbox_level_combo.set_selected(0)
            elif rec_type == 'medium_isolation':
                self.sandbox_level_combo.set_selected(1)

    def set_sandbox_settings(self, enabled: bool, level: int = 1):
        self.sandbox_expander_row.set_enable_expansion(enabled)
        if 0 <= level < 3:
            self.sandbox_level_combo.set_selected(level)

    def get_current_step(self) -> str:
        return self.review_view_stack.get_visible_child_name()

    def set_current_step(self, step_name: str):
        valid_steps = ["step1", "step2", "step3"]
        if step_name in valid_steps:
            self.review_view_stack.set_visible_child_name(step_name)

    def get_risk_assessment(self) -> Dict[str, Any]:
        return {
            'acknowledged_risks': {
                'sudo_commands': self.risk_sudo_row.get_active(),
                'unverified_sources': self.risk_unverified_sources_row.get_active(),
            },
            'security_analysis': self.security_analysis,
            'risk_level': self._calculate_overall_risk_level()
        }

    def _calculate_overall_risk_level(self) -> str:
        risk_factors = []

        if self.risk_sudo_row.get_active():
            risk_factors.append('high')
        if self.risk_unverified_sources_row.get_active():
            risk_factors.append('medium')

        if 'high' in risk_factors:
            return 'high'
        elif 'medium' in risk_factors:
            return 'medium'
        elif risk_factors:
            return 'low'
        else:
            return 'minimal'

    def reset_dialog(self):
        self.current_package_data = {}
        self.current_risks = []
        self.security_analysis = {}

        self.set_current_step("step1")

        if self.heatmap_text_buffer:
            self.heatmap_text_buffer.set_text("")
        if self.source_diff_buffer:
            self.source_diff_buffer.set_text("")

        self.risk_sudo_row.set_active(False)
        self.risk_unverified_sources_row.set_active(False)

        self.set_sandbox_settings(False, 1)

    def validate_review_completion(self) -> bool:
        current_step = self.get_current_step()

        if current_step != "step3":
            return False

        if not self.current_package_data:
            return False

        return True

    def get_build_configuration(self) -> Dict[str, Any]:
        if not self.validate_review_completion():
            return {}

        return self._gather_build_settings()
