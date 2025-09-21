import os
import re
import subprocess
import logging
import json
import difflib # For patch preview
from enum import Enum
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field # Import corrected

# Basic logging configuration for this module
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("file_utils")

# --- Enums & Data Classes ---

class TrustLevel(Enum):
    HIGH = "HIGH"    # 50+ votes
    MEDIUM = "MEDIUM" # 10-50 votes
    LOW = "LOW"      # <10 votes
    NONE = "NONE"    # Cannot determine / No AUR info

@dataclass
class FileItem:
    """Represents a file or directory item to be displayed in the UI."""
    name: str
    path: str
    is_dir: bool
    file_type: str = "UNKNOWN" # PKGBUILD, PACKAGE, PATCH, ADVANCED, UNKNOWN
    version: str = "N/A"
    trust_level: Optional[TrustLevel] = TrustLevel.NONE
    votes: int = 0
    last_update_str: str = "N/A"
    pgp_status: str = "N/A"
    signature_status: str = "N/A" # For packages
    extra_info: Optional[str] = None # For patch description, package details, etc.

    def get_icon_name(self) -> str:
        """Returns the appropriate icon name for the file type."""
        if self.is_dir:
            return "folder-symbolic"
        elif self.file_type == 'PKGBUILD':
            return "text-x-generic-symbolic"
        elif self.file_type == 'PACKAGE':
            return "package-x-generic-symbolic"
        elif self.file_type == 'PATCH':
            return "text-x-patch-symbolic"
        elif self.file_type == 'ADVANCED':
            return "utilities-terminal-symbolic"
        return "text-x-generic-symbolic"

    def get_trust_icon(self) -> str:
        """Returns the appropriate trust level icon name."""
        if self.trust_level == TrustLevel.HIGH:
            return "security-high-symbolic"
        elif self.trust_level == TrustLevel.MEDIUM:
            return "security-medium-symbolic"
        elif self.trust_level == TrustLevel.LOW:
            return "security-low-symbolic"
        return "dialog-question-symbolic" # Unknown/None


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
        # PkGBUILDAnalyzer instance will be created and used for detailed parsing
        from paru_gui.pkgbuild_analyzer import PkGBUILDAnalyzer # Import here to avoid circular dependency on init
        self.pkgbuild_analyzer = PkGBUILDAnalyzer()


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

    def get_aur_votes_and_last_update(self, pkgname: str) -> Tuple[int, str]:
        """
        Fetches AUR votes and last update time for a given package name using `paru -Si`.
        This is a blocking call and should be executed in a separate thread/process.

        Args:
            pkgname: The name of the package on AUR.

        Returns:
            A tuple (votes: int, last_update_str: str). Returns (0, "N/A") if not found/error.
        """
        if not pkgname or pkgname == "unknown":
            return 0, "N/A"
        logger.info(f"Fetching AUR info for {pkgname} using paru -Si (blocking)...")
        try:
            result = subprocess.run(
                ['paru', '-Si', pkgname],
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )
            if result.returncode == 0:
                votes_match = re.search(r'Votes\s*:\s*(\d+)', result.stdout)
                last_update_match = re.search(r'Last Update\s*:\s*(.*)', result.stdout)

                votes = int(votes_match.group(1)) if votes_match else 0
                last_update_str = last_update_match.group(1).strip() if last_update_match else "N/A"
                return votes, last_update_str
            else:
                logger.warning(f"Paru command failed for {pkgname} (AUR info): {result.stderr.strip()}")
                return 0, "N/A"
        except FileNotFoundError:
            logger.error("Error: 'paru' command not found. Is paru installed?")
            return 0, "N/A"
        except subprocess.TimeoutExpired:
            logger.warning(f"Paru command timed out for {pkgname} (AUR info).")
            return 0, "N/A"
        except Exception as e:
            logger.error(f"Error getting AUR info for {pkgname}: {e}")
            return 0, "N/A"

    def get_trust_level(self, votes: int) -> TrustLevel:
        """
        Determines the TrustLevel based on the number of AUR votes.

        Args:
            votes: The number of AUR votes.

        Returns:
            A TrustLevel enum member.
        """
        min_medium = self.preferences_manager.get_min_votes_medium_trust() if self.preferences_manager else 10
        min_high = self.preferences_manager.get_min_votes_high_trust() if self.preferences_manager else 50

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

            # Use pacman-key for robust verification if available
            try:
                result = subprocess.run(
                    ['pacman-key', '--verify', sig_path, filepath],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False
                )
                if result.returncode == 0 and "Good signature" in result.stdout:
                    return "Verified"
                else:
                    logger.warning(f"Signature verification failed for {filepath}: {result.stderr.strip()}")
                    return "Verification failed"
            except FileNotFoundError:
                logger.warning("pacman-key not found. Falling back to gpg (less integrated).")
                # Fallback to gpg if pacman-key is not found
                try:
                    result = subprocess.run(
                        ['gpg', '--verify', sig_path, filepath],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=False
                    )
                    if result.returncode == 0 and "Good signature" in result.stderr: # gpg output to stderr
                        return "Verified"
                    else:
                        logger.warning(f"Signature verification failed (gpg) for {filepath}: {result.stderr.strip()}")
                        return "Verification failed"
                except FileNotFoundError:
                    logger.error("Neither pacman-key nor gpg found. Cannot verify signature.")
                    return "Verification failed (tools missing)"

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
                # Try to extract from the diff header if no comment line
                diff_header_match = re.match(r'--- a/(.+?)\s+\+\+\+ b/(.+?)', first_line)
                if diff_header_match:
                    return f"Patch for {diff_header_match.group(1)}"
                return "Generic patch file"
        except Exception as e:
            logger.error(f"Error reading patch description from {filepath}: {e}")
            return "Unknown patch"

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
            # Using difflib to generate a diff directly if both files are provided
            # This offers better control and doesn't rely on `diff` command.
            if original_filepath and os.path.exists(original_filepath):
                with open(original_filepath, 'r', encoding='utf-8') as of:
                    original_lines = of.readlines()
                with open(patch_filepath, 'r', encoding='utf-8') as pf:
                    # For a "preview" of a patch file, we show the patch itself.
                    # If we wanted to *apply* a patch for preview, we'd use patch --dry-run.
                    # This function is for showing the patch content for review.
                    patch_content_lines = pf.readlines()

                # For diff preview, we usually just want to see the patch file content.
                # The 'original_filepath' might be used to derive context/metadata if needed,
                # but the diff content is typically the patch file itself.
                # If the intention was to show `diff -u original patched` after applying,
                # that would be a different operation.
                # For a "preview_patch_diff", returning the patch file content itself is standard.
                return True, "".join(patch_content_lines), None

            else:
                # Just return the raw patch content if no original file for diffing or applying context
                with open(patch_filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                return True, content, None
        except Exception as e:
            logger.error(f"Error generating patch preview for {patch_filepath}: {e}")
            return False, "", str(e)


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

    def scan_compatible_files_worker(self, folder_path: str) -> List[FileItem]:
        """
        Scans the given folder for compatible files (PKGBUILDs, .pkg.tar.zst, .patch)
        and extracts relevant metadata. This is a worker function for a separate thread/process.

        Args:
            folder_path: The directory to scan.

        Returns:
            A list of FileItem objects.
        """
        file_items: List[FileItem] = []
        if not os.path.isdir(folder_path):
            logger.warning(f"Scan path is not a directory: {folder_path}")
            return []

        # Add an "Advanced Mode" virtual item if not in simplified mode
        # This check is better handled in the UI layer (`_update_content_view`)
        # when deciding which cards to create based on preferences.

        try:
            with os.scandir(folder_path) as entries:
                for entry in entries:
                    if entry.name.startswith('.'): # Skip hidden files/dirs
                        continue

                    full_path = entry.path

                    if entry.is_dir():
                        file_items.append(FileItem(
                            name=entry.name,
                            path=full_path,
                            is_dir=True
                        ))
                    elif entry.is_file():
                        file_type = self.identify_file_type(full_path)
                        item_name = entry.name
                        item_version = "N/A"
                        item_trust_level = TrustLevel.NONE
                        item_votes = 0
                        item_last_update_str = "N/A"
                        item_pgp_status = "N/A"
                        item_signature_status = "N/A"
                        item_extra_info = None

                        if file_type == 'PKGBUILD':
                            pkgname, pkgver, pkgrel = self.extract_pkgbuild_info(full_path)
                            item_name = pkgname
                            item_version = f"{pkgver}-{pkgrel}"
                            if self.preferences_manager and self.preferences_manager.get_show_trust_icons():
                                votes, last_update = self.get_aur_votes_and_last_update(pkgname)
                                item_votes = votes
                                item_last_update_str = last_update
                                item_trust_level = self.get_trust_level(votes)
                                # PGP status could be fetched here from SecurityAnalyzer if needed,
                                # but usually done during full security review.
                                # For initial display, keep as N/A or derive from simple check.

                        elif file_type == 'PACKAGE':
                            item_name = self.get_pkg_name_from_zst(full_path)
                            item_version = self.get_pkg_version_from_zst(full_path)
                            item_signature_status = self.check_signature_zst(full_path)

                        elif file_type == 'PATCH':
                            item_extra_info = self.get_patch_description(full_path)

                        file_items.append(FileItem(
                            name=item_name,
                            path=full_path,
                            is_dir=False,
                            file_type=file_type,
                            version=item_version,
                            trust_level=item_trust_level,
                            votes=item_votes,
                            last_update_str=item_last_update_str,
                            pgp_status=item_pgp_status,
                            signature_status=item_signature_status,
                            extra_info=item_extra_info
                        ))
        except Exception as e:
            logger.error(f"Error scanning directory {folder_path}: {e}")

        # Sort directories first, then files alphabetically
        file_items.sort(key=lambda x: (not x.is_dir, x.name.lower()))

        # Add a single 'ADVANCED' card at the end if not in simplified mode
        # This is handled in `_update_content_view` now when populating the FlowBox.

        return file_items

# Example Usage (for testing this module directly)
if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG) # Enable DEBUG logs for testing

    # Mock a PreferencesManager for testing purposes
    class MockPreferencesManager:
        def get_show_trust_icons(self): return True
        def get_min_votes_medium_trust(self): return 10
        def get_min_votes_high_trust(self): return 50

    mock_prefs = MockPreferencesManager()
    file_utils = FileUtils(preferences_manager=mock_prefs)

    print("\n--- Testing identify_file_type ---")
    dummy_pkgbuild_path = "/tmp/PKGBUILD"
    dummy_package_path = "/tmp/my-app-1.0.0-1-x86_64.pkg.tar.zst"
    dummy_patch_path = "/tmp/fix.patch"
    dummy_text_path = "/tmp/notes.txt"
    dummy_dir_path = "/tmp/test_dir"

    os.makedirs(dummy_dir_path, exist_ok=True)
    with open(dummy_pkgbuild_path, "w") as f: f.write("pkgname=test\npkgver=1.0.0\npkgrel=1")
    with open(dummy_package_path, "w") as f: f.write("binary data")
    with open(dummy_patch_path, "w") as f: f.write("# My patch\n--- a/file\n+++ b/file")
    with open(dummy_text_path, "w") as f: f.write("hello world")

    print(f"Type of {os.path.basename(dummy_pkgbuild_path)}: {file_utils.identify_file_type(dummy_pkgbuild_path)}")
    print(f"Type of {os.path.basename(dummy_package_path)}: {file_utils.identify_file_type(dummy_package_path)}")
    print(f"Type of {os.path.basename(dummy_patch_path)}: {file_utils.identify_file_type(dummy_patch_path)}")
    print(f"Type of {os.path.basename(dummy_text_path)}: {file_utils.identify_file_type(dummy_text_path)}")


    print("\n--- Testing extract_pkgbuild_info ---")
    pkgname, pkgver, pkgrel = file_utils.extract_pkgbuild_info(dummy_pkgbuild_path)
    print(f"PKGBUILD Info: {pkgname}-{pkgver}-{pkgrel}")


    print("\n--- Testing get_aur_votes_and_last_update (requires paru installed) ---")
    votes, last_update = file_utils.get_aur_votes_and_last_update("paru") # Use a known AUR package
    print(f"Paru AUR Votes: {votes}, Last Update: {last_update} (Trust: {file_utils.get_trust_level(votes).value})")
    votes_unknown, update_unknown = file_utils.get_aur_votes_and_last_update("non-existent-package-123")
    print(f"Non-existent package votes: {votes_unknown}, Last Update: {update_unknown} (Trust: {file_utils.get_trust_level(votes_unknown).value})")


    print("\n--- Testing get_pkg_name_from_zst & get_pkg_version_from_zst (requires tar) ---")
    # For a real test, generate a minimal valid .pkg.tar.zst.
    # The dummy one won't work well as tar expects actual archive.
    pkg_name = file_utils.get_pkg_name_from_zst(dummy_package_path)
    pkg_version = file_utils.get_pkg_version_from_zst(dummy_package_path)
    print(f"Package Name from zst: {pkg_name}, Version: {pkg_version}")


    print("\n--- Testing check_signature_zst (requires pacman-key or gpg) ---")
    # Create dummy .sig file for testing
    dummy_signature_path = dummy_package_path + ".sig"
    with open(dummy_signature_path, "w") as f: f.write("dummy signature content")

    # Simulate a "bad" package name to trigger simulated failure for gpg/pacman-key
    dummy_bad_package_path = "/tmp/badpackage-1.0.0-1-x86_64.pkg.tar.zst"
    with open(dummy_bad_package_path, "w") as f: f.write("malicious binary data")
    with open(dummy_bad_package_path + ".sig", "w") as f: f.write("valid looking sig")

    print(f"Signature Status ({os.path.basename(dummy_package_path)}): {file_utils.check_signature_zst(dummy_package_path)}")
    print(f"Signature Status ({os.path.basename(dummy_bad_package_path)}): {file_utils.check_signature_zst(dummy_bad_package_path)}")
    print(f"Signature Status (no .sig): {file_utils.check_signature_zst(dummy_text_path)}")


    print("\n--- Testing get_patch_description ---")
    print(f"Patch description ({os.path.basename(dummy_patch_path)}): {file_utils.get_patch_description(dummy_patch_path)}")


    print("\n--- Testing preview_patch_diff ---")
    # This will simply return the content of dummy_patch_path as no original_filepath is given.
    success, content, err = file_utils.preview_patch_diff(dummy_patch_path)
    if success:
        print(f"Patch Preview (raw content):\n{content}")
    else:
        print(f"Patch Preview failed: {err}")

    print("\n--- Testing scan_compatible_files_worker ---")
    test_scan_dir = "/tmp" # Scan the /tmp directory
    scanned_items = file_utils.scan_compatible_files_worker(test_scan_dir)
    for item in scanned_items:
        print(f"Scanned: {item.name}, Path: {item.path}, Type: {item.file_type}, IsDir: {item.is_dir}, Version: {item.version}, Trust: {item.trust_level.value}, Votes: {item.votes}")

    # Clean up dummy files
    os.remove(dummy_pkgbuild_path)
    os.remove(dummy_package_path)
    os.remove(dummy_signature_path)
    os.remove(dummy_bad_package_path)
    os.remove(dummy_bad_package_path + ".sig")
    os.remove(dummy_patch_path)
    os.remove(dummy_text_path)
    os.rmdir(dummy_dir_path)

    print("\n--- FileUtils Test Complete ---")
