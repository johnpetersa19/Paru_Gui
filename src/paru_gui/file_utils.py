from gi.repository import Gtk, GObject, Adw, Pango, Gio, Gdk
from typing import Optional, List, Dict, Any, Callable, Tuple
import os
from enum import Enum

class ViewMode(Enum):
    GRID = "grid"
    LIST = "list"
    DETAILS = "details"

class SortMode(Enum):
    NAME = "name"
    TYPE = "type"
    SIZE = "size"
    MODIFIED = "modified"

class FileItem:
    def __init__(self, name: str, path: str, is_dir: bool = False,
                 file_type: str = "UNKNOWN", size: int = 0, modified_time: float = 0.0):
        self.name = name
        self.path = path
        self.is_dir = is_dir
        self.file_type = file_type
        self.size = size
        self.modified_time = modified_time

    def get_icon_name(self) -> str:
        """Retorna nome do ícone de forma segura, usando ícones mais básicos"""
        if self.is_dir:
            return "folder"  # Remove o "-symbolic" problemático

        # Ícones mais básicos e compatíveis - sem "-symbolic"
        icon_map = {
            "PKGBUILD": "text-x-generic",           # Em vez de text-x-script-symbolic
            "PACKAGE": "package-x-generic",         # Remove -symbolic
            "PATCH": "text-x-generic",              # Em vez de text-x-patch-symbolic
            "ADVANCED": "text-x-generic"            # Mantém genérico
        }
        return icon_map.get(self.file_type, "text-x-generic")

def safe_load_icon(icon_name: str, size: int = 48) -> Gtk.Image:
    """Carrega ícone de forma segura com fallback para evitar erros de GdkPixbuf"""
    try:
        # Primeiro, verifica se o ícone existe no tema atual
        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())

        if theme.has_icon(icon_name):
            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(size)
            return icon
        else:
            print(f"⚠️  Ícone '{icon_name}' não encontrado, usando fallback")
            # Tenta ícones de fallback básicos
            fallback_icons = ["text-x-generic", "application-x-executable", "text-plain"]
            for fallback in fallback_icons:
                if theme.has_icon(fallback):
                    icon = Gtk.Image.new_from_icon_name(fallback)
                    icon.set_pixel_size(size)
                    return icon

            # Último recurso: ícone vazio
            return Gtk.Image()

    except Exception as e:
        print(f"❌ Erro ao carregar ícone '{icon_name}': {e}")
        # Cria um ícone vazio como último recurso
        empty_icon = Gtk.Image()
        empty_icon.set_pixel_size(size)
        return empty_icon

