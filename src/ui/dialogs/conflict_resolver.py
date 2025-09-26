import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GObject, Gio, GLib
import difflib
import subprocess
import os
import tempfile
from typing import Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

class ConflictResolution(Enum):
    KEEP_ORIGINAL = "original"
    ACCEPT_NEW = "new"
    MERGE_MANUAL = "merge"
    CANCELLED = "cancelled"

@dataclass
class FileConflict:
    original_path: str
    new_path: str
    original_content: str
    new_content: str
    conflict_type: str
    description: str

class DiffView(Gtk.TextView):
    def __init__(self):
        super().__init__()
        self.set_editable(False)
        self.set_cursor_visible(False)
        self.add_css_class("monospace")
        
        buffer = self.get_buffer()
        buffer.create_tag("added_line", foreground="#4E9A06", background="#D8F5A2")
        buffer.create_tag("removed_line", foreground="#A40000", background="#F7DDDD")
        buffer.create_tag("header_line", weight=700, foreground="#2E3436")
        buffer.create_tag("context_line", foreground="#555753")
        buffer.create_tag("line_number", foreground="#888A85", size_points=8)

    def show_diff(self, diff_text: str):
        buffer = self.get_buffer()
        buffer.set_text("")
        
        lines = diff_text.split('\n')
        for line in lines:
            iter_end = buffer.get_end_iter()
            
            if line.startswith('+++') or line.startswith('---') or line.startswith('@@'):
                buffer.insert_with_tags_by_name(iter_end, line + '\n', "header_line")
            elif line.startswith('+'):
                buffer.insert_with_tags_by_name(iter_end, line + '\n', "added_line")
            elif line.startswith('-'):
                buffer.insert_with_tags_by_name(iter_end, line + '\n', "removed_line")
            else:
                buffer.insert_with_tags_by_name(iter_end, line + '\n', "context_line")

    def generate_diff(self, original_content: str, new_content: str, original_name: str = "Original", new_name: str = "New") -> str:
        original_lines = original_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=original_name,
            tofile=new_name,
            lineterm=''
        )
        
        return '\n'.join(diff)

