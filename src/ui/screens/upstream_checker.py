import re
import os
import subprocess
import logging
import json
import time
import hashlib
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass, field
import shlex
from datetime import datetime

# Basic logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("upstream_checker")

class HostType(Enum):
    """Supported repository types"""
    GITHUB = "GitHub"
    GITLAB = "GitLab"
    GITLAB_SELF_HOSTED = "GitLab (Self-Hosted)"
    GITEA = "Gitea"
    SOURCEHUT = "SourceHut"
    GENERIC_DOWNLOAD = "Generic Download"
    UNKNOWN = "Unknown"

@dataclass
class UpstreamInfo:
    """Information about the upstream version"""
    host_type: HostType
    version: Optional[str] = None
    release_date: Optional[str] = None
    changelog_url: Optional[str] = None
    cve_fix_info: Optional[str] = None
    repo_details: Dict[str, Any] = field(default_factory=dict)
    raw_data: Optional[Dict[str, Any]] = field(default_factory=dict)

@dataclass
class PkgbuildUpstreamDetails:
    """Details extracted from the PKGBUILD"""
    pkgname: str
    pkgver: str
    pkgrel: str = "1"
    epoch: Optional[str] = None
    source_urls: List[str] = field(default_factory=list)
    project_url: Optional[str] = None
    arch: List[str] = field(default_factory=lambda: ["any", "x86_64"])

