import os
import subprocess
import logging
import shlex
from enum import Enum
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field # Corrected: Added import for dataclass and field

# Basic logging configuration for this module
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sandbox_manager")

class IsolationLevel(Enum):
    """Defines different levels of sandboxing isolation."""
    STRICT = "strict"      # Highly restrictive, minimal access
    MEDIUM = "medium"      # Recommended, balances security with usability
    MINIMAL = "minimal"    # Basic isolation, more permissive

@dataclass
class SandboxOptions:
    """Dataclass to hold sandboxing configuration options."""
    isolation_level: IsolationLevel = IsolationLevel.MEDIUM
    allow_network: bool = False
    allow_home: bool = False
    working_dir: Optional[str] = None # Directory where the command should run inside the sandbox
    bind_paths: List[Tuple[str, str, Optional[str]]] = field(default_factory=list) # (host_path, container_path, flags)

class SandboxManager:
    """
    Manages the creation and execution of sandboxed commands using bubblewrap (bwrap).
    Designed to be run in a separate process to ensure complete isolation.
    """
    def __init__(self):
        logger.info("SandboxManager initialized.")
        self._check_bwrap_installation()

    def _check_bwrap_installation(self):
        """Checks if bubblewrap (bwrap) is installed and available."""
        try:
            subprocess.run(['bwrap', '--version'], check=True, capture_output=True, text=True)
            logger.info("bubblewrap (bwrap) is installed and functional.")
        except FileNotFoundError:
            logger.error("bubblewrap (bwrap) not found. Sandboxing functionality will be limited or unavailable.")
            raise RuntimeError("bubblewrap (bwrap) command not found. Please install it.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error checking bubblewrap version: {e.stderr.strip()}")
            raise RuntimeError(f"bubblewrap (bwrap) found but not working correctly: {e.stderr.strip()}")
        except Exception as e:
            logger.error(f"Unexpected error checking bubblewrap: {e}")
            raise RuntimeError(f"Unexpected error checking bubblewrap: {e}")

    def _build_bwrap_args(self, options: SandboxOptions) -> List[str]:
        """Constructs the bwrap command-line arguments based on SandboxOptions."""
        args: List[str] = []

        # Start with a minimal environment
        args.extend(['--unshare-all', '--die-with-parent'])
        args.extend(['--setenv', 'PATH', '/usr/bin:/bin']) # Minimal PATH
        args.extend(['--setenv', 'HOME', '/home/user'])    # Faked HOME inside sandbox
        args.extend(['--setenv', 'XDG_RUNTIME_DIR', '/run/user/1000']) # Example, adjust as needed

        # Basic mounts for a functional environment
        args.extend(['--dev', '/dev'])
        args.extend(['--proc', '/proc'])
        args.extend(['--tmpfs', '/tmp'])
        args.extend(['--tmpfs', '/dev/shm'])
        args.extend(['--ro-bind', '/usr', '/usr'])
        args.extend(['--ro-bind', '/etc', '/etc']) # Necessary for many system tools
        args.extend(['--ro-bind', '/bin', '/bin'])
        args.extend(['--ro-bind', '/lib', '/lib'])
        args.extend(['--ro-bind', '/lib64', '/lib64'])
        args.extend(['--ro-bind', '/sbin', '/sbin']) # For commands like modprobe if needed

        # Allow network access
        if options.allow_network:
            args.append('--share-net')
        else:
            args.append('--unshare-net') # Explicitly disable network

        # Home directory access
        if options.allow_home:
            # Bind user's real home directory
            user_home = os.path.expanduser('~')
            args.extend(['--bind', user_home, user_home])
            # Or make it read-only for stricter but still accessible
            # args.extend(['--ro-bind', user_home, user_home])
        else:
            # Create an empty, isolated home directory
            args.extend(['--tmpfs', '/home/user']) # Isolated temporary home
            args.extend(['--setenv', 'HOME', '/home/user']) # Point HOME to isolated tmpfs

        # Working directory setup
        if options.working_dir:
            host_wd = options.working_dir
            container_wd = options.working_dir # Assume same path inside sandbox for simplicity
            args.extend(['--bind', host_wd, container_wd])
            # If the working dir is meant to be modifiable, use --bind.
            # If it should be pristine, could use --ro-bind and --tmpfs overlay.
            args.extend(['--chdir', container_wd])
        else:
            # If no specific working dir, chdir to the isolated /tmp
            args.extend(['--chdir', '/tmp'])

        # Additional bind paths (e.g., for specific cache dirs, source files)
        for host_path, container_path, flags in options.bind_paths:
            if flags:
                args.extend([flags, host_path, container_path])
            else:
                args.extend(['--bind', host_path, container_path])

        # Isolation level specific adjustments
        if options.isolation_level == IsolationLevel.STRICT:
            args.extend(['--hostname', 'sandbox']) # Isolated hostname
            args.extend(['--uid', '0', '--gid', '0']) # Run as root inside sandbox (common for builds)
            args.extend(['--no-new-privileges']) # Prevent privilege escalation
            args.extend(['--cap-drop', 'ALL']) # Drop all capabilities
            # More unsharing for strict
            args.extend(['--unshare-ipc', '--unshare-pid', '--unshare-cgroup', '--unshare-user'])
            args.extend(['--bind-data', '/tmp', '/run/user/$UID']) # Simulate XDG_RUNTIME_DIR securely
        elif options.isolation_level == IsolationLevel.MEDIUM:
            # Similar to strict, but might allow specific things if needed.
            # Current args are already fairly restrictive for medium.
            pass
        elif options.isolation_level == IsolationLevel.MINIMAL:
            # Less unsharing, more bind mounts.
            # For this example, current options are already quite strict.
            # A minimal sandbox might just unshare PID and mount /tmp.
            pass

        # Additional common binds for Arch/AUR build tools
        args.extend(['--ro-bind', '/var/cache/pacman', '/var/cache/pacman']) # For paru to fetch packages
        args.extend(['--ro-bind', '/srv/aur', '/srv/aur']) # Common AUR build directory if needed
        args.extend(['--ro-bind', '/var/lib/pacman', '/var/lib/pacman']) # Needed for paru database access

        return args

    def run_sandboxed_command(self,
                              command: List[str],
                              sandbox_options: SandboxOptions,
                              output_callback: Optional[callable] = None, # For real-time GUI update
                              timeout: Optional[int] = None) -> Tuple[int, str, str]:
        """
        Executes a command within a bubblewrap sandbox.
        This function is designed to be called in a separate process.

        Args:
            command: The actual command (list of strings) to execute inside the sandbox.
            sandbox_options: Configuration for the sandbox.
            output_callback: A callback function (line: str, stream: str) for real-time output.
            timeout: Optional timeout for the sandboxed process in seconds.

        Returns:
            A tuple: (return_code, stdout_str, stderr_str)
        """
        bwrap_args = ['bwrap'] + self._build_bwrap_args(sandbox_options) + ['--'] + command

        logger.info(f"Running sandboxed command: {' '.join(shlex.quote(arg) for arg in bwrap_args)}")

        stdout_buffer: List[str] = []
        stderr_buffer: List[str] = []

        try:
            # Use Popen to manage streams for real-time output if callback is provided
            process = subprocess.Popen(
                bwrap_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1, # Line-buffered output
                universal_newlines=True # Ensure correct encoding for text streams
            )

            # Read stdout and stderr simultaneously (or near-simultaneously)
            # This is a simplified approach; for truly concurrent reading,
            # you'd use threading.Thread for each pipe or async I/O.
            # For a separate process, this blocking read is acceptable.
            while True:
                stdout_line = process.stdout.readline()
                stderr_line = process.stderr.readline()

                if stdout_line:
                    stdout_buffer.append(stdout_line)
                    if output_callback:
                        output_callback(stdout_line, "stdout")
                if stderr_line:
                    stderr_buffer.append(stderr_line)
                    if output_callback:
                        output_callback(stderr_line, "stderr")

                if not stdout_line and not stderr_line and process.poll() is not None:
                    break # Process finished and no more output

            # Ensure all remaining output is read after process exits
            stdout_buffer.extend(process.stdout.readlines())
            stderr_buffer.extend(process.stderr.readlines())

            return_code = process.wait(timeout=timeout)

            full_stdout = "".join(stdout_buffer)
            full_stderr = "".join(stderr_buffer)

            if return_code != 0:
                logger.warning(f"Sandboxed command finished with exit code {return_code}: {' '.join(command)}")
                logger.debug(f"Sandboxed STDOUT: {full_stdout.strip()}")
                logger.debug(f"Sandboxed STDERR: {full_stderr.strip()}")
            else:
                logger.info(f"Sandboxed command completed successfully: {' '.join(command)}")

            return return_code, full_stdout, full_stderr

        except FileNotFoundError:
            error_msg = f"Error: 'bwrap' or a command within the sandbox '{command[0]}' not found."
            logger.error(error_msg)
            if output_callback: output_callback(error_msg + "\n", "stderr")
            return 127, "", error_msg # 127 is common for command not found
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            error_msg = f"Sandboxed command timed out after {timeout} seconds: {' '.join(command)}"
            logger.error(error_msg)
            if output_callback: output_callback(error_msg + "\n", "stderr")
            return 124, "", error_msg # 124 is common for timeout
        except Exception as e:
            error_msg = f"Unhandled error during sandboxed execution: {e}"
            logger.exception(error_msg)
            if output_callback: output_callback(error_msg + "\n", "stderr")
            return 1, "", error_msg

    def get_sandbox_activity_log(self, process_output: str) -> List[str]:
        """
        Parses raw process output for potential dangerous activities/warnings from bwrap.
        This is a basic heuristic and might need enhancement based on bwrap's actual logging.
        """
        log_lines = []
        for line in process_output.splitlines():
            if "bwrap:" in line.lower() or "error" in line.lower() or "permission denied" in line.lower():
                log_lines.append(f"[Sandbox Warning] {line}")
            # Add more specific patterns for bwrap errors or security-relevant messages
        return log_lines

