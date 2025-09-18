import os
import subprocess
import logging
import shlex
import threading # Still useful for managing potential cancellation events for the external terminal
import time
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Callable
import concurrent.futures # For ThreadPoolExecutor, if still using for background tasks

from gi.repository import Gtk, GLib # Gtk.TextBuffer, GLib.idle_add, Pango for attributes

# Basic logging configuration for this module
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("terminal_manager")

# No longer needed as output goes to system terminal
# class LogLevel(Enum):
#     MINIMUM = "min"
#     STANDARD = "std"
#     MAXIMUM = "max"

class TerminalManager:
    """
    Manages the execution of commands in the system's default terminal.
    It encapsulates logic for determining the user's preferred terminal,
    launching commands within it, and managing the visibility of the GUI's
    internal terminal control panel.
    """

    DEFAULT_TERMINAL_EMULATORS = ["gnome-terminal", "konsole", "xterm", "alacritty", "kitty", "terminator"]

    def __init__(self,
                 terminal_area_box: Gtk.Box, # The parent box containing the terminal controls
                 preferences_manager: Optional[Any] = None # For GSettings for preferred terminal
                ):

        self.terminal_area_box = terminal_area_box
        self.preferences_manager = preferences_manager

        self._find_default_terminal_emulator()
        self._connect_ui_signals() # Connects Hide/Show buttons
        self._load_preferences() # Load visibility preference

        logger.info(f"TerminalManager initialized. Default emulator: {self.system_terminal_emulator}")

    def _find_default_terminal_emulator(self):
        """
        Attempts to find the user's preferred terminal emulator.
        Checks XDG_TERMINAL_EMULATOR, then common emulators in PATH.
        """
        # Try XDG_TERMINAL_EMULATOR (if set by desktop environment)
        xdg_terminal = os.environ.get('XDG_TERMINAL_EMULATOR')
        if xdg_terminal and self._is_command_available(xdg_terminal):
            self.system_terminal_emulator = xdg_terminal
            logger.debug(f"Using XDG_TERMINAL_EMULATOR: {self.system_terminal_emulator}")
            return

        # Try common desktop-specific defaults
        desktop_session = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        if 'gnome' in desktop_session and self._is_command_available('gnome-terminal'):
            self.system_terminal_emulator = 'gnome-terminal'
        elif 'kde' in desktop_session and self._is_command_available('konsole'):
            self.system_terminal_emulator = 'konsole'
        elif self._is_command_available('alacritty'):
            self.system_terminal_emulator = 'alacritty'
        elif self._is_command_available('kitty'):
            self.system_terminal_emulator = 'kitty'
        elif self._is_command_available('terminator'):
            self.system_terminal_emulator = 'terminator'
        elif self._is_command_available('xterm'):
            self.system_terminal_emulator = 'xterm'
        else:
            # Fallback to the first available from a general list
            for term in self.DEFAULT_TERMINAL_EMULATORS:
                if self._is_command_available(term):
                    self.system_terminal_emulator = term
                    break
            else:
                self.system_terminal_emulator = 'xterm' # Absolute fallback
                logger.warning("No preferred terminal emulator found, falling back to 'xterm'.")

        logger.debug(f"Determined system terminal emulator: {self.system_terminal_emulator}")


    def _is_command_available(self, command: str) -> bool:
        """Checks if a command is available in the system's PATH."""
        return shutil.which(command) is not None # Using shutil.which for robust path checking

    def _connect_ui_signals(self):
        """Connects signals from UI widgets to manager methods."""
        # Assuming these buttons are obtained from the builder in window.py
        # and passed to TerminalManager init.
        # For this simplified version, we only need the hide/show functionality
        # controlled by the main window, not intricate terminal controls.
        pass # UI interactions are now handled directly by window.py and simple callbacks

    def _load_preferences(self):
        """Loads terminal preferences from GSettings (or PreferencesManager)."""
        if self.preferences_manager:
            # Assume a preference for initial visibility
            self.terminal_area_box.set_visible(self.preferences_manager.get_show_realtime_terminal())
            logger.debug(f"Terminal panel visibility loaded: {self.terminal_area_box.get_visible()}")
        else:
            logger.warning("PreferencesManager not provided. Using default terminal panel visibility (hidden).")
            self.terminal_area_box.set_visible(False) # Default to hidden if no preferences manager

    def show_terminal_panel(self):
        """Makes the GUI's terminal control panel visible."""
        self.terminal_area_box.set_visible(True)
        logger.debug("Terminal panel made visible.")
        if self.preferences_manager:
            self.preferences_manager.set_show_realtime_terminal(True)

    def hide_terminal_panel(self):
        """Hides the GUI's terminal control panel."""
        self.terminal_area_box.set_visible(False)
        logger.debug("Terminal panel hidden.")
        if self.preferences_manager:
            self.preferences_manager.set_show_realtime_terminal(False)

    def execute_command_in_system_terminal(self,
                                           command: List[str],
                                           cwd: Optional[str] = None,
                                           is_sandboxed: bool = False,
                                           sandbox_options: Optional[Any] = None # Expects SandboxOptions from sandboxing.py
                                          ) -> subprocess.Popen:
        """
        [ ] Launch commands in the system's standard terminal.
        Launches a command in the system's default terminal emulator.

        Args:
            command: The command and its arguments as a list of strings.
            cwd: The working directory for the command.
            is_sandboxed: True if the command should be executed within a sandbox.
            sandbox_options: SandboxOptions object if `is_sandboxed` is True.

        Returns:
            The Popen object of the launched terminal process.
        """
        full_command_str = " ".join(shlex.quote(arg) for arg in command)

        # Build the command to run INSIDE the terminal
        # This differs per terminal emulator. Often, `--command` or `-e` is used.
        terminal_cmd_args: List[str] = []
        if self.system_terminal_emulator == 'gnome-terminal':
            terminal_cmd_args.extend(['--', 'bash', '-c', f'{full_command_str}; exec bash']) # `exec bash` keeps terminal open
        elif self.system_terminal_emulator == 'konsole':
            terminal_cmd_args.extend(['-e', 'bash', '-c', f'{full_command_str}; exec bash'])
        elif self.system_terminal_emulator == 'alacritty':
            terminal_cmd_args.extend(['-e', 'bash', '-c', f'{full_command_str}; read -p "Press Enter to close..."']) # Keep open until user input
        elif self.system_terminal_emulator == 'kitty':
             terminal_cmd_args.extend(['bash', '-c', f'{full_command_str}; exec bash'])
        elif self.system_terminal_emulator == 'terminator':
            terminal_cmd_args.extend(['-e', 'bash', '-c', f'{full_command_str}; exec bash'])
        elif self.system_terminal_emulator == 'xterm':
            terminal_cmd_args.extend(['-e', 'bash', '-c', f'{full_command_str}; read -p "Press Enter to close..."'])
        else: # Generic fallback, might not keep open
            terminal_cmd_args.extend(['bash', '-c', f'{full_command_str}'])
            logger.warning(f"Using generic command invocation for {self.system_terminal_emulator}. Terminal might close immediately.")

        # Prepend the sandboxing command if needed
        if is_sandboxed:
            if not sandbox_options:
                logger.error("Sandboxed execution requested but no SandboxOptions provided.")
                # Fallback to non-sandboxed or error
                GLib.idle_add(lambda: self.append_output("Error: Sandboxing requested but no options provided. Running non-sandboxed.\n", "error"))
            else:
                from .sandboxing import SandboxManager # Import here to avoid circular dependency on init
                sandbox_mgr = SandboxManager()
                # _build_bwrap_args returns the bwrap command and its arguments up to '--'.
                bwrap_cmd_prefix = ['bwrap'] + sandbox_mgr._build_bwrap_args(sandbox_options) + ['--']

                # The command passed to the terminal is now the bwrap command
                # This makes the terminal launch bwrap, which then launches the actual command.
                final_command_for_terminal = bwrap_cmd_prefix + terminal_cmd_args # This is slightly tricky.
                                                                                # The `bash -c` is part of `terminal_cmd_args`
                                                                                # but needs to execute `bwrap ... -- bash -c "..."`
                                                                                # So the actual command passed to `bwrap` is `bash -c "..."`
                                                                                # Let's rebuild more robustly:

                # The actual command to be executed by bwrap
                bwrap_exec_cmd = ['bash', '-c', f'{full_command_str}; read -p "Press Enter to close sandboxed shell..."'] # Keep sandbox shell open
                full_bwrap_command = ['bwrap'] + sandbox_mgr._build_bwrap_args(sandbox_options) + ['--'] + bwrap_exec_cmd

                # Now, the terminal emulator needs to run this full_bwrap_command
                if self.system_terminal_emulator == 'gnome-terminal':
                    launch_cmd = [self.system_terminal_emulator, '--', *full_bwrap_command]
                elif self.system_terminal_emulator == 'konsole':
                    launch_cmd = [self.system_terminal_emulator, '-e', *full_bwrap_command]
                elif self.system_terminal_emulator == 'alacritty':
                    launch_cmd = [self.system_terminal_emulator, '-e', *full_bwrap_command]
                elif self.system_terminal_emulator == 'kitty':
                    launch_cmd = [self.system_terminal_emulator, *full_bwrap_command] # Kitty has flexible arg handling
                else: # Generic
                    launch_cmd = [self.system_terminal_emulator, '-e', shlex.join(full_bwrap_command)] # xterm / general expects a single string for -e

                logger.info(f"Launching sandboxed command in system terminal: {' '.join(shlex.quote(arg) for arg in launch_cmd)}")
                return subprocess.Popen(launch_cmd, cwd=cwd)

        # Non-sandboxed execution
        launch_cmd = [self.system_terminal_emulator] + terminal_cmd_args
        logger.info(f"Launching non-sandboxed command in system terminal: {' '.join(shlex.quote(arg) for arg in launch_cmd)}")
        return subprocess.Popen(launch_cmd, cwd=cwd)

    # The streaming logic for appending output to GtkTextView is now REMOVED.
    # The responsibility is entirely on the external terminal.
    # The `append_output` method is now a simplified internal logger/notifier.
    def append_output(self, line: str, stream_type: str = "stdout", tag_name: Optional[str] = None):
        """
        This version of append_output acts as an internal logger/notifier
        since actual output goes to the system terminal.
        """
        log_method = logger.info
        if stream_type == "error": log_method = logger.error
        elif stream_type == "warning": log_method = logger.warning
        elif stream_type == "command": log_method = logger.debug
        log_method(f"[GUI Log] {stream_type.upper()}: {line.strip()}")
        # You could also add a temporary Toast or similar for critical messages here.
        # Adw.Toast.new(line[:100]).set_title(stream_type.upper()).set_timeout(2).set_priority(Adw.ToastPriority.HIGH)


    # The following methods related to internal terminal state are also removed
    # as the content is no longer managed by this class directly.
    # def _autoscroll_to_end(self): pass
    # def clear_terminal_output(self, *args): pass
    # def _on_autoscroll_toggled(self, toggle_button: Gtk.ToggleButton): pass
    # def _on_detail_level_changed(self, combo_box: Gtk.ComboBoxText): pass


