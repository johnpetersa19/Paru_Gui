from typing import List, Dict, Any, Optional, Tuple
import os
import re
import subprocess
import tempfile
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum


class PackageType(Enum):
    BINARY = "binary"
    SOURCE = "source"
    SPLIT = "split"
    GROUP = "group"


class SecurityLevel(Enum):
    SAFE = "safe"
    CAUTION = "caution"
    WARNING = "warning"
    DANGER = "danger"


@dataclass
class PKGBUILDInfo:
    pkgname: str = ""
    pkgver: str = ""
    pkgrel: str = ""
    pkgdesc: str = ""
    arch: List[str] = field(default_factory=list)
    url: str = ""
    license: List[str] = field(default_factory=list)
    depends: List[str] = field(default_factory=list)
    makedepends: List[str] = field(default_factory=list)
    optdepends: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    replaces: List[str] = field(default_factory=list)
    source: List[str] = field(default_factory=list)
    sha256sums: List[str] = field(default_factory=list)
    md5sums: List[str] = field(default_factory=list)
    sha512sums: List[str] = field(default_factory=list)
    backup: List[str] = field(default_factory=list)
    options: List[str] = field(default_factory=list)
    install: str = ""
    changelog: str = ""
    validpgpkeys: List[str] = field(default_factory=list)
    epoch: str = ""
    groups: List[str] = field(default_factory=list)
    has_build_function: bool = False
    has_package_function: bool = False
    has_prepare_function: bool = False
    has_check_function: bool = False
    is_valid: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    security_level: SecurityLevel = SecurityLevel.SAFE
    file_path: str = ""


@dataclass
class PackageInfo:
    pkgname: str = ""
    pkgbase: str = ""
    pkgver: str = ""
    pkgdesc: str = ""
    arch: str = ""
    url: str = ""
    license: List[str] = field(default_factory=list)
    groups: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    depends: List[str] = field(default_factory=list)
    optdepends: List[str] = field(default_factory=list)
    makedepends: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    replaces: List[str] = field(default_factory=list)
    backup: List[str] = field(default_factory=list)
    packager: str = ""
    builddate: str = ""
    installdate: str = ""
    size: int = 0
    reason: int = 0
    validation: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    file_count: int = 0
    compressed_size: int = 0
    package_type: PackageType = PackageType.BINARY
    is_valid: bool = False
    errors: List[str] = field(default_factory=list)
    file_path: str = ""