@Gtk.Template(resource_path="/org/gnome/paru-gui/ui/screens/content_view.ui")
class ContentView(Gtk.Box):
    __gtype_name__ = "ContentView"

    toolbar = Gtk.Template.Child()
    path_label = Gtk.Template.Child()
    view_mode_buttons = Gtk.Template.Child()
    grid_view_button = Gtk.Template.Child()
    list_view_button = Gtk.Template.Child()
    sort_button = Gtk.Template.Child()
    main_stack = Gtk.Template.Child()
    grid_scrolled = Gtk.Template.Child()
    content_flowbox = Gtk.Template.Child()
    list_scrolled = Gtk.Template.Child()
    content_listbox = Gtk.Template.Child()
    status_bar = Gtk.Template.Child()
    items_count_label = Gtk.Template.Child()
    selection_info_label = Gtk.Template.Child()
    action_bar = Gtk.Template.Child()
    back_button = Gtk.Template.Child()
    refresh_button = Gtk.Template.Child()
    action_button = Gtk.Template.Child()

    __gsignals__ = {
        'item-selected': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'item-activated': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'back-requested': (GObject.SignalFlags.RUN_LAST, None, ()),
        'refresh-requested': (GObject.SignalFlags.RUN_LAST, None, ()),
        'action-requested': (GObject.SignalFlags.RUN_LAST, None, (str, object)),
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_path: Optional[str] = None
        self._all_items: List[FileItem] = []
        self._filtered_items: List[FileItem] = []
        self._selected_items: List[FileItem] = []
        self._view_mode = ViewMode.GRID
        self._sort_mode = SortMode.NAME
        self._sort_ascending = True
        self._filter_text = ""
        self._loading = False

        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(0)
        self._connect_signals()
        self._setup_interface()

    def _connect_signals(self):
        self.grid_view_button.connect("clicked", lambda btn: self.set_view_mode(ViewMode.GRID))
        self.list_view_button.connect("clicked", lambda btn: self.set_view_mode(ViewMode.LIST))
        self.back_button.connect("clicked", self._on_back_clicked)
        self.refresh_button.connect("clicked", self._on_refresh_clicked)
        self.action_button.connect("clicked", self._on_action_clicked)
        self.content_flowbox.connect("child-activated", self._on_flowbox_item_activated)
        self.content_flowbox.connect("selected-children-changed", self._on_flowbox_selection_changed)
        self.content_listbox.connect("row-activated", self._on_listbox_item_activated)
        self.content_listbox.connect("selected-rows-changed", self._on_listbox_selection_changed)

    def _setup_interface(self):
        self.content_flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        self.content_flowbox.set_activate_on_single_click(True)
        self.content_flowbox.set_max_children_per_line(4)
        self.content_flowbox.set_min_children_per_line(2)
        self.content_flowbox.set_row_spacing(12)
        self.content_flowbox.set_column_spacing(12)

        self.content_listbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        self.content_listbox.set_activate_on_single_click(True)

        self.main_stack.set_visible_child_name("grid")
        self._update_view_mode_buttons()
        self._setup_sort_menu()

    def _setup_sort_menu(self):
        menu = Gio.Menu()

        sort_section = Gio.Menu()
        sort_section.append("Name", "content.sort-by-name")
        sort_section.append("Type", "content.sort-by-type")
        sort_section.append("Size", "content.sort-by-size")
        sort_section.append("Modified", "content.sort-by-modified")
        menu.append_section("Sort by", sort_section)

        direction_section = Gio.Menu()
        direction_section.append("Ascending", "content.sort-ascending")
        direction_section.append("Descending", "content.sort-descending")
        menu.append_section("Direction", direction_section)

        self.sort_button.set_menu_model(menu)
        self._create_sort_actions()

    def _create_sort_actions(self):
        actions = {
            'sort-by-name': lambda a, p: self.set_sort_mode(SortMode.NAME),
            'sort-by-type': lambda a, p: self.set_sort_mode(SortMode.TYPE),
            'sort-by-size': lambda a, p: self.set_sort_mode(SortMode.SIZE),
            'sort-by-modified': lambda a, p: self.set_sort_mode(SortMode.MODIFIED),
            'sort-ascending': lambda a, p: self.set_sort_direction(True),
            'sort-descending': lambda a, p: self.set_sort_direction(False),
        }

        action_group = Gio.SimpleActionGroup()
        for name, callback in actions.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect('activate', callback)
            action_group.add_action(action)

        self.insert_action_group('content', action_group)

    def load_content(self, path: str, items: Optional[List[FileItem]] = None):
        self._current_path = path
        self.path_label.set_label(path)
        self.path_label.set_tooltip_text(path)

        if items is not None:
            self._all_items = items
        else:
            self._all_items = self._scan_directory(path)

        self._apply_filters_and_sort()
        self._update_display()

    def set_view_mode(self, mode: ViewMode):
        if self._view_mode != mode:
            self._view_mode = mode
            self._update_view_mode_buttons()

            if mode == ViewMode.GRID:
                self.main_stack.set_visible_child_name("grid")
            elif mode == ViewMode.LIST:
                self.main_stack.set_visible_child_name("list")

            self._update_display()

    def set_sort_mode(self, mode: SortMode):
        if self._sort_mode != mode:
            self._sort_mode = mode
            self._apply_filters_and_sort()
            self._update_display()

    def set_sort_direction(self, ascending: bool):
        if self._sort_ascending != ascending:
            self._sort_ascending = ascending
            self._apply_filters_and_sort()
            self._update_display()

    def set_filter(self, filter_text: str):
        if self._filter_text != filter_text:
            self._filter_text = filter_text
            self._apply_filters_and_sort()
            self._update_display()

    def refresh_content(self):
        if self._current_path:
            self.load_content(self._current_path)

    def get_selected_items(self) -> List[FileItem]:
        return self._selected_items.copy()

    def clear_selection(self):
        if self._view_mode == ViewMode.GRID:
            self.content_flowbox.unselect_all()
        else:
            for i in range(len(self._filtered_items)):
                row = self.content_listbox.get_row_at_index(i)
                if row:
                    self.content_listbox.unselect_row(row)

    def select_all(self):
        if self._view_mode == ViewMode.GRID:
            self.content_flowbox.select_all()
        else:
            for i in range(len(self._filtered_items)):
                row = self.content_listbox.get_row_at_index(i)
                if row:
                    self.content_listbox.select_row(row)

    def _scan_directory(self, path: str) -> List[FileItem]:
        items = []

        if not os.path.exists(path) or not os.path.isdir(path):
            return items

        try:
            for entry in os.listdir(path):
                entry_path = os.path.join(path, entry)
                is_dir = os.path.isdir(entry_path)

                file_type = "UNKNOWN"
                if not is_dir:
                    if entry == "PKGBUILD":
                        file_type = "PKGBUILD"
                    elif entry.endswith(".pkg.tar.zst"):
                        file_type = "PACKAGE"
                    elif entry.endswith((".patch", ".diff")):
                        file_type = "PATCH"
                    else:
                        file_type = "ADVANCED"

                try:
                    stat = os.stat(entry_path)
                    size = stat.st_size
                    modified = stat.st_mtime
                except OSError:
                    size = 0
                    modified = 0.0

                items.append(FileItem(entry, entry_path, is_dir, file_type, size, modified))

        except PermissionError:
            pass

        return items

    def _apply_filters_and_sort(self):
        if self._filter_text:
            self._filtered_items = [
                item for item in self._all_items
                if self._filter_text.lower() in item.name.lower()
            ]
        else:
            self._filtered_items = self._all_items.copy()

        self._sort_items()

    def _sort_items(self):
        def sort_key(item: FileItem):
            if self._sort_mode == SortMode.NAME:
                return item.name.lower()
            elif self._sort_mode == SortMode.TYPE:
                return (0 if item.is_dir else 1, item.file_type, item.name.lower())
            elif self._sort_mode == SortMode.SIZE:
                return (0 if item.is_dir else item.size, item.name.lower())
            elif self._sort_mode == SortMode.MODIFIED:
                return (item.modified_time, item.name.lower())
            return item.name.lower()

        self._filtered_items.sort(key=sort_key, reverse=not self._sort_ascending)

    def _update_display(self):
        if self._view_mode == ViewMode.GRID:
            self._update_grid_view()
        else:
            self._update_list_view()

        self._update_status_bar()

    def _update_grid_view(self):
        while self.content_flowbox.get_first_child():
            self.content_flowbox.remove(self.content_flowbox.get_first_child())

        for item in self._filtered_items:
            card = self._create_grid_card(item)
            if card:
                self.content_flowbox.append(card)

    def _update_list_view(self):
        while self.content_listbox.get_first_child():
            self.content_listbox.remove(self.content_listbox.get_first_child())

        for item in self._filtered_items:
            row = self._create_list_row(item)
            if row:
                self.content_listbox.append(row)

    def _create_grid_card(self, item: FileItem) -> Optional[Gtk.FlowBoxChild]:
        child = Gtk.FlowBoxChild()

        frame = Gtk.Frame()
        frame.add_css_class("card")
        frame.add_css_class("content-card")
        frame.set_size_request(200, 160)

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_start=12, margin_end=12,
            margin_top=12, margin_bottom=12
        )

        # ✅ CORREÇÃO APLICADA: Usar carregamento seguro de ícones
        icon = safe_load_icon(item.get_icon_name(), 48)

        name_label = Gtk.Label(
            label=item.name,
            wrap=True,
            max_width_chars=20,
            ellipsize=Pango.EllipsizeMode.END
        )
        name_label.add_css_class("heading")

        if item.is_dir:
            info_text = "Directory"
        else:
            info_text = f"{item.file_type} • {self._format_size(item.size)}"

        info_label = Gtk.Label(
            label=info_text,
            wrap=True,
            max_width_chars=25
        )
        info_label.add_css_class("caption")
        info_label.add_css_class("dim-label")

        box.append(icon)
        box.append(name_label)
        box.append(info_label)

        frame.set_child(box)
        frame.set_tooltip_text(item.path)

        child.set_child(frame)
        return child

    def _create_list_row(self, item: FileItem) -> Optional[Gtk.ListBoxRow]:
        row = Gtk.ListBoxRow()

        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_start=12, margin_end=12,
            margin_top=8, margin_bottom=8
        )

        # ✅ CORREÇÃO APLICADA: Usar carregamento seguro de ícones
        icon = safe_load_icon(item.get_icon_name(), 32)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_hexpand(True)

        name_label = Gtk.Label(label=item.name, halign=Gtk.Align.START)
        name_label.add_css_class("heading")

        details_text = f"{item.file_type}" if not item.is_dir else "Directory"
        details_label = Gtk.Label(label=details_text, halign=Gtk.Align.START)
        details_label.add_css_class("caption")
        details_label.add_css_class("dim-label")

        info_box.append(name_label)
        info_box.append(details_label)

        size_label = Gtk.Label(
            label=self._format_size(item.size) if not item.is_dir else "",
            halign=Gtk.Align.END
        )
        size_label.add_css_class("caption")
        size_label.add_css_class("dim-label")

        box.append(icon)
        box.append(info_box)
        box.append(size_label)

        row.set_child(box)
        row.set_tooltip_text(item.path)

        return row

    def _format_size(self, size: int) -> str:
        if size == 0:
            return "0 B"
        elif size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"

    def _update_view_mode_buttons(self):
        self.grid_view_button.remove_css_class("suggested-action")
        self.list_view_button.remove_css_class("suggested-action")

        if self._view_mode == ViewMode.GRID:
            self.grid_view_button.add_css_class("suggested-action")
        else:
            self.list_view_button.add_css_class("suggested-action")

    def _update_status_bar(self):
        total_items = len(self._all_items)
        filtered_items = len(self._filtered_items)
        selected_items = len(self._selected_items)

        if self._filter_text and filtered_items != total_items:
            count_text = f"{filtered_items} of {total_items} items"
        else:
            count_text = f"{total_items} item{'s' if total_items != 1 else ''}"

        self.items_count_label.set_label(count_text)

        if selected_items > 0:
            selection_text = f"{selected_items} selected"
            self.selection_info_label.set_label(selection_text)
            self.selection_info_label.set_visible(True)
        else:
            self.selection_info_label.set_visible(False)

    def _on_back_clicked(self, button: Gtk.Button):
        self.emit("back-requested")

    def _on_refresh_clicked(self, button: Gtk.Button):
        self.emit("refresh-requested")

    def _on_action_clicked(self, button: Gtk.Button):
        self.emit("action-requested", "default", self._selected_items)

    def _on_flowbox_item_activated(self, flowbox: Gtk.FlowBox, child: Gtk.FlowBoxChild):
        """Callback para quando um item é ativado no grid view"""
        try:
            # Encontra o índice do item baseado no child
            index = -1
            current_child = flowbox.get_first_child()
            current_index = 0

            while current_child:
                if current_child == child:
                    index = current_index
                    break
                current_child = current_child.get_next_sibling()
                current_index += 1

            if 0 <= index < len(self._filtered_items):
                item = self._filtered_items[index]
                self.emit("item-activated", item)
                print(f"🖱️  Item ativado: {item.name}")

        except Exception as e:
            print(f"❌ Erro ao processar ativação do item: {e}")

    def _on_flowbox_selection_changed(self, flowbox: Gtk.FlowBox):
        """Callback para mudanças de seleção no grid view"""
        try:
            # Atualiza lista de itens selecionados
            self._selected_items.clear()
            selected_children = flowbox.get_selected_children()

            for child in selected_children:
                # Encontra o índice do item baseado no child
                current_child = flowbox.get_first_child()
                current_index = 0

                while current_child:
                    if current_child == child:
                        if 0 <= current_index < len(self._filtered_items):
                            item = self._filtered_items[current_index]
                            self._selected_items.append(item)
                            self.emit("item-selected", item)
                        break
                    current_child = current_child.get_next_sibling()
                    current_index += 1

            self._update_status_bar()
            print(f"📋 Seleção atualizada: {len(self._selected_items)} itens")

        except Exception as e:
            print(f"❌ Erro ao processar mudança de seleção: {e}")

    def _on_listbox_item_activated(self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow):
        """Callback para quando um item é ativado no list view"""
        try:
            index = row.get_index()
            if 0 <= index < len(self._filtered_items):
                item = self._filtered_items[index]
                self.emit("item-activated", item)
                print(f"🖱️  Item ativado: {item.name}")

        except Exception as e:
            print(f"❌ Erro ao processar ativação do item: {e}")

    def _on_listbox_selection_changed(self, listbox: Gtk.ListBox):
        """Callback para mudanças de seleção no list view"""
        try:
            # Atualiza lista de itens selecionados
            self._selected_items.clear()
            selected_rows = listbox.get_selected_rows()

            for row in selected_rows:
                index = row.get_index()
                if 0 <= index < len(self._filtered_items):
                    item = self._filtered_items[index]
                    self._selected_items.append(item)
                    self.emit("item-selected", item)

            self._update_status_bar()
            print(f"📋 Seleção atualizada: {len(self._selected_items)} itens")

        except Exception as e:
            print(f"❌ Erro ao processar mudança de seleção: {e}")
