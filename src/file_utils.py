import os
import re
import subprocess
import logging
import json
import difflib # For patch preview
from enum import Enum
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

# Basic logging configuration for this module
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("file_utils")

# --- Enums & Data Classes (Moved/Copied from window.py for cohesion in this module) ---
# Note: TrustLevel might eventually reside in security_analyzer.py or a shared `common.py`
# if it's used across many modules. For now, it lives here with its dependent logic.

class TrustLevel(Enum):
    HIGH = "HIGH"    # 50+ votes
    MEDIUM = "MEDIUM" # 10-50 votes
    LOW = "LOW"      # <10 votes

class FileUtils:
    """
    Provides utility functions for file system operations, metadata extraction,
    and basic security-related file checks (e.g., signature analysis, patch preview).
    These functions are designed to be callable from separate threads/processes
    to avoid blocking the main UI thread.
    """
    def __init__(self, preferences_manager=None):
        logger.info("FileUtils initialized.")
        self.preferences_manager = preferences_manager # To be integrated for preferences
        # Pre-compile regex for performance
        self._pkgname_re = re.compile(r'^\s*pkgname\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', re.MULTILINE)
        self._pkgver_re = re.compile(r'^\s*pkgver\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', re.MULTILINE)
        self._pkgrel_re = re.compile(r'^\s*pkgrel\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', re.MULTILINE)
        self._votes_re = re.compile(r'Votes\s*:\s*(\d+)')
        self._pkginfo_pkgver_re = re.compile(r'pkgver\s*=\s*(\S+)')
        self._pkginfo_pkgrel_re = re.compile(r'pkgrel\s*=\s*(\S+)')

    # --- Implement smart file format detection (Moved from window.py) ---
    @staticmethod
    def identify_file_type(filepath: str) -> str:
        """
        Identifies the primary type of a given file.

        Args:
            filepath: The full path to the file.

        Returns:
            A string representing the file type ('PKGBUILD', 'PACKAGE', 'PATCH', 'UNKNOWN').
        """
        if os.path.basename(filepath) == "PKGBUILD":
            return 'PKGBUILD'
        elif filepath.endswith('.pkg.tar.zst'):
            return 'PACKAGE'
        elif filepath.endswith(('.patch', '.diff')):
            return 'PATCH'
        return 'UNKNOWN'

    # --- Develop logic to extract PKGBUILD metadata (Moved from window.py) ---
    def extract_pkgbuild_info(self, path: str) -> Tuple[str, str, str]:
        """
        Safely extracts pkgname, pkgver, and pkgrel from a PKGBUILD file without execution.

        Args:
            path: The full path to the PKGBUILD file.

        Returns:
            A tuple (pkgname, pkgver, pkgrel). Returns "unknown" for missing values.
        """
        pkgname = "unknown"
        pkgver = "unknown"
        pkgrel = "1"

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            name_match = self._pkgname_re.search(content)
            ver_match = self._pkgver_re.search(content)
            rel_match = self._pkgrel_re.search(content)

            if name_match: pkgname = name_match.group(1)
            if ver_match: pkgver = ver_match.group(1)
            if rel_match: pkgrel = rel_match.group(1)

        except Exception as e:
            logger.error(f"Error reading PKGBUILD {path} for info extraction: {e}")
        return (pkgname, pkgver, pkgrel)

    def get_aur_votes(self, pkgname: str) -> int:
        """
        Fetches AUR votes for a given package name using `paru -Si`.
        This is a blocking call and should be executed in a separate thread/process.

        Args:
            pkgname: The name of the package on AUR.

        Returns:
            The number of votes, or 0 if not found/error.
        """
        if not pkgname or pkgname == "unknown":
            return 0
        logger.info(f"Fetching AUR votes for {pkgname} using paru -Si (blocking)...")
        try:
            # TODO: Integrate with CacheManager (if not already handled by UpstreamChecker)
            result = subprocess.run(
                ['paru', '-Si', pkgname],
                capture_output=True,
                text=True,
                timeout=10, # Increased timeout for network call
                check=False
            )
            if result.returncode == 0:
                votes_match = self._votes_re.search(result.stdout)
                return int(votes_match.group(1)) if votes_match else 0
            else:
                logger.warning(f"Paru command failed for {pkgname} (AUR votes): {result.stderr.strip()}")
                return 0
        except FileNotFoundError:
            logger.error("Error: 'paru' command not found. Is paru installed?")
            return 0
        except subprocess.TimeoutExpired:
            logger.warning(f"Paru command timed out for {pkgname} (AUR votes).")
            return 0
        except Exception as e:
            logger.error(f"Error getting AUR votes for {pkgname}: {e}")
            return 0

    def get_trust_level(self, votes: int) -> TrustLevel:
        """
        Determines the TrustLevel based on the number of AUR votes.

        Args:
            votes: The number of AUR votes.

        Returns:
            A TrustLevel enum member.
        """
        # TODO: Integrate with PreferencesManager for configurable thresholds
        min_medium = 10 # self.preferences_manager.get_min_votes_medium_trust()
        min_high = 50   # self.preferences_manager.get_min_votes_high_trust()

        if votes >= min_high:
            return TrustLevel.HIGH
        elif votes >= min_medium:
            return TrustLevel.MEDIUM
        return TrustLevel.LOW

    def get_pkg_name_from_zst(self, filepath: str) -> str:
        """
        Extracts the package name from a .pkg.tar.zst file using `tar`.
        This is a blocking call and should be executed in a separate thread/process.

        Args:
            filepath: The full path to the .pkg.tar.zst file.

        Returns:
            The extracted package name, or a default name derived from the filename.
        """
        base_name = os.path.basename(filepath)
        default_name = base_name.replace('.pkg.tar.zst', '')

        try:
            result = subprocess.run(
                ['tar', '--zstd', '-tvf', filepath], # Inspect .zst file content
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
            if result.returncode == 0:
                # Look for .PKGINFO, then extract name. Heuristic: name is before first '-'
                for line in result.stdout.splitlines():
                    if '.PKGINFO' in line:
                        return base_name.split('-')[0]
                return default_name
            else:
                logger.warning(f"Tar command failed for {filepath} (pkg name): {result.stderr.strip()}")
                return default_name
        except FileNotFoundError:
            logger.error("Error: 'tar' command not found.")
            return default_name
        except subprocess.TimeoutExpired:
            logger.warning(f"Tar command timed out for {filepath} (pkg name).")
            return default_name
        except Exception as e:
            logger.error(f"Error extracting package name from {filepath}: {e}")
            return default_name

    def get_pkg_version_from_zst(self, filepath: str) -> str:
        """
        Extracts the package version (pkgver-pkgrel) from a .pkg.tar.zst file by reading its .PKGINFO.
        This is a blocking call and should be executed in a separate thread/process.

        Args:
            filepath: The full path to the .pkg.tar.zst file.

        Returns:
            The extracted version string (e.g., "1.2.3-1"), or "unknown".
        """
        try:
            result = subprocess.run(
                ['tar', '--zstd', '-xOf', filepath, '.PKGINFO'], # Extract .PKGINFO content
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
            if result.returncode == 0:
                pkgver_match = self._pkginfo_pkgver_re.search(result.stdout)
                pkgrel_match = self._pkginfo_pkgrel_re.search(result.stdout)

                pkgver = pkgver_match.group(1) if pkgver_match else "unknown"
                pkgrel = pkgrel_match.group(1) if pkgrel_match else "1"

                return f"{pkgver}-{pkgrel}"
            else:
                logger.warning(f"Tar command (PKGINFO) failed for {filepath} (pkg version): {result.stderr.strip()}")
                return "unknown"
        except FileNotFoundError:
            logger.error("Error: 'tar' command not found.")
            return "unknown"
        except subprocess.TimeoutExpired:
            logger.warning(f"Tar command (PKGINFO) timed out for {filepath} (pkg version).")
            return "unknown"
        except Exception as e:
            logger.error(f"Error extracting package version from {filepath}: {e}")
            return "unknown"

    # --- Create signature analysis system for .zst packages (Moved from window.py) ---
    def check_signature_zst(self, filepath: str) -> str:
        """
        Checks the digital signature status of a .pkg.tar.zst package.
        This is a blocking call and should be executed in a separate thread/process.

        Args:
            filepath: The full path to the .pkg.tar.zst file.

        Returns:
            "Verified", "Not signed", or "Verification failed".
        """
        try:
            sig_path = filepath + '.sig'
            if not os.path.exists(sig_path):
                logger.info(f"Signature file not found for {filepath}.")
                return "Not signed"

            # TODO: [ ] Implement actual signature verification via `gpg` or `pacman-key --verify`
            # This is a placeholder for the real cryptographic verification.
            logger.info(f"Performing signature verification for {filepath} (placeholder)...")

            # Simulate a verification check
            import time
            time.sleep(0.5)
            # For demonstration purposes, simulate success/failure
            if "badpackage" in os.path.basename(filepath).lower():
                raise Exception("Simulated bad signature")

            # A real verification might look like:
            # result = subprocess.run(['pacman-key', '--verify', sig_path, filepath], ...)
            # if result.returncode == 0: return "Verified"
            # else: raise Exception(result.stderr)

            return "Verified"
        except Exception as e:
            logger.error(f"Error checking signature for {filepath}: {e}")
            return "Verification failed"

    def get_patch_description(self, filepath: str) -> str:
        """
        Extracts a brief description from the first comment line of a patch file.

        Args:
            filepath: The full path to the patch file.

        Returns:
            The description, or a generic string if no suitable comment is found.
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if first_line.startswith('#'):
                    return first_line[1:].strip()
                return "Generic patch file"
        except Exception as e:
            logger.error(f"Error reading patch description from {filepath}: {e}")
            return "Unknown patch"

    # --- Implement patch preview with change identification ---
    def preview_patch_diff(self, patch_filepath: str, original_filepath: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """
        Generates a unified diff string for a patch file.
        If `original_filepath` is provided, it attempts to show how the patch would apply.
        Otherwise, it just shows the content of the patch file.

        Args:
            patch_filepath: The path to the .patch or .diff file.
            original_filepath: Optional path to the original file the patch applies to.

        Returns:
            A tuple (success: bool, diff_content: str, error_message: Optional[str]).
            The diff_content will contain colorized ANSI escape codes if a real diff is run.
        """
        if not os.path.exists(patch_filepath):
            return False, "", f"Patch file not found: {patch_filepath}"

        logger.info(f"Generating diff preview for {patch_filepath} (blocking)...")
        try:
            if original_filepath and os.path.exists(original_filepath):
                # Use `diff` command for a more realistic and potentially colorized output
                # `diff -u -L` for unified format, -L for labels
                cmd = ['diff', '-u', '-L', os.path.basename(original_filepath), '-L', os.path.basename(patch_filepath), original_filepath, patch_filepath]
                # A more accurate way to apply a patch for preview is to use `patch --dry-run`
                # which also needs the original file and its directory.
                # For simplicity here, we'll read the patch content and maybe run `diff -u` on it.

                with open(patch_filepath, 'r', encoding='utf-8') as pf:
                    patch_lines = pf.readlines()
                with open(original_filepath, 'r', encoding='utf-8') as of:
                    original_lines = of.readlines()

                d = difflib.unified_diff(original_lines, patch_lines,
                                         fromfile=os.path.basename(original_filepath),
                                         tofile=os.path.basename(patch_filepath),
                                         lineterm='') # Avoid extra newlines

                diff_text = "".join(list(d))
                return True, diff_text, None

            else:
                # Just return the raw patch content if no original file for diffing
                with open(patch_filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                return True, content, None
        except Exception as e:
            logger.error(f"Error generating patch preview for {patch_filepath}: {e}")
            return False, "", str(e)


    # --- Develop utilities for secure AUR PKGBUILD download ---
    def download_pkgbuild_from_aur(self, pkgname: str, target_dir: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Downloads a PKGBUILD and its associated files from AUR into a target directory using `paru -G`.
        This is a blocking call and should be executed in a separate thread/process.

        Args:
            pkgname: The name of the AUR package.
            target_dir: The directory where the PKGBUILD should be downloaded.

        Returns:
            A tuple (success: bool, pkgbuild_path: Optional[str], error_message: Optional[str]).
        """
        if not os.path.isdir(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        logger.info(f"Downloading PKGBUILD for {pkgname} to {target_dir} using paru -G (blocking)...")
        try:
            # paru -G <package> downloads the PKGBUILD and related files
            # into a subdirectory named <package> in the current working directory.
            result = subprocess.run(
                ['paru', '-G', pkgname],
                cwd=target_dir, # Run paru in the target directory
                capture_output=True,
                text=True,
                timeout=30, # Longer timeout for network operation
                check=False
            )

            if result.returncode == 0:
                downloaded_path = os.path.join(target_dir, pkgname, "PKGBUILD")
                if os.path.exists(downloaded_path):
                    logger.info(f"PKGBUILD for {pkgname} downloaded successfully to {downloaded_path}")
                    return True, downloaded_path, None
                else:
                    error_msg = f"Paru -G succeeded, but PKGBUILD not found at expected path: {downloaded_path}. STDERR: {result.stderr.strip()}"
                    logger.error(error_msg)
                    return False, None, error_msg
            else:
                error_msg = f"Failed to download PKGBUILD for {pkgname}. Exit Code: {result.returncode}. STDERR: {result.stderr.strip()}"
                logger.error(error_msg)
                return False, None, error_msg
        except FileNotFoundError:
            error_msg = "Error: 'paru' command not found. Is paru installed?"
            logger.error(error_msg)
            return False, None, error_msg
        except subprocess.TimeoutExpired:
            error_msg = f"Downloading PKGBUILD for {pkgname} timed out after 30 seconds."
            logger.error(error_msg)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Unexpected error downloading PKGBUILD for {pkgname}: {e}"
            logger.exception(error_msg)
            return False, None, error_msg


# Example Usage (for testing this module directly)
if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG) # Enable DEBUG logs for testing

    file_utils = FileUtils()

    print("\n--- Testing identify_file_type ---")
    dummy_pkgbuild = "/tmp/PKGBUILD"
    dummy_package = "/tmp/my-app-1.0.0-1-x86_64.pkg.tar.zst"
    dummy_patch = "/tmp/fix.patch"
    dummy_text = "/tmp/notes.txt"

    with open(dummy_pkgbuild, "w") as f: f.write("pkgname=test")
    with open(dummy_package, "w") as f: f.write("binary data")
    with open(dummy_patch, "w") as f: f.write("--- a/file\n+++ b/file")
    with open(dummy_text, "w") as f: f.write("hello world")

    print(f"Type of {os.path.basename(dummy_pkgbuild)}: {file_utils.identify_file_type(dummy_pkgbuild)}")
    print(f"Type of {os.path.basename(dummy_package)}: {file_utils.identify_file_type(dummy_package)}")
    print(f"Type of {os.path.basename(dummy_patch)}: {file_utils.identify_file_type(dummy_patch)}")
    print(f"Type of {os.path.basename(dummy_text)}: {file_utils.identify_file_type(dummy_text)}")


    print("\n--- Testing extract_pkgbuild_info ---")
    pkgname, pkgver, pkgrel = file_utils.extract_pkgbuild_info(dummy_pkgbuild)
    print(f"PKGBUILD Info: {pkgname}-{pkgver}-{pkgrel}")


    print("\n--- Testing get_aur_votes (requires paru installed) ---")
    # This will attempt to run `paru -Si` for 'spotify'
    # If paru is not installed or network is down, it will log errors and return 0.
    # Replace 'spotify' with a known AUR package for reliable testing.
    votes = file_utils.get_aur_votes("spotify")
    print(f"Spotify AUR Votes: {votes} (Trust: {file_utils.get_trust_level(votes).value})")
    votes_unknown = file_utils.get_aur_votes("non-existent-package-123")
    print(f"Non-existent package votes: {votes_unknown} (Trust: {file_utils.get_trust_level(votes_unknown).value})")


    print("\n--- Testing get_pkg_name_from_zst & get_pkg_version_from_zst ---")
    # This assumes dummy_package contains a valid .PKGINFO.
    # For a real test, you'd generate a minimal valid .pkg.tar.zst.
    pkg_name = file_utils.get_pkg_name_from_zst(dummy_package)
    pkg_version = file_utils.get_pkg_version_from_zst(dummy_package)
    print(f"Package Name: {pkg_name}, Version: {pkg_version}")


    print("\n--- Testing check_signature_zst ---")
    # Create dummy .sig file for testing
    dummy_signature = dummy_package + ".sig"
    with open(dummy_signature, "w") as f: f.write("dummy signature content")

    # Simulate a "bad" package name to trigger simulated failure
    dummy_bad_package = "/tmp/badpackage-1.0.0-1-x86_64.pkg.tar.zst"
    with open(dummy_bad_package, "w") as f: f.write("malicious binary data")
    with open(dummy_bad_package + ".sig", "w") as f: f.write("valid looking sig")

    print(f"Signature Status ({os.path.basename(dummy_package)}): {file_utils.check_signature_zst(dummy_package)}")
    print(f"Signature Status ({os.path.basename(dummy_bad_package)}): {file_utils.check_signature_zst(dummy_bad_package)}")
    print(f"Signature Status (no .sig): {file_utils.check_signature_zst(dummy_text)}")


    print("\n--- Testing get_patch_description ---")
    dummy_patch_with_desc = "/tmp/patch_with_desc.patch"
    with open(dummy_patch_with_desc, "w") as f:
        f.write("# This is a test patch description\n--- a/file\n+++ b/file")
    print(f"Patch description: {file_utils.get_patch_description(dummy_patch_with_desc)}")
    print(f"Patch description ({os.path.basename(dummy_patch)}): {file_utils.get_patch_description(dummy_patch)}")


    print("\n--- Testing preview_patch_diff ---")
    dummy_original_file = "/tmp/original.txt"
    dummy_modified_file = "/tmp/modified.txt"
    dummy_simple_patch = "/tmp/simple.patch"

    with open(dummy_original_file, "w") as f: f.write("line 1\nline 2\nline 3\n")
    with open(dummy_modified_file, "w") as f: f.write("line 1\nchanged line 2\nline 3.1\n")

    # Create a patch using diff command for testing
    try:
        patch_process = subprocess.run(
            ['diff', '-u', dummy_original_file, dummy_modified_file],
            capture_output=True, text=True, check=True
        )
        with open(dummy_simple_patch, "w") as f: f.write(patch_process.stdout)

        success, diff_content, err_msg = file_utils.preview_patch_diff(dummy_simple_patch, dummy_original_file)
        if success:
            print(f"Patch Preview (with original file):\n{diff_content}")
        else:
            print(f"Patch Preview failed: {err_msg}")
    except Exception as e:
        print(f"Could not create dummy patch for testing diff preview: {e}")

    success, content, err = file_utils.preview_patch_diff(dummy_simple_patch)
    if success:
        print(f"Patch Preview (raw content):\n{content}")
    else:
        print(f"Patch Preview (raw) failed: {err}")


    print("\n--- Testing download_pkgbuild_from_aur (requires paru and network) ---")
    test_download_dir = "/tmp/aur_download_test"
    test_aur_pkg = "paru" # Use paru itself as a test case

    success, downloaded_pkgbuild_path, err_msg = file_utils.download_pkgbuild_from_aur(test_aur_pkg, test_download_dir)
    if success:
        print(f"PKGBUILD for '{test_aur_pkg}' downloaded to: {downloaded_pkgbuild_path}")
        # Verify content
        if os.path.exists(downloaded_pkgbuild_path):
            with open(downloaded_pkgbuild_path, 'r') as f:
                first_line = f.readline().strip()
                print(f"First line of downloaded PKGBUILD: {first_line}")
    else:
        print(f"Failed to download PKGBUILD for '{test_aur_pkg}': {err_msg}")

    # Clean up downloaded files
    if os.path.exists(os.path.join(test_download_dir, test_aur_pkg)):
        import shutil
        shutil.rmtree(os.path.join(test_download_dir, test_aur_pkg))


    # Clean up dummy files
    os.remove(dummy_pkgbuild)
    os.remove(dummy_package)
    os.remove(dummy_signature)
    os.remove(dummy_bad_package)
    os.remove(dummy_bad_package + ".sig")
    os.remove(dummy_patch)
    os.remove(dummy_text)
    if os.path.exists(dummy_patch_with_desc): os.remove(dummy_patch_with_desc)
    if os.path.exists(dummy_original_file): os.remove(dummy_original_file)
    if os.path.exists(dummy_modified_file): os.remove(dummy_modified_file)
    if os.path.exists(dummy_simple_patch): os.remove(dummy_simple_patch)
    if os.path.exists(test_download_dir): os.rmdir(test_download_dir) # Only if empty

    print("\n--- FileUtils Test Complete ---")