class FileUtils:

    def __init__(self):
        self.temp_dirs: List[str] = []
        self.supported_compressions = ['.xz', '.zst', '.gz', '.bz2']
        self.dangerous_commands = [
            'rm -rf', 'sudo', 'su ', 'wget', 'curl', 'git clone',
            'chmod +x', 'chown', 'dd ', 'mkfs', 'mount', 'umount'
        ]

    def __del__(self):
        self.cleanup_temp_dirs()

    def cleanup_temp_dirs(self):
        for temp_dir in self.temp_dirs:
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            except Exception:
                pass
        self.temp_dirs.clear()

    def analyze_pkgbuild(self, pkgbuild_path: str) -> PKGBUILDInfo:
        info = PKGBUILDInfo(file_path=pkgbuild_path)

        if not os.path.exists(pkgbuild_path):
            info.errors.append("PKGBUILD file not found")
            return info

        try:
            with open(pkgbuild_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(pkgbuild_path, 'r', encoding='latin-1') as f:
                    content = f.read()
            except Exception as e:
                info.errors.append(f"Failed to read file: {e}")
                return info
        except Exception as e:
            info.errors.append(f"Failed to read file: {e}")
            return info

        info = self._parse_pkgbuild_content(content, info)
        info = self._validate_pkgbuild(info)
        info = self._analyze_security(content, info)

        return info

    def analyze_package(self, package_path: str) -> PackageInfo:
        info = PackageInfo(file_path=package_path)

        if not os.path.exists(package_path):
            info.errors.append("Package file not found")
            return info

        if not self._is_valid_package_file(package_path):
            info.errors.append("Invalid package file format")
            return info

        try:
            info.compressed_size = os.path.getsize(package_path)

            temp_dir = tempfile.mkdtemp()
            self.temp_dirs.append(temp_dir)

            pkginfo_content = self._extract_pkginfo(package_path, temp_dir)
            if pkginfo_content:
                info = self._parse_pkginfo_content(pkginfo_content, info)
            else:
                info.errors.append("Failed to extract .PKGINFO")
                return info

            file_list = self._extract_file_list(package_path)
            if file_list:
                info.files = file_list
                info.file_count = len(file_list)

            info.is_valid = len(info.errors) == 0

        except Exception as e:
            info.errors.append(f"Failed to analyze package: {e}")

        return info

    def extract_source_files(self, pkgbuild_path: str, dest_dir: str) -> Tuple[bool, List[str]]:
        extracted_files = []

        if not os.path.exists(pkgbuild_path):
            return False, ["PKGBUILD not found"]

        pkgbuild_info = self.analyze_pkgbuild(pkgbuild_path)
        if not pkgbuild_info.is_valid:
            return False, pkgbuild_info.errors

        work_dir = os.path.dirname(pkgbuild_path)

        try:
            for source in pkgbuild_info.source:
                source_clean = self._clean_source_url(source)

                if self._is_url(source_clean):
                    filename = self._get_filename_from_url(source_clean)
                    dest_path = os.path.join(dest_dir, filename)

                    if self._download_file(source_clean, dest_path):
                        extracted_files.append(dest_path)
                else:
                    source_path = os.path.join(work_dir, source_clean)
                    dest_path = os.path.join(dest_dir, os.path.basename(source_clean))

                    if os.path.exists(source_path):
                        shutil.copy2(source_path, dest_path)
                        extracted_files.append(dest_path)

        except Exception as e:
            return False, [f"Extraction failed: {e}"]

        return len(extracted_files) > 0, extracted_files

    def validate_checksums(self, pkgbuild_path: str) -> Tuple[bool, Dict[str, Any]]:
        if not os.path.exists(pkgbuild_path):
            return False, {"error": "PKGBUILD not found"}

        pkgbuild_info = self.analyze_pkgbuild(pkgbuild_path)
        work_dir = os.path.dirname(pkgbuild_path)

        validation_results = {
            "valid": True,
            "results": {},
            "missing_files": [],
            "checksum_mismatches": [],
            "warnings": []
        }

        try:
            for i, source in enumerate(pkgbuild_info.source):
                source_clean = self._clean_source_url(source)

                if self._is_url(source_clean):
                    filename = self._get_filename_from_url(source_clean)
                else:
                    filename = source_clean

                file_path = os.path.join(work_dir, filename)

                if not os.path.exists(file_path):
                    validation_results["missing_files"].append(filename)
                    validation_results["valid"] = False
                    continue

                expected_checksums = {
                    'sha256': pkgbuild_info.sha256sums[i] if i < len(pkgbuild_info.sha256sums) else None,
                    'md5': pkgbuild_info.md5sums[i] if i < len(pkgbuild_info.md5sums) else None,
                    'sha512': pkgbuild_info.sha512sums[i] if i < len(pkgbuild_info.sha512sums) else None
                }

                file_results = {"filename": filename, "checksums": {}}

                for hash_type, expected in expected_checksums.items():
                    if expected and expected != 'SKIP':
                        actual = self._calculate_checksum(file_path, hash_type)
                        file_results["checksums"][hash_type] = {
                            "expected": expected,
                            "actual": actual,
                            "match": actual == expected
                        }

                        if actual != expected:
                            validation_results["checksum_mismatches"].append({
                                "file": filename,
                                "hash_type": hash_type,
                                "expected": expected,
                                "actual": actual
                            })
                            validation_results["valid"] = False

                validation_results["results"][filename] = file_results

        except Exception as e:
            validation_results["error"] = str(e)
            validation_results["valid"] = False

        return validation_results["valid"], validation_results

    def get_package_dependencies(self, pkgbuild_path: str) -> Dict[str, List[str]]:
        pkgbuild_info = self.analyze_pkgbuild(pkgbuild_path)

        return {
            "depends": pkgbuild_info.depends,
            "makedepends": pkgbuild_info.makedepends,
            "optdepends": pkgbuild_info.optdepends,
            "conflicts": pkgbuild_info.conflicts,
            "provides": pkgbuild_info.provides,
            "replaces": pkgbuild_info.replaces
        }

    def _parse_pkgbuild_content(self, content: str, info: PKGBUILDInfo) -> PKGBUILDInfo:
        single_patterns = {
            'pkgname': r'^pkgname=(.+?)$',
            'pkgver': r'^pkgver=(.+?)$',
            'pkgrel': r'^pkgrel=(.+?)$',
            'pkgdesc': r'^pkgdesc=(.+?)$',
            'url': r'^url=(.+?)$',
            'install': r'^install=(.+?)$',
            'changelog': r'^changelog=(.+?)$',
            'epoch': r'^epoch=(.+?)$',
            'pkgbase': r'^pkgbase=(.+?)$'
        }

        array_patterns = {
            'arch': r'^arch=\(([^)]+)\)$',
            'license': r'^license=\(([^)]+)\)$',
            'depends': r'^depends=\(([^)]+)\)$',
            'makedepends': r'^makedepends=\(([^)]+)\)$',
            'optdepends': r'^optdepends=\(([^)]+)\)$',
            'provides': r'^provides=\(([^)]+)\)$',
            'conflicts': r'^conflicts=\(([^)]+)\)$',
            'replaces': r'^replaces=\(([^)]+)\)$',
            'source': r'^source=\(([^)]+)\)$',
            'sha256sums': r'^sha256sums=\(([^)]+)\)$',
            'md5sums': r'^md5sums=\(([^)]+)\)$',
            'sha512sums': r'^sha512sums=\(([^)]+)\)$',
            'backup': r'^backup=\(([^)]+)\)$',
            'options': r'^options=\(([^)]+)\)$',
            'groups': r'^groups=\(([^)]+)\)$',
            'validpgpkeys': r'^validpgpkeys=\(([^)]+)\)$'
        }

        for field, pattern in single_patterns.items():
            matches = re.findall(pattern, content, re.MULTILINE)
            if matches:
                setattr(info, field, self._clean_quoted_string(matches[0]))

        for field, pattern in array_patterns.items():
            matches = re.findall(pattern, content, re.MULTILINE)
            if matches:
                array_content = matches[0]
                items = self._parse_bash_array(array_content)
                setattr(info, field, items)

        info.has_build_function = bool(re.search(r'^build\s*\(\s*\)\s*{', content, re.MULTILINE))
        info.has_package_function = bool(re.search(r'^package(?:_[\w]+)?\s*\(\s*\)\s*{', content, re.MULTILINE))
        info.has_prepare_function = bool(re.search(r'^prepare\s*\(\s*\)\s*{', content, re.MULTILINE))
        info.has_check_function = bool(re.search(r'^check\s*\(\s*\)\s*{', content, re.MULTILINE))

        return info

    def _parse_pkginfo_content(self, content: str, info: PackageInfo) -> PackageInfo:
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if '=' not in line:
                continue

            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()

            if key in ['pkgname', 'pkgbase', 'pkgver', 'pkgdesc', 'arch', 'url', 'packager', 'builddate', 'installdate']:
                setattr(info, key, value)
            elif key == 'size':
                info.size = int(value) if value.isdigit() else 0
            elif key == 'reason':
                info.reason = int(value) if value.isdigit() else 0
            elif key in ['license', 'groups', 'provides', 'depends', 'optdepends', 'makedepends', 'conflicts', 'replaces', 'backup', 'validation']:
                current_list = getattr(info, key, [])
                current_list.append(value)
                setattr(info, key, current_list)

        info.is_valid = bool(info.pkgname and info.pkgver)
        return info

    def _validate_pkgbuild(self, info: PKGBUILDInfo) -> PKGBUILDInfo:
        required_fields = ['pkgname', 'pkgver', 'pkgrel']
        missing_required = [field for field in required_fields if not getattr(info, field)]

        if missing_required:
            info.errors.extend([f"Missing required field: {field}" for field in missing_required])

        if not info.arch:
            info.warnings.append("No architecture specified")
        elif 'any' not in info.arch and not any(arch in ['x86_64', 'i686', 'arm', 'armv7h', 'aarch64'] for arch in info.arch):
            info.warnings.append("Unusual architecture specification")

        if not info.license:
            info.warnings.append("No license specified")

        if info.source and not (info.sha256sums or info.md5sums or info.sha512sums):
            info.warnings.append("Source files without checksums")

        if not info.has_build_function and not info.has_package_function:
            info.warnings.append("No build() or package() function found")

        if info.pkgver and not re.match(r'^[0-9]+(\.[0-9a-zA-Z]+)*$', info.pkgver):
            info.warnings.append("Unusual version format")

        info.is_valid = len(info.errors) == 0
        return info

    def _analyze_security(self, content: str, info: PKGBUILDInfo) -> PKGBUILDInfo:
        security_score = 0

        for dangerous_cmd in self.dangerous_commands:
            if dangerous_cmd in content:
                info.warnings.append(f"Contains potentially dangerous command: {dangerous_cmd}")
                security_score += 2

        if re.search(r'curl.*\|\s*bash', content) or re.search(r'wget.*\|\s*sh', content):
            info.warnings.append("Downloads and executes scripts directly")
            security_score += 3

        if 'sudo' in content:
            info.warnings.append("Uses sudo - requires elevated privileges")
            security_score += 2

        if not info.validpgpkeys and any('git+' in src or 'svn+' in src for src in info.source):
            info.warnings.append("VCS sources without PGP verification")
            security_score += 1

        if any(checksum == 'SKIP' for checksum in info.sha256sums + info.md5sums + info.sha512sums):
            info.warnings.append("Some sources skip checksum verification")
            security_score += 1

        if security_score == 0:
            info.security_level = SecurityLevel.SAFE
        elif security_score <= 2:
            info.security_level = SecurityLevel.CAUTION
        elif security_score <= 4:
            info.security_level = SecurityLevel.WARNING
        else:
            info.security_level = SecurityLevel.DANGER

        return info

    def _extract_pkginfo(self, package_path: str, temp_dir: str) -> Optional[str]:
        try:
            result = subprocess.run([
                'tar', '--extract', '--file', package_path,
                '--directory', temp_dir,
                '.PKGINFO'
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                pkginfo_path = os.path.join(temp_dir, '.PKGINFO')
                if os.path.exists(pkginfo_path):
                    with open(pkginfo_path, 'r', encoding='utf-8') as f:
                        return f.read()
            return None

        except Exception:
            return None

    def _extract_file_list(self, package_path: str) -> Optional[List[str]]:
        try:
            result = subprocess.run([
                'tar', '--list', '--file', package_path
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                files = [line.strip() for line in result.stdout.split('\n') if line.strip()]
                return [f for f in files if not f.startswith('.')]
            return None

        except Exception:
            return None

    def _is_valid_package_file(self, file_path: str) -> bool:
        if not os.path.isfile(file_path):
            return False

        filename = os.path.basename(file_path)
        return any(filename.endswith(f'.pkg.tar{ext}') for ext in self.supported_compressions)

    def _clean_quoted_string(self, s: str) -> str:
        s = s.strip()
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1]
        return s

    def _parse_bash_array(self, array_content: str) -> List[str]:
        items = []
        current_item = ""
        in_quotes = False
        quote_char = None

        i = 0
        while i < len(array_content):
            char = array_content[i]

            if not in_quotes:
                if char in ['"', "'"]:
                    in_quotes = True
                    quote_char = char
                elif char in [' ', '\t', '\n']:
                    if current_item.strip():
                        items.append(current_item.strip())
                        current_item = ""
                else:
                    current_item += char
            else:
                if char == quote_char:
                    in_quotes = False
                    quote_char = None
                else:
                    current_item += char

            i += 1

        if current_item.strip():
            items.append(current_item.strip())

        return [self._clean_quoted_string(item) for item in items if item.strip()]

    def _clean_source_url(self, source: str) -> str:
        if '::' in source:
            return source.split('::', 1)[1]
        return source

    def _is_url(self, s: str) -> bool:
        return s.startswith(('http://', 'https://', 'ftp://', 'ftps://'))

    def _get_filename_from_url(self, url: str) -> str:
        return os.path.basename(url.split('?')[0])

    def _download_file(self, url: str, dest_path: str) -> bool:
        try:
            result = subprocess.run([
                'curl', '-L', '-o', dest_path, url
            ], capture_output=True, timeout=120)
            return result.returncode == 0 and os.path.exists(dest_path)
        except Exception:
            return False

    def _calculate_checksum(self, file_path: str, hash_type: str) -> Optional[str]:
        hash_commands = {
            'md5': ['md5sum'],
            'sha256': ['sha256sum'],
            'sha512': ['sha512sum']
        }

        if hash_type not in hash_commands:
            return None

        try:
            result = subprocess.run(
                hash_commands[hash_type] + [file_path],
                capture_output=True, text=True, timeout=60
            )

            if result.returncode == 0:
                return result.stdout.split()[0]
            return None

        except Exception:
            return None
