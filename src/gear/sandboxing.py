import os
import subprocess
import shlex
import shutil
from enum import Enum
from typing import List, Dict, Optional, Tuple, Callable
from dataclasses import dataclass, field
from pathlib import Path


class IsolationLevel(Enum):
    STRICT = "strict"
    MEDIUM = "medium"
    MINIMAL = "minimal"


class SandboxStatus(Enum):
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class SandboxOptions:
    isolation_level: IsolationLevel = IsolationLevel.MEDIUM
    allow_network: bool = False
    allow_home: bool = False
    allow_x11: bool = False
    allow_dbus: bool = False
    working_dir: Optional[str] = None
    bind_paths: List[Tuple[str, str, Optional[str]]] = field(default_factory=list)
    env_vars: Dict[str, str] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    uid: Optional[int] = None
    gid: Optional[int] = None
    hostname: Optional[str] = None
    tmpfs_paths: List[str] = field(default_factory=list)
    ro_bind_paths: List[Tuple[str, str]] = field(default_factory=list)
    dev_bind_paths: List[Tuple[str, str]] = field(default_factory=list)


@dataclass
class SandboxResult:
    return_code: int
    stdout: str
    stderr: str
    status: SandboxStatus
    execution_time: float = 0.0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class SandboxManager:
    
    def __init__(self):
        self._check_dependencies()
        self._running_processes: Dict[str, subprocess.Popen] = {}
        
    def _check_dependencies(self):
        if not self._is_bwrap_available():
            raise RuntimeError("bubblewrap (bwrap) is required but not found")
        
        if not self._verify_bwrap_functionality():
            raise RuntimeError("bubblewrap (bwrap) is not functioning correctly")
    
    def _is_bwrap_available(self) -> bool:
        return shutil.which('bwrap') is not None
    
    def _verify_bwrap_functionality(self) -> bool:
        try:
            result = subprocess.run(
                ['bwrap', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def create_sandbox_options(self, isolation_level: IsolationLevel = IsolationLevel.MEDIUM,
                             **kwargs) -> SandboxOptions:
        options = SandboxOptions(isolation_level=isolation_level)
        
        for key, value in kwargs.items():
            if hasattr(options, key):
                setattr(options, key, value)
        
        return options
    
    def execute_sandboxed_makepkg(self, build_dir: str,
                                 makepkg_args: Optional[List[str]] = None,
                                 options: Optional[SandboxOptions] = None) -> bool:
        
        if not options:
            options = SandboxOptions(
                isolation_level=IsolationLevel.MEDIUM,
                allow_network=True,
                working_dir=build_dir
            )
        
        makepkg_cmd = ['makepkg']
        if makepkg_args:
            makepkg_cmd.extend(makepkg_args)
        else:
            makepkg_cmd.extend(['-s', '-r', '-c'])
        
        result = self.run_sandboxed_command(makepkg_cmd, options)
        return result.status == SandboxStatus.COMPLETED and result.return_code == 0
    
    def execute_sandboxed_paru(self, paru_args: List[str],
                              options: Optional[SandboxOptions] = None) -> SandboxResult:
        
        if not options:
            options = SandboxOptions(
                isolation_level=IsolationLevel.MEDIUM,
                allow_network=True,
                allow_home=True
            )
        
        paru_cmd = ['paru'] + paru_args
        return self.run_sandboxed_command(paru_cmd, options)
    
    def run_sandboxed_command(self, command: List[str],
                             options: SandboxOptions,
                             timeout: Optional[int] = None,
                             output_callback: Optional[Callable[[str, str], None]] = None) -> SandboxResult:
        
        import time
        start_time = time.time()
        
        try:
            bwrap_args = self._build_bwrap_command(command, options)
            
            process = subprocess.Popen(
                bwrap_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                cwd=options.working_dir
            )
            
            stdout_lines = []
            stderr_lines = []
            
            try:
                while True:
                    stdout_line = process.stdout.readline()
                    stderr_line = process.stderr.readline()
                    
                    if stdout_line:
                        stdout_lines.append(stdout_line)
                        if output_callback:
                            output_callback(stdout_line.rstrip(), "stdout")
                    
                    if stderr_line:
                        stderr_lines.append(stderr_line)
                        if output_callback:
                            output_callback(stderr_line.rstrip(), "stderr")
                    
                    if not stdout_line and not stderr_line and process.poll() is not None:
                        break
                
                remaining_stdout, remaining_stderr = process.communicate(timeout=timeout)
                if remaining_stdout:
                    stdout_lines.extend(remaining_stdout.splitlines(keepends=True))
                if remaining_stderr:
                    stderr_lines.extend(remaining_stderr.splitlines(keepends=True))
                
                execution_time = time.time() - start_time
                
                stdout_str = ''.join(stdout_lines)
                stderr_str = ''.join(stderr_lines)
                
                result = SandboxResult(
                    return_code=process.returncode,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    status=SandboxStatus.COMPLETED if process.returncode == 0 else SandboxStatus.FAILED,
                    execution_time=execution_time
                )
                
                result.warnings = self._extract_warnings(stdout_str, stderr_str)
                result.errors = self._extract_errors(stderr_str)
                
                return result
                
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                
                return SandboxResult(
                    return_code=-1,
                    stdout=''.join(stdout_lines),
                    stderr=''.join(stderr_lines),
                    status=SandboxStatus.TIMEOUT,
                    execution_time=time.time() - start_time,
                    errors=["Command timed out"]
                )
                
        except Exception as e:
            return SandboxResult(
                return_code=-1,
                stdout="",
                stderr=str(e),
                status=SandboxStatus.FAILED,
                execution_time=time.time() - start_time,
                errors=[f"Execution error: {str(e)}"]
            )
    
    def _build_bwrap_command(self, command: List[str], options: SandboxOptions) -> List[str]:
        args = ['bwrap']
        
        args.extend(['--unshare-all', '--die-with-parent'])
        
        if options.isolation_level == IsolationLevel.STRICT:
            args.extend(['--unshare-user', '--unshare-ipc', '--unshare-pid', '--unshare-cgroup'])
            args.extend(['--no-new-privileges'])
            args.extend(['--cap-drop', 'ALL'])
            
            for cap in options.capabilities:
                args.extend(['--cap-add', cap])
        
        elif options.isolation_level == IsolationLevel.MEDIUM:
            args.extend(['--unshare-user', '--unshare-ipc'])
            
        elif options.isolation_level == IsolationLevel.MINIMAL:
            pass
        
        args.extend(['--dev', '/dev'])
        args.extend(['--proc', '/proc'])
        args.extend(['--tmpfs', '/tmp'])
        args.extend(['--tmpfs', '/var/tmp'])
        
        for tmpfs_path in options.tmpfs_paths:
            args.extend(['--tmpfs', tmpfs_path])
        
        essential_ro_binds = [
            '/usr', '/bin', '/lib', '/lib64', '/sbin', '/etc'
        ]
        
        for path in essential_ro_binds:
            if os.path.exists(path):
                args.extend(['--ro-bind', path, path])
        
        for host_path, container_path in options.ro_bind_paths:
            if os.path.exists(host_path):
                args.extend(['--ro-bind', host_path, container_path])
        
        for host_path, container_path in options.dev_bind_paths:
            if os.path.exists(host_path):
                args.extend(['--dev-bind', host_path, container_path])
        
        for host_path, container_path, flags in options.bind_paths:
            if os.path.exists(host_path):
                bind_type = flags if flags else '--bind'
                args.extend([bind_type, host_path, container_path])
        
        if options.allow_network:
            args.extend(['--share-net'])
        else:
            args.extend(['--unshare-net'])
        
        if options.allow_home:
            home_dir = os.path.expanduser('~')
            args.extend(['--bind', home_dir, home_dir])
        else:
            args.extend(['--tmpfs', '/home'])
            fake_home = '/home/sandbox'
            args.extend(['--mkdir', fake_home])
            args.extend(['--setenv', 'HOME', fake_home])
        
        if options.allow_x11:
            x11_socket = os.environ.get('DISPLAY')
            if x11_socket and os.path.exists('/tmp/.X11-unix'):
                args.extend(['--bind', '/tmp/.X11-unix', '/tmp/.X11-unix'])
                args.extend(['--setenv', 'DISPLAY', x11_socket])
        
        if options.allow_dbus:
            dbus_session = os.environ.get('DBUS_SESSION_BUS_ADDRESS')
            if dbus_session:
                args.extend(['--setenv', 'DBUS_SESSION_BUS_ADDRESS', dbus_session])
                
                xdg_runtime_dir = os.environ.get('XDG_RUNTIME_DIR')
                if xdg_runtime_dir and os.path.exists(xdg_runtime_dir):
                    args.extend(['--bind', xdg_runtime_dir, xdg_runtime_dir])
        
        if options.working_dir:
            if not os.path.exists(options.working_dir):
                try:
                    os.makedirs(options.working_dir, exist_ok=True)
                except:
                    pass
            
            args.extend(['--bind', options.working_dir, options.working_dir])
            args.extend(['--chdir', options.working_dir])
        else:
            args.extend(['--chdir', '/tmp'])
        
        if options.uid is not None:
            args.extend(['--uid', str(options.uid)])
        
        if options.gid is not None:
            args.extend(['--gid', str(options.gid)])
        
        if options.hostname:
            args.extend(['--hostname', options.hostname])
        
        default_env = {
            'PATH': '/usr/bin:/bin:/usr/sbin:/sbin',
            'LANG': os.environ.get('LANG', 'C.UTF-8'),
            'USER': 'sandbox',
            'LOGNAME': 'sandbox'
        }
        
        for key, value in default_env.items():
            args.extend(['--setenv', key, value])
        
        for key, value in options.env_vars.items():
            args.extend(['--setenv', key, value])
        
        pacman_paths = [
            '/var/lib/pacman',
            '/var/cache/pacman',
            '/etc/pacman.conf',
            '/etc/pacman.d'
        ]
        
        for path in pacman_paths:
            if os.path.exists(path):
                args.extend(['--ro-bind', path, path])
        
        args.append('--')
        args.extend(command)
        
        return args
    
    def _extract_warnings(self, stdout: str, stderr: str) -> List[str]:
        warnings = []
        combined_output = stdout + stderr
        
        warning_patterns = [
            'warning:',
            'caution:',
            'deprecated',
            'bwrap:',
            'permission denied',
            'access denied'
        ]
        
        for line in combined_output.splitlines():
            line_lower = line.lower()
            for pattern in warning_patterns:
                if pattern in line_lower:
                    warnings.append(line.strip())
                    break
        
        return warnings
    
    def _extract_errors(self, stderr: str) -> List[str]:
        errors = []
        
        error_patterns = [
            'error:',
            'failed:',
            'cannot',
            'unable to',
            'not found',
            'permission denied',
            'access denied'
        ]
        
        for line in stderr.splitlines():
            line_lower = line.lower()
            for pattern in error_patterns:
                if pattern in line_lower:
                    errors.append(line.strip())
                    break
        
        return errors
    
    def test_sandbox_functionality(self) -> Tuple[bool, List[str]]:
        test_results = []
        all_passed = True
        
        try:
            options = SandboxOptions(
                isolation_level=IsolationLevel.MINIMAL,
                allow_network=False,
                allow_home=False
            )
            
            test_cmd = ['echo', 'sandbox test']
            result = self.run_sandboxed_command(test_cmd, options, timeout=10)
            
            if result.status == SandboxStatus.COMPLETED and result.return_code == 0:
                test_results.append("Basic sandbox execution: PASS")
            else:
                test_results.append("Basic sandbox execution: FAIL")
                all_passed = False
                
        except Exception as e:
            test_results.append(f"Basic sandbox execution: FAIL - {str(e)}")
            all_passed = False
        
        try:
            options = SandboxOptions(
                isolation_level=IsolationLevel.STRICT,
                allow_network=False,
                allow_home=False
            )
            
            network_test_cmd = ['ping', '-c', '1', '8.8.8.8']
            result = self.run_sandboxed_command(network_test_cmd, options, timeout=10)
            
            if result.return_code != 0:
                test_results.append("Network isolation test: PASS")
            else:
                test_results.append("Network isolation test: FAIL - Network access not blocked")
                all_passed = False
                
        except Exception as e:
            test_results.append(f"Network isolation test: FAIL - {str(e)}")
            all_passed = False
        
        return all_passed, test_results
    
    def get_sandbox_info(self) -> Dict[str, any]:
        info = {
            'bwrap_available': self._is_bwrap_available(),
            'bwrap_functional': False,
            'bwrap_version': 'unknown',
            'running_processes': len(self._running_processes),
            'supported_features': []
        }
        
        if info['bwrap_available']:
            try:
                result = subprocess.run(
                    ['bwrap', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    info['bwrap_functional'] = True
                    version_line = result.stdout.strip().split('\n')[0]
                    info['bwrap_version'] = version_line
                    
            except:
                pass
        
        features = ['user_namespaces', 'network_isolation', 'filesystem_isolation', 'process_isolation']
        info['supported_features'] = features
        
        return info
    
    def cleanup_processes(self):
        for process_id, process in list(self._running_processes.items()):
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                
                del self._running_processes[process_id]
            except:
                pass
    
    def get_isolation_recommendations(self, command: List[str]) -> SandboxOptions:
        if not command:
            return SandboxOptions()
        
        cmd_name = os.path.basename(command[0]).lower()
        
        if cmd_name in ['makepkg', 'paru', 'yay']:
            return SandboxOptions(
                isolation_level=IsolationLevel.MEDIUM,
                allow_network=True,
                allow_home=False,
                ro_bind_paths=[
                    ('/var/lib/pacman', '/var/lib/pacman'),
                    ('/var/cache/pacman', '/var/cache/pacman'),
                    ('/etc/pacman.conf', '/etc/pacman.conf'),
                    ('/etc/pacman.d', '/etc/pacman.d')
                ]
            )
        
        elif cmd_name in ['git', 'wget', 'curl']:
            return SandboxOptions(
                isolation_level=IsolationLevel.MEDIUM,
                allow_network=True,
                allow_home=False
            )
        
        elif cmd_name in ['gcc', 'g++', 'make', 'cmake']:
            return SandboxOptions(
                isolation_level=IsolationLevel.MINIMAL,
                allow_network=False,
                allow_home=False
            )
        
        else:
            return SandboxOptions(
                isolation_level=IsolationLevel.MEDIUM,
                allow_network=False,
                allow_home=False
            )
