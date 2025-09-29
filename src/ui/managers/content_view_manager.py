import os
from typing import Optional, List
from gi.repository import Gtk, Gdk

from ...file_utils import FileItem
from ...preferences_manager import PreferencesManager

class ContentViewManager:
    def __init__(self, window, content_cards, preferences_manager, security_analyzer):
        self.window = window
        self.content_cards = content_cards
        self.preferences_manager = preferences_manager
        self.security_analyzer = security_analyzer

    def update_content_view(self, file_items: List[FileItem], folder_path: str,
                           initial_selection_path: Optional[str] = None):
        content_view_widget = self.window.builder.get_object('content_view')

        terminal_area_box = self.window.builder.get_object('terminal_area', content_view_widget)
        if terminal_area_box and hasattr(self.window, 'terminal_manager'):
            self.window.terminal_manager.terminal_area_box = terminal_area_box
            self.window.terminal_manager._load_preferences()

        content_cards = self.content_cards
        current_path_label = self.window.builder.get_object('current_path_label', content_view_widget)
        file_count_label = self.window.builder.get_object('file_count_label', content_view_widget)
        up_button = self.window.builder.get_object('up_button', content_view_widget)

        if current_path_label:
            current_path_label.set_label(folder_path)
            current_path_label.set_tooltip_text(folder_path)
        if file_count_label:
            file_count_label.set_label(f"{len(file_items)} files found")

        if up_button and not hasattr(up_button, '_connected_up_button'):
            up_button.connect('clicked', self._on_up_button_clicked)
            up_button._connected_up_button = True

        if not content_cards:
            print("Content cards FlowBox not found in UI.")
            return

        while content_cards.get_first_child() is not None:
            content_cards.remove(content_cards.get_first_child())

        displayable_file_items = [item for item in file_items if not item.is_dir]

        if not displayable_file_items:
            self._create_empty_state_card(content_cards, folder_path)
        else:
            for item in file_items:
                if item.is_dir:
                    self._create_directory_card(content_cards, item)

            for item in file_items:
                if not item.is_dir:
                    if (item.file_type == 'ADVANCED' and
                        self.preferences_manager.get_simplified_mode()):
                        continue

                    self._create_file_card(content_cards, item)

        if initial_selection_path:
            self._select_initial_item(content_cards, initial_selection_path)

        self.window.ui_manager.show_content_view()

    def _create_empty_state_card(self, content_cards, folder_path):
        empty_state_instance = Gtk.Builder.get_template(
            self.window.__class__, 'empty_card_template'
        ).new_with_values([])

        if not empty_state_instance:
            print("Empty state box template not found in UI.")
            return

        empty_state_box = empty_state_instance
        empty_state_box.set_visible(True)

        title_label = self.window.builder.get_object('heading', empty_state_box)
        desc_label = self.window.builder.get_object('label', empty_state_box)
        download_button = self.window.builder.get_object('download_button', empty_state_box)

        if title_label:
            title_label.set_label("Empty Directory")
        if desc_label:
            desc_label.set_label(f"No compatible files found in '{os.path.basename(folder_path)}'.")
        if download_button:
            if hasattr(download_button, '_connected_empty_state_download'):
                download_button.disconnect_by_func(self._on_empty_state_download_pkgbuild_clicked)
            download_button.connect('clicked', self._on_empty_state_download_pkgbuild_clicked)
            download_button._connected_empty_state_download = True

        flowbox_child = Gtk.FlowBoxChild()
        flowbox_child.set_child(empty_state_box)
        content_cards.append(flowbox_child)

    def _create_directory_card(self, content_cards, item: FileItem):
        card_frame = Gtk.Frame()
        card_frame.add_css_class("card")
        card_frame.add_css_class("file-card")
        card_frame.set_size_request(220, 180)

        card_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_start=12,
            margin_end=12,
            margin_top=12,
            margin_bottom=12
        )
        card_frame.set_child(card_box)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        card_box.append(header_box)

        icon = Gtk.Image.new_from_icon_name("folder-symbolic")
        icon.set_pixel_size(32)
        header_box.append(icon)

        title_label = Gtk.Label()
        title_label.set_text(item.name)
        title_label.set_ellipsize(3)
        title_label.set_halign(Gtk.Align.START)
        title_label.add_css_class("heading")
        header_box.append(title_label)

        description_label = Gtk.Label()
        description_label.set_text("Directory")
        description_label.set_halign(Gtk.Align.START)
        description_label.add_css_class("dim-label")
        card_box.append(description_label)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.set_halign(Gtk.Align.END)
        card_box.append(button_box)

        open_button = Gtk.Button.new_with_label("Open")
        open_button.add_css_class("suggested-action")
        open_button.connect('clicked', self._on_directory_open_clicked, item)
        button_box.append(open_button)

        flowbox_child = Gtk.FlowBoxChild()
        flowbox_child.set_child(card_frame)
        content_cards.append(flowbox_child)

    def _create_file_card(self, content_cards, item: FileItem):
        card_frame = Gtk.Frame()
        card_frame.add_css_class("card")
        card_frame.add_css_class("file-card")
        card_frame.set_size_request(220, 180)

        card_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_start=12,
            margin_end=12,
            margin_top=12,
            margin_bottom=12
        )
        card_frame.set_child(card_box)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        card_box.append(header_box)

        icon_name = self._get_file_icon(item)
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(32)
        header_box.append(icon)

        title_label = Gtk.Label()
        title_label.set_text(item.name)
        title_label.set_ellipsize(3)
        title_label.set_halign(Gtk.Align.START)
        title_label.add_css_class("heading")
        header_box.append(title_label)

        type_label = Gtk.Label()
        type_label.set_text(self._get_file_type_description(item.file_type))
        type_label.set_halign(Gtk.Align.START)
        type_label.add_css_class("dim-label")
        card_box.append(type_label)

        if hasattr(item, 'security_status') and item.security_status:
            security_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            security_box.set_halign(Gtk.Align.START)

            security_icon = Gtk.Image.new_from_icon_name(self._get_security_icon(item.security_status))
            security_icon.set_pixel_size(16)
            security_box.append(security_icon)

            security_label = Gtk.Label()
            security_label.set_text(item.security_status.title())
            security_label.add_css_class("caption")
            security_box.append(security_label)

            card_box.append(security_box)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.set_halign(Gtk.Align.END)
        card_box.append(button_box)

        if item.file_type == 'PKGBUILD':
            review_button = Gtk.Button.new_with_label("Review")
            review_button.add_css_class("suggested-action")
            review_button.connect('clicked', self._on_file_review_clicked, item)
            button_box.append(review_button)
        else:
            edit_button = Gtk.Button.new_with_label("Edit")
            edit_button.connect('clicked', self._on_file_edit_clicked, item)
            button_box.append(edit_button)

        flowbox_child = Gtk.FlowBoxChild()
        flowbox_child.set_child(card_frame)
        content_cards.append(flowbox_child)

    def _get_file_icon(self, item: FileItem) -> str:
        if item.file_type == 'PKGBUILD':
            return "package-x-generic-symbolic"
        elif item.file_type == 'SRCINFO':
            return "text-x-generic-symbolic"
        elif item.file_type == 'INSTALL':
            return "application-x-executable-symbolic"
        elif item.file_type == 'PATCH':
            return "text-x-patch-symbolic"
        elif item.file_type == 'SOURCE':
            return "folder-download-symbolic"
        elif item.file_type == 'CONFIG':
            return "preferences-system-symbolic"
        else:
            return "text-x-generic-symbolic"

    def _get_file_type_description(self, file_type: str) -> str:
        descriptions = {
            'PKGBUILD': 'Package Build Script',
            'SRCINFO': 'Source Information',
            'INSTALL': 'Installation Script',
            'PATCH': 'Patch File',
            'SOURCE': 'Source File',
            'CONFIG': 'Configuration File',
            'ADVANCED': 'Advanced File',
            'UNKNOWN': 'Unknown File'
        }
        return descriptions.get(file_type, 'Unknown File')

    def _get_security_icon(self, security_status: str) -> str:
        if security_status.lower() == 'safe':
            return "security-high-symbolic"
        elif security_status.lower() == 'warning':
            return "security-medium-symbolic"
        elif security_status.lower() == 'danger':
            return "security-low-symbolic"
        else:
            return "dialog-question-symbolic"

    def _select_initial_item(self, content_cards, initial_selection_path: str):
        for child in content_cards:
            if isinstance(child, Gtk.FlowBoxChild):
                card_widget = child.get_child()
                if hasattr(card_widget, 'file_item'):
                    if card_widget.file_item.path == initial_selection_path:
                        content_cards.select_child(child)
                        break

    def _on_up_button_clicked(self, button):
        if hasattr(self.window, 'file_operations'):
            current_path = self.window.file_operations.current_directory
            if current_path:
                parent_path = os.path.dirname(current_path)
                if parent_path != current_path:
                    self.window.file_operations.scan_directory(parent_path)

    def _on_empty_state_download_pkgbuild_clicked(self, button):
        if hasattr(self.window, 'action_handlers'):
            self.window.action_handlers.handle_download_pkgbuild()

    def _on_directory_open_clicked(self, button, item: FileItem):
        if hasattr(self.window, 'file_operations'):
            self.window.file_operations.scan_directory(item.path)

    def _on_file_review_clicked(self, button, item: FileItem):
        if hasattr(self.window, 'action_handlers'):
            self.window.action_handlers.handle_file_review(item)

    def _on_file_edit_clicked(self, button, item: FileItem):
        if hasattr(self.window, 'action_handlers'):
            self.window.action_handlers.handle_file_edit(item)

    def clear_content_view(self):
        if self.content_cards:
            while self.content_cards.get_first_child() is not None:
                self.content_cards.remove(self.content_cards.get_first_child())

    def get_selected_items(self) -> List[FileItem]:
        selected_items = []
        if not self.content_cards:
            return selected_items

        for child in self.content_cards.get_selected_children():
            if isinstance(child, Gtk.FlowBoxChild):
                card_widget = child.get_child()
                if hasattr(card_widget, 'file_item'):
                    selected_items.append(card_widget.file_item)

        return selected_items

    def refresh_content_view(self):
        if hasattr(self.window, 'file_operations'):
            current_path = self.window.file_operations.current_directory
            if current_path:
                self.window.file_operations.scan_directory(current_path)

    def update_security_indicators(self, file_items: List[FileItem]):
        if not self.content_cards or not self.security_analyzer:
            return

        for child in self.content_cards:
            if isinstance(child, Gtk.FlowBoxChild):
                card_widget = child.get_child()
                if hasattr(card_widget, 'file_item'):
                    item = card_widget.file_item
                    for updated_item in file_items:
                        if updated_item.path == item.path:
                            if hasattr(updated_item, 'security_status'):
                                self._update_card_security_indicator(card_widget, updated_item.security_status)
                            break

    def _update_card_security_indicator(self, card_widget, security_status: str):
        pass
