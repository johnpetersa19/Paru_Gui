import re
import os
import subprocess
import logging
import json
import requests
import time
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("security_analyzer")

class RiskLevel(Enum):
    CRITICAL = 4
    HIGH = 3
    MEDIUM = 2
    LOW = 1
    NONE = 0

@dataclass
class PkgbuildSection:
    name: str
    content: str
    start_line: int
    end_line: int

@dataclass
class DetectedRisk:
    level: RiskLevel
    description: str
    line_number: Optional[int] = None
    snippet: Optional[str] = None
    category: str = "General"

@dataclass
class CVEResult:
    cve_id: str
    description: str
    severity: str
    published_date: str
    affected_versions: List[str] = field(default_factory=list)

@dataclass
class PGPKeyInfo:
    key_id: str
    valid: bool
    trust_level: str
    missing: bool
    imported: bool = False

@dataclass
class PkgbuildSecurityAnalysisResult:
    pkgname: str
    pkgver: str
    overall_trust_score: float = 0.0
    overall_trust_level: RiskLevel = RiskLevel.NONE
    detected_risks: List[DetectedRisk] = field(default_factory=list)
    heatmap_lines: List[Tuple[int, RiskLevel, str]] = field(default_factory=list)
    aur_info: Dict[str, Any] = field(default_factory=dict)
    cve_results: List[CVEResult] = field(default_factory=list)
    pgp_validation_results: Dict[str, Any] = field(default_factory=dict)
    raw_pkgbuild_content: str = ""
    heatmap_data: str = ""
    security_suggestions: List[str] = field(default_factory=list)

