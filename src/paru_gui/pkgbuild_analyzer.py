import os
import re
import subprocess
import logging
import difflib # For diffing PKGBUILDs
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

# Basic logging configuration for this module
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("pkgbuild_analyzer")

@dataclass
class PkgbuildFunction:
    """Represents a shell function within a PKGBUILD."""
    name: str
    content: str
    start_line: int
    end_line: int

@dataclass
class PkgbuildMetadata:
    """Core metadata extracted from a PKGBUILD."""
    pkgname: str
    pkgver: str
    pkgrel: str = "1"
    epoch: Optional[str] = None
    arch: List[str] = field(default_factory=list)
    url: Optional[str] = None
    license: Optional[str] = None
    depends: List[str] = field(default_factory=list)
    makedepends: List[str] = field(default_factory=list)
    checkdepends: List[str] = field(default_factory=list)
    optdepends: List[str] = field(default_factory=list)
    source: List[str] = field(default_factory=list) # Raw source array entries
    functions: Dict[str, PkgbuildFunction] = field(default_factory=dict)

@dataclass
class PkgbuildComparisonResult:
    """Result of comparing two PKGBUILDs."""
    diff: str # Unified diff string
    has_changes: bool
    critical_sections_changed: List[str] # e.g., ['source', 'prepare']
    version_diff: Tuple[Optional[str], Optional[str]] = (None, None) # (local_ver, upstream_ver)

@dataclass
class DependencyAnalysisResult:
    """Result of analyzing package dependencies."""
    package_name: str
    current_pkgver: str
    dependencies: Dict[str, List[str]] = field(default_factory=dict) # e.g., {'depends': [...], 'makedepends': [...]}
    missing_deps: List[str] = field(default_factory=list)
    installed_deps: List[str] = field(default_factory=list)
    optional_deps_available: List[str] = field(default_factory=list)


