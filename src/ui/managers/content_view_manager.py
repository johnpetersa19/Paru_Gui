# src/ui/content_view_manager.py
#
# Copyright 2025 Unknown
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from typing import Optional, List
from gi.repository import Gtk, Gdk

from ...file_utils import FileItem
from ...preferences_manager import PreferencesManager


class ContentViewManager:
    """Manages the content view, card creation and population."""

    def __init__(self, window, builder, preferences_manager):
        self.window = window
        self.builder = builder
        self.preferences_manager = preferences_manager

    def update_content_view(self, file_items: List[FileItem], folder_path: str,
                           initial_selection_path: Optional[str] = None):
        """Populates the content view with scanned file items."""
        content_view_widget = self.builder.get_object('content_view')

        # Update terminal area if needed
        terminal_area_box = self.builder.get_object('terminal_area', content_view_widget)
        if terminal_area_box and hasattr(self.window, 'terminal_manager'):
            self.window.terminal_manager.terminal_area_box = terminal_area_box
            self.window.terminal_manager._load_preferences()

        # Get UI elements
        content_cards = self.builder.get_object('content_cards', content_view_widget)
        current_path_label = self.builder.get_object('current_path_label', content_view_widget)
        file_count_label = self.builder.get_object('file_count_label', content_view_widget)
        up_button = self.builder.get_object('up_button', content_view_widget)

        # Update labels
        if current_path_label:
            current_path_label.set_label(folder_path)
            current_path_label.set_tooltip_text(folder_path)
        if file_count_label:
            file_count_label.set_label(f"{len(file_items)} files found")

        # Connect up button
        if up_button and not hasattr(up_button, '_connected_up_button'):
            up_button.connect('clicked', self._on_up_button_clicked)
            up_button._connected_up_button = True

        if not content_cards:
            print("Content cards FlowBox not found in UI.")
            return

        # Clear existing cards
        while content_cards.get_first_child() is not None:
            content_cards.remove(content_cards.get_first_child())

        # Filter out directories for empty state condition
        displayable_file_items = [item for item in file_items if not item.is_dir]

        # Show empty state if no files found
        if not displayable_file_items:
            self._create_empty_state_card(content_cards, folder_path)
        else:
            # Add directory cards first
            for item in file_items:
                if item.is_dir:
                    self._create_directory_card(content_cards, item)

            # Add file cards
            for item in file_items:
                if not item.is_dir:
                    # Skip advanced card in simplified mode
                    if (item.file_type == 'ADVANCED' and
                        self.preferences_manager.get_simplified_mode()):
                        continue

                    self._create_file_card(content_cards, item)

        # Handle initial selection
        if initial_selection_path:
            self._select_initial_item(content_cards, initial_selection_path)

        self.window.ui_manager.show_content_view()

    def _create_empty_state_card(self, content_cards, folder_path):
        """Creates and adds empty state card."""
        empty_state_instance = Gtk.Builder.get_template(
            self.window.__class__, 'empty_card_template'
        ).new_with_values([])

        if not empty_state_instance:
            print("Empty state box template not found in UI.")
            return

        empty_state_box = empty_state_instance
        empty_state_box.set_visible(True)

        # Populate empty state content
        title_label = self.builder.get_object('heading', empty_state_box)
        desc_label = self.builder.get_object('label', empty_state_box)
        download_button = self.builder.get_object('download_button', empty_state_box)

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
        """Creates and adds a directory card."""
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

        icon = Gtk.Image.new_from_icon_name("folder-symbolic", Gtk.IconSize.LARGE)
        icon.set_pixel_size(48)

        name_label = Gtk.Label(label=item.name, wrap=True, max_width_chars=20)
        name_label.add_css_class("heading")

        path_label = Gtk.Label(
            label=f"Folder: {os.path.basename(item.path)}",
            wrap=True,
            max_width_chars=25
        )
        path_label.add_css_class("caption")
        path_label.add_css_class("dim-label")

        card_box.append(icon)
        card_box.append(name_label)
        card_box.append(path_label)
        card_frame.set_child(card_box)
        card_frame.set_tooltip_text(item.path)
        card_frame.set_cursor(Gdk.Cursor.new_from_name(self.window.get_display(), "pointer"))
        card_frame.add_css_class('interactive')

        # Add click handler
        gesture = Gtk.GestureClick.new()
        gesture.set_button(0)
        gesture.connect("released", self._on_card_activated_gesture, item)
        card_frame.add_controller(gesture)

        flowbox_child = Gtk.FlowBoxChild()
        flowbox_child.set_child(card_frame)
        content_cards.append(flowbox_child)

    def _create_file_card(self, content_cards, item: FileItem):
        """Creates and adds a file card."""
        # Get template from builder
        template_box = Gtk.Builder.get_template(
            self.window.__class__, f"{item.file_type.lower()}_card_template"
        ).new_with_values([])

        if not template_box:
            print(f"No card template found for {item.file_type.lower()}_card_template.")
            return

        # Create wrapper frame
        card_wrapper_frame = Gtk.Frame()
        card_wrapper_frame.add_css_class("card")
        card_wrapper_frame.add_css_class(f"{item.file_type.lower()}-card")
        card_wrapper_frame.set_size_request(220, 300)
        card_wrapper_frame.set_child(template_box)
        card_wrapper_frame.set_visible(True)
        card_wrapper_frame.set_tooltip_text(item.path)
        card_wrapper_frame.set_cursor(Gdk.Cursor.new_from_name(self.window.get_display(), "pointer"))
        card_wrapper_frame.add_css_class('interactive')

        # Add click handler
        gesture = Gtk.GestureClick.new()
        gesture.set_button(0)
        gesture.connect("released", self._on_card_activated_gesture, item)
        card_wrapper_frame.add_controller(gesture)

        # Populate card specific information
        self._populate_card_specific_info(template_box, item)

        # Connect card actions
        self._connect_card_actions(template_box, item)

        flowbox_child = Gtk.FlowBoxChild()
        flowbox_child.set_child(card_wrapper_frame)
        content_cards.append(flowbox_child)

    def _populate_card_specific_info(self, card_box: Gtk.Box, item: FileItem):
        """Populates card-specific information based on file type."""
        if item.file_type == 'PKGBUILD':
            self._populate_pkgbuild_card(card_box, item)
        elif item.file_type == 'PACKAGE':
            self._populate_package_card(card_box, item)
        elif item.file_type == 'PATCH':
            self._populate_patch_card(card_box, item)
        # ADVANCED cards typically don't need dynamic content

    def _populate_pkgbuild_card(self, card_box: Gtk.Box, item: FileItem):
        """Populates PKGBUILD card information."""
        icon_widget = self.builder.get_object('pkgbuild_icon', card_box)
        name_label = self.builder.get_object('pkgbuild_name', card_box)
        version_label = self.builder.get_object('pkgbuild_version', card_box)
        trust_icon = self.builder.get_object('trust_icon', card_box)
        trust_label = self.builder.get_object('trust_label', card_box)

        if icon_widget:
            icon_widget.set_from_icon_name(item.get_icon_name())
        if name_label:
            name_label.set_label(item.name)
        if version_label:
            version_label.set_label(f"Version: {item.version}")

        # Show trust indicators if enabled
        show_trust_icons = self.preferences_manager.get_show_trust_icons()
        if show_trust_icons and item.trust_level and trust_icon and trust_label:
            trust_icon.set_from_icon_name(item.get_trust_icon())
            trust_icon.set_visible(True)
            trust_label.set_label(item.trust_level.value)

            # Apply trust level styling
            trust_label.get_style_context().remove_class("success-color")
            trust_label.get_style_context().remove_class("warning-color")
            trust_label.get_style_context().remove_class("error-color")

            from ..file_utils import TrustLevel
            if item.trust_level == TrustLevel.HIGH:
                trust_label.get_style_context().add_class("success-color")
            elif item.trust_level == TrustLevel.MEDIUM:
                trust_label.get_style_context().add_class("warning-color")
            else:
                trust_label.get_style_context().add_class("error-color")
        else:
            if trust_icon:
                trust_icon.set_visible(False)
            if trust_label:
                trust_label.set_visible(False)

    def _populate_package_card(self, card_box: Gtk.Box, item: FileItem):
        """Populates package card information."""
        icon_widget = self.builder.get_object('package_icon', card_box)
        name_label = self.builder.get_object('package_name', card_box)
        version_label = self.builder.get_object('package_version', card_box)
        signature_icon = self.builder.get_object('signature_icon', card_box)
        signature_label = self.builder.get_object('signature_label', card_box)

        if icon_widget:
            icon_widget.set_from_icon_name(item.get_icon_name())
        if name_label:
            name_label.set_label(item.name)
        if version_label:
            version_label.set_label(f"Version: {item.version}")

        # Show signature status
        if signature_icon and signature_label:
            if item.signature_status == "Verified":
                signature_icon.set_from_icon_name("security-high-symbolic")
                signature_label.set_label("Verified")
                signature_label.get_style_context().add_class("success-color")
                signature_label.get_style_context().remove_class("error-color")
            else:
                signature_icon.set_from_icon_name("security-low-symbolic")
                signature_label.set_label("Not signed")
                signature_label.get_style_context().add_class("error-color")
                signature_label.get_style_context().remove_class("success-color")

    def _populate_patch_card(self, card_box: Gtk.Box, item: FileItem):
        """Populates patch card information."""
        icon_widget = self.builder.get_object('patch_icon', card_box)
        name_label = self.builder.get_object('patch_name', card_box)
        description_label = self.builder.get_object('patch_description', card_box)

        if icon_widget:
            icon_widget.set_from_icon_name(item.get_icon_name())
        if name_label:
            name_label.set_label(item.name)
        if description_label:
            description_label.set_label(item.extra_info or "Patch file with changes.")

    def _connect_card_actions(self, card_box: Gtk.Box, item: FileItem):
        """Connects action buttons on a card to their handlers."""
        if not hasattr(self.window, 'action_handlers'):
            return

        action_handlers = self.window.action_handlers

        if item.file_type == 'PKGBUILD':
            self._connect_pkgbuild_actions(card_box, item, action_handlers)
        elif item.file_type == 'PACKAGE':
            self._connect_package_actions(card_box, item, action_handlers)
        elif item.file_type == 'PATCH':
            self._connect_patch_actions(card_box, item, action_handlers)

    def _connect_pkgbuild_actions(self, card_box: Gtk.Box, item: FileItem, action_handlers):
        """Connects PKGBUILD card action buttons."""
        build_button = self.builder.get_object('build_button', card_box)
        edit_button = self.builder.get_object('edit_button', card_box)
        dependencies_button = self.builder.get_object('dependencies_button', card_box)
        sources_button = self.builder.get_object('sources_button', card_box)

        if build_button:
            build_button.connect('clicked', action_handlers.on_build_package, item.path)
        if edit_button:
            edit_button.connect('clicked', action_handlers.on_edit_pkgbuild, item.path)
        if dependencies_button:
            dependencies_button.connect('clicked', action_handlers.on_view_dependencies, item.path)
        if sources_button:
            sources_button.connect('clicked', action_handlers.on_download_sources, item.path)

    def _connect_package_actions(self, card_box: Gtk.Box, item: FileItem, action_handlers):
        """Connects package card action buttons."""
        install_button = self.builder.get_object('install_button', card_box)
        info_button = self.builder.get_object('info_button', card_box)
        verify_button = self.builder.get_object('verify_button', card_box)

        if install_button:
            install_button.connect('clicked', action_handlers.on_install_package, item.path)
        if info_button:
            info_button.connect('clicked', action_handlers.on_view_package_info, item.path)
        if verify_button:
            verify_button.connect('clicked', action_handlers.on_verify_signature, item.path)

    def _connect_patch_actions(self, card_box: Gtk.Box, item: FileItem, action_handlers):
        """Connects patch card action buttons."""
        apply_patch_button = self.builder.get_object('apply_patch_button', card_box)
        diff_button = self.builder.get_object('diff_button', card_box)

        if apply_patch_button:
            apply_patch_button.connect('clicked', action_handlers.on_apply_patch, item.path)
        if diff_button:
            diff_button.connect('clicked', action_handlers.on_view_diff, item.path)

    def _select_initial_item(self, content_cards, initial_selection_path):
        """Selects and scrolls to the initially selected item."""
        for child in content_cards:
            child_frame = child.get_child()
            if (isinstance(child_frame, Gtk.Frame) and
                child_frame.get_tooltip_text() == initial_selection_path):
                content_cards.select_child(child)
                break

    def _on_card_activated_gesture(self, gesture: Gtk.GestureClick, n_press: int,
                                  x: float, y: float, item: FileItem):
        """Processes item activation in flowbox."""
        if n_press == 1:  # Single click
            if item.is_dir:
                self.window.current_path = item.path
                if hasattr(self.window, 'file_operations'):
                    self.window.file_operations.start_scan_compatible_files_async(
                        self.window.current_path
                    )
            else:
                self._process_selected_item(item)

    def _process_selected_item(self, item: FileItem):
        """Process selection of a non-directory item."""
        # This would typically open a review dialog or perform default action
        # For now, just log the selection
        print(f"Selected item: {item.name} ({item.file_type})")

    def _on_up_button_clicked(self, button: Gtk.Button):
        """Handles up button click."""
        if hasattr(self.window, 'file_operations'):
            self.window.file_operations.on_up_button_clicked(button)

    def _on_empty_state_download_pkgbuild_clicked(self, button: Gtk.Button):
        """Handler for 'Download PKGBUILD' button on empty state card."""
        print("Empty State: Download PKGBUILD button clicked.")
        # Show info dialog or trigger download flow
        if hasattr(self.window, 'ui_manager'):
            self.window.ui_manager.show_info_dialog(
                "Download PKGBUILD",
                "Enter the AUR package name to download its PKGBUILD.",
                "system-search-symbolic"
            )