class CacheManager:
    """Cache manager for check results"""

    def __init__(self, cache_dir: Optional[str] = None, ttl: int = 86400):
        """
        Initializes the cache manager.

        Args:
            cache_dir: Directory to store the cache (default: ~/.cache/upstream_checker)
            ttl: Cache Time-To-Live in seconds (default: 24 hours)
        """
        self.ttl = ttl
        self.cache_dir = cache_dir or os.path.join(
            os.path.expanduser("~"),
            ".cache",
            "upstream_checker"
        )

        os.makedirs(self.cache_dir, exist_ok=True)
        logger.debug(f"Cache directory: {self.cache_dir}")

    def _get_cache_key(self, pkgbuild_id: str) -> str:
        """Generates a secure cache key based on the ID"""
        return hashlib.sha256(pkgbuild_id.encode()).hexdigest()

    def _get_cache_file_path(self, cache_key: str) -> str:
        """Gets the full path to the cache file"""
        return os.path.join(self.cache_dir, f"{cache_key}.json")

    def get_cached_update(self, pkgbuild_id: str) -> Optional[UpstreamInfo]:
        """
        Retrieves cached update information, if valid.

        Args:
            pkgbuild_id: Unique identifier for the PKGBUILD

        Returns:
            UpstreamInfo if valid cache exists, None otherwise
        """
        cache_key = self._get_cache_key(pkgbuild_id)
        cache_file = self._get_cache_file_path(cache_key)

        if not os.path.exists(cache_file):
            logger.debug(f"Cache file {cache_file} does not exist")
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            current_time = time.time()
            if current_time - cache_data.get('timestamp', 0) > self.ttl:
                logger.debug(f"Cache expired for {pkgbuild_id}")
                return None

            upstream_info = UpstreamInfo(
                host_type=HostType(cache_data['host_type']),
                version=cache_data.get('version'),
                release_date=cache_data.get('release_date'),
                changelog_url=cache_data.get('changelog_url'),
                cve_fix_info=cache_data.get('cve_fix_info'),
                repo_details=cache_data.get('repo_details', {}),
                raw_data=cache_data.get('raw_data', {})
            )
            logger.info(f"Successfully retrieved cached data for {pkgbuild_id}")
            return upstream_info

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Error reading cache for {pkgbuild_id}: {str(e)}")
            return None

    def set_cached_update(self, pkgbuild_id: str, info: UpstreamInfo):
        """
        Stores update information in cache.

        Args:
            pkgbuild_id: Unique identifier for the PKGBUILD
            info: Update information to cache
        """
        cache_key = self._get_cache_key(pkgbuild_id)
        cache_file = self._get_cache_file_path(cache_key)

        cache_data = {
            'timestamp': time.time(),
            'host_type': info.host_type.value,
            'version': info.version,
            'release_date': info.release_date,
            'changelog_url': info.changelog_url,
            'cve_fix_info': info.cve_fix_info,
            'repo_details': info.repo_details,
            'raw_data': info.raw_data
        }

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            logger.info(f"Successfully cached data for {pkgbuild_id}")
        except Exception as e:
            logger.error(f"Failed to write cache for {pkgbuild_id}: {str(e)}")

    def clear_expired_cache(self):
        """Removes all expired cache files"""
        current_time = time.time()
        cleared = 0

        for filename in os.listdir(self.cache_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(self.cache_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)

                    if current_time - cache_data.get('timestamp', 0) > self.ttl:
                        os.remove(file_path)
                        cleared += 1
                except Exception as e:
                    logger.warning(f"Failed to clear cache file {file_path}: {e}")
                    continue

        if cleared > 0:
            logger.info(f"Cleared {cleared} expired cache entries")
        return cleared

class VersionUtils:
    """Utilities for version manipulation and comparison"""

    @staticmethod
    def normalize_version(version: str) -> str:
        """
        Normalizes a version string for comparison.

        Args:
            version: Version string to normalize

        Returns:
            Normalized version (without 'v' prefixes, with consistent separators)
        """
        if not version:
            return ""

        normalized = re.sub(r'^[vVrR]', '', version)
        normalized = normalized.replace('_', '.').replace('-', '.')
        normalized = re.sub(r'\.release\.?$', '', normalized, flags=re.IGNORECASE)

        return normalized

    @staticmethod
    def compare_versions(current: str, upstream: str) -> int:
        """
        Compares two versions.

        Args:
            current: Current version
            upstream: Upstream version

        Returns:
            -1 if current < upstream
             0 if current == upstream
             1 if current > upstream
        """
        current_norm = VersionUtils.normalize_version(current)
        upstream_norm = VersionUtils.normalize_version(upstream)

        try:
            current_parts = [int(x) for x in re.findall(r'\d+', current_norm)]
            upstream_parts = [int(x) for x in re.findall(r'\d+', upstream_norm)]

            for i in range(max(len(current_parts), len(upstream_parts))):
                current_val = current_parts[i] if i < len(current_parts) else 0
                upstream_val = upstream_parts[i] if i < len(upstream_parts) else 0

                if current_val < upstream_val:
                    return -1
                elif current_val > upstream_val:
                    return 1

            return 0
        except (ValueError, TypeError):
            if current_norm < upstream_norm:
                return -1
            elif current_norm > upstream_norm:
                return 1
            return 0

    @staticmethod
    def is_prerelease(version: str) -> bool:
        """
        Checks if a version is a pre-release.

        Args:
            version: Version string to check

        Returns:
            True if it's a pre-release, False otherwise
        """
        version_lower = version.lower()
        return any(marker in version_lower for marker in
                  ['alpha', 'beta', 'rc', 'pre', 'dev', 'snapshot', 'git'])


class UpstreamChecker:
    """
    Main upstream update checker.
    [x] All core functionalities for update checking.
    [ ] Architectural Decision: Remove redundant GitHubCommandBuilder and GitLabCommandBuilder classes.
    [~] NVDIntegration.check_cves call needs to be asynchronous from GUI. (Current implementation is blocking).
    """

    def __init__(self, cache_dir: Optional[str] = None, cache_ttl: int = 86400):
        self.cache_manager = CacheManager(cache_dir, cache_ttl)
        self.version_utils = VersionUtils()
        logger.info("UpstreamChecker initialized")

    def _parse_pkgbuild_for_upstream_info(self, pkgbuild_path: str) -> Optional[PkgbuildUpstreamDetails]:
        """
        Parses the PKGBUILD to extract upstream information.
        Handles multi-line arrays, interpolated variables, and comments.
        """
        if not os.path.exists(pkgbuild_path):
            logger.error(f"PKGBUILD not found at {pkgbuild_path}")
            return None

        pkgname = None
        pkgver = None
        pkgrel = "1"
        epoch = None
        source_urls = []
        project_url = None
        arch = ["any", "x86_64"]

        try:
            with open(pkgbuild_path, 'r', encoding='utf-8') as f:
                content = f.read()

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
                    line = re.sub(r'\$pkgname', pkgname or '', line)
                    line = re.sub(r'\$pkgver', pkgver or '', line)
                    if re.match(r'https?://', line): source_urls.append(line)

            if not source_urls:
                source_single_match = re.search(r'^\s*source\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content_no_comments, re.MULTILINE)
                if source_single_match:
                    source_url = source_single_match.group(1)
                    if pkgname: source_url = source_url.replace('$pkgname', pkgname)
                    if pkgver: source_url = source_url.replace('$pkgver', pkgver)
                    if re.match(r'https?://', source_url): source_urls.append(source_url)

            if not pkgname: logger.error("Missing pkgname in PKGBUILD")
            if not pkgver: logger.error("Missing pkgver in PKGBUILD")
            if not source_urls and not project_url: logger.error("No source URLs or project URL found in PKGBUILD")

            if pkgname and pkgver:
                return PkgbuildUpstreamDetails(
                    pkgname=pkgname, pkgver=pkgver, pkgrel=pkgrel, epoch=epoch,
                    source_urls=source_urls, project_url=project_url, arch=arch
                )

        except Exception as e:
            logger.exception(f"Error parsing PKGBUILD at {pkgbuild_path}: {str(e)}")

        return None

    def _identify_host_type_and_details(self, url: str) -> Tuple[HostType, Dict[str, Any]]:
        """
        Identifies the repository type from the URL and extracts relevant details.
        """
        if not url: return HostType.UNKNOWN, {"url": url}

        github_match = re.match(r"https?://(?:www\.)?github\.com/([^/]+)/([^/]+)(?:/.*)?", url)
        if github_match:
            owner, repo_name = github_match.groups()
            return HostType.GITHUB, {
                "owner": owner, "repo_name": repo_name, "url": url, "api_base_url": "https://api.github.com"
            }

        gitlab_match = re.match(r"https?://(?:www\.)?gitlab\.com/((?:[^/]+/)+[^/]+)(?:/.*)?", url)
        if gitlab_match:
            project_path = gitlab_match.group(1)
            return HostType.GITLAB, {
                "project_path": project_path, "url": url, "api_base_url": "https://gitlab.com"
            }

        gitlab_selfhosted_match = re.match(r"https?://([^/]+)/((?:[^/]+/)+[^/]+)(?:/.*)?", url)
        if gitlab_selfhosted_match and "gitlab" in gitlab_selfhosted_match.group(1).lower():
            domain = gitlab_selfhosted_match.group(1)
            project_path = gitlab_selfhosted_match.group(2)
            return HostType.GITLAB_SELF_HOSTED, {
                "domain": domain, "project_path": project_path, "url": url, "api_base_url": f"https://{domain}"
            }

        gitea_match = re.match(r"https?://([^/]+)/((?:[^/]+/)+[^/]+)(?:/.*)?", url)
        if gitea_match and "gitea" in gitea_match.group(1).lower():
            domain = gitea_match.group(1)
            project_path = gitea_match.group(2)
            return HostType.GITEA, {
                "domain": domain, "project_path": project_path, "url": url, "api_base_url": f"https://{domain}"
            }

        sourcehut_match = re.match(r"https?://git\.sr\.ht/~([^/]+)/([^/]+)", url)
        if sourcehut_match:
            namespace, repo = sourcehut_match.groups()
            return HostType.SOURCEHUT, {
                "namespace": namespace, "repo": repo, "url": url, "api_base_url": "https://git.sr.ht"
            }

        if any(url.endswith(ext) for ext in ['.tar.gz', '.zip', '.tgz', '.gz', '.bz2', '.xz', '.deb', '.rpm', '.pkg.tar.zst']):
            return HostType.GENERIC_DOWNLOAD, {"url": url}

        if re.match(r"https?://github\.com/([^/]+)/([^/]+)/releases/", url):
            release_match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/releases/", url)
            if release_match:
                owner, repo_name = release_match.groups()
                return HostType.GITHUB, {
                    "owner": owner, "repo_name": repo_name, "url": url, "api_base_url": "https://api.github.com"
                }

        return HostType.UNKNOWN, {"url": url}

    def _build_github_command_and_parser(self, repo_details: Dict[str, Any]) -> Tuple[Optional[List[str]], Optional[Callable[[str], Tuple[Optional[str], Dict[str, Any]]]]]:
        """
        Builds the shell command and returns the parser for GitHub API responses.
        """
        owner = repo_details.get("owner")
        repo_name = repo_details.get("repo_name")

        if not owner or not repo_name:
            logger.error("GitHub owner and repo_name missing from details.")
            return None, None

        command = [
            "curl", "-s", "-H", "Accept: application/vnd.github.v3+json",
            f"https://api.github.com/repos/{owner}/{repo_name}/releases/latest"
        ]

        def parser_func(output: str) -> Tuple[Optional[str], Dict[str, Any]]:
            try:
                data = json.loads(output)
                if "message" in data and data["message"] == "Not Found":
                    logger.error("GitHub repository not found or no releases.")
                    return None, {"error": "Repo not found or no releases"}

                tag_name = data.get("tag_name", "")
                if not tag_name:
                    logger.warning("No tag_name found in GitHub release data.")
                    return None, data

                version = tag_name.lstrip("v")
                release_date = data.get("published_at")
                changelog_url = data.get("html_url")

                logger.info(f"GitHub parsed version: {version} (from tag: {tag_name})")
                return version, {
                    "tag_name": tag_name, "version": version, "release_date": release_date,
                    "changelog_url": changelog_url, "raw": data
                }
            except json.JSONDecodeError:
                logger.error("Failed to parse GitHub API response as JSON.")
                return None, {"error": "JSON parse error"}
            except Exception as e:
                logger.exception(f"Error parsing GitHub response: {str(e)}")
                return None, {"error": str(e)}

        return command, parser_func

    def _build_gitlab_command_and_parser(self, repo_details: Dict[str, Any]) -> Tuple[Optional[List[str]], Optional[Callable[[str], Tuple[Optional[str], Dict[str, Any]]]]]:
        """
        Builds the shell command and returns the parser for GitLab API responses.
        """
        project_path = repo_details.get("project_path")
        api_base_url = repo_details.get("api_base_url", "https://gitlab.com")

        if not project_path:
            logger.error("GitLab project_path missing from details.")
            return None, None

        encoded_path = project_path.replace('/', '%2F')
        command = [
            "curl", "-s",
            f"{api_base_url}/api/v4/projects/{encoded_path}/releases?order_by=released_at&sort=desc&per_page=1"
        ]

        def parser_func(output: str) -> Tuple[Optional[str], Dict[str, Any]]:
            try:
                data = json.loads(output)
                if not data or not isinstance(data, list) or len(data) == 0:
                    logger.warning("No releases found in GitLab response.")
                    return None, {"error": "No releases"}

                release = data[0]
                tag_name = release.get("tag_name", "")
                if not tag_name:
                    logger.warning("No tag_name found in GitLab release data.")
                    return None, release

                version = tag_name.lstrip("v")
                release_date = release.get("released_at")
                changelog_url = release.get("description", "").split('\n')[0] if release.get("description") else release.get("web_url")

                logger.info(f"GitLab parsed version: {version} (from tag: {tag_name})")
                return version, {
                    "tag_name": tag_name, "version": version, "release_date": release_date,
                    "changelog_url": changelog_url, "raw": release
                }
            except json.JSONDecodeError:
                logger.error("Failed to parse GitLab API response as JSON.")
                return None, {"error": "JSON parse error"}
            except Exception as e:
                logger.exception(f"Error parsing GitLab response: {str(e)}")
                return None, {"error": str(e)}

        return command, parser_func

    def _extract_version_from_generic_url(self, url: str) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Attempts to extract a version string directly from a generic download URL.
        This is a heuristic and relies on common versioning patterns in filenames or paths.
        """
        if not url: return None, {}

        VERSION_PATTERNS = [
            re.compile(r'v?(\d+\.\d+\.\d+(?:[.-]\w+)?)', re.IGNORECASE),
            re.compile(r'v?(\d+\.\d+(?:[.-]\w+)?)', re.IGNORECASE),
            re.compile(r'v?(\d+(?:[.-]\w+)?)', re.IGNORECASE),
            re.compile(r'(\d{8}|\d{6})')
        ]

        path_segments_match = re.search(r"/(?:Tree|version|v)(\d+[\d.-]*[\w.-]*)/", url, re.IGNORECASE)
        if path_segments_match:
            version_raw_from_path = path_segments_match.group(1)
            version_processed = version_raw_from_path.split('-')[0]
            logger.info(f"Extracted version '{version_processed}' from URL path segment: {url}")
            return version_processed, {"source_url": url, "version_source": "url_path_segment"}

        filename = os.path.basename(url)
        for ext in ['.tar.gz', '.zip', '.tgz', '.gz', '.bz2', '.xz', '.deb', '.rpm', '.pkg.tar.zst']:
            if filename.endswith(ext):
                filename = filename[:-len(ext)]
                break

        for pattern in VERSION_PATTERNS:
            match_filename = pattern.search(filename)
            if match_filename:
                version = match_filename.group(1)
                version_processed = version.split('-')[0]
                logger.info(f"Extracted version '{version_processed}' from filename '{filename}' using pattern: {pattern.pattern}")
                return version_processed, {"source_url": url, "version_source": "filename_pattern"}

            match_url = pattern.search(url)
            if match_url:
                version = match_url.group(1)
                version_processed = version.split('-')[0]
                logger.info(f"Extracted version '{version_processed}' from full URL '{url}' using pattern: {pattern.pattern}")
                return version_processed, {"source_url": url, "version_source": "url_generic_pattern"}

        logger.warning(f"Could not extract version from generic URL: {url}")
        return None, {"source_url": url, "version_source": "none"}

    def _execute_shell_command(self, command: List[str]) -> Optional[str]:
        """
        Executes a shell command and returns its stdout if successful.
        This method is blocking and should be called from a separate thread/process
        when used in a GUI application.
        """
        try:
            logger.debug(f"Executing command: {' '.join(shlex.quote(c) for c in command)}")
            start_time = time.time()

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=15,
                check=False
            )

            elapsed = time.time() - start_time
            logger.debug(f"Command executed in {elapsed:.2f}s")

            if result.returncode == 0:
                return result.stdout
            else:
                logger.error(f"Command failed with exit code {result.returncode}: {result.stderr.strip()}")
        except FileNotFoundError:
            logger.error(f"Command '{command[0]}' not found. Is curl and bash installed?")
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out after 15 seconds: {' '.join(command)}")
        except Exception as e:
            logger.exception(f"Error executing command: {str(e)}")
        return None

    def check_for_updates(self, pkgbuild_path: str) -> Optional[UpstreamInfo]:
        """
        Checks for available updates for the PKGBUILD.
        This method should be called from a separate thread/process in the GUI.

        Returns:
            UpstreamInfo if an update is available, None otherwise
        """
        pkgbuild_id = f"{os.path.basename(pkgbuild_path)}-{os.path.getmtime(pkgbuild_path)}"
        cached_info = self.cache_manager.get_cached_update(pkgbuild_id)
        if cached_info:
            logger.info(f"Using cached update information for {pkgbuild_id}")
            return cached_info

        pkgbuild_details = self._parse_pkgbuild_for_upstream_info(pkgbuild_path)
        if not pkgbuild_details:
            logger.error(f"Could not parse PKGBUILD at {pkgbuild_path}")
            return None

        logger.info(f"Analyzing PKGBUILD: {pkgbuild_details.pkgname} (current version: {pkgbuild_details.pkgver})")

        candidate_urls = []
        if pkgbuild_details.project_url: candidate_urls.append(pkgbuild_details.project_url)
        candidate_urls.extend(pkgbuild_details.source_urls)

        for url in candidate_urls:
            logger.info(f"Checking URL: {url}")
            host_type, repo_details = self._identify_host_type_and_details(url)
            logger.debug(f"Identified host type: {host_type.value}")

            command: Optional[List[str]] = None
            parser_func: Optional[Callable[[str], Tuple[Optional[str], Dict[str, Any]]]] = None

            if host_type == HostType.GITHUB:
                command, parser_func = self._build_github_command_and_parser(repo_details)
            elif host_type in [HostType.GITLAB, HostType.GITLAB_SELF_HOSTED]:
                command, parser_func = self._build_gitlab_command_and_parser(repo_details)
            elif host_type == HostType.GENERIC_DOWNLOAD:
                found_version, metadata = self._extract_version_from_generic_url(url)
                if found_version:
                    upstream_info = UpstreamInfo(
                        host_type=host_type, version=found_version, repo_details=repo_details, raw_data=metadata
                    )
                    comparison = self.version_utils.compare_versions(pkgbuild_details.pkgver, found_version)
                    if comparison < 0:
                        self.cache_manager.set_cached_update(pkgbuild_id, upstream_info)
                        return upstream_info
                    elif comparison == 0:
                        logger.info(f"Generic download version '{found_version}' is up to date with PKGBUILD's '{pkgbuild_details.pkgver}'.")
                    else:
                         logger.warning(f"Generic download version '{found_version}' is older than PKGBUILD's '{pkgbuild_details.pkgver}'.")
                continue

            if command and parser_func:
                raw_command_output = self._execute_shell_command(command)
                if raw_command_output:
                    version, metadata = parser_func(raw_command_output)
                    found_version = version

                    if found_version:
                        if self.version_utils.is_prerelease(found_version):
                            logger.info(f"Found pre-release version: {found_version}. May be skipped based on config.")

                        comparison = self.version_utils.compare_versions(pkgbuild_details.pkgver, found_version)

                        if comparison < 0:
                            logger.info(f"UPDATE AVAILABLE: {pkgbuild_details.pkgname} {pkgbuild_details.pkgver} -> {found_version}")

                            # [~] NVDIntegration.check_cves call needs to be asynchronous from GUI.
                            # Calling it here means it runs blocking within the UpstreamChecker thread.
                            # When integrated with window.py, window.py should submit this call to a process pool.
                            cves = NVDIntegration.check_cves(pkgbuild_details.pkgname, pkgbuild_details.pkgver)
                            cve_info = f"{len(cves)} CVEs fixed" if cves else None

                            upstream_info = UpstreamInfo(
                                host_type=host_type, version=found_version, release_date=metadata.get("release_date"),
                                changelog_url=metadata.get("changelog_url", url), cve_fix_info=cve_info,
                                repo_details=repo_details, raw_data=metadata
                            )

                            self.cache_manager.set_cached_update(pkgbuild_id, upstream_info)
                            return upstream_info

                        elif comparison == 0:
                            logger.info(f"Version is up to date: {pkgbuild_details.pkgver}")
                        else:
                            logger.warning(f"Upstream version is older? Current: {pkgbuild_details.pkgver}, Upstream: {found_version}")

        logger.info(f"No updates found for {pkgbuild_details.pkgname} after checking all candidate URLs.")
        return None

    def detect_security_updates(self, pkgname: str, pkgver: str) -> List[Dict[str, Any]]:
        """
        Detects security updates for the package using NVDIntegration.
        This method should be called from a separate thread/process in the GUI.
        """
        logger.info(f"Checking security updates for {pkgname} version {pkgver}")
        return NVDIntegration.check_cves(pkgname, pkgver)

    def schedule_auto_checks(self, interval_hours: int = 24):
        """
        Schedules automatic update checks.
        This is a placeholder for actual scheduling mechanism in the GUI's main loop.
        """
        logger.info(f"Scheduled automatic update checks every {interval_hours} hours (placeholder)")

    def notify_critical_update(self, pkgname: str, cves: List[Dict[str, Any]]):
        """
        Notifies about critical security updates.
        This is a placeholder for actual notification mechanism in the GUI.
        """
        if not cves: return

        severity_counts = {}
        for cve in cves:
            severity = cve.get('severity', 'UNKNOWN')
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        summary = ", ".join([f"{count} {severity}" for severity, count in severity_counts.items()])
        logger.critical(f"CRITICAL SECURITY UPDATE for {pkgname}: {len(cves)} CVEs ({summary}) (placeholder for GUI notification)")


# --- NVD Integration ---

class NVDIntegration:
    """Integration with the National Vulnerability Database (NVD)"""

    NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

    @classmethod
    def _execute_curl_command(cls, url: str) -> Optional[str]:
        """
        Helper to execute curl command for NVD API.
        This is a blocking call and should be managed by a separate thread/process in a GUI.
        """
        try:
            cmd = ["curl", "-s", url]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=20, check=False
            )
            if result.returncode == 0:
                return result.stdout
            else:
                logger.error(f"NVD curl command failed with exit code {result.returncode}: {result.stderr.strip()}")
        except Exception as e:
            logger.error(f"Error executing NVD curl command: {e}")
        return None

    @classmethod
    def check_cves(cls, pkgname: str, version: str) -> List[Dict[str, Any]]:
        """
        Checks for CVEs for a specific package and version using curl.
        This method is blocking and should be called from a separate thread/process in the GUI.
        """
        logger.info(f"Checking CVEs for {pkgname} version {version} via NVD curl (blocking call).")

        try:
            search_query_url = f"{cls.NVD_API_URL}?keywordSearch={pkgname}&resultsPerPage=10"
            logger.debug(f"NVD search URL: {search_query_url}")

            raw_output = cls._execute_curl_command(search_query_url)
            if not raw_output: return []

            try:
                data = json.loads(raw_output)
                vulnerabilities = data.get('vulnerabilities', [])

                relevant_cves = []
                for vuln_entry in vulnerabilities:
                    cve = vuln_entry.get('cve', {})
                    cve_id = cve.get('id', 'N/A')
                    descriptions = cve.get('descriptions', [])
                    description_text = " ".join([d.get('value', '') for d in descriptions if d.get('lang') == 'en'])

                    if pkgname.lower() in description_text.lower() and version in description_text:
                        severity = "HIGH" # Placeholder, actual NVD parsing is more complex
                        relevant_cves.append({"id": cve_id, "severity": severity, "description": description_text})

                logger.info(f"Found {len(relevant_cves)} potential relevant CVEs for {pkgname} {version}.")
                return relevant_cves

            except json.JSONDecodeError:
                logger.error("Failed to parse NVD API response as JSON.")
                return []

        except Exception as e:
            logger.exception(f"Error checking CVEs via NVD curl: {str(e)}")
            return []


# Example usage (for testing this module directly)
if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)

    test_pkgbuild_content = """
    pkgname=my-test-package
    pkgver=1.0.0
    pkgrel=1
    arch=('x86_64')
    url="https://github.com/someuser/some-repo"
    license=('GPL')
    depends=('bash')
    source=(
        "https://github.com/someuser/some-repo/releases/download/v${pkgver}/my-test-package-${pkgver}.tar.gz"
        "https://gitlab.com/anotheruser/another-project/-/archive/v1.2.3/another-project-v1.2.3.tar.gz"
        "https://example.com/downloads/my_app_v2.0.0.tar.gz"
    )
    sha256sums=('SKIP')
    """
    test_pkgbuild_path = "/tmp/test_PKGBUILD_upstream"
    with open(test_pkgbuild_path, "w", encoding='utf-8') as f:
        f.write(test_pkgbuild_content)

    checker = UpstreamChecker(cache_ttl=300)

    print("\n--- PKGBUILD Parsing Test ---")
    details = checker._parse_pkgbuild_for_upstream_info(test_pkgbuild_path)
    if details:
        print(f"Parsed Pkgname: {details.pkgname}")
        print(f"Parsed Pkgver: {details.pkgver}")
        print(f"Parsed Source URLs: {details.source_urls}")
        print(f"Parsed Project URL: {details.project_url}")
    else:
        print("Failed to parse PKGBUILD.")

    print("\n--- URL Identification Test ---")
    urls_to_test = [
        "https://github.com/johnpetersa19/unix-tree-master-pt_br",
        "https://gitlab.com/OldManProgrammer/unix-tree",
        "https://mygitlab.com/myuser/myproject",
        "https://gitea.example.org/user/repo",
        "https://git.sr.ht/~user/project",
        "https://example.com/downloads/software-1.2.3.tar.gz",
        "ftp://mirror.example.com/repo/package-4.5.6.zip",
        "https://www.google.com"
    ]
    for test_url in urls_to_test:
        host_type, repo_details = checker._identify_host_type_and_details(test_url)
        print(f"URL: {test_url} -> HostType: {host_type.value}, Details: {repo_details}")

    print("\n--- Main Update Check Test ---")
    # This will simulate a check, but actual network calls may fail if URLs are invalid or API limits hit.
    update_info = checker.check_for_updates(test_pkgbuild_path)

    if update_info:
        print(f"\nUpdate available for {details.pkgname if details else 'N/A'}:")
        print(f"  Host Type: {update_info.host_type.value}")
        print(f"  New version: {update_info.version}")
        print(f"  Release date: {update_info.release_date or 'N/A'}")
        print(f"  Changelog: {update_info.changelog_url or 'N/A'}")
        if update_info.cve_fix_info:
            print(f"  Security fixes: {update_info.cve_fix_info}")
    else:
        print("\nNo updates found.")

    if details:
        print(f"\n--- Security Update Check Test for {details.pkgname} {details.pkgver} ---")
        cves = checker.detect_security_updates(details.pkgname, details.pkgver)
        if cves:
            print(f"Found {len(cves)} potential security vulnerabilities:")
            for i, cve in enumerate(cves[:3]):
                print(f"  CVE-{i+1}: {cve.get('id', 'N/A')} - Severity: {cve.get('severity', 'N/A')}")
            if len(cves) > 3:
                print(f"  ... and {len(cves)-3} more (showing top 3)")
        else:
            print("No potential CVEs found for this package/version.")

    os.remove(test_pkgbuild_path)
    print(f"\nCleaned up {test_pkgbuild_path}.")
