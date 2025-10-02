import os
import subprocess
import shlex
import shutil
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Callable, Union
from gi.repository import Gtk, GLib
from pathlib import Path


class TerminalType(Enum):
    GNOME_TERMINAL = "gnome-terminal"
    KONSOLE = "konsole"
    XTERM = "xterm"
    ALACRITTY = "alacritty"
    KITTY = "kitty"
    TERMINATOR = "terminator"
    TILIX = "tilix"
    MATE_TERMINAL = "mate-terminal"
    XFCE_TERMINAL = "xfce4-terminal"


class ExecutionMode(Enum):
    NORMAL = "normal"
    SANDBOXED = "sandboxed"
    PERSISTENT = "persistent"
    DETACHED = "detached"


class TerminalManager:
    
    def __init__(self, terminal_area_box: Optional[Gtk.Box] = None, preferences_manager: Optional[Any] = None):
        self.terminal_area_box = terminal_area_box
        self.preferences_manager = preferences_manager
        self.system_terminal_emulator = None
        self.terminal_type = None
        
        self._running_processes: Dict[str, subprocess.Popen] = {}
        self._terminal_commands: Dict[TerminalType, Dict[str, List[str]]] = {}
        
        self._initialize_terminal_commands()
        self._detect_system_terminal()
        self._setup_ui_components()
        self._load_preferences()
    
    def _initialize_terminal_commands(self):
        self._terminal_commands = {
            TerminalType.GNOME_TERMINAL: {
                'execute': ['--', 'bash', '-c'],
                'title': ['--title'],
                'working_dir': ['--working-directory'],
                'hold': [],
                'new_window': ['--window'],
                'new_tab': ['--tab']
            },
            TerminalType.KONSOLE: {
                'execute': ['-e', 'bash', '-c'],
                'title': ['-p', 'tabtitle'],
                'working_dir': ['--workdir'],
                'hold': ['--hold'],
                'new_window': ['--new-window'],
                'new_tab': ['--new-tab']
            },
            TerminalType.XTERM: {
                'execute': ['-e', 'bash', '-c'],
                'title': ['-T'],
                'working_dir': ['-cd'],
                'hold': ['-hold'],
                'new_window': [],
                'new_tab': []
            },
            TerminalType.ALACRITTY: {
                'execute': ['-e', 'bash', '-c'],
                'title': ['-t'],
                'working_dir': ['--working-directory'],
                'hold': [],
                'new_window': ['--class'],
                'new_tab': []
            },
            TerminalType.KITTY: {
                'execute': ['bash', '-c'],
                'title': ['--title'],
                'working_dir': ['--directory'],
                'hold': [],
                'new_window': ['--new-window'],
                'new_tab': ['--new-tab']
            },
            TerminalType.TERMINATOR: {
                'execute': ['-e', 'bash', '-c'],
                'title': ['-T'],
                'working_dir': ['--working-directory'],
                'hold': ['-H'],
                'new_window': ['--new-window'],
                'new_tab': ['--new-tab']
            },
            TerminalType.TILIX: {
                'execute': ['-e', 'bash', '-c'],
                'title': ['-t'],
                'working_dir': ['--working-directory'],
                'hold': [],
                'new_window': ['--new-window'],
                'new_tab': ['--new-tab']
            },
            TerminalType.MATE_TERMINAL: {
                'execute': ['-e', 'bash', '-c'],
                'title': ['-t'],
                'working_dir': ['--working-directory'],
                'hold': [],
                'new_window': ['--window'],
                'new_tab': ['--tab']
            },
            TerminalType.XFCE_TERMINAL: {
                'execute': ['-e', 'bash', '-c'],
                'title': ['-T'],
                'working_dir': ['--working-directory'],
                'hold': ['--hold'],
                'new_window': ['--window'],
                'new_tab': ['--tab']
            }
        }
    
    def _detect_system_terminal(self):
        xdg_terminal = os.environ.get('XDG_TERMINAL_EMULATOR')
        if xdg_terminal and self._is_command_available(xdg_terminal):
            self.system_terminal_emulator = xdg_terminal
            self.terminal_type = self._get_terminal_type(xdg_terminal)
            return
        
        desktop_session = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        desktop_priorities = {
            'gnome': [TerminalType.GNOME_TERMINAL, TerminalType.TILIX],
            'kde': [TerminalType.KONSOLE],
            'xfce': [TerminalType.XFCE_TERMINAL, TerminalType.XTERM],
            'mate': [TerminalType.MATE_TERMINAL, TerminalType.XTERM],
            'unity': [TerminalType.GNOME_TERMINAL, TerminalType.XTERM]
        }
        
        for de_name, terminals in desktop_priorities.items():
            if de_name in desktop_session:
                for terminal_type in terminals:
                    if self._is_command_available(terminal_type.value):
                        self.system_terminal_emulator = terminal_type.value
                        self.terminal_type = terminal_type
                        return
        
        fallback_order = [
            TerminalType.ALACRITTY,
            TerminalType.KITTY,
            TerminalType.GNOME_TERMINAL,
            TerminalType.KONSOLE,
            TerminalType.TERMINATOR,
            TerminalType.TILIX,
            TerminalType.MATE_TERMINAL,
            TerminalType.XFCE_TERMINAL,
            TerminalType.XTERM
        ]
        
        for terminal_type in fallback_order:
            if self._is_command_available(terminal_type.value):
                self.system_terminal_emulator = terminal_type.value
                self.terminal_type = terminal_type
                return
        
        self.system_terminal_emulator = 'xterm'
        self.terminal_type = TerminalType.XTERM
    
    def _get_terminal_type(self, terminal_name: str) -> TerminalType:
        for terminal_type in TerminalType:
            if terminal_type.value in terminal_name:
                return terminal_type
        return TerminalType.XTERM
    
    def _is_command_available(self, command: str) -> bool:
        return shutil.which(command) is not None
    
    def _setup_ui_components(self):
        if self.terminal_area_box:
            self.terminal_area_box.set_visible(False)
    
    def _load_preferences(self):
        if self.preferences_manager:
            show_terminal = self.preferences_manager.get_preference("show_terminal_panel", False)
            if self.terminal_area_box:
                self.terminal_area_box.set_visible(show_terminal)
    
    def get_available_terminals(self) -> List[str]:
        available = []
        for terminal_type in TerminalType:
            if self._is_command_available(terminal_type.value):
                available.append(terminal_type.value)
        return available
    
    def set_preferred_terminal(self, terminal_name: str) -> bool:
        if self._is_command_available(terminal_name):
            self.system_terminal_emulator = terminal_name
            self.terminal_type = self._get_terminal_type(terminal_name)
            if self.preferences_manager:
                self.preferences_manager.set_preference("preferred_terminal", terminal_name)
            return True
        return False
    
    def show_terminal_panel(self):
        if self.terminal_area_box:
            self.terminal_area_box.set_visible(True)
            if self.preferences_manager:
                self.preferences_manager.set_preference("show_terminal_panel", True)
    
    def hide_terminal_panel(self):
        if self.terminal_area_box:
            self.terminal_area_box.set_visible(False)
            if self.preferences_manager:
                self.preferences_manager.set_preference("show_terminal_panel", False)
    
    def toggle_terminal_panel(self):
        if self.terminal_area_box:
            visible = self.terminal_area_box.get_visible()
            if visible:
                self.hide_terminal_panel()
            else:
                self.show_terminal_panel()
    
    def is_terminal_panel_visible(self) -> bool:
        if self.terminal_area_box:
            return self.terminal_area_box.get_visible()
        return False
    
    def execute_command(self, command: Union[str, List[str]], 
                       working_dir: Optional[str] = None,
                       title: Optional[str] = None,
                       hold_open: bool = True,
                       mode: ExecutionMode = ExecutionMode.NORMAL,
                       new_window: bool = False,
                       env_vars: Optional[Dict[str, str]] = None) -> Optional[subprocess.Popen]:
        
        if isinstance(command, str):
            command_list = shlex.split(command)
        else:
            command_list = command[:]
        
        if not command_list:
            return None
        
        try:
            terminal_cmd = self._build_terminal_command(
                command_list, working_dir, title, hold_open, new_window
            )
            
            env = os.environ.copy()
            if env_vars:
                env.update(env_vars)
            
            process = subprocess.Popen(
                terminal_cmd,
                cwd=working_dir,
                env=env,
                start_new_session=True
            )
            
            process_id = f"{title or 'terminal'}_{process.pid}"
            self._running_processes[process_id] = process
            
            return process
            
        except Exception as e:
            return None
    
    def execute_sandboxed_command(self, command: Union[str, List[str]],
                                 working_dir: Optional[str] = None,
                                 title: Optional[str] = None,
                                 sandbox_options: Optional[Any] = None) -> Optional[subprocess.Popen]:
        
        if isinstance(command, str):
            command_list = shlex.split(command)
        else:
            command_list = command[:]
        
        if not sandbox_options:
            return self.execute_command(command, working_dir, title)
        
        try:
            from ..paru_gui.sandboxing import SandboxManager
            
            sandbox_manager = SandboxManager()
            bwrap_args = sandbox_manager._build_bwrap_args(sandbox_options)
            
            sandboxed_command = ['bwrap'] + bwrap_args + ['--'] + command_list
            
            return self.execute_command(
                sandboxed_command,
                working_dir,
                title or "Sandboxed Command",
                hold_open=True,
                mode=ExecutionMode.SANDBOXED
            )
            
        except ImportError:
            return self.execute_command(command, working_dir, title)
        except Exception as e:
            return None
    
    def run_makepkg(self, build_dir: str, flags: Optional[List[str]] = None, title: str = "Building Package") -> bool:
        makepkg_cmd = ['makepkg']
        
        if flags:
            makepkg_cmd.extend(flags)
        else:
            makepkg_cmd.extend(['-s', '-r', '-c'])
        
        process = self.execute_command(
            makepkg_cmd,
            working_dir=build_dir,
            title=title,
            hold_open=True
        )
        
        return process is not None
    
    def run_paru_command(self, paru_args: List[str], title: str = "Paru Command") -> bool:
        paru_cmd = ['paru'] + paru_args
        
        process = self.execute_command(
            paru_cmd,
            title=title,
            hold_open=True
        )
        
        return process is not None
    
    def run_pacman_command(self, pacman_args: List[str], title: str = "Pacman Command", use_sudo: bool = True) -> bool:
        if use_sudo:
            pacman_cmd = ['sudo', 'pacman'] + pacman_args
        else:
            pacman_cmd = ['pacman'] + pacman_args
        
        process = self.execute_command(
            pacman_cmd,
            title=title,
            hold_open=True
        )
        
        return process is not None
    
    def run_command_async(self, command: Union[str, List[str]],
                         working_dir: Optional[str] = None,
                         title: Optional[str] = None,
                         callback: Optional[Callable[[bool, str], None]] = None) -> bool:
        
        process = self.execute_command(command, working_dir, title, hold_open=False)
        
        if process and callback:
            def monitor_process():
                try:
                    stdout, stderr = process.communicate()
                    success = process.returncode == 0
                    output = stdout.decode('utf-8') if stdout else ""
                    if stderr:
                        output += "\n" + stderr.decode('utf-8')
                    
                    GLib.idle_add(lambda: callback(success, output))
                except:
                    GLib.idle_add(lambda: callback(False, "Process execution failed"))
            
            import threading
            thread = threading.Thread(target=monitor_process)
            thread.daemon = True
            thread.start()
        
        return process is not None
    
    def run_command_with_sudo(self, command: Union[str, List[str]],
                             working_dir: Optional[str] = None,
                             title: Optional[str] = None) -> bool:
        
        if isinstance(command, str):
            command_list = shlex.split(command)
        else:
            command_list = command[:]
        
        sudo_command = ['sudo'] + command_list
        
        process = self.execute_command(
            sudo_command,
            working_dir=working_dir,
            title=title or "Elevated Command",
            hold_open=True
        )
        
        return process is not None
    
    def open_terminal(self, working_dir: Optional[str] = None, title: Optional[str] = None) -> bool:
        if not working_dir:
            working_dir = os.path.expanduser("~")
        
        process = self.execute_command(
            ['bash'],
            working_dir=working_dir,
            title=title or "Terminal",
            hold_open=False,
            new_window=True
        )
        
        return process is not None
    
    def open_file_manager(self, path: str = None) -> bool:
        if not path:
            path = os.path.expanduser("~")
        
        try:
            subprocess.Popen(['xdg-open', path], start_new_session=True)
            return True
        except:
            return False
    
    def kill_process(self, process_id: str) -> bool:
        if process_id in self._running_processes:
            try:
                process = self._running_processes[process_id]
                process.terminate()
                
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                
                del self._running_processes[process_id]
                return True
            except:
                return False
        return False
    
    def kill_all_processes(self):
        for process_id in list(self._running_processes.keys()):
            self.kill_process(process_id)
    
    def get_running_processes(self) -> List[str]:
        alive_processes = []
        dead_processes = []
        
        for process_id, process in self._running_processes.items():
            if process.poll() is None:
                alive_processes.append(process_id)
            else:
                dead_processes.append(process_id)
        
        for dead_id in dead_processes:
            del self._running_processes[dead_id]
        
        return alive_processes
    
    def _build_terminal_command(self, command: List[str],
                               working_dir: Optional[str] = None,
                               title: Optional[str] = None,
                               hold_open: bool = True,
                               new_window: bool = False) -> List[str]:
        
        if not self.terminal_type or self.terminal_type not in self._terminal_commands:
            return [self.system_terminal_emulator] + command
        
        term_config = self._terminal_commands[self.terminal_type]
        terminal_cmd = [self.system_terminal_emulator]
        
        if new_window and term_config.get('new_window'):
            terminal_cmd.extend(term_config['new_window'])
        
        if title and term_config.get('title'):
            terminal_cmd.extend(term_config['title'])
            terminal_cmd.append(title)
        
        if working_dir and term_config.get('working_dir'):
            terminal_cmd.extend(term_config['working_dir'])
            terminal_cmd.append(working_dir)
        
        if hold_open and term_config.get('hold'):
            terminal_cmd.extend(term_config['hold'])
        
        if term_config.get('execute'):
            terminal_cmd.extend(term_config['execute'])
            
            command_str = ' '.join(shlex.quote(arg) for arg in command)
            if hold_open:
                if self.terminal_type in [TerminalType.GNOME_TERMINAL, TerminalType.KONSOLE, TerminalType.TERMINATOR]:
                    command_str += '; exec bash'
                elif self.terminal_type in [TerminalType.ALACRITTY, TerminalType.XTERM]:
                    command_str += '; read -p "Press Enter to close..."'
                elif self.terminal_type == TerminalType.KITTY:
                    command_str += '; exec bash'
            
            terminal_cmd.append(command_str)
        else:
            terminal_cmd.extend(command)
        
        return terminal_cmd
    
    def get_terminal_info(self) -> Dict[str, Any]:
        return {
            'emulator': self.system_terminal_emulator,
            'type': self.terminal_type.value if self.terminal_type else 'unknown',
            'available_terminals': self.get_available_terminals(),
            'panel_visible': self.is_terminal_panel_visible(),
            'running_processes': len(self._running_processes)
        }
    
    def validate_terminal_setup(self) -> Tuple[bool, List[str]]:
        issues = []
        
        if not self.system_terminal_emulator:
            issues.append("No terminal emulator detected")
        elif not self._is_command_available(self.system_terminal_emulator):
            issues.append(f"Terminal emulator '{self.system_terminal_emulator}' not found in PATH")
        
        if not self.get_available_terminals():
            issues.append("No terminal emulators available on system")
        
        required_commands = ['bash', 'sh']
        for cmd in required_commands:
            if not self._is_command_available(cmd):
                issues.append(f"Required command '{cmd}' not found in PATH")
        
        return len(issues) == 0, issues
