import os
import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from gi.repository import Gtk, GObject, Gio, GLib, Pango, Gdk

class SuggestionType(Enum):
    COMMAND = "command"
    PACKAGE = "package"
    FILE = "file"
    DIRECTORY = "directory"
    OPTION = "option"
    PARAMETER = "parameter"
    HISTORY = "history"
    CONTEXT = "context"

class CommandContext(Enum):
    SEARCH = "search"
    INSTALL = "install"
    REMOVE = "remove"
    UPDATE = "update"
    BUILD = "build"
    FILE_OPERATION = "file_operation"
    GENERAL = "general"

@dataclass
class CommandSuggestion:
    text: str
    description: str
    suggestion_type: SuggestionType
    context: CommandContext
    score: float = 0.0
    icon: str = "application-x-executable-symbolic"
    shortcut: Optional[str] = None
    parameters: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)

@dataclass
class CommandTemplate:
    command: str
    description: str
    parameters: List[str]
    examples: List[str]
    context: CommandContext
    aliases: List[str] = field(default_factory=list)

class CommandAssistant(GObject.Object):
    __gsignals__ = {
        'suggestion-selected': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'command-executed': (GObject.SignalFlags.RUN_LAST, None, (str,)),
        'history-updated': (GObject.SignalFlags.RUN_LAST, None, ()),
        'context-changed': (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(self, preferences_manager=None):
        super().__init__()
        self.preferences_manager = preferences_manager
        self.command_history = []
        self.suggestion_cache = {}
        self.cache_timeout = 300
        self.max_suggestions = 20
        self.min_query_length = 1
        self.current_context = CommandContext.GENERAL
        self.completion_providers = {}
        self.custom_commands = {}
        
        self._load_command_templates()
        self._load_history()
        self._setup_completion_providers()

    def _load_command_templates(self):
        self.paru_commands = [
            CommandTemplate(
                command="paru",
                description="AUR helper and package manager",
                parameters=["-S", "-R", "-Ss", "-Q", "-U"],
                examples=["paru -S package", "paru -Ss search"],
                context=CommandContext.GENERAL,
                aliases=["p"]
            ),
            CommandTemplate(
                command="paru -S",
                description="Install packages from repositories and AUR",
                parameters=["--needed", "--noconfirm", "--asdeps"],
                examples=["paru -S firefox", "paru -S --needed base-devel"],
                context=CommandContext.INSTALL
            ),
            CommandTemplate(
                command="paru -R",
                description="Remove packages",
                parameters=["-s", "-c", "-n"],
                examples=["paru -R package", "paru -Rs package"],
                context=CommandContext.REMOVE
            ),
            CommandTemplate(
                command="paru -Ss",
                description="Search for packages",
                parameters=["--repo", "--aur"],
                examples=["paru -Ss firefox", "paru -Ss --aur browser"],
                context=CommandContext.SEARCH
            ),
            CommandTemplate(
                command="paru -Syu",
                description="Update all packages",
                parameters=["--devel", "--noconfirm"],
                examples=["paru -Syu", "paru -Syu --devel"],
                context=CommandContext.UPDATE
            ),
            CommandTemplate(
                command="paru -Q",
                description="Query installed packages",
                parameters=["-e", "-m", "-n", "-t"],
                examples=["paru -Q", "paru -Qm"],
                context=CommandContext.SEARCH
            ),
            CommandTemplate(
                command="paru -U",
                description="Install packages from local files",
                parameters=["--noconfirm", "--asdeps"],
                examples=["paru -U package.pkg.tar.zst"],
                context=CommandContext.INSTALL
            ),
            CommandTemplate(
                command="paru -Sua",
                description="Update AUR packages only",
                parameters=["--devel", "--noconfirm"],
                examples=["paru -Sua", "paru -Sua --devel"],
                context=CommandContext.UPDATE
            ),
            CommandTemplate(
                command="paru -c",
                description="Clean package cache",
                parameters=["-c", "-cc"],
                examples=["paru -c", "paru -cc"],
                context=CommandContext.GENERAL
            ),
            CommandTemplate(
                command="paru --pgpfetch",
                description="Fetch PGP keys for packages",
                parameters=["--needed"],
                examples=["paru --pgpfetch"],
                context=CommandContext.GENERAL
            )
        ]

        self.file_commands = [
            CommandTemplate(
                command="makepkg",
                description="Build packages from PKGBUILD",
                parameters=["-s", "-i", "-c", "-f", "-r", "-d"],
                examples=["makepkg -si", "makepkg -scf", "makepkg -sr"],
                context=CommandContext.BUILD
            ),
            CommandTemplate(
                command="makepkg -si",
                description="Build and install package with dependencies",
                parameters=["-c", "-f", "-r"],
                examples=["makepkg -si", "makepkg -sic"],
                context=CommandContext.BUILD
            ),
            CommandTemplate(
                command="makepkg -scf",
                description="Clean build with force",
                parameters=["-i", "-r", "-d"],
                examples=["makepkg -scf", "makepkg -scfi"],
                context=CommandContext.BUILD
            ),
            CommandTemplate(
                command="ls",
                description="List directory contents",
                parameters=["-l", "-a", "-h", "-t", "-r"],
                examples=["ls -la", "ls -lth", "ls -lar"],
                context=CommandContext.FILE_OPERATION
            ),
            CommandTemplate(
                command="cd",
                description="Change directory",
                parameters=[],
                examples=["cd /path/to/directory", "cd ..", "cd ~"],
                context=CommandContext.FILE_OPERATION
            ),
            CommandTemplate(
                command="pwd",
                description="Print working directory",
                parameters=[],
                examples=["pwd"],
                context=CommandContext.FILE_OPERATION
            ),
            CommandTemplate(
                command="mkdir",
                description="Create directories",
                parameters=["-p", "-m"],
                examples=["mkdir dirname", "mkdir -p path/to/dir"],
                context=CommandContext.FILE_OPERATION
            ),
            CommandTemplate(
                command="rm",
                description="Remove files and directories",
                parameters=["-r", "-f", "-i", "-v"],
                examples=["rm file", "rm -rf directory"],
                context=CommandContext.FILE_OPERATION
            ),
            CommandTemplate(
                command="cp",
                description="Copy files and directories",
                parameters=["-r", "-f", "-i", "-v"],
                examples=["cp source dest", "cp -r dir dest"],
                context=CommandContext.FILE_OPERATION
            ),
            CommandTemplate(
                command="mv",
                description="Move/rename files and directories",
                parameters=["-f", "-i", "-v"],
                examples=["mv source dest", "mv old_name new_name"],
                context=CommandContext.FILE_OPERATION
            )
        ]

        self.all_commands = self.paru_commands + self.file_commands

    def _setup_completion_providers(self):
        self.completion_providers = {
            'packages': self._get_package_completions,
            'files': self._get_file_completions,
            'directories': self._get_directory_completions,
            'commands': self._get_command_completions,
            'options': self._get_option_completions
        }

    def _load_history(self):
        history_file = os.path.expanduser("~/.config/paru-gui/command_history.json")
        try:
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.command_history = [
                        {
                            'command': item['command'],
                            'timestamp': datetime.fromisoformat(item['timestamp']),
                            'context': CommandContext(item.get('context', 'general')),
                            'success': item.get('success', True)
                        }
                        for item in data
                    ]
        except Exception:
            self.command_history = []

    def _save_history(self):
        history_file = os.path.expanduser("~/.config/paru-gui/command_history.json")
        os.makedirs(os.path.dirname(history_file), exist_ok=True)
        
        try:
            data = [
                {
                    'command': item['command'],
                    'timestamp': item['timestamp'].isoformat(),
                    'context': item['context'].value,
                    'success': item['success']
                }
                for item in self.command_history[-1000:]
            ]
            
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get_suggestions(self, query: str, context: Optional[CommandContext] = None) -> List[CommandSuggestion]:
        if len(query) < self.min_query_length:
            return self._get_recent_suggestions()

        query = query.strip().lower()
        cache_key = f"{query}:{context or self.current_context}"
        
        if cache_key in self.suggestion_cache:
            cache_entry = self.suggestion_cache[cache_key]
            if datetime.now() - cache_entry['timestamp'] < timedelta(seconds=self.cache_timeout):
                return cache_entry['suggestions']

        suggestions = []
        search_context = context or self.current_context

        suggestions.extend(self._get_command_suggestions(query, search_context))
        suggestions.extend(self._get_package_suggestions(query, search_context))
        suggestions.extend(self._get_file_suggestions(query, search_context))
        suggestions.extend(self._get_history_suggestions(query, search_context))
        suggestions.extend(self._get_contextual_suggestions(query, search_context))

        suggestions = self._score_and_sort_suggestions(suggestions, query)
        suggestions = suggestions[:self.max_suggestions]

        self.suggestion_cache[cache_key] = {
            'suggestions': suggestions,
            'timestamp': datetime.now()
        }

        return suggestions

    def _get_command_suggestions(self, query: str, context: CommandContext) -> List[CommandSuggestion]:
        suggestions = []
        
        for template in self.all_commands:
            if context != CommandContext.GENERAL and template.context != context and template.context != CommandContext.GENERAL:
                continue
            
            if query in template.command.lower() or any(alias for alias in template.aliases if query in alias.lower()):
                score = self._calculate_match_score(query, template.command)
                
                suggestion = CommandSuggestion(
                    text=template.command,
                    description=template.description,
                    suggestion_type=SuggestionType.COMMAND,
                    context=template.context,
                    score=score,
                    icon="application-x-executable-symbolic",
                    parameters=template.parameters,
                    examples=template.examples
                )
                suggestions.append(suggestion)
        
        return suggestions

    def _get_package_suggestions(self, query: str, context: CommandContext) -> List[CommandSuggestion]:
        if context not in [CommandContext.INSTALL, CommandContext.REMOVE, CommandContext.SEARCH]:
            return []
        
        suggestions = []
        
        try:
            import subprocess
            result = subprocess.run(['paru', '-Ss', query], 
                                 capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                packages = set()
                
                for line in lines:
                    if line.strip() and not line.startswith(' '):
                        parts = line.split(' ')
                        if len(parts) >= 2:
                            package_name = parts[0].split('/')[-1]
                            if len(package_name) > 0:
                                packages.add(package_name)
                
                for package in list(packages)[:10]:
                    if query.lower() in package.lower():
                        score = self._calculate_match_score(query, package)
                        suggestion = CommandSuggestion(
                            text=package,
                            description=f"Package: {package}",
                            suggestion_type=SuggestionType.PACKAGE,
                            context=context,
                            score=score,
                            icon="package-x-generic-symbolic"
                        )
                        suggestions.append(suggestion)
        except Exception:
            pass
        
        return suggestions

    def _get_file_suggestions(self, query: str, context: CommandContext) -> List[CommandSuggestion]:
        if context != CommandContext.FILE_OPERATION:
            return []
        
        suggestions = []
        
        try:
            if '/' in query:
                directory = os.path.dirname(query) or '.'
                filename = os.path.basename(query)
            else:
                directory = '.'
                filename = query
            
            if os.path.exists(directory):
                for item in os.listdir(directory):
                    if filename.lower() in item.lower():
                        full_path = os.path.join(directory, item)
                        is_dir = os.path.isdir(full_path)
                        
                        score = self._calculate_match_score(filename, item)
                        suggestion = CommandSuggestion(
                            text=full_path,
                            description=f"{'Directory' if is_dir else 'File'}: {item}",
                            suggestion_type=SuggestionType.DIRECTORY if is_dir else SuggestionType.FILE,
                            context=context,
                            score=score,
                            icon="folder-symbolic" if is_dir else "text-x-generic-symbolic"
                        )
                        suggestions.append(suggestion)
        except Exception:
            pass
        
        return suggestions

    def _get_history_suggestions(self, query: str, context: CommandContext) -> List[CommandSuggestion]:
        suggestions = []
        
        for entry in reversed(self.command_history[-50:]):
            command = entry['command']
            if query.lower() in command.lower():
                if context == CommandContext.GENERAL or entry['context'] == context:
                    score = self._calculate_match_score(query, command)
                    score *= 0.8
                    
                    suggestion = CommandSuggestion(
                        text=command,
                        description=f"Recent: {command}",
                        suggestion_type=SuggestionType.HISTORY,
                        context=entry['context'],
                        score=score,
                        icon="document-open-recent-symbolic"
                    )
                    suggestions.append(suggestion)
        
        return suggestions

    def _get_contextual_suggestions(self, query: str, context: CommandContext) -> List[CommandSuggestion]:
        suggestions = []
        
        contextual_commands = {
            CommandContext.INSTALL: [
                ("install package", "Install a new package", "paru -S "),
                ("install from file", "Install from local package file", "paru -U "),
                ("install dependencies", "Install build dependencies", "paru -S --asdeps "),
                ("install needed", "Install only needed packages", "paru -S --needed ")
            ],
            CommandContext.REMOVE: [
                ("remove package", "Remove an installed package", "paru -R "),
                ("remove with dependencies", "Remove package and unused dependencies", "paru -Rs "),
                ("remove configuration", "Remove package with configuration files", "paru -Rn "),
                ("remove cascade", "Remove package and all dependencies", "paru -Rc ")
            ],
            CommandContext.SEARCH: [
                ("search packages", "Search in package repositories", "paru -Ss "),
                ("search installed", "Search installed packages", "paru -Qs "),
                ("search files", "Search files in packages", "paru -Fl "),
                ("search info", "Show package information", "paru -Si ")
            ],
            CommandContext.UPDATE: [
                ("update system", "Update all packages", "paru -Syu"),
                ("update aur", "Update AUR packages only", "paru -Sua"),
                ("update database", "Update package database", "paru -Sy"),
                ("update devel", "Update development packages", "paru -Syu --devel")
            ],
            CommandContext.BUILD: [
                ("build package", "Build package from PKGBUILD", "makepkg -s"),
                ("build and install", "Build and install package", "makepkg -si"),
                ("clean build", "Clean build with force", "makepkg -scf"),
                ("build repackage", "Build and repackage", "makepkg -sr")
            ],
            CommandContext.FILE_OPERATION: [
                ("list files", "List directory contents", "ls -la"),
                ("change directory", "Change to directory", "cd "),
                ("copy files", "Copy files or directories", "cp -r "),
                ("move files", "Move or rename files", "mv ")
            ]
        }
        
        if context in contextual_commands:
            for cmd_name, description, command in contextual_commands[context]:
                if query.lower() in cmd_name.lower() or query.lower() in command.lower():
                    score = self._calculate_match_score(query, cmd_name)
                    suggestion = CommandSuggestion(
                        text=command + query if command.endswith(' ') else command,
                        description=description,
                        suggestion_type=SuggestionType.CONTEXT,
                        context=context,
                        score=score,
                        icon="system-run-symbolic"
                    )
                    suggestions.append(suggestion)
        
        return suggestions

    def _get_recent_suggestions(self) -> List[CommandSuggestion]:
        suggestions = []
        recent_commands = list(reversed(self.command_history[-10:]))
        
        for i, entry in enumerate(recent_commands):
            suggestion = CommandSuggestion(
                text=entry['command'],
                description=f"Recent: {entry['command']}",
                suggestion_type=SuggestionType.HISTORY,
                context=entry['context'],
                score=1.0 - (i * 0.1),
                icon="document-open-recent-symbolic"
            )
            suggestions.append(suggestion)
        
        return suggestions

    def _calculate_match_score(self, query: str, text: str) -> float:
        query = query.lower()
        text = text.lower()
        
        if query == text:
            return 1.0
        
        if text.startswith(query):
            return 0.9
        
        if query in text:
            position_score = 1.0 - (text.index(query) / len(text))
            return 0.7 * position_score
        
        common_chars = set(query) & set(text)
        if common_chars:
            return 0.3 * (len(common_chars) / len(query))
        
        return 0.0

    def _score_and_sort_suggestions(self, suggestions: List[CommandSuggestion], query: str) -> List[CommandSuggestion]:
        for suggestion in suggestions:
            base_score = suggestion.score
            
            type_bonus = {
                SuggestionType.COMMAND: 0.2,
                SuggestionType.PACKAGE: 0.15,
                SuggestionType.HISTORY: 0.1,
                SuggestionType.CONTEXT: 0.05,
                SuggestionType.FILE: 0.0,
                SuggestionType.DIRECTORY: 0.05,
                SuggestionType.OPTION: 0.08,
                SuggestionType.PARAMETER: 0.08
            }.get(suggestion.suggestion_type, 0.0)
            
            context_bonus = 0.1 if suggestion.context == self.current_context else 0.0
            
            suggestion.score = base_score + type_bonus + context_bonus
        
        return sorted(suggestions, key=lambda s: s.score, reverse=True)

    def add_to_history(self, command: str, success: bool = True):
        entry = {
            'command': command,
            'timestamp': datetime.now(),
            'context': self.current_context,
            'success': success
        }
        
        self.command_history.append(entry)
        
        if len(self.command_history) > 1000:
            self.command_history = self.command_history[-1000:]
        
        self._save_history()
        self.suggestion_cache.clear()
        self.emit('history-updated')

    def set_context(self, context: CommandContext):
        if self.current_context != context:
            self.current_context = context
            self.suggestion_cache.clear()
            self.emit('context-changed', context.value)

    def get_context(self) -> CommandContext:
        return self.current_context

    def clear_history(self):
        self.command_history.clear()
        self._save_history()
        self.suggestion_cache.clear()
        self.emit('history-updated')

    def get_command_completions(self, partial_command: str) -> List[str]:
        completions = []
        words = partial_command.split()
        
        if len(words) == 1:
            for template in self.all_commands:
                if template.command.startswith(partial_command):
                    completions.append(template.command)
        elif len(words) > 1:
            base_command = words[0]
            for template in self.all_commands:
                if template.command.startswith(base_command):
                    for param in template.parameters:
                        if param.startswith(words[-1]):
                            completion = ' '.join(words[:-1] + [param])
                            completions.append(completion)
        
        return sorted(set(completions))

    def get_parameter_suggestions(self, command: str) -> List[str]:
        for template in self.all_commands:
            if command.startswith(template.command):
                return template.parameters
        return []

    def validate_command(self, command: str) -> Tuple[bool, str]:
        command = command.strip()
        
        if not command:
            return False, "Empty command"
        
        words = command.split()
        base_command = words[0]
        
        valid_commands = [cmd.command.split()[0] for cmd in self.all_commands]
        system_commands = ['cd', 'ls', 'pwd', 'mkdir', 'rm', 'cp', 'mv', 'cat', 'grep', 'find']
        
        if base_command not in valid_commands and base_command not in system_commands:
            return False, f"Unknown command: {base_command}"
        
        if base_command == 'paru':
            if len(words) < 2:
                return False, "Paru requires at least one argument"
            
            valid_operations = ['-S', '-R', '-Q', '-Ss', '-Rs', '-Qs', '-Syu', '-U', '-Sua', '-c']
            operation = words[1]
            if not any(operation.startswith(op) for op in valid_operations):
                return False, f"Invalid paru operation: {operation}"
        
        return True, "Valid command"

    def get_command_help(self, command: str) -> Optional[str]:
        for template in self.all_commands:
            if command.startswith(template.command):
                help_text = f"{template.description}\n\n"
                help_text += f"Usage: {template.command}\n\n"
                
                if template.parameters:
                    help_text += "Parameters:\n"
                    for param in template.parameters:
                        help_text += f"  {param}\n"
                    help_text += "\n"
                
                if template.examples:
                    help_text += "Examples:\n"
                    for example in template.examples:
                        help_text += f"  {example}\n"
                
                return help_text
        
        return None

    def add_custom_command(self, template: CommandTemplate):
        self.custom_commands[template.command] = template
        self.all_commands.append(template)
        self.suggestion_cache.clear()

    def remove_custom_command(self, command: str):
        if command in self.custom_commands:
            template = self.custom_commands[command]
            del self.custom_commands[command]
            if template in self.all_commands:
                self.all_commands.remove(template)
            self.suggestion_cache.clear()

    def export_settings(self) -> Dict[str, Any]:
        return {
            'max_suggestions': self.max_suggestions,
            'min_query_length': self.min_query_length,
            'cache_timeout': self.cache_timeout,
            'current_context': self.current_context.value,
            'custom_commands': {
                cmd: {
                    'command': template.command,
                    'description': template.description,
                    'parameters': template.parameters,
                    'examples': template.examples,
                    'context': template.context.value,
                    'aliases': template.aliases
                }
                for cmd, template in self.custom_commands.items()
            }
        }

    def import_settings(self, settings: Dict[str, Any]):
        self.max_suggestions = settings.get('max_suggestions', 20)
        self.min_query_length = settings.get('min_query_length', 1)
        self.cache_timeout = settings.get('cache_timeout', 300)
        self.current_context = CommandContext(settings.get('current_context', 'general'))
        
        custom_commands = settings.get('custom_commands', {})
        for cmd, data in custom_commands.items():
            template = CommandTemplate(
                command=data['command'],
                description=data['description'],
                parameters=data['parameters'],
                examples=data['examples'],
                context=CommandContext(data['context']),
                aliases=data.get('aliases', [])
            )
            self.add_custom_command(template)

    def get_statistics(self) -> Dict[str, Any]:
        total_commands = len(self.command_history)
        successful_commands = sum(1 for entry in self.command_history if entry['success'])
        failed_commands = sum(1 for entry in self.command_history if not entry['success'])
        
        return {
            'total_commands': total_commands,
            'successful_commands': successful_commands,
            'failed_commands': failed_commands,
            'success_rate': successful_commands / total_commands if total_commands > 0 else 0,
            'cache_size': len(self.suggestion_cache),
            'custom_commands': len(self.custom_commands),
            'contexts_used': len(set(entry['context'] for entry in self.command_history)),
            'most_used_commands': self._get_most_used_commands(5),
            'recent_activity': len([e for e in self.command_history 
                                 if datetime.now() - e['timestamp'] < timedelta(days=7)])
        }

    def _get_most_used_commands(self, limit: int = 5) -> List[Tuple[str, int]]:
        from collections import Counter
        commands = [entry['command'].split()[0] for entry in self.command_history]
        return Counter(commands).most_common(limit)

    def clear_cache(self):
        self.suggestion_cache.clear()

    def _get_package_completions(self, query: str) -> List[str]:
        try:
            import subprocess
            result = subprocess.run(['paru', '-Ss', query], 
                                 capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                packages = []
                for line in result.stdout.split('\n')[:20]:
                    if line.strip() and not line.startswith(' '):
                        parts = line.split(' ')
                        if len(parts) >= 1:
                            package_name = parts[0].split('/')[-1]
                            if package_name:
                                packages.append(package_name)
                return packages
        except Exception:
            pass
        return []

    def _get_file_completions(self, query: str) -> List[str]:
        try:
            if os.path.isdir(query):
                return [os.path.join(query, f) for f in os.listdir(query)[:20]]
            else:
                dirname = os.path.dirname(query) or '.'
                basename = os.path.basename(query)
                if os.path.isdir(dirname):
                    return [
                        os.path.join(dirname, f) 
                        for f in os.listdir(dirname)[:20]
                        if f.startswith(basename)
                    ]
        except Exception:
            pass
        return []

    def _get_directory_completions(self, query: str) -> List[str]:
        completions = self._get_file_completions(query)
        return [path for path in completions if os.path.isdir(path)]

    def _get_command_completions(self, query: str) -> List[str]:
        return [cmd.command for cmd in self.all_commands if cmd.command.startswith(query)]

    def _get_option_completions(self, query: str) -> List[str]:
        options = set()
        for template in self.all_commands:
            options.update(template.parameters)
        return [opt for opt in options if opt.startswith(query)]

    def get_smart_suggestions(self, query: str, file_path: Optional[str] = None) -> List[CommandSuggestion]:
        suggestions = []
        
        if file_path:
            if file_path.endswith('PKGBUILD'):
                build_suggestions = [
                    CommandSuggestion(
                        text="makepkg -si",
                        description="Build and install package",
                        suggestion_type=SuggestionType.CONTEXT,
                        context=CommandContext.BUILD,
                        score=0.9,
                        icon="system-run-symbolic"
                    ),
                    CommandSuggestion(
                        text="makepkg -scf",
                        description="Clean build with force",
                        suggestion_type=SuggestionType.CONTEXT,
                        context=CommandContext.BUILD,
                        score=0.8,
                        icon="system-run-symbolic"
                    )
                ]
                suggestions.extend(build_suggestions)
            elif file_path.endswith('.pkg.tar.zst'):
                install_suggestion = CommandSuggestion(
                    text=f"paru -U {os.path.basename(file_path)}",
                    description="Install local package",
                    suggestion_type=SuggestionType.CONTEXT,
                    context=CommandContext.INSTALL,
                    score=0.9,
                    icon="package-x-generic-symbolic"
                )
                suggestions.append(install_suggestion)
        
        regular_suggestions = self.get_suggestions(query)
        suggestions.extend(regular_suggestions)
        
        return self._score_and_sort_suggestions(suggestions, query)[:self.max_suggestions]

    def execute_command_with_feedback(self, command: str, callback=None):
        self.add_to_history(command, True)
        self.emit('command-executed', command)
        if callback:
            GLib.idle_add(callback, command)
