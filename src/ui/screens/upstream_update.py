# src/ui/screens/upstream_update.py

from gi.repository import Gtk, GObject, Adw

@Gtk.Template(resource_path="/org/gnome/paru-gui/ui/screens/upstream_update.ui")
class UpstreamUpdateCard(Gtk.Frame):
    __gtype_name__ = "UpstreamUpdateCard"

    # Define widgets from the UI file
    package_name_label = Gtk.Template.Child()
    aur_version_label = Gtk.Template.Child()
    upstream_version_label = Gtk.Template.Child()
    source_url_label = Gtk.Template.Child()
    release_info_label = Gtk.Template.Child()
    cve_fix_label = Gtk.Template.Child()
    update_button = Gtk.Template.Child()
    view_changelog_button = Gtk.Template.Child()
    ignore_version_button = Gtk.Template.Child()

    # Sandboxing widgets
    sandbox_expander = Gtk.Template.Child()
    enable_sandbox_check = Gtk.Template.Child()
    sandbox_options_box = Gtk.Template.Child()
    sandbox_level_combo = Gtk.Template.Child()
    sandbox_network_check = Gtk.Template.Child()
    sandbox_home_check = Gtk.Template.Child()
    confirm_sandbox_update = Gtk.Template.Child()


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initial setup or data binding can happen here
        print("UpstreamUpdateCard initialized.")
        self.connect_signals()

    def connect_signals(self):
        # Connect signals for buttons and checks
        self.update_button.connect("clicked", self.on_update_clicked)
        self.view_changelog_button.connect("clicked", self.on_view_changelog_clicked)
        self.ignore_version_button.connect("clicked", self.on_ignore_version_clicked)
        self.enable_sandbox_check.connect("toggled", self.on_enable_sandbox_toggled)
        self.confirm_sandbox_update.connect("clicked", self.on_confirm_sandbox_update_clicked)

        # Set initial visibility of sandbox options
        self.sandbox_options_box.set_visible(self.enable_sandbox_check.get_active())

    def update_card_data(self, package_name: str, aur_version: str, upstream_info: dict):
        """
        Updates the UI elements of the card with provided package and upstream data.
        """
        self.package_name_label.set_label(package_name)
        self.aur_version_label.set_label(f"AUR: {aur_version}")
        self.upstream_version_label.set_label(f"Upstream: {upstream_info.get('version', 'N/A')}")
        self.source_url_label.set_label(f"Source: {upstream_info.get('changelog_url', upstream_info.get('url', 'N/A'))}")
        self.release_info_label.set_label(f"Released: {upstream_info.get('release_date', 'N/A')}")
        self.cve_fix_label.set_label(f"CVE Fix: {upstream_info.get('cve_fix_info', 'N/A')}")

        # Adjust visibility/styling based on data (e.g., if CVEs are present)
        if upstream_info.get('cve_fix_info'):
            self.cve_fix_label.add_css_class("error-color")
        else:
            self.cve_fix_label.remove_css_class("error-color")


    def on_update_clicked(self, button):
        print(f"Update button clicked for {self.package_name_label.get_label()}")
        # Logic to initiate the update process without sandboxing
        pass

    def on_view_changelog_clicked(self, button):
        changelog_url = self.source_url_label.get_label().replace("Source: ", "")
        print(f"View Changelog clicked for {self.package_name_label.get_label()}, URL: {changelog_url}")
        # Logic to open the changelog URL in a web browser
        if changelog_url and changelog_url != "N/A":
            Gtk.show_uri(self.get_root(), changelog_url, Gdk.CURRENT_TIME) # GTK4 for opening URL
        pass

    def on_ignore_version_clicked(self, button):
        print(f"Ignore Version clicked for {self.package_name_label.get_label()} (Version: {self.upstream_version_label.get_label()})")
        # Logic to store this version as ignored in preferences
        pass

    def on_enable_sandbox_toggled(self, checkbutton):
        self.sandbox_options_box.set_visible(checkbutton.get_active())
        print(f"Sandbox toggled: {checkbutton.get_active()}")

    def on_confirm_sandbox_update_clicked(self, button):
        level_id = self.sandbox_level_combo.get_active_id()
        allow_network = self.sandbox_network_check.get_active()
        allow_home = self.sandbox_home_check.get_active()

        print(f"Confirm Sandboxed Update for {self.package_name_label.get_label()} with settings:")
        print(f"  Level: {level_id}, Network: {allow_network}, Home: {allow_home}")
        # Logic to initiate the update process with sandboxing and selected settings
        pass