# Example Usage (for testing this module directly)
if __name__ == "__main__":
    # Ensure gi is initialized for Gtk/GLib
    try:
        import gi
        gi.require_version('Gtk', '4.0')
        gi.require_version('Adw', '1') # Often Adw is used with Gtk4
        from gi.repository import Adw
        import shutil # For shutil.which
    except ValueError as e:
        print(f"GI requirements not met for testing: {e}")
        print("Please ensure you have pygobject installed and GTK/Adwaita libraries are available.")
        print("Skipping direct test of TerminalManager due to GI environment.")
        exit(1)

    class MockPreferencesManager:
        """A simple mock for PreferencesManager for testing."""
        def get_show_realtime_terminal(self): return True
        def set_show_realtime_terminal(self, value): pass
        # Add a mock for get_default_terminal_emulator if you want to set a preference
        # def get_default_terminal_emulator(self): return "konsole"

    class TestTerminalApp(Adw.Application):
        def __init__(self):
            super().__init__(application_id='org.gnome.paru-gui.terminal-test')
            self.window: Optional[Adw.ApplicationWindow] = None
            self.terminal_manager: Optional[TerminalManager] = None
            self.preferences_manager = MockPreferencesManager()
            self.current_ext_terminal_process: Optional[subprocess.Popen] = None # To keep track

        def do_activate(self):
            if not self.window:
                self.window = Adw.ApplicationWindow(application=self, title="Terminal Manager Test")
                self.window.set_default_size(500, 300)

                main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=10, margin_bottom=10, margin_start=10, margin_end=10)
                self.window.set_child(main_box)

                # Command input
                cmd_entry = Gtk.Entry(placeholder_text="Enter command (e.g., ls -l /; sleep 2; echo 'Done')")
                main_box.append(cmd_entry)

                # Execute button
                execute_button = Gtk.Button(label="Execute Command in System Terminal")
                main_box.append(execute_button)
                execute_button.connect("clicked", self.on_execute_command, cmd_entry)

                # Execute Sandboxed button
                execute_sandboxed_button = Gtk.Button(label="Execute Sandboxed Command (requires bwrap)", css_classes=['suggested-action'])
                main_box.append(execute_sandboxed_button)
                execute_sandboxed_button.connect("clicked", self.on_execute_sandboxed_command, cmd_entry)

                # Hide/Show Panel buttons
                hide_show_box = Gtk.Box(spacing=5)
                show_panel_button = Gtk.Button(label="Show Terminal Panel")
                hide_panel_button = Gtk.Button(label="Close Terminal Panel") # Renamed from Hide

                hide_show_box.append(show_panel_button)
                hide_show_box.append(hide_panel_button)
                main_box.append(hide_show_box)


                # Terminal Control Panel (this is the Gtk.Box that gets hidden/shown)
                # It will only contain the hide button for this example,
                # as other controls (autoscroll, clear, filters) are no longer managed here.
                terminal_area_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, margin_top=10)
                terminal_area_box.add_css_class("terminal-box") # For visual styling
                terminal_area_box.set_hexpand(True)
                terminal_area_box.set_vexpand(True) # Allow it to expand if visible

                terminal_panel_label = Gtk.Label(label="System Terminal Panel Controls", hexpand=True, halign=Gtk.Align.START, css_classes=['heading'])
                terminal_area_box.append(terminal_panel_label)
                terminal_area_box.append(Gtk.Label(label="Commands will launch in your default system terminal."))

                main_box.append(terminal_area_box)

                self.terminal_manager = TerminalManager(
                    terminal_area_box,
                    self.preferences_manager
                )

                # Connect buttons for showing/hiding the panel
                show_panel_button.connect("clicked", lambda btn: self.terminal_manager.show_terminal_panel())
                hide_panel_button.connect("clicked", lambda btn: self.terminal_manager.hide_terminal_panel())

                self.window.present()

        def on_execute_command(self, button: Gtk.Button, cmd_entry: Gtk.Entry):
            command_str = cmd_entry.get_text().strip()
            if not command_str: return

            cmd_list = shlex.split(command_str)
            self.terminal_manager.execute_command_in_system_terminal(cmd_list, cwd=os.path.expanduser("~"))
            cmd_entry.set_text("")

        def on_execute_sandboxed_command(self, button: Gtk.Button, cmd_entry: Gtk.Entry):
            command_str = cmd_entry.get_text().strip()
            if not command_str: return

            cmd_list = shlex.split(command_str)

            # Mock SandboxOptions
            from .sandboxing import SandboxOptions, IsolationLevel # Import here for test
            sandbox_opts = SandboxOptions(
                isolation_level=IsolationLevel.MEDIUM,
                allow_network=False, # Network access usually restricted in sandbox
                allow_home=False, # Home access usually restricted
                working_dir="/tmp" # Sandbox working dir
            )

            self.terminal_manager.execute_command_in_system_terminal(
                cmd_list,
                cwd="/tmp", # Set cwd for external terminal
                is_sandboxed=True,
                sandbox_options=sandbox_opts
            )
            cmd_entry.set_text("")

    app = TestTerminalApp()
    sys.exit(app.run(sys.argv))