class SecurityAnalyzer:
    DANGEROUS_COMMAND_PATTERNS = [
        re.compile(r'\bsudo\s+(rm|mv|cp)\s+-?rf?\s*/', re.IGNORECASE),
        re.compile(r'\b(chown|chmod)\s+-?R?\s*root\s*/', re.IGNORECASE),
        re.compile(r'\bmkfs\b'),
        re.compile(r'\bdd\s+if=/dev/zero', re.IGNORECASE),
        re.compile(r'\bcurl\s+.*?\|\s*(bash|sh|zsh)\b', re.IGNORECASE),
        re.compile(r'\bwget\s+.*?\|\s*(bash|sh|zsh)\b', re.IGNORECASE),
        re.compile(r'\b(curl|wget)\s+.*?(/etc/passwd|/etc/shadow|~/\.ssh)', re.IGNORECASE),
        re.compile(r'\brm\s+-rf?\s*(/|/usr|/etc|/boot)', re.IGNORECASE),
        re.compile(r'\bchmod\s+777\s+/', re.IGNORECASE),
        re.compile(r'\beval\s+\$\(.*\)', re.IGNORECASE),
        re.compile(r'\b(nc|netcat)\s+.*-e\s+(bash|sh)', re.IGNORECASE),
        re.compile(r'\biptables\s+-F', re.IGNORECASE),
        re.compile(r'\buseradd\s+.*root', re.IGNORECASE),
        re.compile(r'\bpasswd\s+root', re.IGNORECASE),
        re.compile(r'\b(systemctl|service)\s+(disable|stop)\s+firewall', re.IGNORECASE),
    ]

    INSECURE_PATTERNS = [
        (r'sha\d+sums=\([^)]*[\'"]SKIP[\'"][^)]*\)', RiskLevel.HIGH, "Checksum verification skipped"),
        (r'--disable-ssl-verify', RiskLevel.HIGH, "SSL verification disabled"),
        (r'--no-check-certificate', RiskLevel.HIGH, "Certificate checking disabled"),
        (r'--insecure', RiskLevel.HIGH, "Insecure connection allowed"),
        (r'\bsu\s+-\s+root', RiskLevel.MEDIUM, "Direct root access attempted"),
        (r'\bpkexec\b', RiskLevel.MEDIUM, "PolicyKit execution detected"),
        (r'PKGEXT=.*\.tar\b', RiskLevel.LOW, "Uncompressed package format"),
        (r'--ignore-certificate-errors', RiskLevel.HIGH, "Certificate errors ignored"),
        (r'--disable-web-security', RiskLevel.HIGH, "Web security disabled"),
    ]

    TRUSTED_DOMAINS = [
        "github.com", "gitlab.com", "aur.archlinux.org", "archlinux.org",
        "download.mozilla.org", "ftp.gnu.org", "kernel.org", "sourceforge.net",
        "bitbucket.org", "codeberg.org", "sr.ht", "pypi.org", "npmjs.com",
        "download.kde.org", "download.gnome.org", "releases.ubuntu.com"
    ]

    CVE_API_BASE = "https://cve.circl.lu/api"
    NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"

    def __init__(self):
        logger.info("SecurityAnalyzer initialized")
        self.upstream_checker = None
        self.cve_cache = {}
        self.pgp_keyring_path = os.path.expanduser("~/.gnupg")
        self.api_rate_limit = 1.0
        self.max_cve_results = 10

    def set_upstream_checker(self, checker):
        self.upstream_checker = checker

    def analyze_pkgbuild(self, pkgbuild_path: str) -> PkgbuildSecurityAnalysisResult:
        if not os.path.exists(pkgbuild_path):
            logger.error(f"PKGBUILD not found: {pkgbuild_path}")
            return self._create_empty_result("N/A", "N/A", "PKGBUILD not found")

        try:
            with open(pkgbuild_path, 'r', encoding='utf-8') as f:
                pkgbuild_content = f.read()

            pkgname, pkgver, pkgrel, epoch, source_urls, project_url, arch = self._parse_pkgbuild_details_static(pkgbuild_content)

            analysis_result = PkgbuildSecurityAnalysisResult(
                pkgname=pkgname,
                pkgver=pkgver,
                raw_pkgbuild_content=pkgbuild_content,
                aur_info={}
            )

            self._analyze_static_content(pkgbuild_content, analysis_result)
            self._analyze_source_urls(source_urls, project_url, analysis_result)
            self._fetch_aur_info(pkgname, analysis_result)
            self._check_cve_vulnerabilities(pkgname, pkgver, analysis_result)
            self._validate_pgp_signatures(pkgbuild_content, analysis_result)
            self._calculate_overall_trust(analysis_result)
            self._generate_heatmap_data(pkgbuild_content, analysis_result)
            self._generate_security_suggestions(analysis_result)

            logger.info(f"Completed security analysis for {pkgname} (v{pkgver}). Trust Level: {analysis_result.overall_trust_level.name}")
            return analysis_result

        except Exception as e:
            logger.exception(f"Unhandled error during PKGBUILD analysis for {pkgbuild_path}: {e}")
            return self._create_empty_result("N/A", "N/A", f"Analysis failed: {e}")

    def suggest_pgp_keys(self, pkgbuild_path: str) -> List[str]:
        try:
            with open(pkgbuild_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            missing_keys = []
            sig_pattern = re.search(r'validpgpkeys\s*=\s*\(([^)]+)\)', content, re.MULTILINE)
            
            if sig_pattern:
                keys_str = sig_pattern.group(1)
                keys = [key.strip().strip("'\"") for key in keys_str.split() if key.strip()]
                
                for key_id in keys:
                    key_id = key_id.strip("'\"")
                    if not self._is_pgp_key_available(key_id):
                        missing_keys.append(key_id)
            
            return missing_keys
            
        except Exception as e:
            logger.error(f"Error suggesting PGP keys for {pkgbuild_path}: {e}")
            return []

    def fetch_pgp_keys(self, key_ids: List[str]) -> Dict[str, bool]:
        results = {}
        
        for key_id in key_ids:
            try:
                fetch_cmd = ['paru', '--pgpfetch', key_id]
                result = subprocess.run(fetch_cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    results[key_id] = True
                    logger.info(f"Successfully fetched PGP key: {key_id}")
                else:
                    success = self._attempt_key_import(key_id)
                    results[key_id] = success
                    
            except Exception as e:
                logger.error(f"Failed to fetch PGP key {key_id}: {e}")
                results[key_id] = False
        
        return results

    def _create_empty_result(self, pkgname: str, pkgver: str, error_msg: str) -> PkgbuildSecurityAnalysisResult:
        return PkgbuildSecurityAnalysisResult(
            pkgname=pkgname,
            pkgver=pkgver,
            overall_trust_level=RiskLevel.LOW,
            detected_risks=[DetectedRisk(RiskLevel.CRITICAL, error_msg, category="Internal Error")],
            raw_pkgbuild_content=error_msg
        )

    def _parse_pkgbuild_details_static(self, content: str) -> Tuple[str, str, str, Optional[str], List[str], Optional[str], List[str]]:
        pkgname = "unknown"
        pkgver = "unknown"
        pkgrel = "1"
        epoch = None
        source_urls = []
        project_url = None
        arch = ["any", "x86_64"]

        content_no_comments = re.sub(r'#.*$', '', content, flags=re.MULTILINE)

        pkgname_match = re.search(r'^\s*pkgname\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content_no_comments, re.MULTILINE)
        if pkgname_match: 
            pkgname = pkgname_match.group(1)

        pkgver_match = re.search(r'^\s*pkgver\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content_no_comments, re.MULTILINE)
        if pkgver_match: 
            pkgver = pkgver_match.group(1)

        pkgrel_match = re.search(r'^\s*pkgrel\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content_no_comments, re.MULTILINE)
        if pkgrel_match: 
            pkgrel = pkgrel_match.group(1)

        epoch_match = re.search(r'^\s*epoch\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content_no_comments, re.MULTILINE)
        if epoch_match: 
            epoch = epoch_match.group(1)

        url_match = re.search(r'^\s*url\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content_no_comments, re.MULTILINE)
        if url_match: 
            project_url = url_match.group(1)

        arch_match = re.search(r'^\s*arch\s*=\s*\(([^)]+)\)', content_no_comments, re.MULTILINE)
        if arch_match:
            arch_str = arch_match.group(1)
            arch = [a.strip().strip("'\"") for a in arch_str.split() if a.strip()]

        source_match = re.search(r'^\s*source\s*=\s*\(\s*([^\)]*)\s*\)', content_no_comments, re.MULTILINE | re.DOTALL)
        if source_match:
            sources_str = source_match.group(1)
            for line in sources_str.splitlines():
                line = line.strip()
                if not line: 
                    continue
                line = line.strip("'\"")
                line = re.sub(r'\$pkgname', pkgname, line)
                line = re.sub(r'\$pkgver', pkgver, line)
                if re.match(r'https?://', line): 
                    source_urls.append(line)

        if not source_urls:
            source_single_match = re.search(r'^\s*source\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content_no_comments, re.MULTILINE)
            if source_single_match:
                source_url = source_single_match.group(1)
                source_url = source_url.replace('$pkgname', pkgname).replace('$pkgver', pkgver)
                if re.match(r'https?://', source_url): 
                    source_urls.append(source_url)

        return pkgname, pkgver, pkgrel, epoch, source_urls, project_url, arch

    def _analyze_static_content(self, pkgbuild_content: str, result: PkgbuildSecurityAnalysisResult):
        lines = pkgbuild_content.splitlines()
        
        for i, line in enumerate(lines):
            line_num = i + 1
            
            for pattern in self.DANGEROUS_COMMAND_PATTERNS:
                if pattern.search(line) and not line.strip().startswith('#'):
                    risk = DetectedRisk(
                        level=RiskLevel.CRITICAL,
                        description=f"Dangerous command detected: '{line.strip()}'",
                        line_number=line_num,
                        snippet=line.strip(),
                        category="Command"
                    )
                    result.detected_risks.append(risk)
                    result.heatmap_lines.append((line_num, RiskLevel.CRITICAL, risk.description))
                    logger.warning(f"Dangerous command at line {line_num}: {line.strip()}")
                    break

        self._check_insecure_patterns(pkgbuild_content, result)
        self._analyze_function_sections(pkgbuild_content, result)

    def _check_insecure_patterns(self, content: str, result: PkgbuildSecurityAnalysisResult):
        lines = content.splitlines()
        
        for i, line in enumerate(lines):
            if line.strip().startswith('#'):
                continue
                
            for pattern, risk_level, description in self.INSECURE_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    risk = DetectedRisk(
                        level=risk_level,
                        description=description,
                        line_number=i + 1,
                        snippet=line.strip(),
                        category="Security"
                    )
                    result.detected_risks.append(risk)
                    result.heatmap_lines.append((i + 1, risk_level, description))

    def _analyze_function_sections(self, content: str, result: PkgbuildSecurityAnalysisResult):
        function_patterns = [
            ('prepare', RiskLevel.MEDIUM, "Source modification function"),
            ('build', RiskLevel.LOW, "Build process function"),
            ('check', RiskLevel.LOW, "Testing function"),
            ('package', RiskLevel.MEDIUM, "Installation function")
        ]
        
        for func_name, base_risk, description in function_patterns:
            func_match = re.search(rf'^{func_name}\s*\(\s*\)\s*{{(.*?)^}}', content, re.MULTILINE | re.DOTALL)
            if func_match:
                func_content = func_match.group(1)
                
                if re.search(r'\bsudo\b', func_content):
                    risk = DetectedRisk(
                        level=RiskLevel.HIGH,
                        description=f"Sudo usage in {func_name}() function",
                        category="Function"
                    )
                    result.detected_risks.append(risk)
                
                if re.search(r'\b(curl|wget).*\|\s*(bash|sh)\b', func_content):
                    risk = DetectedRisk(
                        level=RiskLevel.CRITICAL,
                        description=f"Remote code execution in {func_name}() function",
                        category="Function"
                    )
                    result.detected_risks.append(risk)

    def _analyze_source_urls(self, source_urls: List[str], project_url: Optional[str], result: PkgbuildSecurityAnalysisResult):
        all_urls = source_urls + ([project_url] if project_url else [])
        
        for url in all_urls:
            if not url: 
                continue

            if url.startswith("http://"):
                risk = DetectedRisk(
                    level=RiskLevel.HIGH,
                    description=f"Insecure HTTP source URL: '{url}'",
                    snippet=url,
                    category="Source"
                )
                result.detected_risks.append(risk)
                logger.warning(f"Insecure HTTP source: {url}")

            parsed_domain = re.match(r'https?://(?:www\.)?([^/]+)/.*', url)
            if parsed_domain:
                domain = parsed_domain.group(1)
                if not any(trusted_domain in domain for trusted_domain in self.TRUSTED_DOMAINS):
                    risk = DetectedRisk(
                        level=RiskLevel.MEDIUM,
                        description=f"Untrusted source domain: '{domain}'",
                        snippet=url,
                        category="Source"
                    )
                    result.detected_risks.append(risk)

            if re.search(r'\.(exe|msi|bat|cmd|scr|vbs)$', url, re.IGNORECASE):
                risk = DetectedRisk(
                    level=RiskLevel.HIGH,
                    description=f"Potentially dangerous file type: '{url}'",
                    snippet=url,
                    category="Source"
                )
                result.detected_risks.append(risk)

    def _fetch_aur_info(self, pkgname: str, result: PkgbuildSecurityAnalysisResult):
        if pkgname == "unknown":
            result.detected_risks.append(DetectedRisk(RiskLevel.LOW, "Cannot fetch AUR info: package name unknown", category="AUR"))
            return

        logger.info(f"Fetching AUR info for {pkgname}")
        
        try:
            paru_info_output = subprocess.run(
                ['paru', '-Si', pkgname],
                capture_output=True,
                text=True,
                timeout=15,
                check=False
            )

            if paru_info_output.returncode == 0:
                aur_data = self._parse_paru_si_output(paru_info_output.stdout)
                result.aur_info.update(aur_data)
                result.aur_info['status'] = 'found'

                maintainer = aur_data.get('Maintainer')
                pgp_verified = self._validate_maintainer_pgp(maintainer) if maintainer else False
                result.aur_info['maintainer_pgp_verified'] = pgp_verified
                
                if not pgp_verified:
                    result.detected_risks.append(DetectedRisk(
                        RiskLevel.MEDIUM, 
                        f"Maintainer '{maintainer}' PGP key not verified",
                        category="PGP"
                    ))

                votes = aur_data.get('Votes', 0)
                if isinstance(votes, int) and votes < 5:
                    result.detected_risks.append(DetectedRisk(
                        RiskLevel.MEDIUM, 
                        f"Low community support ({votes} votes)",
                        category="AUR"
                    ))

                days_since_update = aur_data.get('Days_Since_Update', -1)
                if days_since_update > 365:
                    result.detected_risks.append(DetectedRisk(
                        RiskLevel.MEDIUM, 
                        f"Package outdated ({days_since_update} days)",
                        category="AUR"
                    ))

            else:
                result.aur_info['status'] = 'not_found'
                result.detected_risks.append(DetectedRisk(
                    RiskLevel.MEDIUM, 
                    f"Package '{pkgname}' not found on AUR",
                    category="AUR"
                ))

        except FileNotFoundError:
            result.detected_risks.append(DetectedRisk(
                RiskLevel.CRITICAL, 
                "paru command not found",
                category="System"
            ))
        except subprocess.TimeoutExpired:
            result.detected_risks.append(DetectedRisk(
                RiskLevel.HIGH, 
                f"AUR info fetch timeout for {pkgname}",
                category="Network"
            ))
        except Exception as e:
            result.detected_risks.append(DetectedRisk(
                RiskLevel.CRITICAL, 
                f"Error fetching AUR info: {e}",
                category="AUR"
            ))

    def _parse_paru_si_output(self, output: str) -> Dict[str, Any]:
        data = {}
        lines = output.splitlines()
        
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().replace(" ", "_")
                data[key] = value.strip()

        if "Votes" in data:
            try: 
                data["Votes"] = int(data["Votes"])
            except ValueError: 
                pass
                
        if "Last_Update" in data:
            try:
                data["Last_Update_dt"] = datetime.strptime(data["Last_Update"].replace(" UTC", ""), "%Y-%m-%d %H:%M:%S")
                data["Days_Since_Update"] = (datetime.utcnow() - data["Last_Update_dt"]).days
            except ValueError:
                data["Days_Since_Update"] = -1

        return data

    def _check_cve_vulnerabilities(self, pkgname: str, pkgver: str, result: PkgbuildSecurityAnalysisResult):
        logger.info(f"Checking CVE vulnerabilities for {pkgname} v{pkgver}")
        
        if pkgname in self.cve_cache:
            cache_time, cached_results = self.cve_cache[pkgname]
            if time.time() - cache_time < 3600:
                result.cve_results = cached_results
                return

        try:
            cve_results = []
            search_terms = [pkgname, pkgname.replace('-', '_'), pkgname.replace('_', '-')]
            
            for term in search_terms[:2]:
                try:
                    response = requests.get(
                        f"{self.CVE_API_BASE}/search/{term}",
                        timeout=10,
                        headers={'User-Agent': 'SecurityAnalyzer/1.0'}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        for cve_item in data[:self.max_cve_results]:
                            if isinstance(cve_item, dict):
                                cve_id = cve_item.get('id', 'Unknown')
                                summary = cve_item.get('summary', 'No description available')
                                cvss_score = cve_item.get('cvss', 0)
                                
                                severity = self._calculate_cve_severity(cvss_score)
                                published = cve_item.get('Published', 'Unknown')
                                
                                cve_result = CVEResult(
                                    cve_id=cve_id,
                                    description=summary[:200] + "..." if len(summary) > 200 else summary,
                                    severity=severity,
                                    published_date=published
                                )
                                cve_results.append(cve_result)
                                
                                if severity in ['CRITICAL', 'HIGH']:
                                    risk_level = RiskLevel.HIGH if severity == 'HIGH' else RiskLevel.CRITICAL
                                    result.detected_risks.append(DetectedRisk(
                                        level=risk_level,
                                        description=f"CVE {cve_id} ({severity}): {summary[:100]}",
                                        category="CVE"
                                    ))
                    
                    time.sleep(self.api_rate_limit)
                    
                except requests.RequestException as e:
                    logger.warning(f"Failed to fetch CVE data for {term}: {e}")
                    continue
                    
            result.cve_results = cve_results[:self.max_cve_results]
            self.cve_cache[pkgname] = (time.time(), result.cve_results)
            
            logger.info(f"Found {len(result.cve_results)} CVE entries for {pkgname}")
                
        except Exception as e:
            logger.error(f"Error checking CVE vulnerabilities for {pkgname}: {e}")
            result.detected_risks.append(DetectedRisk(
                RiskLevel.LOW, 
                f"Could not check CVE vulnerabilities: {e}", 
                category="CVE"
            ))

    def _calculate_cve_severity(self, cvss_score: float) -> str:
        if cvss_score >= 9.0:
            return "CRITICAL"
        elif cvss_score >= 7.0:
            return "HIGH"
        elif cvss_score >= 4.0:
            return "MEDIUM"
        else:
            return "LOW"

    def _validate_pgp_signatures(self, pkgbuild_content: str, result: PkgbuildSecurityAnalysisResult):
        logger.info("Validating PGP signatures")
        
        pgp_results = {
            'has_pgp_signatures': False,
            'valid_signatures': [],
            'invalid_signatures': [],
            'missing_keys': [],
            'signature_files_found': False,
            'key_details': []
        }
        
        sig_pattern = re.search(r'validpgpkeys\s*=\s*\(([^)]+)\)', pkgbuild_content, re.MULTILINE)
        if sig_pattern:
            pgp_results['has_pgp_signatures'] = True
            keys_str = sig_pattern.group(1)
            keys = [key.strip().strip("'\"") for key in keys_str.split() if key.strip()]
            
            for key_id in keys:
                key_id = key_id.strip("'\"")
                if len(key_id) in [16, 40]:
                    validation_result = self._validate_pgp_key(key_id)
                    pgp_results['key_details'].append(validation_result)
                    
                    if validation_result['valid']:
                        pgp_results['valid_signatures'].append(key_id)
                    else:
                        pgp_results['invalid_signatures'].append(key_id)
                        if validation_result['missing']:
                            pgp_results['missing_keys'].append(key_id)
        
        sources_with_sig = re.findall(r'["\']([^"\']*\.sig)["\']', pkgbuild_content)
        if sources_with_sig:
            pgp_results['signature_files_found'] = True
        
        result.pgp_validation_results = pgp_results
        
        if pgp_results['has_pgp_signatures']:
            if pgp_results['invalid_signatures']:
                result.detected_risks.append(DetectedRisk(
                    RiskLevel.HIGH,
                    f"Invalid PGP keys: {', '.join(pgp_results['invalid_signatures'])}",
                    category="PGP"
                ))
            
            if pgp_results['missing_keys']:
                result.detected_risks.append(DetectedRisk(
                    RiskLevel.MEDIUM,
                    f"Missing PGP keys: {', '.join(pgp_results['missing_keys'])}",
                    category="PGP"
                ))
        else:
            if pgp_results['signature_files_found']:
                result.detected_risks.append(DetectedRisk(
                    RiskLevel.MEDIUM,
                    "Signature files found but no validpgpkeys defined",
                    category="PGP"
                ))
            else:
                result.detected_risks.append(DetectedRisk(
                    RiskLevel.LOW,
                    "No PGP signature validation configured",
                    category="PGP"
                ))

    def _validate_pgp_key(self, key_id: str) -> Dict[str, Any]:
        try:
            check_cmd = ['gpg', '--list-keys', key_id]
            result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                trust_output = subprocess.run(
                    ['gpg', '--list-keys', '--with-colons', key_id],
                    capture_output=True, text=True, timeout=10
                )
                
                trust_level = 'unknown'
                if trust_output.returncode == 0:
                    for line in trust_output.stdout.split('\n'):
                        if line.startswith('pub:'):
                            fields = line.split(':')
                            if len(fields) > 8:
                                trust_char = fields[8]
                                trust_map = {
                                    'e': 'expired',
                                    'q': 'undefined', 
                                    'n': 'never',
                                    'm': 'marginal',
                                    'f': 'full',
                                    'u': 'ultimate'
                                }
                                trust_level = trust_map.get(trust_char, 'unknown')
                
                return {
                    'valid': True,
                    'missing': False,
                    'trust_level': trust_level,
                    'key_id': key_id
                }
            else:
                return {
                    'valid': False,
                    'missing': True,
                    'trust_level': 'missing',
                    'key_id': key_id
                }
                    
        except subprocess.TimeoutExpired:
            logger.warning(f"PGP key validation timeout for {key_id}")
            return {'valid': False, 'missing': False, 'trust_level': 'timeout', 'key_id': key_id}
        except Exception as e:
            logger.error(f"Error validating PGP key {key_id}: {e}")
            return {'valid': False, 'missing': False, 'trust_level': 'error', 'key_id': key_id}

    def _is_pgp_key_available(self, key_id: str) -> bool:
        try:
            check_cmd = ['gpg', '--list-keys', key_id]
            result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception:
            return False

    def _attempt_key_import(self, key_id: str) -> bool:
        keyservers = [
            'hkps://keys.openpgp.org',
            'hkps://keyserver.ubuntu.com',
            'hkps://pgp.mit.edu'
        ]
        
        for keyserver in keyservers:
            try:
                import_cmd = ['gpg', '--keyserver', keyserver, '--recv-keys', key_id]
                result = subprocess.run(import_cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    logger.info(f"Successfully imported PGP key {key_id} from {keyserver}")
                    return True
                    
            except subprocess.TimeoutExpired:
                continue
            except Exception:
                continue
        
        return False

    def _validate_maintainer_pgp(self, maintainer: str) -> bool:
        if not maintainer:
            return False
            
        try:
            search_cmd = ['gpg', '--search-keys', maintainer]
            result = subprocess.run(search_cmd, capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0 and maintainer.lower() in result.stdout.lower():
                return True
                
            email_pattern = re.search(r'<([^>]+)>', maintainer)
            if email_pattern:
                email = email_pattern.group(1)
                search_cmd = ['gpg', '--search-keys', email]
                result = subprocess.run(search_cmd, capture_output=True, text=True, timeout=15)
                return result.returncode == 0
                
        except Exception as e:
            logger.warning(f"Error validating maintainer PGP for {maintainer}: {e}")
            
        return False

    def _calculate_overall_trust(self, result: PkgbuildSecurityAnalysisResult):
        score = 1.0

        for risk in result.detected_risks:
            if risk.level == RiskLevel.CRITICAL:
                score -= 0.5
            elif risk.level == RiskLevel.HIGH:
                score -= 0.2
            elif risk.level == RiskLevel.MEDIUM:
                score -= 0.1
            elif risk.level == RiskLevel.LOW:
                score -= 0.05
                
        score = max(0.0, score)

        aur_info = result.aur_info
        votes = aur_info.get("Votes", 0)
        days_since_update = aur_info.get("Days_Since_Update", -1)
        pgp_verified = aur_info.get("maintainer_pgp_verified", False)

        if isinstance(votes, int):
            if votes < 10:
                score -= 0.2
            elif votes < 50:
                score -= 0.05
            elif votes > 100:
                score += 0.1

        if days_since_update > 180 or days_since_update == -1:
            score -= 0.15
        elif days_since_update > 60:
            score -= 0.05

        if not pgp_verified:
            score -= 0.1

        if result.pgp_validation_results.get('has_pgp_signatures', False):
            if result.pgp_validation_results.get('valid_signatures'):
                score += 0.1
            if result.pgp_validation_results.get('invalid_signatures'):
                score -= 0.2

        critical_cves = sum(1 for cve in result.cve_results if cve.severity == 'CRITICAL')
        high_cves = sum(1 for cve in result.cve_results if cve.severity == 'HIGH')
        
        score -= critical_cves * 0.3
        score -= high_cves * 0.15

        score = max(0.0, min(1.0, score))
        result.overall_trust_score = score

        if score >= 0.8:
            result.overall_trust_level = RiskLevel.NONE
        elif score >= 0.6:
            result.overall_trust_level = RiskLevel.LOW
        elif score >= 0.3:
            result.overall_trust_level = RiskLevel.MEDIUM
        elif score >= 0.1:
            result.overall_trust_level = RiskLevel.HIGH
        else:
            result.overall_trust_level = RiskLevel.CRITICAL

    def _generate_heatmap_data(self, pkgbuild_content: str, result: PkgbuildSecurityAnalysisResult):
        lines = pkgbuild_content.splitlines()
        heatmap_annotations = {}

        for risk in result.detected_risks:
            if risk.line_number is not None:
                current_risk_level = heatmap_annotations.get(risk.line_number, (RiskLevel.NONE, ""))[0]
                if risk.level.value > current_risk_level.value:
                    heatmap_annotations[risk.line_number] = (risk.level, risk.description)

        result.heatmap_lines = []
        for line_num, (level, desc) in heatmap_annotations.items():
            result.heatmap_lines.append((line_num, level, desc))

        heatmap_text_lines = []
        for i, line in enumerate(lines):
            line_num = i + 1
            annotation = heatmap_annotations.get(line_num)
            if annotation:
                level, desc = annotation
                heatmap_text_lines.append(f"[{level.name}] {line}")
            else:
                heatmap_text_lines.append(line)

        result.heatmap_data = "\n".join(heatmap_text_lines)

    def _generate_security_suggestions(self, result: PkgbuildSecurityAnalysisResult):
        suggestions = []
        
        if result.overall_trust_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
            suggestions.append("Review this package manually before installation")
            
        if any(risk.category == "Command" for risk in result.detected_risks):
            suggestions.append("Package contains dangerous commands - verify maintainer intentions")
            
        if any(risk.category == "Source" for risk in result.detected_risks):
            suggestions.append("Verify source URLs and prefer HTTPS sources")
            
        if result.pgp_validation_results.get('missing_keys'):
            missing_keys = result.pgp_validation_results['missing_keys']
            suggestions.append(f"Import missing PGP keys: paru --pgpfetch {' '.join(missing_keys)}")
            
        if result.cve_results:
            critical_cves = [cve for cve in result.cve_results if cve.severity == 'CRITICAL']
            if critical_cves:
                suggestions.append("Critical CVE vulnerabilities found - consider alternatives")
            else:
                suggestions.append("Review CVE vulnerabilities for applicability")
            
        if result.aur_info.get('Votes', 0) < 10:
            suggestions.append("Low community adoption - consider well-maintained alternatives")
            
        if result.aur_info.get('Days_Since_Update', 0) > 365:
            suggestions.append("Package not recently updated - check for maintenance status")

        result.security_suggestions = suggestions

    def get_security_suggestions(self, result: PkgbuildSecurityAnalysisResult) -> List[str]:
        return result.security_suggestions