class PKGBUILDAnalyzer:
    """
    Provides specialized analysis capabilities for PKGBUILD files,
    including detailed parsing, diffing against upstream versions,
    and dependency analysis.
    """

    # Regex for extracting array-like variables (e.g., depends, source)
    # This regex is simplified and might need refinement for edge cases.
    _array_var_re = re.compile(r'^\s*(?P<var_name>\w+)\s*=\s*\((?P<content>[^)]*)\)', re.MULTILINE | re.DOTALL)
    _single_var_re = re.compile(r'^\s*(?P<var_name>\w+)\s*=\s*(?P<content>.*?)\s*$', re.MULTILINE)
    _function_re = re.compile(r'^\s*(?P<func_name>\w+)\s*\(\s*\)\s*{', re.MULTILINE)
    _func_end_re = re.compile(r'^\s*}', re.MULTILINE)

    def __init__(self, upstream_checker: Optional[Any] = None):
        """
        Initializes the PKGBUILDAnalyzer.

        Args:
            upstream_checker: An instance of UpstreamChecker to fetch upstream PKGBUILDs.
        """
        self.upstream_checker = upstream_checker
        logger.info("PKGBUILDAnalyzer initialized.")

    def parse_pkgbuild_detailed(self, pkgbuild_path: str) -> Optional[PkgbuildMetadata]:
        """
        [ ] Implement focused extraction of critical parts (`source=`, `prepare()`, `build()`, etc.).
        Parses a PKGBUILD file to extract all metadata variables and function contents.

        Args:
            pkgbuild_path: The path to the PKGBUILD file.

        Returns:
            A PkgbuildMetadata object if parsing is successful, None otherwise.
        """
        if not os.path.exists(pkgbuild_path):
            logger.error(f"PKGBUILD not found: {pkgbuild_path}")
            return None

        try:
            with open(pkgbuild_path, 'r', encoding='utf-8') as f:
                content_lines = f.readlines()
            full_content = "".join(content_lines)

            # Remove comments for easier parsing of variables/functions
            content_no_comments = re.sub(r'#.*$', '', full_content, flags=re.MULTILINE)

            metadata = PkgbuildMetadata(
                pkgname="unknown", pkgver="unknown", arch=[],
                depends=[], makedepends=[], checkdepends=[], optdepends=[], source=[]
            )

            # Extract basic variables (pkgname, pkgver, pkgrel, epoch, url, license)
            for var_name in ['pkgname', 'pkgver', 'pkgrel', 'epoch', 'url', 'license', 'arch']:
                match = re.search(r'^\s*' + var_name + r'\s*=\s*(?P<value>.*?)\s*$', content_no_comments, re.MULTILINE)
                if match:
                    value = match.group('value').strip().strip('\'"()') # Strip quotes and parentheses
                    if var_name == 'pkgname': metadata.pkgname = value
                    elif var_name == 'pkgver': metadata.pkgver = value
                    elif var_name == 'pkgrel': metadata.pkgrel = value
                    elif var_name == 'epoch': metadata.epoch = value
                    elif var_name == 'url': metadata.url = value
                    elif var_name == 'license': metadata.license = value
                    elif var_name == 'arch': metadata.arch = [a.strip() for a in value.split()]

            # Extract array variables (depends, makedepends, checkdepends, optdepends, source)
            # This logic needs to handle both single-line and multi-line arrays.
            for var_match in self._array_var_re.finditer(content_no_comments):
                var_name = var_match.group('var_name')
                raw_content = var_match.group('content')
                items = [item.strip().strip('\'"') for item in raw_content.split() if item.strip()]

                if var_name == 'depends': metadata.depends.extend(items)
                elif var_name == 'makedepends': metadata.makedepends.extend(items)
                elif var_name == 'checkdepends': metadata.checkdepends.extend(items)
                elif var_name == 'optdepends': metadata.optdepends.extend(items)
                elif var_name == 'source': metadata.source.extend(items)

            # Re-process source to substitute variables using extracted metadata
            resolved_sources = []
            for src_entry in metadata.source:
                resolved_src = src_entry.replace('$pkgname', metadata.pkgname).replace('$pkgver', metadata.pkgver)
                # Apply further variable substitutions if necessary (e.g., $arch, custom variables)
                resolved_sources.append(resolved_src)
            metadata.source = resolved_sources


            # Extract shell functions (prepare, build, package, check, pkgver)
            in_function = False
            current_func_name = ""
            func_content_lines = []
            func_start_line = -1

            for i, line in enumerate(content_lines):
                func_start_match = self._function_re.match(line)
                func_end_match = self._func_end_re.match(line)

                if func_start_match:
                    if in_function: # Handle case where a function might not have a closing brace
                        logger.warning(f"PKGBUILD parsing: Function '{current_func_name}' did not have closing brace before new function at line {i+1}.")
                        metadata.functions[current_func_name] = PkgbuildFunction(
                            name=current_func_name, content="".join(func_content_lines),
                            start_line=func_start_line, end_line=i-1
                        )

                    in_function = True
                    current_func_name = func_start_match.group('func_name')
                    func_content_lines = []
                    func_start_line = i + 1 # Content starts on next line (after function header)

                elif in_function and func_end_match:
                    metadata.functions[current_func_name] = PkgbuildFunction(
                        name=current_func_name, content="".join(func_content_lines),
                        start_line=func_start_line, end_line=i + 1 # Include the closing brace line
                    )
                    in_function = False
                    current_func_name = ""
                    func_content_lines = []
                    func_start_line = -1

                elif in_function:
                    func_content_lines.append(line)

            # Handle case where the last function might not have a closing brace
            if in_function and current_func_name:
                metadata.functions[current_func_name] = PkgbuildFunction(
                    name=current_func_name, content="".join(func_content_lines),
                    start_line=func_start_line, end_line=len(content_lines)
                )


            return metadata

        except Exception as e:
            logger.exception(f"Error detailed parsing PKGBUILD at {pkgbuild_path}: {e}")
            return None


    def compare_pkgbuilds(self, local_pkgbuild_path: str, upstream_pkgbuild_path: str) -> Optional[PkgbuildComparisonResult]:
        """
        [ ] Develop intelligent diff system to review changes between local and upstream PKGBUILD.
        Compares a local PKGBUILD with an upstream version, generating a detailed diff
        and identifying changes in critical sections.

        Args:
            local_pkgbuild_path: Path to the local PKGBUILD.
            upstream_pkgbuild_path: Path to the upstream PKGBUILD.

        Returns:
            A PkgbuildComparisonResult object, or None if files cannot be read.
        """
        if not os.path.exists(local_pkgbuild_path):
            logger.error(f"Local PKGBUILD not found: {local_pkgbuild_path}")
            return None
        if not os.path.exists(upstream_pkgbuild_path):
            logger.error(f"Upstream PKGBUILD not found: {upstream_pkgbuild_path}")
            return None

        try:
            with open(local_pkgbuild_path, 'r', encoding='utf-8') as f:
                local_lines = f.readlines()
            with open(upstream_pkgbuild_path, 'r', encoding='utf-8') as f:
                upstream_lines = f.readlines()

            # Generate unified diff
            diff_generator = difflib.unified_diff(
                local_lines, upstream_lines,
                fromfile=f"a/{os.path.basename(local_pkgbuild_path)}",
                tofile=f"b/{os.path.basename(upstream_pkgbuild_path)}",
                lineterm=''
            )
            diff_content = "".join(list(diff_generator))
            has_changes = bool(diff_content)

            # Identify changes in critical sections (conceptual for now)
            # This would require detailed parsing of both PKGBUILDs and then comparing
            # the content of specific functions/variables like 'source', 'prepare()', 'package()'.
            critical_sections_changed = []
            if has_changes:
                # Placeholder logic: if diff exists, assume some critical sections *might* have changed
                # A real implementation would parse and compare 'source', 'url', and function contents.
                if "source=" in diff_content or "prepare()" in diff_content or "package()" in diff_content:
                    critical_sections_changed.append("source")
                    critical_sections_changed.append("prepare_function")
                    critical_sections_changed.append("package_function") # Simplified detection

            # Get version diff
            local_meta = self.parse_pkgbuild_detailed(local_pkgbuild_path)
            upstream_meta = self.parse_pkgbuild_detailed(upstream_pkgbuild_path)

            local_ver = f"{local_meta.pkgver}-{local_meta.pkgrel}" if local_meta else "N/A"
            upstream_ver = f"{upstream_meta.pkgver}-{upstream_meta.pkgrel}" if upstream_meta else "N/A"


            return PkgbuildComparisonResult(
                diff=diff_content,
                has_changes=has_changes,
                critical_sections_changed=critical_sections_changed,
                version_diff=(local_ver, upstream_ver)
            )

        except Exception as e:
            logger.exception(f"Error comparing PKGBUILDs: {e}")
            return None


    def analyze_dependencies(self, pkgbuild_path: str) -> Optional[DependencyAnalysisResult]:
        """
        [ ] Create analysis of dependencies and relations between packages.
        Analyzes the dependencies of a PKGBUILD, comparing them against installed packages.
        This is a blocking call and should be executed in a separate thread/process.

        Args:
            pkgbuild_path: Path to the PKGBUILD file.

        Returns:
            A DependencyAnalysisResult object, or None if analysis fails.
        """
        pkg_metadata = self.parse_pkgbuild_detailed(pkgbuild_path)
        if not pkg_metadata:
            logger.error(f"Could not parse PKGBUILD for dependency analysis: {pkgbuild_path}")
            return None

        logger.info(f"Analyzing dependencies for {pkg_metadata.pkgname} (blocking)...")
        result = DependencyAnalysisResult(pkg_metadata.pkgname, pkg_metadata.pkgver)
        result.dependencies = {
            'depends': pkg_metadata.depends,
            'makedepends': pkg_metadata.makedepends,
            'checkdepends': pkg_metadata.checkdepends,
            'optdepends': pkg_metadata.optdepends,
        }

        all_required_deps = set(pkg_metadata.depends + pkg_metadata.makedepends + pkg_metadata.checkdepends)

        # Fetch installed packages (this is a blocking operation)
        installed_packages_output = subprocess.run(
            ['pacman', '-Q', 'q'], # List installed packages in quiet mode
            capture_output=True, text=True, check=False, timeout=10
        )
        installed_packages = set(installed_packages_output.stdout.splitlines())

        # Check for missing dependencies
        for dep in all_required_deps:
            # Simple check: does the dependency name exist in installed packages?
            # More complex: handle version constraints (e.g., 'package>=1.0'), virtual packages
            if dep not in installed_packages:
                result.missing_deps.append(dep)
            else:
                result.installed_deps.append(dep)

        # Check for available optional dependencies
        for optdep in pkg_metadata.optdepends:
            if optdep in installed_packages: # Check if the optional dep is installed
                result.optional_deps_available.append(optdep)

        return result

    def verify_version_compatibility(self, pkgbuild_path: str) -> Tuple[bool, str]:
        """
        [ ] Implement version compatibility and system requirements verification.
        Verifies if the PKGBUILD's specified version and architecture are compatible
        with the current system. (Conceptual for now).

        Args:
            pkgbuild_path: Path to the PKGBUILD file.

        Returns:
            A tuple (is_compatible: bool, message: str).
        """
        metadata = self.parse_pkgbuild_detailed(pkgbuild_path)
        if not metadata:
            return False, "Could not parse PKGBUILD metadata."

        current_arch = subprocess.run(['uname', '-m'], capture_output=True, text=True, check=True).stdout.strip()

        # Check architecture compatibility
        if "any" not in metadata.arch and current_arch not in metadata.arch:
            return False, f"Architecture '{current_arch}' not supported by PKGBUILD (supports: {', '.join(metadata.arch)})."

        # TODO: Implement more advanced version compatibility checks
        # - Check minimum kernel version (if specified in PKGBUILD or implicit for dependencies)
        # - Check library versions (e.g., 'glibc>=2.30') by parsing dependencies and system status.

        return True, "Version and architecture appear compatible."

    def integrate_with_security_analysis(self, pkgbuild_path: str, security_analyzer: Any) -> Any:
        """
        [ ] Develop integration with the security system for PKGBUILD-specific risk analysis.
        Delegates to the SecurityAnalyzer for in-depth risk analysis of the PKGBUILD.
        """
        if not security_analyzer:
            logger.error("SecurityAnalyzer instance not provided.")
            return None

        logger.info(f"Integrating PKGBUILD-specific risk analysis for {pkgbuild_path}")
        return security_analyzer.analyze_pkgbuild(pkgbuild_path)


