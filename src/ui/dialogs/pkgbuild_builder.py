import os
import re
import json
import hashlib
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from gi.repository import Gtk, Adw, GObject, Gio, GLib, Pango, Gdk

class PKGBUILDType(Enum):
    BINARY = "binary"
    SOURCE = "source"
    GIT = "git"
    PYTHON = "python"
    NODE = "node"
    LIBRARY = "library"
    KERNEL_MODULE = "kernel_module"
    FONTS = "fonts"
    THEMES = "themes"
    CUSTOM = "custom"

class ValidationLevel(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

@dataclass
class ValidationResult:
    level: ValidationLevel
    field: str
    message: str
    suggestion: Optional[str] = None

@dataclass
class PKGBUILDTemplate:
    name: str
    type: PKGBUILDType
    description: str
    template: str
    required_fields: List[str]
    optional_fields: List[str]
    default_values: Dict[str, str] = field(default_factory=dict)

@dataclass
class PKGBUILDField:
    name: str
    display_name: str
    field_type: str
    required: bool
    default_value: str = ""
    placeholder: str = ""
    tooltip: str = ""
    validation_pattern: Optional[str] = None
    multiline: bool = False

class PKGBUILDBuilder(Adw.Window):
    __gsignals__ = {
        'pkgbuild-created': (GObject.SignalFlags.RUN_LAST, None, (str, str)),
        'template-changed': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'validation-completed': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'builder-closed': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, parent_window: Optional[Gtk.Window] = None, initial_path: Optional[str] = None):
        super().__init__()
        self.set_title("PKGBUILD Builder")
        self.set_default_size(950, 750)
        self.set_modal(True)
        if parent_window:
            self.set_transient_for(parent_window)
        
        self.current_template = None
        self.field_values = {}
        self.validation_results = []
        self.wizard_pages = []
        self.current_page = 0
        self.initial_path = initial_path
        self.auto_save_enabled = True
        self.auto_save_timer = None
        
        self._load_templates()
        self._setup_ui()
        self._setup_wizard_pages()
        self._load_user_preferences()

    def _load_templates(self):
        self.templates = {
            PKGBUILDType.BINARY: PKGBUILDTemplate(
                name="Binary Package",
                type=PKGBUILDType.BINARY,
                description="Pre-compiled binary package ready for installation",
                template="""# Maintainer: {maintainer}
pkgname={pkgname}
pkgver={pkgver}
pkgrel={pkgrel}
pkgdesc="{pkgdesc}"
arch=({arch})
url="{url}"
license=({license})
depends=({depends})
source=("{source}")
sha256sums=('{sha256sum}')

package() {{
    cd "$srcdir"
    {package_function}
}}""",
                required_fields=["maintainer", "pkgname", "pkgver", "pkgrel", "pkgdesc", "arch", "source"],
                optional_fields=["url", "license", "depends", "optdepends", "conflicts", "provides", "backup"]
            ),
            
            PKGBUILDType.SOURCE: PKGBUILDTemplate(
                name="Source Package",
                type=PKGBUILDType.SOURCE,
                description="Package built from source code with compilation",
                template="""# Maintainer: {maintainer}
pkgname={pkgname}
pkgver={pkgver}
pkgrel={pkgrel}
pkgdesc="{pkgdesc}"
arch=({arch})
url="{url}"
license=({license})
depends=({depends})
makedepends=({makedepends})
checkdepends=({checkdepends})
source=("{source}")
sha256sums=('{sha256sum}')

prepare() {{
    cd "$srcdir/{source_dir}"
    {prepare_function}
}}

build() {{
    cd "$srcdir/{source_dir}"
    {build_function}
}}

check() {{
    cd "$srcdir/{source_dir}"
    {check_function}
}}

package() {{
    cd "$srcdir/{source_dir}"
    {package_function}
}}""",
                required_fields=["maintainer", "pkgname", "pkgver", "pkgrel", "pkgdesc", "arch", "source"],
                optional_fields=["url", "license", "depends", "makedepends", "checkdepends", "optdepends", "source_dir"]
            ),
            
            PKGBUILDType.GIT: PKGBUILDTemplate(
                name="Git Package",
                type=PKGBUILDType.GIT,
                description="Package from Git repository with version control",
                template="""# Maintainer: {maintainer}
pkgname={pkgname}
pkgver={pkgver}
pkgrel={pkgrel}
pkgdesc="{pkgdesc}"
arch=({arch})
url="{url}"
license=({license})
depends=({depends})
makedepends=('git' {makedepends})
provides=('{provides}')
conflicts=('{conflicts}')
source=('git+{git_url}')
sha256sums=('SKIP')

pkgver() {{
    cd "$srcdir/{git_dir}"
    {pkgver_function}
}}

prepare() {{
    cd "$srcdir/{git_dir}"
    {prepare_function}
}}

build() {{
    cd "$srcdir/{git_dir}"
    {build_function}
}}

package() {{
    cd "$srcdir/{git_dir}"
    {package_function}
}}""",
                required_fields=["maintainer", "pkgname", "pkgver", "pkgrel", "pkgdesc", "arch", "git_url"],
                optional_fields=["url", "license", "depends", "makedepends", "provides", "conflicts", "git_dir"]
            ),
            
            PKGBUILDType.PYTHON: PKGBUILDTemplate(
                name="Python Package",
                type=PKGBUILDType.PYTHON,
                description="Python package from PyPI with modern build system",
                template="""# Maintainer: {maintainer}
pkgname={pkgname}
pkgver={pkgver}
pkgrel={pkgrel}
pkgdesc="{pkgdesc}"
arch=({arch})
url="{url}"
license=({license})
depends=('python' {depends})
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel' {makedepends})
checkdepends=('python-pytest' {checkdepends})
source=("https://pypi.org/packages/source/{first_letter}/{python_name}/{python_name}-$pkgver.tar.gz")
sha256sums=('{sha256sum}')

build() {{
    cd "$srcdir/{python_name}-$pkgver"
    python -m build --wheel --no-isolation
}}

check() {{
    cd "$srcdir/{python_name}-$pkgver"
    python -m pytest
}}

package() {{
    cd "$srcdir/{python_name}-$pkgver"
    python -m installer --destdir="$pkgdir" dist/*.whl
}}""",
                required_fields=["maintainer", "pkgname", "pkgver", "pkgrel", "pkgdesc", "python_name"],
                optional_fields=["url", "license", "depends", "makedepends", "checkdepends", "optdepends"]
            ),
            
            PKGBUILDType.NODE: PKGBUILDTemplate(
                name="Node.js Package",
                type=PKGBUILDType.NODE,
                description="Node.js package with npm/yarn build system",
                template="""# Maintainer: {maintainer}
pkgname={pkgname}
pkgver={pkgver}
pkgrel={pkgrel}
pkgdesc="{pkgdesc}"
arch=({arch})
url="{url}"
license=({license})
depends=('nodejs' {depends})
makedepends=('npm' {makedepends})
source=("https://registry.npmjs.org/{node_name}/-/{node_name}-$pkgver.tgz")
sha256sums=('{sha256sum}')

build() {{
    cd "$srcdir/package"
    npm install --production
}}

package() {{
    cd "$srcdir/package"
    npm pack
    install -dm755 "$pkgdir/usr/lib/node_modules/{node_name}"
    tar xf {node_name}-$pkgver.tgz --strip-components=1 -C "$pkgdir/usr/lib/node_modules/{node_name}"
    
    if [[ -f bin/{node_name} ]]; then
        install -dm755 "$pkgdir/usr/bin"
        ln -s "/usr/lib/node_modules/{node_name}/bin/{node_name}" "$pkgdir/usr/bin/{node_name}"
    fi
}}""",
                required_fields=["maintainer", "pkgname", "pkgver", "pkgrel", "pkgdesc", "node_name"],
                optional_fields=["url", "license", "depends", "makedepends", "optdepends"]
            ),
            
            PKGBUILDType.LIBRARY: PKGBUILDTemplate(
                name="Library Package",
                type=PKGBUILDType.LIBRARY,
                description="Shared library with development files",
                template="""# Maintainer: {maintainer}
pkgbase={pkgbase}
pkgname=('{pkgname}' '{pkgname}-dev')
pkgver={pkgver}
pkgrel={pkgrel}
pkgdesc="{pkgdesc}"
arch=({arch})
url="{url}"
license=({license})
depends=({depends})
makedepends=({makedepends})
source=("{source}")
sha256sums=('{sha256sum}')

build() {{
    cd "$srcdir/{source_dir}"
    {build_function}
}}

package_{pkgname}() {{
    pkgdesc="{pkgdesc} - runtime library"
    depends=({runtime_depends})
    
    cd "$srcdir/{source_dir}"
    {runtime_package_function}
}}

package_{pkgname}-dev() {{
    pkgdesc="{pkgdesc} - development files"
    depends=('{pkgname}={pkgver}')
    
    cd "$srcdir/{source_dir}"
    {dev_package_function}
}}""",
                required_fields=["maintainer", "pkgbase", "pkgname", "pkgver", "pkgrel", "pkgdesc", "arch", "source"],
                optional_fields=["url", "license", "depends", "makedepends", "runtime_depends", "source_dir"]
            ),
            
            PKGBUILDType.FONTS: PKGBUILDTemplate(
                name="Font Package",
                type=PKGBUILDType.FONTS,
                description="Font package with proper installation paths",
                template="""# Maintainer: {maintainer}
pkgname={pkgname}
pkgver={pkgver}
pkgrel={pkgrel}
pkgdesc="{pkgdesc}"
arch=('any')
url="{url}"
license=({license})
depends=('fontconfig')
source=("{source}")
sha256sums=('{sha256sum}')

package() {{
    cd "$srcdir"
    
    install -dm755 "$pkgdir/usr/share/fonts/{font_family}"
    {font_install_commands}
    
    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}}""",
                required_fields=["maintainer", "pkgname", "pkgver", "pkgrel", "pkgdesc", "source", "font_family"],
                optional_fields=["url", "license", "font_install_commands"]
            ),
            
            PKGBUILDType.CUSTOM: PKGBUILDTemplate(
                name="Custom Package",
                type=PKGBUILDType.CUSTOM,
                description="Fully customizable package template",
                template="""# Maintainer: {maintainer}
pkgname={pkgname}
pkgver={pkgver}
pkgrel={pkgrel}
pkgdesc="{pkgdesc}"
arch=({arch})
url="{url}"
license=({license})
depends=({depends})
makedepends=({makedepends})
source=({source})
sha256sums=({sha256sum})

{custom_functions}""",
                required_fields=["maintainer", "pkgname", "pkgver", "pkgrel", "pkgdesc"],
                optional_fields=["arch", "url", "license", "depends", "makedepends", "source", "sha256sum", "custom_functions"]
            )
        }
        
        self.field_definitions = {
            "maintainer": PKGBUILDField("maintainer", "Maintainer", "entry", True, "", "Your Name <email@example.com>", "Package maintainer information"),
            "pkgbase": PKGBUILDField("pkgbase", "Package Base", "entry", False, "", "package-base", "Base name for split packages"),
            "pkgname": PKGBUILDField("pkgname", "Package Name", "entry", True, "", "my-package", "Unique package name (lowercase, no spaces)", r"^[a-z0-9][a-z0-9+._-]*$"),
            "pkgver": PKGBUILDField("pkgver", "Version", "entry", True, "", "1.0.0", "Package version", r"^[0-9]+(\.[0-9]+)*.*$"),
            "pkgrel": PKGBUILDField("pkgrel", "Release", "entry", True, "1", "1", "Package release number", r"^[0-9]+$"),
            "pkgdesc": PKGBUILDField("pkgdesc", "Description", "entry", True, "", "Short package description", "Brief description of the package"),
            "arch": PKGBUILDField("arch", "Architecture", "combo", True, "'x86_64'", "", "Target architecture"),
            "url": PKGBUILDField("url", "Homepage URL", "entry", False, "", "https://example.com", "Project homepage"),
            "license": PKGBUILDField("license", "License", "combo", False, "'unknown'", "", "Package license"),
            "depends": PKGBUILDField("depends", "Dependencies", "entry", False, "", "glibc", "Runtime dependencies (space-separated)"),
            "makedepends": PKGBUILDField("makedepends", "Build Dependencies", "entry", False, "", "gcc make", "Build-time dependencies"),
            "checkdepends": PKGBUILDField("checkdepends", "Check Dependencies", "entry", False, "", "python-pytest", "Test dependencies"),
            "optdepends": PKGBUILDField("optdepends", "Optional Dependencies", "text", False, "", "optional-pkg: for extra functionality", "Optional dependencies with descriptions", None, True),
            "provides": PKGBUILDField("provides", "Provides", "entry", False, "", "", "Virtual packages provided"),
            "conflicts": PKGBUILDField("conflicts", "Conflicts", "entry", False, "", "", "Conflicting packages"),
            "replaces": PKGBUILDField("replaces", "Replaces", "entry", False, "", "", "Packages replaced by this one"),
            "backup": PKGBUILDField("backup", "Backup Files", "entry", False, "", "etc/config.conf", "Configuration files to backup"),
            "source": PKGBUILDField("source", "Source URL", "entry", True, "", "https://example.com/file.tar.gz", "Source download URL"),
            "sha256sum": PKGBUILDField("sha256sum", "SHA256 Checksum", "entry", False, "SKIP", "", "SHA256 checksum of source"),
            "git_url": PKGBUILDField("git_url", "Git URL", "entry", False, "", "https://github.com/user/repo.git", "Git repository URL"),
            "git_dir": PKGBUILDField("git_dir", "Git Directory", "entry", False, "", "repo-name", "Git repository directory name"),
            "python_name": PKGBUILDField("python_name", "Python Package Name", "entry", False, "", "package-name", "Python package name on PyPI"),
            "node_name": PKGBUILDField("node_name", "Node Package Name", "entry", False, "", "package-name", "Node.js package name on npm"),
            "first_letter": PKGBUILDField("first_letter", "First Letter", "entry", False, "", "p", "First letter for PyPI URL"),
            "source_dir": PKGBUILDField("source_dir", "Source Directory", "entry", False, "", "package-1.0.0", "Source directory name"),
            "font_family": PKGBUILDField("font_family", "Font Family", "entry", False, "", "TTF", "Font family directory"),
            "font_install_commands": PKGBUILDField("font_install_commands", "Font Install Commands", "text", False, "", "install -m644 *.ttf \"$pkgdir/usr/share/fonts/TTF/\"", "Commands to install fonts", None, True),
            "runtime_depends": PKGBUILDField("runtime_depends", "Runtime Dependencies", "entry", False, "", "glibc", "Runtime library dependencies"),
            "prepare_function": PKGBUILDField("prepare_function", "Prepare Function", "text", False, "", "patch -p1 < ../fix.patch", "Commands for prepare() function", None, True),
            "build_function": PKGBUILDField("build_function", "Build Function", "text", False, "", "./configure --prefix=/usr\nmake", "Commands for build() function", None, True),
            "check_function": PKGBUILDField("check_function", "Check Function", "text", False, "", "make check", "Commands for check() function", None, True),
            "package_function": PKGBUILDField("package_function", "Package Function", "text", False, "", "make DESTDIR=\"$pkgdir\" install", "Commands for package() function", None, True),
            "pkgver_function": PKGBUILDField("pkgver_function", "Version Function", "text", False, "", "git describe --long --tags | sed 's/^v//;s/\\([^-]*-g\\)/r\\1/;s/-/./g'", "Commands for pkgver() function", None, True),
            "runtime_package_function": PKGBUILDField("runtime_package_function", "Runtime Package Function", "text", False, "", "make DESTDIR=\"$pkgdir\" install", "Commands for runtime package", None, True),
            "dev_package_function": PKGBUILDField("dev_package_function", "Development Package Function", "text", False, "", "make DESTDIR=\"$pkgdir\" install-dev", "Commands for development package", None, True),
            "custom_functions": PKGBUILDField("custom_functions", "Custom Functions", "text", False, "", "build() {\n    # Custom build commands\n}", "Custom PKGBUILD functions", None, True)
        }

    def _setup_ui(self):
        self.header_bar = Adw.HeaderBar()
        self.set_titlebar(self.header_bar)
        
        self.cancel_button = Gtk.Button.new_with_label("Cancel")
        self.cancel_button.connect("clicked", self._on_cancel)
        self.header_bar.pack_start(self.cancel_button)
        
        self.help_button = Gtk.Button.new_from_icon_name("help-about-symbolic")
        self.help_button.set_tooltip_text("Show Help")
        self.help_button.connect("clicked", self._show_help)
        self.header_bar.pack_end(self.help_button)
        
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.main_box)
        
        self._create_wizard_navigation()
        self._create_content_area()
        self._create_action_buttons()

    def _create_wizard_navigation(self):
        self.nav_scrolled = Gtk.ScrolledWindow()
        self.nav_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.nav_scrolled.set_min_content_height(60)
        
        self.nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.nav_box.add_css_class("toolbar")
        self.nav_box.set_margin_top(12)
        self.nav_box.set_margin_bottom(12)
        self.nav_box.set_margin_start(12)
        self.nav_box.set_margin_end(12)
        
        self.nav_buttons = []
        steps = ["Template", "Basic Info", "Dependencies", "Build Config", "Functions", "Review"]
        
        for i, step in enumerate(steps):
            button = Gtk.ToggleButton.new_with_label(f"{i+1}. {step}")
            button.set_group(self.nav_buttons[0] if self.nav_buttons else None)
            button.connect("toggled", self._on_nav_button_toggled, i)
            button.add_css_class("navigation-button")
            self.nav_buttons.append(button)
            self.nav_box.append(button)
        
        self.nav_scrolled.set_child(self.nav_box)
        self.main_box.append(self.nav_scrolled)

    def _create_content_area(self):
        self.stack = Adw.ViewStack()
        self.stack.set_vexpand(True)
        self.main_box.append(self.stack)

    def _create_action_buttons(self):
        self.action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.action_box.set_margin_top(12)
        self.action_box.set_margin_bottom(12)
        self.action_box.set_margin_start(12)
        self.action_box.set_margin_end(12)
        self.action_box.set_halign(Gtk.Align.END)
        
        self.auto_save_switch = Gtk.Switch()
        self.auto_save_switch.set_active(self.auto_save_enabled)
        self.auto_save_switch.connect("state-set", self._on_auto_save_toggled)
        
        auto_save_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        auto_save_box.append(Gtk.Label(label="Auto-save:"))
        auto_save_box.append(self.auto_save_switch)
        self.action_box.append(auto_save_box)
        
        self.action_box.append(Gtk.Separator())
        
        self.previous_button = Gtk.Button.new_with_label("Previous")
        self.previous_button.connect("clicked", self._on_previous)
        self.previous_button.set_sensitive(False)
        self.action_box.append(self.previous_button)
        
        self.next_button = Gtk.Button.new_with_label("Next")
        self.next_button.add_css_class("suggested-action")
        self.next_button.connect("clicked", self._on_next)
        self.action_box.append(self.next_button)
        
        self.finish_button = Gtk.Button.new_with_label("Create PKGBUILD")
        self.finish_button.add_css_class("suggested-action")
        self.finish_button.connect("clicked", self._on_finish)
        self.finish_button.set_visible(False)
        self.action_box.append(self.finish_button)
        
        self.main_box.append(self.action_box)

    def _setup_wizard_pages(self):
        self._create_template_page()
        self._create_basic_info_page()
        self._create_dependencies_page()
        self._create_build_config_page()
        self._create_functions_page()
        self._create_review_page()
        
        self.nav_buttons[0].set_active(True)

    def _create_template_page(self):
        page = Adw.PreferencesPage()
        page.set_title("Choose Template")
        
        group = Adw.PreferencesGroup()
        group.set_title("PKGBUILD Templates")
        group.set_description("Select a template that matches your package type for guided creation")
        page.add(group)
        
        self.template_list = Gtk.ListBox()
        self.template_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.template_list.add_css_class("boxed-list")
        self.template_list.connect("row-selected", self._on_template_selected)
        
        template_icons = {
            PKGBUILDType.BINARY: "package-x-generic-symbolic",
            PKGBUILDType.SOURCE: "text-x-script-symbolic",
            PKGBUILDType.GIT: "software-update-available-symbolic",
            PKGBUILDType.PYTHON: "applications-development-symbolic",
            PKGBUILDType.NODE: "applications-internet-symbolic",
            PKGBUILDType.LIBRARY: "system-component-library-symbolic",
            PKGBUILDType.FONTS: "font-x-generic-symbolic",
            PKGBUILDType.CUSTOM: "text-editor-symbolic"
        }
        
        for template_type, template in self.templates.items():
            row = Adw.ActionRow()
            row.set_title(template.name)
            row.set_subtitle(template.description)
            
            icon_name = template_icons.get(template_type, "text-x-script-symbolic")
            icon = Gtk.Image.new_from_icon_name(icon_name)
            row.add_prefix(icon)
            
            check_icon = Gtk.Image.new_from_icon_name("object-select-symbolic")
            check_icon.set_visible(False)
            row.add_suffix(check_icon)
            
            row.template_type = template_type
            row.check_icon = check_icon
            self.template_list.append(row)
        
        group.add(self.template_list)
        
        self.stack.add_titled(page, "template", "Template")

    def _create_basic_info_page(self):
        page = Adw.PreferencesPage()
        page.set_title("Basic Information")
        
        self.basic_fields = {}
        
        general_group = Adw.PreferencesGroup()
        general_group.set_title("Package Information")
        general_group.set_description("Essential package metadata and identification")
        page.add(general_group)
        
        basic_field_names = ["maintainer", "pkgname", "pkgver", "pkgrel", "pkgdesc", "arch", "url", "license"]
        
        for field_name in basic_field_names:
            field_def = self.field_definitions.get(field_name)
            if not field_def:
                continue
                
            if field_def.field_type == "entry":
                row = Adw.EntryRow()
                row.set_title(field_def.display_name)
                if field_def.placeholder:
                    row.set_placeholder_text(field_def.placeholder)
                if field_def.default_value:
                    row.set_text(field_def.default_value)
                if field_def.tooltip:
                    row.set_tooltip_text(field_def.tooltip)
                
                if field_def.required:
                    title_widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                    title_widget.append(Gtk.Label(label=field_def.display_name))
                    required_label = Gtk.Label(label="*")
                    required_label.add_css_class("error")
                    title_widget.append(required_label)
                    row.set_title_widget(title_widget)
                
                entry = row.get_delegate()
                entry.connect("changed", self._on_field_changed, field_name)
                self.basic_fields[field_name] = entry
                
            elif field_def.field_type == "combo":
                row = Adw.ComboRow()
                row.set_title(field_def.display_name)
                if field_def.tooltip:
                    row.set_tooltip_text(field_def.tooltip)
                
                if field_name == "arch":
                    model = Gtk.StringList()
                    archs = ["'x86_64'", "'i686'", "'arm'", "'armv6h'", "'armv7h'", "'aarch64'", "'any'"]
                    for arch in archs:
                        model.append(arch)
                    row.set_model(model)
                    row.set_selected(0)
                    
                elif field_name == "license":
                    model = Gtk.StringList()
                    licenses = ["'GPL2'", "'GPL3'", "'LGPL2.1'", "'LGPL3'", "'BSD'", "'MIT'", "'Apache'", "'MPL2'", "'custom'", "'unknown'"]
                    for license in licenses:
                        model.append(license)
                    row.set_model(model)
                    row.set_selected(9)
                
                row.connect("notify::selected", self._on_combo_changed, field_name)
                self.basic_fields[field_name] = row
            
            general_group.add(row)
        
        self.stack.add_titled(page, "basic", "Basic Info")

    def _create_dependencies_page(self):
        page = Adw.PreferencesPage()
        page.set_title("Dependencies")
        
        self.dep_fields = {}
        
        deps_group = Adw.PreferencesGroup()
        deps_group.set_title("Package Dependencies")
        deps_group.set_description("Specify runtime, build-time, and optional dependencies")
        page.add(deps_group)
        
        dep_field_names = ["depends", "makedepends", "checkdepends", "optdepends", "provides", "conflicts", "replaces"]
        
        for field_name in dep_field_names:
            field_def = self.field_definitions.get(field_name)
            if not field_def:
                continue
            
            if field_def.multiline:
                row = Adw.PreferencesRow()
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
                box.set_margin_top(12)
                box.set_margin_bottom(12)
                box.set_margin_start(12)
                box.set_margin_end(12)
                
                label = Gtk.Label()
                label.set_text(field_def.display_name)
                label.set_halign(Gtk.Align.START)
                label.add_css_class("heading")
                box.append(label)
                
                scrolled = Gtk.ScrolledWindow()
                scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
                scrolled.set_min_content_height(100)
                
                text_view = Gtk.TextView()
                text_view.set_wrap_mode(Gtk.WrapMode.WORD)
                text_view.set_left_margin(8)
                text_view.set_right_margin(8)
                text_view.set_top_margin(8)
                text_view.set_bottom_margin(8)
                
                if field_def.placeholder:
                    placeholder_label = Gtk.Label(label=field_def.placeholder)
                    placeholder_label.add_css_class("dim-label")
                    placeholder_label.set_halign(Gtk.Align.START)
                    box.append(placeholder_label)
                
                scrolled.set_child(text_view)
                box.append(scrolled)
                
                row.set_child(box)
                buffer = text_view.get_buffer()
                buffer.connect("changed", self._on_text_buffer_changed, field_name)
                self.dep_fields[field_name] = buffer
                
            else:
                row = Adw.EntryRow()
                row.set_title(field_def.display_name)
                if field_def.placeholder:
                    row.set_placeholder_text(field_def.placeholder)
                if field_def.tooltip:
                    row.set_tooltip_text(field_def.tooltip)
                
                entry = row.get_delegate()
                entry.connect("changed", self._on_field_changed, field_name)
                self.dep_fields[field_name] = entry
            
            deps_group.add(row)
        
        self.stack.add_titled(page, "dependencies", "Dependencies")

    def _create_build_config_page(self):
        page = Adw.PreferencesPage()
        page.set_title("Build Configuration")
        
        self.build_fields = {}
        
        source_group = Adw.PreferencesGroup()
        source_group.set_title("Source Configuration")
        source_group.set_description("Configure source files and checksums")
        page.add(source_group)
        
        source_fields = ["source", "git_url", "python_name", "node_name", "first_letter", "source_dir", "git_dir"]
        
        for field_name in source_fields:
            field_def = self.field_definitions.get(field_name)
            if not field_def:
                continue
                
            row = Adw.EntryRow()
            row.set_title(field_def.display_name)
            if field_def.placeholder:
                row.set_placeholder_text(field_def.placeholder)
            if field_def.tooltip:
                row.set_tooltip_text(field_def.tooltip)
            
            entry = row.get_delegate()
            entry.connect("changed", self._on_field_changed, field_name)
            self.build_fields[field_name] = entry
            source_group.add(row)
        
        checksum_group = Adw.PreferencesGroup()
        checksum_group.set_title("File Verification")
        page.add(checksum_group)
        
        checksum_row = Adw.ActionRow()
        checksum_row.set_title("SHA256 Checksum")
        checksum_row.set_subtitle("Leave empty for auto-calculation or use 'SKIP' for VCS sources")
        
        checksum_entry = Gtk.Entry()
        checksum_entry.set_placeholder_text("Auto-calculated or SKIP")
        checksum_entry.set_hexpand(True)
        checksum_entry.connect("changed", self._on_field_changed, "sha256sum")
        self.build_fields["sha256sum"] = checksum_entry
        checksum_row.add_suffix(checksum_entry)
        
        calculate_button = Gtk.Button.new_with_label("Calculate")
        calculate_button.set_tooltip_text("Download and calculate checksum")
        calculate_button.connect("clicked", self._on_calculate_checksum)
        checksum_row.add_suffix(calculate_button)
        checksum_group.add(checksum_row)
        
        self.stack.add_titled(page, "build", "Build Config")

    def _create_functions_page(self):
        page = Adw.PreferencesPage()
        page.set_title("Build Functions")
        
        self.function_fields = {}
        
        functions_group = Adw.PreferencesGroup()
        functions_group.set_title("PKGBUILD Functions")
        functions_group.set_description("Customize the build process with shell commands")
        page.add(functions_group)
        
        function_data = [
            ("prepare_function", "prepare()", "Prepare source code (patches, configuration)"),
            ("build_function", "build()", "Compile and build the software"),
            ("check_function", "check()", "Run tests and quality checks"),
            ("package_function", "package()", "Install files to package directory"),
            ("pkgver_function", "pkgver()", "Generate version for VCS packages"),
            ("custom_functions", "Custom Functions", "Additional custom functions")
        ]
        
        for func_name, title, description in function_data:
            field_def = self.field_definitions.get(func_name)
            if not field_def:
                continue
                
            row = Adw.PreferencesRow()
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            box.set_margin_top(12)
            box.set_margin_bottom(12)
            box.set_margin_start(12)
            box.set_margin_end(12)
            
            header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            
            label = Gtk.Label()
            label.set_text(title)
            label.set_halign(Gtk.Align.START)
            label.add_css_class("heading")
            header_box.append(label)
            
            desc_label = Gtk.Label()
            desc_label.set_text(description)
            desc_label.set_halign(Gtk.Align.START)
            desc_label.add_css_class("dim-label")
            desc_label.add_css_class("caption")
            header_box.append(desc_label)
            
            box.append(header_box)
            
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            scrolled.set_min_content_height(120)
            
            text_view = Gtk.TextView()
            text_view.set_wrap_mode(Gtk.WrapMode.WORD)
            text_view.add_css_class("monospace")
            text_view.set_left_margin(8)
            text_view.set_right_margin(8)
            text_view.set_top_margin(8)
            text_view.set_bottom_margin(8)
            
            if field_def.default_value:
                buffer = text_view.get_buffer()
                buffer.set_text(field_def.default_value)
            
            scrolled.set_child(text_view)
            box.append(scrolled)
            
            row.set_child(box)
            buffer = text_view.get_buffer()
            buffer.connect("changed", self._on_text_buffer_changed, func_name)
            self.function_fields[func_name] = buffer
            functions_group.add(row)
        
        self.stack.add_titled(page, "functions", "Functions")

    def _create_review_page(self):
        page = Adw.PreferencesPage()
        page.set_title("Review and Create")
        
        preview_group = Adw.PreferencesGroup()
        preview_group.set_title("PKGBUILD Preview")
        preview_group.set_description("Review the generated PKGBUILD before creation")
        page.add(preview_group)
        
        self.preview_scrolled = Gtk.ScrolledWindow()
        self.preview_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.preview_scrolled.set_min_content_height(350)
        
        self.preview_text = Gtk.TextView()
        self.preview_text.set_editable(False)
        self.preview_text.set_wrap_mode(Gtk.WrapMode.WORD)
        self.preview_text.add_css_class("monospace")
        self.preview_text.set_left_margin(12)
        self.preview_text.set_right_margin(12)
        self.preview_text.set_top_margin(12)
        self.preview_text.set_bottom_margin(12)
        
        self.preview_scrolled.set_child(self.preview_text)
        preview_group.add(self.preview_scrolled)
        
        validation_group = Adw.PreferencesGroup()
        validation_group.set_title("Validation Results")
        validation_group.set_description("Checks for common issues and best practices")
        page.add(validation_group)
        
        self.validation_list = Gtk.ListBox()
        self.validation_list.add_css_class("boxed-list")
        validation_group.add(self.validation_list)
        
        actions_group = Adw.PreferencesGroup()
        actions_group.set_title("Actions")
        page.add(actions_group)
        
        save_template_row = Adw.ActionRow()
        save_template_row.set_title("Save as Template")
        save_template_row.set_subtitle("Save current configuration as a reusable template")
        save_template_button = Gtk.Button.new_with_label("Save Template")
        save_template_button.connect("clicked", self._on_save_template)
        save_template_row.add_suffix(save_template_button)
        actions_group.add(save_template_row)
        
        self.stack.add_titled(page, "review", "Review")

    def _on_template_selected(self, listbox, row):
        if row:
            for child in listbox:
                if hasattr(child, 'check_icon'):
                    child.check_icon.set_visible(False)
            
            row.check_icon.set_visible(True)
            template_type = row.template_type
            self.current_template = self.templates[template_type]
            self.emit('template-changed', self.current_template)
            self._populate_template_defaults()
            self._setup_auto_save()

    def _populate_template_defaults(self):
        if not self.current_template:
            return
        
        for field_name, default_value in self.current_template.default_values.items():
            if field_name in self.basic_fields:
                field = self.basic_fields[field_name]
                if isinstance(field, Gtk.Entry):
                    field.set_text(default_value)
                elif isinstance(field, Adw.ComboRow):
                    model = field.get_model()
                    for i in range(model.get_n_items()):
                        if model.get_string(i) == default_value:
                            field.set_selected(i)
                            break
        
        self._auto_fill_python_fields()
        self._auto_fill_git_fields()

    def _auto_fill_python_fields(self):
        if self.current_template and self.current_template.type == PKGBUILDType.PYTHON:
            python_name = self.build_fields.get("python_name")
            first_letter = self.build_fields.get("first_letter")
            
            if python_name and first_letter:
                python_name.connect("changed", lambda entry: 
                    first_letter.set_text(entry.get_text()[0].lower() if entry.get_text() else ""))

    def _auto_fill_git_fields(self):
        if self.current_template and self.current_template.type == PKGBUILDType.GIT:
            git_url = self.build_fields.get("git_url")
            git_dir = self.build_fields.get("git_dir")
            
            if git_url and git_dir:
                def update_git_dir(entry):
                    url = entry.get_text()
                    if url:
                        import os
                        repo_name = os.path.splitext(os.path.basename(url))[0]
                        git_dir.set_text(repo_name)
                
                git_url.connect("changed", update_git_dir)

    def _on_field_changed(self, entry, field_name):
        self.field_values[field_name] = entry.get_text()
        self._trigger_auto_save()
        if self.current_page == 5:
            self._update_preview()

    def _on_combo_changed(self, combo, pspec, field_name):
        model = combo.get_model()
        selected = combo.get_selected()
        if model and selected != Gtk.INVALID_LIST_POSITION:
            self.field_values[field_name] = model.get_string(selected)
            self._trigger_auto_save()
            if self.current_page == 5:
                self._update_preview()

    def _on_text_buffer_changed(self, buffer, field_name):
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        self.field_values[field_name] = buffer.get_text(start, end, False)
        self._trigger_auto_save()
        if self.current_page == 5:
            self._update_preview()

    def _on_calculate_checksum(self, button):
        source_entry = self.build_fields.get("source")
        if not source_entry or not source_entry.get_text():
            self._show_error("No source URL provided", "Please enter a source URL first.")
            return
        
        url = source_entry.get_text()
        button.set_sensitive(False)
        button.set_label("Calculating...")
        
        def calculate_in_thread():
            try:
                response = urllib.request.urlopen(url, timeout=30)
                content = response.read()
                sha256_hash = hashlib.sha256(content).hexdigest()
                
                GLib.idle_add(self._on_checksum_calculated, sha256_hash, button)
            except Exception as e:
                GLib.idle_add(self._on_checksum_error, str(e), button)
        
        import threading
        thread = threading.Thread(target=calculate_in_thread)
        thread.daemon = True
        thread.start()

    def _on_checksum_calculated(self, checksum, button):
        checksum_field = self.build_fields.get("sha256sum")
        if checksum_field:
            checksum_field.set_text(checksum)
        
        button.set_sensitive(True)
        button.set_label("Calculate")
        
        self._show_info("Checksum calculated successfully", f"SHA256: {checksum[:16]}...")

    def _on_checksum_error(self, error_msg, button):
        button.set_sensitive(True)
        button.set_label("Calculate")
        self._show_error("Checksum calculation failed", f"Could not download or calculate checksum: {error_msg}")

    def _on_nav_button_toggled(self, button, page_index):
        if button.get_active():
            self._switch_to_page(page_index)

    def _on_previous(self, button):
        if self.current_page > 0:
            self.current_page -= 1
            self.nav_buttons[self.current_page].set_active(True)

    def _on_next(self, button):
        if self._validate_current_page():
            if self.current_page < len(self.nav_buttons) - 1:
                self.current_page += 1
                self.nav_buttons[self.current_page].set_active(True)

    def _switch_to_page(self, page_index):
        self.current_page = page_index
        
        pages = ["template", "basic", "dependencies", "build", "functions", "review"]
        if page_index < len(pages):
            self.stack.set_visible_child_name(pages[page_index])
        
        self.previous_button.set_sensitive(page_index > 0)
        
        for i, button in enumerate(self.nav_buttons):
            if i < page_index:
                button.add_css_class("completed")
            else:
                button.remove_css_class("completed")
        
        if page_index == len(pages) - 1:
            self.next_button.set_visible(False)
            self.finish_button.set_visible(True)
            self._update_preview()
            self._validate_all_fields()
        else:
            self.next_button.set_visible(True)
            self.finish_button.set_visible(False)

    def _validate_current_page(self) -> bool:
        if self.current_page == 0:
            if not self.current_template:
                self._show_error("Template Required", "Please select a PKGBUILD template.")
                return False
            return True
        elif self.current_page == 1:
            return self._validate_basic_fields()
        elif self.current_page == 2:
            return self._validate_dependencies()
        elif self.current_page == 3:
            return self._validate_build_config()
        return True

    def _validate_basic_fields(self) -> bool:
        if not self.current_template:
            return False
        
        errors = []
        for field_name in self.current_template.required_fields:
            field_def = self.field_definitions.get(field_name)
            if not field_def:
                continue
            
            value = self.field_values.get(field_name, "").strip()
            if field_def.required and not value:
                errors.append(f"{field_def.display_name} is required")
                continue
            
            if field_def.validation_pattern and value:
                if not re.match(field_def.validation_pattern, value):
                    errors.append(f"Invalid format for {field_def.display_name}")
        
        if errors:
            self._show_error("Validation Failed", "\n".join(errors))
            return False
        
        return True

    def _validate_dependencies(self) -> bool:
        return True

    def _validate_build_config(self) -> bool:
        source = self.field_values.get("source", "")
        git_url = self.field_values.get("git_url", "")
        
        if self.current_template and self.current_template.type == PKGBUILDType.GIT:
            if not git_url:
                self._show_error("Git URL Required", "Git packages require a Git repository URL.")
                return False
        elif not source and self.current_template and "source" in self.current_template.required_fields:
            self._show_error("Source Required", "Please provide a source URL.")
            return False
        
        return True

    def _validate_all_fields(self):
        self.validation_results.clear()
        
        while self.validation_list.get_first_child():
            self.validation_list.remove(self.validation_list.get_first_child())
        
        if not self.current_template:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR, "template", "No template selected"
            ))
        else:
            for field_name in self.current_template.required_fields:
                self._validate_field(field_name)
            
            for field_name in self.current_template.optional_fields:
                if field_name in self.field_values and self.field_values[field_name]:
                    self._validate_field(field_name)
            
            self._validate_best_practices()
        
        self._display_validation_results()
        self.emit('validation-completed', self.validation_results)

    def _validate_field(self, field_name: str):
        field_def = self.field_definitions.get(field_name)
        if not field_def:
            return
        
        value = self.field_values.get(field_name, "").strip()
        
        if field_def.required and not value:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR, field_name, f"{field_def.display_name} is required"
            ))
            return
        
        if not value:
            return
        
        if field_def.validation_pattern:
            if not re.match(field_def.validation_pattern, value):
                self.validation_results.append(ValidationResult(
                    ValidationLevel.ERROR, field_name, 
                    f"Invalid format for {field_def.display_name}",
                    f"Expected pattern: {field_def.validation_pattern}"
                ))
        
        if field_name == "source" and value:
            valid_protocols = ["http://", "https://", "ftp://", "git+", "file://"]
            if not any(value.startswith(protocol) for protocol in valid_protocols):
                self.validation_results.append(ValidationResult(
                    ValidationLevel.WARNING, field_name,
                    "Source URL should use a standard protocol (http, https, ftp, git+)"
                ))
        
        if field_name == "pkgname" and value:
            if not re.match(r"^[a-z0-9][a-z0-9+._-]*$", value):
                self.validation_results.append(ValidationResult(
                    ValidationLevel.ERROR, field_name,
                    "Package name must be lowercase and contain only letters, numbers, +, ., _, -"
                ))

    def _validate_best_practices(self):
        maintainer = self.field_values.get("maintainer", "")
        if maintainer and "@" not in maintainer:
            self.validation_results.append(ValidationResult(
                ValidationLevel.WARNING, "maintainer",
                "Maintainer should include email address",
                "Format: Your Name <email@example.com>"
            ))
        
        pkgdesc = self.field_values.get("pkgdesc", "")
        if pkgdesc:
            if len(pkgdesc) > 80:
                self.validation_results.append(ValidationResult(
                    ValidationLevel.WARNING, "pkgdesc",
                    "Package description should be under 80 characters"
                ))
            if pkgdesc.lower().startswith(("a ", "an ", "the ")):
                self.validation_results.append(ValidationResult(
                    ValidationLevel.INFO, "pkgdesc",
                    "Package description should not start with articles (a, an, the)"
                ))
        
        url = self.field_values.get("url", "")
        if url and not (url.startswith("http://") or url.startswith("https://")):
            self.validation_results.append(ValidationResult(
                ValidationLevel.WARNING, "url",
                "Homepage URL should use http:// or https:// protocol"
            ))

    def _display_validation_results(self):
        if not self.validation_results:
            row = Adw.ActionRow()
            row.set_title("All validations passed")
            row.set_subtitle("PKGBUILD is ready to create")
            icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
            icon.add_css_class("success")
            row.add_prefix(icon)
            self.validation_list.append(row)
            return
        
        error_count = sum(1 for r in self.validation_results if r.level == ValidationLevel.ERROR)
        warning_count = sum(1 for r in self.validation_results if r.level == ValidationLevel.WARNING)
        info_count = sum(1 for r in self.validation_results if r.level == ValidationLevel.INFO)
        
        summary_row = Adw.ActionRow()
        summary_row.set_title(f"Validation Summary: {error_count} errors, {warning_count} warnings, {info_count} info")
        self.validation_list.append(summary_row)
        
        for result in self.validation_results:
            row = Adw.ActionRow()
            row.set_title(result.message)
            row.set_subtitle(f"Field: {result.field}")
            
            if result.suggestion:
                row.set_subtitle(f"Field: {result.field} • Suggestion: {result.suggestion}")
            
            if result.level == ValidationLevel.ERROR:
                icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic")
                row.add_css_class("error")
            elif result.level == ValidationLevel.WARNING:
                icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
                row.add_css_class("warning")
            else:
                icon = Gtk.Image.new_from_icon_name("dialog-information-symbolic")
                row.add_css_class("info")
            
            row.add_prefix(icon)
            self.validation_list.append(row)

    def _update_preview(self):
        if not self.current_template:
            return
        
        self._collect_all_field_values()
        
        template_content = self.current_template.template
        
        for field_name, value in self.field_values.items():
            placeholder = "{" + field_name + "}"
            if placeholder in template_content:
                template_content = template_content.replace(placeholder, str(value))
        
        remaining_placeholders = re.findall(r'\{([^}]+)\}', template_content)
        for placeholder in remaining_placeholders:
            if placeholder not in self.field_values or not self.field_values[placeholder]:
                template_content = template_content.replace("{" + placeholder + "}", f"# TODO: {placeholder}")
        
        buffer = self.preview_text.get_buffer()
        buffer.set_text(template_content)

    def _collect_all_field_values(self):
        all_field_containers = [self.basic_fields, self.dep_fields, self.build_fields, self.function_fields]
        
        for container in all_field_containers:
            for field_name, widget in container.items():
                if isinstance(widget, Gtk.Entry):
                    self.field_values[field_name] = widget.get_text()
                elif isinstance(widget, Adw.ComboRow):
                    model = widget.get_model()
                    selected = widget.get_selected()
                    if model and selected != Gtk.INVALID_LIST_POSITION:
                        self.field_values[field_name] = model.get_string(selected)
                elif isinstance(widget, Gtk.TextBuffer):
                    start = widget.get_start_iter()
                    end = widget.get_end_iter()
                    self.field_values[field_name] = widget.get_text(start, end, False)

    def _on_finish(self, button):
        self._validate_all_fields()
        
        has_errors = any(result.level == ValidationLevel.ERROR for result in self.validation_results)
        if has_errors:
            self._show_error("Validation Errors", "Please fix the validation errors before creating the PKGBUILD.")
            return
        
        self._collect_all_field_values()
        pkgbuild_content = self.preview_text.get_buffer().get_text(
            self.preview_text.get_buffer().get_start_iter(),
            self.preview_text.get_buffer().get_end_iter(),
            False
        )
        
        file_dialog = Gtk.FileDialog()
        file_dialog.set_title("Save PKGBUILD")
        file_dialog.set_initial_name("PKGBUILD")
        
        if self.initial_path:
            initial_folder = Gio.File.new_for_path(os.path.dirname(self.initial_path))
            file_dialog.set_initial_folder(initial_folder)
        
        file_dialog.save(self, None, self._on_file_save_complete, pkgbuild_content)

    def _on_file_save_complete(self, dialog, result, pkgbuild_content):
        try:
            file = dialog.save_finish(result)
            if file:
                file_path = file.get_path()
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(pkgbuild_content)
                
                self.emit('pkgbuild-created', file_path, pkgbuild_content)
                self._show_info("PKGBUILD Created", f"PKGBUILD saved successfully to {file_path}")
                self.close()
        except Exception as e:
            if not isinstance(e, GLib.Error):
                self._show_error("Save Failed", f"Could not save PKGBUILD: {str(e)}")

    def _on_cancel(self, button):
        self.emit('builder-closed')
        self.close()

    def _on_save_template(self, button):
        if not self.current_template:
            self._show_error("No Template", "Please complete the wizard first.")
            return
        
        self._collect_all_field_values()
        
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Save Template",
            body="Enter a name for this template:"
        )
        
        entry = Gtk.Entry()
        entry.set_placeholder_text("My Custom Template")
        dialog.set_extra_child(entry)
        
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        
        dialog.connect("response", self._on_save_template_response, entry)
        dialog.present()

    def _on_save_template_response(self, dialog, response, entry):
        if response == "save":
            template_name = entry.get_text().strip()
            if template_name:
                self._save_custom_template(template_name)
        dialog.destroy()

    def _save_custom_template(self, name):
        config_dir = os.path.expanduser("~/.config/paru-gui/templates")
        os.makedirs(config_dir, exist_ok=True)
        
        template_data = {
            "name": name,
            "type": self.current_template.type.value,
            "template": self.current_template.template,
            "field_values": self.field_values,
            "created": datetime.now().isoformat()
        }
        
        file_path = os.path.join(config_dir, f"{name.lower().replace(' ', '_')}.json")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(template_data, f, indent=2, ensure_ascii=False)
            self._show_info("Template Saved", f"Template '{name}' saved successfully.")
        except Exception as e:
            self._show_error("Save Failed", f"Could not save template: {str(e)}")

    def _show_help(self, button):
        help_dialog = Adw.MessageDialog(
            transient_for=self,
            heading="PKGBUILD Builder Help",
            body="""This wizard helps you create PKGBUILD files for Arch Linux packages.

Steps:
1. Choose a template that matches your package type
2. Fill in basic package information
3. Specify dependencies and relationships
4. Configure build sources and checksums
5. Customize build functions if needed
6. Review and create the PKGBUILD

Tips:
• Required fields are marked with *
• Use the validation results to fix issues
• Templates provide sensible defaults
• Auto-save keeps your progress safe"""
        )
        help_dialog.add_response("ok", "OK")
        help_dialog.present()

    def _show_error(self, heading, body):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=heading,
            body=body
        )
        dialog.add_response("ok", "OK")
        dialog.present()

    def _show_info(self, heading, body):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=heading,
            body=body
        )
        dialog.add_response("ok", "OK")
        dialog.present()

    def _on_auto_save_toggled(self, switch, state):
        self.auto_save_enabled = state
        if state:
            self._setup_auto_save()
        else:
            self._stop_auto_save()

    def _setup_auto_save(self):
        if self.auto_save_enabled:
            self._stop_auto_save()
            self.auto_save_timer = GLib.timeout_add_seconds(30, self._auto_save)

    def _stop_auto_save(self):
        if self.auto_save_timer:
            GLib.source_remove(self.auto_save_timer)
            self.auto_save_timer = None

    def _trigger_auto_save(self):
        if self.auto_save_enabled:
            self._setup_auto_save()

    def _auto_save(self):
        if self.current_template and self.field_values:
            self._save_progress()
        return True

    def _save_progress(self):
        config_dir = os.path.expanduser("~/.config/paru-gui")
        os.makedirs(config_dir, exist_ok=True)
        
        progress_data = {
            "template_type": self.current_template.type.value if self.current_template else None,
            "field_values": self.field_values,
            "current_page": self.current_page,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            with open(os.path.join(config_dir, "builder_progress.json"), 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _load_progress(self):
        config_file = os.path.expanduser("~/.config/paru-gui/builder_progress.json")
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if "template_type" in data and data["template_type"]:
                    template_type = PKGBUILDType(data["template_type"])
                    if template_type in self.templates:
                        self.current_template = self.templates[template_type]
                
                if "field_values" in data:
                    self.field_values = data["field_values"]
                
                if "current_page" in data:
                    self.current_page = min(data["current_page"], len(self.nav_buttons) - 1)
        except Exception:
            pass

    def _load_user_preferences(self):
        self._load_progress()

    def close(self):
        self._stop_auto_save()
        super().close()
