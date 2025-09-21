import os
import re
import subprocess
import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

# Basic logging configuration for this module
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("upstream_checker")

@dataclass
class UpstreamUpdateInfo:
    """Stores information about a detected upstream update."""
    pkgname: str
    current_version: str
    version: str
    release_date: Optional[str] = None
    changelog_url: Optional[str] = None
    download_url: Optional[str] = None
    source_type: str = "Unknown" # e.g., 'GitHub', 'GitLab', 'Custom'
    cve_fix_info: Optional[str] = None # Information about CVEs fixed in this version

@dataclass
class CacheEntry:
    """Represents an entry in the cache."""
    timestamp: datetime
    data: Any # Can be UpstreamUpdateInfo, AUR data, etc.

class CacheManager:
    """
    Manages caching of upstream information to avoid redundant network requests.
    """
    def __init__(self, cache_timeout_hours: int = 6):
        self.cache: Dict[str, CacheEntry] = {}
        self.cache_timeout = timedelta(hours=cache_timeout_hours)
        logger.info(f"CacheManager initialized with timeout: {self.cache_timeout}")

    def get(self, key: str) -> Optional[Any]:
        """Retrieves data from cache if not expired."""
        if key in self.cache:
            entry = self.cache[key]
            if datetime.utcnow() - entry.timestamp < self.cache_timeout:
                logger.debug(f"Cache hit for '{key}'.")
                return entry.data
            else:
                logger.debug(f"Cache for '{key}' expired. Removing.")
                del self.cache[key]
        logger.debug(f"Cache miss for '{key}'.")
        return None

    def set(self, key: str, data: Any):
        """Stores data in cache with current timestamp."""
        self.cache[key] = CacheEntry(timestamp=datetime.utcnow(), data=data)
        logger.debug(f"Key '{key}' added to cache.")

    def invalidate(self, key: str):
        """Removes a specific key from cache."""
        if key in self.cache:
            del self.cache[key]
            logger.debug(f"Key '{key}' invalidated from cache.")

    def clear(self):
        """Clears the entire cache."""
        self.cache.clear()
        logger.info("Cache cleared.")

class NVDIntegration:
    """
    Simulates integration with the National Vulnerability Database (NVD)
    or other CVE databases to check for fixes in new versions.
    """
    def __init__(self):
        logger.info("NVDIntegration initialized (mock).")

    def check_cves(self, pkgname: str, version: str) -> Optional[str]:
        """
        [ ] Placeholder for actual NVD/CVE API integration.
        Simulates checking if a given package version fixes any known CVEs.
        """
        logger.info(f"Simulating CVE check for {pkgname} v{version}...")
        # In a real application, this would involve:
        # 1. Calling NVD API or similar with pkgname and version.
        # 2. Parsing the response to find relevant CVEs and their status.
        # 3. Determining if the new version contains fixes for existing CVEs.

        # Dummy logic for demonstration:
        if "firefox" in pkgname.lower() and "120.0" in version:
            return "Fixes CVE-2023-4567 (Critical)"
        if "nginx" in pkgname.lower() and "1.25.0" in version:
            return "Fixes CVE-2023-9876 (High)"
        return None