# Example Usage (for testing this module directly)
if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)

    # Create dummy PKGBUILD files for testing
    pkgbuild_content_local = """
    # Contributor: Local User
    pkgname=my-app
    pkgver=1.0.0
    pkgrel=1
    arch=('x86_64' 'i686')
    url="https://example.com/my-app"
    license=('MIT')
    depends=('bash' 'python>=3.8')
    makedepends=('git')
    source=("my-app-$pkgver.tar.gz::https://example.com/releases/$pkgver/my-app.tar.gz")

    prepare() {
        cd "$srcdir/$pkgname-$pkgver"
        ./configure --prefix=/usr
    }

    build() {
        make
    }

    package() {
        make install DESTDIR="$pkgdir"
    }

    check() {
        make check
    }
    """
    local_pkgbuild_path = "/tmp/my-app/PKGBUILD"
    os.makedirs(os.path.dirname(local_pkgbuild_path), exist_ok=True)
    with open(local_pkgbuild_path, "w", encoding='utf-8') as f:
        f.write(pkgbuild_content_local)

    pkgbuild_content_upstream = """
    # Contributor: Upstream Dev
    pkgname=my-app
    pkgver=1.0.1
    pkgrel=1
    arch=('x86_64')
    url="https://example.com/my-app-new" # Changed URL
    license=('MIT')
    depends=('bash' 'python>=3.9' 'new-dep') # Added new-dep, updated python
    makedepends=('git' 'cmake') # Added cmake
    source=("my-app-$pkgver.tar.gz::https://example.com/releases/$pkgver/my-app.tar.gz")

    prepare() {
        cd "$srcdir/$pkgname-$pkgver"
        ./configure --prefix=/usr --enable-features # Added feature flag
    }

    build() {
        echo "Building new version!" # Changed build message
        make
    }

    package() {
        make install DESTDIR="$pkgdir"
        install -m644 new-file "$pkgdir/usr/share/my-app/" # Added new file
    }
    """
    upstream_pkgbuild_path = "/tmp/my-app-upstream/PKGBUILD"
    os.makedirs(os.path.dirname(upstream_pkgbuild_path), exist_ok=True)
    with open(upstream_pkgbuild_path, "w", encoding='utf-8') as f:
        f.write(pkgbuild_content_upstream)


    analyzer = PKGBUILDAnalyzer()

    print("\n--- Testing parse_pkgbuild_detailed (Local) ---")
    local_metadata = analyzer.parse_pkgbuild_detailed(local_pkgbuild_path)
    if local_metadata:
        print(f"Pkgname: {local_metadata.pkgname}")
        print(f"Pkgver: {local_metadata.pkgver}-{local_metadata.pkgrel}")
        print(f"Arch: {local_metadata.arch}")
        print(f"Depends: {local_metadata.depends}")
        print(f"Makedepends: {local_metadata.makedepends}")
        print(f"Source: {local_metadata.source}")
        print("Functions:")
        for name, func in local_metadata.functions.items():
            print(f"  - {func.name} (Lines {func.start_line}-{func.end_line}):\n{func.content[:100]}...") # Show first 100 chars
    else:
        print("Failed to parse local PKGBUILD.")


    print("\n--- Testing compare_pkgbuilds ---")
    comparison_result = analyzer.compare_pkgbuilds(local_pkgbuild_path, upstream_pkgbuild_path)
    if comparison_result:
        print(f"Has Changes: {comparison_result.has_changes}")
        print(f"Version Diff: Local={comparison_result.version_diff[0]}, Upstream={comparison_result.version_diff[1]}")
        print(f"Critical Sections Changed: {comparison_result.critical_sections_changed}")
        print("\nUnified Diff:\n")
        print(comparison_result.diff)
    else:
        print("Failed to compare PKGBUILDs.")


    print("\n--- Testing analyze_dependencies (requires pacman) ---")
    # This will assume 'bash' and 'python' are installed on the system.
    # 'new-dep' might be missing if not installed for the 'upstream' PKGBUILD.
    dep_analysis = analyzer.analyze_dependencies(upstream_pkgbuild_path)
    if dep_analysis:
        print(f"Dependencies for {dep_analysis.package_name} v{dep_analysis.current_pkgver}:")
        print(f"  Depends: {dep_analysis.dependencies.get('depends')}")
        print(f"  Makedepends: {dep_analysis.dependencies.get('makedepends')}")
        print(f"  Missing Dependencies: {dep_analysis.missing_deps}")
        print(f"  Installed Dependencies: {dep_analysis.installed_deps}")
    else:
        print("Failed to analyze dependencies.")

    print("\n--- Testing verify_version_compatibility ---")
    compatible, msg = analyzer.verify_version_compatibility(local_pkgbuild_path)
    print(f"Compatibility for local PKGBUILD: {compatible} - {msg}")

    compatible_upstream, msg_upstream = analyzer.verify_version_compatibility(upstream_pkgbuild_path)
    print(f"Compatibility for upstream PKGBUILD: {compatible_upstream} - {msg_upstream}")


    # Clean up dummy files
    os.remove(local_pkgbuild_path)
    os.rmdir(os.path.dirname(local_pkgbuild_path)) # Remove dir if empty
    os.remove(upstream_pkgbuild_path)
    os.rmdir(os.path.dirname(upstream_pkgbuild_path)) # Remove dir if empty

    print("\n--- PKGBUILDAnalyzer Test Complete ---")
