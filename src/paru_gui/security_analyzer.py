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
    ]

    TRUSTED_DOMAINS = [
        "github.com", "gitlab.com", "aur.archlinux.org", "archlinux.org",
        "download.mozilla.org", "ftp.gnu.org", "kernel.org", "sourceforge.net",
        "bitbucket.org", "codeberg.org", "sr.ht", "pypi.org", "npmjs.com"
    ]

    CVE_API_BASE = "https://cve.circl.lu/api"
    NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"

    def __init__(self):
        logger.info("SecurityAnalyzer initialized.")
        self.upstream_checker = None
        self.cve_cache = {}
        self.pgp_keyring_path = os.path.expanduser("~/.gnupg")

    def set_upstream_checker(self, checker):
        self.upstream_checker = checker

    def analyze_pkgbuild(self, pkgbuild_path: str) -> PkgbuildSecurityAnalysisResult:
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
                aur_info={}
            )

            self._analyze_static_content(pkgbuild_content, analysis_result)
            self._analyze_source_urls(source_urls, project_url, analysis_result)
            self._fetch_aur_info(pkgname, analysis_result)
            self._check_cve_vulnerabilities(pkgname, pkgver, analysis_result)
            self._validate_pgp_signatures(pkgbuild_content, analysis_result)
            self._calculate_overall_trust(analysis_result)
            self._generate_heatmap_data(pkgbuild_content, analysis_result)

            logger.info(f"Completed security analysis for {pkgname} (v{pkgver}). Trust Level: {analysis_result.overall_trust_level.name}")
            return analysis_result

        except Exception as e:
            logger.exception(f"Unhandled error during PKGBUILD analysis for {pkgbuild_path}: {e}")
            return self._create_empty_result("N/A", "N/A", f"Analysis failed: {e}")

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
                line = line.strip("'\"")
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
        lines = pkgbuild_content.splitlines()
        extracted_sections: Dict[str, PkgbuildSection] = {}

        current_section = None
        current_section_content_lines = []
        section_start_line = -1

        for i, line in enumerate(lines):
            func_match = re.match(r'^\s*(pkgver|prepare|build|check|package)\s*\(\s*\)', line)
            source_array_match = re.match(r'^\s*source\s*=\s*\(', line)

            if func_match or source_array_match:
                if current_section:
                    extracted_sections[current_section.name] = PkgbuildSection(
                        name=current_section.name,
                        content="\n".join(current_section_content_lines),
                        start_line=section_start_line,
                        end_line=i - 1
                    )
                current_section_content_lines = []
                section_start_line = i + 1
                if func_match:
                    current_section = PkgbuildSection(name=func_match.group(1), content="", start_line=-1, end_line=-1)
                elif source_array_match:
                    current_section = PkgbuildSection(name="source_array", content="", start_line=-1, end_line=-1)
                continue

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

        if current_section and current_section_content_lines:
            extracted_sections[current_section.name] = PkgbuildSection(
                name=current_section.name,
                content="\n".join(current_section_content_lines),
                start_line=section_start_line,
                end_line=len(lines)
            )

        for i, line in enumerate(lines):
            line_num = i + 1
            for pattern in self.DANGEROUS_COMMAND_PATTERNS:
                if pattern.search(line):
                    if not line.strip().startswith('#'):
                        risk = DetectedRisk(
                            level=RiskLevel.CRITICAL,
                            description=f"Potential dangerous command detected: '{line.strip()}'",
                            line_number=line_num,
                            snippet=line.strip(),
                            category="Command"
                        )
                        result.detected_risks.append(risk)
                        result.heatmap_lines.append((line_num, RiskLevel.CRITICAL, risk.description))
                        logger.warning(f"Static risk: {risk.description} at line {line_num}")
                        break

        self._check_insecure_patterns(pkgbuild_content, result)

    def _check_insecure_patterns(self, content: str, result: PkgbuildSecurityAnalysisResult):
        insecure_patterns = [
            (r'sha\d+sums=\([^)]*[\'"]SKIP[\'"][^)]*\)', RiskLevel.HIGH, "Checksum verification skipped (SKIP found)"),
            (r'--disable-ssl-verify', RiskLevel.HIGH, "SSL verification disabled"),
            (r'--no-check-certificate', RiskLevel.HIGH, "Certificate checking disabled"),
            (r'\bsu\s+-\s+root', RiskLevel.MEDIUM, "Direct root access attempted"),
            (r'\bpkexec\b', RiskLevel.MEDIUM, "PolicyKit execution detected"),
        ]

        lines = content.splitlines()
        for i, line in enumerate(lines):
            for pattern, risk_level, description in insecure_patterns:
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

    def _analyze_source_urls(self, source_urls: List[str], project_url: Optional[str], result: PkgbuildSecurityAnalysisResult):
        all_urls = source_urls + ([project_url] if project_url else [])
        for url in all_urls:
            if not url: continue

            if url.startswith("http://"):
                risk = DetectedRisk(
                    level=RiskLevel.HIGH,
                    description=f"Insecure source URL (HTTP) detected: '{url}'. Consider HTTPS.",
                    snippet=url,
                    category="Source"
                )
                result.detected_risks.append(risk)
                logger.warning(f"Source risk: {risk.description}")

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

            if re.search(r'\.(exe|msi|bat|cmd|scr|vbs)$', url, re.IGNORECASE):
                risk = DetectedRisk(
                    level=RiskLevel.HIGH,
                    description=f"Potentially dangerous file type in source: '{url}'",
                    snippet=url,
                    category="Source"
                )
                result.detected_risks.append(risk)

    def _fetch_aur_info(self, pkgname: str, result: PkgbuildSecurityAnalysisResult):
        if pkgname == "unknown":
            result.detected_risks.append(DetectedRisk(RiskLevel.LOW, "Cannot fetch AUR info: pkgname unknown.", category="AUR"))
            return

        logger.info(f"Fetching AUR info for {pkgname}...")
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
                        RiskLevel.MEDIUM, f"Maintainer '{maintainer}' does not have a verified PGP key or key could not be checked.",
                        category="PGP"
                    ))
                    logger.warning(f"PGP risk: Maintainer PGP not verified for {pkgname}")

                votes = aur_data.get('Votes', 0)
                if isinstance(votes, int) and votes < 5:
                    result.detected_risks.append(DetectedRisk(
                        RiskLevel.MEDIUM, f"Package has low community support (only {votes} votes)",
                        category="AUR"
                    ))

                days_since_update = aur_data.get('Days_Since_Update', -1)
                if days_since_update > 365:
                    result.detected_risks.append(DetectedRisk(
                        RiskLevel.MEDIUM, f"Package not updated in {days_since_update} days",
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
        data = {}
        lines = output.splitlines()
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().replace(" ", "_")
                data[key] = value.strip()

        if "Votes" in data:
            try: data["Votes"] = int(data["Votes"])
            except ValueError: pass
        if "Last_Update" in data:
            try:
                data["Last_Update_dt"] = datetime.strptime(data["Last_Update"].replace(" UTC", ""), "%Y-%m-%d %H:%M:%S")
                data["Days_Since_Update"] = (datetime.utcnow() - data["Last_Update_dt"]).days
            except ValueError:
                logger.warning(f"Could not parse Last_Update: {data['Last_Update']}")
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
            
            for term in search_terms:
                try:
                    response = requests.get(
                        f"{self.CVE_API_BASE}/search/{term}",
                        timeout=10,
                        headers={'User-Agent': 'SecurityAnalyzer/1.0'}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        for cve_item in data[:5]:
                            if isinstance(cve_item, dict):
                                cve_id = cve_item.get('id', 'Unknown')
                                summary = cve_item.get('summary', 'No description available')
                                cvss_score = cve_item.get('cvss', 0)
                                
                                severity = "LOW"
                                if cvss_score >= 9.0:
                                    severity = "CRITICAL"
                                elif cvss_score >= 7.0:
                                    severity = "HIGH"
                                elif cvss_score >= 4.0:
                                    severity = "MEDIUM"
                                
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
                                        description=f"CVE found: {cve_id} ({severity}) - {summary[:100]}",
                                        category="CVE"
                                    ))
                    
                    time.sleep(1)
                    
                except requests.RequestException as e:
                    logger.warning(f"Failed to fetch CVE data for {term}: {e}")
                    continue
                    
            result.cve_results = cve_results
            self.cve_cache[pkgname] = (time.time(), cve_results)
            
            if not cve_results:
                logger.info(f"No CVE vulnerabilities found for {pkgname}")
            else:
                logger.info(f"Found {len(cve_results)} CVE entries for {pkgname}")
                
        except Exception as e:
            logger.error(f"Error checking CVE vulnerabilities for {pkgname}: {e}")
            result.detected_risks.append(DetectedRisk(
                RiskLevel.LOW, 
                f"Could not check CVE vulnerabilities: {e}", 
                category="CVE"
            ))

    def _validate_pgp_signatures(self, pkgbuild_content: str, result: PkgbuildSecurityAnalysisResult):
        logger.info("Validating PGP signatures")
        
        pgp_results = {
            'has_pgp_signatures': False,
            'valid_signatures': [],
            'invalid_signatures': [],
            'missing_keys': [],
            'signature_files_found': False
        }
        
        sig_pattern = re.search(r'validpgpkeys\s*=\s*\(([^)]+)\)', pkgbuild_content, re.MULTILINE)
        if sig_pattern:
            pgp_results['has_pgp_signatures'] = True
            keys_str = sig_pattern.group(1)
            keys = [key.strip().strip("'\"") for key in keys_str.split() if key.strip()]
            
            for key_id in keys:
                key_id = key_id.strip("'\"")
                if len(key_id) == 16 or len(key_id) == 40:
                    validation_result = self._validate_pgp_key(key_id)
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
                    f"Invalid or missing PGP keys found: {', '.join(pgp_results['invalid_signatures'])}",
                    category="PGP"
                ))
            
            if pgp_results['missing_keys']:
                result.detected_risks.append(DetectedRisk(
                    RiskLevel.MEDIUM,
                    f"PGP keys not found in keyring: {', '.join(pgp_results['missing_keys'])}. Consider importing them.",
                    category="PGP"
                ))
            
            if pgp_results['valid_signatures']:
                logger.info(f"Valid PGP signatures found: {', '.join(pgp_results['valid_signatures'])}")
        else:
            if pgp_results['signature_files_found']:
                result.detected_risks.append(DetectedRisk(
                    RiskLevel.MEDIUM,
                    "Signature files found but no validpgpkeys array defined",
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
                try_import = self._attempt_key_import(key_id)
                if try_import:
                    return {
                        'valid': True,
                        'missing': False,
                        'trust_level': 'imported',
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
            logger.warning(f"PGP key validation timed out for {key_id}")
            return {'valid': False, 'missing': False, 'trust_level': 'timeout', 'key_id': key_id}
        except Exception as e:
            logger.error(f"Error validating PGP key {key_id}: {e}")
            return {'valid': False, 'missing': False, 'trust_level': 'error', 'key_id': key_id}

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
                logger.warning(f"Key import timed out for {key_id} from {keyserver}")
                continue
            except Exception as e:
                logger.warning(f"Failed to import key {key_id} from {keyserver}: {e}")
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

    def get_security_suggestions(self, result: PkgbuildSecurityAnalysisResult) -> List[str]:
        suggestions = []
        
        if result.overall_trust_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
            suggestions.append("Consider reviewing this package manually before installation")
            
        if any(risk.category == "Command" for risk in result.detected_risks):
            suggestions.append("Package contains potentially dangerous commands - verify the maintainer's intentions")
            
        if any(risk.category == "Source" for risk in result.detected_risks):
            suggestions.append("Consider verifying source URLs and using HTTPS when possible")
            
        if result.pgp_validation_results.get('missing_keys'):
            missing_keys = result.pgp_validation_results['missing_keys']
            suggestions.append(f"Import missing PGP keys: gpg --recv-keys {' '.join(missing_keys)}")
            
        if result.cve_results:
            suggestions.append("Review CVE vulnerabilities and check if they affect your use case")
            
        if result.aur_info.get('Votes', 0) < 10:
            suggestions.append("Package has low community adoption - consider alternatives")
            
        return suggestions