# Example usage (for testing this module directly)
if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG) # Enable DEBUG logs for testing

    sandbox_manager = SandboxManager()

    print("\n--- Testing Strict Sandboxing (no network, no home, custom command) ---")
    options_strict = SandboxOptions(
        isolation_level=IsolationLevel.STRICT,
        allow_network=False,
        allow_home=False,
        working_dir="/tmp" # Run in a temporary directory
    )
    # Command to test network and home access
    cmd_strict = ['sh', '-c', 'echo "Hello from sandbox!"; curl -s --head http://example.com || echo "Network access failed as expected."; ls -la /home/user || echo "Home dir access failed as expected."']

    # Real-time output placeholder for direct testing
    def test_output_callback(line: str, stream: str):
        print(f"[{stream.upper()}] {line.strip()}")

    ret_code, stdout, stderr = sandbox_manager.run_sandboxed_command(cmd_strict, options_strict, test_output_callback, timeout=20)
    print(f"\nStrict Sandbox Result: Return Code = {ret_code}")
    print("STDOUT:\n", stdout)
    print("STDERR:\n", stderr)
    print("Activity Log (heuristic from combined output):")
    for log in sandbox_manager.get_sandbox_activity_log(stdout + stderr):
        print(log)

    print("\n--- Testing Medium Sandboxing (allow network, bind home, run paru -V) ---")
    # For this to work, paru needs to be installed on the host and bind-mounted.
    # We need to ensure /usr/bin, /bin, /var/cache/pacman, /var/lib/pacman are properly bound.
    # The default _build_bwrap_args already includes many necessary binds.

    # Ensure a dummy working directory for paru build
    paru_test_dir = "/tmp/paru-sandbox-test"
    os.makedirs(paru_test_dir, exist_ok=True)
    # Create a dummy PKGBUILD here for paru -G test (if paru -G is what you run)
    with open(os.path.join(paru_test_dir, "PKGBUILD"), "w") as f:
        f.write("""pkgname=dummy-paru-pkg\npkgver=0.1.0\nsource=()\nurl="https://example.com"\n""")


    options_medium = SandboxOptions(
        isolation_level=IsolationLevel.MEDIUM,
        allow_network=True,
        allow_home=True, # Allow access to user's real home (e.g., ~/.config/paru)
        working_dir=paru_test_dir # Run paru commands in a specific directory
    )
    # Command to test paru version (safe command)
    cmd_paru = ['paru', '--version']

    # Example for `paru -G` (download sources)
    cmd_paru_get_sources = ['paru', '-G', 'dummy-paru-pkg'] # Assumes dummy-paru-pkg PKGBUILD exists in working_dir

    ret_code, stdout, stderr = sandbox_manager.run_sandboxed_command(cmd_paru_get_sources, options_medium, test_output_callback, timeout=30)
    print(f"\nMedium Sandbox (paru -G) Result: Return Code = {ret_code}")
    print("STDOUT:\n", stdout)
    print("STDERR:\n", stderr)

    # Clean up
    if os.path.exists(paru_test_dir):
        # rmdir might fail if paru -G creates files, use shutil.rmtree
        import shutil
        shutil.rmtree(paru_test_dir)

    print("\n--- Testing Minimal Sandboxing (network, no home) ---")
    options_minimal = SandboxOptions(
        isolation_level=IsolationLevel.MINIMAL,
        allow_network=True,
        allow_home=False,
        working_dir="/tmp"
    )
    cmd_ping = ['ping', '-c', '1', '8.8.8.8'] # Test network
    ret_code, stdout, stderr = sandbox_manager.run_sandboxed_command(cmd_ping, options_minimal, test_output_callback, timeout=10)
    print(f"\nMinimal Sandbox Result: Return Code = {ret_code}")
    print("STDOUT:\n", stdout)
    print("STDERR:\n", stderr)