class UpstreamChecker:
    """
    Identifies, builds commands for, executes, and analyzes upstream update information
    from various sources (GitHub, GitLab, custom URLs).
    """

    def __init__(self):
        self.cache_manager = CacheManager()
        self.nvd_integration = NVDIntegration()
        logger.info("UpstreamChecker initialized.")

    def check_for_updates(self, pkgbuild_path: str) -> Optional[UpstreamUpdateInfo]:
        """
        Main method to check for upstream updates for a given PKGBUILD.
        This method is designed to be called in a separate thread/process.
        """
        if not os.path.exists(pkgbuild_path):
            logger.error(f"PKGBUILD not found: {pkgbuild_path}")
            return None

        # 1. Parse PKGBUILD to get current info and source URLs
        pkgname, current_version, sources, project_url = self._parse_pkgbuild_for_upstream_info(pkgbuild_path)
        if pkgname == "unknown" or current_version == "unknown" or not (sources or project_url):
            logger.warning(f"Could not extract sufficient upstream info from PKGBUILD: {pkgbuild_path}")
            return None

        cache_key = f"upstream_check_{pkgname}_{current_version}"
        cached_info = self.cache_manager.get(cache_key)
        if cached_info:
            return cached_info

        # 2. Determine upstream source type and construct commands
        upstream_source_type, base_url, repo_path = self._determine_upstream_source(sources, project_url)
        if not base_url:
            logger.warning(f"Could not determine upstream source for {pkgname}.")
            return None

        # 3. Fetch upstream version (e.g., from Git tags, API, RSS feed)
        latest_version_info = self._fetch_latest_upstream_version(upstream_source_type, base_url, repo_path)
        if not latest_version_info:
            logger.info(f"No new upstream version found for {pkgname}.")
            return None

        latest_version = latest_version_info.get("version")
        if not latest_version:
            logger.warning(f"Could not extract latest version from upstream for {pkgname}.")
            return None

        # Compare versions
        if self._compare_versions(current_version, latest_version):
            logger.info(f"New upstream version found for {pkgname}: {latest_version}")

            # 4. Check for CVE fixes in the new version (blocking call in this thread)
            cve_fix_info = self.nvd_integration.check_cves(pkgname, latest_version)

            update_info = UpstreamUpdateInfo(
                pkgname=pkgname,
                current_version=current_version,
                version=latest_version,
                release_date=latest_version_info.get("release_date"),
                changelog_url=latest_version_info.get("changelog_url", project_url),
                download_url=latest_version_info.get("download_url"),
                source_type=upstream_source_type,
                cve_fix_info=cve_fix_info
            )
            self.cache_manager.set(cache_key, update_info)
            return update_info
        else:
            logger.info(f"No newer upstream version than {current_version} found for {pkgname}.")
            # Cache "no update" status briefly to avoid repeated checks
            self.cache_manager.set(cache_key, None) # Store None to indicate no update
            return None

    def _parse_pkgbuild_for_upstream_info(self, pkgbuild_path: str) -> Tuple[str, str, List[str], Optional[str]]:
        """
        Parses PKGBUILD to extract pkgname, pkgver, source array, and URL.
        Reuses logic from `file_utils.py` where appropriate, or re-implements here for independence.
        """
        pkgname = "unknown"
        pkgver = "unknown"
        sources: List[str] = []
        project_url: Optional[str] = None

        try:
            with open(pkgbuild_path, 'r', encoding='utf-8') as f:
                content = f.read()

            content_no_comments = re.sub(r'#.*$', '', content, flags=re.MULTILINE)

            pkgname_match = re.search(r'^\s*pkgname\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content_no_comments, re.MULTILINE)
            if pkgname_match: pkgname = pkgname_match.group(1)

            pkgver_match = re.search(r'^\s*pkgver\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content_no_comments, re.MULTILINE)
            if pkgver_match: pkgver = pkgver_match.group(1)

            url_match = re.search(r'^\s*url\s*=\s*(?:\'|")?([^\s\'"]+)(?:\'|")?', content_no_comments, re.MULTILINE)
            if url_match: project_url = url_match.group(1)

            source_match = re.search(r'^\s*source\s*=\s*\((?P<sources>[^)]*)\)', content_no_comments, re.MULTILINE | re.DOTALL)
            if source_match:
                raw_sources = source_match.group('sources').splitlines()
                for line in raw_sources:
                    line = line.strip().strip("'\"")
                    if line and not line.startswith('#'):
                        # Perform variable substitution here for sources
                        line = line.replace('$pkgname', pkgname).replace('$pkgver', pkgver)
                        sources.append(line)
            else: # Handle single-line source
                single_source_match = re.search(r'^\s*source\s*=\s*(?P<source_url>[^\s\'"]+)(?:\'|")?', content_no_comments, re.MULTILINE)
                if single_source_match:
                    source_url = single_source_match.group('source_url').strip("'\"")
                    source_url = source_url.replace('$pkgname', pkgname).replace('$pkgver', pkgver)
                    sources.append(source_url)


        except Exception as e:
            logger.error(f"Error parsing PKGBUILD {pkgbuild_path} for upstream info: {e}")

        return pkgname, pkgver, sources, project_url

    def _determine_upstream_source(self, sources: List[str], project_url: Optional[str]) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Determines the type of upstream source (GitHub, GitLab, Custom URL)
        and extracts relevant base URL and repository path.
        """
        potential_urls = sources + ([project_url] if project_url else [])
        for url in potential_urls:
            if not url: continue

            # GitHub
            github_match = re.search(r'github\.com/([^/]+)/([^/]+)(?:/.*)?', url)
            if github_match:
                owner = github_match.group(1)
                repo = github_match.group(2)
                return "GitHub", f"https://api.github.com/repos/{owner}/{repo}", f"{owner}/{repo}"

            # GitLab
            gitlab_match = re.search(r'(gitlab\.com|code\.example\.com)/([^/]+)/([^/]+)(?:/.*)?', url)
            if gitlab_match:
                host = gitlab_match.group(1)
                owner = gitlab_match.group(2)
                repo = gitlab_match.group(3)
                # GitLab API URL can vary, for gitlab.com it's usually /api/v4/projects/{id} or /api/v4/projects/{owner}%2F{repo}
                # For simplicity, we'll return the base repo URL and let fetcher figure it out
                return "GitLab", f"https://{host}/{owner}/{repo}", f"{owner}/{repo}"

            # Other custom URLs might require more advanced parsing or user configuration
            # For now, treat as 'Custom'
            if url.startswith("http") or url.startswith("https"):
                return "Custom", url, None # Base URL is the full URL

        return "Unknown", None, None

    def _fetch_latest_upstream_version(self, source_type: str, base_url: str, repo_path: Optional[str]) -> Optional[Dict[str, str]]:
        """
        [x] Implement fetching upstream version logic for various sources.
        Fetches the latest version information from the determined upstream source.
        """
        if source_type == "GitHub" and repo_path:
            return self._fetch_from_github(repo_path)
        elif source_type == "GitLab" and repo_path:
            return self._fetch_from_gitlab(base_url, repo_path)
        elif source_type == "Custom":
            return self._fetch_from_custom_url(base_url)
        return None

    def _fetch_from_github(self, repo_path: str) -> Optional[Dict[str, str]]:
        """Fetches latest release/tag from GitHub API."""
        api_url = f"https://api.github.com/repos/{repo_path}/releases/latest"
        logger.debug(f"Fetching GitHub latest release from: {api_url}")
        try:
            # Using curl directly as subprocess to avoid external 'requests' dependency
            # A real implementation would add headers for auth/rate limiting
            result = subprocess.run(
                ['curl', '-s', api_url],
                capture_output=True,
                text=True,
                timeout=15,
                check=True
            )
            release_data = json.loads(result.stdout)
            version = release_data.get('tag_name', '').lstrip('vV') # Remove 'v' prefix if present
            published_at = release_data.get('published_at')
            html_url = release_data.get('html_url')

            if version:
                return {
                    "version": version,
                    "release_date": published_at,
                    "changelog_url": html_url, # Link to release page
                    "download_url": release_data.get('tarball_url')
                }
        except subprocess.CalledProcessError as e:
            logger.error(f"GitHub API call failed: {e.stderr.strip()}")
        except subprocess.TimeoutExpired:
            logger.error(f"GitHub API call timed out for {repo_path}.")
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON response from GitHub for {repo_path}.")
        except Exception as e:
            logger.exception(f"Unexpected error fetching from GitHub for {repo_path}: {e}")
        return None

    def _fetch_from_gitlab(self, base_url: str, repo_path: str) -> Optional[Dict[str, str]]:
        """Fetches latest release/tag from GitLab API."""
        # GitLab API is more complex, typically needs project ID or URL-encoded path
        # Example: https://gitlab.com/api/v4/projects/group%2Fproject/releases/permalink/latest
        # For simplicity, we'll try to guess a common API endpoint or parse RSS if available.
        # A more robust solution would first fetch project ID.

        # Heuristic: try latest release endpoint if base_url is for the UI/repo page
        # If base_url is https://gitlab.com/owner/repo, then api_url might be
        # https://gitlab.com/api/v4/projects/owner%2Frepo/releases/latest
        # This requires the repo_path to be URL-encoded for the API.
        encoded_repo_path = repo_path.replace('/', '%2F')
        api_url = f"{base_url.split('/')[0]}//{base_url.split('/')[2]}/api/v4/projects/{encoded_repo_path}/releases/permalink/latest"
        logger.debug(f"Fetching GitLab latest release from: {api_url}")

        try:
            result = subprocess.run(
                ['curl', '-s', api_url],
                capture_output=True,
                text=True,
                timeout=15,
                check=True
            )
            release_data = json.loads(result.stdout)
            version = release_data.get('tag_name', '').lstrip('vV')
            released_at = release_data.get('released_at')
            web_url = release_data.get('app.url')

            if version:
                return {
                    "version": version,
                    "release_date": released_at,
                    "changelog_url": web_url,
                    "download_url": release_data.get('assets', {}).get('sources', [{}])[0].get('url') # Try to get first source asset
                }
        except subprocess.CalledProcessError as e:
            logger.error(f"GitLab API call failed: {e.stderr.strip()}")
        except subprocess.TimeoutExpired:
            logger.error(f"GitLab API call timed out for {repo_path}.")
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON response from GitLab for {repo_path}.")
        except Exception as e:
            logger.exception(f"Unexpected error fetching from GitLab for {repo_path}: {e}")
        return None

    def _fetch_from_custom_url(self, url: str) -> Optional[Dict[str, str]]:
        """
        [ ] Implement custom URL parsing (e.g., RSS, HTML scraping, or just latest version from URL pattern).
        Fetches latest version info from a custom URL. This is the most challenging
        and often requires site-specific logic (e.g., RSS feed parsing, HTML scraping).
        For now, this is a basic placeholder.
        """
        logger.warning(f"Fetching from custom URL '{url}' (basic placeholder, may not work reliably).")
        # Possible strategies:
        # 1. Look for common version patterns in the URL itself (e.g., /download/vX.Y.Z/)
        # 2. If it's a raw file (e.g., .tar.gz), try to parse the filename.
        # 3. If it's an HTML page, attempt a basic regex scrape for version numbers.
        # 4. If it's an RSS/Atom feed, parse the XML.

        # Dummy logic: Assume the URL itself contains the version or can be derived.
        # e.g., "http://example.com/software/myapp-1.2.3.tar.gz"
        version_match = re.search(r'v?(\d+\.\d+(\.\d+)*(-\w+\d*)?)', url)
        if version_match:
            version = version_match.group(1)
            return {
                "version": version,
                "release_date": "N/A", # Cannot easily determine from URL
                "changelog_url": url,
                "download_url": url
            }
        logger.warning(f"Could not extract version from custom URL: {url}")
        return None

    def _compare_versions(self, current_version: str, latest_version: str) -> bool:
        """
        [x] Implement lógica de comparação de versões robusta.
        Compares two version strings (e.g., "1.0.0-1", "1.0.1").
        Handles common versioning schemes used in Arch Linux.
        Returns True if `latest_version` is newer than `current_version`.
        """
        # Remove 'r' or 'git' prefixes, and handle pkgrel
        def normalize_version(v_str: str) -> Tuple[List[int], int]:
            v_str = v_str.lower().split('::')[0] # Remove potential AUR source prefixes
            v_str = re.sub(r'^(r\d+\.)?(git|svn|hg|beta|alpha|rc|pre)', '', v_str) # Remove common devel/release prefixes

            parts = v_str.split('-')
            version_numbers_str = parts[0]
            pkgrel = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

            version_components = []
            for part in version_numbers_str.split('.'):
                if part.isdigit():
                    version_components.append(int(part))
                else: # Handle mixed alphanumeric parts like "1.0.0.r123.gabcde" or "1.0.0b1"
                    # Simple heuristic: take leading digits for comparison, ignore text
                    sub_parts = re.findall(r'(\d+)', part)
                    if sub_parts:
                        version_components.append(int(sub_parts[0]))
                    else:
                        version_components.append(0) # Fallback

            return version_components, pkgrel

        current_v_nums, current_pkgrel = normalize_version(current_version)
        latest_v_nums, latest_pkgrel = normalize_version(latest_version)

        # Compare version numbers
        if latest_v_nums > current_v_nums:
            return True
        elif latest_v_nums < current_v_nums:
            return False
        else: # Version numbers are equal, compare pkgrel
            return latest_pkgrel > current_pkgrel

    def invalidate_cache(self, pkgname: Optional[str] = None):
        """
        Invalidates cache entries. If pkgname is provided, invalidates for that package.
        Otherwise, clears the entire cache.
        """
        if pkgname:
            # Need a more robust cache key for package-specific invalidation if version is in key
            for key in list(self.cache_manager.cache.keys()):
                if key.startswith(f"upstream_check_{pkgname}_"):
                    self.cache_manager.invalidate(key)
        else:
            self.cache_manager.clear()


# Exemplo de uso (para testar este módulo diretamente)
if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG) # Habilitar logs DEBUG para teste

    # Criar um PKGBUILD dummy para teste
    test_pkgbuild_content_github = """
    # Contributor: Example User
    pkgname=my-github-app
    pkgver=1.0.0
    pkgrel=1
    arch=('x86_64')
    url="https://github.com/octocat/Spoon-Knife"
    license=('MIT')
    depends=('bash')
    source=("https://github.com/octocat/Spoon-Knife/archive/v$pkgver.tar.gz")
    sha256sums=('SKIP')
    """
    test_pkgbuild_path_github = "/tmp/test_PKGBUILD_github"
    os.makedirs(os.path.dirname(test_pkgbuild_path_github), exist_ok=True)
    with open(test_pkgbuild_path_github, "w", encoding='utf-8') as f:
        f.write(test_pkgbuild_content_github)

    test_pkgbuild_content_gitlab = """
    # Contributor: Example User
    pkgname=my-gitlab-app
    pkgver=1.0.0
    pkgrel=1
    arch=('x86_64')
    url="https://gitlab.com/gitlab-org/gitlab-runner"
    license=('MIT')
    depends=('bash')
    source=("https://gitlab.com/gitlab-org/gitlab-runner/-/archive/v$pkgver/gitlab-runner-v$pkgver.tar.gz")
    sha256sums=('SKIP')
    """
    test_pkgbuild_path_gitlab = "/tmp/test_PKGBUILD_gitlab"
    os.makedirs(os.path.dirname(test_pkgbuild_path_gitlab), exist_ok=True)
    with open(test_pkgbuild_path_gitlab, "w", encoding='utf-8') as f:
        f.write(test_pkgbuild_content_gitlab)

    test_pkgbuild_content_custom = """
    # Contributor: Example User
    pkgname=my-custom-app
    pkgver=2.5.0
    pkgrel=1
    arch=('x86_64')
    url="http://ftp.gnu.org/gnu/sed/sed-4.9.tar.xz" # Older version for testing update detection
    license=('GPL')
    depends=('bash')
    source=("http://ftp.gnu.org/gnu/sed/sed-$pkgver.tar.xz")
    sha256sums=('SKIP')
    """
    test_pkgbuild_path_custom = "/tmp/test_PKGBUILD_custom"
    os.makedirs(os.path.dirname(test_pkgbuild_path_custom), exist_ok=True)
    with open(test_pkgbuild_path_custom, "w", encoding='utf-8') as f:
        f.write(test_pkgbuild_content_custom)


    checker = UpstreamChecker()

    print("\n--- Testing GitHub Upstream Check ---")
    update_github = checker.check_for_updates(test_pkgbuild_path_github)
    if update_github:
        print(f"GitHub Update Found for {update_github.pkgname}: {update_github.current_version} -> {update_github.version}")
        print(f"  Release Date: {update_github.release_date}, Changelog: {update_github.changelog_url}")
        if update_github.cve_fix_info: print(f"  CVE Info: {update_github.cve_fix_info}")
    else:
        print("No GitHub update found or an error occurred.")


    print("\n--- Testing GitLab Upstream Check ---")
    update_gitlab = checker.check_for_updates(test_pkgbuild_path_gitlab)
    if update_gitlab:
        print(f"GitLab Update Found for {update_gitlab.pkgname}: {update_gitlab.current_version} -> {update_gitlab.version}")
        print(f"  Release Date: {update_gitlab.release_date}, Changelog: {update_gitlab.changelog_url}")
        if update_gitlab.cve_fix_info: print(f"  CVE Info: {update_gitlab.cve_fix_info}")
    else:
        print("No GitLab update found or an error occurred.")

    print("\n--- Testing Custom URL Upstream Check (GNU Sed - should detect update to 4.9 or higher) ---")
    # For this test, manually update the pkgver in the dummy PKGBUILD to trigger a "new update"
    # Example: change pkgver to 4.8 in the dummy, then run the check.
    # The URL itself contains 4.9. So if current_version is <= 4.8, it should detect 4.9.
    # If pkgver is 4.9 already, it should detect no update.
    update_custom = checker.check_for_updates(test_pkgbuild_path_custom)
    if update_custom:
        print(f"Custom URL Update Found for {update_custom.pkgname}: {update_custom.current_version} -> {update_custom.version}")
        print(f"  Release Date: {update_custom.release_date}, Changelog: {update_custom.changelog_url}")
    else:
        print("No Custom URL update found or an error occurred (or version is current).")


    print("\n--- Testing Version Comparison ---")
    print(f"1.0.0 vs 1.0.1: {checker._compare_versions('1.0.0', '1.0.1')}") # True
    print(f"1.0.1 vs 1.0.0: {checker._compare_versions('1.0.1', '1.0.0')}") # False
    print(f"1.0.0-1 vs 1.0.0-2: {checker._compare_versions('1.0.0-1', '1.0.0-2')}") # True
    print(f"1.0.0-2 vs 1.0.0-1: {checker._compare_versions('1.0.0-2', '1.0.0-1')}") # False
    print(f"1.0.0 vs 1.0.0: {checker._compare_versions('1.0.0', '1.0.0')}") # False
    print(f"1.0beta1 vs 1.0: {checker._compare_versions('1.0beta1', '1.0')}") # True (normalized)
    print(f"1.0.0 vs 1.0.0.r1.g12345: {checker._compare_versions('1.0.0', '1.0.0.r1.g12345')}") # False (often treated as same for stable check)


    # Limpar arquivos dummy
    os.remove(test_pkgbuild_path_github)
    os.rmdir(os.path.dirname(test_pkgbuild_path_github))
    os.remove(test_pkgbuild_path_gitlab)
    os.rmdir(os.path.dirname(test_pkgbuild_path_gitlab))
    os.remove(test_pkgbuild_path_custom)
    os.rmdir(os.path.dirname(test_pkgbuild_path_custom))

    print("\n--- UpstreamChecker Test Complete ---")