class ConflictResolverDialog(Adw.Window):
    __gsignals__ = {
        'resolved': (GObject.SignalFlags.RUN_LAST, None, (str, str)),
        'merge-requested': (GObject.SignalFlags.RUN_LAST, None, (str, str)),
    }

    def __init__(self, parent: Optional[Gtk.Window], conflict: FileConflict):
        super().__init__(transient_for=parent, modal=True)
        self.set_title("File Conflict Resolver")
        self.set_default_size(900, 700)
        
        self.conflict = conflict
        self.resolution = ConflictResolution.CANCELLED
        self.merged_content = ""
        
        self._setup_ui()
        self._setup_actions()
        self._load_content()

    def _setup_ui(self):
        headerbar = Adw.HeaderBar()
        self.set_titlebar(headerbar)
        
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(12)
        
        info_group = Adw.PreferencesGroup()
        info_group.set_title("Conflict Information")
        info_group.set_description(f"File conflict detected: {self.conflict.description}")
        
        file_info_row = Adw.ActionRow()
        file_info_row.set_title("Conflicting File")
        file_info_row.set_subtitle(self.conflict.original_path)
        info_group.add(file_info_row)
        
        main_box.append(info_group)
        
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(450)
        paned.set_vexpand(True)
        
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        original_label = Gtk.Label(label="Original File")
        original_label.add_css_class("heading")
        original_label.set_halign(Gtk.Align.START)
        left_box.append(original_label)
        
        self.original_view = Gtk.TextView()
        self.original_view.set_editable(False)
        self.original_view.add_css_class("monospace")
        original_scroll = Gtk.ScrolledWindow()
        original_scroll.set_child(self.original_view)
        original_scroll.set_vexpand(True)
        left_box.append(original_scroll)
        
        new_label = Gtk.Label(label="New File")
        new_label.add_css_class("heading")
        new_label.set_halign(Gtk.Align.START)
        right_box.append(new_label)
        
        self.new_view = Gtk.TextView()
        self.new_view.set_editable(False)
        self.new_view.add_css_class("monospace")
        new_scroll = Gtk.ScrolledWindow()
        new_scroll.set_child(self.new_view)
        new_scroll.set_vexpand(True)
        right_box.append(new_scroll)
        
        paned.set_start_child(left_box)
        paned.set_end_child(right_box)
        main_box.append(paned)
        
        diff_group = Adw.PreferencesGroup()
        diff_group.set_title("Differences")
        
        diff_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        self.diff_view = DiffView()
        diff_scroll = Gtk.ScrolledWindow()
        diff_scroll.set_child(self.diff_view)
        diff_scroll.set_min_content_height(200)
        diff_box.append(diff_scroll)
        
        diff_group.set_child(diff_box)
        main_box.append(diff_group)
        
        actions_group = Adw.PreferencesGroup()
        actions_group.set_title("Resolution Actions")
        
        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        actions_box.set_halign(Gtk.Align.CENTER)
        actions_box.set_margin_top(12)
        actions_box.set_margin_bottom(12)
        
        self.keep_mine_btn = Gtk.Button(label="Keep Original")
        self.keep_mine_btn.add_css_class("pill")
        self.keep_mine_btn.add_css_class("suggested-action")
        
        self.accept_theirs_btn = Gtk.Button(label="Accept New")
        self.accept_theirs_btn.add_css_class("pill")
        
        self.merge_btn = Gtk.Button(label="Manual Merge")
        self.merge_btn.add_css_class("pill")
        self.merge_btn.add_css_class("destructive-action")
        
        self.cancel_btn = Gtk.Button(label="Cancel")
        self.cancel_btn.add_css_class("pill")
        
        actions_box.append(self.keep_mine_btn)
        actions_box.append(self.accept_theirs_btn)
        actions_box.append(self.merge_btn)
        actions_box.append(self.cancel_btn)
        
        actions_group.set_child(actions_box)
        main_box.append(actions_group)
        
        self.set_content(main_box)

    def _setup_actions(self):
        self.keep_mine_btn.connect("clicked", self._on_keep_original)
        self.accept_theirs_btn.connect("clicked", self._on_accept_new)
        self.merge_btn.connect("clicked", self._on_manual_merge)
        self.cancel_btn.connect("clicked", self._on_cancel)

    def _load_content(self):
        original_buffer = self.original_view.get_buffer()
        original_buffer.set_text(self.conflict.original_content)
        
        new_buffer = self.new_view.get_buffer()
        new_buffer.set_text(self.conflict.new_content)
        
        diff_text = self.diff_view.generate_diff(
            self.conflict.original_content,
            self.conflict.new_content,
            "Original",
            "New"
        )
        self.diff_view.show_diff(diff_text)

    def _on_keep_original(self, button: Gtk.Button):
        self.resolution = ConflictResolution.KEEP_ORIGINAL
        self.emit("resolved", ConflictResolution.KEEP_ORIGINAL.value, self.conflict.original_content)
        self.close()

    def _on_accept_new(self, button: Gtk.Button):
        self.resolution = ConflictResolution.ACCEPT_NEW
        self.emit("resolved", ConflictResolution.ACCEPT_NEW.value, self.conflict.new_content)
        self.close()

    def _on_manual_merge(self, button: Gtk.Button):
        self.resolution = ConflictResolution.MERGE_MANUAL
        self._launch_merge_tool()

    def _on_cancel(self, button: Gtk.Button):
        self.resolution = ConflictResolution.CANCELLED
        self.close()

    def _launch_merge_tool(self):
        try:
            merge_tools = [
                "meld",
                "kdiff3", 
                "vimdiff",
                "code --wait --diff",
                "gedit"
            ]
            
            available_tool = None
            for tool in merge_tools:
                tool_cmd = tool.split()[0]
                if self._is_command_available(tool_cmd):
                    available_tool = tool
                    break
            
            if not available_tool:
                self._show_error_dialog("No suitable merge tool found", 
                                       "Please install meld, kdiff3, or another diff/merge tool.")
                return
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='_original.txt', delete=False) as orig_file:
                orig_file.write(self.conflict.original_content)
                orig_path = orig_file.name
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='_new.txt', delete=False) as new_file:
                new_file.write(self.conflict.new_content)
                new_path = new_file.name
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='_merged.txt', delete=False) as merged_file:
                merged_file.write(self.conflict.original_content)
                merged_path = merged_file.name
            
            if available_tool == "meld":
                cmd = ["meld", orig_path, merged_path, new_path]
            elif available_tool == "kdiff3":
                cmd = ["kdiff3", orig_path, new_path, "-o", merged_path]
            elif available_tool == "vimdiff":
                cmd = ["vimdiff", "-d", orig_path, merged_path, new_path]
            else:
                cmd = available_tool.split() + [orig_path, new_path]
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            self._monitor_merge_process(process, orig_path, new_path, merged_path)
            
        except Exception as e:
            self._show_error_dialog("Merge Tool Error", f"Failed to launch merge tool: {str(e)}")

    def _is_command_available(self, command: str) -> bool:
        try:
            subprocess.run(["which", command], capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def _monitor_merge_process(self, process: subprocess.Popen, orig_path: str, new_path: str, merged_path: str):
        def check_process():
            if process.poll() is None:
                return GLib.SOURCE_CONTINUE
            
            try:
                if os.path.exists(merged_path):
                    with open(merged_path, 'r') as f:
                        self.merged_content = f.read()
                    self.emit("resolved", ConflictResolution.MERGE_MANUAL.value, self.merged_content)
                else:
                    self.emit("resolved", ConflictResolution.CANCELLED.value, "")
            except Exception as e:
                self._show_error_dialog("Merge Read Error", f"Failed to read merged content: {str(e)}")
            finally:
                self._cleanup_temp_files(orig_path, new_path, merged_path)
                self.close()
            
            return GLib.SOURCE_REMOVE
        
        GLib.timeout_add(1000, check_process)

    def _cleanup_temp_files(self, *file_paths):
        for path in file_paths:
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except OSError:
                pass

    def _show_error_dialog(self, title: str, message: str):
        dialog = Adw.MessageDialog(transient_for=self, heading=title, body=message)
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.present()

    def get_resolution(self) -> ConflictResolution:
        return self.resolution

    def get_resolved_content(self) -> str:
        if self.resolution == ConflictResolution.KEEP_ORIGINAL:
            return self.conflict.original_content
        elif self.resolution == ConflictResolution.ACCEPT_NEW:
            return self.conflict.new_content
        elif self.resolution == ConflictResolution.MERGE_MANUAL:
            return self.merged_content
        else:
            return ""

class ConflictManager(GObject.Object):
    __gsignals__ = {
        'conflict-detected': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'conflict-resolved': (GObject.SignalFlags.RUN_LAST, None, (str, str)),
        'all-conflicts-resolved': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self.pending_conflicts = []
        self.resolved_conflicts = []

    def detect_file_conflict(self, original_path: str, new_path: str, conflict_type: str = "file_overwrite") -> Optional[FileConflict]:
        try:
            if not os.path.exists(original_path):
                return None
            
            with open(original_path, 'r', encoding='utf-8', errors='ignore') as f:
                original_content = f.read()
            
            with open(new_path, 'r', encoding='utf-8', errors='ignore') as f:
                new_content = f.read()
            
            if original_content == new_content:
                return None
            
            conflict = FileConflict(
                original_path=original_path,
                new_path=new_path,
                original_content=original_content,
                new_content=new_content,
                conflict_type=conflict_type,
                description=f"File '{os.path.basename(original_path)}' has been modified and conflicts with new version"
            )
            
            self.pending_conflicts.append(conflict)
            self.emit('conflict-detected', conflict)
            return conflict
            
        except Exception as e:
            return None

    def resolve_conflict_interactive(self, conflict: FileConflict, parent_window: Optional[Gtk.Window] = None):
        dialog = ConflictResolverDialog(parent_window, conflict)
        
        def on_resolved(dialog, resolution_type, content):
            self.resolved_conflicts.append({
                'conflict': conflict,
                'resolution': resolution_type,
                'content': content
            })
            
            if conflict in self.pending_conflicts:
                self.pending_conflicts.remove(conflict)
            
            self.emit('conflict-resolved', resolution_type, content)
            
            if not self.pending_conflicts:
                self.emit('all-conflicts-resolved')
        
        dialog.connect('resolved', on_resolved)
        dialog.present()

    def resolve_conflict_automatically(self, conflict: FileConflict, resolution: ConflictResolution) -> str:
        if resolution == ConflictResolution.KEEP_ORIGINAL:
            content = conflict.original_content
        elif resolution == ConflictResolution.ACCEPT_NEW:
            content = conflict.new_content
        else:
            content = conflict.original_content
        
        self.resolved_conflicts.append({
            'conflict': conflict,
            'resolution': resolution.value,
            'content': content
        })
        
        if conflict in self.pending_conflicts:
            self.pending_conflicts.remove(conflict)
        
        self.emit('conflict-resolved', resolution.value, content)
        
        if not self.pending_conflicts:
            self.emit('all-conflicts-resolved')
        
        return content

    def get_pending_conflicts(self) -> List[FileConflict]:
        return self.pending_conflicts.copy()

    def get_resolved_conflicts(self) -> List[dict]:
        return self.resolved_conflicts.copy()

    def has_pending_conflicts(self) -> bool:
        return len(self.pending_conflicts) > 0

    def clear_conflicts(self):
        self.pending_conflicts.clear()
        self.resolved_conflicts.clear()
